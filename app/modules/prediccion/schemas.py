"""Esquemas de /api/predict. Los nombres JSON siguen el contrato de la app Flutter."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.dominio import Altitud, EdadMeses
from app.core.tipos import Sexo


class DatosPrediccion(BaseModel):
    """Entrada de /api/predict. Los campos extra del cliente (codigo, hemoglobina...) se ignoran."""
    edad_meses: EdadMeses
    altitud: Altitud
    sexo: Sexo
    # Las 5 variables del Modelo B son OBLIGATORIAS: un valor por defecto silencioso daría un resultado que parece válido y no lo es.
    cred: bool = Field(..., description="Asiste a control CRED")
    suplementacion: bool = Field(..., description="Recibe suplementación con hierro")

    @field_validator("sexo", mode="before")
    @classmethod
    def _sexo(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


class Factor(BaseModel):
    factor: str
    peso: float


class ResultadoPrediccion(BaseModel):
    riesgo: Literal["Bajo", "Medio", "Alto"]
    probabilidad: float  # probabilidad CALIBRADA de la clase `riesgo` (= probabilidades[riesgo])
    probabilidades: dict[Literal["Bajo", "Medio", "Alto"], float]  # calibradas, suman 1 (±0.0002 por redondeo)
    modelo: str
    tiempo_ms: int
    factores_influyentes: list[Factor]
