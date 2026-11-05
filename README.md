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
| GET/POST | `/api/ninos` | RF08/RF09 (`?q=` por código) y RF07; 409 si el código ya existe |
| GET/PUT/DELETE | `/api/ninos/{id}` | RF10/RF11; DELETE borra también sus valoraciones |
| GET/POST | `/api/usuarios` | RF04/RF03; solo roles `administrador` o `médico` (403 si no) |
| PUT/DELETE | `/api/usuarios/{id}` | RF05; DELETE = inhabilitar (`activo=false`, no puede iniciar sesión) |

`edad_meses` va de 0 a 59 (RN01: menores de cinco años). Roles: `médico`, `enfermero`, `administrador`.
CORS: en desarrollo se permite cualquier puerto de `localhost`/`127.0.0.1` además de `CORS_ORIGENES`;
en producción solo los orígenes de `CORS_ORIGENES`.

### Reporte (`GET /api/reporte?desde=&hasta=`)
Calculado por grupo (`control` / `experimental`) sobre las valoraciones con `fecha` en el periodo (por defecto, 30 días).
- **PC** (% clasificaciones correctas) = valoraciones cuyo riesgo coincide con el riesgo de **referencia por Hb medida** /
  valoraciones **con Hb**. La Hb se ajusta por altitud (OMS 2011, desde 1000 msnm); referencia: <10 Alto, 10-<11 Medio,
  >=11 Bajo. Las valoraciones sin Hb **se excluyen del denominador**. Ojo: el Modelo B no usa Hb, así que un niño con
  Hb baja clasificado "Bajo" cuenta como error (comportamiento esperado).
- **TR** (tiempo de respuesta) = promedio de `tiempo_ms` de las valoraciones, **en segundos** con 3 decimales
  (mide el cálculo en el servidor, sin red).
- **TT** (tasa de tamizaje, %) = niños registrados en el grupo que tienen alguna valoración en el periodo /
  niños registrados en el grupo (el grupo del niño es el de su última valoración o el que se le asigne en `/api/ninos`). Máx. 100.
- Un grupo sin datos devuelve `0.0`: la UI debe usar los conteos para mostrar "sin datos" (n = 0).

Campos de respuesta: `desde, hasta, total, pc, tr, tt` (cada uno `{control, experimental}`) y los conteos usados
`n_valoraciones` (base de TR), `n_pc` (denominador de PC), `n_tt_valorados`, `n_tt_registrados` (numerador/denominador de TT),
también `{control, experimental}`.

## Despliegue en Render
1. Subir este repo a GitHub (incluyendo `modelos/modelo_anemia_rf.pkl`).
2. Render > New > Blueprint > seleccionar el repo (`render.yaml`): crea el web service Docker y PostgreSQL
   (`DATABASE_URL` enlazada, `SECRET_KEY` generada). Define `DEMO_CONTRASENA` cuando lo pida
   (en producción no se admite la clave `demo`). Ajusta `CORS_ORIGENES` si hace falta.
3. Render provee HTTPS y el puerto `$PORT`. Verificar `https://<servicio>.onrender.com/health`.
4. En la app Flutter: `--dart-define=API_URL=https://<servicio>.onrender.com`.

`postgres://` se convierte automáticamente a `postgresql+psycopg://`. SQLite solo para dev/tests.
En `ENTORNO=production` la app no arranca con SECRET_KEY débil ni con SQLite.
