"""add tool pin_status column

Revision ID: d8a3f0b62c14
Revises: c9d2f7a4e10b
Create Date: 2026-05-16 17:30:00.000000

Stage 1B reconciliation slice, Phase A — adds the `pin_status` column
to `tools`: the operator-pin authority class for a tool's residence
in `loaded-on-boot` (DECISIONS D77).

Two values, `always-pinned` / `auto-managed`:
  - `always-pinned` — Concierge's autonomous lifecycle logic may not
    demote / retirement-flag / transition the tool out of
    `loaded-on-boot`; only the operator removes the pin.
  - `auto-managed` — Concierge-managed; usage telemetry drives its
    fate. The default for every row.

The column is `NOT NULL` with `server_default='auto-managed'`, so the
add-column backfills every existing catalog row (the 11 Gate-2 rows)
to `auto-managed`. The Stage 1B catalog reconciliation (Phase B) later
sets the first non-default value — `always-pinned` on Alfred's
semantic-memory MCP.

**No CHECK constraint.** The model types `pin_status` as a SQLAlchemy
`Enum`, but SQLAlchemy 2.x `Enum` defaults to `create_constraint=False`
and Concierge does not override it — so in SQLite the column is a
plain `VARCHAR(13)` (`always-pinned`, 13 chars, is the longest value)
with no DB-level CHECK. The value set is enforced Python-side (the
model `Enum` type). This matches the existing posture of the sibling
Enum columns `lifecycle_state` and `tool_type`. A dedicated follow-on
slice ("Enum CHECK-constraint hardening", sequenced after this slice
closes and before Gate 4) brings all three columns to
`create_constraint=True` together; this migration deliberately does
not get ahead of that.

The column is indexed (`ix_tools_pin_status`) for consistency with the
other low-cardinality catalog status columns (`is_active`,
`is_in_manifest`, `lifecycle_state`) and the Phase B scanner
demotion-exemption filter.

Reversibility: `downgrade()` drops the index and the column. No
data-preservation step is needed — dropping a column is unconditional.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8a3f0b62c14'
down_revision: Union[str, Sequence[str], None] = 'c9d2f7a4e10b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PIN_STATUS_VALUES = ('always-pinned', 'auto-managed')


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'pin_status',
                sa.Enum(*_PIN_STATUS_VALUES, name='pin_status'),
                nullable=False,
                server_default='auto-managed',
            )
        )
        batch_op.create_index(
            'ix_tools_pin_status', ['pin_status'], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.drop_index('ix_tools_pin_status')
        batch_op.drop_column('pin_status')
