"""Logging configuration.

`configure_logging` owns the two Concierge logger families directly:

- ``concierge`` — the hand-named ``concierge.*`` loggers (``core/app.py``,
  ``core/events.py``, ``core/telemetry.py``, ``core/ingest/*``, ...).
- ``core`` — the ``getLogger(__name__)``-derived ``core.*`` loggers
  (``core/memory.py``, ``core/recommend/*``, ``core/api/*``,
  ``core/lifecycle_store/*``, ``core/install/*``, ...).

The two families share no common ancestor but the root logger. The
naming split is a pre-existing inconsistency; until the names are
unified, both family roots must be configured here.

Why both families are configured explicitly — and with
``propagate = False``:

``ensure_schema_current()`` runs Alembic at service startup. Alembic's
``env.py`` calls ``logging.config.fileConfig()``, which reconfigures the
*root* logger to ``WARNING`` per ``alembic.ini``. If the Concierge
loggers sat at ``NOTSET`` (the default) they would inherit that
``WARNING`` from root and silently drop every INFO log for the rest of
the process. Giving each family root an explicit level plus its own
handler, with ``propagate = False``, makes the families self-contained
— immune by construction to whatever ``fileConfig`` (or any other
library) does to the root logger afterward.
"""
import logging
import sys

# The two disjoint Concierge logger families — see module docstring.
_FAMILY_ROOTS = ("concierge", "core")

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _make_stdout_handler(numeric_level: int) -> logging.StreamHandler:
    """A fresh stdout StreamHandler with the Concierge timestamped format."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(
        logging.Formatter(fmt=_LOG_FORMAT, datefmt=_LOG_DATEFMT)
    )
    return handler


def configure_logging(level: str = "INFO") -> None:
    """Configure logging for the Concierge process.

    Idempotent — safe to call more than once: each call clears the
    handlers it manages before re-adding them, so handlers do not stack.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger — kept configured so third-party libraries (alembic,
    # sqlalchemy, huggingface_hub, chromadb) still emit. Alembic's
    # `fileConfig` reconfigures root again during the startup schema
    # check; that is accepted — the Concierge families below no longer
    # depend on root, so their visibility is unaffected.
    root = logging.getLogger()
    root.setLevel(numeric_level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    root.addHandler(_make_stdout_handler(numeric_level))

    # The two Concierge logger families — each given an explicit level,
    # its own handler, and `propagate = False`. Self-contained: a later
    # root reconfiguration cannot raise their effective level or change
    # their output stream/format.
    for name in _FAMILY_ROOTS:
        family = logging.getLogger(name)
        family.setLevel(numeric_level)
        for handler in list(family.handlers):
            family.removeHandler(handler)
        family.addHandler(_make_stdout_handler(numeric_level))
        family.propagate = False
