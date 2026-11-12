"""Dependencias transversales de la API: usuario autenticado y permisos por rol."""
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decodificar_token
from app.db.session import get_db
from app.modules.usuarios.models import Usuario

_bearer = HTTPBearer(auto_error=False)

# Roles que pueden gestionar usuarios (RF03-RF06). Los RF solo definen médico/enfermero; "administrador" es opcional.
ROLES_GESTION = {"administrador", "médico"}


def usuario_actual(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    """Exige un JWT válido; responde 401 si falta, expiró o el usuario está inhabilitado."""
    error = HTTPException(status_code=401, detail="No autenticado", headers={"WWW-Authenticate": "Bearer"})
    if cred is None:
        raise error
    try:
        usuario = db.get(Usuario, decodificar_token(cred.credentials))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise error
    if usuario is None or not usuario.activo:  # inhabilitado: el token deja de servir
        raise error
    return usuario


def gestor_usuarios(user: Usuario = Depends(usuario_actual)) -> Usuario:
    if user.rol not in ROLES_GESTION:
        raise HTTPException(status_code=403, detail="No tiene permisos para gestionar usuarios")
    return user
