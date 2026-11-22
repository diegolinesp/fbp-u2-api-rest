import logging

#Logger de uvicorn: sus mensajes aparecen en la terminal de fastapi dev
logger = logging.getLogger("uvicorn.error")

import os
import time
from typing import Literal

import httpx
from fastapi import HTTPException

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"
TIMEOUT = 10    # segundos

# Caché del token en memoria: se reutiliza hasta poco antes de que caduque (1 hora)
_token = {"value": None, "expires_at": 0.0}


async def _get_token() -> str:
    """Obtiene un token con el flujo Client Credentials (sin usuario de Spotify)."""
    if _token["value"] and time.time() < _token["expires_at"]:
        return _token["value"]
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(os.getenv("SPOTIFY_CLIENT_ID", ""), os.getenv("SPOTIFY_CLIENT_SECRET", "")),
            )
    except httpx.HTTPError:
        logger.exception("Fallo de red al pedir el token a Spotify")
        raise HTTPException(status_code=502, detail="No se pudo contactar con Spotify")
    if r.status_code != 200:
        logger.error("Spotify rechazó la autenticación: %s %s", r.status_code, r.text)
        # Credenciales mal configuradas: es un fallo de nuestro servidor, no del cliente
        raise HTTPException(status_code=502, detail="Error de autenticación con Spotify")
    data = r.json()
    _token["value"] = data["access_token"]
    _token["expires_at"] = time.time() + data["expires_in"] - 60    # margen de 60 s
    return _token["value"]


async def _get(path: str, params: dict | None = None) -> dict:
    """GET a la Web API de Spotify, traduciendo sus errores a códigos HTTP propios."""
    for attemp in range(2):
        token = await _get_token()
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.get(f"{API_URL}{path}", params=params,
                                     headers={"Authorization": f"Bearer {token}"})
        except httpx.TimeoutException:
            logger.warning("Timeout en GET %s", path)
            raise HTTPException(status_code=504, detail="Spotify no ha respondido a tiempo")
        except httpx.RequestError:
            logger.exception("Fallo de red en GET %s", path)
            raise HTTPException(status_code=502, detail="No se pudo contactar con Spotify")
        
        # 401 = token caducado o revocado: se descarta y se reintenta una sola vez
        if r.status_code == 401 and attemp == 0:
            _token["value"] = None
            continue
        break
    
    if r.status_code == 200:
        return r.json()
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="Recurso no encontrado en Spotify")
    if r.status_code == 400:
        raise HTTPException(status_code=400, detail="Parámetros no válidos para Spotify")
    if r.status_code == 429:
        # Límite de peticiones: se reenvía al cliente cuánto debe esperar
        raise HTTPException(status_code=503,
                            detail="Límite de peticiones de Spotify alcanzado, inténtalo más tarde",
                            headers={"Retry-After": r.headers.get("Retry-After", "30")})
    logger.error("Respuesta inesperada de Spotify en %s: %s %s", path, r.status_code, r.text)
    raise HTTPException(status_code=502, detail=f"Error inesperado de Spotify ({r.status_code})")


# Spotify devuelve objetos muy grandes; nos quedamos solo con lo que guarda la BD
def simplify_track(t: dict) -> dict:
    return {
        "id": t["id"],
        "name": t["name"],
        "artist_names": ", ".join(a["name"] for a in t["artists"]),
        "album_name": t.get("album", {}).get("name"),
        "duration_ms": t["duration_ms"],
        "spotify_url": t.get("external_urls", {}).get("spotify"),
    }
    
    
def simplify_artist(a: dict) -> dict:
    images = a.get("images") or []
    return {
        "id": a["id"],
        "name": a["name"],
        "spotify_url": a.get("external_urls", {}).get("spotify"),
        "image_url": images[0]["url"] if images else None,
    }
    
    
async def get_track(track_id: str) -> dict:
    return simplify_track(await _get(f"/tracks/{track_id}"))


async def get_artist(artist_id: str) -> dict:
    return simplify_artist(await _get(f"/artists/{artist_id}"))


async def search(q: str, kind: Literal["track", "artist"], limit: int) -> list[dict]:
    data = await _get("/search", {"q": q, "type": kind, "limit": limit})
    simplify = simplify_track if kind == "track" else simplify_artist
    # Spotify a veces devuelve elementos null en las búsquedas: se descartan
    return [simplify(item) for item in data[f"{kind}s"]["items"] if item]
