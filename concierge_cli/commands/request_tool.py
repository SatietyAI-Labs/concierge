"""`concierge request-tool` subcommand — Stage 1A item 5.

Files a tool / skill / capability request via POST /requests. Surface
is category-agnostic per items-5+6 scope clarification — works for
all four catalog categories (MCP / CLI / HTTP / skill) and any
operator-defined future categories.

Two filing forms:

1. **Alfred form** — pre-item-5 shape. All existing
   `NewRequestDraft` fields available as flags. No worker context.
   Example::

       concierge request-tool \\
           --tool-name csvkit \\
           --category cli \\
           --task-context "profiling a subscriber CSV" \\
           --confidence high

2. **Worker form** — Stage 1A item 5. Triggered by passing
   ``--agent-id <worker>`` (scout / dispatch / radar / bridge). Two
   additional flags become required: ``--gap`` and ``--workaround``.
   The CLI auto-infers ``--escalation-target alfred`` unless
   explicitly overridden. Example::

       concierge request-tool \\
           --tool-name claude-code-review-skill \\
           --category skill \\
           --agent-id scout \\
           --task-context "reviewing a PR" \\
           --gap "no installed skill captures our brand-voice patterns" \\
           --workaround "did the review manually from memory"

Schema validation:

- Worker-form requires ``--gap`` and ``--workaround``: enforced
  client-side per master plan §III.2 item 5 ("schema enforced by
  ``concierge request-tool`` CLI") + items-5+6 Decision N2a.
- ``--agent-id`` must name a worker or alfred (or be omitted); any
  other value exits 2 with a clear error.
- ``--escalation-target`` must be ``"alfred"`` or ``"operator"`` (or
  be omitted); validated client-side before POST.

Help-text and error-message framing is category-neutral. Words like
"tool, skill, package, endpoint, or capability" appear instead of
"MCP server" anywhere the operator-facing surface might imply
category assumption.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Optional

from concierge_cli.client import HttpClient
from concierge_cli.errors import UsageError
from concierge_cli.output import render_request_tool
from core.lifecycle_store.escalation import (
    ESCALATION_TARGET_VALUES,
    WORKER_AGENT_IDS,
    WorkerFormError,
    infer_escalation_target,
    is_worker_form,
    validate_worker_form,
)
from core.lifecycle_store.schema import RequestDetail


# Agent IDs accepted by --agent-id: workers + alfred. Alfred-as-filer
# is permitted (covers Alfred's own onward escalations to operator)
# but doesn't auto-infer escalation_target — operators pass it
# explicitly if they want it.
_ACCEPTED_AGENT_IDS: frozenset[str] = WORKER_AGENT_IDS | {"alfred"}


# Client-side validation failures surface as `UsageError` (exit 2).
# Promoted to `concierge_cli.errors` at Stage 1A item 1b — `concierge
# enable/disable` need the same class, so the formerly-private
# `_UsageError` is now the shared `UsageError` per the D51 forward-carry.


def register(subparsers: argparse._SubParsersAction) -> None:
    sub = subparsers.add_parser(
        "request-tool",
        help=(
            "File a Concierge tool / skill / capability request. "
            "Worker agents (scout, dispatch, radar, bridge) use the "
            "worker form (--agent-id + --gap + --workaround) for "
            "escalation to Alfred."
        ),
    )

    # Common fields (Alfred form + worker form share these).
    sub.add_argument(
        "--tool-name",
        required=True,
        help=(
            "Name of the tool, skill, package, endpoint, or "
            "capability you'd like Concierge to consider. Required."
        ),
    )
    sub.add_argument(
        "--category",
        default=None,
        help=(
            "Catalog category: mcp / cli / http / skill, or any "
            "operator-defined category. Free-form text."
        ),
    )
    sub.add_argument(
        "--install-method",
        dest="install_method",
        default=None,
        help=(
            "How it installs (e.g. 'pipx', 'npm -g', 'binary', "
            "'skill load'). Free-form."
        ),
    )
    sub.add_argument(
        "--task-context",
        dest="task_context",
        default=None,
        help="What you were doing when you noticed the gap.",
    )
    sub.add_argument(
        "--why-this-tool",
        dest="why_this_tool",
        default=None,
        help="Why this specific tool / skill / capability fits the gap.",
    )
    sub.add_argument(
        "--alternatives",
        dest="alternatives_considered",
        default=None,
        help="Other options considered and why they were rejected.",
    )
    sub.add_argument(
        "--risk-cost",
        dest="risk_cost",
        default=None,
        help="Install risk, cost, sudo requirements, license concerns.",
    )
    sub.add_argument(
        "--confidence",
        choices=("high", "medium", "low"),
        default=None,
        help="Your confidence level in this recommendation.",
    )
    sub.add_argument(
        "--discovered",
        action="store_true",
        help=(
            "Set when you discovered the tool / skill / capability "
            "via research rather than already knowing it."
        ),
    )
    sub.add_argument(
        "--source",
        default=None,
        help=(
            "Where you found it (discovery filings only) — package "
            "registry, awesome-list, web search."
        ),
    )
    sub.add_argument(
        "--evidence",
        default=None,
        help=(
            "Supporting evidence (discovery filings only) — stars, "
            "downloads, last commit, license."
        ),
    )

    # Worker-form fields (item 5). Required when --agent-id names a worker.
    sub.add_argument(
        "--agent-id",
        dest="agent_id",
        default=None,
        help=(
            "Codename of the filing agent (one of: scout, dispatch, "
            "radar, bridge, alfred). When a worker codename is "
            "passed, the worker form activates: --gap and "
            "--workaround become required and the escalation target "
            "auto-infers to 'alfred' unless overridden."
        ),
    )
    sub.add_argument(
        "--escalation-target",
        dest="escalation_target",
        choices=sorted(ESCALATION_TARGET_VALUES),
        default=None,
        help=(
            "Routing target for the approval. 'alfred' = worker's "
            "escalation to Alfred. 'operator' = Alfred's onward "
            "escalation to the human operator (Stage 1.5). Omit for "
            "no escalation routing."
        ),
    )
    sub.add_argument(
        "--gap",
        default=None,
        help=(
            "What capability is missing? Required in the worker "
            "form."
        ),
    )
    sub.add_argument(
        "--workaround",
        dest="workaround_used",
        default=None,
        help=(
            "What you did instead. Required in the worker form."
        ),
    )

    # Behavior flags.
    sub.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit raw JSON response to stdout instead of rendered text.",
    )
    sub.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Per-call HTTP timeout in seconds (default 90).",
    )

    sub.set_defaults(func=run)


def _resolve_agent_id(raw: Optional[str]) -> Optional[str]:
    """Lower-case the agent_id and validate against the accepted set.

    Returns None if `raw` is None; raises `UsageError` if `raw` is
    non-None and outside the accepted set. Accepted: workers + alfred.
    """
    if raw is None:
        return None
    lowered = raw.lower()
    if lowered not in _ACCEPTED_AGENT_IDS:
        raise UsageError(
            f"--agent-id {raw!r} is not a recognized codename. "
            f"Accepted: {sorted(_ACCEPTED_AGENT_IDS)}"
        )
    return lowered


def _build_body(args: argparse.Namespace) -> dict[str, Any]:
    """Translate argparse Namespace into a POST /requests body.

    Presence-driven: only keys with non-None / explicitly-set values
    land in the body. The Pydantic schema on the server defaults
    missing keys to None — wire form stays lean.
    """
    body: dict[str, Any] = {"tool_name": args.tool_name}

    # Pass-through Optional fields.
    for src_attr, body_key in (
        ("category", "category"),
        ("install_method", "install_method"),
        ("task_context", "task_context"),
        ("why_this_tool", "why_this_tool"),
        ("alternatives_considered", "alternatives_considered"),
        ("risk_cost", "risk_cost"),
        ("confidence", "confidence"),
        ("source", "source"),
        ("evidence", "evidence"),
        ("agent_id", "agent_id"),
        ("escalation_target", "escalation_target"),
        ("gap", "gap"),
        ("workaround_used", "workaround_used"),
    ):
        value = getattr(args, src_attr, None)
        if value is not None:
            body[body_key] = value

    # `is_discovered` is a boolean store_true flag; True only when
    # explicitly set. We omit when False so the Pydantic default
    # (`is_discovered: bool = False`) engages, matching the lean
    # wire-form discipline from item 1a / item 3.
    if getattr(args, "discovered", False):
        body["is_discovered"] = True

    return body


def run(args: argparse.Namespace) -> int:
    # Normalize agent_id to canonical lowercase form (or surface 2
    # for unknown codename).
    args.agent_id = _resolve_agent_id(args.agent_id)

    # Worker-form auto-infer: only when --agent-id is a worker AND
    # the operator didn't pass --escalation-target explicitly.
    if args.escalation_target is None:
        inferred = infer_escalation_target(args.agent_id)
        if inferred is not None:
            args.escalation_target = inferred

    # Worker-form client-side validation per Decision N2a. The
    # is_worker_form predicate matches when ANY of agent_id /
    # escalation_target / gap / workaround_used carries content —
    # catches "operator passed --gap but forgot --agent-id" as worker
    # form (which then fails the missing-agent-id validation).
    if is_worker_form(
        agent_id=args.agent_id,
        escalation_target=args.escalation_target,
        gap=args.gap,
        workaround_used=args.workaround_used,
    ):
        # Worker-form requires agent_id ∈ WORKER_AGENT_IDS (not alfred,
        # not None). Alfred-as-filer with --gap / --workaround set
        # surfaces here for a clarifying error.
        if args.agent_id is None or args.agent_id not in WORKER_AGENT_IDS:
            raise UsageError(
                "Worker-form filings (--gap / --workaround / "
                "--escalation-target alfred) require --agent-id to "
                "name a worker (one of: "
                f"{sorted(WORKER_AGENT_IDS)})."
            )
        try:
            validate_worker_form(
                agent_id=args.agent_id,
                gap=args.gap,
                workaround_used=args.workaround_used,
            )
        except WorkerFormError as exc:
            raise UsageError(
                f"Worker-form filing for --agent-id {args.agent_id} "
                f"is missing required field(s): "
                f"{', '.join(exc.missing_fields)}. "
                "When --agent-id names a worker, both --gap and "
                "--workaround must be provided."
            ) from None

    body = _build_body(args)
    with HttpClient(timeout=args.timeout) as client:
        response = client.post(
            "/requests", body, response_model=RequestDetail
        )

    if args.emit_json:
        print(response.model_dump_json())
    else:
        render_request_tool(response, sys.stdout)
    return 0
