# UltraThink 2.0

**Reasoning skills for Claude Code that actually make it think.**

> AI's failure mode isn't "can't reason" — it's pattern completion bias.
> These skills force investigation before reasoning, and reasoning before changes.

---

## What This Is

A set of markdown skill files (`.md`) you drop into your Claude Code project to unlock structured reasoning modes. One unified skill that auto-selects depth, or 3 standalone skills you can use individually.

**1,238 lines of operator-grade prompting. MIT licensed. Free.**

## The Problem

Every AI coding assistant has the same failure loop:

```
see familiar pattern → stop reading → predict from training data → patch → fail → repeat
```

UltraThink breaks this loop by forcing the model through structured reasoning before it touches code.

## Skills

### 🧠 UltraThink 2.0 — The Unified Engine
> [`skills/ultrathink2-SKILL.md`](skills/ultrathink2-SKILL.md) · 732 lines

Auto-classifies any task and selects the optimal reasoning architecture:

| Mode | When | Depth | Architecture |
|------|------|-------|-------------|
| **Rapid Strike** | Low complexity, low stakes | 2-5K tokens | Quick confidence check |
| **Deep Think** | Medium tasks | 10-20K tokens | 11 sequential reasoning techniques |
| **Ensemble** | High complexity | 20-40K tokens | 5-way parallel sub-reasoners |
| **Megamind** | Extreme complexity | 40-80K tokens | 10 angles → 3 synthesizers → 1 decision |
| **Grand Jury** | Debugging / prior failures | Evidence-gated | Courtroom-standard investigation |

Auto-escalates when confidence drops. Auto-de-escalates when certainty is high.
Supports parallel subprocess execution via `claude -p` for context efficiency.

### ⚡ Deep Think — 11-Technique Sequential Reasoning
> [`skills/deepthink-SKILL.md`](skills/deepthink-SKILL.md) · 161 lines

Forces the model through every reasoning technique before answering:

Meta-cognition → Step-back → Decomposition → Tree of Thought → First Principles → Analogical Reasoning → Chain of Thought → Devil's Advocate → Inversion → RAVEN Loop → Recursive Self-Improvement

Every checkpoint is mandatory. No shortcuts.

### 🌀 Megamind — 10→3→1 Meta-Reasoning
> [`skills/megamind-SKILL.md`](skills/megamind-SKILL.md) · 172 lines

Maximum depth architecture:
- **10 angle-explorers** (performance, security, edge cases, devil's advocate, scalability, beginner's mind, future self, user perspective, constraint breaker, simplicity)
- **3 synthesizers** (consensus builder, conflict analyzer, risk assessor)
- **1 final reasoner** that integrates everything

Loops until confidence ≥ 7. Maximum 3 iterations.

### ⚖️ DiamondThink — Grand Jury Investigation Protocol
> [`skills/diamondthink-SKILL.md`](skills/diamondthink-SKILL.md) · 173 lines

Courtroom-standard debugging. 8 phases:

1. **Commitment** — declare tools, constraints, pledge
2. **Symptom Record** — lock the problem before investigating
3. **Territory Map** — prove what exists, flag source vs generated
4. **Assumptions Ledger** — surface hidden training-data assumptions
5. **Search Pass** — mandatory repo-wide search with negative proofs
6. **Evidence Ledger** — verbatim excerpts with line numbers, no summaries
7. **Murder Board** — 4+ competing hypotheses with evidence FOR and AGAINST
8. **Pre-Flight** — evidence-backed fix plan, then one atomic change

No claim without evidence. No fix without proof. No retry without new data.

## Quick Start

```bash
# Clone
git clone https://github.com/alexalexalex222/ultrathink.git

# Copy the unified skill into your project
cp ultrathink/skills/ultrathink2-SKILL.md your-project/.claude/skills/

# Or copy individual skills
cp ultrathink/skills/deepthink-SKILL.md your-project/.claude/skills/
cp ultrathink/skills/megamind-SKILL.md your-project/.claude/skills/
cp ultrathink/skills/diamondthink-SKILL.md your-project/.claude/skills/
```

Then in Claude Code:
```
/ultrathink          → auto-select mode
/ultrathink deep     → force 11-technique reasoning
/ultrathink ensemble → force 5-way parallel
/ultrathink mega     → force 10→3→1 architecture
/ultrathink jury     → force investigation protocol
/ultrathink max      → megamind + grand jury combined
```

## Who This Is For

- Engineers using Claude Code who are tired of "guess → patch → fail" loops
- Anyone building agentic systems who needs reliable reasoning
- Developers debugging complex multi-file issues
- People who want their AI to actually think before it acts

## License

MIT — do whatever you want with it.

---

**Built by [@neuralwhisperer](https://x.com/neuralwhisperer)**
