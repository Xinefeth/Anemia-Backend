"""Pruebas de valoración, historial, dashboard y reporte."""
from datetime import date

HOY = date.today().isoformat()


def _nueva(codigo, grupo="control", hb=10.5, fecha=None):
    d = {"codigo": codigo, "edad_meses": 12, "altitud": 34, "sexo": "F", "cred": False,
         "suplementacion": False, "hemoglobina": hb, "grupo": grupo}
    if fecha:
        d["fecha"] = fecha
    return d


def test_requiere_token(client):
    for ruta in ("/api/historial", "/api/valoraciones", "/api/dashboard", "/api/reporte"):
        assert client.get(ruta).status_code == 401


def test_guardar_y_detalle(client, cab):
    r = client.post("/api/valoraciones", json=_nueva("N001"), headers=cab)
    assert r.status_code == 201
    v = r.json()
    assert v["riesgo"] in ["Bajo", "Medio", "Alto"] and v["codigo"] == "N001" and v["id"]
    d = client.get(f"/api/valoraciones/{v['id']}", headers=cab)
    assert d.status_code == 200 and d.json()["hemoglobina"] == 10.5
    assert client.get("/api/valoraciones/99999", headers=cab).status_code == 404


def test_codigo_invalido(client, cab):
    assert client.post("/api/valoraciones", json=_nueva("con espacio y ñ"), headers=cab).status_code == 422


def test_historial_filtros(client, cab):
    client.post("/api/valoraciones", json=_nueva("H100", fecha=f"{HOY}T10:00:00"), headers=cab)
    todos = client.get("/api/historial", headers=cab).json()
    assert len(todos) >= 1
    por_codigo = client.get("/api/valoraciones", params={"q": "H100"}, headers=cab).json()
    assert por_codigo and all("H100" in x["codigo"] for x in por_codigo)
    por_fecha = client.get("/api/valoraciones", params={"q": HOY}, headers=cab).json()
    assert any(x["codigo"] == "H100" for x in por_fecha)
    r = todos[0]["riesgo"]
    assert all(x["riesgo"] == r for x in client.get("/api/valoraciones", params={"riesgo": r.lower()}, headers=cab).json())


def test_eliminar(client, cab):
    i = client.post("/api/valoraciones", json=_nueva("DEL1"), headers=cab).json()["id"]
    assert client.delete(f"/api/valoraciones/{i}", headers=cab).status_code == 204
    assert client.get(f"/api/valoraciones/{i}", headers=cab).status_code == 404


def test_dashboard(client, cab):
    client.post("/api/valoraciones", json=_nueva("D1"), headers=cab)
    j = client.get("/api/dashboard", headers=cab).json()
    assert j["total"] == j["alto"] + j["medio"] + j["bajo"] >= 1
    assert len(j["ultimos_dias"]) == 7 and j["recientes"]


def test_reporte(client, cab):
    client.post("/api/valoraciones", json=_nueva("R1", "control"), headers=cab)
    client.post("/api/valoraciones", json=_nueva("R2", "experimental"), headers=cab)
    j = client.get("/api/reporte", params={"desde": "2020-01-01", "hasta": "2100-01-01"}, headers=cab).json()
    assert j["total"] >= 2
    for k in ("pc", "tr", "tt"):
        assert set(j[k]) == {"control", "experimental"}
    assert 0 <= j["pc"]["control"] <= 100 and 0 <= j["tt"]["experimental"] <= 100
    assert client.get("/api/reporte", params={"desde": "2030-01-01", "hasta": "2020-01-01"}, headers=cab).status_code == 422


def test_referencia_hb():
    from app.modules.reportes.service import riesgo_referencia
    assert riesgo_referencia(9.0, 34) == "Alto"
    assert riesgo_referencia(10.5, 34) == "Medio"
    assert riesgo_referencia(12.0, 34) == "Bajo"
