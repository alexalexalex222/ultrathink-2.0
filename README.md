# Reasoning Swarm for Claude Code

**Adaptive parallel reasoning skills for Claude Code, with synthesis and max-signal distillation.**

> AI's failure mode isn't "can't reason" — it's pattern completion bias.
> These skills force investigation before reasoning, and reasoning before changes.

![Reasoning Swarm architecture](ultrathink-2.0.png)

## Install (One Command)

```bash
# Creates .claude/skills/ and downloads Reasoning Swarm
mkdir -p .claude/skills && curl -sL https://raw.githubusercontent.com/alexalexalex222/reasoning-swarm/main/skills/reasoning-swarm-SKILL.md -o .claude/skills/reasoning-swarm-SKILL.md
```

**Want all 4 skills?**
```bash
mkdir -p .claude/skills && for f in reasoning-swarm-SKILL.md ultrathink2-SKILL.md deepthink-SKILL.md megamind-SKILL.md diamondthink-SKILL.md; do curl -sL "https://raw.githubusercontent.com/alexalexalex222/reasoning-swarm/main/skills/$f" -o ".claude/skills/$f"; done
```

That's it. Open Claude Code in your project and the skills are live.

---

## The Problem

Every AI coding assistant has the same failure loop:

```
see familiar pattern → stop reading → predict from training data → patch → fail → repeat
```

Reasoning Swarm breaks this loop by forcing structured reasoning *before* the model touches code.

---

## How It Works

Reasoning Swarm auto-classifies any task and selects the right reasoning depth:

| Mode | When | Architecture |
|------|------|-------------|
| **Rapid Strike** | Low stakes, obvious answer | Quick confidence check |
| **Deep Think** | Medium tasks | 11 sequential reasoning techniques |
| **Ensemble** | High complexity | 5-way parallel sub-reasoners |
| **Megamind** | Extreme complexity | 10 angles → 3 synthesizers → 1 decision |
| **Grand Jury** | Debugging / prior failures | Courtroom-standard investigation |

If confidence drops below threshold, it automatically escalates to the next mode.

### Usage
```
/reasoning-swarm          → auto-select mode
/reasoning-swarm deep     → force 11-technique reasoning
/reasoning-swarm ensemble → force 5-way parallel
/reasoning-swarm mega     → force 10→3→1 architecture
/reasoning-swarm jury     → force investigation protocol
/reasoning-swarm distill  → condense parallel outputs into one max-signal pack
/reasoning-swarm max      → megamind + grand jury combined
```

Legacy alias still works:
```text
/ultrathink ...
```

---

## Context Management & Token Costs

This is the real reason Reasoning Swarm exists in skill form instead of hardcoded prompts.

### The Context Problem

Claude Code has a finite context window. Heavy reasoning eats tokens fast. If you run Megamind (10 angle-explorers + 3 synthesizers) in-context, you've burned 50K+ tokens on reasoning alone — leaving less room for your actual codebase.

### How Reasoning Swarm Solves It

**1. Adaptive depth = no wasted tokens**

Most tasks don't need maximum reasoning. Reasoning Swarm's auto-classifier prevents you from burning 50K tokens on a task that only needs 2K. The matrix:

| Mode | Context Cost | When It's Used |
|------|-------------|----------------|
| Rapid Strike | ~2-5K tokens | Quick fixes, obvious answers |
| Deep Think | ~10-20K tokens | Medium complexity, single-file |
| Ensemble | ~20-40K tokens | High complexity, multiple approaches needed |
| Megamind | ~40-80K tokens | Extreme complexity, architecture decisions |
| Grand Jury | Variable (evidence-gated) | Debugging, investigation, prior failures |

**2. Parallel subprocess execution = reasoning without context cost**

Instead of running 10 angle-explorers inside your main context (50K+ tokens), Reasoning Swarm spawns them as separate Claude processes via CLI:

```bash
# 10 parallel reasoners, each in their own context
for i in 1 2 3 4 5 6 7 8 9 10; do
  claude -p "ANGLE $i: [problem]" --model opus > /tmp/ut2-angle$i.md &
done
wait
```

The main context only receives distilled outputs, not the full reasoning traces. This means:

| Method | Context Cost |
|--------|-------------|
| In-context Megamind | **50K+ tokens** (reasoning fills your window) |
| In-context Ensemble | **30K+ tokens** |
| In-context Deep Think | **20K+ tokens** |
| **Subprocess (any mode)** | **~500 tokens** (just the outputs) |

You get the same reasoning depth at 1/100th the context cost.

**3. Distillation layer = portable signal, not raw dump**

When multiple lanes finish, Reasoning Swarm can condense them into a compact max-signal pack:

- recommended path
- compressed reasoning trace
- agreements
- disagreements
- top risks
- strongest dissent
- missing evidence
- next action

That gives the main session the useful reasoning without dragging every intermediate token back in.

**4. Confidence-gated escalation = efficient by default**

Reasoning Swarm starts with the lightest mode that could work. It only escalates when confidence drops below 7. This means 80% of tasks resolve at Rapid Strike or Deep Think cost, and you only pay the full Megamind price when it's genuinely needed.

---

## Skills Included

### 🧠 Reasoning Swarm — The Unified Engine (847 lines)
> [`skills/reasoning-swarm-SKILL.md`](skills/reasoning-swarm-SKILL.md)

The main skill. Auto-classifies, auto-selects depth, auto-escalates. Includes all modes, subprocess execution templates, confidence calibration, and anti-shortcut detection.

### ⚡ Deep Think (166 lines)
> [`skills/deepthink-SKILL.md`](skills/deepthink-SKILL.md)

11 sequential reasoning techniques: Meta-cognition → Step-back → Decomposition → Tree of Thought → First Principles → Analogical Reasoning → Chain of Thought → Devil's Advocate → Inversion → RAVEN Loop → Recursive Self-Improvement. Every checkpoint mandatory.

### 🌀 Megamind (177 lines)
> [`skills/megamind-SKILL.md`](skills/megamind-SKILL.md)

Maximum depth: 10 angle-explorers (performance, security, edge cases, devil's advocate, scalability, beginner's mind, future self, user perspective, constraint breaker, simplicity) → 3 synthesizers (consensus, conflict, risk) → 1 final decision. Loops until confident.

### ⚖️ DiamondThink — Grand Jury (178 lines)
> [`skills/diamondthink-SKILL.md`](skills/diamondthink-SKILL.md)

Courtroom-standard debugging: symptom lock → territory map → assumptions ledger → search pass → evidence ledger (verbatim excerpts + line numbers) → chain-of-custody → murder board (4+ hypotheses with evidence FOR and AGAINST) → pre-flight → one atomic fix. No claim without evidence. No retry without new data.

---

## 1,368 Lines Across 4 Core Skills

Backwards compatibility:
- `skills/ultrathink2-SKILL.md` still exists as the legacy install path.

All MIT licensed. Use them, break them, improve them.

---

**Built by [@neuralwhisperer](https://x.com/neuralwhisperer)**
