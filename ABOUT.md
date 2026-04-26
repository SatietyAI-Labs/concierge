# About

I'm Lewis Sloan. 20+ years teaching, with a parallel career in residential automation, networking, and high-end whole-house AV integration. In March 2025 I got exposed to AI and went all-in within a month.

My teaching is project-based and multimodal — students learn by building real things, with the subject reinforced from multiple directions until it's load-bearing in their thinking. The method has stayed the same for two decades; the subject keeps moving. Lately the subject is AI. The integration-systems work gave me hands for thinking in capabilities, interfaces, and how systems mesh; the teaching gave me the pedagogy for making complex layered subjects legible to first-time learners. Concierge is what comes out of that synthesis.

Concierge started from an observation about agent behavior across the whole agent space, not just early systems. Agents will reach for the wrong tool and never tell you why they're struggling. They load whatever they want and don't surface their reasoning unless explicitly asked — even current products like Cowork do this. The point of Concierge is making that reasoning visible: agents that explain what tool they're reaching for, why, and how that benefits the task, so the operator-agent dialogue includes the tool-thinking that's normally invisible.

## Prior systems

OpenClaw (formerly Moltbot) is the third-party agent runtime I work in and on. I adopted it early, deployed it via WhatsApp on WSL on a Windows server, and have built inside it ever since.

**Semantic-memory MCP** — a ChromaDB-backed memory layer with sentence-transformer embeddings (`all-MiniLM-L6-v2`), built originally as a standalone Claude-targeted MCP server. I extended OpenClaw to accept arbitrary Claude MCPs as peer capabilities — a harness modification that let the memory layer run inside OpenClaw alongside other tools rather than as an external process. The memory stores tool decisions and persistent identity notes; Concierge inherits the same architecture and continues evolving it as the substrate generalizes across harnesses.

**Tool concierge for OpenClaw** — the beta iteration that became the testbed for the current harness-agnostic Concierge build. Embedded in the OpenClaw agent personality (`SKILL.md` and `SOUL-ADDITIONS.md`), it has been running the recommendation-and-lifecycle behavior across the fleet for the last few weeks; underlying components (the semantic-memory layer, the OpenClaw modifications to accept Claude MCPs) have been in place longer. Architecturally it's load-light-and-hot-swap: load only what's needed for the task, then unload so context frees up — DNA that carries directly into Concierge. The current iteration generalizes the design: model-agnostic, working across LLM providers rather than being OpenClaw-embedded, which is why it ships as harness-agnostic infrastructure.

## SatietyAI

SatietyAI is the teaching practice that wraps all of this. Right now it's courses and coaching — hands-on, project-based, applied to AI; the same pedagogical method I've been using for two decades, with a new subject. Product offerings for companies are on the roadmap.

## Mission

AI is the most consequential tool for individual self-development since the lever, the pulley, the industrial revolution. That's the actual claim — not that AI will solve everything, but that it's the next entry in a short list of tools that meaningfully expand what one person can do. SatietyAI is one vehicle for putting that tool in people's hands with guidance. Concierge is infrastructure for the same end — making AI tools accessible and well-used by the people building with them. Both are downstream of the same conviction: human flourishing through better tools, full stop.

---

- **Email:** hello@satietyai.io
- **Web:** https://satietyai.io
