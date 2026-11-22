import logging
import os
import mysql.connector
import spotify_client
from mysql.connector import errorcode
from dotenv import load_dotenv
from fastapi import Request, Depends, FastAPI, HTTPException, Path, Query, Response
from fastapi.responses import JSONResponse
from schemas import (SPOTIFY_ID_PATTERN, ArtistOut, PreferencesIn, PreferencesOut, TrackOut, UserCreate, UserOut, UserUpdate, FavoriteArtistIn, FavoriteArtistOut, FavoriteTrackIn, FavoriteTrackOut)
from configuration.connections import DatabaseConnection

logger = logging.getLogger("uvicorn.error")

load_dotenv() # carga las variables del archivo .env


app = FastAPI(
    title="Spotify Users API",
    description = "API REST para gestionar usuarios, sus preferencias musicales " \
                  "y sus canciones y artistas favoritos, integrada con Spotify y MySQL.",
    version="1.0.0",
)


@app.exception_handler(mysql.connector.Error)
async def mysql_error_handler(request: Request, exc: mysql.connector.Error):
    # Cualquier error de MySQL no capturado en un endpoint acaba aquí:
    # se registra el detalle en el servidor y el cliente recibe un 503 genérico
    logger.exception("Error de MySQL en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=503, content={"detail": "Error de base de datos"})


async def get_cursor():
    """Abre una conexión por petición y la cierra al terminar."""
    mydb = DatabaseConnection(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )
    try:
        conn = await mydb.get_db_connection()
    except mysql.connector.Error:
        raise HTTPException(status_code=503, detail="No se pudo conectar con la base de datos")
    cursor = conn.cursor(dictionary=True)
    try:
        yield conn, cursor
    finally:
        cursor.close()
        conn.close()
        
@app.get("/health", tags=["Sistema"],summary="Comprueba el estado de la API y de MySQL")
async def health(db=Depends(get_cursor)):
    conn, cursor = db
    cursor.execute("SELECT 1 AS ok")
    return {"status": "ok", "database": cursor.fetchone()["ok"] == 1}


# Columnas que se devuelven al cliente. Es una constante del código, no un dato
# del usuario, así que interpolarla con f-string no abre la puerta a inyección SQL.
USER_COLUMNS = "id, username, email, full_name, created_at, updated_at"


def get_user_or_404(cursor, user_id: int) -> dict:
    cursor.execute(f"SELECT {USER_COLUMNS} FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail=f"Usuario {user_id} no encontrado")
    return user


def handle_integrity_error(conn, e: mysql.connector.IntegrityError):
    conn.rollback()
    # username y email son UNIQUE en la tabla: un duplicado es un conflicto (409)
    if e.errno == errorcode.ER_DUP_ENTRY:
        raise HTTPException(status_code=409, detail="El username o el email ya están en uso")
    raise HTTPException(status_code=400, detail="Datos inválidos")


@app.post("/users", response_model=UserOut, status_code=201, tags=["Usuarios"],
          summary="Crea un usuario")
async def create_user(user: UserCreate, db=Depends(get_cursor)):
    conn, cursor = db
    try:
        # Consulta parametrizada (%s); el driver escapa los valores
        cursor.execute(
            "INSERT INTO users (username, email, full_name) VALUES (%s, %s, %s)",
            (user.username, user.email, user.full_name),
        )
        conn.commit()
    except mysql.connector.IntegrityError as e:
        handle_integrity_error(conn, e)
    # Se relee la fila para devolver el id y los timestamps generados por MySQL
    return get_user_or_404(cursor, cursor.lastrowid)


@app.get("/users", response_model=list[UserOut], tags=["Usuarios"],
         summary="Lista usuarios (paginado)")
async def list_users(
    limit: int = Query(20, ge=1, le=100), # tope de 100 para no devolver tablas enteras
    offset: int = Query(0, ge=0),
    db=Depends(get_cursor),
):
    conn, cursor = db
    cursor.execute(f"SELECT {USER_COLUMNS} FROM users ORDER BY id LIMIT %s OFFSET %s",
                   (limit, offset))
    return cursor.fetchall()


@app.get("/users/{user_id}", response_model=UserOut, tags=["Usuarios"],
         summary="Obtiene un usuario")
async def get_user(user_id: int = Path(..., ge=1), db = Depends(get_cursor)):
    conn, cursor = db
    return get_user_or_404(cursor, user_id)


@app.put("/users/{user_id}", response_model=UserOut, tags=["Usuarios"],
         summary="Actualiza un usuario (sustitución completa)")
async def update_user(user: UserUpdate, user_id: int = Path(..., ge=1),
                      db = Depends(get_cursor)):
    conn, cursor = db
    # Se comprueba antes de actualizar porque en un UPDATE el rowcount cuenta las filas
    # *modificadas*: si los datos no cambian vale 0 aunque el usuario exista
    get_user_or_404(cursor, user_id)
    try:
        cursor.execute(
            "UPDATE users SET username = %s, email = %s, full_name = %s WHERE id = %s",
            (user.username, user.email, user.full_name, user_id),
        )
        conn.commit()
    except mysql.connector.IntegrityError as e:
        handle_integrity_error(conn, e)
    # updated_at lo actualiza MySQL solo (ON UPDATE CURRENT_TIMESTAMP)
    return get_user_or_404(cursor, user_id)


@app.delete("/users/{user_id}", status_code=204, tags=["Usuarios"],
            summary="Elimina un usuario y sus preferencias y favoritos")
async def delete_user(user_id: int = Path(..., ge=1), db=Depends(get_cursor)):
    conn, cursor = db
    # ON DELETE CASCADE borra también sus géneros y favoritos, pero no la caché
    # de canciones y artistas, que puede estar compartida con otros usuarios
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    # En un DELETE el rowcount sí es fiable: 0 significa que no existía
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Usuario {user_id} no encontrado")
    return Response(status_code=204) # 204 = éxito sin cuerpo


def get_genres(cursor, user_id: int) -> list[str]:
    cursor.execute("SELECT genre FROM user_genres WHERE user_id = %s ORDER BY genre",
                   (user_id,))
    return [row["genre"] for row in cursor.fetchall()]


@app.get("/users/{user_id}/preferences", response_model=PreferencesOut,
         tags=["Preferencias"], summary="Obtiene los géneros favoritos de un usuario")
async def get_preferences(user_id: int = Path(..., ge=1), db = Depends(get_cursor)):
    conn, cursor = db
    get_user_or_404(cursor, user_id) # 404 si el usuario no existe (no una lista vacía)
    return {"user_id": user_id, "genres": get_genres(cursor, user_id)}


@app.put("/users/{user_id}/preferences", response_model=PreferencesOut,
         tags=["Preferencias"], summary="Sustituye los géneros favoritos de un usuario")
async def replace_preferences(prefs: PreferencesIn, user_id: int = Path(..., ge=1),
                              db=Depends(get_cursor)):
    conn, cursor = db
    get_user_or_404(cursor, user_id)
    try:
        # PUT sustituye la lista completa: se borra la anterior y se inserta la nueva.
        # Las dos operaciones van en la misma transacción (mysql.connector no hace
        # autocommit), así que si algo falla no queda la lista a medias
        cursor.execute("DELETE FROM user_genres WHERE user_id = %s", (user_id,))
        if prefs.genres:
            cursor.executemany(
                "INSERT INTO user_genres (user_id, genre) VALUES (%s, %s)",
                [(user_id, genre) for genre in prefs.genres],
            )
        conn.commit()
    except mysql.connector.Error:
        conn.rollback()
        raise HTTPException(status_code=503, detail="Error al guardar las preferencias")
    return {"user_id": user_id, "genres": get_genres(cursor, user_id)}


@app.get("/spotify/search/tracks", response_model=list[TrackOut], tags=["Spotify"],
         summary="Busca canciones en Spotify")
async def search_tracks(q: str = Query(..., min_length=1, max_length=100),
                        limit: int = Query(10, ge=1, le=50)):
    return await spotify_client.search(q, "track", limit)


@app.get("/spotify/search/artists", response_model=list[ArtistOut], tags=["Spotify"],
         summary="Busca artistas en Spotify")
async def search_artists(q: str = Query(..., min_length=1, max_length=100),
                         limit: int = Query(10, ge=1, le=50)):
    return await spotify_client.search(q, "artist", limit)


@app.get("/spotify/tracks/{track_id}", response_model=TrackOut, tags=["Spotify"],
         summary="Obtiene una canción de Spotify")
async def spotify_track(track_id: str = Path(..., pattern=SPOTIFY_ID_PATTERN)):
    return await spotify_client.get_track(track_id)


@app.get("/spotify/artists/{artist_id}", response_model=ArtistOut, tags=["Spotify"],
         summary="Obtiene un artista de Spotify")
async def spotify_artist(artist_id: str = Path(..., pattern=SPOTIFY_ID_PATTERN)):
    return await spotify_client.get_artist(artist_id)


# ---------- Caché de Spotify en MySQL ----------

def upsert_track(cursor, t: dict):
    # Inserta la canción en la caché o, si ya estaba, actualiza sus datos
    cursor.execute(
        """INSERT INTO tracks (id, name, artist_names, album_name, duration_ms, spotify_url)
           VALUES (%s, %s, %s, %s, %s, %s) AS new
           ON DUPLICATE KEY UPDATE name = new.name, artist_names = new.artist_names,
               album_name = new.album_name, duration_ms = new.duration_ms,
               spotify_url = new.spotify_url""",
        (t["id"], t["name"], t["artist_names"], t["album_name"], t["duration_ms"],
         t["spotify_url"]),
    )


def upsert_artist(cursor, a: dict):
    cursor.execute(
        """INSERT INTO artists (id, name, spotify_url, image_url)
           VALUES (%s, %s, %s, %s) AS new
           ON DUPLICATE KEY UPDATE name = new.name, spotify_url = new.spotify_url,
               image_url = new.image_url""",
        (a["id"], a["name"], a["spotify_url"], a["image_url"]),
    )


FAV_TRACKS_SQL = """SELECT t.id, t.name, t.artist_names, t.album_name, t.duration_ms,
                           t.spotify_url, f.added_at
                    FROM user_favorite_tracks f JOIN tracks t ON t.id = f.track_id
                    WHERE f.user_id = %s"""

FAV_ARTISTS_SQL = """SELECT a.id, a.name, a.spotify_url, a.image_url, f.added_at
                     FROM user_favorite_artists f JOIN artists a ON a.id = f.artist_id
                     WHERE f.user_id = %s"""


# ---------- Canciones favoritas ----------

@app.post("/users/{user_id}/favorites/tracks", response_model=FavoriteTrackOut,
          status_code=201, tags=["Favoritos"], summary="Añade una canción a favoritos")
async def add_favorite_track(fav: FavoriteTrackIn, user_id: int = Path(..., ge=1),
                             db=Depends(get_cursor)):
    conn, cursor = db
    get_user_or_404(cursor, user_id)
    # Se consulta Spotify: valida que la canción existe (404 si no) y trae sus datos
    track = await spotify_client.get_track(fav.track_id)
    try:
        # Caché y relación en la misma transacción
        upsert_track(cursor, track)
        cursor.execute("INSERT INTO user_favorite_tracks (user_id, track_id) VALUES (%s, %s)",
                       (user_id, track["id"]))
        conn.commit()
    except mysql.connector.IntegrityError as e:
        conn.rollback()
        if e.errno == errorcode.ER_DUP_ENTRY:  # clave primaria (user_id, track_id)
            raise HTTPException(status_code=409, detail="La canción ya está en favoritos")
        raise HTTPException(status_code=400, detail="Datos inválidos")
    cursor.execute(FAV_TRACKS_SQL + " AND f.track_id = %s", (user_id, track["id"]))
    return cursor.fetchone()


@app.get("/users/{user_id}/favorites/tracks", response_model=list[FavoriteTrackOut],
         tags=["Favoritos"], summary="Lista las canciones favoritas de un usuario")
async def list_favorite_tracks(
    user_id: int = Path(..., ge=1),
    refresh: bool = Query(False, description="Actualiza los datos desde Spotify antes de devolverlos"),
    db=Depends(get_cursor),
):
    conn, cursor = db
    get_user_or_404(cursor, user_id)
    # Por defecto se sirve desde la caché (rápido, sin gastar peticiones a Spotify);
    # con refresh=true se vuelve a pedir cada canción a Spotify y se actualiza la caché
    if refresh:
        cursor.execute("SELECT track_id FROM user_favorite_tracks WHERE user_id = %s",
                       (user_id,))
        for row in cursor.fetchall():
            upsert_track(cursor, await spotify_client.get_track(row["track_id"]))
        conn.commit()
    cursor.execute(FAV_TRACKS_SQL + " ORDER BY f.added_at DESC", (user_id,))
    return cursor.fetchall()


@app.delete("/users/{user_id}/favorites/tracks/{track_id}", status_code=204,
            tags=["Favoritos"], summary="Quita una canción de favoritos")
async def remove_favorite_track(user_id: int = Path(..., ge=1),
                                track_id: str = Path(..., pattern=SPOTIFY_ID_PATTERN),
                                db=Depends(get_cursor)):
    conn, cursor = db
    # Solo se borra la relación; la canción sigue en la caché para otros usuarios
    cursor.execute("DELETE FROM user_favorite_tracks WHERE user_id = %s AND track_id = %s",
                   (user_id, track_id))
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="La canción no está en los favoritos del usuario")
    return Response(status_code=204)


# ---------- Artistas favoritos ----------

@app.post("/users/{user_id}/favorites/artists", response_model=FavoriteArtistOut,
          status_code=201, tags=["Favoritos"], summary="Añade un artista a favoritos")
async def add_favorite_artist(fav: FavoriteArtistIn, user_id: int = Path(..., ge=1),
                              db=Depends(get_cursor)):
    conn, cursor = db
    get_user_or_404(cursor, user_id)
    artist = await spotify_client.get_artist(fav.artist_id)
    try:
        upsert_artist(cursor, artist)
        cursor.execute("INSERT INTO user_favorite_artists (user_id, artist_id) VALUES (%s, %s)",
                       (user_id, artist["id"]))
        conn.commit()
    except mysql.connector.IntegrityError as e:
        conn.rollback()
        if e.errno == errorcode.ER_DUP_ENTRY:
            raise HTTPException(status_code=409, detail="El artista ya está en favoritos")
        raise HTTPException(status_code=400, detail="Datos inválidos")
    cursor.execute(FAV_ARTISTS_SQL + " AND f.artist_id = %s", (user_id, artist["id"]))
    return cursor.fetchone()


@app.get("/users/{user_id}/favorites/artists", response_model=list[FavoriteArtistOut],
         tags=["Favoritos"], summary="Lista los artistas favoritos de un usuario")
async def list_favorite_artists(
    user_id: int = Path(..., ge=1),
    refresh: bool = Query(False, description="Actualiza los datos desde Spotify antes de devolverlos"),
    db=Depends(get_cursor),
):
    conn, cursor = db
    get_user_or_404(cursor, user_id)
    if refresh:
        cursor.execute("SELECT artist_id FROM user_favorite_artists WHERE user_id = %s",
                       (user_id,))
        for row in cursor.fetchall():
            upsert_artist(cursor, await spotify_client.get_artist(row["artist_id"]))
        conn.commit()
    cursor.execute(FAV_ARTISTS_SQL + " ORDER BY f.added_at DESC", (user_id,))
    return cursor.fetchall()


@app.delete("/users/{user_id}/favorites/artists/{artist_id}", status_code=204,
            tags=["Favoritos"], summary="Quita un artista de favoritos")
async def remove_favorite_artist(user_id: int = Path(..., ge=1),
                                 artist_id: str = Path(..., pattern=SPOTIFY_ID_PATTERN),
                                 db=Depends(get_cursor)):
    conn, cursor = db
    cursor.execute("DELETE FROM user_favorite_artists WHERE user_id = %s AND artist_id = %s",
                   (user_id, artist_id))
    conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="El artista no está en los favoritos del usuario")
    return Response(status_code=204)
