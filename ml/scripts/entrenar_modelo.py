"""
Entrenamiento del Modelo B (Random Forest SIN hemoglobina) - CRISP-DM: Modelado.
Fuente única y reproducible del modelo que sirve la API.

Diseño
  - Features NOMBRADAS (DataFrame), en el orden exacto de la API: edad_meses, altitud, sexo (M=1, F=0), cred, suplementacion.
    El modelo guarda feature_names_in_, así sklearn rechaza un cambio de nombre/orden en vez de predecir mal en silencio.
  - Objetivo: Riesgo (Bajo/Medio/Alto) = Normal->Bajo, Anemia Leve->Medio, Moderada+Severa->Alto. La Hb NO es variable.
  - Split 70/30 estratificado; SMOTE (k=5) SOLO sobre datos de entrenamiento (dentro de cada fold en la CV);
    RandomForest(150 árboles, max_depth=12, class_weight='balanced').
  - REGLA DE DECISIÓN (clase `riesgo`): argmax de las probabilidades del RF entrenado con SMOTE (a priori balanceado).
    Es una regla de tamizaje sensible, NO la clase más probable en la población real.
  - PROBABILIDADES: calibradas (isotónica por clase, ajustadas con predicciones fuera de muestra de una CV 5-fold
    estratificada, con SMOTE solo dentro de cada fold) para que reflejen la frecuencia real. Con ellas, argmax daría
    siempre "Bajo" (prevalencia de Alto = 0.5 %), por eso NO se usan para decidir la clase.
  - Los UMBRALES para priorizar recall de Alto son una decisión clínica/de tesis (asesor): el .meta.json incluye la
    curva umbral -> alertas/recall/precisión sobre el conjunto de prueba para decidirlo con datos.

Artefacto: un único .pkl (joblib) con un dict {formato, modelo (RF), clases, features, calibradores, piso_probabilidad}.
Solo contiene objetos de scikit-learn/numpy (la API no necesita imbalanced-learn). Se escribe SOLO si todo terminó bien
(archivos temporales + renombrado atómico).

Uso (desde la raíz):
  python ml/scripts/entrenar_modelo.py --datos ml/data/trujillo_modelo.csv [--salida ml/artefactos/modelo_anemia_rf.pkl] [--seed 42]
"""
import argparse
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone

import imblearn
import joblib
import numpy as np
import pandas as pd
import sklearn
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix, log_loss, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FORMATO = 2
# Nombres y orden de las features = los de la API (app/modules/prediccion/service.py: ORDEN).
FEATURES = ["edad_meses", "altitud", "sexo", "cred", "suplementacion"]
MAPA_RIESGO = {"Normal": "Bajo", "Anemia Leve": "Medio", "Anemia Moderada": "Alto", "Anemia Severa": "Alto"}
HIPERPARAMETROS = dict(n_estimators=150, max_depth=12, class_weight="balanced")
PISO_PROBABILIDAD = 0.001  # nunca se informa 0 % ni 100 %: con n finito no hay certeza
FOLDS = 5
# Rango que acepta la API (debe coincidir con app/core/dominio.py; un test lo verifica).
RANGO_API = {"edad_meses": [6, 59], "altitud": [0, 700]}


def sha256(ruta: str) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def cargar(datos: str) -> tuple[pd.DataFrame, np.ndarray]:
    """Lee el CSV (limpieza como en el cuaderno, secc. 3.2) y devuelve X (DataFrame nombrado) e y."""
    df = pd.read_csv(datos)
    if "Riesgo" not in df.columns:
        df["Riesgo"] = df["Dx_anemia"].map(MAPA_RIESGO)
    for c in ["EdadMeses", "AlturaREN", "Cred", "Suplementacion"]:
        df[c] = pd.to_numeric(df[c].astype(str).str.strip(), errors="coerce")
    df["Sexo_num"] = (df["Sexo"].astype(str).str.strip() == "M").astype(int)
    df = df.dropna(subset=["EdadMeses", "AlturaREN", "Cred", "Suplementacion", "Riesgo"])
    X = pd.DataFrame({"edad_meses": df["EdadMeses"], "altitud": df["AlturaREN"], "sexo": df["Sexo_num"],
                      "cred": df["Cred"], "suplementacion": df["Suplementacion"]})[FEATURES].astype(float)
    return X.reset_index(drop=True), df["Riesgo"].values


def pipeline_base(seed: int) -> Pipeline:
    """SMOTE + RF. imblearn aplica SMOTE solo al ajustar (fit), nunca al predecir ni a los folds de validación."""
    return Pipeline([("smote", SMOTE(random_state=seed, k_neighbors=5)),
                     ("rf", RandomForestClassifier(**HIPERPARAMETROS, random_state=seed, n_jobs=-1))])


def aplicar_calibradores(proba: np.ndarray, calibradores: list, piso: float = PISO_PROBABILIDAD) -> np.ndarray:
    """Calibra cada clase, acota a [piso, 1-piso] y renormaliza a suma 1. (Misma lógica que usa la API.)"""
    cal = np.column_stack([c.predict(proba[:, k]) for k, c in enumerate(calibradores)])
    cal = np.clip(cal, piso, 1 - piso)
    return cal / cal.sum(axis=1, keepdims=True)


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    """Intervalo de confianza 95 % (Wilson) de una proporción k/n."""
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    mitad = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(float(centro - mitad), 4), round(float(centro + mitad), 4)]


def brier_multiclase(p: np.ndarray, y: np.ndarray, clases: list) -> float:
    Y = np.stack([(y == c).astype(float) for c in clases], axis=1)
    return float(((p - Y) ** 2).sum(axis=1).mean())


def ece_clase(p: np.ndarray, y: np.ndarray, clase: str, clases: list, bins: int = 10) -> float:
    """Error de calibración esperado de una clase (bins por cuantiles)."""
    pc, yc = p[:, clases.index(clase)], (y == clase).astype(float)
    bordes = np.unique(np.quantile(pc, np.linspace(0, 1, bins + 1)))
    idx = np.clip(np.digitize(pc, bordes[1:-1]), 0, max(len(bordes) - 2, 0))
    return float(sum(abs(pc[idx == b].mean() - yc[idx == b].mean()) * (idx == b).mean() for b in np.unique(idx)))


def calidad_probabilidades(p: np.ndarray, y: np.ndarray, clases: list) -> dict:
    return {"log_loss": round(float(log_loss(y, p, labels=clases)), 4),
            "brier": round(brier_multiclase(p, y, clases), 4),
            "ece": {c: round(ece_clase(p, y, c, clases), 4) for c in clases}}


def validacion_cruzada(X: pd.DataFrame, y: np.ndarray, clases: list, seed: int) -> dict:
    """CV estratificada de FOLDS pliegues sobre TODO el dataset (SMOTE solo dentro de cada pliegue)."""
    skf = StratifiedKFold(FOLDS, shuffle=True, random_state=seed)
    filas = {c: {"precision": [], "recall": [], "f1": []} for c in clases}
    for tr, te in skf.split(X, y):
        m = pipeline_base(seed).fit(X.iloc[tr], y[tr])
        inf = classification_report(y[te], m.predict(X.iloc[te]), labels=clases, zero_division=0, output_dict=True)
        for c in clases:
            filas[c]["precision"].append(inf[c]["precision"])
            filas[c]["recall"].append(inf[c]["recall"])
            filas[c]["f1"].append(inf[c]["f1-score"])
    res = {c: {m: {"media": round(float(np.mean(v)), 4), "desv": round(float(np.std(v)), 4),
                   "por_pliegue": [round(float(x), 4) for x in v]} for m, v in d.items()} for c, d in filas.items()}
    return {"pliegues": FOLDS, "estratificada": True, "smote_dentro_de_cada_pliegue": True, "por_clase": res}


def curva_umbrales(p_cal: np.ndarray, y: np.ndarray, clases: list) -> dict:
    """Si se alertara por 'probabilidad calibrada de la clase >= t': cuántas alertas, recall y precisión (conjunto de prueba)."""
    out = {}
    for c in ("Alto", "Medio"):
        real, pc, filas = (y == c), p_cal[:, clases.index(c)], []
        for t in (0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30):
            a = pc >= t
            tp = int((a & real).sum())
            filas.append({"umbral": t, "alertas": int(a.sum()), "recall": round(tp / real.sum(), 4),
                          "precision": round(tp / a.sum(), 4) if a.sum() else None})
        out[c] = filas
    return out


def entrenar(datos: str, salida: str, seed: int) -> None:
    if not os.path.exists(datos):
        raise SystemExit(f"No existe {datos}. Para desarrollo use ml/scripts/generar_modelo_respaldo.py")
    X, y = cargar(datos)
    clases = sorted(set(y))
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.30, stratify=y, random_state=seed)
    print(f"Registros: {len(X)} | train {len(y_tr)} | test {len(y_te)} | clases {clases}")

    print(f"\n[1/4] Validación cruzada estratificada ({FOLDS} pliegues, todo el dataset)...")
    cv = validacion_cruzada(X, y, clases, seed)
    for c in clases:
        d = cv["por_clase"][c]
        print(f"  {c:<6} recall {d['recall']['media']:.3f} ± {d['recall']['desv']:.3f} | "
              f"precision {d['precision']['media']:.3f} ± {d['precision']['desv']:.3f} | F1 {d['f1']['media']:.3f} ± {d['f1']['desv']:.3f}")

    print("\n[2/4] Calibración: predicciones fuera de muestra (CV sobre train) -> isotónica por clase...")
    skf = StratifiedKFold(FOLDS, shuffle=True, random_state=seed)
    p_oof = cross_val_predict(pipeline_base(seed), X_tr, y_tr, cv=skf, method="predict_proba")
    calibradores = [IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(p_oof[:, k], (y_tr == c).astype(float))
                    for k, c in enumerate(clases)]

    print("[3/4] Modelo final (SMOTE solo en train)...")
    final = pipeline_base(seed).fit(X_tr, y_tr)
    rf = final.named_steps["rf"]
    rf.set_params(n_jobs=None)  # en la API no se paraleliza (servidor pequeño)
    assert list(rf.classes_) == clases and list(rf.feature_names_in_) == FEATURES

    print("[4/4] Evaluación en el conjunto de prueba...")
    proba_raw = rf.predict_proba(X_te)
    pred = np.array(clases)[proba_raw.argmax(axis=1)]
    assert (pred == rf.predict(X_te)).all()
    proba_cal = aplicar_calibradores(proba_raw, calibradores)

    cm = confusion_matrix(y_te, pred, labels=clases)
    informe = classification_report(y_te, pred, labels=clases, zero_division=0, output_dict=True)
    auc_raw = float(roc_auc_score(y_te, proba_raw, multi_class="ovr", average="macro", labels=clases))
    auc_cal = float(roc_auc_score(y_te, proba_cal, multi_class="ovr", average="macro", labels=clases))
    cal_antes, cal_despues = calidad_probabilidades(proba_raw, y_te, clases), calidad_probabilidades(proba_cal, y_te, clases)
    imp = dict(zip(FEATURES, rf.feature_importances_.round(4).tolist()))

    print("\nMatriz de confusión (filas=real, columnas=predicho), clases:", clases)
    print(cm)
    print("\n" + classification_report(y_te, pred, labels=clases, zero_division=0, digits=3))
    print(f"ROC-AUC macro: {auc_raw:.4f} (probabilidades del RF) | {auc_cal:.4f} (calibradas) | accuracy {accuracy_score(y_te, pred):.4f}")
    print("Calidad de probabilidades  antes:", cal_antes)
    print("Calidad de probabilidades después:", cal_despues)
    for c in ("Alto", "Medio"):
        k, n = int(cm[clases.index(c), clases.index(c)]), int((y_te == c).sum())
        print(f"Recall {c}: {k}/{n} = {k / n:.3f}  IC95% Wilson {wilson(k, n)}")
    print("Importancia de variables:", imp)

    prev = {c: round(float((y == c).mean()), 4) for c in clases}
    prev["anemia_total"] = round(float((y != "Bajo").mean()), 4)
    dominio = {
        "poblacion": "niños atendidos en establecimientos de salud de Trujillo (SIEN-HIS 2025+2026)",
        "edad_meses": {"min_entrenamiento": round(float(X["edad_meses"].min()), 2), "max_entrenamiento": round(float(X["edad_meses"].max()), 2),
                       "rango_api": RANGO_API["edad_meses"]},
        "altitud": {"nota": "altitud del ESTABLECIMIENTO (no de la residencia); solo toma estos valores en el entrenamiento",
                    "valores_entrenamiento": sorted(int(v) for v in X["altitud"].unique()), "rango_api": RANGO_API["altitud"]},
        "rn01": "RN01 (menores de 5 años, 0-59 meses) PENDIENTE DE VALIDAR CON EL ASESOR; la API exige 6-59 meses por el dominio del modelo.",
    }
    por_clase = {}
    for j, c in enumerate(clases):
        k, n = int(cm[j, j]), int(informe[c]["support"])
        por_clase[c] = {"precision": round(informe[c]["precision"], 4), "recall": round(informe[c]["recall"], 4),
                        "f1": round(informe[c]["f1-score"], 4), "soporte": n, "recall_ic95": wilson(k, n)}
    meta = {
        "sintetico": False,
        "formato": FORMATO,
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version_sklearn": sklearn.__version__, "version_imblearn": imblearn.__version__,
        "version_numpy": np.__version__, "version_pandas": pd.__version__, "version_python": platform.python_version(),
        "random_state": seed,
        "hiperparametros": {k: v for k, v in rf.get_params().items()
                            if k in ("n_estimators", "max_depth", "class_weight", "random_state", "criterion",
                                     "min_samples_split", "min_samples_leaf", "max_features")},
        "features": FEATURES,
        "codificacion": {"sexo": "M=1, F=0", "cred": "1=asiste a control CRED", "suplementacion": "1=recibe hierro",
                         "altitud": "msnm", "edad_meses": "meses cumplidos (entero 0-59)"},
        "clases": clases,
        "datos": os.path.basename(datos), "sha256_datos": sha256(datos),
        "registros": int(len(X)), "n_train_original": int(len(y_tr)), "n_train_balanceado": int(pd.Series(y_tr).value_counts().max()) * len(clases),  # SMOTE nivela a la clase mayoritaria
        "n_test": int(len(y_te)),
        "distribucion_test": {c: int((y_te == c).sum()) for c in clases},
        "regla_decision": ("riesgo = argmax de las probabilidades del RF entrenado con SMOTE (a priori balanceado). "
                           "NO es el argmax de las probabilidades calibradas (daría siempre 'Bajo'). "
                           "Umbrales de alerta: pendientes de definir con el asesor (ver curva_umbrales)."),
        "prevalencia_entrenamiento": prev,
        "dominio_validez": dominio,
        "calibracion": {"metodo": "isotonica por clase (one-vs-rest) + normalizacion", "piso_probabilidad": PISO_PROBABILIDAD,
                        "prevalencia_calibrada": prev,
                        "advertencia": (f"Las probabilidades están calibradas a la prevalencia del dataset de entrenamiento "
                                        f"(anemia total {prev['anemia_total'] * 100:.1f} %: Medio {prev['Medio'] * 100:.1f} %, Alto {prev['Alto'] * 100:.1f} %). "
                                        "En poblaciones con mayor prevalencia pueden SUBESTIMAR el riesgo real."),
                        "ajustada_con": f"predicciones fuera de muestra de CV {FOLDS}-fold estratificada sobre train (SMOTE solo dentro de cada fold)",
                        "antes": cal_antes, "despues": cal_despues},
        "metricas": {
            "accuracy": round(float(accuracy_score(y_te, pred)), 4),
            "roc_auc_macro": round(auc_raw, 4), "roc_auc_macro_calibrada": round(auc_cal, 4),
            "por_clase": por_clase,
            "matriz_confusion": {"orden_clases": clases, "valores": cm.tolist()},
        },
        "validacion_cruzada": cv,
        "curva_umbrales_prob_calibrada": curva_umbrales(proba_cal, y_te, clases),
        "importancias": imp,
    }

    bundle = {"formato": FORMATO, "modelo": rf, "clases": clases, "features": FEATURES,
              "calibradores": calibradores, "piso_probabilidad": PISO_PROBABILIDAD}
    # Todo salió bien: recién ahora se escriben los artefactos (temporal + renombrado atómico).
    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    ruta_meta = os.path.splitext(salida)[0] + ".meta.json"
    tmp_pkl, tmp_meta = salida + ".tmp", ruta_meta + ".tmp"
    try:
        joblib.dump(bundle, tmp_pkl)
        with open(tmp_meta, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        # Releer lo escrito: el artefacto debe cargar y dar las mismas probabilidades.
        b2 = joblib.load(tmp_pkl)
        assert np.allclose(aplicar_calibradores(b2["modelo"].predict_proba(X_te), b2["calibradores"]), proba_cal)
        os.replace(tmp_pkl, salida)
        os.replace(tmp_meta, ruta_meta)
    finally:
        for t in (tmp_pkl, tmp_meta):
            if os.path.exists(t):
                os.remove(t)
    print("\nModelo guardado en:", salida, f"({os.path.getsize(salida) / 1e6:.1f} MB)")
    print("Metadatos en:", ruta_meta)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--datos", default=os.path.join(RAIZ, "ml", "data", "trujillo_modelo.csv"), help="ruta del CSV")
    p.add_argument("--salida", default=os.path.join(RAIZ, "ml", "artefactos", "modelo_anemia_rf.pkl"))
    p.add_argument("--seed", type=int, default=42, help="random_state (split, SMOTE, RF y CV)")
    a = p.parse_args()
    try:
        entrenar(a.datos, a.salida, a.seed)
    except Exception as e:  # no se deja ningún artefacto a medias
        print("ENTRENAMIENTO FALLIDO, no se guardó nada:", repr(e), file=sys.stderr)
        raise
