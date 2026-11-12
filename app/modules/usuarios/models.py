"""Entidad USUARIO (personal de salud)."""
from sqlalchemy import Boolean, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column("idUsuario", Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    usuario: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    contrasena: Mapped[str] = mapped_column(String(100))  # hash bcrypt, nunca texto plano
    rol: Mapped[str] = mapped_column(String(30))  # médico | enfermero | administrador
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())  # False = inhabilitado
