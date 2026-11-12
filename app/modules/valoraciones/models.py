"""Entidad VALORACION (riesgo calculado para un niño en una fecha)."""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.modules.ninos.models import Nino


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
