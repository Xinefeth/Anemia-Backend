"""Definiciones de PC / TR / TT, n usados y migración del grupo de niños existentes."""
import pytest
from sqlalchemy import create_engine, text

from app.db.migraciones import migrar
from app.services.reportes import hb_ajustada, riesgo_referencia

VENT = {"desde": "2031-03-01", "hasta": "2031-03-31"}  # ventana aislada del resto de tests


def _val(client, cab, codigo, grupo, hb, edad=20, dia="2031-03-10", altitud=34):
    d = {"codigo": codigo, "edad_meses": edad, "altitud": altitud, "sexo": "F", "grupo": grupo,
         "cred": True, "suplementacion": True, "fecha": f"{dia}T09:00:00"}
    if hb is not None:
        d["hemoglobina"] = hb
    r = client.post("/api/valoraciones", json=d, headers=cab)
    assert r.status_code == 201
    return r.json()


def test_pc_excluye_sin_hb_y_devuelve_n(client, cab):
    v1 = _val(client, cab, "PC1", "control", 9.2)
    v2 = _val(client, cab, "PC2", "control", 14.0)
    _val(client, cab, "PC3", "control", None)  # sin Hb: no entra a PC
    r = client.get("/api/reporte", params=VENT, headers=cab).json()
    ref = {"PC1": riesgo_referencia(9.2, 34), "PC2": riesgo_referencia(14.0, 34)}
    aciertos = (v1["riesgo"] == ref["PC1"]) + (v2["riesgo"] == ref["PC2"])
    assert r["n_pc"]["control"] == 2 and r["n_valoraciones"]["control"] == 3
    assert r["pc"]["control"] == round(100 * aciertos / 2, 1)
    # grupo sin datos: indicador 0.0 con n=0 (la UI debe mostrar "sin datos")
    assert r["n_pc"]["experimental"] == 0 and r["n_valoraciones"]["experimental"] == 0
    assert r["pc"]["experimental"] == 0.0 and r["tr"]["experimental"] == 0.0


def test_pc_hb_baja_modelo_bajo_es_incorrecto():
    # Caso del frontend: Hb 9.2 -> referencia Alto; el Modelo B (sin Hb) puede decir Bajo => no coincide.
    assert riesgo_referencia(9.2, 34) == "Alto" and riesgo_referencia(10.5, 34) == "Medio"
    assert riesgo_referencia(11.0, 34) == "Bajo"


def test_hb_ajustada_altitud():
    assert hb_ajustada(12.0, 500) == 12.0
    assert hb_ajustada(12.0, 3000) < 12.0  # a 3000 msnm se resta ~1.8 g/dL


def test_tr_segundos_con_tres_decimales(client, cab):
    _val(client, cab, "TR1", "experimental", 11.5, dia="2031-03-11")
    r = client.get("/api/reporte", params=VENT, headers=cab).json()
    assert 0 < r["tr"]["experimental"] < 5  # segundos, no ms, y no se redondea a 0
    assert round(r["tr"]["experimental"], 3) == r["tr"]["experimental"]


def test_tt_un_solo_grupo_y_maximo_100(client, cab):
    _val(client, cab, "TT1", "experimental", 11.5, dia="2031-03-12")
    # niño registrado en 'experimental' pero sin valorar en el periodo
    assert client.post("/api/ninos", json={"codigo": "TT_SIN", "edad_meses": 12, "sexo": "M",
                                           "grupo": "experimental"}, headers=cab).status_code == 201
    r = client.get("/api/reporte", params=VENT, headers=cab).json()
    ex = r["n_tt_registrados"]["experimental"]
    assert 0 < r["n_tt_valorados"]["experimental"] < ex  # TT_SIN cuenta como registrado no valorado
    assert 0 < r["tt"]["experimental"] < 100
    assert r["tt"]["control"] <= 100 and r["tt"]["experimental"] <= 100
    # periodo sin valoraciones: TT = 0 pero n_tt_registrados sigue informando el denominador
    v = client.get("/api/reporte", params={"desde": "2040-01-01", "hasta": "2040-01-31"}, headers=cab).json()
    assert v["total"] == 0 and v["tt"]["experimental"] == 0.0 and v["n_tt_registrados"]["experimental"] >= ex


def test_migracion_backfill_grupo_nino():
    """BD antigua (sin usuario.activo ni nino.grupo): migrar() las agrega y toma el grupo de la última valoración."""
    e = create_engine("sqlite://")
    with e.begin() as c:
        c.execute(text('CREATE TABLE usuario ("idUsuario" INTEGER PRIMARY KEY, nombre VARCHAR, usuario VARCHAR, '
                       'contrasena VARCHAR, rol VARCHAR)'))
        c.execute(text('CREATE TABLE nino ("idNino" INTEGER PRIMARY KEY, codigo VARCHAR)'))
        c.execute(text('CREATE TABLE valoracion ("idValoracion" INTEGER PRIMARY KEY, "idNino" INTEGER, '
                       'grupo VARCHAR, fecha DATETIME)'))
        c.execute(text("INSERT INTO usuario VALUES (1,'A','a','x','médico')"))
        c.execute(text("INSERT INTO nino VALUES (1,'N1'),(2,'N2')"))
        c.execute(text("INSERT INTO valoracion VALUES (1,1,'control','2030-01-01'),(2,1,'experimental','2030-02-01')"))
    migrar(e)
    migrar(e)  # idempotente
    with e.connect() as c:
        assert c.execute(text("SELECT activo FROM usuario")).scalar() in (1, True)
        g = dict(c.execute(text("SELECT codigo, grupo FROM nino")).all())
    assert g == {"N1": "experimental", "N2": "control"}
