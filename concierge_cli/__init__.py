"""Thin HTTP-shim CLI for the Concierge service.

The CLI talks to the core FastAPI service on 127.0.0.1:8000 (or
$CONCIERGE_URL). Subcommands map 1:1 to service endpoints; the CLI
itself owns nothing operational — it renders responses and exits.

Stage 1A item 1a ships `concierge recommend` only. The remaining
subcommands (`request-tool`, `list-active`, `enable`, `disable`)
land in item 1b after their server-side dependencies (Stage 1A
items 4 / 5 / 6) are in place.
"""

__version__ = "0.1.0"
