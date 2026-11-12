"""Reporte de indicadores PC / TR / TT por grupo (protegido con JWT)."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.db.session import get_db
from app.modules.reportes import service
from app.modules.reportes.schemas import ReporteOut

router = APIRouter(prefix="/api", tags=["Reportes"], dependencies=[Depends(usuario_actual)])


@router.get("/reporte", response_model=ReporteOut)
def reporte(desde: date | None = None, hasta: date | None = None, db: Session = Depends(get_db)):
    """Indicadores PC, TR y TT por grupo en el periodo (por defecto, últimos 30 días)."""
    hasta = hasta or date.today()
    desde = desde or hasta - timedelta(days=30)
    if desde > hasta:
        raise HTTPException(status_code=422, detail="'desde' no puede ser posterior a 'hasta'")
    return service.generar(db, desde, hasta)
