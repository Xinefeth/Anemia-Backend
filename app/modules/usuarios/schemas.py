"""Esquemas de gestión de usuarios (RF03-RF06)."""
from pydantic import BaseModel, Field, field_validator

from app.core.tipos import Rol


def _rol(v):
    if isinstance(v, str):
        v = v.strip().lower()
        return {"medico": "médico"}.get(v, v)
    return v


class UsuarioIn(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    usuario: str = Field(..., pattern=r"^[A-Za-z0-9_.\-]{3,50}$")
    contrasena: str = Field(..., min_length=4, max_length=128)
    rol: Rol

    _norm_rol = field_validator("rol", mode="before")(staticmethod(_rol))


class UsuarioUpdate(BaseModel):
    """PUT /api/usuarios/{id}: todos los campos son opcionales; contrasena solo si se quiere cambiar."""
    nombre: str | None = Field(None, min_length=1, max_length=100)
    usuario: str | None = Field(None, pattern=r"^[A-Za-z0-9_.\-]{3,50}$")
    contrasena: str | None = Field(None, min_length=4, max_length=128)
    rol: Rol | None = None
    activo: bool | None = None

    _norm_rol = field_validator("rol", mode="before")(staticmethod(_rol))


class UsuarioGestionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    nombre: str
    usuario: str
    rol: str
    activo: bool
