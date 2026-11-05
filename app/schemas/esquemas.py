"""
Esquemas Pydantic (entrada/salida de la API). Los nombres JSON siguen el contrato de la app Flutter.
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Sexo = Literal["M", "F"]
Grupo = Literal["control", "experimental"]


class DatosPrediccion(BaseModel):
    """Entrada de /api/predict. Los campos extra del cliente (codigo, hemoglobina...) se ignoran."""
    edad_meses: int = Field(..., ge=0, le=59, description="Edad en meses (0-59, RN01: menor de 5 años)")
    altitud: float = Field(0, ge=0, le=5500, description="Altitud en msnm")
    sexo: Sexo
    # Variables del Modelo B. Si el cliente aún no las envía se asume el caso conservador (0).
    cred: bool = Field(False, description="Asiste a control CRED")
    suplementacion: bool = Field(False, description="Recibe suplementación con hierro")

    @field_validator("sexo", mode="before")
    @classmethod
    def _sexo(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


class DatosValoracion(DatosPrediccion):
    """Entrada de POST /api/valoraciones."""
    codigo: str = Field(..., pattern=r"^[A-Za-z0-9_\-]{1,30}$", description="Código anónimo del niño")
    hemoglobina: float | None = Field(None, gt=0, le=25, description="Hb g/dL (solo referencia, no entra al modelo)")
    grupo: Grupo = "control"
    fecha: datetime | None = None


class Factor(BaseModel):
    factor: str
    peso: float


class ResultadoPrediccion(BaseModel):
    riesgo: Literal["Bajo", "Medio", "Alto"]
    probabilidad: float
    modelo: str
    tiempo_ms: int
    factores_influyentes: list[Factor]


class ValoracionOut(BaseModel):
    """Valoración aplanada (valoración + niño) como la espera el cliente."""
    id: int
    codigo: str
    edad_meses: int
    sexo: str
    hemoglobina: float | None
    altitud: float
    cred: bool
    suplementacion: bool
    grupo: str
    riesgo: str
    probabilidad: float
    fecha: datetime
    pendiente: bool = False


class LoginIn(BaseModel):
    usuario: str = Field(..., min_length=1, max_length=50)
    contrasena: str = Field(..., min_length=1, max_length=128)


class UsuarioOut(BaseModel):
    id: int
    nombre: str
    rol: str


class LoginOut(BaseModel):
    token: str
    usuario: UsuarioOut


class DashboardOut(BaseModel):
    total: int
    alto: int
    medio: int
    bajo: int
    hb_promedio: float
    ultimos_dias: list[int]
    recientes: list[ValoracionOut]


class Indicador(BaseModel):
    control: float
    experimental: float


class Conteo(BaseModel):
    control: int
    experimental: int


class ReporteOut(BaseModel):
    desde: date
    hasta: date
    total: int
    pc: Indicador  # % clasificaciones correctas
    tr: Indicador  # tiempo de respuesta (s)
    tt: Indicador  # tasa de tamizaje (%)
    # n usados en cada indicador, por grupo (n=0 => el indicador no es calculable y se muestra 0.0).
    n_valoraciones: Conteo  # valoraciones del grupo en el periodo (base de TR)
    n_pc: Conteo  # valoraciones con Hb medida (denominador de PC)
    n_tt_valorados: Conteo  # niños del grupo valorados en el periodo (numerador de TT)
    n_tt_registrados: Conteo  # niños registrados en el grupo (denominador de TT)


# ---------- Gestión de niños (RF08-RF11) ----------
class NinoIn(BaseModel):
    """Entrada de POST/PUT /api/ninos (mismos campos aplanados que ValoracionOut)."""
    codigo: str = Field(..., pattern=r"^[A-Za-z0-9_\-]{1,30}$", description="Código anónimo del niño")
    edad_meses: int = Field(..., ge=0, le=59, description="Edad en meses (0-59, RN01)")
    sexo: Sexo
    altitud: float = Field(0, ge=0, le=5500)
    cred: bool = False
    suplementacion: bool = False
    hemoglobina: float | None = Field(None, gt=0, le=25)
    grupo: Grupo = "control"

    @field_validator("sexo", mode="before")
    @classmethod
    def _sexo(cls, v):
        return v.strip().upper() if isinstance(v, str) else v


class NinoOut(NinoIn):
    model_config = {"from_attributes": True}
    id: int


# ---------- Gestión de usuarios (RF03-RF06) ----------
Rol = Literal["médico", "enfermero", "administrador"]


def _rol(v):
    if isinstance(v, str):
        v = v.strip().lower()
        return {"medico": "médico"}.get(v, v)
    return v


class UsuarioIn(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    usuario: str = Field(..., pattern=r"^[A-Za-z0-9_.\-]{3,50}$")
    contrasena: str = Field(..., min_length=4, max_length=128)
    rol: Rol

    _norm_rol = field_validator("rol", mode="before")(staticmethod(_rol))


class UsuarioUpdate(BaseModel):
    """PUT /api/usuarios/{id}: todos los campos son opcionales; contrasena solo si se quiere cambiar."""
    nombre: str | None = Field(None, min_length=1, max_length=100)
    usuario: str | None = Field(None, pattern=r"^[A-Za-z0-9_.\-]{3,50}$")
    contrasena: str | None = Field(None, min_length=4, max_length=128)
    rol: Rol | None = None
    activo: bool | None = None

    _norm_rol = field_validator("rol", mode="before")(staticmethod(_rol))


class UsuarioGestionOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    nombre: str
    usuario: str
    rol: str
    activo: bool
