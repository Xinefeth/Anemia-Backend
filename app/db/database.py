"""
Conexión a la base de datos (SQLAlchemy). PostgreSQL en producción, SQLite en dev/tests.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _crear_engine():
    url = get_settings().db_url
    if url.startswith("sqlite"):
        extra = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url in ("sqlite://", "sqlite:///"):
            extra["poolclass"] = StaticPool  # una sola conexión para BD en memoria
        return create_engine(url, **extra)
    return create_engine(url, pool_pre_ping=True)


engine = _crear_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """Dependencia FastAPI: una sesión por petición."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
