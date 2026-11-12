"""
API REST para la valoración del riesgo de anemia infantil (FastAPI).
Valoración de RIESGO (Bajo/Medio/Alto), no diagnóstico.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.init_db import inicializar
from app.modules.prediccion import service as predictor

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    s.validar_produccion()
    inicializar()  # tablas, migración ligera y usuario demo
    predictor.cargar_modelo(s.ruta_modelo)  # una sola vez
    yield


def crear_app() -> FastAPI:
    cfg = get_settings()
    app = FastAPI(
        title="API Valoración de Riesgo de Anemia",
        description="Valoración de riesgo (no diagnóstico) de anemia infantil con Machine Learning.",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.origenes_cors,  # producción: solo los de CORS_ORIGENES
        # Desarrollo: cualquier puerto de localhost/127.0.0.1 (Flutter web / Chrome usa puertos aleatorios).
        allow_origin_regex=None if cfg.entorno == "production" else r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=False, allow_methods=["*"], allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.api_route("/health", methods=["GET", "HEAD"], tags=["Estado"])
    def health():
        """Chequeo de salud (Render) - público y barato: no toca la base de datos."""
        return {"estado": "ok", "modelo_cargado": predictor.modelo_disponible()}

    @app.get("/", tags=["Estado"])
    def inicio():
        return {"mensaje": "API de valoración de riesgo de anemia activa"}

    return app


app = crear_app()
