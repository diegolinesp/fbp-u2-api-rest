from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

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