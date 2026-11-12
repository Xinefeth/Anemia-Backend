"""
Servicio de predicción. Modelo B (Random Forest SIN hemoglobina, evita data leakage).

Artefacto (.pkl, formato 2, lo genera ml/scripts/entrenar_modelo.py): dict con el RF entrenado con features NOMBRADAS,
las clases, los calibradores isotónicos por clase y un piso de probabilidad.
  - `riesgo` (Bajo/Medio/Alto): argmax de las probabilidades del RF (a priori balanceado por SMOTE). Regla de tamizaje
    sensible; NO es la clase más probable en la población real.
  - `probabilidades` / `probabilidad`: probabilidades CALIBRADAS (reflejan frecuencias reales; la de Alto rara vez pasa de 0.3).
El modelo se carga UNA vez al iniciar la app (lifespan) y se verifica que sus features coincidan con ORDEN.
"""
import json
import logging
import os
import time

import joblib
import numpy as np
import pandas as pd

from app.modules.prediccion.schemas import DatosPrediccion, Factor, ResultadoPrediccion

log = logging.getLogger("anemia.predictor")

# Nombres y orden de las features del modelo. Se verifica contra model.feature_names_in_ al cargar.
ORDEN = ["edad_meses", "altitud", "sexo", "cred", "suplementacion"]
ORDEN_RIESGO = ["Bajo", "Medio", "Alto"]  # orden de salida de `probabilidades`
# Importancias globales aproximadas (respaldo si el modelo no las expone).
IMPORTANCIAS_REF = {"edad_meses": 0.43, "cred": 0.29, "altitud": 0.20, "sexo": 0.04, "suplementacion": 0.04}

_estado: dict = {"modelo": None, "clases": None, "calibradores": None, "piso": 0.0, "nombre": "modelo no cargado"}


def _validar(paquete) -> None:
    if not isinstance(paquete, dict) or paquete.get("formato") != 2:
        raise RuntimeError("Formato de modelo no reconocido: reentrene con ml/scripts/entrenar_modelo.py")
    rf = paquete["modelo"]
    nombres = list(getattr(rf, "feature_names_in_", []))
    if nombres != ORDEN:
        raise RuntimeError(f"Las features del modelo {nombres} no coinciden (nombre u orden) con las del servicio {ORDEN}")
    if set(rf.classes_) != set(ORDEN_RIESGO):
        raise RuntimeError(f"Clases inesperadas en el modelo: {list(rf.classes_)}")
    cal = paquete.get("calibradores")
    if cal is not None and len(cal) != len(rf.classes_):
        raise RuntimeError("Número de calibradores distinto al de clases")


def cargar_modelo(ruta: str) -> None:
    """Carga el .pkl (joblib). Si no existe, la API arranca pero /predict responde 503. Si es inválido, falla al arrancar."""
    if not os.path.exists(ruta):
        log.warning("No se encontró el modelo en %s", ruta)
        return
    paquete = joblib.load(ruta)
    _validar(paquete)
    _estado.update(modelo=paquete["modelo"], clases=list(paquete["modelo"].classes_),
                   calibradores=paquete.get("calibradores"), piso=float(paquete.get("piso_probabilidad", 0.0)))
    nombre = "Random Forest - Modelo B (sin hemoglobina)"
    meta = os.path.splitext(ruta)[0] + ".meta.json"
    if os.path.exists(meta):
        with open(meta, encoding="utf-8") as f:
            if json.load(f).get("sintetico"):
                nombre += " [RESPALDO SINTETICO - NO ES EL MODELO REAL]"
    _estado["nombre"] = nombre
    log.info("Modelo cargado: %s (calibrado=%s)", nombre, _estado["calibradores"] is not None)


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


def _calibrar(proba: np.ndarray) -> np.ndarray:
    """Probabilidades calibradas: isotónica por clase, acotada a [piso, 1-piso] y renormalizada a suma 1."""
    cal = _estado["calibradores"]
    if cal is None:  # modelo de respaldo sin calibradores
        return proba
    p = np.clip(np.array([c.predict([proba[k]])[0] for k, c in enumerate(cal)]), _estado["piso"], 1 - _estado["piso"])
    return p / p.sum()


def predecir(d: DatosPrediccion) -> ResultadoPrediccion:
    modelo = _estado["modelo"]
    if modelo is None:
        raise RuntimeError("Modelo no disponible")
    t0 = time.perf_counter()
    # DataFrame con los nombres de entrenamiento: sklearn rechaza cualquier desajuste de nombre/orden.
    x = pd.DataFrame([[d.edad_meses, d.altitud, 1 if d.sexo == "M" else 0, int(d.cred), int(d.suplementacion)]],
                     columns=ORDEN).astype(float)
    bruta = modelo.predict_proba(x)[0]
    clases = _estado["clases"]
    riesgo = str(clases[int(np.argmax(bruta))])  # regla de decisión: ver docstring del módulo
    cal = _calibrar(bruta)
    probs = {c: round(float(p), 4) for c, p in zip(clases, cal)}

    pesos = dict(zip(ORDEN, map(float, modelo.feature_importances_))) if len(modelo.feature_importances_) == 5 else IMPORTANCIAS_REF
    top = sorted(pesos.items(), key=lambda kv: kv[1], reverse=True)[:3]
    factores = [Factor(factor=_texto_factor(k, d), peso=round(v, 3)) for k, v in top]
    ms = int(round((time.perf_counter() - t0) * 1000))
    return ResultadoPrediccion(
        riesgo=riesgo, probabilidad=probs[riesgo], probabilidades={c: probs[c] for c in ORDEN_RIESGO},
        modelo=_estado["nombre"], tiempo_ms=ms, factores_influyentes=factores,
    )
