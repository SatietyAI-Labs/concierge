"""Concierge HTTP API — FastAPI routers for catalog and lifecycle surfaces.

This package's `__init__` is deliberately import-free. The router
modules (`tools`, `packs`, `recommend`, ...) each import FastAPI;
`core/app.py` imports the submodules it needs explicitly at service
startup. Eagerly importing routers here would pull FastAPI into the
import graph of any module that touches `core.api.schemas` — and
`concierge_cli` imports `core.api.schemas` for the `ToolList` /
`ToolOut` response models behind `concierge list-active`. Keeping this
file import-free preserves the CLI's thin-shim weight (no FastAPI on a
`concierge recommend` invocation). See Stage 1A item 1b close.
"""
