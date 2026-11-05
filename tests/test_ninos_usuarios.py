"""Pruebas de gestión de niños (RF08-RF11), usuarios (RF03-RF06), RN01 y CORS."""
NINO = {"codigo": "NG001", "edad_meses": 20, "sexo": "F", "altitud": 34, "cred": True,
        "suplementacion": False, "hemoglobina": 11.2, "grupo": "control"}


def _login(client, usuario, contrasena):
    return client.post("/api/login", json={"usuario": usuario, "contrasena": contrasena})


def _cab(client, usuario, contrasena):
    return {"Authorization": f"Bearer {_login(client, usuario, contrasena).json()['token']}"}


# ---------- niños ----------
def test_ninos_requiere_token(client):
    assert client.get("/api/ninos").status_code == 401


def test_ninos_crud(client, cab):
    r = client.post("/api/ninos", json=NINO, headers=cab)
    assert r.status_code == 201
    n = r.json()
    assert n["id"] and {k: n[k] for k in NINO} == NINO
    assert client.post("/api/ninos", json=NINO, headers=cab).status_code == 409  # código repetido
    assert any(x["id"] == n["id"] for x in client.get("/api/ninos", headers=cab).json())
    assert [x["codigo"] for x in client.get("/api/ninos", params={"q": "ng00"}, headers=cab).json()] == ["NG001"]
    assert client.get("/api/ninos", params={"q": "zzzz"}, headers=cab).json() == []

    n2 = client.put(f"/api/ninos/{n['id']}", json={**NINO, "edad_meses": 30, "grupo": "experimental"}, headers=cab)
    assert n2.status_code == 200 and n2.json()["edad_meses"] == 30 and n2.json()["grupo"] == "experimental"
    otro = client.post("/api/ninos", json={**NINO, "codigo": "NG002"}, headers=cab).json()
    assert client.put(f"/api/ninos/{otro['id']}", json=NINO, headers=cab).status_code == 409

    assert client.delete(f"/api/ninos/{n['id']}", headers=cab).status_code == 204
    assert client.get(f"/api/ninos/{n['id']}", headers=cab).status_code == 404
    assert client.put("/api/ninos/99999", json=NINO, headers=cab).status_code == 404
    assert client.delete("/api/ninos/99999", headers=cab).status_code == 404


def test_eliminar_nino_borra_sus_valoraciones(client, cab):
    v = client.post("/api/valoraciones", json={"codigo": "NGV1", "edad_meses": 10, "altitud": 0, "sexo": "M"},
                    headers=cab).json()
    nino = next(x for x in client.get("/api/ninos", params={"q": "NGV1"}, headers=cab).json())
    assert client.delete(f"/api/ninos/{nino['id']}", headers=cab).status_code == 204
    assert client.get(f"/api/valoraciones/{v['id']}", headers=cab).status_code == 404


def test_rn01_edad_0_59(client, cab):
    base = {"edad_meses": 59, "altitud": 34, "sexo": "M"}
    assert client.post("/api/predict", json=base, headers=cab).status_code == 200
    assert client.post("/api/predict", json={**base, "edad_meses": 60}, headers=cab).status_code == 422
    assert client.post("/api/valoraciones", json={**base, "codigo": "E60", "edad_meses": 60},
                       headers=cab).status_code == 422
    assert client.post("/api/ninos", json={**NINO, "codigo": "E60", "edad_meses": 60}, headers=cab).status_code == 422


# ---------- usuarios ----------
def test_usuarios_ciclo_completo(client, cab):
    nuevo = {"nombre": "Enf. Prueba", "usuario": "enf1", "contrasena": "secreta1", "rol": "enfermero"}
    r = client.post("/api/usuarios", json=nuevo, headers=cab)
    assert r.status_code == 201
    u = r.json()
    assert u == {"id": u["id"], "nombre": "Enf. Prueba", "usuario": "enf1", "rol": "enfermero", "activo": True}
    assert "contrasena" not in u
    assert client.post("/api/usuarios", json=nuevo, headers=cab).status_code == 409
    assert any(x["usuario"] == "enf1" for x in client.get("/api/usuarios", headers=cab).json())

    assert _login(client, "enf1", "secreta1").status_code == 200  # contraseña hasheada pero válida
    cab_enf = _cab(client, "enf1", "secreta1")
    assert client.get("/api/usuarios", headers=cab_enf).status_code == 403  # enfermero no gestiona usuarios
    assert client.post("/api/usuarios", json={**nuevo, "usuario": "x2"}, headers=cab_enf).status_code == 403
    assert client.get("/api/ninos", headers=cab_enf).status_code == 200  # pero sí usa el resto

    p = client.put(f"/api/usuarios/{u['id']}", json={"nombre": "Enf. Editada", "contrasena": "nueva123"}, headers=cab)
    assert p.status_code == 200 and p.json()["nombre"] == "Enf. Editada" and p.json()["rol"] == "enfermero"
    assert _login(client, "enf1", "secreta1").status_code == 400
    assert _login(client, "enf1", "nueva123").status_code == 200

    assert client.delete(f"/api/usuarios/{u['id']}", headers=cab).status_code == 204  # inhabilita
    lista = client.get("/api/usuarios", headers=cab).json()
    assert next(x for x in lista if x["id"] == u["id"])["activo"] is False  # no se borra
    assert _login(client, "enf1", "nueva123").status_code == 403
    assert client.get("/api/ninos", headers=cab_enf).status_code == 401  # su token ya no sirve
    re = client.put(f"/api/usuarios/{u['id']}", json={"activo": True}, headers=cab)  # reactivar
    assert re.json()["activo"] is True and _login(client, "enf1", "nueva123").status_code == 200


def test_usuarios_reglas(client, cab):
    yo = next(x for x in client.get("/api/usuarios", headers=cab).json() if x["usuario"] == "demo")
    assert client.delete(f"/api/usuarios/{yo['id']}", headers=cab).status_code == 400
    assert client.put(f"/api/usuarios/{yo['id']}", json={"activo": False}, headers=cab).status_code == 400
    assert client.put(f"/api/usuarios/{yo['id']}", json={"rol": "enfermero"}, headers=cab).status_code == 400
    assert client.put("/api/usuarios/99999", json={"nombre": "x"}, headers=cab).status_code == 404
    assert client.delete("/api/usuarios/99999", headers=cab).status_code == 404
    mal = {"nombre": "A", "usuario": "ab", "contrasena": "123", "rol": "dios"}
    assert client.post("/api/usuarios", json=mal, headers=cab).status_code == 422
    assert client.get("/api/usuarios").status_code == 401


# ---------- CORS y health ----------
def test_cors_localhost_cualquier_puerto(client):
    for origen in ("http://localhost:54321", "http://127.0.0.1:8080", "http://localhost"):
        r = client.options("/api/login", headers={"Origin": origen, "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") in (origen, "*"), origen


def test_health_get_y_head(client):
    assert client.get("/health").json()["estado"] == "ok"
    assert client.head("/health").status_code == 200
