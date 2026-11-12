"""
Genera un modelo de RESPALDO para desarrollo/demostración, entrenado con datos SINTETICOS.

!!! NO es el modelo real de la tesis. Sirve solo para que /api/predict funcione cuando
!!! aún no existe ml/artefactos/modelo_anemia_rf.pkl entrenado con ml/data/trujillo_modelo.csv.
El modelo real se entrena con: python ml/scripts/entrenar_modelo.py

Uso (desde la raíz):  python ml/scripts/generar_modelo_respaldo.py [--forzar]
"""
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

SALIDA = os.path.join(os.path.dirname(__file__), "..", "artefactos", "modelo_anemia_rf.pkl")


def main() -> None:
    if os.path.exists(SALIDA) and "--forzar" not in sys.argv:
        print(f"Ya existe {SALIDA}; no se sobrescribe (use --forzar).")
        return
    rng = np.random.default_rng(42)
    n = 4000
    edad = rng.integers(6, 60, n)
    altitud = rng.choice([0, 34, 300, 1500, 2500, 3200], n).astype(float)
    sexo = rng.integers(0, 2, n)          # M=1, F=0
    cred = rng.integers(0, 2, n)          # 1 = asiste a CRED
    supl = rng.integers(0, 2, n)
    # Puntaje de riesgo inventado: más riesgo en menores de 2 años, sin CRED y a mayor altitud.
    score = (np.where(edad < 24, 1.4, 0.4) + (1 - cred) * 1.0 + altitud / 3000
             + (1 - supl) * 0.3 + rng.normal(0, 0.4, n))
    y = np.where(score < 1.2, "Bajo", np.where(score < 2.2, "Medio", "Alto"))
    # DataFrame con las features NOMBRADAS de la API (mismo formato 2 que el modelo real, sin calibradores).
    X = pd.DataFrame({"edad_meses": edad, "altitud": altitud, "sexo": sexo, "cred": cred, "suplementacion": supl}).astype(float)
    rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42).fit(X, y)
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    joblib.dump({"formato": 2, "modelo": rf, "clases": list(rf.classes_), "features": list(X.columns),
                 "calibradores": None, "piso_probabilidad": 0.0}, SALIDA)
    with open(os.path.splitext(SALIDA)[0] + ".meta.json", "w", encoding="utf-8") as f:
        json.dump({"sintetico": True, "aviso": "Modelo de respaldo con datos sintéticos; no usar clínicamente"}, f)
    print(f"Modelo de respaldo SINTETICO guardado en {os.path.abspath(SALIDA)}")


if __name__ == "__main__":
    main()
