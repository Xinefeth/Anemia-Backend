"""
Indicadores del estudio por grupo (control / experimental) en un periodo:
- PC: porcentaje de clasificaciones correctas. Se compara el riesgo del sistema con el riesgo de
  REFERENCIA derivado de la hemoglobina medida (ajustada por altitud, criterio OMS/MINSA):
  Hb ajustada < 10 -> Alto; 10 a < 11 -> Medio; >= 11 -> Bajo. Solo cuentan valoraciones con Hb.
- TR: tiempo de respuesta promedio del sistema, en segundos.
- TT: tasa de tamizaje (%) = niños del grupo valorados en el periodo / niños del grupo registrados.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entidades import Valoracion
from app.schemas.esquemas import Indicador, ReporteOut

GRUPOS = ("control", "experimental")


def hb_ajustada(hb: float, altitud_m: float) -> float:
    """Ajuste de Hb por altitud (OMS 2011) para altitudes >= 1000 msnm."""
    if altitud_m < 1000:
        return hb
    a = altitud_m / 1000 * 3.3
    return hb - (-0.032 * a + 0.022 * a * a)


def riesgo_referencia(hb: float, altitud_m: float) -> str:
    h = hb_ajustada(hb, altitud_m)
    return "Alto" if h < 10 else "Medio" if h < 11 else "Bajo"


def _prom(x: list[float]) -> float:
    return round(sum(x) / len(x), 2) if x else 0.0


def generar(db: Session, desde: date, hasta: date) -> ReporteOut:
    todas = list(db.scalars(select(Valoracion)))
    ini = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
    periodo = [v for v in todas if ini <= v.fecha < fin]
    pc, tr, tt = {}, {}, {}
    for g in GRUPOS:
        vs = [v for v in periodo if v.grupo == g]
        con_hb = [v for v in vs if v.nino.hemoglobina is not None]
        ok = [v for v in con_hb if v.riesgo == riesgo_referencia(v.nino.hemoglobina, v.nino.altitud)]
        pc[g] = round(100 * len(ok) / len(con_hb), 1) if con_hb else 0.0
        tr[g] = _prom([v.tiempo_ms / 1000 for v in vs])
        registrados = {v.id_nino for v in todas if v.grupo == g}
        valorados = {v.id_nino for v in vs}
        tt[g] = round(100 * len(valorados) / len(registrados), 1) if registrados else 0.0

    def ind(d):
        return Indicador(control=d["control"], experimental=d["experimental"])

    return ReporteOut(desde=desde, hasta=hasta, total=len(periodo), pc=ind(pc), tr=ind(tr), tt=ind(tt))
