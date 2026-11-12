# Pendientes y decisiones — backend / ML AnemIA

Última actualización: 2026-11-12. Rama de trabajo: `refactor/arquitectura-modular-y-modelo-calibrado` (sin merge a `main` hasta indicación).

## Pendientes de validar con el asesor

| # | Tema | Estado | Dónde está documentado |
|---|---|---|---|
| 1 | **Norma y tabla de altitud para la referencia de hemoglobina** (indicador PC). `riesgo_referencia` / `hb_ajustada` **NO se modifican** hasta confirmar. Hoy la referencia coincide solo 90.2 % con la etiqueta de entrenamiento (5,102 lactantes con Hb 10.5–10.96 se cuentan como error). | En validación con el asesor | `app/modules/reportes/README.md` |
| 2 | **RN01** ("menores de cinco años", 0–59 meses). La API exige 6–59 meses por el dominio del modelo; el rango definitivo depende de la validación. | Pendiente de validar con el asesor | `docs/API_CONTRATO.md` · `app/core/dominio.py` · `meta.json` (`dominio_validez.rn01`) |
| 3 | **Umbrales de alerta** (priorizar recall de Alto/Medio aceptando más falsas alarmas). Es una decisión de política de tamizaje. Datos para decidir: `curva_umbrales_prob_calibrada` en `ml/artefactos/modelo_anemia_rf.meta.json`. | Pendiente (decisión clínica/de tesis) | `docs/API_CONTRATO.md` · `meta.json` (`regla_decision`) |

## Decisiones tomadas

| Fecha | Decisión |
|---|---|
| 2026-11-12 | `altitud`, `cred` y `suplementacion` obligatorios en `/api/predict`, `/api/valoraciones` y `/api/ninos` (sin valores por defecto). |
| 2026-11-12 | **Dominio de validez:** `edad_meses` 6–59 y `altitud` 0–700 msnm (solo establecimientos de Trujillo); fuera de rango → 422 (`fuera_de_dominio_modelo`). Se aplica a predicción, valoraciones y niños. |
| 2026-11-12 | `/api/predict` devuelve `probabilidades` calibradas por clase. **Están calibradas a una prevalencia de ~2.8 %** (la del dataset de entrenamiento) y pueden subestimar el riesgo en poblaciones con mayor prevalencia (advertencia en `meta.json` y en el contrato). |
| 2026-11-12 | La regla de decisión de `riesgo` se mantiene (argmax del RF con SMOTE); no se usan trucos de umbral. |
| 2026-11-12 | **Variables extra** (Juntos, SIS, Qaliwarma, consejería, sesión, distrito): probadas aparte con `trujillo_2025.csv` (AUC 0.792 → 0.812); **no se integran** en el modelo ni en la API por ahora. |
| 2026-11-12 | No se usa hemoglobina como entrada del modelo (fuga de datos). |
