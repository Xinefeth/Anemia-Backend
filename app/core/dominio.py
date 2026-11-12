"""
Dominio de validez del modelo ML: rangos con los que se entrenó (dataset SIEN-HIS de Trujillo, 2025+2026).
Fuera de estos rangos el modelo extrapolaría sin sentido clínico, por eso la API responde 422.

  - edad: el dataset tiene niños de 6.0 a 59.99 meses (el tamizaje de hemoglobina empieza a los 6 meses).
  - altitud: es la del ESTABLECIMIENTO de salud y solo toma 10 valores entre 10 y 659 msnm.

⚠️ RN01 (hoy "menores de 5 años", 0-59 meses) está PENDIENTE DE VALIDAR CON EL ASESOR: mientras tanto la API exige 6-59
meses por el dominio del modelo. Los valores se repiten en ml/artefactos/modelo_anemia_rf.meta.json (`dominio_validez`)
y un test verifica que coincidan.
"""
from typing import Annotated

from pydantic import AfterValidator, Field
from pydantic_core import PydanticCustomError

EDAD_MIN_MESES, EDAD_MAX_MESES = 6, 59
ALTITUD_MIN_MSNM, ALTITUD_MAX_MSNM = 0, 700


def _edad(v: int) -> int:
    if not EDAD_MIN_MESES <= v <= EDAD_MAX_MESES:
        raise PydanticCustomError(
            "fuera_de_dominio_modelo",
            "edad_meses debe estar entre {min} y {max} meses: el modelo se entrenó con niños de 6 a 59 meses y no es válido fuera de ese rango",
            {"min": EDAD_MIN_MESES, "max": EDAD_MAX_MESES})
    return v


def _altitud(v: float) -> float:
    if not ALTITUD_MIN_MSNM <= v <= ALTITUD_MAX_MSNM:
        raise PydanticCustomError(
            "fuera_de_dominio_modelo",
            "altitud debe estar entre {min} y {max} msnm: el modelo solo es válido para establecimientos de Trujillo (entrenado con altitudes de 10 a 659 msnm)",
            {"min": ALTITUD_MIN_MSNM, "max": ALTITUD_MAX_MSNM})
    return v


EdadMeses = Annotated[
    int, Field(description=f"Edad en meses cumplidos, entero de {EDAD_MIN_MESES} a {EDAD_MAX_MESES} (dominio del modelo; RN01 pendiente de validar con el asesor)",
               json_schema_extra={"minimum": EDAD_MIN_MESES, "maximum": EDAD_MAX_MESES}),
    AfterValidator(_edad)]
Altitud = Annotated[
    float, Field(description=f"Altitud del establecimiento en msnm, de {ALTITUD_MIN_MSNM} a {ALTITUD_MAX_MSNM} (solo Trujillo)",
                 json_schema_extra={"minimum": ALTITUD_MIN_MSNM, "maximum": ALTITUD_MAX_MSNM}),
    AfterValidator(_altitud)]
