# Módulo `reportes` — indicadores PC / TR / TT

`GET /api/reporte?desde=&hasta=` calcula por grupo (`control` / `experimental`) tres indicadores del estudio. La lógica
está en `service.py`; el contrato JSON, en `schemas.py` y en `docs/API_CONTRATO.md`.

## ⚠️ PENDIENTE: referencia de hemoglobina del indicador PC (no modificar hasta validar con el asesor)

**Estado:** `riesgo_referencia()` / `hb_ajustada()` en `service.py` **no se han modificado a propósito**. La norma y la tabla de
ajuste por altitud que debe usarse **aún no están confirmadas** (en validación con el asesor).

**Qué hace hoy** (PC = % de valoraciones cuyo riesgo coincide con la referencia por hemoglobina medida):
- Referencia: Hb < 10 → Alto · 10 a < 11 → Medio · ≥ 11 → Bajo (igual para todas las edades).
- Ajuste por altitud: fórmula OMS 2011, **solo desde 1000 msnm** (por debajo no se corrige nada).

**Por qué es un problema:** el modelo se entrenó con una definición distinta (revisada el 2026-11-12 sobre `trujillo_modelo.csv`, 55,207 niños):
- Los cortes **dependen de la edad**: normal si Hb ≥ **10.5 g/dL en menores de 24 meses** y ≥ **11.0 en mayores**; en menores de 24 meses, Leve = 9.5–10.4 y Moderada = 7.0–9.4 (en mayores: Leve 10.0–10.9, Moderada 7.0–9.9; Severa < 7). La regla se verifica contra el diagnóstico del CSV con 99.6 % de coincidencia (el resto son Leve de lactantes con Hb 9.5–9.9).
- El diagnóstico sigue la hemoglobina **corregida** (`Hbc`): a 604 y 659 msnm el dataset corrige +0.35 y +0.39 g/dL, es decir, **corrige por debajo de 1000 msnm**.

**Efecto medido:** aplicando `riesgo_referencia` a los 55,207 niños, solo coincide con la etiqueta del modelo en **90.2 %**.
Hay **5,102 lactantes (< 24 meses, Hb 10.5 a 10.96)** que el entrenamiento etiqueta "Bajo" y esta referencia llama "Medio"; además, 221 Medio y 4 Alto
de la etiqueta caen en otra clase. Mientras no se alinee, **el PC subestima los aciertos del modelo de forma sistemática** y no debe
interpretarse como medida de su desempeño en el grupo experimental.

**Qué falta para cerrarlo (decisión del asesor):**
1. Norma/versión vigente de los cortes de anemia por edad (6-23 y 24-59 meses).
2. Tabla de corrección por altitud (desde qué altitud y cuánto), para altitudes de Trujillo (≤ ~700 msnm).
3. Una vez confirmadas: hacer que `riesgo_referencia` reciba también `edad_meses` (el niño ya la tiene), actualizar `test_reporte.py` y `test_valoraciones.py::test_referencia_hb`, y documentar la nueva regla aquí y en `docs/API_CONTRATO.md`.

Ver también `docs/PENDIENTES.md`.

## Indicadores
- **PC** (% clasificaciones correctas): valoraciones cuyo riesgo coincide con el de referencia por Hb medida / valoraciones **con** Hb. Sin Hb se excluyen del denominador. *(Referencia pendiente: ver arriba.)*
- **TR** (tiempo de respuesta): promedio de `tiempo_ms` de las valoraciones, en segundos con 3 decimales (mide el cálculo en el servidor).
- **TT** (tasa de tamizaje, %): niños registrados en el grupo con alguna valoración en el periodo / niños registrados en el grupo. Máx. 100.
- Un grupo sin datos devuelve `0.0`; los campos `n_*` indican con cuántos datos se calculó.
