"""Valoraciones, historial y dashboard (todo protegido con JWT)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.db.session import get_db
from app.modules.prediccion import service as predictor
from app.modules.usuarios.models import Usuario
from app.modules.valoraciones import service as svc
from app.modules.valoraciones.models import Valoracion
from app.modules.valoraciones.schemas import DashboardOut, DatosValoracion, ValoracionOut

router = APIRouter(prefix="/api", tags=["Valoraciones"], dependencies=[Depends(usuario_actual)])


@router.post("/valoraciones", response_model=ValoracionOut, status_code=201)
@router.post("/valoracion", response_model=ValoracionOut, status_code=201, include_in_schema=False)
def crear(datos: DatosValoracion, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    """Guarda la valoración; el servidor recalcula el riesgo."""
    if not predictor.modelo_disponible():
        raise HTTPException(status_code=503, detail="Modelo no disponible")
    return svc.a_salida(svc.guardar(db, datos, user.id))


@router.get("/valoraciones", response_model=list[ValoracionOut])
@router.get("/historial", response_model=list[ValoracionOut], include_in_schema=False)
def listar(riesgo: str | None = Query(None, pattern="(?i)^(bajo|medio|alto)$"),
           q: str | None = Query(None, max_length=40), db: Session = Depends(get_db)):
    """Historial, filtrable por riesgo y por código de niño o fecha (aaaa-mm-dd)."""
    return [svc.a_salida(v) for v in svc.listar(db, riesgo, q)]


@router.get("/valoraciones/{id}", response_model=ValoracionOut)
def detalle(id: int, db: Session = Depends(get_db)):
    v = db.get(Valoracion, id)
    if v is None:
        raise HTTPException(status_code=404, detail="Valoración no encontrada")
    return svc.a_salida(v)


@router.delete("/valoraciones/{id}", status_code=204)
def eliminar(id: int, db: Session = Depends(get_db)):
    v = db.get(Valoracion, id)
    if v is None:
        raise HTTPException(status_code=404, detail="Valoración no encontrada")
    db.delete(v)
    db.commit()
    return Response(status_code=204)


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    return svc.dashboard(db)

