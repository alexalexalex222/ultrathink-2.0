---
name: diamondthink
description: "Use for debugging, investigation, and any task that has previously failed. Enforces courtroom-standard evidence requirements: verbatim excerpts with line numbers, assumptions ledger with training-data flagging, murder board with competing hypotheses, chain-of-custody from source to runtime, and atomic single-fix changes."
---

# DiamondThink Protocol — Grand Jury Edition
### by @neuralwhisperer

**Purpose:** Enforce investigation BEFORE reasoning, and reasoning BEFORE changes.
Prevent "read 2 files → guess → patch → fail" loops by making shortcuts detectable and disallowed.

Built for Claude Code / Opus 4.5. Transfers to any high-skill assistant.

---

## The Core Failure Mode (What This Fixes)

Claude's recurring failure pattern is not "can't reason" — it is **Pattern Completion Bias**:
- It sees a familiar framework (React / Next.js / Express / Shopify)
- It stops reading and starts *predicting* based on training-data averages
- It fills checklists with *expected* facts instead of verified facts
- It makes multi-part patches that "seem plausible", then iterates by guessing

**DiamondThink** converts passive checklists into **active interrogation**:
- Claims must survive a **courtroom standard** ("admissible evidence" only)
- Hypotheses must survive a **Murder Board** ("devil's advocate" required)
- Changes must be **atomic** (one logical fix per attempt)

---

## Non-Negotiables (Anti-Circumvention Rules)

1. **No solution before Pre-Flight is complete.** You may not propose a fix until Phase 7 passes.
2. **No claim without Evidence IDs (E#).** If it can't cite an E#, it's not a fact.
3. **Evidence = verbatim excerpt + line numbers or raw command output.** Summaries are not evidence.
4. **Training-data knowledge is SUSPECT until verified** against the actual repo.
5. **Prove at least one negative.** ("No file defines X", "This CSS is not loaded")
6. **One attempt = one atomic change.** No "while I'm here" refactors.
7. **If verification is blocked, stop and ask for artifacts.** Guessing is forbidden.
8. **If a fix fails → Failure Recovery Protocol.** ≥2 new evidence entries before second attempt.
9. **No hallucinated files.** Prove it exists (ls/find/rg output or read excerpt).

---

## Definitions

### "Atomic change"
One logical fix. Not "one file" — one intention.
- ✅ "Switch `/cart/add` → `/cart/add.js` so response is JSON"
- ❌ "Fix add-to-cart + refactor drawer + remove console logs"

### "Evidence" (admissible)
- Verbatim code excerpt with line numbers (E#)
- Raw command output (E#)
- Runtime artifact — screenshot, computed styles, network trace (E#)
- Calculated value from verified inputs (E#)

NOT evidence: "I checked it", "It's standard", "It should"

---

## Strictness Levels

| Level | When | Evidence Min | Hypotheses Min |
|-------|------|-------------|----------------|
| 1 (Practical) | Small scoped tasks | ≥4 entries | ≥2 |
| 2 (Full) | Normal bugfixes | ≥8 entries | ≥3 |
| 3 (Grand Jury) | CSS/framework/multi-file/prior failure | ≥12 entries | ≥4 (Murder Board) |

**Hard override:** CSS, framework-specific, multi-file, security, deployment, or already failed once → strictness 3.

---

## The 8 Phases

### Phase 0 — Commitment
State: repo root, available tools, constraints, what you can/cannot verify.
Pledge: "I will not propose a fix until Pre-Flight (Phase 7) is complete."

### Phase 1 — Symptom Record (No file reads yet)
Lock the problem statement before investigating.
- User quote (exact words)
- Expected vs Actual
- Severity / blast radius
- Success criteria
- Non-goals

### Phase 1.5 — Territory Map
Stop hallucinated paths and source/output confusion.
- Repo type (from actual files, not assumptions)
- Source vs generated directories
- Verify existence of every file you plan to read/edit
- Origin check: is it source or generated? What process overwrites it?

### Phase 2 — Assumptions Ledger
Surface assumptions Claude doesn't realize it's making.

| A# | Statement | Category (Training-Data / Project-Context) | Confidence | Status | How to verify |
|----|----------|-------------------------------------------|-----------|--------|---------------|
| A1 | "Dawn uses Grid" | Training-Data | 70% | UNVERIFIED | search component CSS |

Any assumption <90% confidence cannot influence fix plan until verified.

### Phase 3 — Search Pass (MANDATORY before reading)
Repo-wide searches for exact error strings, selectors, function names, endpoints.

| S# | Command | Key hits | What it narrows |
|----|---------|----------|-----------------|
| S1 | `rg -n "Error adding" .` | path:line | finds where thrown |

**Negative Search Rule:** If you claim "X doesn't exist", show a negative search with zero hits.

### Phase 4 — Read Pass + Evidence Ledger

| E# | Source | Lines | Excerpt (verbatim) | What it proves | Quality |
|----|--------|-------|--------------------|----------------|---------|
| E1 | path/to/file | L10-18 | `...` | ... | VERIFIED |

Every file claimed "read" must contribute ≥1 evidence entry.

### Phase 5 — Chain-of-Custody (Static → Runtime)

Prove the chain from source to runtime:

**CSS/UI chain:**
1. Markup: class exists on element (E#)
2. CSS: rule exists (E#)
3. Load order: stylesheet loaded on failing page (E#)
4. Cascade: specificity winner (E#)
5. Runtime: computed style (E#)

**JS chain:**
1. Trigger → Handler → Network → Response → UI update (each with E#)

### Phase 6 — The Murder Board

| H# | Hypothesis | Evidence FOR | Evidence AGAINST | Differentiator test | Status |
|----|-----------|-------------|-----------------|--------------------|----|
| H1 | Primary Suspect | E1,E2 | E3 | run/read... | CONFIRMED |
| H2 | Challenger | E4 | E1 | ... | DISPROVED |
| H3 | Null | E5 | E2 | ... | UNCERTAIN |
| H4 | "My model is wrong" | — | — | ... | UNCERTAIN |

Every hypothesis needs evidence FOR and AGAINST. No confirmation bias.

### Phase 7 — Pre-Flight Checklist

1. Files read (each with E#)
2. Root cause (one sentence, no hedging) + E#
3. Eliminated hypotheses + why
4. Atomic fix plan + why it works (E#)
5. Risk analysis + detection strategy
6. Verification plan (exact commands + runtime check)

**Gate:** If any item lacks evidence support, go back.

### Phase 8 — Atomic Change + Verify

1. Make ONE logical change
2. Execute verification plan
3. If it fails → Failure Recovery Protocol (≥2 new evidence entries before retry)

---

## Known Shortcut Attempts (And How DiamondThink Blocks Them)

| Shortcut | Tell | Blocker |
|----------|------|---------|
| "I read the file" (didn't quote it) | No verbatim excerpt | Per-file proof requirement |
| "Architecture is obvious" | Framework claims without citations | Training-data = SUSPECT |
| "I searched" (didn't record it) | "Couldn't find..." with no command | Search Ledger |
| Big patch to cover uncertainty | Touches many things "just in case" | Atomic change rule |
| Second try without learning | Another tweak, no new evidence | FRP: ≥2 new evidence entries |
| Hallucinated file path | Mentions config with no proof | File existence rule |

---

**DiamondThink activated. Beginning Phase 0: Commitment.**
