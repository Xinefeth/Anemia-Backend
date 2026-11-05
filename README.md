# AnemIA - Backend

API REST (FastAPI) para la **valoración de riesgo** (Bajo / Medio / Alto, no diagnóstico) de anemia infantil.
Modelo B: Random Forest **sin hemoglobina** (evita data leakage). Entrada del modelo, en orden:
`[edad_meses, altitud, sexo_num (M=1,F=0), cred, suplementacion]`.

## Estructura
```
app/core        configuración (env) y seguridad (bcrypt, JWT)
app/db          conexión SQLAlchemy
app/models      entidades de BD: USUARIO, NINO, VALORACION
app/schemas     esquemas Pydantic (contrato JSON con la app Flutter)
app/services    predictor (modelo), valoraciones, reportes (PC/TR/TT)
app/routers     auth, predicción, valoraciones/dashboard/reporte
ml/scripts      entrenar_modelo.py (modelo real, reproducible)
scripts         generar_modelo_respaldo.py (modelo SINTETICO de respaldo)
modelos         modelo_anemia_rf.pkl (+ .meta.json)
tests           pytest
```
Las tablas se crean al iniciar (`create_all`). El niño solo tiene `codigo` (anonimizado).

## Instalación y uso local
```bash
python -m venv .venv && .venv/Scripts/activate      # Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                                 # usa SQLite por defecto
uvicorn app.main:app --reload                        # http://localhost:8000/docs
pytest
```
Usuario demo (seed, configurable con `DEMO_*`): `demo` / `demo`.

## Modelo ML
- Reentrenar con datos reales: `python ml/scripts/entrenar_modelo.py --datos trujillo_modelo.csv`
  (instala `ml/requirements.txt`; usa SMOTE como el cuaderno). Genera `modelos/modelo_anemia_rf.pkl`.
- Si falta el `.pkl`, `python scripts/generar_modelo_respaldo.py` crea un modelo **SINTETICO** (marcado en
  `modelo` de la respuesta). No usar clínicamente. El Dockerfile lo ejecuta solo si no hay `.pkl`.
- El `.pkl` debe versionarse (o incluirse en la imagen) para que Render use el modelo real. Debe cargarse
  con la misma versión de scikit-learn (1.7.0) con que se entrenó.

## Endpoints (JWT `Authorization: Bearer <token>`, salvo login y health)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | estado (público) |
| POST | `/api/login` | `{usuario, contrasena}` -> `{token, usuario:{id,nombre,rol}}`; error 400 si credenciales malas |
| POST | `/api/predict` | `{edad_meses, altitud, sexo:"M"/"F", cred, suplementacion}` -> `{riesgo, probabilidad, modelo, tiempo_ms, factores_influyentes:[{factor,peso}]}` |
| POST | `/api/valoraciones` (alias `/api/valoracion`) | guarda; añade `codigo`, `grupo`, `hemoglobina?`, `fecha?`; el servidor recalcula el riesgo |
| GET | `/api/valoraciones` (alias `/api/historial`) | filtros `riesgo`, `q` (código o aaaa-mm-dd) |
| GET/DELETE | `/api/valoraciones/{id}` | detalle / eliminar |
| GET | `/api/dashboard` | totales por riesgo, Hb promedio, últimos 7 días, recientes |
| GET | `/api/reporte?desde=&hasta=` | PC, TR, TT por grupo control/experimental |

Definiciones del reporte: **PC** = % de valoraciones cuyo riesgo coincide con el riesgo de referencia por Hb
medida (ajustada por altitud; <10 Alto, 10-<11 Medio, >=11 Bajo); **TR** = tiempo de respuesta promedio (s);
**TT** = niños del grupo valorados en el periodo / niños del grupo registrados (%).

## Despliegue en Render
1. Subir este repo a GitHub (incluyendo `modelos/modelo_anemia_rf.pkl`).
2. Render > New > Blueprint > seleccionar el repo (`render.yaml`): crea el web service Docker y PostgreSQL
   (`DATABASE_URL` enlazada, `SECRET_KEY` generada). Define `DEMO_CONTRASENA` cuando lo pida
   (en producción no se admite la clave `demo`). Ajusta `CORS_ORIGENES` si hace falta.
3. Render provee HTTPS y el puerto `$PORT`. Verificar `https://<servicio>.onrender.com/health`.
4. En la app Flutter: `--dart-define=API_URL=https://<servicio>.onrender.com`.

`postgres://` se convierte automáticamente a `postgresql+psycopg://`. SQLite solo para dev/tests.
En `ENTORNO=production` la app no arranca con SECRET_KEY débil ni con SQLite.
