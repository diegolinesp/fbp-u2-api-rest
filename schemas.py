from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$",
                          examples=["diego_99"])
    email: EmailStr = Field(..., examples=["diego@example.com"])
    full_name: str | None = Field(None, max_length=100, examples=["Diego Linares"])
    

class UserCreate(UserBase):
    pass


class UserUpdate(UserBase):
    pass # PUT = sustitución completa: se envían todos los campos


class UserOut(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime


# Cada género se normaliza (sin espacios sobrantes y en minúsculas), para que
# "Rock", " rock" y "ROCK" cuenten como el mismo
Genre = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True,
                                         min_length=1, max_length=50)]


class PreferencesIn(BaseModel):
    genres: list[Genre] = Field(..., max_length=20, examples=[["rock, indie, jazz"]])
    
    @field_validator("genres")
    @classmethod
    def remove_duplicates(cls, v: list[str]) -> list[str]:
        # Elimina repetidos conservando el orden; si no, la clave primaria
        # (user_id, genre) haría fallar el INSERT
        return list(dict.fromkeys(v))
    
    
class PreferencesOut(BaseModel):
    user_id: int
    genres: list[str]
    
    
# Los IDs de Spotify son 22 caracteres en base62
SPOTIFY_ID_PATTERN = r"^[0-9A-Za-z]{22}$"


class TrackOut(BaseModel):
    id: str
    name: str
    artist_names: str
    album_name: str | None = None
    duration_ms: int
    spotify_url: str | None = None


class ArtistOut(BaseModel):
    id: str
    name: str
    spotify_url: str | None = None
    image_url: str | None = None


class FavoriteTrackIn(BaseModel):
    track_id: str = Field(..., pattern=SPOTIFY_ID_PATTERN, examples=["4u7EnebtmKWzUH433cf5Qv"])


class FavoriteArtistIn(BaseModel):
    artist_id: str = Field(..., pattern=SPOTIFY_ID_PATTERN, examples=["1dfeR4HaWDbWqFHLkxsg1d"])


class FavoriteTrackOut(TrackOut):
    added_at: datetime


class FavoriteArtistOut(ArtistOut):
    added_at: datetime
