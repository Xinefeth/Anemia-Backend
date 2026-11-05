"""
Entidades de base de datos (MER): USUARIO, NINO, VALORACION.
El niño se identifica solo por un código: no se guardan nombres (anonimizado).
"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column("idUsuario", Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    usuario: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    contrasena: Mapped[str] = mapped_column(String(100))  # hash bcrypt, nunca texto plano
    rol: Mapped[str] = mapped_column(String(30))  # médico | enfermero


class Nino(Base):
    __tablename__ = "nino"
    id: Mapped[int] = mapped_column("idNino", Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # seudónimo
    edad_meses: Mapped[int] = mapped_column("edadMeses", Integer)
    altitud: Mapped[float] = mapped_column(Float)
    sexo: Mapped[str] = mapped_column(String(1))  # M | F
    cred: Mapped[bool] = mapped_column(Boolean)  # asiste a control CRED
    suplementacion: Mapped[bool] = mapped_column(Boolean)
    # Hb medida: NO entra al modelo; solo sirve de referencia para medir PC en reportes.
    hemoglobina: Mapped[float | None] = mapped_column(Float, nullable=True)


class Valoracion(Base):
    __tablename__ = "valoracion"
    id: Mapped[int] = mapped_column("idValoracion", Integer, primary_key=True)
    id_nino: Mapped[int] = mapped_column("idNino", ForeignKey("nino.idNino"), index=True)
    id_usuario: Mapped[int] = mapped_column("idUsuario", ForeignKey("usuario.idUsuario"))
    riesgo: Mapped[str] = mapped_column(String(10), index=True)
    probabilidad: Mapped[float] = mapped_column(Float)
    fecha: Mapped[datetime] = mapped_column(DateTime, index=True)
    grupo: Mapped[str] = mapped_column(String(15))  # control | experimental
    tiempo_ms: Mapped[int] = mapped_column(Integer, default=0)  # insumo del indicador TR

    nino: Mapped[Nino] = relationship(lazy="joined")
