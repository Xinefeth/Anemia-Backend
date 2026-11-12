"""
Pruebas del artefacto ML REAL (ml/artefactos/modelo_anemia_rf.pkl, formato 2), no del modelo sintético de los demás tests.
Garantizan que el .pkl versionado carga, es el modelo esperado, es coherente con el servicio y con su .meta.json.
"""
import json
import os

import joblib
import numpy as np
import pandas as pd
import pytest
import sklearn
from sklearn.ensemble import RandomForestClassifier

from app.modules.prediccion import service
from app.modules.prediccion.schemas import DatosPrediccion

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKL = os.path.join(RAIZ, "ml", "artefactos", "modelo_anemia_rf.pkl")
META = os.path.join(RAIZ, "ml", "artefactos", "modelo_anemia_rf.meta.json")


@pytest.fixture(scope="module")
def paquete():
    return joblib.load(PKL)


@pytest.fixture(scope="module")
def modelo(paquete):
    return paquete["modelo"]


@pytest.fixture(scope="module")
def meta():
    with open(META, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def entradas():
    """Niños de prueba con los nombres de columna del entrenamiento."""
    rng = np.random.default_rng(0)
    n = 500
    return pd.DataFrame({
        "edad_meses": rng.integers(6, 60, n), "altitud": rng.choice([10, 19, 24, 25, 74, 92, 107, 137, 604, 659], n),
        "sexo": rng.integers(0, 2, n), "cred": rng.integers(0, 2, n), "suplementacion": rng.integers(0, 2, n),
    }).astype(float)


@pytest.fixture
def servicio_real(monkeypatch):
    """Carga el .pkl real en un estado aislado del servicio (sin tocar el del resto de tests)."""
    monkeypatch.setattr(service, "_estado", {"modelo": None, "clases": None, "calibradores": None, "piso": 0.0,
                                             "nombre": "modelo no cargado"})
    service.cargar_modelo(PKL)
    return service


# ---------- el artefacto ----------
def test_pkl_carga_y_es_random_forest(paquete, modelo):
    assert paquete["formato"] == 2
    assert type(modelo) is RandomForestClassifier


def test_pkl_no_es_sintetico(meta):
    assert meta["sintetico"] is False
    assert meta["registros"] == 55207


def test_clases_solo_bajo_medio_alto(modelo, entradas):
    assert set(modelo.classes_) == {"Bajo", "Medio", "Alto"}
    assert set(modelo.predict(entradas)) <= {"Bajo", "Medio", "Alto"}


def test_probabilidades_brutas_suman_uno(modelo, entradas):
    p = modelo.predict_proba(entradas)
    assert p.shape == (len(entradas), 3)
    assert np.allclose(p.sum(axis=1), 1.0, atol=1e-6)


def test_features_nombradas_coinciden_con_el_servicio(paquete, modelo, meta):
    """Nombre Y orden se verifican desde el propio modelo (feature_names_in_), no por convención."""
    assert list(modelo.feature_names_in_) == service.ORDEN == meta["features"] == paquete["features"]
    assert modelo.n_features_in_ == len(service.ORDEN) == 5


def test_modelo_rechaza_columnas_en_otro_orden(modelo, entradas):
    """Si alguien cambia el orden de las columnas, sklearn falla en vez de predecir mal en silencio."""
    desordenado = entradas[["altitud", "edad_meses", "sexo", "cred", "suplementacion"]]
    with pytest.raises(ValueError):
        modelo.predict(desordenado)


def test_calibradores_y_probabilidades_calibradas(paquete, modelo, entradas):
    cal, piso = paquete["calibradores"], paquete["piso_probabilidad"]
    assert len(cal) == 3 and piso > 0
    bruta = modelo.predict_proba(entradas)
    p = np.clip(np.column_stack([c.predict(bruta[:, k]) for k, c in enumerate(cal)]), piso, 1 - piso)
    p = p / p.sum(axis=1, keepdims=True)
    assert np.allclose(p.sum(axis=1), 1.0, atol=1e-9)
    assert (p > 0).all() and (p < 1).all()  # nunca 0 % ni 100 %


# ---------- .meta.json ----------
def test_meta_coincide_con_el_modelo(modelo, meta):
    assert meta["clases"] == list(modelo.classes_)
    assert meta["hiperparametros"]["n_estimators"] == modelo.n_estimators
    assert meta["hiperparametros"]["class_weight"] == "balanced"
    for clave in ("fecha", "sha256_datos", "metricas", "version_sklearn", "version_python", "regla_decision",
                  "calibracion", "validacion_cruzada", "curva_umbrales_prob_calibrada"):
        assert meta[clave], clave


def test_meta_reporta_recall_de_alto_por_separado(meta):
    alto = meta["metricas"]["por_clase"]["Alto"]
    assert {"precision", "recall", "f1", "soporte", "recall_ic95"} <= set(alto)
    cm = meta["metricas"]["matriz_confusion"]
    i = cm["orden_clases"].index("Alto")
    assert alto["recall"] == pytest.approx(cm["valores"][i][i] / sum(cm["valores"][i]), abs=1e-3)
    cv = meta["validacion_cruzada"]
    assert cv["pliegues"] == 5 and cv["estratificada"] and len(cv["por_clase"]["Alto"]["recall"]["por_pliegue"]) == 5


def test_calibracion_mejora_log_loss(meta):
    c = meta["calibracion"]
    assert c["despues"]["log_loss"] < c["antes"]["log_loss"]
    assert c["despues"]["brier"] < c["antes"]["brier"]


def test_version_sklearn_coincide_con_la_del_entrenamiento(meta):
    # Un .pkl de RandomForest solo es seguro de cargar con la misma versión de scikit-learn.
    assert sklearn.__version__ == meta["version_sklearn"]


# ---------- el servicio con el modelo real ----------
def test_servicio_con_modelo_real(servicio_real, modelo, paquete):
    d = DatosPrediccion(edad_meses=12, altitud=137, sexo="F", cred=False, suplementacion=False)
    r = servicio_real.predecir(d)
    x = pd.DataFrame([[12, 137, 0, 0, 0]], columns=service.ORDEN).astype(float)
    bruta = modelo.predict_proba(x)[0]
    assert r.riesgo == modelo.predict(x)[0] == "Alto"  # regla de decisión = argmax del RF (sin cambios)
    assert "SINTETICO" not in r.modelo
    cal = np.clip(np.array([c.predict([bruta[k]])[0] for k, c in enumerate(paquete["calibradores"])]),
                  paquete["piso_probabilidad"], 1 - paquete["piso_probabilidad"])
    cal = cal / cal.sum()
    for c, p in zip(modelo.classes_, cal):
        assert r.probabilidades[c] == pytest.approx(float(p), abs=1e-4)
    assert sum(r.probabilidades.values()) == pytest.approx(1.0, abs=2e-4)
    assert r.probabilidad == r.probabilidades[r.riesgo]
    # Calibrada: P(Alto) real es mucho menor que el 0.99 "crudo" del RF.
    assert r.probabilidades["Alto"] < bruta[list(modelo.classes_).index("Alto")]


def test_servicio_devuelve_las_tres_clases(servicio_real):
    vistos = set()
    for edad, alt, cred, supl in [(36, 74, 1, 1), (8, 659, 1, 1), (12, 137, 0, 0)]:
        d = DatosPrediccion(edad_meses=edad, altitud=alt, sexo="F", cred=bool(cred), suplementacion=bool(supl))
        vistos.add(servicio_real.predecir(d).riesgo)
    assert vistos == {"Bajo", "Medio", "Alto"}


# ---------- el servicio rechaza artefactos incompatibles (falla al arrancar, no predice mal) ----------
def _bundle(tmp_path, columnas, **extra):
    rng = np.random.default_rng(1)
    X = pd.DataFrame(rng.integers(0, 5, (60, 5)), columns=columnas).astype(float)
    y = np.array(["Bajo", "Medio", "Alto"] * 20)
    rf = RandomForestClassifier(n_estimators=5, random_state=0).fit(X, y)
    ruta = tmp_path / "m.pkl"
    joblib.dump({"formato": 2, "modelo": rf, "calibradores": None, "piso_probabilidad": 0.0, **extra}, ruta)
    return str(ruta)


def test_servicio_rechaza_features_en_otro_orden(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_estado", dict(service._estado))
    ruta = _bundle(tmp_path, ["altitud", "edad_meses", "sexo", "cred", "suplementacion"])
    with pytest.raises(RuntimeError, match="no coinciden"):
        service.cargar_modelo(ruta)


def test_servicio_rechaza_modelo_sin_nombres_o_formato_viejo(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_estado", dict(service._estado))
    rf = RandomForestClassifier(n_estimators=3).fit(np.random.rand(30, 5), ["Bajo", "Medio", "Alto"] * 10)
    ruta = tmp_path / "viejo.pkl"
    joblib.dump(rf, ruta)  # formato 1: RF "pelado" (sin nombres)
    with pytest.raises(RuntimeError, match="Formato"):
        service.cargar_modelo(str(ruta))


# ---------- advertencia de calibración y dominio de validez ----------
def test_meta_declara_la_prevalencia_de_calibracion(meta):
    prev = meta["prevalencia_entrenamiento"]
    assert prev["anemia_total"] == pytest.approx(0.0279, abs=1e-3)
    assert meta["calibracion"]["prevalencia_calibrada"] == prev
    adv = meta["calibracion"]["advertencia"]
    assert "prevalencia" in adv and "SUBESTIMAR" in adv and "2.8" in adv


def test_meta_dominio_coincide_con_los_limites_de_la_api(meta):
    from app.core import dominio
    d = meta["dominio_validez"]
    assert d["edad_meses"]["rango_api"] == [dominio.EDAD_MIN_MESES, dominio.EDAD_MAX_MESES]
    assert d["altitud"]["rango_api"] == [dominio.ALTITUD_MIN_MSNM, dominio.ALTITUD_MAX_MSNM]
    # La API no acepta nada fuera de lo observado en el entrenamiento (más un margen pequeño de altitud).
    assert d["edad_meses"]["min_entrenamiento"] >= dominio.EDAD_MIN_MESES
    assert max(d["altitud"]["valores_entrenamiento"]) <= dominio.ALTITUD_MAX_MSNM
    assert "PENDIENTE" in d["rn01"]
