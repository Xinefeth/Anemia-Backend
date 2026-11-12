"""Esquemas de valoraciones, historial y dashboard."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.tipos import Grupo
from app.modules.prediccion.schemas import DatosPrediccion


class DatosValoracion(DatosPrediccion):
    """Entrada de POST /api/valoraciones."""
    codigo: str = Field(..., pattern=r"^[A-Za-z0-9_\-]{1,30}$", description="Código anónimo del niño")
    hemoglobina: float | None = Field(None, gt=0, le=25, description="Hb g/dL (solo referencia, no entra al modelo)")
    grupo: Grupo = "control"
    fecha: datetime | None = None


class ValoracionOut(BaseModel):
    """Valoración aplanada (valoración + niño) como la espera el cliente."""
    id: int
    codigo: str
    edad_meses: int
    sexo: str
    hemoglobina: float | None
    altitud: float
    cred: bool
    suplementacion: bool
    grupo: str
    riesgo: str
    probabilidad: float
    fecha: datetime
    pendiente: bool = False


class DashboardOut(BaseModel):
    total: int
    alto: int
    medio: int
    bajo: int
    hb_promedio: float
    ultimos_dias: list[int]
    recientes: list[ValoracionOut]
