"""
API REST para la valoración del riesgo de anemia infantil (FastAPI).
Valoración de RIESGO (Bajo/Medio/Alto), no diagnóstico.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hashear
from app.db.database import Base, SessionLocal, engine
from app.models.entidades import Usuario
from app.db.migraciones import migrar
from app.routers import auth, ninos, prediccion, usuarios, valoraciones
from app.services import predictor

logging.basicConfig(level=logging.INFO)


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    s.validar_produccion()
    Base.metadata.create_all(engine)  # creación de tablas al inicio
    migrar(engine)  # columnas nuevas en BD existentes
    sembrar_demo()
    predictor.cargar_modelo(s.ruta_modelo)  # una sola vez
    yield


app = FastAPI(
    title="API Valoración de Riesgo de Anemia",
    description="Valoración de riesgo (no diagnóstico) de anemia infantil con Machine Learning.",
    version="2.0.0",
    lifespan=lifespan,
)
_cfg = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cfg.origenes_cors,  # producción: solo los de CORS_ORIGENES
    # Desarrollo: cualquier puerto de localhost/127.0.0.1 (Flutter web / Chrome usa puertos aleatorios).
    allow_origin_regex=None if _cfg.entorno == "production" else r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False, allow_methods=["*"], allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(prediccion.router)
app.include_router(valoraciones.router)
app.include_router(ninos.router)
app.include_router(usuarios.router)


@app.api_route("/health", methods=["GET", "HEAD"], tags=["Estado"])
def health():
    """Chequeo de salud (Render) - público y barato: no toca la base de datos."""
    return {"estado": "ok", "modelo_cargado": predictor.modelo_disponible()}


@app.get("/", tags=["Estado"])
def inicio():
    return {"mensaje": "API de valoración de riesgo de anemia activa"}
