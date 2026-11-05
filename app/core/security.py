"""
Seguridad: hash de contraseñas (bcrypt) y tokens JWT.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models.entidades import Usuario

_bearer = HTTPBearer(auto_error=False)


def hashear(contrasena: str) -> str:
    return bcrypt.hashpw(contrasena.encode()[:72], bcrypt.gensalt()).decode()


def verificar(contrasena: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(contrasena.encode()[:72], hash_guardado.encode())
    except ValueError:
        return False


def crear_token(id_usuario: int) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.token_minutos)
    return jwt.encode({"sub": str(id_usuario), "exp": exp}, s.secret_key, algorithm=s.jwt_algoritmo)


def usuario_actual(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    """Dependencia que exige un JWT válido; responde 401 si falta o expiró."""
    s = get_settings()
    error = HTTPException(status_code=401, detail="No autenticado", headers={"WWW-Authenticate": "Bearer"})
    if cred is None:
        raise error
    try:
        datos = jwt.decode(cred.credentials, s.secret_key, algorithms=[s.jwt_algoritmo])
        usuario = db.get(Usuario, int(datos["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise error
    if usuario is None or not usuario.activo:  # inhabilitado: el token deja de servir
        raise error
    return usuario


# Roles que pueden gestionar usuarios (RF03-RF06). Los RF solo definen médico/enfermero; "administrador" es opcional.
ROLES_GESTION = {"administrador", "médico"}


def gestor_usuarios(user: Usuario = Depends(usuario_actual)) -> Usuario:
    if user.rol not in ROLES_GESTION:
        raise HTTPException(status_code=403, detail="No tiene permisos para gestionar usuarios")
    return user
