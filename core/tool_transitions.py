"""Tool-level lifecycle-state transition validation.

Mirrors `core/lifecycle_store/transitions.py` for the Request folder-
state machine. Per blueprint-v2 §D audit and DECISIONS
`[2026-04-25 Fix Day 2]`, the `Tool.lifecycle_state` column is the
**third** state machine in the Concierge data model (distinct from
Request folder state and Request status field). Its vocabulary
(`discovered` / `pending` / `used` / `loaded-on-boot` / `retired`)
captures how a catalog entry moves from candidacy through usage to
retirement; this module defines the legal transitions between those
states and enforces them on every ORM write.

**Enforcement strategy — hybrid (per Fix Day 3 Fork 1 ruling):**

1. Service method `transition_tool_lifecycle(session, tool, new_state)`
   is the canonical write path. Callers that go through the service
   get an explicit failure locus in tests and logs when a transition
   is illegal.

2. SQLAlchemy `before_update` event listener on `Tool` fires on every
   ORM write to `lifecycle_state`, raising the same exception if the
   transition is illegal. Belt-and-suspenders — callers that do bare
   `tool.lifecycle_state = X; session.flush()` still hit validation
   and can't silently bypass it.

**Intentional bypass — Alembic migrations + audited backfills.**
Validation fires on SQLAlchemy ORM writes. Intentional bypass via raw
SQL UPDATE is reserved for Alembic migrations and audited backfills
(precedent: Fix Day 2 migration `2fe7a135d9dd` backfilled
`lifecycle_state` across 48 rows using `op.execute(...UPDATE...)`
rather than ORM transitions). Future sessions needing to override
lifecycle state at scale should use the same raw-SQL-in-migration
pattern, log the mapping rationale in DECISIONS.md, and cite this
paragraph as the explicit-by-design precedent.

**Initial inserts** are not validated — a Tool can be created in any
lifecycle_state (skills ingest creates rows at `discovered`; catalog
ingest creates rows at `loaded-on-boot` or `discovered` based on the
source's active/in-manifest signal). Validation only gates *updates*.

---

## Skills-specific lifecycle semantics (Fix Day 3 Task 4)

Skills (`tool_type='skill'`) share the same five-state enum as MCP /
CLI / HTTP tools, but the state labels carry slightly different
semantics because skills are ambient-loaded (no per-session install,
no explicit load step):

- **`discovered`** — default state on first ingest. The SKILL.md
  exists under `<skills_root>/{public,user,examples}/<slug>/` and
  Concierge knows about it, but no session has demonstrably exercised
  it (no `UsageEvent(event_type='used')` row referencing the skill).
  A skill can also fall back to `discovered` if its loaded-on-boot /
  used status is later revoked (via a transition into `discovered`).
- **`pending`** — reserved for the request-pipeline lifecycle; does
  not apply to skills directly (skills don't go through
  `concierge_request_tool` — they're catalogued from disk). A skill
  should normally never hold `pending`; landing there is a bug.
- **`used`** — the skill has been exercised in at least one session.
  Defined operationally as: Claude referenced the skill's instructions
  in a response (observed via the skill's inclusion in Claude's
  active-tools list at recommendation time), OR the skill's
  `description` contributed to a tool-selection decision (observed via
  a memory hit on `tool-selection` tags that names the skill). The
  Fix Day 4 scanner + telemetry surfaces will instrument both signals;
  until then, skills transition to `used` only via explicit operator
  action or direct test fixtures.
- **`loaded-on-boot`** — skill is pinned for proactive surfacing. The
  `ambient_loading=True` flag set at ingest is NOT the same as
  `loaded-on-boot`: ambient_loading says "SKILL.md's trigger
  conditions load it into context when matched," whereas
  loaded-on-boot says "the operator has decided this skill is
  sufficiently load-bearing that its summary belongs in the identity
  note and weekly-review cadence." The default for newly-ingested
  skills is ambient_loading=True, lifecycle_state=discovered —
  trigger-loadable but not operator-pinned.
- **`retired`** — operator explicitly demoted the skill. The SKILL.md
  may still exist on disk; retired just means "don't surface this in
  recommendations." Reinstating requires the standard
  retired → discovered two-step (see `_TRANSITIONS` below).

**What "used" does NOT mean for skills:** merely reading the SKILL.md
frontmatter at ingest time is not "used." Ingest is a catalog-level
operation; "used" is a session-level operation. The distinction
matters for the §C7 promotion/demotion scanner's aggregation query —
if ingest counted as usage, every skill would be perpetually
"recently used" and the promotion signal would collapse.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.orm.base import NO_VALUE

from core.db.models import LIFECYCLE_STATE_VALUES, Tool


log = logging.getLogger("concierge.tool_transitions")


TransitionHook = Callable[[Tool, str, str], None]
"""Optional post-transition callback: `(tool, old_state, new_state)`.

Called after the state change is flushed to the DB. Use for
side-effects like identity-note refresh on loaded-on-boot crossings
(see `core.identity.refresh_identity_on_loaded_on_boot_change`).
Hook exceptions are logged WARN and swallowed so side-effect
failures don't roll back a validated transition.
"""


_TRANSITIONS: dict[str, frozenset[str]] = {
    # From discovered — known to the catalog, not yet in play. Any
    # downstream state is reachable as a first move.
    "discovered": frozenset(
        {"pending", "used", "loaded-on-boot", "retired"}
    ),
    # From pending — request is in-flight. Approval outcomes are
    # `used` or `loaded-on-boot`; denial sends the row back to
    # `discovered` (tool still known, just not installed) or to
    # `retired` if the denial is a considered demotion.
    "pending": frozenset(
        {"discovered", "used", "loaded-on-boot", "retired"}
    ),
    # From used — actively exercised. Promotion path is
    # `loaded-on-boot`; demotion paths are `discovered` (usage fell
    # off) or `retired` (explicit demotion).
    "used": frozenset({"discovered", "loaded-on-boot", "retired"}),
    # From loaded-on-boot — always-on. Can demote to `used` (no
    # longer auto-loaded but still exercised), fully unload to
    # `discovered`, or retire outright.
    "loaded-on-boot": frozenset({"used", "discovered", "retired"}),
    # From retired — operator-demoted. The ONLY legal exit is
    # `discovered`, forcing explicit reinstatement before any other
    # transition. This preserves the audit trail: a retired tool
    # cannot silently become loaded-on-boot without an intermediate
    # "I've decided to reconsider this" step.
    "retired": frozenset({"discovered"}),
}


VALID_LIFECYCLE_STATES: frozenset[str] = frozenset(LIFECYCLE_STATE_VALUES)


class IllegalLifecycleTransition(ValueError):
    """Raised when a `Tool.lifecycle_state` transition is not legal.

    Subclasses `ValueError` so existing `except ValueError` handlers
    (e.g. in the service layer) catch it, but tests can assert the
    exact class to distinguish from generic value errors.
    """


def is_legal_transition(current: str, target: str) -> bool:
    """Predicate form of the transition table.

    Self-transitions (`X → X`) are legal no-ops. Unknown states
    return False — validation catches them upstream with a clearer
    message via `assert_legal_transition`.
    """
    if current == target:
        return True
    allowed = _TRANSITIONS.get(current)
    if allowed is None:
        return False
    return target in allowed


def assert_legal_transition(*, current: str, target: str, slug: str) -> None:
    """Raise `IllegalLifecycleTransition` if `current → target` is illegal.

    `slug` is included in the error message so the failure locus is
    clear when the exception bubbles up through a bulk operation.
    """
    if current not in VALID_LIFECYCLE_STATES:
        raise IllegalLifecycleTransition(
            f"current lifecycle_state {current!r} is not a recognized "
            f"tool-level state "
            f"(valid: {sorted(VALID_LIFECYCLE_STATES)}) "
            f"[slug={slug!r}]"
        )
    if target not in VALID_LIFECYCLE_STATES:
        raise IllegalLifecycleTransition(
            f"target lifecycle_state {target!r} is not a recognized "
            f"tool-level state "
            f"(valid: {sorted(VALID_LIFECYCLE_STATES)}) "
            f"[slug={slug!r}]"
        )
    if current == target:
        return  # self-transition is a legal no-op
    allowed = _TRANSITIONS[current]
    if target not in allowed:
        raise IllegalLifecycleTransition(
            f"illegal lifecycle_state transition {current!r} → {target!r} "
            f"(allowed from {current!r}: {sorted(allowed)}) "
            f"[slug={slug!r}]"
        )


def transition_tool_lifecycle(
    session: Session,
    tool: Tool,
    new_state: str,
    *,
    on_transition: Optional[TransitionHook] = None,
) -> None:
    """Canonical write path for `Tool.lifecycle_state`.

    Validates the transition, logs it, applies it, and flushes. The
    SQLAlchemy event listener in this module also validates direct
    setattr writes (`tool.lifecycle_state = X; session.flush()`) as
    the belt-and-suspenders guard. Going through this service method
    is preferred because the failure locus is clearer for the caller
    and the log line includes intent-level context; direct setattr
    works but emits a slightly less informative listener-side log.

    `on_transition` (Fix Day 3 Task 7 — Fork 5 hook): optional
    callback invoked AFTER a non-noop state change is flushed. Fires
    with `(tool, old_state, new_state)`. Exceptions are logged WARN
    and swallowed — the DB is in the new state regardless of whether
    the side-effect succeeds. Skipped for self-transitions (no change
    → no hook).
    """
    old = tool.lifecycle_state
    assert_legal_transition(current=old, target=new_state, slug=tool.slug)
    if old == new_state:
        return
    log.info(
        "tool_transitions.apply slug=%s %s -> %s",
        tool.slug, old, new_state,
    )
    tool.lifecycle_state = new_state
    session.flush()
    if on_transition is not None:
        try:
            on_transition(tool, old, new_state)
        except Exception as exc:
            log.warning(
                "tool_transitions.hook_failed slug=%s %s -> %s "
                "error=%s: %s",
                tool.slug, old, new_state, type(exc).__name__, exc,
            )


# ---- SQLAlchemy event listener (belt-and-suspenders) -------------------


def _on_lifecycle_state_set(
    target: Tool, value: str, oldvalue, initiator
) -> None:
    """Reject illegal `lifecycle_state` changes at the ORM setattr boundary.

    Fires immediately on `tool.lifecycle_state = X`, BEFORE the flush.
    `active_history=True` (set on the listener registration below)
    forces SQLAlchemy to load the committed value from the DB even if
    the attribute is expired — so `oldvalue` is reliably populated for
    rows that exist. For fresh inserts where no committed value exists,
    `oldvalue` is `NO_VALUE` and we skip validation (initial inserts
    are not validated per module docstring).

    NOT fired for raw `connection.execute(UPDATE...)` statements —
    that's the intentional-bypass path for Alembic migrations + audited
    backfills documented in this module's top-of-file docstring.

    On validation failure this raises `IllegalLifecycleTransition`,
    which SQLAlchemy propagates out of the setattr call. The new value
    is NOT stored on the instance; the prior value remains intact.
    """
    if oldvalue is NO_VALUE or oldvalue is None:
        return  # fresh insert or newly-constructed instance
    if oldvalue == value:
        return  # self-transition is a legal no-op
    try:
        assert_legal_transition(
            current=oldvalue, target=value, slug=target.slug
        )
    except IllegalLifecycleTransition as exc:
        log.warning(
            "tool_transitions.rejected slug=%s %s -> %s reason=%s",
            target.slug, oldvalue, value, str(exc),
        )
        raise


event.listen(
    Tool.lifecycle_state,
    "set",
    _on_lifecycle_state_set,
    active_history=True,
    propagate=True,
)
