"""
Lógica de negocio de valoraciones: guardar, listar y dashboard.
"""
import re
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entidades import Nino, Valoracion
from app.schemas.esquemas import DashboardOut, DatosValoracion, ValoracionOut
from app.services import predictor


def a_salida(v: Valoracion) -> ValoracionOut:
    n = v.nino
    return ValoracionOut(
        id=v.id, codigo=n.codigo, edad_meses=n.edad_meses, sexo=n.sexo, hemoglobina=n.hemoglobina,
        altitud=n.altitud, cred=n.cred, suplementacion=n.suplementacion, grupo=v.grupo,
        riesgo=v.riesgo, probabilidad=v.probabilidad, fecha=v.fecha,
    )


def guardar(db: Session, d: DatosValoracion, id_usuario: int) -> Valoracion:
    """Recalcula el riesgo en el servidor y guarda niño (upsert por código) + valoración."""
    res = predictor.predecir(d)
    nino = db.scalar(select(Nino).where(Nino.codigo == d.codigo))
    if nino is None:
        nino = Nino(codigo=d.codigo)
        db.add(nino)
    nino.edad_meses, nino.altitud, nino.sexo = d.edad_meses, d.altitud, d.sexo
    nino.cred, nino.suplementacion, nino.grupo = d.cred, d.suplementacion, d.grupo
    if d.hemoglobina is not None:
        nino.hemoglobina = d.hemoglobina
    fecha = d.fecha.replace(tzinfo=None) if d.fecha else datetime.now()
    v = Valoracion(nino=nino, id_usuario=id_usuario, riesgo=res.riesgo, probabilidad=res.probabilidad,
                   fecha=fecha, grupo=d.grupo, tiempo_ms=res.tiempo_ms)
    db.add(v)
    db.commit()
    return v


def listar(db: Session, riesgo: str | None, q: str | None) -> list[Valoracion]:
    stmt = select(Valoracion).join(Nino).order_by(Valoracion.fecha.desc(), Valoracion.id.desc())
    if riesgo:
        stmt = stmt.where(func.lower(Valoracion.riesgo) == riesgo.lower())
    if q:
        q = q.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", q):
            try:
                dia = datetime.strptime(q, "%Y-%m-%d")
            except ValueError:
                return []
            stmt = stmt.where(Valoracion.fecha >= dia, Valoracion.fecha < dia + timedelta(days=1))
        else:
            stmt = stmt.where(Nino.codigo.ilike(f"%{q}%"))
    return list(db.scalars(stmt))


def dashboard(db: Session) -> DashboardOut:
    cuentas = dict(db.execute(select(Valoracion.riesgo, func.count()).group_by(Valoracion.riesgo)).all())
    hoy = datetime.now().date()
    inicio = datetime.combine(hoy - timedelta(days=6), datetime.min.time())
    fechas = db.scalars(select(Valoracion.fecha).where(Valoracion.fecha >= inicio)).all()
    por_dia = [0] * 7  # últimos 7 días, el último es hoy
    for f in fechas:
        i = (f.date() - inicio.date()).days
        if 0 <= i < 7:
            por_dia[i] += 1
    hb = db.scalar(select(func.avg(Nino.hemoglobina)))
    recientes = db.scalars(
        select(Valoracion).order_by(Valoracion.fecha.desc(), Valoracion.id.desc()).limit(5)).all()
    return DashboardOut(
        total=sum(cuentas.values()), alto=cuentas.get("Alto", 0), medio=cuentas.get("Medio", 0),
        bajo=cuentas.get("Bajo", 0), hb_promedio=round(float(hb or 0), 2), ultimos_dias=por_dia,
        recientes=[a_salida(v) for v in recientes],
    )
