"""
Fixtures: BD SQLite en memoria y modelo de respaldo generado en una carpeta temporal.
Las variables de entorno se fijan ANTES de importar la app.
"""
import os
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tmp = tempfile.mkdtemp()
_pkl = os.path.join(_tmp, "modelo_anemia_rf.pkl")
os.environ.update({
    "DATABASE_URL": "sqlite://", "ENTORNO": "development", "SECRET_KEY": "x" * 40,
    "RUTA_MODELO": _pkl, "SEED_DEMO": "true", "DEMO_USUARIO": "demo", "DEMO_CONTRASENA": "demo",
})
# Genera el modelo sintético de respaldo solo para las pruebas (el script usa ml/artefactos/).
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location("gen", os.path.join(RAIZ, "ml", "scripts", "generar_modelo_respaldo.py"))
_gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gen)
_gen.SALIDA = _pkl
sys.argv = ["x", "--forzar"]
_gen.main()

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:  # dispara lifespan: tablas, seed, modelo
        yield c


@pytest.fixture(scope="session")
def cab(client):
    r = client.post("/api/login", json={"usuario": "demo", "contrasena": "demo"})
    return {"Authorization": f"Bearer {r.json()['token']}"}
