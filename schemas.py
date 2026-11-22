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