"""Esquemas de autenticación."""
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    usuario: str = Field(..., min_length=1, max_length=50)
    contrasena: str = Field(..., min_length=1, max_length=128)


class UsuarioOut(BaseModel):
    id: int
    nombre: str
    rol: str


class LoginOut(BaseModel):
    token: str
    usuario: UsuarioOut
