"""
Servicio de predicción. Modelo B (Random Forest SIN hemoglobina, evita data leakage).
Entrada del modelo, en orden: [edad_meses, altitud, sexo_num, cred, suplementacion] con M=1, F=0.
El modelo se carga UNA vez al iniciar la app (lifespan).
"""
import json
import logging
import os
import time

import joblib
import numpy as np

from app.schemas.esquemas import DatosPrediccion, Factor, ResultadoPrediccion

log = logging.getLogger("anemia.predictor")

ORDEN = ["edad_meses", "altitud", "sexo", "cred", "suplementacion"]
# Importancias globales aproximadas (respaldo si el modelo no las expone).
IMPORTANCIAS_REF = {"edad_meses": 0.43, "cred": 0.29, "altitud": 0.20, "sexo": 0.04, "suplementacion": 0.04}
ETIQUETAS = {0: "Bajo", 1: "Medio", 2: "Alto"}

_estado: dict = {"modelo": None, "nombre": "modelo no cargado"}


def cargar_modelo(ruta: str) -> None:
    """Carga el .pkl (joblib). Si no existe, la API arranca pero /predict responde 503."""
    if not os.path.exists(ruta):
        log.warning("No se encontró el modelo en %s", ruta)
        return
    _estado["modelo"] = joblib.load(ruta)
    nombre = "Random Forest - Modelo B (sin hemoglobina)"
    meta = os.path.splitext(ruta)[0] + ".meta.json"
    if os.path.exists(meta):
        with open(meta, encoding="utf-8") as f:
            if json.load(f).get("sintetico"):
                nombre += " [RESPALDO SINTETICO - NO ES EL MODELO REAL]"
    _estado["nombre"] = nombre
    log.info("Modelo cargado: %s", nombre)


def modelo_disponible() -> bool:
    return _estado["modelo"] is not None


def _texto_factor(clave: str, d: DatosPrediccion) -> str:
    if clave == "edad_meses":
        return f"Edad del niño ({d.edad_meses} meses)"
    if clave == "cred":
        return "Asiste a control CRED" if d.cred else "No asiste a control CRED"
    if clave == "altitud":
        return f"Altitud de residencia ({d.altitud:.0f} msnm)"
    if clave == "suplementacion":
        return "Recibe suplementación con hierro" if d.suplementacion else "No recibe suplementación con hierro"
    return "Sexo masculino" if d.sexo == "M" else "Sexo femenino"


def predecir(d: DatosPrediccion) -> ResultadoPrediccion:
    modelo = _estado["modelo"]
    if modelo is None:
        raise RuntimeError("Modelo no disponible")
    t0 = time.perf_counter()
    x = np.array([[d.edad_meses, d.altitud, 1 if d.sexo == "M" else 0, int(d.cred), int(d.suplementacion)]], dtype=float)
    proba = modelo.predict_proba(x)[0]
    clases = list(modelo.classes_)
    i = int(np.argmax(proba))
    clase = clases[i]
    riesgo = clase.capitalize() if isinstance(clase, str) else ETIQUETAS.get(int(clase), "Medio")

    imp = getattr(modelo, "feature_importances_", None)
    pesos = dict(zip(ORDEN, map(float, imp))) if imp is not None and len(imp) == 5 else IMPORTANCIAS_REF
    top = sorted(pesos.items(), key=lambda kv: kv[1], reverse=True)[:3]
    factores = [Factor(factor=_texto_factor(k, d), peso=round(v, 3)) for k, v in top]
    ms = int(round((time.perf_counter() - t0) * 1000))
    return ResultadoPrediccion(
        riesgo=riesgo, probabilidad=round(float(proba[i]), 4), modelo=_estado["nombre"],
        tiempo_ms=ms, factores_influyentes=factores,
    )
