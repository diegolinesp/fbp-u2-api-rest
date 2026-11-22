import os
import mysql.connector
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from configuration.connections import DatabaseConnection

load_dotenv() # carga las variables del archivo .env

app = FastAPI(
    title="Spotify Users API",
    description = "API REST para gestionar usuarios, sus preferencias musicales " \
                  "y sus canciones y artistas favoritos, integrada con Spotify y MySQL.",
    version="1.0.0",
)

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
