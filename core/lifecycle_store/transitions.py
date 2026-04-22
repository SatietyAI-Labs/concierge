"""File-side status-transition validation for the lifecycle store.

Separate from `core.lifecycle_policy.TOOL_SELECTION_STATUS_TRANSITIONS`
(which is the **memory-side** vocabulary — per the skill's memory-
tagging convention). The two overlap but are not identical:

- **File-side** (X10 README): `pending`, `approved`, `denied`,
  `installed`, `failed`, `deferred`. `deferred` is a human "later"
  disposition; `removed` does not exist at this layer (there is no
  concept of "the file was removed" — archived is cron-managed).
- **Memory-side** (X7-B policy): `pending`, `approved`,
  `installed`, `denied`, `failed`, `removed`. `removed` exists
  because a memory entry persists post-install and can later be
  retired; `deferred` does not exist at the memory layer.

N7 operates on files. Transitions here are file-side only. Do NOT
import `TOOL_SELECTION_STATUS_TRANSITIONS` and use it as the
authority here — it has different terminal vocabulary and would
accept/reject transitions the cron can't handle.
"""
from __future__ import annotations


# Legal file-side transitions. `pending` is the entry state; the
# five resolved states are all reachable from `pending`. Post-
# resolution, `approved` → `installed` or `failed` is legitimate
# (the human approved, then the install happened or failed). The
# cron (X11) reads `status:` and moves files; it does not care about
# transition legality, so server-side validation is the only gate.
_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"approved", "denied", "deferred", "failed"}),
    "approved": frozenset({"installed", "failed"}),
    "deferred": frozenset({"pending", "approved", "denied"}),
    # Terminal file-side states:
    "denied": frozenset(),
    "installed": frozenset(),
    "failed": frozenset(),
}


VALID_FILE_STATUSES: frozenset[str] = frozenset(_TRANSITIONS.keys())


class InvalidTransitionError(ValueError):
    """Raised when a status transition is not in the legal table.

    Service layer catches this and re-raises as HTTP 409 so the
    endpoint's error body distinguishes "illegal transition" from
    "file not found" (404) and from "upstream broke" (500).
    """


def assert_valid_transition(*, current: str, target: str) -> None:
    """Raise `InvalidTransitionError` if `current -> target` is
    not in the legal transition table. Called from the service
    layer before writing the new status to file or DB.
    """
    if current not in _TRANSITIONS:
        raise InvalidTransitionError(
            f"current status {current!r} is not a recognized file-side status "
            f"(valid: {sorted(VALID_FILE_STATUSES)})"
        )
    if target not in VALID_FILE_STATUSES:
        raise InvalidTransitionError(
            f"target status {target!r} is not a recognized file-side status "
            f"(valid: {sorted(VALID_FILE_STATUSES)})"
        )
    allowed = _TRANSITIONS[current]
    if target not in allowed:
        if not allowed:
            raise InvalidTransitionError(
                f"status {current!r} is terminal; no transitions allowed"
            )
        raise InvalidTransitionError(
            f"illegal transition {current!r} -> {target!r} "
            f"(allowed from {current!r}: {sorted(allowed)})"
        )
