"""harden tools enum columns with check constraints

Revision ID: 103a85689166
Revises: 771ddc8fcccf
Create Date: 2026-05-17 15:44:36.437102

Stage 1B Enum CHECK-constraint hardening slice (DECISIONS D110) — adds
DB-level CHECK constraints to the three `Enum`-typed columns on `tools`:
`tool_type`, `lifecycle_state`, and `pin_status`.

**Background.** SQLAlchemy 2.x `Enum` defaults to `create_constraint=
False`, and Concierge had never overridden it (DECISIONS D109): the
three columns were plain `VARCHAR(N)` in SQLite with the value sets
enforced Python-side only (the model `Enum` type + `tool_transitions.py`).
This migration brings all three to `create_constraint=True` together —
consistency, not piecemeal — so the database rejects an off-list write
at the door instead of accepting garbage silently.

**This migration DOES change the SQLite schema** — unlike `c9d2f7a4e10b`
(the `on-demand` Enum-value add), whose `alter_column` was a no-op
precisely because both the old and new `Enum` carried `create_constraint
=False`. Here the new `Enum` carries `create_constraint=True`, so the
SQLite batch rebuild emits three `CONSTRAINT ... CHECK (col IN (...))`
clauses. The column *types* are unchanged — `pending-decision` (16),
`always-pinned` (13), `skill` (5) remain the longest values, so the
`VARCHAR(N)` widths do not move; only the CHECK clauses are added.

**Constraint naming.** `Base.metadata` carries no naming convention, so
SQLAlchemy names the auto-generated Enum CHECK after the `Enum`'s `name`
attribute — the constraints land as `CONSTRAINT tool_type CHECK (...)`,
`CONSTRAINT lifecycle_state CHECK (...)`, `CONSTRAINT pin_status CHECK
(...)`. The bare name matching the column name is legal in SQLite
(constraints and columns occupy distinct namespaces; the indexes are
`ix_tools_*`, no collision).

**Pre-flight.** A CHECK added over non-conforming data fails the batch
rebuild's copy step. Every live `tools` row was verified in-enum before
this migration was written (the slice's inspection §3) and is re-verified
live as Phase C step C1 immediately before `alembic upgrade head`.

**Downgrade** is the symmetric toggle-off: it rebuilds the three columns
with `create_constraint` unset, dropping the CHECK clauses. No data step
is needed — removing a constraint never rejects a row.

The migration value tuples below are **migration-local literals**, not
imports of the `core/db/models.py` constants: a migration pins the value
set as it was at the revision, so a later model edit cannot silently
rewrite migration history (the `c9d2f7a4e10b` / `d8a3f0b62c14`
convention).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '103a85689166'
down_revision: Union[str, Sequence[str], None] = '771ddc8fcccf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Migration-local value sets — pinned at this revision (see module
# docstring). Mirror core/db/models.py's TOOL_TYPE_VALUES /
# LIFECYCLE_STATE_VALUES / PIN_STATUS_VALUES as of 103a85689166.
_TOOL_TYPE_VALUES = ('mcp', 'cli', 'http', 'skill')
_LIFECYCLE_STATE_VALUES = (
    'discovered', 'pending', 'used', 'loaded-on-boot', 'retired',
    'pending-decision', 'on-demand',
)
_PIN_STATUS_VALUES = ('always-pinned', 'auto-managed')


def upgrade() -> None:
    """Add the three CHECK constraints by rebuilding `tools` once with
    each Enum column toggled to `create_constraint=True`."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.alter_column(
            'tool_type',
            existing_type=sa.Enum(*_TOOL_TYPE_VALUES, name='tool_type'),
            type_=sa.Enum(
                *_TOOL_TYPE_VALUES, name='tool_type', create_constraint=True
            ),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'lifecycle_state',
            existing_type=sa.Enum(
                *_LIFECYCLE_STATE_VALUES, name='lifecycle_state'
            ),
            type_=sa.Enum(
                *_LIFECYCLE_STATE_VALUES, name='lifecycle_state',
                create_constraint=True,
            ),
            existing_nullable=False,
            existing_server_default='discovered',
        )
        batch_op.alter_column(
            'pin_status',
            existing_type=sa.Enum(*_PIN_STATUS_VALUES, name='pin_status'),
            type_=sa.Enum(
                *_PIN_STATUS_VALUES, name='pin_status', create_constraint=True
            ),
            existing_nullable=False,
            existing_server_default='auto-managed',
        )


def downgrade() -> None:
    """Drop the three CHECK constraints by rebuilding `tools` once with
    each Enum column toggled back to `create_constraint` unset. No data
    step — removing a constraint rejects nothing."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.alter_column(
            'tool_type',
            existing_type=sa.Enum(
                *_TOOL_TYPE_VALUES, name='tool_type', create_constraint=True
            ),
            type_=sa.Enum(*_TOOL_TYPE_VALUES, name='tool_type'),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'lifecycle_state',
            existing_type=sa.Enum(
                *_LIFECYCLE_STATE_VALUES, name='lifecycle_state',
                create_constraint=True,
            ),
            type_=sa.Enum(
                *_LIFECYCLE_STATE_VALUES, name='lifecycle_state'
            ),
            existing_nullable=False,
            existing_server_default='discovered',
        )
        batch_op.alter_column(
            'pin_status',
            existing_type=sa.Enum(
                *_PIN_STATUS_VALUES, name='pin_status', create_constraint=True
            ),
            type_=sa.Enum(*_PIN_STATUS_VALUES, name='pin_status'),
            existing_nullable=False,
            existing_server_default='auto-managed',
        )
