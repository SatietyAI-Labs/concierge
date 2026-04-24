"""Concierge database layer — SQLAlchemy 2.x declarative models + session factory."""

from core.db.base import Base
from core.db.session import get_db, get_engine, get_session_factory, init_db, make_engine

# Side-effect import: registers the SQLAlchemy event listener that
# validates Tool.lifecycle_state transitions. Importing core.db is
# enough for the listener to be attached; no explicit setup call
# required. See core/tool_transitions.py for the hybrid
# service-method + listener design.
from core import tool_transitions as _tool_transitions  # noqa: F401

__all__ = [
    "Base",
    "get_db",
    "get_engine",
    "get_session_factory",
    "init_db",
    "make_engine",
]
