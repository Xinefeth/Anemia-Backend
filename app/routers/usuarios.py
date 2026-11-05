"""Gestión de usuarios (RF03-RF06). Solo roles de gestión (administrador / médico). DELETE = inhabilitar."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import ROLES_GESTION, gestor_usuarios, hashear
from app.db.database import get_db
from app.models.entidades import Usuario
from app.schemas.esquemas import UsuarioGestionOut, UsuarioIn, UsuarioUpdate

router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])


def _obtener(db: Session, id: int) -> Usuario:
    u = db.get(Usuario, id)
    if u is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return u


def _nombre_libre(db: Session, nombre: str, excepto: int | None = None) -> None:
    otro = db.scalar(select(Usuario).where(Usuario.usuario == nombre))
    if otro is not None and otro.id != excepto:
        raise HTTPException(status_code=409, detail="Ya existe un usuario con ese nombre de usuario")


@router.get("", response_model=list[UsuarioGestionOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(gestor_usuarios)):
    return list(db.scalars(select(Usuario).order_by(Usuario.id)))


@router.post("", response_model=UsuarioGestionOut, status_code=201)
def crear(datos: UsuarioIn, db: Session = Depends(get_db), _: Usuario = Depends(gestor_usuarios)):
    _nombre_libre(db, datos.usuario)
    u = Usuario(nombre=datos.nombre, usuario=datos.usuario, contrasena=hashear(datos.contrasena),
                rol=datos.rol, activo=True)
    db.add(u)
    db.commit()
    return u


@router.put("/{id}", response_model=UsuarioGestionOut)
def modificar(id: int, datos: UsuarioUpdate, db: Session = Depends(get_db),
              yo: Usuario = Depends(gestor_usuarios)):
    u = _obtener(db, id)
    cambios = datos.model_dump(exclude_unset=True, exclude_none=True)
    if id == yo.id:  # no puede quitarse a sí mismo el acceso ni los permisos de gestión
        if cambios.get("activo") is False:
            raise HTTPException(status_code=400, detail="No puede inhabilitarse a sí mismo")
        if "rol" in cambios and cambios["rol"] not in ROLES_GESTION:
            raise HTTPException(status_code=400, detail="No puede quitarse a sí mismo el permiso de gestión")
    if "usuario" in cambios:
        _nombre_libre(db, cambios["usuario"], excepto=id)
    if "contrasena" in cambios:
        cambios["contrasena"] = hashear(cambios["contrasena"])
    for k, v in cambios.items():
        setattr(u, k, v)
    db.commit()
    return u


@router.delete("/{id}", status_code=204)
def inhabilitar(id: int, db: Session = Depends(get_db), yo: Usuario = Depends(gestor_usuarios)):
    """Inhabilita (no borra): el usuario ya no puede iniciar sesión ni usar su token."""
    if id == yo.id:
        raise HTTPException(status_code=400, detail="No puede inhabilitarse a sí mismo")
    _obtener(db, id).activo = False
    db.commit()
    return Response(status_code=204)
