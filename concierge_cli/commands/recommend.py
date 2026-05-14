"""`concierge recommend` subcommand.

POSTs to /recommend and renders the response. The render layer in
`concierge_cli.output` is responsible for the prominent
memory-unavailable warning when applicable.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from concierge_cli.client import HttpClient
from concierge_cli.output import render_recommend
from core.recommend.schemas import RecommendResponse


def register(subparsers: argparse._SubParsersAction) -> None:
    sub = subparsers.add_parser(
        "recommend",
        help="Ask Concierge for a tool recommendation.",
    )
    sub.add_argument("task", help="Free-text description of the task.")
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


def run(args: argparse.Namespace) -> int:
    body: dict[str, Any] = {"task": args.task}
    with HttpClient(timeout=args.timeout) as client:
        response = client.post(
            "/recommend", body, response_model=RecommendResponse
        )

    if args.emit_json:
        print(response.model_dump_json())
    else:
        render_recommend(response, sys.stdout)
    return 0
