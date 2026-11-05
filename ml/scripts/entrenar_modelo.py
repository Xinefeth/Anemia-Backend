"""
Entrenamiento del Modelo B (Random Forest SIN hemoglobina) - CRISP-DM: Modelado.
Reproduce el enfoque B del cuaderno Modelo_Anemia_CRISP_DM.ipynb:
  - features (orden que usa la API): EdadMeses, AlturaREN, Sexo_num (M=1, F=0), Cred, Suplementacion
  - objetivo: Riesgo (Bajo / Medio / Alto), derivado de Dx_anemia
  - split 70/30 estratificado, random_state=42, SMOTE solo en train (si imbalanced-learn está instalado)
  - RandomForest(n_estimators=150, max_depth=12, class_weight='balanced')
La hemoglobina NO se usa (evita data leakage).

Uso (desde la raíz del repo):  python ml/scripts/entrenar_modelo.py [--datos trujillo_modelo.csv] [--salida modelos/modelo_anemia_rf.pkl]
"""
import argparse
import json
import os

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FEATURES = ["EdadMeses", "AlturaREN", "Sexo_num", "Cred", "Suplementacion"]
NOMBRES = ["edad_meses", "altitud", "sexo", "cred", "suplementacion"]


def entrenar(datos: str, salida: str) -> None:
    if not os.path.exists(datos):
        raise SystemExit(f"No existe {datos}. Para desarrollo use scripts/generar_modelo_respaldo.py")
    df = pd.read_csv(datos)
    X, y = df[FEATURES].astype(float).values, df["Riesgo"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.30, stratify=y, random_state=42)
    try:
        from imblearn.over_sampling import SMOTE
        X_tr, y_tr = SMOTE(random_state=42, k_neighbors=5).fit_resample(X_tr, y_tr)
        print("SMOTE aplicado al conjunto de entrenamiento")
    except ImportError:
        print("imbalanced-learn no instalado: se entrena solo con class_weight='balanced'")
    modelo = RandomForestClassifier(n_estimators=150, max_depth=12, class_weight="balanced", random_state=42)
    modelo.fit(X_tr, y_tr)
    y_pred = modelo.predict(X_te)
    print("Matriz de confusión:\n", confusion_matrix(y_te, y_pred, labels=modelo.classes_))
    print(classification_report(y_te, y_pred, zero_division=0))
    print("Importancias:", dict(zip(NOMBRES, modelo.feature_importances_.round(3))))
    os.makedirs(os.path.dirname(salida), exist_ok=True)
    joblib.dump(modelo, salida)
    with open(os.path.splitext(salida)[0] + ".meta.json", "w", encoding="utf-8") as f:
        json.dump({"sintetico": False, "datos": os.path.basename(datos), "registros": len(df),
                   "features": NOMBRES}, f)
    print("Modelo guardado en:", salida)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--datos", default=os.path.join(RAIZ, "trujillo_modelo.csv"))
    p.add_argument("--salida", default=os.path.join(RAIZ, "modelos", "modelo_anemia_rf.pkl"))
    a = p.parse_args()
    entrenar(a.datos, a.salida)
