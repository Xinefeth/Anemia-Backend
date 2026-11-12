"""Esquemas del reporte de indicadores (PC, TR, TT)."""
from datetime import date

from pydantic import BaseModel


class Indicador(BaseModel):
    control: float
    experimental: float


class Conteo(BaseModel):
    control: int
    experimental: int


class ReporteOut(BaseModel):
    desde: date
    hasta: date
    total: int
    pc: Indicador  # % clasificaciones correctas
    tr: Indicador  # tiempo de respuesta (s)
    tt: Indicador  # tasa de tamizaje (%)
    # n usados en cada indicador, por grupo (n=0 => el indicador no es calculable y se muestra 0.0).
    n_valoraciones: Conteo  # valoraciones del grupo en el periodo (base de TR)
    n_pc: Conteo  # valoraciones con Hb medida (denominador de PC)
    n_tt_valorados: Conteo  # niños del grupo valorados en el periodo (numerador de TT)
    n_tt_registrados: Conteo  # niños registrados en el grupo (denominador de TT)
