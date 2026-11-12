"""Contrato de /api/predict: las 5 variables son obligatorias, entradas inválidas -> 422, /health -> 200 y forma de la respuesta."""
import pytest

OK = {"edad_meses": 18, "altitud": 34, "sexo": "M", "cred": True, "suplementacion": False}


def test_health_200_sin_token(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok", "modelo_cargado": True}


@pytest.mark.parametrize("cuerpo", [
    {**OK, "edad_meses": -1},          # edad negativa
    {**OK, "edad_meses": 60},          # fuera de rango (RN01: 0-59)
    {**OK, "edad_meses": 18.5},        # decimal (debe ser entero)
    {**OK, "edad_meses": "abc"},       # tipo incorrecto
    {**OK, "sexo": "X"},               # sexo desconocido
    {**OK, "sexo": ""},                # sexo vacío
    {**OK, "altitud": -5},             # altitud negativa
    {**OK, "altitud": 9000},           # altitud fuera de rango
    {**OK, "cred": "quizas"},          # booleano inválido
    {**OK, "cred": None},              # null no es un valor
    {**OK, "suplementacion": None},
], ids=["edad<0", "edad>59", "edad-decimal", "edad-texto", "sexo-X", "sexo-vacio", "altitud<0", "altitud>5500",
        "cred-invalido", "cred-null", "suplementacion-null"])
def test_predict_valor_invalido_422(client, cab, cuerpo):
    r = client.post("/api/predict", json=cuerpo, headers=cab)
    assert r.status_code == 422, r.text
    assert r.json()["detail"]


@pytest.mark.parametrize("campo", ["edad_meses", "altitud", "sexo", "cred", "suplementacion"])
def test_predict_las_cinco_variables_son_obligatorias(client, cab, campo):
    """Sin valores por defecto silenciosos: omitir cualquiera de las 5 variables del modelo da 422."""
    cuerpo = {k: v for k, v in OK.items() if k != campo}
    r = client.post("/api/predict", json=cuerpo, headers=cab)
    assert r.status_code == 422, r.text
    assert any(e["type"] == "missing" and e["loc"] == ["body", campo] for e in r.json()["detail"])


def test_predict_cuerpo_vacio_o_ausente_422(client, cab):
    assert client.post("/api/predict", json={}, headers=cab).status_code == 422
    assert client.post("/api/predict", headers=cab).status_code == 422


def test_valoraciones_tambien_exige_las_cinco_variables(client, cab):
    base = {**OK, "codigo": "OBL1"}
    assert client.post("/api/valoraciones", json=base, headers=cab).status_code == 201
    for campo in ("altitud", "cred", "suplementacion"):
        r = client.post("/api/valoraciones", json={k: v for k, v in base.items() if k != campo}, headers=cab)
        assert r.status_code == 422, campo


def test_predict_formatos_aceptados(client, cab):
    """Lo que SÍ se acepta: sexo en minúscula, enteros como texto/float entero, booleanos 1/0, campos extra ignorados."""
    r = client.post("/api/predict", json={"edad_meses": "10", "altitud": "34.5", "sexo": " f ", "cred": 1,
                                          "suplementacion": 0, "codigo": "X", "hemoglobina": 9.1}, headers=cab)
    assert r.status_code == 200, r.text


def test_predict_respuesta_tiene_los_campos_del_contrato(client, cab):
    j = client.post("/api/predict", json=OK, headers=cab).json()
    assert set(j) == {"riesgo", "probabilidad", "probabilidades", "modelo", "tiempo_ms", "factores_influyentes"}
    assert j["riesgo"] in {"Bajo", "Medio", "Alto"}
    assert set(j["probabilidades"]) == {"Bajo", "Medio", "Alto"}
    assert sum(j["probabilidades"].values()) == pytest.approx(1.0, abs=2e-4)
    assert all(0 < p < 1 for p in j["probabilidades"].values())
    assert j["probabilidad"] == j["probabilidades"][j["riesgo"]]
    assert all(set(f) == {"factor", "peso"} for f in j["factores_influyentes"])


@pytest.mark.parametrize("campo", ["altitud", "cred", "suplementacion"])
def test_ninos_tambien_exige_las_variables_del_modelo(client, cab, campo):
    nino = {"codigo": f"NOB_{campo}", "edad_meses": 20, "sexo": "F", "altitud": 34, "cred": True, "suplementacion": True}
    r = client.post("/api/ninos", json={k: v for k, v in nino.items() if k != campo}, headers=cab)
    assert r.status_code == 422, r.text
    assert any(e["type"] == "missing" and e["loc"] == ["body", campo] for e in r.json()["detail"])
    creado = client.post("/api/ninos", json=nino, headers=cab)
    assert creado.status_code == 201
    client.delete(f"/api/ninos/{creado.json()['id']}", headers=cab)  # la BD de tests es compartida: no dejar rastro


# ---------- dominio de validez del modelo (edad 6-59 meses, altitud 0-700 msnm) ----------
@pytest.mark.parametrize("edad", [6, 7, 59])
def test_edad_dentro_del_dominio_ok(client, cab, edad):
    assert client.post("/api/predict", json={**OK, "edad_meses": edad}, headers=cab).status_code == 200


@pytest.mark.parametrize("edad", [0, 1, 5, 60, 100])
def test_edad_fuera_del_dominio_422_con_mensaje_claro(client, cab, edad):
    r = client.post("/api/predict", json={**OK, "edad_meses": edad}, headers=cab)
    assert r.status_code == 422
    e = r.json()["detail"][0]
    assert e["loc"] == ["body", "edad_meses"] and e["type"] == "fuera_de_dominio_modelo"
    assert "entre 6 y 59 meses" in e["msg"] and "modelo" in e["msg"]
    assert e["ctx"] == {"min": 6, "max": 59}


@pytest.mark.parametrize("alt", [0, 34, 659, 700])
def test_altitud_dentro_del_dominio_ok(client, cab, alt):
    assert client.post("/api/predict", json={**OK, "altitud": alt}, headers=cab).status_code == 200


@pytest.mark.parametrize("alt", [-1, 700.5, 701, 1500, 3400, 5500])
def test_altitud_fuera_del_dominio_422_explica_que_es_solo_trujillo(client, cab, alt):
    r = client.post("/api/predict", json={**OK, "altitud": alt}, headers=cab)
    assert r.status_code == 422
    e = r.json()["detail"][0]
    assert e["loc"] == ["body", "altitud"] and e["type"] == "fuera_de_dominio_modelo"
    assert "entre 0 y 700 msnm" in e["msg"] and "Trujillo" in e["msg"]


def test_limites_de_dominio_aplican_tambien_a_valoraciones_y_ninos(client, cab):
    for edad, alt in ((5, 34), (20, 1500)):
        r = client.post("/api/valoraciones", json={**OK, "codigo": "DOM1", "edad_meses": edad, "altitud": alt}, headers=cab)
        assert r.status_code == 422, (edad, alt)
        n = client.post("/api/ninos", json={"codigo": "DOM2", "edad_meses": edad, "sexo": "M", "altitud": alt,
                                            "cred": True, "suplementacion": True}, headers=cab)
        assert n.status_code == 422, (edad, alt)


def test_openapi_documenta_los_rangos(client):
    props = client.get("/openapi.json").json()["components"]["schemas"]["DatosPrediccion"]["properties"]
    assert (props["edad_meses"]["minimum"], props["edad_meses"]["maximum"]) == (6, 59)
    assert (props["altitud"]["minimum"], props["altitud"]["maximum"]) == (0, 700)
