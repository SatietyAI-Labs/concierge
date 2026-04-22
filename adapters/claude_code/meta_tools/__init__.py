"""N11 meta-tools — three MCP tools that back on Concierge HTTP endpoints.

Call `register_meta_tools(dispatcher)` from the shim's `main()` after
`build_default_dispatcher()` but before the stdin-read loop starts.
The N9 DECISIONS entry `[2026-04-22 11:48]` establishes this
pre-stdin-readiness constraint — registration must complete before
the dispatcher accepts the client's initial `tools/list` query.

The three tools are registered unconditionally. Cut 3 (per
build-plan §F.2.3) drops `concierge_list_active` by removing its
registration line here and deleting the `list_active.py` module.
"""
from adapters.claude_code.dispatcher import Dispatcher
from adapters.claude_code.meta_tools.list_active import (
    handle_list_active,
    list_active_spec,
)
from adapters.claude_code.meta_tools.recommend import (
    handle_recommend,
    recommend_spec,
)
from adapters.claude_code.meta_tools.request_tool import (
    handle_request_tool,
    request_tool_spec,
)


def register_meta_tools(dispatcher: Dispatcher) -> None:
    """Register all N11 meta-tools onto the given dispatcher.

    Registration is synchronous and in priority order (recommend
    first, then request_tool, then list_active) so that if a future
    extension throws partway through, the highest-priority tool is
    already available.
    """
    dispatcher.register_tool(recommend_spec, handle_recommend)
    dispatcher.register_tool(request_tool_spec, handle_request_tool)
    dispatcher.register_tool(list_active_spec, handle_list_active)


__all__ = ["register_meta_tools"]
