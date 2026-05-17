"""add on-demand lifecycle state

Revision ID: c9d2f7a4e10b
Revises: e17b8137cade
Create Date: 2026-05-16 17:00:00.000000

Stage 1B reconciliation slice, Phase A0 — adds `on-demand` as the
seventh allowed value on the `tools.lifecycle_state` Enum.

`on-demand` is a *settled* state for a tool deliberately kept but not
boot-loaded: installed and usable, reachable on demand, deliberately
off the boot context budget (cf. master plan §IX context-weight
philosophy). Distinct from `pending-decision` ("fate undecided") —
`on-demand` says "we have decided to keep this, just not at boot."
The state is general; ElevenLabs is its first occupant (the Stage 1B
catalog reconciliation moves it `loaded-on-boot → on-demand`).

The vocabulary it was reaching for appeared in 2026-05-13 planning
notes as `available` (CLAUDE.md §2.5 / DECISIONS D-02), a name the
implemented `lifecycle_state` Enum never adopted; `on-demand` is the
properly-designed state that fills that gap.

Transition edges into / out of `on-demand` are defined in
`core/tool_transitions.py` (Phase A0, same slice); this migration
records the persisted-Enum value-set change.

**Schema-level mechanics — honest note.** SQLAlchemy 2.x `Enum`
defaults to `create_constraint=False`, and the Concierge model does
not override it: the `lifecycle_state` column is a plain
`VARCHAR(16)` in SQLite with **no CHECK constraint** (verified
2026-05-16 against the live `tools` DDL). The value set is enforced
Python-side (the model `Enum` type + `core/tool_transitions.py`),
not by the database. Consequently the `alter_column` below is a
schema-level **no-op on SQLite** — it rebuilds `lifecycle_state` as
the same `VARCHAR(16)` (`pending-decision`, 16 chars, stays the
longest value, so the width does not even change). The migration is
kept regardless: it records the value-set change in `alembic
history` for intent/portability (a Postgres backend, or a future
`create_constraint=True`, would make it load-bearing), and it
mirrors the precedent set by `fa46ebdf05b9` (which likewise framed
the `pending-decision` add as a CHECK change — the same inaccuracy;
not edited, append-only history).

`upgrade()` therefore changes nothing observable in the SQLite
schema. The one observable effect of this migration is in
`downgrade()`.

Reversibility: `downgrade()` demotes any rows currently at
`on-demand` to `discovered`, then issues the (no-op) Enum revert.
The demotion is defensive data-hygiene — without a CHECK it is not
strictly required (an `on-demand` row would survive the column
rebuild), but a row carrying a value the code-at-that-revision no
longer knows is a latent inconsistency, so the demotion cleans it
up. `discovered` is the safe target ("known but not in play", the
closest pre-extension state). Mirrors `fa46ebdf05b9`'s
`pending-decision → discovered` downgrade — the D44 guard pattern.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d2f7a4e10b'
down_revision: Union[str, Sequence[str], None] = 'e17b8137cade'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_LIFECYCLE_VALUES = (
    'discovered', 'pending', 'used', 'loaded-on-boot', 'retired',
    'pending-decision',
)
_NEW_LIFECYCLE_VALUES = _OLD_LIFECYCLE_VALUES + ('on-demand',)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.alter_column(
            'lifecycle_state',
            existing_type=sa.Enum(*_OLD_LIFECYCLE_VALUES, name='lifecycle_state'),
            type_=sa.Enum(*_NEW_LIFECYCLE_VALUES, name='lifecycle_state'),
            existing_nullable=False,
            existing_server_default='discovered',
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Defensive data-hygiene: demote any `on-demand` row to `discovered`
    # so no row carries a value the code-at-this-revision no longer
    # knows. There is no CHECK constraint to fail (see module docstring),
    # so this is not strictly load-bearing on SQLite — but it keeps the
    # data consistent with the reverted value set. `discovered` is the
    # safe target — "known but not in play", the closest pre-extension
    # state. Mirrors fa46ebdf05b9's `pending-decision → discovered`
    # downgrade; the D44 guard pattern.
    op.execute(
        "UPDATE tools SET lifecycle_state = 'discovered' "
        "WHERE lifecycle_state = 'on-demand'"
    )
    with op.batch_alter_table('tools', schema=None) as batch_op:
        batch_op.alter_column(
            'lifecycle_state',
            existing_type=sa.Enum(*_NEW_LIFECYCLE_VALUES, name='lifecycle_state'),
            type_=sa.Enum(*_OLD_LIFECYCLE_VALUES, name='lifecycle_state'),
            existing_nullable=False,
            existing_server_default='discovered',
        )
