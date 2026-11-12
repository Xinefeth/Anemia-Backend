# Contrato de la API — AnemIA (valoración de riesgo de anemia infantil)

> Verificado contra el servidor real (uvicorn + modelo Random Forest real, calibrado) el 2026-11-12.
> La API entrega una **valoración de RIESGO** (Bajo / Medio / Alto), **no un diagnóstico**.

## Base URL

| Entorno | URL |
|---|---|
| Local | `http://localhost:8000` (`uvicorn app.main:app --reload`) |
| Producción (Render) | `https://<servicio>.onrender.com` — **por definir** (pendiente de confirmar la URL real) |

Documentación interactiva (OpenAPI): `GET /docs` · esquema: `GET /openapi.json`.
Todas las rutas `/api/*` usan JSON (`Content-Type: application/json`) y, salvo `/api/login`, exigen token.

> En Android/iOS con `localhost`: el emulador Android accede al PC como `http://10.0.2.2:8000`; un celular físico,
> con la IP LAN del PC (ej. `http://192.168.1.20:8000`).

---

## 1. Autenticación

### `POST /api/login`
Request:
```json
{ "usuario": "demo", "contrasena": "demo" }
```
| Campo | Tipo | Reglas |
|---|---|---|
| `usuario` | string | 1–50 caracteres |
| `contrasena` | string | 1–128 caracteres |

Response `200`:
```json
{ "token": "eyJhbGciOi...", "usuario": { "id": 1, "nombre": "Dra. Demo", "rol": "médico" } }
```
Enviar el token en **todas** las demás llamadas: `Authorization: Bearer <token>`. Vigencia: 480 min (por defecto).

| Código | Cuándo | Cuerpo |
|---|---|---|
| 400 | usuario o contraseña incorrectos | `{"detail":"Usuario o contraseña incorrectos"}` |
| 403 | usuario inhabilitado | `{"detail":"Usuario inhabilitado"}` |
| 422 | cuerpo inválido | ver sección 4 |

⚠️ Un login fallido devuelve **400, no 401**, a propósito: la app trata **401 como "sesión expirada"**.

---

## 2. Predicción de riesgo

### `POST /api/predict`  (requiere token)

**Request — las 5 variables son OBLIGATORIAS** (sin valores por defecto: omitir una da **422**; un resultado "por defecto" parecería válido y no lo sería).

| Campo | Tipo | Valores válidos |
|---|---|---|
| `edad_meses` | **entero** | **6 a 59** (ver "Dominio de validez") |
| `sexo` | string | `"M"` o `"F"` (acepta minúscula y espacios: `"m"`) |
| `altitud` | número | **0 a 700** msnm, altitud del **establecimiento** de salud (ver "Dominio de validez") |
| `cred` | booleano | `true`/`false` (también `1`/`0`, `"true"`/`"false"`). Asiste a control CRED |
| `suplementacion` | booleano | igual que `cred`. Recibe suplementación con hierro |

Notas:
- `edad_meses` **debe ser entero**: `18`, `18.0` y `"18"` pasan; **`18.5` da 422**. Si la app calcula meses con decimales, truncar/redondear antes de enviar.
- `null`, `""` o textos como `"si"` en `cred`/`suplementacion` → 422.
- Campos extra (`codigo`, `hemoglobina`, `grupo`, etc.) se **ignoran** sin error. La hemoglobina **nunca** entra al modelo.
- ⚠️ **Cambio de contrato (2026-11-12, dominio):** `edad_meses` pasó de 0–59 a **6–59** y `altitud` de 0–5500 a **0–700**. Fuera de rango → 422 (ver abajo).
- ⚠️ **Cambio de contrato (2026-11-12):** antes `altitud`, `cred` y `suplementacion` eran opcionales. Un cliente que no los envíe recibirá **422** hasta que el formulario los incluya. Lo mismo aplica a `POST /api/valoraciones`.

**Response `200`**

| Campo | Tipo | Descripción |
|---|---|---|
| `riesgo` | string | `"Bajo"`, `"Medio"` o `"Alto"` (ver "Cómo se decide `riesgo`") |
| `probabilidades` | objeto `{Bajo, Medio, Alto}` | probabilidad **calibrada** de cada clase; suman 1 (±0.0002 por redondeo). Nunca 0 ni 1 (mín. 0.001) |
| `probabilidad` | número 0–1 | `probabilidades[riesgo]` (la de la clase devuelta). Se mantiene por compatibilidad |
| `modelo` | string | p. ej. `"Random Forest - Modelo B (sin hemoglobina)"`. Si fuera el de respaldo contendría `[RESPALDO SINTETICO - NO ES EL MODELO REAL]` |
| `tiempo_ms` | entero | tiempo de cálculo del modelo en el servidor |
| `factores_influyentes` | lista de `{factor: string, peso: número}` | los 3 factores con mayor importancia **global** del modelo (no por niño) |

Ejemplo real:
```json
{
  "riesgo": "Alto",
  "probabilidad": 0.3158,
  "probabilidades": {"Bajo": 0.6767, "Medio": 0.0075, "Alto": 0.3158},
  "modelo": "Random Forest - Modelo B (sin hemoglobina)",
  "tiempo_ms": 36,
  "factores_influyentes": [
    {"factor": "No asiste a control CRED", "peso": 0.302},
    {"factor": "Edad del niño (12 meses)", "peso": 0.299},
    {"factor": "Altitud de residencia (300 msnm)", "peso": 0.182}
  ]
}
```

### Dominio de validez (rangos que acepta la API)

El modelo solo es válido para el tipo de niño con el que se entrenó: **niños de 6 a 59 meses atendidos en establecimientos de salud de Trujillo**
(SIEN-HIS 2025+2026). Fuera de ese dominio el modelo extrapolaría sin sentido clínico, así que la API **rechaza** la entrada con 422:

| Campo | Rango aceptado | Por qué |
|---|---|---|
| `edad_meses` | 6 a 59 | el dataset tiene niños de 6.0 a 59.99 meses (el tamizaje de hemoglobina empieza a los 6 meses) |
| `altitud` | 0 a 700 msnm | es la altitud del **establecimiento** y en el entrenamiento solo tomó 10 valores (10–659 msnm). Una altitud de 3400 m no es "más riesgo": el modelo la trataría como el establecimiento de 659 m, que tiene mucha más anemia |

Formato del error (el `type` es siempre `fuera_de_dominio_modelo`, y `ctx` trae el rango; la app puede mostrar `msg` tal cual):
```json
{"detail":[{"type":"fuera_de_dominio_modelo","loc":["body","edad_meses"],
  "msg":"edad_meses debe estar entre 6 y 59 meses: el modelo se entrenó con niños de 6 a 59 meses y no es válido fuera de ese rango",
  "input":4,"ctx":{"min":6,"max":59}}]}
{"detail":[{"type":"fuera_de_dominio_modelo","loc":["body","altitud"],
  "msg":"altitud debe estar entre 0 y 700 msnm: el modelo solo es válido para establecimientos de Trujillo (entrenado con altitudes de 10 a 659 msnm)",
  "input":3400,"ctx":{"min":0,"max":700}}]}
```
Aplica a `/api/predict`, `/api/valoraciones` y `/api/ninos`.

> **RN01 pendiente de validar con el asesor.** La regla de negocio RN01 ("menores de cinco años", 0–59 meses) todavía no está confirmada. Mientras tanto la API exige 6–59 meses por el dominio del modelo. Si el asesor valida otro rango, se cambia en un solo lugar (`app/core/dominio.py`) y se reentrena si hace falta.

### Cómo se decide `riesgo` y qué significan las probabilidades (leer antes de diseñar la pantalla)

- **`riesgo` es una alerta de tamizaje sensible**, no la clase más probable. Se decide con el modelo entrenado con SMOTE (a priori balanceado). Por eso un niño puede tener `riesgo: "Alto"` con `probabilidades.Alto = 0.32` y `Bajo = 0.68`: **es lo esperado**. En la población real solo ~0.5 % de los niños es "Alto", así que con estas 5 variables la probabilidad calibrada de Alto rara vez supera 0.3.
- **`probabilidades` están calibradas** (reflejan frecuencias reales observadas en el dataset de Trujillo): `Alto: 0.32` significa que, entre niños con ese perfil, ~32 % tuvo anemia moderada/severa. Es la cifra adecuada para el anillo de riesgo.
- ⚠️ **Calibradas a una prevalencia de ~2.8 %** (anemia total en el dataset de entrenamiento: Medio 2.3 %, Alto 0.5 %). En poblaciones con **mayor prevalencia pueden SUBESTIMAR el riesgo real**. No presentarlas como probabilidad válida para cualquier población (ver `calibracion.advertencia` en `ml/artefactos/modelo_anemia_rf.meta.json`).
- **No usar `max(probabilidades)` para decidir la clase** (daría "Bajo" casi siempre). Usar `riesgo`.
- Los **umbrales de alerta** (qué probabilidad dispara "Alto"/"Medio") están **pendientes de decisión con el asesor**; cuando se definan, cambiará el cálculo de `riesgo` en el servidor, no el formato de la respuesta.
- `factores_influyentes.peso` es la importancia **global** del modelo (casi igual para todos los niños), **no** una explicación individual. En la app rotular como **"factores generales del modelo"**, nunca como "por qué este niño salió Alto".
- Calidad esperada (conjunto de prueba, ver `ml/artefactos/modelo_anemia_rf.meta.json`): detecta ~21 % de los casos Alto y ~31 % de los Medio; es un **apoyo al tamizaje, no un diagnóstico**. Mostrar siempre ese aviso.

---

## 3. Salud del servicio

### `GET /health` (público, también `HEAD`)
```json
{ "estado": "ok", "modelo_cargado": true }
```
Siempre `200` si el proceso vive. Si `modelo_cargado` es `false`, `/api/predict` responderá `503`.

---

## 4. Errores

| Código | Significado | Cuerpo |
|---|---|---|
| 401 | falta token, token inválido/expirado o usuario inhabilitado | `{"detail":"No autenticado"}` (+ header `WWW-Authenticate: Bearer`) → la app debe volver al login |
| 422 | validación del cuerpo | `{"detail":[{"type","loc":["body","<campo>"],"msg","input"}]}` (lista; un elemento por campo inválido) |
| 503 | modelo no cargado | `{"detail":"Modelo no disponible"}` |

Ejemplos reales de 422:
```json
{"detail":[{"type":"fuera_de_dominio_modelo","loc":["body","edad_meses"],"msg":"edad_meses debe estar entre 6 y 59 meses: el modelo se entrenó con niños de 6 a 59 meses y no es válido fuera de ese rango","input":-3,"ctx":{"min":6,"max":59}}]}
{"detail":[{"type":"literal_error","loc":["body","sexo"],"msg":"Input should be 'M' or 'F'","input":"X","ctx":{"expected":"'M' or 'F'"}}]}
{"detail":[{"type":"missing","loc":["body","edad_meses"],"msg":"Field required","input":{"altitud":34}}]}
```
Los `msg` están en inglés; la app debe mostrar sus propios mensajes usando `loc` para saber qué campo falló.

---

## 5. Ejemplo curl

```bash
# 1) Login y token
TOKEN=$(curl -s -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"usuario":"demo","contrasena":"demo"}' | sed 's/.*"token":"\([^"]*\)".*/\1/')

# 2) Predicción
curl -X POST http://localhost:8000/api/predict \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"edad_meses":12,"altitud":300,"sexo":"F","cred":false,"suplementacion":false}'   # las 5 son obligatorias
```

---

## 6. CORS

- **App móvil nativa (Flutter Android/iOS): CORS no aplica**; no requiere configuración.
- **Flutter web / navegador:** en desarrollo se permite cualquier puerto de `localhost`/`127.0.0.1` (y por defecto `CORS_ORIGENES=*`). Verificado: el preflight `OPTIONS` con `Authorization, Content-Type` responde 200 con `access-control-allow-origin`.
- **Producción:** solo los orígenes de la variable `CORS_ORIGENES` (separados por coma, p. ej. `https://mi-front.com`). Si el front web usa otro dominio, hay que añadirlo ahí.
- La API no usa cookies (`allow_credentials=false`); la autenticación es solo por header `Authorization`.

---

## 7. Otros endpoints (resumen)

Todos requieren token. Detalle completo de campos en `/docs`.

| Método | Ruta | Uso |
|---|---|---|
| POST / GET | `/api/valoraciones` | guardar valoración (el servidor **recalcula** el riesgo) / historial (`?riesgo=`, `?q=`) |
| GET / DELETE | `/api/valoraciones/{id}` | detalle / eliminar |
| GET | `/api/dashboard` | totales por riesgo y recientes |
| GET | `/api/reporte?desde=&hasta=` | indicadores PC, TR, TT por grupo |
| GET / POST | `/api/ninos` · GET / PUT / DELETE `/api/ninos/{id}` | gestión de niños (código anónimo). POST/PUT exigen `codigo`, `edad_meses`, `sexo`, `altitud`, `cred` y `suplementacion` (422 si falta alguno); `hemoglobina` y `grupo` son opcionales |
| GET / POST | `/api/usuarios` · PUT / DELETE `/api/usuarios/{id}` | gestión de usuarios (solo roles `administrador`/`médico`) |
