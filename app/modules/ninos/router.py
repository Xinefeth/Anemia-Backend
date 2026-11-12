"""Gestión de niños (RF08-RF11), protegida con JWT. El niño se identifica solo por un código anónimo."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import usuario_actual
from app.db.session import get_db
from app.modules.ninos.models import Nino
from app.modules.ninos.schemas import NinoIn, NinoOut
from app.modules.valoraciones.models import Valoracion

router = APIRouter(prefix="/api/ninos", tags=["Niños"], dependencies=[Depends(usuario_actual)])


def _obtener(db: Session, id: int) -> Nino:
    n = db.get(Nino, id)
    if n is None:
        raise HTTPException(status_code=404, detail="Niño no encontrado")
    return n


def _codigo_libre(db: Session, codigo: str, excepto: int | None = None) -> None:
    otro = db.scalar(select(Nino).where(Nino.codigo == codigo))
    if otro is not None and otro.id != excepto:
        raise HTTPException(status_code=409, detail="Ya existe un niño con ese código")


@router.get("", response_model=list[NinoOut])
def listar(q: str | None = Query(None, max_length=40), db: Session = Depends(get_db)):
    """Lista de niños; ?q= filtra por código (contiene, sin distinguir mayúsculas)."""
    stmt = select(Nino).order_by(Nino.id.desc())
    if q and q.strip():
        stmt = stmt.where(Nino.codigo.ilike(f"%{q.strip()}%"))
    return list(db.scalars(stmt))


@router.get("/{id}", response_model=NinoOut)
def detalle(id: int, db: Session = Depends(get_db)):
    return _obtener(db, id)


@router.post("", response_model=NinoOut, status_code=201)
def crear(datos: NinoIn, db: Session = Depends(get_db)):
    _codigo_libre(db, datos.codigo)
    n = Nino(**datos.model_dump())
    db.add(n)
    db.commit()
    return n


@router.put("/{id}", response_model=NinoOut)
def modificar(id: int, datos: NinoIn, db: Session = Depends(get_db)):
    n = _obtener(db, id)
    _codigo_libre(db, datos.codigo, excepto=id)
    for k, v in datos.model_dump().items():
        setattr(n, k, v)
    db.commit()
    return n


@router.delete("/{id}", status_code=204)
def eliminar(id: int, db: Session = Depends(get_db)):
    """Elimina el niño y, con él, sus valoraciones (dependen de él)."""
    n = _obtener(db, id)
    db.execute(delete(Valoracion).where(Valoracion.id_nino == id))
    db.delete(n)
    db.commit()
    return Response(status_code=204)
