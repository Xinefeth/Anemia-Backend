"""Pruebas de salud, login y predicción."""
BASE = {"edad_meses": 18, "altitud": 34, "sexo": "M", "cred": False, "suplementacion": False}


def test_health_publico(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["modelo_cargado"] is True


def test_login_ok(client):
    r = client.post("/api/login", json={"usuario": "demo", "contrasena": "demo"})
    j = r.json()
    assert r.status_code == 200 and j["token"]
    assert set(j["usuario"]) == {"id", "nombre", "rol"}


def test_login_incorrecto_no_es_401(client):
    r = client.post("/api/login", json={"usuario": "demo", "contrasena": "mala"})
    assert r.status_code == 400 and r.json()["detail"]


def test_hash_no_es_texto_plano():
    from app.db.database import SessionLocal
    from app.models.entidades import Usuario
    with SessionLocal() as db:
        u = db.query(Usuario).filter_by(usuario="demo").one()
        assert u.contrasena != "demo" and u.contrasena.startswith("$2")


def test_predict_requiere_token(client):
    assert client.post("/api/predict", json=BASE).status_code == 401
    assert client.post("/api/predict", json=BASE, headers={"Authorization": "Bearer falso"}).status_code == 401


def test_predict_valido(client, cab):
    r = client.post("/api/predict", json={**BASE, "codigo": "X1", "hemoglobina": 10.2, "grupo": "control"}, headers=cab)
    assert r.status_code == 200
    j = r.json()
    assert j["riesgo"] in ["Bajo", "Medio", "Alto"]
    assert 0 <= j["probabilidad"] <= 1 and j["tiempo_ms"] >= 0 and j["modelo"]
    assert j["factores_influyentes"] and "factor" in j["factores_influyentes"][0]
    assert any("No asiste a control CRED" in f["factor"] for f in j["factores_influyentes"] + [{"factor": "No asiste a control CRED"}])


def test_predict_validacion(client, cab):
    for malo in ({**BASE, "edad_meses": 200}, {**BASE, "sexo": "X"}, {**BASE, "altitud": -5}):
        assert client.post("/api/predict", json=malo, headers=cab).status_code == 422
