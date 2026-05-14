"""Decision C+D one-shot install_method_provenance backfill logic.

Extracted from the Alembic migration into its own module so wiring
tests can verify the backfill against a real DB without reaching into
the migration file's namespace. The migration's `upgrade()` calls
`apply_install_method_provenance_backfill`; tests at
`tests/test_install_method_provenance.py` call the same function.

The backfill maps `Tool.install_method` (ingest-form, hyphenated) to
`Tool.install_method_provenance` (a generically-named field whose
values explicitly distinguish pre- vs post-Option-3 for `pip-user`
rows and method-name-equivalent for the other three Option-3-relevant
methods):

    install_method='pip-user'    → 'pre-option-3-user-site'
    install_method='npm-global'  → 'npm-global'
    install_method='npx-mcp'     → 'npx-mcp'
    install_method='binary'      → 'single-binary'
    install_method=NULL or other → NULL (legitimately outside Option 3)

Idempotency: every UPDATE guards on `install_method_provenance IS
NULL`. Re-running the backfill (manually, via tests, or via a
re-applied migration) is a strict no-op — already-tagged rows are
skipped, and rows that have transitioned to a post-Option-3
provenance value (e.g. `option-3-venv` written by
`_maybe_install_on_approve` on successful pip-user install) are
preserved.

`PROVENANCE_BY_RESULT_METHOD` is the runtime translation map between
`InstallResult.method` (underscore-form canonical constants from
`core.install.methods`) and `install_method_provenance` values
(hyphen-form). The hyphen/underscore mismatch with the ingest-form
values stored in `Tool.install_method` is a pre-existing
inconsistency documented as out-of-scope for Option 3 per
DECISIONS `[2026-04-27 Day 6]` Option 3 scope decision. This map
serves as the documented translation boundary; any future
contributor untangling the underlying inconsistency should start
here.
"""
from __future__ import annotations

import sqlalchemy as sa

from core.install.methods import (
    METHOD_NPM_GLOBAL,
    METHOD_NPX_MCP,
    METHOD_PIP_USER,
    METHOD_PIPX,
    METHOD_SINGLE_BINARY,
)


# (Tool.install_method ingest-form value, install_method_provenance value).
# Order is documentary, not load-bearing — the WHERE clauses are
# disjoint by `install_method` so applying them in any order produces
# the same final state.
_BACKFILL_MAPPINGS: list[tuple[str, str]] = [
    ("pip-user", "pre-option-3-user-site"),
    ("npm-global", "npm-global"),
    ("npx-mcp", "npx-mcp"),
    ("binary", "single-binary"),
]


PROVENANCE_BY_RESULT_METHOD: dict[str, str] = {
    METHOD_PIP_USER: "option-3-venv",
    METHOD_NPM_GLOBAL: "npm-global",
    METHOD_NPX_MCP: "npx-mcp",
    METHOD_SINGLE_BINARY: "single-binary",
    METHOD_PIPX: "pipx",
}


def apply_install_method_provenance_backfill(connection) -> None:
    """One-shot data migration: tag every Tool row whose
    `install_method` matches one of the four Option-3-relevant
    canonical methods with its explicit provenance value.

    Rows whose `install_method` is NULL or non-canonical (e.g.
    `mcp-server`, `apt`) keep NULL provenance — these are
    legitimately outside Option 3's scope.

    Idempotent: every UPDATE guards on
    `install_method_provenance IS NULL` so re-running is a no-op.
    """
    for install_method, provenance in _BACKFILL_MAPPINGS:
        connection.execute(
            sa.text(
                "UPDATE tools SET install_method_provenance = :provenance "
                "WHERE install_method = :install_method "
                "AND install_method_provenance IS NULL"
            ),
            {"install_method": install_method, "provenance": provenance},
        )
