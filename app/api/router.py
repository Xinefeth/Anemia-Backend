"""Agrupa los routers de todos los módulos."""
from fastapi import APIRouter

from app.modules.auth.router import router as auth
from app.modules.ninos.router import router as ninos
from app.modules.prediccion.router import router as prediccion
from app.modules.reportes.router import router as reportes
from app.modules.usuarios.router import router as usuarios
from app.modules.valoraciones.router import router as valoraciones

api_router = APIRouter()
for r in (auth, prediccion, valoraciones, reportes, ninos, usuarios):
    api_router.include_router(r)
