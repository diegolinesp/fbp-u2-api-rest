# Spotify Users API

API REST desarrollada con **FastAPI** para gestionar usuarios, sus preferencias musicales
y sus canciones y artistas favoritos, con persistencia en **MySQL** e integración con la
**Web API de Spotify**.

## Tecnologías
- Python 3.10+ · FastAPI · Pydantic
- MySQL 8.0.19+ (`mysql-connector-python`)
- httpx (cliente asíncrono para Spotify)
- Postman (pruebas)

## Requisitos previos
- MySQL Server 8.0.19 o superior en ejecución.
- Una app creada en el [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
  (Client ID y Client Secret).

## Instalación
```bash
git clone <URL_DEL_REPOSITORIO>
cd fbp-u2-api-rest
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

1. Copia `.env.example` a `.env` y rellena los valores.
2. Crea la base de datos y las tablas: `mysql -u root -p < schema.sql`
   (o abre `schema.sql` en MySQL Workbench y ejecútalo).

## Ejecución
```bash
fastapi dev main.py
```
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Estructura
```
├── configuration/connections.py   # Conexión a MySQL
├── main.py                        # App FastAPI y endpoints
├── schemas.py                     # Modelos Pydantic (validación)
├── spotify_client.py              # Cliente de la Web API de Spotify
├── schema.sql                     # Esquema de la base de datos
├── postman/                       # Colección de pruebas
├── .env.example
└── requirements.txt
```

## Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado de la API y de MySQL |
| POST | `/users` | Crea un usuario |
| GET | `/users` | Lista usuarios (`limit`, `offset`) |
| GET | `/users/{id}` | Obtiene un usuario |
| PUT | `/users/{id}` | Actualiza un usuario |
| DELETE | `/users/{id}` | Elimina un usuario (y sus preferencias y favoritos) |
| GET | `/users/{id}/preferences` | Géneros favoritos del usuario |
| PUT | `/users/{id}/preferences` | Sustituye los géneros favoritos |
| POST | `/users/{id}/favorites/tracks` | Añade una canción favorita (validada en Spotify) |
| GET | `/users/{id}/favorites/tracks` | Lista canciones favoritas (`refresh=true` actualiza desde Spotify) |
| DELETE | `/users/{id}/favorites/tracks/{track_id}` | Quita una canción favorita |
| POST | `/users/{id}/favorites/artists` | Añade un artista favorito (validado en Spotify) |
| GET | `/users/{id}/favorites/artists` | Lista artistas favoritos (`refresh=true` actualiza desde Spotify) |
| DELETE | `/users/{id}/favorites/artists/{artist_id}` | Quita un artista favorito |
| GET | `/spotify/search/tracks` | Busca canciones en Spotify (`q`, `limit`) |
| GET | `/spotify/search/artists` | Busca artistas en Spotify (`q`, `limit`) |
| GET | `/spotify/tracks/{track_id}` | Datos de una canción |
| GET | `/spotify/artists/{artist_id}` | Datos de un artista |

## Códigos de respuesta
| Código | Significado |
|---|---|
| 200 / 201 / 204 | Éxito / recurso creado / eliminado sin contenido |
| 400 | Petición inválida para Spotify |
| 404 | Usuario, favorito o recurso de Spotify no encontrado |
| 409 | Duplicado (username, email o favorito ya existente) |
| 422 | Error de validación de datos |
| 502 / 504 | Error o timeout al contactar con Spotify |
| 503 | Base de datos no disponible o límite de peticiones de Spotify |

## Pruebas
1. Importa `postman/spotify-users-api.postman_collection.json` en Postman.
2. Comprueba que la variable de colección `baseUrl` apunta a `http://127.0.0.1:8000`.
3. Con la API en marcha, ejecuta la colección con el *Collection Runner*
   (57 tests: casos de éxito, validación y errores).