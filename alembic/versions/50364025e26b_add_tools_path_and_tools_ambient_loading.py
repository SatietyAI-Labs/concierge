"""add tools.path and tools.ambient_loading

Revision ID: 50364025e26b
Revises: 7d29e49d52c5
Create Date: 2026-04-24 02:03:05.010700

Skills-specific fields on the shared Tool table. Both columns stay NULL
for non-skill rows (MCP / CLI / HTTP) — `path` has no analogue outside
skills, and `ambient_loading` is a skills-only concept (SKILL.md gets
loaded into context when its trigger conditions match, vs. MCP which
requires explicit session-level load). The skills ingest path at
`core/ingest/skills.py` populates both for `tool_type='skill'` rows.

No backfill needed: existing rows are all non-skill categories, and
NULL is the correct value for them.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '50364025e26b'
down_revision: Union[str, Sequence[str], None] = '7d29e49d52c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.add_column(sa.Column('path', sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column('ambient_loading', sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.drop_column('ambient_loading')
        batch_op.drop_column('path')
