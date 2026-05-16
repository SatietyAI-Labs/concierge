"""Tests for `core.logging.configure_logging`.

The defect these tests pin: `ensure_schema_current()` runs Alembic at
startup, whose `env.py` calls `logging.config.fileConfig()` and
reconfigures the *root* logger to WARNING. If the Concierge loggers sit
at NOTSET they inherit that WARNING and silently drop all INFO output.
`configure_logging` defends against this by owning both Concierge
logger families (`concierge` and `core`) directly — explicit level,
own handler, `propagate = False`.

The two-family coverage is the point: a test that checked only the
`concierge` family would pass against an incomplete fix that left the
`core.*` loggers — including `core.memory`, whose `ChromaDB client
initialized` / `Embedding model loaded` lines the D88 pre-warm
verification depends on — still suppressed.

The `_restore_concierge_logger_families` autouse fixture (conftest.py)
restores the global `concierge` / `core` logger state after each test
here, so `configure_logging`'s `propagate = False` does not leak.
"""
from __future__ import annotations

import logging
import sys

from core.db.session import ensure_schema_current
from core.logging import configure_logging

# One representative child logger per family — `concierge.events` is a
# hand-named `concierge.*` logger; `core.memory` is a
# `getLogger(__name__)`-derived `core.*` logger.
_CONCIERGE_CHILD = "concierge.events"
_CORE_CHILD = "core.memory"


class _ListHandler(logging.Handler):
    """A handler that just collects the records it receives."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class TestConfigureLoggingLevels:
    """`configure_logging` sets an explicit level on both family roots."""

    def test_sets_concierge_family_level(self):
        configure_logging("INFO")
        assert logging.getLogger("concierge").level == logging.INFO

    def test_sets_core_family_level(self):
        configure_logging("INFO")
        assert logging.getLogger("core").level == logging.INFO

    def test_level_argument_is_honored(self):
        configure_logging("WARNING")
        assert logging.getLogger("concierge").level == logging.WARNING
        assert logging.getLogger("core").level == logging.WARNING


class TestFamiliesImmuneToRootReconfiguration:
    """An explicit family-root level means a later root reconfiguration
    to WARNING cannot raise the families' effective level — the core of
    the fix."""

    def test_both_families_immune_to_root_set_to_warning(self):
        configure_logging("INFO")
        # Simulate what Alembic's fileConfig does to the root logger.
        logging.getLogger().setLevel(logging.WARNING)
        assert logging.getLogger(_CONCIERGE_CHILD).isEnabledFor(logging.INFO)
        assert logging.getLogger(_CORE_CHILD).isEnabledFor(logging.INFO)

    def test_family_roots_do_not_propagate(self):
        configure_logging("INFO")
        assert logging.getLogger("concierge").propagate is False
        assert logging.getLogger("core").propagate is False

    def test_family_handlers_use_concierge_stdout_format(self):
        """The handler stays on stdout with the timestamped Concierge
        format, so output is consistent before and after the schema
        check rather than flipping to Alembic's stderr generic format."""
        configure_logging("INFO")
        for name in ("concierge", "core"):
            handlers = logging.getLogger(name).handlers
            assert len(handlers) == 1
            handler = handlers[0]
            assert isinstance(handler, logging.StreamHandler)
            assert handler.stream is sys.stdout
            assert (
                handler.formatter._fmt
                == "%(asctime)s %(levelname)s %(name)s: %(message)s"
            )


class TestRealSchemaCheckReproduction:
    """End-to-end reproduction of the defect: `configure_logging` then a
    real `ensure_schema_current()` — which runs Alembic and its
    `fileConfig` — after which INFO must still emit on *both* families.
    """

    def test_concierge_and_core_info_survive_ensure_schema_current(self):
        configure_logging("INFO")
        # Real Alembic run — env.py's fileConfig resets the root logger
        # to WARNING. Idempotent (no-op upgrade when the DB is at head).
        ensure_schema_current()

        # The families have propagate=False, so a root-attached handler
        # would not see them — attach a collector to each family root.
        collector = _ListHandler()
        for name in ("concierge", "core"):
            logging.getLogger(name).addHandler(collector)

        logging.getLogger(_CONCIERGE_CHILD).info("probe-concierge-family")
        logging.getLogger(_CORE_CHILD).info("probe-core-family")

        messages = [r.getMessage() for r in collector.records]
        # Both must be present — checking only the concierge family
        # would pass against a fix that left the core.* family suppressed.
        assert "probe-concierge-family" in messages
        assert "probe-core-family" in messages


class TestConfigureLoggingIdempotent:
    """Repeated calls must not stack handlers."""

    def test_repeated_calls_do_not_stack_handlers(self):
        configure_logging("INFO")
        after_first = {
            n: len(logging.getLogger(n).handlers) for n in ("concierge", "core")
        }
        configure_logging("INFO")
        after_second = {
            n: len(logging.getLogger(n).handlers) for n in ("concierge", "core")
        }
        assert after_first == after_second
        assert all(count == 1 for count in after_second.values())
