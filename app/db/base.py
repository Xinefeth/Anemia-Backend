"""Base declarativa de SQLAlchemy (los modelos de cada módulo heredan de aquí)."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
