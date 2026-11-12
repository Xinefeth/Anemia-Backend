"""Autenticación del personal de salud."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.modules.auth.schemas import LoginIn, LoginOut, UsuarioOut
from app.modules.usuarios.models import Usuario

router = APIRouter(prefix="/api", tags=["Autenticación"])

# Hash ficticio para igualar el tiempo de respuesta cuando el usuario no existe.
_HASH_FALSO = security.hashear("no-existe")


@router.post("/login", response_model=LoginOut)
def login(datos: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(Usuario).where(Usuario.usuario == datos.usuario))
    ok = security.verificar(datos.contrasena, u.contrasena if u else _HASH_FALSO)
    if not u or not ok:
        # 400 (no 401): la app trata 401 como "sesión expirada".
        raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos")
    if not u.activo:
        raise HTTPException(status_code=403, detail="Usuario inhabilitado")
    return LoginOut(token=security.crear_token(u.id), usuario=UsuarioOut(id=u.id, nombre=u.nombre, rol=u.rol))
