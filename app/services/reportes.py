"""
Indicadores del estudio por grupo (control / experimental) en un periodo:
- PC: porcentaje de clasificaciones correctas. Se compara el riesgo del sistema con el riesgo de
  REFERENCIA derivado de la hemoglobina medida (ajustada por altitud, criterio OMS/MINSA):
  Hb ajustada < 10 -> Alto; 10 a < 11 -> Medio; >= 11 -> Bajo. Solo cuentan valoraciones con Hb.
- TR: tiempo de respuesta promedio del sistema (cálculo de la predicción en el servidor), en segundos, 3 decimales.
- TT: tasa de tamizaje (%) = niños registrados en el grupo que tienen una valoración en el periodo /
  niños registrados en el grupo.
Un grupo sin datos devuelve 0.0 en el indicador; los campos n_* indican con cuántos datos se calculó.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entidades import Nino, Valoracion
from app.schemas.esquemas import Conteo, Indicador, ReporteOut

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


def _prom(x: list[float], dec: int = 3) -> float:
    return round(sum(x) / len(x), dec) if x else 0.0


def _pct(num: int, den: int) -> float:
    return round(100 * num / den, 1) if den else 0.0


def generar(db: Session, desde: date, hasta: date) -> ReporteOut:
    ini = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta + timedelta(days=1), datetime.min.time())
    periodo = list(db.scalars(select(Valoracion).where(Valoracion.fecha >= ini, Valoracion.fecha < fin)))
    ninos = list(db.scalars(select(Nino)))
    valorados_ids = {v.id_nino for v in periodo}
    pc, tr, tt, n_val, n_pc, n_tt, n_reg = {}, {}, {}, {}, {}, {}, {}
    for g in GRUPOS:
        vs = [v for v in periodo if v.grupo == g]
        # PC: solo valoraciones con Hb medida (las demás no tienen referencia y se excluyen del denominador).
        con_hb = [v for v in vs if v.nino.hemoglobina is not None]
        ok = [v for v in con_hb if v.riesgo == riesgo_referencia(v.nino.hemoglobina, v.nino.altitud)]
        pc[g] = _pct(len(ok), len(con_hb))
        tr[g] = _prom([v.tiempo_ms / 1000 for v in vs])
        # TT: niños registrados en el grupo que fueron valorados en el periodo (siempre <= 100 %).
        registrados = [n for n in ninos if n.grupo == g]
        valorados = [n for n in registrados if n.id in valorados_ids]
        tt[g] = _pct(len(valorados), len(registrados))
        n_val[g], n_pc[g], n_tt[g], n_reg[g] = len(vs), len(con_hb), len(valorados), len(registrados)

    def ind(d):
        return Indicador(control=d["control"], experimental=d["experimental"])

    def cnt(d):
        return Conteo(control=d["control"], experimental=d["experimental"])

    return ReporteOut(
        desde=desde, hasta=hasta, total=len(periodo), pc=ind(pc), tr=ind(tr), tt=ind(tt),
        n_valoraciones=cnt(n_val), n_pc=cnt(n_pc), n_tt_valorados=cnt(n_tt), n_tt_registrados=cnt(n_reg),
    )
