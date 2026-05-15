"""add tool catalog metadata columns and pending-decision state

Revision ID: fa46ebdf05b9
Revises: e78148142145
Create Date: 2026-05-14 18:33:53.131388

Stage 1A item 4 — extends the `tools` table with seven nullable
catalog-metadata columns and adds `pending-decision` as a sixth
allowed value on the `lifecycle_state` Enum.

Seven new columns map to TOOL-MANIFEST.md fields the prototype
catalog tracked but the v0.1.0 Tool model didn't carry. All nullable
so existing rows backfill to NULL (the catalog ingest script in item
7 populates them from the live manifest):

  agent_owner   VARCHAR(64)  — "Only available to:" lines; NULL = fleet-wide
  best_for      TEXT         — use-case prose
  limitation    TEXT         — anti-pattern prose
  prefix        VARCHAR(32)  — tool naming pattern (e.g., firefox_*)
  transport     VARCHAR(32)  — per-tool transport (separate from Pack.transport)
  auth          VARCHAR(32)  — auth mechanism (api_key, oauth, jwt, ...)
  succeeded_by  VARCHAR(64)  — retirement lineage; plain slug reference

`succeeded_by` is intentionally NOT a foreign key — retirement lineage
is informational for the recommendation engine, not a structural
constraint.

The `lifecycle_state` Enum gains `pending-decision` for tools under
active operator evaluation (distinct from `discovered`, which means
known-but-not-loaded with no active evaluation). Existing rows retain
their prior state values; the new value is reachable only via
explicit transitions per core/tool_transitions.py.

SQLite Enum extension uses `batch_alter_table`'s `alter_column` to
recreate the column with the wider CHECK constraint; existing values
survive the rebuild byte-for-byte. No backfill needed.

Reversibility: `downgrade()` first demotes any rows currently at
`pending-decision` to `discovered` (data preservation under the
narrowed enum), then reverts the Enum to its prior five values and
drops the seven new columns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa46ebdf05b9'
down_revision: Union[str, Sequence[str], None] = 'e78148142145'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_LIFECYCLE_VALUES = (
    'discovered', 'pending', 'used', 'loaded-on-boot', 'retired',
)
_NEW_LIFECYCLE_VALUES = _OLD_LIFECYCLE_VALUES + ('pending-decision',)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.add_column(sa.Column('agent_owner', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('best_for', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('limitation', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('prefix', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('transport', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('auth', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('succeeded_by', sa.String(length=64), nullable=True))
        batch_op.alter_column(
            'lifecycle_state',
            existing_type=sa.Enum(*_OLD_LIFECYCLE_VALUES, name='lifecycle_state'),
            type_=sa.Enum(*_NEW_LIFECYCLE_VALUES, name='lifecycle_state'),
            existing_nullable=False,
            existing_server_default='discovered',
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Preserve data: any row currently at `pending-decision` must move
    # off the value before the Enum narrows, otherwise the table-rebuild
    # would fail the CHECK constraint on the surviving rows. `discovered`
    # is the safe demotion target — it makes the row look "known but not
    # under active evaluation", which is the closest pre-extension state.
    op.execute(
        "UPDATE tools SET lifecycle_state = 'discovered' "
        "WHERE lifecycle_state = 'pending-decision'"
    )
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.alter_column(
            'lifecycle_state',
            existing_type=sa.Enum(*_NEW_LIFECYCLE_VALUES, name='lifecycle_state'),
            type_=sa.Enum(*_OLD_LIFECYCLE_VALUES, name='lifecycle_state'),
            existing_nullable=False,
            existing_server_default='discovered',
        )
        batch_op.drop_column('succeeded_by')
        batch_op.drop_column('auth')
        batch_op.drop_column('transport')
        batch_op.drop_column('prefix')
        batch_op.drop_column('limitation')
        batch_op.drop_column('best_for')
        batch_op.drop_column('agent_owner')
