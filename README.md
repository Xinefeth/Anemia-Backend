# AnemIA - Backend

API REST (FastAPI) para la **valoración de riesgo** (Bajo / Medio / Alto, no diagnóstico) de anemia infantil.
Modelo B: Random Forest **sin hemoglobina** (evita data leakage). Entrada del modelo, en orden:
`[edad_meses, altitud, sexo_num (M=1,F=0), cred, suplementacion]`.

## Estructura
Arquitectura **modular por funcionalidad**: cada módulo agrupa todo lo suyo (modelo, esquemas, servicio, router)
y dentro mantiene capas ligeras `router -> service -> models`. Los routers solo manejan HTTP; la lógica vive en `service.py`.
```
app/
  main.py              crea la app FastAPI (CORS, routers, /health, lifespan)
  api/                 deps.py (usuario autenticado, roles) y router.py (agrupa los módulos)
  core/                config.py (env), security.py (bcrypt + JWT), tipos.py (Sexo, Grupo, Rol)
  db/                  base.py, session.py (engine/get_db), init_db.py (tablas + seed), migraciones.py
  modules/
    auth/              login
    usuarios/          gestión de usuarios (RF03-RF06)
    ninos/             gestión de niños (RF07-RF11)
    prediccion/        /api/predict + service.py (carga y uso del modelo ML)
    valoraciones/      valoraciones, historial y dashboard
    reportes/          indicadores PC / TR / TT
    (cada módulo: models.py · schemas.py · service.py · router.py, según corresponda)
ml/
  notebooks/           Modelo_Anemia_CRISP_DM.ipynb
  data/                datasets locales (no versionados)
  scripts/             entrenar_modelo.py (real), generar_modelo_respaldo.py (SINTETICO)
  artefactos/          modelo_anemia_rf.pkl (+ .meta.json) que carga la API
tests/                 pytest
```
**Regla de dependencias:** `modules/*` pueden usar `core`, `db` y `api/deps`; un módulo solo importa de otro
lo mínimo (p. ej. `valoraciones` usa `ninos.models` y `prediccion`). `core` no importa de `modules`.
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
- **Reentrenar (fuente única):** `python ml/scripts/entrenar_modelo.py --datos ml/data/trujillo_modelo.csv`
  (instala `ml/requirements.txt`). Hace validación cruzada estratificada, calibra las probabilidades (isotónica) y escribe
  `ml/artefactos/modelo_anemia_rf.pkl` + `.meta.json` (métricas por clase, CV, calibración, curva de umbrales, SHA256 del CSV,
  versiones). Solo guarda si todo terminó bien. El modelo se entrena con **features nombradas** y la API verifica nombre y orden al arrancar.
- `riesgo` = alerta de tamizaje (argmax del RF con SMOTE); `probabilidades` = calibradas **a una prevalencia de ~2.8 %** (la del dataset): pueden subestimar el riesgo en poblaciones con mayor prevalencia. Los umbrales están pendientes de decisión (asesor).
- Si falta el `.pkl`, `python ml/scripts/generar_modelo_respaldo.py` crea un modelo **SINTETICO** (marcado en
  `modelo` de la respuesta). No usar clínicamente. El Dockerfile lo ejecuta solo si no hay `.pkl`.
- El `.pkl` debe versionarse (o incluirse en la imagen) y cargarse con la misma versión de scikit-learn (1.7.0).
- **Contrato de la API para el frontend:** `docs/API_CONTRATO.md`.

## Endpoints (JWT `Authorization: Bearer <token>`, salvo login y health)
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | estado (público) |
| POST | `/api/login` | `{usuario, contrasena}` -> `{token, usuario:{id,nombre,rol}}`; error 400 si credenciales malas |
| POST | `/api/predict` | `{edad_meses, altitud, sexo:"M"/"F", cred, suplementacion}` (las 5 obligatorias) -> `{riesgo, probabilidad, probabilidades:{Bajo,Medio,Alto}, modelo, tiempo_ms, factores_influyentes:[{factor,peso}]}` |
| POST | `/api/valoraciones` (alias `/api/valoracion`) | guarda; añade `codigo`, `grupo`, `hemoglobina?`, `fecha?`; el servidor recalcula el riesgo |
| GET | `/api/valoraciones` (alias `/api/historial`) | filtros `riesgo`, `q` (código o aaaa-mm-dd) |
| GET/DELETE | `/api/valoraciones/{id}` | detalle / eliminar |
| GET | `/api/dashboard` | totales por riesgo, Hb promedio, últimos 7 días, recientes |
| GET | `/api/reporte?desde=&hasta=` | PC, TR, TT por grupo control/experimental |
| GET/POST | `/api/ninos` | RF08/RF09 (`?q=` por código) y RF07; 409 si el código ya existe |
| GET/PUT/DELETE | `/api/ninos/{id}` | RF10/RF11; DELETE borra también sus valoraciones |
| GET/POST | `/api/usuarios` | RF04/RF03; solo roles `administrador` o `médico` (403 si no) |
| PUT/DELETE | `/api/usuarios/{id}` | RF05; DELETE = inhabilitar (`activo=false`, no puede iniciar sesión) |

**Dominio de validez del modelo:** `edad_meses` **6 a 59** y `altitud` **0 a 700 msnm** (solo establecimientos de Trujillo);
fuera de rango la API responde 422. *RN01 (menores de cinco años, 0-59 meses) está **pendiente de validar con el asesor**.*
Roles: `médico`, `enfermero`, `administrador`.
Pendientes y decisiones abiertas: `docs/PENDIENTES.md` (p. ej. la referencia de hemoglobina del PC, ver `app/modules/reportes/README.md`).
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
1. Subir este repo a GitHub (incluyendo `ml/artefactos/modelo_anemia_rf.pkl`).
2. Render > New > Blueprint > seleccionar el repo (`render.yaml`): crea el web service Docker y PostgreSQL
   (`DATABASE_URL` enlazada, `SECRET_KEY` generada). Define `DEMO_CONTRASENA` cuando lo pida
   (en producción no se admite la clave `demo`). Ajusta `CORS_ORIGENES` si hace falta.
3. Render provee HTTPS y el puerto `$PORT`. Verificar `https://<servicio>.onrender.com/health`.
4. En la app Flutter: `--dart-define=API_URL=https://<servicio>.onrender.com`.

`postgres://` se convierte automáticamente a `postgresql+psycopg://`. SQLite solo para dev/tests.
En `ENTORNO=production` la app no arranca con SECRET_KEY débil ni con SQLite.
