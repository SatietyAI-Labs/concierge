# Contributing

**Concierge's value isn't just the code — it's the working discipline behind the code.**

## Working discipline

Every architectural decision is logged at `planning/decisions/DECISIONS.md` following a standard template. Every session writes a handoff snapshot at `planning/sessions/SESSION-YYYY-MM-DD-NN.md`. The day's plan lives at `planning/today.md`. The full operating protocol — session boundaries, handoff specs, decision log, the surface-then-execute discipline, wiring-test default rule, live-verify fresh-session-only rule — is at `planning/concierge-operations-protocol.md`. New contributors should read the protocol before opening a non-trivial PR; the protocol is what makes the project reproducibly improvable across sessions.

Surface-then-execute is the defining contribution shape: surface the approach, name the architectural fork(s) the change resolves, get alignment on the chosen path, then execute. PR descriptions should name the fork(s) the change resolves so reviewers can see the design surface without reading the code first. Tests for new functionality assert client-observable contracts; the wiring-test discipline is documented in the ops-protocol.

## Contributing flow

Clone the repo, run `uv sync`, run the test suite with `uv run pytest -m 'not slow'` to confirm a clean baseline before making changes. Open a GitHub Issue first for non-trivial work so the design surface is on the record before code lands. PRs should reference the Issue and name the fork(s) resolved. Bug reports and feature requests both go through the GitHub Issues templates.
