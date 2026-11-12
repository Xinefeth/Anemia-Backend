"""Esquemas de gestión de niños (RF08-RF11)."""
from pydantic import BaseModel, Field, field_validator

from app.core.dominio import Altitud, EdadMeses
from app.core.tipos import Grupo, Sexo


class NinoIn(BaseModel):
    """Entrada de POST/PUT /api/ninos (mismos campos aplanados que ValoracionOut)."""
    codigo: str = Field(..., pattern=r"^[A-Za-z0-9_\-]{1,30}$", description="Código anónimo del niño")
    edad_meses: EdadMeses
    sexo: Sexo
    # Obligatorios (igual que en /api/predict): sin valores por defecto silenciosos.
    altitud: Altitud
    cred: bool = Field(..., description="Asiste a control CRED")
    suplementacion: bool = Field(..., description="Recibe suplementación con hierro")
    hemoglobina: float | None = Field(None, gt=0, le=25)
    grupo: Grupo = "control"

    @field_validator("sexo", mode="before")
    @classmethod
    def _sexo(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


class NinoOut(NinoIn):
    model_config = {"from_attributes": True}
    id: int
