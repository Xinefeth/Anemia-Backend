"""Entidad NINO. El niño se identifica solo por un código: no se guardan nombres (anonimizado)."""
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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
    grupo: Mapped[str] = mapped_column(String(15), default="control", server_default="control")
