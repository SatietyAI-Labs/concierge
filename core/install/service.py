"""install_by_method dispatcher + install-method-string normalizer.

`install_by_method(...)` routes an operator-authored `install_method`
string (e.g. "npm -g", "pip install --user", "single binary") to
the right low-level installer. Returns `None` (not an InstallResult)
when the string doesn't match any known method — that signals
"operator must install manually" to the caller, distinct from an
install failure.

`normalize_install_method(...)` is exposed so the eventual
lifecycle-store wire-in can decide *whether* to call install_by_method
at all (e.g. skip the X13 call entirely if the method is unknown,
transitioning the request to `deferred` instead of calling X13 and
then branching on None).
"""
from __future__ import annotations

import logging
from typing import Optional

from core.install.methods import (
    METHOD_NPM_GLOBAL,
    METHOD_NPX_MCP,
    METHOD_PIP_USER,
    METHOD_PIPX,
    METHOD_SINGLE_BINARY,
    install_npm_global,
    install_npx_mcp,
    install_pip_user,
    install_pipx,
    install_single_binary,
)
from core.install.schemas import InstallResult


logger = logging.getLogger(__name__)


def normalize_install_method(install_method: Optional[str]) -> Optional[str]:
    """Canonicalize an operator-authored install-method string to one
    of `npm_global` / `pip_user` / `single_binary`, or None if no
    match.

    Operators fill in the `install_method` field on a tool request
    free-form; we match against a set of common substrings rather
    than requiring exact strings. Case-insensitive.
    """
    if not install_method:
        return None
    s = install_method.strip().lower()
    if not s:
        return None

    # npx_mcp signals — check BEFORE npm_global so "npx ..." strings
    # (which contain "npm" as a substring via "npx") route to the
    # MCP handler instead of the global-install one.
    if "npx" in s:
        return METHOD_NPX_MCP
    if s in {"npx-mcp", "npx_mcp"}:
        return METHOD_NPX_MCP

    # npm_global signals
    if "npm" in s and ("global" in s or "-g " in s or s.endswith("-g") or " -g" in s):
        return METHOD_NPM_GLOBAL
    if s in {"npm", "npm-global", "npm_global", "npm global"}:
        return METHOD_NPM_GLOBAL

    # pipx signals — check BEFORE pip_user so "pipx ..." strings
    # (which contain "pip" as a substring via "pipx") route to the
    # pipx handler instead of the pip-user one. The substring check
    # alone covers every meaningful pipx string ("pipx", "pipx install",
    # "pipx-install", etc. all contain the "pipx" substring).
    if "pipx" in s:
        return METHOD_PIPX

    # pip_user signals
    if "pip" in s and ("--user" in s or "user" in s):
        return METHOD_PIP_USER
    if s in {"pip", "pip-user", "pip_user"}:
        return METHOD_PIP_USER

    # single_binary signals
    if "single binary" in s or "binary" in s or "curl" in s or "download" in s:
        return METHOD_SINGLE_BINARY
    if s in {"binary", "single-binary", "single_binary"}:
        return METHOD_SINGLE_BINARY

    return None


def install_by_method(
    install_method: str,
    *,
    tool_name: str,
    binary_url: Optional[str] = None,
    binary_dest: Optional[str] = None,
    timeout_seconds: Optional[float] = None,
) -> Optional[InstallResult]:
    """Route `install_method` to a low-level installer.

    Parameters:
        install_method   free-form method string (e.g. "npm -g")
        tool_name        package name for npm / pip methods
        binary_url       required for single_binary
        binary_dest      required for single_binary (destination path,
                         `~/bin/<tool_name>` if caller wants the
                         default — NOT defaulted here so the caller's
                         choice is explicit in the audit trail)
        timeout_seconds  optional override; installer-specific default
                         used when None

    Returns:
        InstallResult on attempt (success or failure).
        None when:
          - install_method doesn't canonicalize to a known method, OR
          - single_binary is selected but binary_url/dest are missing.
        The None-return path signals "operator must handle this
        manually" — distinct from an attempted-but-failed install.
    """
    method_key = normalize_install_method(install_method)
    if method_key is None:
        logger.info(
            "install.dispatcher.unrecognized install_method=%r — operator must handle manually",
            install_method,
        )
        return None

    if method_key == METHOD_NPM_GLOBAL:
        kwargs = {"timeout_seconds": timeout_seconds} if timeout_seconds is not None else {}
        return install_npm_global(tool_name, **kwargs)

    if method_key == METHOD_NPX_MCP:
        kwargs = {"timeout_seconds": timeout_seconds} if timeout_seconds is not None else {}
        return install_npx_mcp(tool_name, **kwargs)

    if method_key == METHOD_PIP_USER:
        kwargs = {"timeout_seconds": timeout_seconds} if timeout_seconds is not None else {}
        return install_pip_user(tool_name, **kwargs)

    if method_key == METHOD_PIPX:
        kwargs = {"timeout_seconds": timeout_seconds} if timeout_seconds is not None else {}
        return install_pipx(tool_name, **kwargs)

    if method_key == METHOD_SINGLE_BINARY:
        if binary_url is None or binary_dest is None:
            logger.info(
                "install.dispatcher.missing_binary_params install_method=%r — url=%s dest=%s",
                install_method,
                binary_url,
                binary_dest,
            )
            return None
        kwargs = {"timeout_seconds": timeout_seconds} if timeout_seconds is not None else {}
        return install_single_binary(binary_url, binary_dest, **kwargs)

    # Should be unreachable — normalize_install_method returns one of
    # the three constants or None; belt-and-suspenders.
    logger.warning("install.dispatcher.unreachable method_key=%r", method_key)
    return None
