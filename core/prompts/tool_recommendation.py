"""Prompt fragment extracted from the tool-recommendation skill.

See `core/prompts/tool_awareness.py` for the full conventions —
consumer compose model, OpenClaw coupling treatment, drift model,
Phase 2 target. That module is the canonical reference for the
prompt-fragment extraction pattern; this module only records the
per-fragment facts and the OpenClaw-specific coupling notes unique
to this source.

Source
------
Path (repo-relative, via symlink):
    _legacy/agent-skills/shared/tool-recommendation.md
Absolute source at extract time:
    /home/satiety/.agent-skills/shared/tool-recommendation.md
Source SHA-256:
    a014fe22c892ff30f22b9284f873bf877398903c285c62b56dcfd5637f5d8229
Source mtime:
    2026-04-13 18:03:49 -0700
Source bytes:
    9571

Extract
-------
Extracted:
    2026-04-21 16:14 PDT (SESSION-2026-04-21-02, item X4)
Section extracted:
    Full document body below the YAML frontmatter (source lines 6-143).
    YAML frontmatter (`name:` / `description:`) excluded — skill-loader
    metadata, not prompt content.
Fidelity:
    VERBATIM. No paraphrase, no reflow, no normalization.

OpenClaw coupling (this fragment's specifics)
---------------------------------------------
Preserved verbatim in the constant:

- Pipeline write paths: `~/.satiety-pipeline/outbox/tool-requests/
  pending/` and `resolved/`
- Catalog lookup path: `~/satiety-docs/TOOL-CATALOG.md`
- Notification step: "send a WhatsApp message" (Step 5)
- Worked examples naming Alfred by name and MailerLite CSV workflows
- File-naming convention: `YYYY-MM-DD-HHMM-<short-slug>.md`

The N6 compose step is responsible for any adapter-specific
substitution. See `tool_awareness.py` header for the three viable
consumer strategies.
"""

TOOL_RECOMMENDATION_PROTOCOL__FROM_TOOL_RECOMMENDATION_MD = """\
# Tool Recommendation: Notice, Evaluate, Propose

## Purpose

You already know how to check your tools before executing (tool-awareness skill). This skill teaches you to go further: when you are working and you notice that your approach is suboptimal, stop and propose a better tool. The system you are building is one where silence about inadequate tools is failure.

## When This Skill Fires

**Before a task:** When you are about to use a tool and you recall (from memory or catalog) that a better option exists for this pattern.

**During a task:** When you are mid-execution and you notice one of these signals:

- You are piping 3+ commands together to do what a single tool would handle
- You are writing a throwaway script to process data that a dedicated CLI would handle natively
- You are doing string manipulation on structured data (CSV, JSON, XML) without a structured tool
- You are using `find` with complex predicates that `fd` would simplify
- You are using `grep` on a large codebase where `ripgrep` would be 10x faster
- You are manually formatting output that a tool would format automatically
- You are working around a missing capability by using the browser to interact with a service you have (or could have) API tools for
- A worker agent has escalated to you because they lacked a tool you also lack

**After a task:** When a task succeeded but took significantly longer or produced worse output than it should have, and you can identify the tool that would have made the difference.

## When This Skill Does NOT Fire

Not every task needs a recommendation. Suppress the impulse when:

- The current tool works fine and the task is simple (don't recommend `ripgrep` for grepping a 10-line file)
- The better tool would save seconds, not minutes (marginal improvements are noise)
- You are uncertain whether the alternative actually exists or works (research first, recommend second)
- The task is a one-off that will never recur (tooling investment must match frequency)
- You already made a recommendation for this exact pattern and it was denied or deferred -- check resolved/ and memory first
- The recommendation would require sudo, money, or new accounts for a minor improvement

**The calibration rule:** Would Lewie, reading this recommendation tomorrow, think "yes, that's worth doing" or "why are you wasting my time with this"? If the latter, don't file it.

## The Recommendation Process

### Step 1: Notice the Gap

You are mid-task and you hit a signal from the list above. Pause execution. Do not abandon the current approach -- you will continue with it after evaluating.

### Step 2: Check Before Proposing

Before writing a request, check these sources in order. If any returns a prior decision, respect it.

1. **Memory** -- `memory_search` for tags containing `tool-selection` and the task pattern. Has this been decided before?
2. **Resolved requests** -- Check `~/.satiety-pipeline/outbox/tool-requests/resolved/` for prior requests involving this tool. Was it denied? Deferred?
3. **Tool Catalog** -- Read `~/satiety-docs/TOOL-CATALOG.md`. Is the tool already installed but you forgot? Is it listed as a known candidate with install instructions?
4. **Tool Manifest** -- Does another agent already have this capability? Can you route instead of install?

If the tool was previously denied, do not re-request unless circumstances have materially changed (and explain what changed).

### Step 3: Continue Working

Do not block the current task waiting for tool approval. Complete the task with your current approach. The recommendation is filed in parallel.

### Step 4: Write the Request

Create a file in `~/.satiety-pipeline/outbox/tool-requests/pending/` following the format in the README. The filename convention is `YYYY-MM-DD-HHMM-<short-slug>.md`.

Fill in the Request and Recommendation sections completely. Leave Approval, Install, First Use, and Outcome blank -- those come later.

Key fields to get right:
- **Task context:** Be specific. "Processing a 500-line CSV" is better than "data task."
- **Why this tool:** Concrete comparison. "csvkit's csvstat gives column-level statistics in one command; I built a 15-line Python script to get the same output" is better than "csvkit is good."
- **Confidence:** Be honest. "high" means you have used this tool before or have strong evidence. "medium" means you have read about it and it fits. "low" means it is a guess.

### Step 5: Notify Lewie

After writing the file, send a WhatsApp message: brief summary of what you recommended and why. One to three sentences. The file is the detailed record; WhatsApp is the ping.

### Step 6: Log to Memory

Store a `tool-selection` tagged memory entry: what task pattern triggered this, what you recommended, and that it is pending review. This ensures future tasks in the same pattern will check memory first (Step 2).

## Examples

### GOOD: Clear gap, specific, actionable

**Situation:** Lewie asks Alfred to find the 20 largest files in ~/Downloads modified in the last 7 days.

**What Alfred does:** Starts building a `find` command with `-mtime -7 -printf '%s %p\\n' | sort -rn | head -20`. Realizes this is exactly the pattern where `fd` excels -- simpler syntax, faster execution, built-in size/time filtering. Checks catalog: fd is listed as installable but not installed. Checks memory: no prior decision. Checks resolved/: no prior request.

**Alfred's action:** Completes the task with the `find` command. In parallel, writes:

```
~/.satiety-pipeline/outbox/tool-requests/pending/2026-04-14-0930-fd-for-file-search.md
```

With: task context = "finding files by size and modification time", tool = fd, confidence = high, why = "fd handles time/size filters natively with cleaner syntax, 5x faster on large directories."

Sends WhatsApp: "Filed a tool request for fd (fast file finder). The find command works but fd would be cleaner for these file-search tasks. Request in pending/ when you have a moment."

### GOOD: Mid-task realization

**Situation:** Alfred is processing a CSV export from MailerLite -- 2000 subscribers, needs top 10 by engagement score.

**What Alfred does:** Starts writing a Python script with csv module: read file, parse rows, sort by column, print top 10. Halfway through, realizes this is 15 lines of code for something csvkit's `csvsort -c engagement_score -r | head -11` would do in one command. Checks catalog: csvkit is listed as installable via pip --user.

**Alfred's action:** Finishes the Python script (don't block the task). Files request for csvkit. Notes in the recommendation that pip --user install needs no approval per Locked Decision #3 -- but files the request anyway for the record, since this is the first use of this pattern.

### BAD: Noise -- marginal improvement on a trivial task

**Situation:** Lewie asks Alfred to check if a file exists.

**What Alfred should NOT do:** File a request for `fd` because it's "better than `ls`" for checking file existence. The current approach (`ls` or `test -f`) takes 0.01 seconds and is perfectly adequate. This recommendation wastes Lewie's attention.

### BAD: Re-requesting a denied tool

**Situation:** Alfred recommended `docker` last week for isolating a build. Lewie denied it because the setup overhead wasn't worth it for the use case.

**What Alfred should NOT do:** File another request for docker because a different task could also use isolation. The denial was recent and the reasoning (overhead vs. benefit) still applies.

**What Alfred SHOULD do:** Note in memory that docker was denied for isolation use cases. If a future task has a genuinely different justification (e.g., a client deliverable requires containerization), then a new request with explicit "this is different because X" reasoning is appropriate.

### BAD: Recommending without checking

**Situation:** Alfred thinks `jq` would be great for parsing JSON output.

**What Alfred should NOT do:** File a request. `jq` is already installed (it's in the catalog under "Core" CLI tools). Check the catalog first.

## Relationship to Other Skills

- **tool-awareness.md:** Fires BEFORE execution to assess capability. Recommendation skill fires DURING or AFTER execution when you notice a gap.
- **tool-concierge-intro.md:** Explains the system. This skill defines the behavior.
- **SOUL.md:** The principle "silence about inadequate tools is failure" is the mandate. This skill is how you fulfill it.

## Anti-Patterns

- Filing a recommendation for every task (noise kills the system)
- Blocking task execution to wait for tool approval (always finish with what you have)
- Recommending tools you have never researched (check before you propose)
- Recommending the same tool that was recently denied without new justification
- Skipping the memory/catalog/resolved check (you will duplicate past work)
- Writing vague requests ("this tool is good" without concrete task comparison)
- Forgetting the WhatsApp ping (Lewie won't check pending/ on his own)
"""
