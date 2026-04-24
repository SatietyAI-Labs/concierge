"""add tool_usage_events table

Revision ID: 7d29e49d52c5
Revises: 2fe7a135d9dd
Create Date: 2026-04-24 01:53:24.316005

Lands the §D usage-log table so the per-tool telemetry the §C7
promotion/demotion scanner needs has a place to write. Emit hooks
(`concierge_recommend` → 'recommended', `install_by_method` →
'installed', Claude Code loader → 'loaded', etc.) wire in on Fix Day 3;
this revision only lands schema so the table is ready to accept writes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7d29e49d52c5'
down_revision: Union[str, Sequence[str], None] = '2fe7a135d9dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tool_usage_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tool_id', sa.Integer(), nullable=False),
        sa.Column(
            'event_type',
            sa.Enum(
                'recommended', 'installed', 'loaded', 'used', 'removed',
                name='usage_event_type',
            ),
            nullable=False,
        ),
        sa.Column(
            'timestamp',
            sa.DateTime(),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.Column('session_id', sa.String(length=128), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('tool_usage_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tool_usage_events_event_type'), ['event_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_tool_usage_events_session_id'), ['session_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tool_usage_events_timestamp'), ['timestamp'], unique=False)
        batch_op.create_index(batch_op.f('ix_tool_usage_events_tool_id'), ['tool_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('tool_usage_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tool_usage_events_tool_id'))
        batch_op.drop_index(batch_op.f('ix_tool_usage_events_timestamp'))
        batch_op.drop_index(batch_op.f('ix_tool_usage_events_session_id'))
        batch_op.drop_index(batch_op.f('ix_tool_usage_events_event_type'))

    op.drop_table('tool_usage_events')
