"""
Seguridad: hash de contraseñas (bcrypt) y tokens JWT. Sin dependencias de FastAPI ni de la BD.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

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


def decodificar_token(token: str) -> int:
    """Devuelve el id de usuario del JWT; lanza jwt.PyJWTError / ValueError / KeyError si no es válido."""
    s = get_settings()
    return int(jwt.decode(token, s.secret_key, algorithms=[s.jwt_algoritmo])["sub"])
