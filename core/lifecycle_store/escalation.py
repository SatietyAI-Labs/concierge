"""Worker-to-Alfred escalation routing primitives — Stage 1A item 5.

Three sets + two predicates + one validator + one inferrer. All pure
functions / frozensets; no I/O, no DB, no FastAPI awareness. The
consumer surfaces are:

- `concierge_cli/commands/request_tool.py` — validates worker form
  client-side before POST; auto-infers escalation_target=alfred when
  --agent-id names a worker.
- `core/lifecycle_store/service.py::create_request` — propagates
  agent_id + escalation_target onto the Request row; uses the
  agent_prefix mapping for filename construction.
- `core/api/requests.py::list_pending` — accepts the
  escalation_target query parameter for Alfred's review queue.

Scope reframe per items-5+6 Finding C / operator confirmation:
Concierge does NOT send live notifications. The "real-time form"
in CLAUDE.md §6 is the worker's responsibility downstream, encoded
in worker SKILL.md and delivered via OpenClaw's `sessions_send` (or
whatever the host platform offers). This module handles ONLY the
durable record routing — what the lifecycle store persists and what
Alfred queries against.

Schema-fields-preserved-rendering-shape-unified per Finding F /
Decision N1: the worker form's five fields (Worker / Task / Gap /
Workaround used / Suggested tool) land in a unified `# Tool Request:`
file with an additional `## Escalation` section. The "Task" + "Tool
suggested" fields reuse the existing Request section's `task_context`
+ `tool_suggested` slots — no duplication. The Escalation section
carries Worker + Gap + Workaround used.
"""
from __future__ import annotations

from typing import Optional


# ---- Allowed values --------------------------------------------------------


ESCALATION_TARGET_VALUES: frozenset[str] = frozenset({"alfred", "operator"})
"""The two non-NULL routing values for `Request.escalation_target`.

- ``"alfred"`` — Alfred is the approver. Worker requests + any
  Alfred-routable escalation. Items-5+6 Phase B is the entry point.
- ``"operator"`` — the human operator is the approver. Used for
  Alfred's own onward escalations once Stage 1.5 wires the Discord
  notification adapter; included here from day one per items-5+6
  Decision 2 to avoid a follow-up migration.

NULL on the column means "no escalation routing" — the default for
Alfred-form filings and back-compat with pre-item-5 rows. Adding a
new value (e.g. ``"discord"``) lands here + in the API endpoint's
Literal alias + in the validation test that pins the set
exhaustively.
"""


WORKER_AGENT_IDS: frozenset[str] = frozenset(
    {"scout", "dispatch", "radar", "bridge"}
)
"""The four worker codenames per CLAUDE.md §2.

Used to:
1. Auto-infer ``escalation_target="alfred"`` when ``--agent-id`` names
   a worker.
2. Drive the `worker-<name>-<slug>` filename prefix.
3. Decide which client-side validation rules apply (worker form
   requires --gap and --workaround; Alfred form doesn't).

Alfred is NOT in this set — Alfred-as-filer doesn't escalate to
himself. Alfred-form filings either skip escalation (NULL) or
specify ``escalation_target="operator"`` explicitly (Stage 1.5
forward use).
"""


# ---- Predicates ------------------------------------------------------------


def is_worker_form(
    *,
    agent_id: Optional[str],
    escalation_target: Optional[str],
    gap: Optional[str],
    workaround_used: Optional[str],
) -> bool:
    """True iff the draft is a worker-form filing.

    A draft is worker-form when ANY of these is true:
    - `agent_id` names a worker (in WORKER_AGENT_IDS)
    - `escalation_target == "alfred"`
    - `gap` or `workaround_used` carries content

    The OR-shape catches incomplete worker forms (e.g. caller set
    --gap but forgot --agent-id) so `validate_worker_form` can fire
    on them rather than silently treating them as Alfred-form. The
    CLI uses this as the gate for "should I run worker validation."
    """
    return any([
        (agent_id or "").lower() in WORKER_AGENT_IDS,
        escalation_target == "alfred",
        bool(gap and gap.strip()),
        bool(workaround_used and workaround_used.strip()),
    ])


# ---- Validators ------------------------------------------------------------


class WorkerFormError(ValueError):
    """Raised when a worker-form draft is missing one of the required
    worker-specific fields (gap, workaround_used).

    Distinct from generic ValueError so callers can render a
    consistent CLI error message that names the missing fields by
    operator-facing flag name (`--gap`, `--workaround`) rather than
    Python attribute name.
    """

    def __init__(self, missing_fields: tuple[str, ...]) -> None:
        self.missing_fields = missing_fields
        super().__init__(
            f"worker-form filing is missing required field(s): "
            f"{', '.join(missing_fields)}"
        )


def validate_worker_form(
    *,
    agent_id: Optional[str],
    gap: Optional[str],
    workaround_used: Optional[str],
) -> None:
    """Raise `WorkerFormError` if a worker-form draft is missing
    `gap` or `workaround_used`.

    Called client-side from the CLI before POST per Decision N2a
    (master plan §III.2 item 5 explicitly names the CLI as the schema
    enforcement point). Server-side accepts the fields as plain
    Optional values — server validation would re-raise here, but the
    CLI is the primary gate.

    `agent_id` is informational — the worker form is identified by
    presence of gap/workaround, not by agent_id alone (see
    `is_worker_form`). Passed only so a future enhancement could
    surface the agent context in the error message.
    """
    missing: list[str] = []
    if not gap or not gap.strip():
        missing.append("--gap")
    if not workaround_used or not workaround_used.strip():
        missing.append("--workaround")
    if missing:
        raise WorkerFormError(tuple(missing))


# ---- Inferrer --------------------------------------------------------------


def infer_escalation_target(agent_id: Optional[str]) -> Optional[str]:
    """Worker agent_id → ``"alfred"``; anything else → ``None``.

    The CLI uses this to auto-populate `--escalation-target` when the
    operator passes `--agent-id <worker>` without specifying a target
    explicitly. Alfred-as-filer (`agent_id="alfred"`) and unknown
    agent_ids both produce `None` — there's no fleet-side automatic
    routing target for those cases, and the CLI defers to whatever
    the operator passes via explicit `--escalation-target`.

    Case-insensitive on the agent_id lookup so a worker passing
    `--agent-id Scout` (capital S) still routes correctly. The stored
    value lowercases per the WORKER_AGENT_IDS canonical form.
    """
    if agent_id is None:
        return None
    if agent_id.lower() in WORKER_AGENT_IDS:
        return "alfred"
    return None


# ---- Filename prefix -------------------------------------------------------


def worker_filename_prefix(agent_id: Optional[str]) -> Optional[str]:
    """Return ``"worker-<agent>"`` when agent_id names a worker, else
    None.

    Used by `generate_filename` to produce the
    ``YYYY-MM-DD-HHMM-worker-<name>-<slug>.md`` convention per
    CLAUDE.md §6 — operators grep `pending/worker-*` to find
    worker-escalated requests at a glance.

    Alfred-as-filer produces None (no prefix); Alfred's own filings
    keep the bare `YYYY-MM-DD-HHMM-<slug>.md` shape.
    """
    if agent_id is None:
        return None
    lowered = agent_id.lower()
    if lowered in WORKER_AGENT_IDS:
        return f"worker-{lowered}"
    return None
