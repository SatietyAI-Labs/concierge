"""add request escalation target

Revision ID: e17b8137cade
Revises: fa46ebdf05b9
Create Date: 2026-05-14 21:15:00.000000

Stage 1A item 5 — adds the `escalation_target` column to `requests`,
backing the worker-to-Alfred routing surface.

Allowed non-NULL values are `"alfred"` or `"operator"`; NULL means
"no escalation routing" (default for Alfred-form filings and back-
compat with all pre-item-5 rows). Validation lives at the Pydantic
Literal on the API query parameter and on `NewRequestDraft`, not at
the DB level — producer and consumer both enforce the enum, and the
column stays plain VARCHAR(16) so a future addition (e.g. a
`"discord"` routing target) doesn't require a separate migration to
widen a CHECK constraint.

Indexed because the `GET /requests/pending?escalation_target=alfred`
filter is the Alfred-facing review-queue lookup — exactly the case
where a sparse-index pays.

Reversibility: `downgrade()` drops the index and the column.
Existing rows lose their `escalation_target` value (NULL or one of
the two enum values); since `escalation_target` is a routing hint
not a state machine input, the loss is informational and the
downgrade does NOT need a data-preserving demotion step (contrast
the `pending-decision` demotion in fa46ebdf05b9's downgrade).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e17b8137cade'
down_revision: Union[str, Sequence[str], None] = 'fa46ebdf05b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('requests', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('escalation_target', sa.String(length=16), nullable=True)
        )
        batch_op.create_index(
            'ix_requests_escalation_target', ['escalation_target'], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('requests', schema=None) as batch_op:
        batch_op.drop_index('ix_requests_escalation_target')
        batch_op.drop_column('escalation_target')
