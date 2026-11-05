"""
Configuración central de la aplicación, leída desde variables de entorno (o .env).
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ_BACKEND = Path(__file__).resolve().parents[2]
_CLAVE_DEV = "clave-solo-para-desarrollo-cambiar"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    entorno: str = "development"  # development | production
    # PostgreSQL en producción; SQLite solo para desarrollo local y tests.
    database_url: str = "sqlite:///./anemia_dev.db"
    secret_key: str = _CLAVE_DEV
    jwt_algoritmo: str = "HS256"
    token_minutos: int = 480
    # Orígenes CORS separados por coma ("*" = todos; útil para app móvil/dev).
    cors_origenes: str = "*"
    ruta_modelo: str = str(RAIZ_BACKEND / "modelos" / "modelo_anemia_rf.pkl")
    # Usuario demo (seed). Desactivar con SEED_DEMO=false.
    seed_demo: bool = True
    demo_usuario: str = "demo"
    demo_contrasena: str = "demo"
    demo_nombre: str = "Dra. Demo"
    demo_rol: str = "médico"

    @property
    def db_url(self) -> str:
        """Normaliza la URL: Render entrega postgres://, SQLAlchemy+psycopg necesita postgresql+psycopg://."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    @property
    def origenes_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origenes.split(",") if o.strip()]

    def validar_produccion(self) -> None:
        """En producción exige SECRET_KEY propia y PostgreSQL."""
        if self.entorno == "production":
            if self.secret_key == _CLAVE_DEV or len(self.secret_key) < 32:
                raise RuntimeError("SECRET_KEY insegura: defina una clave de >= 32 caracteres")
            if self.db_url.startswith("sqlite"):
                raise RuntimeError("En producción se requiere PostgreSQL (DATABASE_URL)")
            if self.seed_demo and self.demo_contrasena == "demo":
                raise RuntimeError("Defina DEMO_CONTRASENA (o SEED_DEMO=false) en producción")


@lru_cache
def get_settings() -> Settings:
    return Settings()
