"""
SQLAlchemy declarative base for ORM models.

All database models inherit from `Base` to share the same metadata registry
and type configuration.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
