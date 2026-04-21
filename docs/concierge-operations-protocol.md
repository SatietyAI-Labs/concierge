# Concierge — Operations Protocol
### How AI sessions, handoffs, decisions, and the daily rhythm work during the build week

This protocol governs the operational mechanics of working with Claude Code
across the Concierge build week. It exists because hackathon builds rarely
fail on the code — they fail on the working pattern around the code:
fragmented sessions, lost decisions, context drift, sleep deprivation,
stale test fixtures, panic refactors at hour 60.

The build plan references this protocol at every phase boundary. Treat it
as the operating system the build runs on.

---

## Optimization priorities (read this first)

The build operates under one explicit priority hierarchy:

1. **AI quality** — every decision favors the option that produces better
   thinking and cleaner output, regardless of cost
2. **Build smoothness** — handoffs, recovery, and continuity over speed
3. **Demo readiness by Day 4** — substantive completion early so polish
   and rehearsal have room
4. **Token cost / credit conservation — explicitly NOT a priority**

This means: effort stays at `xhigh` or `max` throughout. Sessions can run
deep into context. Re-explanation is fine when it improves grounding. Tool
calls stay generous. Parallel exploration is on the table for hard
decisions. Quality of thinking is the metric.

---

## The session model

### Session boundaries

**One session per phase deliverable, with soft and hard limits.**

A session is the period from `claude` launch to `/exit`. Each session has:
- One primary goal (defined before launch)
- One end-state criterion (what "done" looks like)
- One handoff snapshot (written by the agent in the last 5-10 minutes)

**Soft limits (trigger end-of-session handoff):**
- 6 hours of active work, OR
- 70% context utilization, OR
- The session goal is achieved

Whichever comes first.

**Hard limits (force end-of-session even if mid-task):**
- 8 hours of active work, OR
- 85% context utilization

Past 85% context, model quality degrades meaningfully. Past 8 hours
continuous, your input quality also degrades. Force the boundary.

### Exception: UI iteration sessions

Day 4 UI work benefits from longer continuous sessions because iterative
visual styling depends on the agent remembering small previous choices.
Allow up to 7 hours / 80% context for UI sessions specifically.

### Session count per day

Most days: **2 sessions** (morning block, afternoon block) plus a brief
**morning alignment session** (~20 min, just reads previous snapshots and
confirms day's plan).

Day 4: possibly **1-2 longer sessions** for UI work.

Days 5-6: variable. Could be many short sessions for bug fixes, or one long
session for demo recording prep.

---

## The handoff document spec

This is the single highest-leverage practice for cross-session continuity.
Every session ends with the agent producing a structured snapshot file. The
next session reads it first, before doing anything else.

### Location

`planning/sessions/SESSION-YYYY-MM-DD-NN.md`

Where `NN` is the session number for that day (01, 02, 03).

Example: `planning/sessions/SESSION-2026-04-22-02.md` is the second session
on Wednesday, April 22.

### Required template

```markdown
# Session SESSION-YYYY-MM-DD-NN

**Started:** [timestamp]
**Ended:** [timestamp]
**Primary goal:** [one sentence — what this session was for]
**Goal achieved:** [Yes / Partial / No]

## What was attempted this session
[One paragraph describing the session's arc]

## What was completed
- [concrete item with file path citation]
- [concrete item with file path citation]
- [...]

## What was started but not finished
- [item] — current state: [where it stopped, what remains]
- [...]

## Decisions made this session
- [Decision title] — see DECISIONS.md entry [timestamp]
- [...]

## Bugs / issues discovered
- [Bug description] — file: [path], reproduction: [steps]
- [...]

## Open questions for Lewie
- [Question] — options: [A], [B]; default if no answer: [option]
- [...]

## Next session should start by
[ONE specific concrete action — not "continue the work"]

## Context the next session needs to read first
1. [file path]
2. [file path]
3. [file path]
(Maximum 5 files. If next session needs more, you're framing the next
session too broadly.)
```

### Discipline

The handoff snapshot is **non-negotiable**. The agent writes it in the last
5-10 minutes of every session. If a session is forced to end at the hard
limit, the snapshot still gets written — even if it's brief. A bad
snapshot is infinitely better than no snapshot.

If a session ends without a snapshot (crash, accidental exit, etc.), the
**next session's first action** is to reconstruct one by reading the most
recent code changes and the decision log. Spend up to 30 minutes on this
before continuing.

---

## The decision log

Separate from session snapshots, every meaningful architectural or scope
decision is appended to a single growing log file.

### Location

`planning/decisions/DECISIONS.md`

### Entry template

```markdown
## [YYYY-MM-DD HH:MM] — [Decision Title]

**Context:** [What problem prompted this decision]

**Options considered:**
- [Option A] — [brief description]
- [Option B] — [brief description]
- [Option C] — [brief description]

**Decision:** [What we chose]

**Reasoning:** [Why — 2-4 sentences]

**Reversibility:** [Easy / Hard / Permanent]

**Decided by:** [Lewie / Claude Code / both via chat]

**Affects:** [List of files, components, or future decisions]

---
```

### When to log

A decision goes in DECISIONS.md when ANY of:
- It affects more than one file
- It affects how a future session will think about something
- It would be hard to remember in 3 days
- It traded off two reasonable alternatives

Routine implementation choices ("use a list comprehension here") do not get
logged. Architectural choices ("store the catalog as SQLite with markdown
export rather than markdown only") absolutely do.

### Use during sessions

Sessions should reference DECISIONS.md whenever:
- Approaching a component for the first time (read relevant prior
  decisions about it)
- About to make a choice that contradicts a prior decision (read the
  prior decision's reasoning, then either align or log the reversal)

---

## The two-workspace flow

You're operating in two parallel workspaces during the build week:

- **Claude.ai chat (this conversation)** — strategic planning, second
  opinions, architecture discussions, content drafting
- **Claude Code in WSL** — actual code, file operations, agent
  archaeology and build work

Keep them in sync via files, not by re-explaining.

### Pattern: Chat → Claude Code

When a decision is made in chat that affects the build:

1. Lewie summarizes the decision in one paragraph
2. Pastes into Claude Code with the wrapper:
   > "Decision update from planning chat: [paragraph]. Append to
   > planning/decisions/DECISIONS.md following the standard template,
   > then acknowledge."
3. Claude Code logs and confirms. Done.

### Pattern: Claude Code → Chat

When a Claude Code output needs strategic input:

1. Lewie copies the relevant snapshot file or planning doc into chat
2. Asks the question
3. I respond, decision gets logged via the Chat → Claude Code pattern

**You never re-explain context in either direction. Files are the source
of truth.**

### Pattern: Pasting bigger material to Claude Code

When you have larger reference material to give Claude Code:

1. Save it as a file in `planning/scratch/[descriptive-name].md`
2. Tell Claude Code: "I dropped reference material at
   planning/scratch/[name].md, please read it before responding to:
   [question]."

Avoid pasting large content directly into the prompt — creates ambiguity
about which version is canonical (in-context vs. on-disk).

---

## Test fixture management

A small but high-leverage practice. On Day 1 morning, create a
`planning/test-fixtures/` directory containing the test data used all week.

### Required fixtures

- `sample-task.md` — a realistic Claude Code task description that
  triggers Concierge (e.g., "analyze this CSV")
- `sample-csv.csv` — the CSV referenced by the sample task
- `sample-tool-request.md` — a sample pending request markdown file
  (matching the existing schema)
- `sample-catalog-state.json` — the starting state of the tool catalog
  for demo runs
- `expected-recommendation.md` — what the recommendation engine should
  produce for the sample task

### Discipline

- Same fixtures used in every test, every demo run, every troubleshooting
  scenario, every day of the week
- If a fixture needs to change, that's a Decision worthy of logging
- Demo recording on Day 6 uses these exact fixtures so behavior is
  predictable

---

## The daily rhythm

A repeating shape that creates predictability for the AI sessions and your
energy.

### Morning (target: 7am-8am start)

**Read previous evening's session snapshots** (15 min)
You read the last 1-2 SESSION snapshots from the previous day. Confirm
nothing surprising. If something needs adjustment, write it into
`planning/today.md`.

**Update today's plan** (15 min)
Open `planning/today.md`. Write:
- Today's primary goal
- Today's session plan (which sessions, which goals)
- Any open questions to resolve in the morning alignment session

**Morning alignment session** (~20 min, short Claude Code session)
Launch Claude Code. Single prompt:
> "Read the last session snapshot at planning/sessions/[file], read
> CLAUDE.md, read planning/today.md. Confirm understanding of today's
> goals. List any concerns or questions before I start the first build
> session."

Resolve any concerns. End the session. Move on.

### Build blocks (2-3 sessions, 3-6 hours each)

Each build session:

**Pre-session** (5 min)
Open `planning/today.md`. Confirm which session goal you're starting.
Write the goal and end-state criterion to a fresh `SESSION-START.md` file
in the project root. Launch Claude Code.

**Session opener prompt:**
> "Read SESSION-START.md, read the most recent file in
> planning/sessions/, read CLAUDE.md if you haven't already in this
> session. Confirm understanding of this session's goal. Then begin."

**During session:**
- Let the agent work
- Interrupt only when you have substantive direction or questions
- If something feels off, name it explicitly: "Pause. Are you sure
  about [X]? My concern is [Y]."

**Session close** (last 5-10 min)
Tell the agent: "We're closing this session. Write the handoff snapshot
to planning/sessions/SESSION-[today]-[NN].md following the standard
template. Append any decisions made this session to DECISIONS.md. Confirm
both files exist before exiting."

Verify the snapshot exists and is complete. Then `/exit`.

### Midday checkpoint (~15 min, after lunch break)

Skim the morning session snapshots. If something looks off, address it
before the afternoon session starts. Cheap insurance against drift.

If everything looks good, no action needed. Move on.

### Evening close (30 min, target 8-9pm)

**Last session writes its snapshot.** You read it carefully.

**Write tomorrow's first action** into `planning/today.md` so tomorrow's
morning session has a clear starting point.

**Stop.** No more build sessions in the day.

### Hard stop

No build sessions after 9pm. No exceptions. If something feels urgent at
9:30pm, it almost never is. Tomorrow's first session at 7am will be more
productive than tonight's panic at 11pm.

---

## Phase checkpoint criteria

Each phase boundary has explicit pass/fail criteria. Either everything is
checked or you're not at the next phase. No "basically done."

### Phase A — Codification

- [ ] `planning/inventory.md` exists
- [ ] Every component from the v2 blueprint is mapped to a file path
      (or marked "not found" with explanation)
- [ ] Cron housekeeping script located and documented
- [ ] Beta tool concierge MCP load/unload code located
- [ ] Top 5 findings summarized in chat to Lewie
- [ ] Open questions list reviewed by Lewie before continuing

### Phase B — Architecture Mapping

- [ ] `planning/architecture-map.md` exists
- [ ] Every existing component mapped to one or more blueprint components
- [ ] Claude Code adapter gap fully specified
- [ ] UI gap fully specified (data needs per section)
- [ ] Lewie has reviewed the map before Phase C

### Phase C — Classify

- [ ] `planning/classification.md` exists
- [ ] Every existing component has exactly one classification
- [ ] Effort estimates totaled and sanity-checked
- [ ] Scope risk flagged if total exceeds 50 hours
- [ ] Lewie has reviewed and signed off on classifications

### Phase D — Dependency Graph

- [ ] `planning/dependency-graph.md` exists
- [ ] Critical path identified
- [ ] Parallel work and deferrable items called out

### Phase E — Gap Analysis

- [ ] `planning/gap-analysis.md` exists
- [ ] Every demo capability has clear coverage status
- [ ] Top 5 risks documented

### Phase F — Build Plan

- [ ] `planning/build-plan.md` exists
- [ ] Day-by-day plan produced
- [ ] Demo scenario validated as achievable
- [ ] Risk register complete
- [ ] `planning/executive-summary.md` produced as capstone

### Build Day 1 (Tuesday)

- [ ] Catalog API endpoint `GET /tools` returns JSON from SQLite store
- [ ] Lewie can curl the endpoint and see the catalog data
- [ ] Day 1 handoff snapshot written

### Build Day 2 (Wednesday)

- [ ] `POST /recommend` returns ranked recommendations for a sample task
- [ ] `GET /requests/pending` lists current pending requests
- [ ] `POST /requests/{id}/approve` updates the status line in the
      markdown file
- [ ] Cron picks up the status change and moves the file
- [ ] Day 2 handoff snapshot written

### Build Day 3 (Thursday)

- [ ] Claude Code session can call `POST /recommend` and receive a
      response
- [ ] Claude Code session can have an MCP server loaded mid-session via
      Concierge
- [ ] Gap report injection works (Concierge can push a recommendation
      into the agent's context)
- [ ] One end-to-end task scenario demonstrated working
- [ ] Day 3 handoff snapshot written

### Build Day 4 (Friday) — Substantive completion target

- [ ] UI loads in browser at localhost
- [ ] Tool Registry section shows packs and sub-tools, expandable
- [ ] Pending Requests Inbox renders requests, approve/deny/defer buttons
      work via HTMX
- [ ] Health/Stats bar at top displays live data
- [ ] End-to-end demo scenario passes start to finish at least once
      without intervention
- [ ] Day 4 handoff snapshot written

### Build Day 5 (Saturday)

- [ ] Demo scenario passes 5 consecutive runs without intervention
- [ ] Top 3 bugs from Day 4 fixed
- [ ] UI polish complete (titles, labels, empty states, error states)
- [ ] Day 5 handoff snapshot written

### Build Day 6 (Sunday)

- [ ] Demo video recorded (3 minutes)
- [ ] README written
- [ ] Project description for submission written
- [ ] Submission complete

---

## Recovery procedures

Three severity levels. Each has a clear action.

### Level 1 — Session went weird

**Symptoms:**
- Agent contradicts its own earlier statements within the same session
- Agent loops on the same wrong approach
- Output is obviously incorrect or incoherent
- Agent forgets requirements stated minutes earlier

**Action:**
1. End the session immediately with `/exit`
2. Write a brief snapshot capturing what went wrong (manually if needed)
3. Start a fresh session
4. New session reads the snapshot + CLAUDE.md only
5. Restart the work

**Cost:** ~15 minutes, no real damage.

**Common cause:** Context utilization too high. Don't let it happen again
on the same session — once an agent goes weird, it doesn't recover.

### Level 2 — A day's deliverable doesn't pass checkpoint criteria

**Symptoms:**
- End of day, checkpoint checklist has unchecked items
- The deliverable "almost works" but has a bug you can't isolate
- A core piece is missing that you thought was done

**Action:**
1. Do not push into the next day's work
2. Write the day's snapshot honestly — what works, what doesn't, what
   the bug looks like
3. Sleep
4. Next morning's first session is dedicated to diagnosing the issue in
   isolation
5. Only after the diagnosis is clear do you decide: fix, work around, or
   re-scope

The build plan has buffer for this. Do not skip the diagnosis to "save
time" — undiagnosed bugs grow.

### Level 3 — A core architectural decision was wrong

**Symptoms:**
- Discovered on Day 3 or 4 that something built on Day 1-2 doesn't work
  for what we now need
- The agent keeps proposing workarounds that feel forced
- You realize you misunderstood a constraint

**Action:**
1. Stop. Do not try to fix architecture inside Claude Code in panic mode.
2. Open this Claude.ai chat. Describe what's wrong and what changed.
3. We talk through options, choose a path, log the new decision in
   DECISIONS.md.
4. Claude Code gets a fresh prompt with the new direction.
5. The day's plan in `planning/today.md` gets revised.

This is what Day 5's buffer is partially for. A Level 3 event on Day 4
or 5 is recoverable. A Level 3 event on Day 6 likely means cutting a
feature from the demo. That's acceptable — better to demo less, smoothly.

---

## Effort level guidance per phase

The default is `xhigh` throughout. Specific guidance:

- **Phase A (Codification)** — `xhigh`. Routine read-and-document work
  with occasional judgment calls.
- **Phase B (Architecture Mapping)** — `xhigh`. Same shape as A.
- **Phase C (Classify)** — `max`. This is the highest-stakes planning
  decision. Burn the cycles.
- **Phase D (Dependency Graph)** — `xhigh`.
- **Phase E (Gap Analysis)** — `xhigh`.
- **Phase F (Build Plan)** — `max`. Capstone planning document. Worth
  every cycle.
- **Build Day 1-3** — `xhigh` default. Bump to `max` when making
  architecture choices that came up mid-build.
- **Build Day 4 (UI)** — `xhigh`. UI iteration benefits from speed of
  iteration; max would slow it without much quality gain.
- **Build Day 5-6** — `xhigh` for bug fixes, `max` only if a stubborn
  bug needs deep reasoning.

To set per-session: open Claude Code, type `/effort max` (or `xhigh`).

---

## Energy management

This isn't only about your brain — agent quality follows your input
quality. Tired prompts produce worse outputs that take more turns to fix.

### Mandatory practices

- **Sleep window: 11pm to 6am minimum.** No build sessions in this
  window.
- **Mid-day break: 30 minutes.** Outside or away from screens. Eat real
  food.
- **Hydration cadence: every 2 hours.** Set a timer if needed.
- **Hard stop: 9pm.** No new build sessions after this.

### The "tomorrow rule"

If you find yourself thinking "let me just finish this one thing" past
9pm, stop. Write the snapshot. Tomorrow's first session at 7am will be
more productive than tonight's grinding at 11pm.

The buffer in the build plan exists to absorb this. Use it.

### When to take an unplanned break

If you notice ANY of:
- You've re-read the same paragraph three times
- You're typing prompts that don't make sense
- You're frustrated with the agent for things that aren't its fault
- You're considering "just one more session" past your stop time

→ Stop. 30-minute break minimum. Walk away from the screen.

---

## Token / context economy (revised priorities)

Since AI quality > token cost, the rules are minimal:

**Practices to keep:**
- Files in folders for large reference material (avoids in-context vs.
  on-disk ambiguity, regardless of cost)
- Single source of truth in CLAUDE.md and decision log (avoids
  contradictions, regardless of cost)
- `/compact` is **avoided** in favor of session boundaries with proper
  snapshots (snapshots are higher fidelity than auto-summary)

**Practices to drop:**
- "Don't paste large content" — fine to paste if it helps clarity, just
  prefer files-in-folders for anything you'll reference more than once
- "Drop to lower effort for routine work" — stay at xhigh
- "Minimize tool calls per turn" — let the agent read and verify as
  thoroughly as it wants

**Practices to add:**
- For hard decisions, **parallel exploration** is on the table. Have
  Claude Code work two approaches in two sessions, compare results, pick
  the better one. Worth the credits for design-defining choices.

---

## A note on consistency

Almost all of this protocol's value comes from following it consistently,
not from the specific rules being optimal. A mediocre snapshot template
followed every time beats a perfect template followed three out of six
days.

If something in this protocol breaks down on Day 2, talk about it in chat
before deviating. Adjust the protocol; don't abandon it.
