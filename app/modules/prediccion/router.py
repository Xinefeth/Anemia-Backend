"""Endpoint de predicción de riesgo (protegido con JWT)."""
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import usuario_actual
from app.modules.prediccion import service as predictor
from app.modules.prediccion.schemas import DatosPrediccion, ResultadoPrediccion

router = APIRouter(prefix="/api", tags=["Valoración"], dependencies=[Depends(usuario_actual)])


@router.post("/predict", response_model=ResultadoPrediccion)
def predict(datos: DatosPrediccion):
    """Devuelve la valoración de RIESGO (no es un diagnóstico) con los factores más influyentes."""
    if not predictor.modelo_disponible():
        raise HTTPException(status_code=503, detail="Modelo no disponible")
    return predictor.predecir(datos)
