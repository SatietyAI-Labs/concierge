"""Claude Code MCP adapter — stdio proxy shim (N10 framework + N11+ content).

Day 2 evening scope: framework only (jsonrpc + dispatcher + shim
main loop + stderr-only logging). Meta-tool handlers (N11),
backing-server forwarding (N13), and gap-report injection (N12)
all land Day 3.

Reading order:

1. `jsonrpc.py` — parse/serialize (pure)
2. `dispatcher.py` — async method registry + default handlers
3. `shim.py` — asyncio main loop
4. `logging_setup.py` — stderr-only logger config
"""
