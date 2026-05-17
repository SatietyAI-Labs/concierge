"""drop tools is_active column

Revision ID: 771ddc8fcccf
Revises: d8a3f0b62c14
Create Date: 2026-05-17 12:39:15.692710

Stage 1B `is_active`-retirement slice, Phase B — drops the legacy
`is_active` column (and its `ix_tools_is_active` index) from `tools`.

`is_active` was a half-retired legacy field (DECISIONS D112): set once
at ingest, never mutated at runtime, derived inconsistently across the
three ingest sources, and deliberately not maintained by
`transition_tool_lifecycle` (the Fix-Day-3 deprecation). Phase A of
this slice migrated its last consumers — `/health`'s catalog counts and
`/tools`'s `?active=` / `?dormant=` filters — onto `lifecycle_state`,
the canonical authority. This migration removes the now-unreferenced
column.

**Downgrade is intentionally lossy — documented.** `is_active` cannot
be perfectly reconstructed: its original values were minted by three
inconsistent rules (manifest.py: `lifecycle_state == 'loaded-on-boot'`;
catalog.py: a table Status word; skills.py: unconditional `True`). The
downgrade re-adds the column and backfills it with the *manifest.py*
rule — `is_active = (lifecycle_state == 'loaded-on-boot')` — the only
principled derivation. It restores a coherent value, NOT the original
per-row data. The downgrade exists for migration-history correctness
and the round-trip test; restoring production state from this migration
is done by file-restore from the pre-migration backup, never by
`alembic downgrade` (see the slice's Phase C procedure).

The downgrade re-adds `is_active` as `BOOLEAN NOT NULL` with no
server default — byte-identical to the baseline (`4ff5b5898f71`) column
DDL. Because re-adding a NOT-NULL column to a populated table needs the
rows backfilled first, the downgrade adds the column NULLABLE, backfills
every row, then flips it to NOT NULL.

**No CHECK constraint** is involved: `is_active` is a plain `Boolean`,
not an `Enum` — the D109 "no DB-level CHECK on the Enum columns"
standing fact does not bear on it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '771ddc8fcccf'
down_revision: Union[str, Sequence[str], None] = 'd8a3f0b62c14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the `ix_tools_is_active` index and the `is_active` column."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.drop_index('ix_tools_is_active')
        batch_op.drop_column('is_active')


def downgrade() -> None:
    """Re-add `is_active` (BOOLEAN NOT NULL, no server default) and its
    index. Lossy: `is_active` is backfilled as
    `lifecycle_state == 'loaded-on-boot'` — the manifest.py derivation —
    and does NOT recover the original inconsistently-minted values."""
    # Step 1 — add the column NULLABLE so the populated table accepts it
    # without a server default.
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=True))
    # Step 2 — backfill every row from `lifecycle_state` (manifest rule).
    op.execute(
        "UPDATE tools SET is_active = "
        "(CASE WHEN lifecycle_state = 'loaded-on-boot' THEN 1 ELSE 0 END)"
    )
    # Step 3 — every row now carries a value; flip to NOT NULL and
    # re-create the index. The column DDL now matches the baseline.
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.alter_column('is_active', nullable=False)
        batch_op.create_index('ix_tools_is_active', ['is_active'], unique=False)
