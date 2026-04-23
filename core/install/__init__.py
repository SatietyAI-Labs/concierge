"""X13 — tool install module.

Three low-level subprocess-wrapper installers plus a dispatcher
that routes an install_method string to the right one. Pure
adapter: owns subprocess invocation + result structuring; does
not touch the lifecycle store, does not emit log-level status
transitions, does not know whether the install is happening in
response to an approval or a manual CLI invocation.

**Caller contract (per N7 scope-boundary DECISIONS
`[2026-04-22 10:35]` and X13 architectural-touch note on Day 3):**

The intended upstream caller is `core/lifecycle_store/service.py::
update_status()` when the new status is `approved`. That service
extracts the install_method + tool_name (plus binary_url + dest if
applicable) from the request, passes them into
`install_by_method(...)`, and then applies a follow-up `installed`-
or-`failed` state transition based on the returned `InstallResult`.

The service-side wire-in is deliberately NOT bundled into the X13
commit. This module ships as independently-testable, independently-
callable surface; the wire-in (adding install_method to
RequestDetail, the `update_status` hook, integration tests) is a
~15-min follow-up commit.

**No-sudo invariant:** all three installers target user-writable
paths per the SOUL-delta `## Requesting Capabilities` rule:

- `install_npm_global` → `~/.npm-global` via `npm install -g`
  (requires the npm prefix to be set in the user's environment;
  `scripts/concierge-shim`'s parent shell typically has this).
- `install_pip_user` → `~/.local/` via `pip install --user`.
- `install_single_binary` → `~/bin/` (or caller-supplied dest; the
  dispatcher defaults to `~/bin/<slug>`).

Any install that would require sudo falls outside X13's scope.
Operator handles those manually per the behavioral rules.
"""
from core.install.methods import (
    install_npm_global,
    install_npx_mcp,
    install_pip_user,
    install_single_binary,
)
from core.install.schemas import InstallResult
from core.install.service import install_by_method, normalize_install_method


__all__ = [
    "InstallResult",
    "install_by_method",
    "install_npm_global",
    "install_npx_mcp",
    "install_pip_user",
    "install_single_binary",
    "normalize_install_method",
]
