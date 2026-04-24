"""add lifecycle_state column with backfill

Revision ID: 2fe7a135d9dd
Revises: 7bdb4433afa8
Create Date: 2026-04-24 01:50:52.600132

Adds the tool-level lifecycle state machine (the third state machine per
audit §D — distinct from Request folder state and Request status field).
Five peer values matching the blueprint:

  discovered / pending / used / loaded-on-boot / retired

Transition validation lands in Fix Day 3 (`core/tool_transitions.py`);
this revision only lands the column + backfill. The server_default of
`discovered` gives newly-inserted rows a safe floor.

Backfill mapping from the prior (`is_in_manifest`, `is_active`) pair:

  active=True,  in_manifest=True  → loaded-on-boot
  active=True,  in_manifest=False → used         (session-loaded but not permanent)
  active=False, *                 → discovered   (known-but-not-loaded; pre-Task-4
                                                   we have no usage history to
                                                   distinguish discovered vs retired,
                                                   and retired requires an explicit
                                                   operator decision — so dormant
                                                   rows go to the safe floor)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2fe7a135d9dd'
down_revision: Union[str, Sequence[str], None] = '7bdb4433afa8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lifecycle_state', sa.Enum('discovered', 'pending', 'used', 'loaded-on-boot', 'retired', name='lifecycle_state'), server_default='discovered', nullable=False))
        batch_op.create_index(batch_op.f('ix_tools_lifecycle_state'), ['lifecycle_state'], unique=False)

    # Backfill mapping (see module docstring for rationale).
    op.execute(
        "UPDATE tools SET lifecycle_state = 'loaded-on-boot' "
        "WHERE is_active = 1 AND is_in_manifest = 1"
    )
    op.execute(
        "UPDATE tools SET lifecycle_state = 'used' "
        "WHERE is_active = 1 AND is_in_manifest = 0"
    )
    # is_active=0 rows retain the server_default 'discovered' — no UPDATE needed.


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tools_lifecycle_state'))
        batch_op.drop_column('lifecycle_state')
