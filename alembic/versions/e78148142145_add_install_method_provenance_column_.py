"""add install_method_provenance column with backfill

Revision ID: e78148142145
Revises: 50364025e26b
Create Date: 2026-04-25 08:11:48.509659

DECISIONS `[2026-04-27 Day 6]` Option 3 scope + migration:

  Option 3 (Concierge-managed venv at `~/.concierge/tools-venv/`)
  changes the canonical install path for pip-installed Python tools.
  This migration adds `install_method_provenance` to the tools table
  and one-shot tags every existing row whose `install_method`
  matches one of the four Option-3-relevant canonical methods.

Backfill mapping (see `core/install/provenance.py` for the
canonical statement and the runtime translation map):

  install_method='pip-user'    → 'pre-option-3-user-site'
  install_method='npm-global'  → 'npm-global'
  install_method='npx-mcp'     → 'npx-mcp'
  install_method='binary'      → 'single-binary'
  install_method=NULL or other → NULL

Idempotency: backfill UPDATEs guard on
`install_method_provenance IS NULL` — defense-in-depth so manual
re-execution doesn't clobber rows that have transitioned to a
post-Option-3 provenance value.

Hyphen/underscore mismatch (out of scope per Decision C+D):

  `Tool.install_method` (set during ingest) stores hyphenated values
  ('pip-user', 'npm-global', 'npx-mcp', 'binary'). `InstallResult.method`
  (returned by the install dispatcher) uses underscored canonical
  constants ('pip_user', 'npm_global', 'npx_mcp', 'single_binary').
  This pre-existing inconsistency is documented as out-of-scope for
  Option 3. The translation lives in
  `core/install/provenance.py::PROVENANCE_BY_RESULT_METHOD` (used by
  `core/lifecycle_store/service.py::_maybe_install_on_approve` to
  set provenance on new installs).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from core.install.provenance import apply_install_method_provenance_backfill


# revision identifiers, used by Alembic.
revision: str = 'e78148142145'
down_revision: Union[str, Sequence[str], None] = '50364025e26b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('install_method_provenance', sa.String(64), nullable=True)
        )
        batch_op.create_index(
            batch_op.f('ix_tools_install_method_provenance'),
            ['install_method_provenance'],
            unique=False,
        )

    # One-shot data migration. The backfill function is shared with
    # the wiring tests at tests/test_install_method_provenance.py;
    # both call the same code so verification matches production.
    apply_install_method_provenance_backfill(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tools_install_method_provenance'))
        batch_op.drop_column('install_method_provenance')
