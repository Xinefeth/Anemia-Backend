"""
Migración ligera al iniciar: create_all no agrega columnas a tablas existentes (p. ej. la BD de Render),
así que se añaden aquí las columnas nuevas si faltan. Idempotente.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# (tabla, columna, definición SQL)
_COLUMNAS = [
    ("usuario", "activo", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ("nino", "grupo", "VARCHAR(15) NOT NULL DEFAULT 'control'"),
]


def migrar(engine: Engine) -> None:
    insp = inspect(engine)
    for tabla, columna, definicion in _COLUMNAS:
        if tabla in insp.get_table_names() and columna not in {c["name"] for c in insp.get_columns(tabla)}:
            with engine.begin() as con:
                con.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}"))
                if (tabla, columna) == ("nino", "grupo") and "valoracion" in insp.get_table_names():
                    # Niños ya existentes: toman el grupo de su última valoración (no el 'control' por defecto).
                    con.execute(text(
                        'UPDATE nino SET grupo = (SELECT v.grupo FROM valoracion v WHERE v."idNino" = nino."idNino" '
                        'ORDER BY v.fecha DESC, v."idValoracion" DESC LIMIT 1) '
                        'WHERE EXISTS (SELECT 1 FROM valoracion v WHERE v."idNino" = nino."idNino")'))
