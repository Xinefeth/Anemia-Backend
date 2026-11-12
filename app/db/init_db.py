"""Inicialización de la BD al arrancar: tablas, migración ligera y usuario demo."""
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hashear
from app.db.base import Base
from app.db.migraciones import migrar
from app.db.session import SessionLocal, engine
# Importar los modelos registra sus tablas en Base.metadata (necesario para create_all).
from app.modules.ninos.models import Nino  # noqa: F401
from app.modules.usuarios.models import Usuario
from app.modules.valoraciones.models import Valoracion  # noqa: F401


def sembrar_demo() -> None:
    """Crea el usuario demo (configurable por env) si no existe."""
    s = get_settings()
    if not s.seed_demo:
        return
    with SessionLocal() as db:
        if db.scalar(select(Usuario).where(Usuario.usuario == s.demo_usuario)) is None:
            db.add(Usuario(nombre=s.demo_nombre, usuario=s.demo_usuario,
                           contrasena=hashear(s.demo_contrasena), rol=s.demo_rol))
            db.commit()


def inicializar() -> None:
    Base.metadata.create_all(engine)  # creación de tablas al inicio
    migrar(engine)  # columnas nuevas en BD existentes
    sembrar_demo()
