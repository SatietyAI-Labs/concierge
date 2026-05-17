"""`concierge list-active` subcommand — Stage 1A item 1b.

GETs `/tools` and renders the catalog as a quick inventory grouped by
pack. By default it filters to `active=true` (loaded-on-boot tools);
`--dormant` flips the filter to in-manifest activation candidates, per
the `/tools` endpoint's `dormant` convenience filter. Both filters
resolve to `lifecycle_state` — the legacy `is_active` column was
retired (DECISIONS D112).

This is the one item-1b subcommand that is a genuine HTTP shim — the
catalog lives in the service's database. `enable` / `disable` are the
principled outliers (local-filesystem mutators, no HTTP).

The render surfaces the Stage 1A items-4+7 catalog metadata columns
(`best_for`, `limitation`, `agent_owner`, `transport`) so an operator
gets the use-case / anti-pattern prose inline rather than having to
cross-reference TOOL-MANIFEST.md.
"""
from __future__ import annotations

import argparse
import sys

from concierge_cli.client import HttpClient
from concierge_cli.output import render_list_active
from core.api.schemas import ToolList


# Meta-tool precedent (`concierge_list_active`) requests the full set
# rather than a page — an inventory subcommand wants everything.
_LIST_LIMIT = 1000


def register(subparsers: argparse._SubParsersAction) -> None:
    sub = subparsers.add_parser(
        "list-active",
        help=(
            "List tools currently active in Concierge's catalog, "
            "grouped by pack. Pass --dormant to list "
            "in-manifest-but-inactive tools (activation candidates) "
            "instead."
        ),
    )
    sub.add_argument(
        "--dormant",
        action="store_true",
        help=(
            "List in-manifest-but-inactive tools instead of active "
            "ones — candidates for activation via `concierge enable`."
        ),
    )
    sub.add_argument(
        "--category",
        default=None,
        help="Filter to a single catalog category (e.g. 'data-processing').",
    )
    sub.add_argument(
        "--pack-slug",
        dest="pack_slug",
        default=None,
        help="Filter to a single pack slug.",
    )
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


def _build_params(args: argparse.Namespace) -> dict[str, object]:
    """Translate argparse Namespace into `/tools` query parameters.

    `--dormant` and the default `active=true` are mutually exclusive:
    dormant is the in-manifest activation-candidate set (lifecycle_state
    in discovered/pending/pending-decision), disjoint from the
    loaded-on-boot `active` set, so sending `active=true` alongside
    would contradict it.
    """
    params: dict[str, object] = {}
    if args.dormant:
        params["dormant"] = "true"
    else:
        params["active"] = "true"
    if args.category is not None:
        params["category"] = args.category
    if args.pack_slug is not None:
        params["pack_slug"] = args.pack_slug
    params["limit"] = _LIST_LIMIT
    return params


def run(args: argparse.Namespace) -> int:
    params = _build_params(args)
    with HttpClient(timeout=args.timeout) as client:
        response = client.get("/tools", params=params, response_model=ToolList)

    if args.emit_json:
        print(response.model_dump_json())
    else:
        render_list_active(response, sys.stdout, dormant=args.dormant)
    return 0
