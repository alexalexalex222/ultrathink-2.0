---
name: reasoning-swarm
description: "Use when tackling any complex task. Adaptive parallel reasoning for Claude Code: auto-classifies by complexity, stakes, and failure history, then routes to Rapid Strike, Deep Think, Ensemble, Megamind, or Grand Jury. Supports context-efficient parallel subprocess execution and synthesis."
---

# Reasoning Swarm for Claude Code
### by @neuralwhisperer

**One skill to rule them all.**
Auto-classifies any task, selects the optimal reasoning architecture, and executes
with full technique coverage. Supports parallel sub-agent spawning for maximum depth.

Built for Claude Code. Transfers to any model with tool use + system prompts.

---

## Architecture Overview

```
                         ┌──────────────────────┐
                         │  INTAKE CLASSIFIER   │
                         │  (auto-detect mode)  │
                         └──────────┬───────────┘
                                    │
              ┌─────────┬──────────┼──────────┬──────────┐
              ▼          ▼          ▼          ▼          ▼
         ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
         │ RAPID  │ │ DEEP   │ │ENSEMBLE│ │  MEGA  │ │ GRAND  │
         │ STRIKE │ │ THINK  │ │ 5-WAY  │ │  MIND  │ │  JURY  │
         │        │ │        │ │        │ │10→3→1  │ │(invest)│
         └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
              │          │          │          │          │
              └─────────┴──────────┼──────────┴──────────┘
                                   ▼
                         ┌──────────────────────┐
                         │   OUTPUT + VERIFY    │
                         │   confidence gate    │
                         └──────────────────────┘
```

---

## PHASE 0: INTAKE CLASSIFIER

Before ANY reasoning, classify the task. This is mandatory and non-negotiable.

```
┌─ INTAKE ──────────────────────────────────────────────────────────┐
│                                                                   │
│ TASK TYPE:                                                        │
│ □ BUG_FIX    □ IMPLEMENTATION   □ ARCHITECTURE   □ RESEARCH      │
│ □ OPTIMIZE   □ DEBUGGING        □ CREATIVE       □ ANALYSIS      │
│ □ PLANNING   □ INVESTIGATION    □ DESIGN         □ UNKNOWN       │
│                                                                   │
│ COMPLEXITY:  □ LOW   □ MEDIUM   □ HIGH   □ EXTREME               │
│ STAKES:      □ LOW   □ MEDIUM   □ HIGH   □ CRITICAL              │
│ PRIOR FAILS: □ NONE  □ 1       □ 2+                              │
│ FILES INVOLVED: □ 1-2  □ 3-5   □ 6+                              │
│                                                                   │
│ FRAMEWORK/CSS INVOLVED: □ YES  □ NO                               │
│ PRODUCTION SYSTEM:      □ YES  □ NO                               │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### AUTO-SELECT MATRIX

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ CONDITION                                          │ MODE                     │
├────────────────────────────────────────────────────┼──────────────────────────┤
│ LOW complexity + LOW stakes + no prior fails       │ → RAPID STRIKE           │
│ MEDIUM complexity OR MEDIUM stakes                 │ → DEEP THINK             │
│ HIGH complexity OR HIGH stakes                     │ → ENSEMBLE (5-way)       │
│ EXTREME complexity OR CRITICAL stakes OR UNKNOWN   │ → MEGAMIND (10→3→1)      │
│ BUG_FIX/DEBUG + prior fails ≥1                     │ → GRAND JURY (forced)    │
│ BUG_FIX/DEBUG + framework/CSS + multi-file         │ → GRAND JURY (forced)    │
│ INVESTIGATION type (any complexity)                │ → GRAND JURY (forced)    │
│ PRODUCTION + stakes ≥ MEDIUM                       │ → GRAND JURY (forced)    │
└────────────────────────────────────────────────────┴──────────────────────────┘
```

**Override rules:**
- User says "think harder" → escalate one level
- User says "quick" or "just do it" → RAPID STRIKE (unless CRITICAL stakes)
- Any prior failure on this exact task → minimum ENSEMBLE, consider GRAND JURY
- If you catch yourself guessing → escalate immediately

---

## MODE 1: RAPID STRIKE (2-5K tokens)

For straightforward tasks where the answer is likely correct on first pass.

```
┌─ RAPID STRIKE ────────────────────────────────────────────────────┐
│                                                                   │
│ 1. PROBLEM: [one sentence]                                        │
│ 2. OBVIOUS ANSWER: [what pattern-matching says]                   │
│ 3. SANITY CHECK: [one reason this could be wrong]                 │
│ 4. CONFIDENCE: [1-10]                                             │
│                                                                   │
│ If confidence ≥ 8 → execute                                       │
│ If confidence < 8 → escalate to DEEP THINK                        │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## MODE 2: DEEP THINK (10-20K tokens)

All 11 reasoning techniques executed sequentially. No sub-agents.
Full technique coverage for medium-complexity tasks.

### Technique 1: META-COGNITION
```
┌─ META-COGNITION ──────────────────────────────────────────────────┐
│ Problem type: [answer]                                            │
│ Confidence (1-10): [answer]                                       │
│ Uncertainties: [answer]                                           │
│ Am I rushing/lazy/overcomplicating?: [answer]                     │
│ Missing perspective: [answer]                                     │
│ [CHECKPOINT 1]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Technique 2: STEP-BACK
```
┌─ STEP-BACK ───────────────────────────────────────────────────────┐
│ Literal request: [answer]                                         │
│ What user ACTUALLY wants: [answer]                                │
│ WHY they need this: [answer]                                      │
│ What I should ACTUALLY do: [answer]                               │
│ [CHECKPOINT 2]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Technique 3: DECOMPOSITION
```
┌─ DECOMPOSITION ───────────────────────────────────────────────────┐
│ MAIN PROBLEM: [state]                                             │
│ SUB-PROBLEMS:                                                     │
│   1. [sub] → 1.1 [sub-sub]                                        │
│   2. [sub]                                                        │
│   3. [sub]                                                        │
│ DEPENDENCIES: [what before what]                                  │
│ OPTIMAL ORDER: [sequence]                                         │
│ [CHECKPOINT 3]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Technique 4: TREE OF THOUGHT (ToT)
```
┌─ TREE OF THOUGHT ─────────────────────────────────────────────────┐
│ BRANCH A: [approach]                                              │
│   Pros: [list] | Cons: [list] | Verdict: [PURSUE/PRUNE]           │
│ BRANCH B: [approach]                                              │
│   Pros: [list] | Cons: [list] | Verdict: [PURSUE/PRUNE]           │
│ BRANCH C: [approach]                                              │
│   Pros: [list] | Cons: [list] | Verdict: [PURSUE/PRUNE]           │
│ SELECTED: [which + WHY]                                           │
│ [CHECKPOINT 4]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Technique 5: FIRST PRINCIPLES
```
┌─ FIRST PRINCIPLES ────────────────────────────────────────────────┐
│ Assumptions:                                                      │
│   1. [assumption] → [true/convention/false]                       │
│   2. [assumption] → [true/convention/false]                       │
│   3. [assumption] → [true/convention/false]                       │
│ What is FUNDAMENTALLY required: [answer]                          │
│ [CHECKPOINT 5]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Technique 6: ANALOGICAL REASONING
```
┌─ ANALOGICAL ──────────────────────────────────────────────────────┐
│ Abstract pattern: [describe]                                      │
│ Similar solved problems:                                          │
│   1. [similar] → solution: [X]                                    │
│   2. [similar] → solution: [Y]                                    │
│ What transfers / what doesn't: [answer]                           │
│ [CHECKPOINT 6]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Technique 7: CHAIN OF THOUGHT (CoT)
```
┌─ CHAIN OF THOUGHT ────────────────────────────────────────────────┐
│ Step 1: [step] — Why: [reason]                                    │
│ Step 2: [step] — Why: [reason]                                    │
│ Step 3: [step] — Why: [reason]                                    │
│ Step N: [continue until done]                                     │
│ Conclusion: [final answer]                                        │
│ [CHECKPOINT 7]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Technique 8: DEVIL'S ADVOCATE
```
┌─ DEVIL'S ADVOCATE ────────────────────────────────────────────────┐
│ My solution: [state]                                              │
│ ATTACK 1: "Wrong because..." → Defense: [counter]                 │
│ ATTACK 2: "Better approach..." → Defense: [counter or CHANGE]     │
│ ATTACK 3: "Ignoring..." → Defense: [counter]                      │
│ [CHECKPOINT 8]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Technique 9: INVERSION / PRE-MORTEM
```
┌─ INVERSION ───────────────────────────────────────────────────────┐
│ How to GUARANTEE failure:                                         │
│   1. [way] → Prevention: [how]                                    │
│   2. [way] → Prevention: [how]                                    │
│   3. [way] → Prevention: [how]                                    │
│ 1 month later, it failed. Why: [reason]                           │
│ [CHECKPOINT 9]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

### Technique 10: RAVEN LOOP (Reflect → Adapt → Verify → Execute → Navigate)
```
┌─ RAVEN ───────────────────────────────────────────────────────────┐
│ REFLECT: Understanding? Assumptions? Unclear?                     │
│ → [answer]                                                        │
│ ADAPT: What to change based on reflection?                        │
│ → [answer]                                                        │
│ VERIFY: Is adapted approach sound? Provable?                      │
│ → [answer]                                                        │
│ EXECUTE: [action/output]                                          │
│ NAVIGATE: Did it work? Lessons?                                   │
│ → [answer]                                                        │
│ LOOP AGAIN? [yes/no]                                              │
│ [CHECKPOINT 10]                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### Technique 11: RECURSIVE SELF-IMPROVEMENT
```
┌─ IMPROVE ─────────────────────────────────────────────────────────┐
│ DRAFT: [answer]                                                   │
│ CRITIQUE: Weakness 1: [x] | Weakness 2: [y]                       │
│ IMPROVED: [better version]                                        │
│ FINAL CONFIDENCE: [1-10]                                          │
│ [CHECKPOINT 11]                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### DEEP THINK Output
```
🧠 DEEP THINK COMPLETE
Checkpoints Hit: [X/11]
Reasoning Depth: ~[X]K tokens
Confidence: [1-10]
Key Uncertainties: [top 3]
---
[RESPONSE]
```

**Confidence gate:** If confidence < 7, escalate to ENSEMBLE.

---

## MODE 3: ENSEMBLE — 5-Way Parallel Reasoning (20-40K tokens)

Spawn 5 sub-reasoners, each exploring from a different angle.
Each sub-reasoner uses the FULL Deep Think technique stack.

### The 5 Angles

```
┌────┬─────────────────────┬────────────────────────────────────────┐
│ #  │ ANGLE               │ DIRECTIVE                              │
├────┼─────────────────────┼────────────────────────────────────────┤
│ 1  │ PERFORMANCE         │ Optimize for speed/efficiency          │
│ 2  │ SIMPLICITY          │ Optimize for maintainability           │
│ 3  │ SECURITY            │ Optimize for safety/security           │
│ 4  │ EDGE CASES          │ Find what breaks                       │
│ 5  │ DEVIL'S ADVOCATE    │ Why is the obvious answer WRONG?       │
└────┴─────────────────────┴────────────────────────────────────────┘
```

### Execution (Parallel via Task/Subprocess)

```bash
# PARALLEL EXECUTION — spawn 5 separate reasoning processes
claude -p "ANGLE: PERFORMANCE. [problem + context]. Use full reasoning. Return: reasoning summary (3-5 sentences with evidence), concrete recommendation with tradeoffs, confidence (1-10), key risks, and dissenting considerations." > /tmp/ut2-angle1.md &
claude -p "ANGLE: SIMPLICITY. [problem + context]. ..." > /tmp/ut2-angle2.md &
claude -p "ANGLE: SECURITY. [problem + context]. ..." > /tmp/ut2-angle3.md &
claude -p "ANGLE: EDGE CASES. [problem + context]. ..." > /tmp/ut2-angle4.md &
claude -p "ANGLE: DEVIL'S ADVOCATE. [problem + context]. ..." > /tmp/ut2-angle5.md &
wait
```

### Collection
```
┌────┬─────────────────┬────────────┬─────────────────────────────┐
│ #  │ ANGLE           │ CONFIDENCE │ CONCLUSION                  │
├────┼─────────────────┼────────────┼─────────────────────────────┤
│ 1  │ Performance     │ [N]        │ [summary]                   │
│ 2  │ Simplicity      │ [N]        │ [summary]                   │
│ 3  │ Security        │ [N]        │ [summary]                   │
│ 4  │ Edge Cases      │ [N]        │ [summary]                   │
│ 5  │ Devil's Adv     │ [N]        │ [summary]                   │
└────┴─────────────────┴────────────┴─────────────────────────────┘
```

### Synthesis
```
┌─ SYNTHESIS ───────────────────────────────────────────────────────┐
│ AGREEMENT: What do most angles agree on? → [answer]               │
│ DISAGREEMENT: Where do they differ? → [answer]                    │
│ RESOLUTION: How to resolve conflicts? → [answer]                  │
│ RISKS: From security + edge case angles → [answer]                │
│ DEVIL'S CONCERNS: Valid or dismissed? → [answer]                  │
└───────────────────────────────────────────────────────────────────┘
```

### ENSEMBLE Output
```
🧠 ENSEMBLE COMPLETE
Sub-Reasoners: 5
Agreement Level: [X/5 agree]
Confidence: [weighted average]
Key Conflicts Resolved: [list]
---
[SYNTHESIZED RESPONSE]
```

**Confidence gate:** If confidence < 7, escalate to MEGAMIND.

---

## MODE 4: MEGAMIND — 10→3→1 Ultra-Meta Reasoning (40-80K tokens)

Maximum reasoning depth. 10 angle-explorers → 3 synthesizers → 1 final reasoner.
Can iterate up to 3 times until confident.

### Phase M1: Initial Pass
Execute full DEEP THINK (all 11 techniques) to establish baseline.
```
Preliminary Answer: [X]
Confidence: [N/10]
→ If confidence ≥ 9: output directly
→ If confidence < 9: proceed to Phase M2
```

### Phase M2: Spawn 10 Angle-Explorers (Parallel)

```
┌────┬─────────────────────┬────────────────────────────────────────┐
│ #  │ ANGLE               │ DIRECTIVE                              │
├────┼─────────────────────┼────────────────────────────────────────┤
│ 1  │ PERFORMANCE         │ Optimize for speed/efficiency          │
│ 2  │ SIMPLICITY          │ Optimize for maintainability           │
│ 3  │ SECURITY            │ Optimize for safety/security           │
│ 4  │ SCALABILITY         │ What if this scales 100x?              │
│ 5  │ EDGE CASES          │ Find what breaks                       │
│ 6  │ DEVIL'S ADVOCATE    │ Why is the obvious answer WRONG?       │
│ 7  │ BEGINNER'S MIND     │ What's actually confusing here?        │
│ 8  │ FUTURE SELF         │ What will we regret in 6 months?       │
│ 9  │ USER PERSPECTIVE    │ What does the end user actually need?  │
│ 10 │ CONSTRAINT BREAKER  │ What if we removed a key constraint?   │
└────┴─────────────────────┴────────────────────────────────────────┘
```

```bash
# PARALLEL EXECUTION — 10 angle-explorers
for i in 1 2 3 4 5 6 7 8 9 10; do
  claude -p "ANGLE $i: [DIRECTIVE]. [problem + context]. Full reasoning. Return: reasoning summary (3-5 sentences with evidence), concrete recommendation with tradeoffs, confidence (1-10), key risks, dissenting considerations, and follow-up flag if confidence < 7." \
    --model opus > /tmp/ut2-mega-angle$i.md 2>/dev/null &
done
wait
```

### Phase M3: Spawn 3 Synthesizers (Parallel)

Each receives ALL 10 angle outputs.

```bash
# Feed all 10 outputs to 3 synthesizers
ALL_ANGLES=$(cat /tmp/ut2-mega-angle*.md)

claude -p "SYNTHESIZER A: CONSENSUS. Find what most angles agree on. $ALL_ANGLES" \
  --model opus > /tmp/ut2-synth-a.md 2>/dev/null &
claude -p "SYNTHESIZER B: CONFLICT. Identify disagreements and root causes. $ALL_ANGLES" \
  --model opus > /tmp/ut2-synth-b.md 2>/dev/null &
claude -p "SYNTHESIZER C: RISK. Assess worst-case scenarios. $ALL_ANGLES" \
  --model opus > /tmp/ut2-synth-c.md 2>/dev/null &
wait
```

**Synthesizer A (Consensus):** majority position, agreement level, what 7+ agree on
**Synthesizer B (Conflict):** key conflicts, root causes, resolutions
**Synthesizer C (Risk):** scariest risks, worst case, minimum safe answer

### Phase M4: Final Synthesis + Confidence Gate

```
┌─ FINAL SYNTHESIS ─────────────────────────────────────────────────┐
│ SYNTH A says: [consensus view]                                    │
│ SYNTH B says: [conflict analysis]                                 │
│ SYNTH C says: [risk assessment]                                   │
│                                                                   │
│ INTEGRATION:                                                      │
│ - Consensus answer: [X]                                           │
│ - Modified by conflicts: [adjustments]                            │
│ - Risk mitigations added: [safeguards]                            │
│                                                                   │
│ CONFIDENCE: [1-10]                                                │
│ → If < 7: LOOP TO PHASE M2 (max 3 iterations)                    │
│ → If ≥ 7: output                                                  │
└───────────────────────────────────────────────────────────────────┘
```

### MEGAMIND Output
```
🧠 MEGAMIND COMPLETE
Architecture: 10 → 3 → 1
Iterations: [N]
Agreement Level: [X/10 aligned]
Conflicts Resolved: [list]
Risks Mitigated: [list]
Final Confidence: [1-10]
---
[FINAL SYNTHESIZED RESPONSE]
```

---

## MODE 5: GRAND JURY — Investigation Protocol (Variable, Evidence-Gated)

For debugging, investigation, and any task that has failed before.
Enforces investigation BEFORE reasoning, reasoning BEFORE changes.

### Why This Mode Exists

The core AI failure mode is **Pattern Completion Bias**:
- See familiar framework → stop reading → start predicting from training data
- Fill checklists with *expected* facts instead of *verified* facts
- Multi-part patches that "seem plausible" → iterate by guessing

Grand Jury converts passive checklists into **active interrogation**.

### Non-Negotiables
1. No solution before Pre-Flight (GJ-7) is complete
2. No claim without Evidence IDs (E#)
3. Evidence = verbatim excerpt + line numbers or raw command output
4. Training-data knowledge is **SUSPECT** until verified against this repo
5. Prove at least one negative ("No file defines X")
6. One attempt = one atomic change
7. If verification is blocked → stop and ask for artifacts
8. Fix fails → Failure Recovery Protocol (≥2 new evidence entries first)
9. No hallucinated file paths (prove existence)

### Phase GJ-0: Commitment
```
┌─ COMMITMENT ──────────────────────────────────────────────────────┐
│ Repo root: [path]                                                 │
│ Available tools: [search, read, shell, browser, tests]            │
│ Constraints: [read-only? do-not-edit? time?]                      │
│ Can verify directly: [list]                                       │
│ Cannot verify: [list]                                             │
│                                                                   │
│ PLEDGE: "I will not propose a fix until Pre-Flight (GJ-7) is     │
│ complete and supported by Evidence IDs."                           │
└───────────────────────────────────────────────────────────────────┘
```

### Phase GJ-1: Symptom Record (NO file reads yet)
```
┌─ SYMPTOM RECORD ──────────────────────────────────────────────────┐
│ Reported (verbatim): "..."                                        │
│ Expected: [behavior]                                              │
│ Actual: [behavior]                                                │
│ Severity / blast radius: [assessment]                             │
│ Success criteria: [how we know it's fixed]                        │
│ Non-goals: [what we will NOT change]                              │
└───────────────────────────────────────────────────────────────────┘
```

### Phase GJ-1.5: Territory Map
```
┌─ TERRITORY MAP ───────────────────────────────────────────────────┐
│ Framework/build system: [from actual files, not assumptions] (E#) │
│ Key directories: [list] (E#)                                      │
│ Source vs generated: [suspicion list]                              │
│ Black boxes (cannot see): [list]                                  │
│                                                                   │
│ For each file to modify:                                          │
│ - Is it source or generated?                                      │
│ - What process overwrites it?                                     │
│ - How does the change reach runtime?                              │
└───────────────────────────────────────────────────────────────────┘
```

### Phase GJ-2: Assumptions Ledger

| A# | Statement | Category | Confidence | Status | How to verify |
|----|-----------|----------|-----------|--------|---------------|
| A1 | [claim] | TDK/PC | [0-100%] | UNVERIFIED | [method] |

- **TDK** = Training-Data Knowledge (SUSPECT by default)
- **PC** = Project-Context Knowledge (from actual repo)
- Any assumption <90% confidence → cannot influence fix plan until verified

### Phase GJ-3: Search Pass (MANDATORY before reading)

| S# | Command | Key hits | What it narrows |
|----|---------|----------|-----------------|
| S1 | `rg -n "[term]" .` | path:line | [insight] |

**Negative Search Rule:** Claiming "X doesn't exist" requires a search showing zero hits.

### Phase GJ-4: Evidence Ledger

| E# | Source | Lines | Excerpt (verbatim) | What it proves | Quality |
|----|--------|-------|--------------------|----------------|---------|
| E1 | path | L-L | `...` | ... | VERIFIED/CALCULATED |

- Excerpts: verbatim, 2-12 lines, no `...` ellipses
- Every file "read" must contribute ≥1 evidence entry
- INFERRED allowed only in hypotheses, never in root cause

### Phase GJ-5: Chain-of-Custody (Static → Runtime)

**CSS/UI chain:** Markup → CSS rule → Load order → Cascade/specificity → Runtime computed style
**JS chain:** Trigger → Handler → Network → Response → UI update
**Build chain:** Source → Pipeline → Output artifact

Each link must cite Evidence IDs. Missing links → gather more evidence.

### Phase GJ-6: The Murder Board (≥4 Hypotheses)

| H# | Hypothesis | Evidence FOR | Evidence AGAINST | Differentiator test | Status |
|----|-----------|-------------|-----------------|--------------------|----|
| H1 | Primary Suspect | E#,E# | E# | [test] | CONFIRMED/DISPROVED |
| H2 | Challenger | E# | E# | [test] | ... |
| H3 | Null Hypothesis | E# | E# | [test] | ... |
| H4 | "My model is wrong" | — | — | [test] | ... |

- Every hypothesis needs evidence FOR and AGAINST
- CONFIRMED requires VERIFIED evidence + elimination of alternatives
- No confirmation bias allowed

### Phase GJ-7: Pre-Flight Checklist

```
┌─ PRE-FLIGHT ──────────────────────────────────────────────────────┐
│ 1. Files read (each with E#): [list]                              │
│ 2. Root cause (one sentence, NO hedging) + E#: [statement]        │
│ 3. Eliminated hypotheses: H# DISPROVED because [reason] (E#)     │
│ 4. Atomic fix plan: [one change] — works because: [reason] (E#)  │
│ 5. Risks + detection: [risk] → detect by [method]                │
│ 6. Verification plan: [exact commands + runtime check]            │
│                                                                   │
│ GATE: If any item lacks evidence → RETURN TO SEARCH/READ/MURDER  │
└───────────────────────────────────────────────────────────────────┘
```

### Phase GJ-8: Atomic Change + Verify

1. Make ONE logical fix
2. Execute verification plan from GJ-7
3. If FAIL → Failure Recovery Protocol:
   - Add ≥2 new evidence entries
   - Update hypothesis table
   - Re-run Murder Board
   - New Pre-Flight before retry

### GRAND JURY Output
```
⚖️ GRAND JURY COMPLETE
Evidence Entries: [N]
Hypotheses Tested: [N]
Root Cause: [one sentence]
Fix: [atomic change description]
Verification: [PASS/FAIL + evidence]
Post-Mortem: [most dangerous assumption + turning point evidence]
```

---

## SUBPROCESS EXECUTION (Parallel Agentic Reasoning)

For ENSEMBLE and MEGAMIND modes, use subprocess spawning to avoid context bloat.

### Why Subprocess?

| Method | Context Cost |
|--------|-------------|
| In-context MEGAMIND | 50K+ tokens |
| In-context DEEP THINK | 20K+ tokens |
| In-context ENSEMBLE | 30K+ tokens |
| **Subprocess (any)** | **500-1,500 tokens** (distilled output) |

### Subprocess Template

```bash
claude -p "[MODE]: [PROBLEM STATEMENT]

CONTEXT:
[paste relevant context, code, errors]

RETURN FORMAT (aim for 500-1500 tokens — preserve signal, not just conclusions):
1. Reasoning summary (3-5 sentences explaining HOW you reached your conclusion, with specific evidence cited)
2. Concrete recommendation with tradeoffs (what you'd do and what you'd sacrifice)
3. Confidence (1-10) with calibration note
4. Key risks or uncertainties (be specific — name files, functions, edge cases)
5. Dissenting considerations (what a reasonable person might disagree with)
6. Follow-up flag: does this need deeper investigation? (yes/no + why)" \
  --model opus \
  --dangerously-skip-permissions \
  2>/dev/null | tee /tmp/ut2-result.md
```

> **Why 500-1500 instead of ~500?** At ~500 tokens the subprocess outputs were over-compressed — conclusions without reasoning traces, one-line insights that lost the "why." The synthesizer needs enough signal to detect genuine disagreements between angles, not just surface-level conclusion differences. 1500 tokens per subprocess × 10 angles = 15K tokens to the synthesizer, which is still 3x cheaper than in-context MEGAMIND (50K+).

### Parallel Multi-Mode Consensus

For maximum confidence on critical decisions, run multiple modes simultaneously:

```bash
# Triple-mode parallel consensus
claude -p "DEEP THINK: [problem]" --model opus > /tmp/ut2-deep.md 2>/dev/null &
claude -p "ENSEMBLE: [problem]" --model opus > /tmp/ut2-ensemble.md 2>/dev/null &
claude -p "MEGAMIND: [problem]" --model opus > /tmp/ut2-mega.md 2>/dev/null &
wait

# Compare all three
echo "=== DEEP ===" && cat /tmp/ut2-deep.md
echo "=== ENSEMBLE ===" && cat /tmp/ut2-ensemble.md
echo "=== MEGA ===" && cat /tmp/ut2-mega.md
```

Then synthesize the three outputs yourself for ultimate confidence.

---

## ESCALATION + DE-ESCALATION RULES

### Auto-Escalate When:
- Confidence drops below 7 at any stage
- You catch yourself writing "probably" or "likely" about root cause
- You're about to make a second attempt without new evidence
- The task involves CSS/framework + multiple files
- You realize you're pattern-matching from training data

### De-Escalate When:
- Confidence hits 9+ and task is clearly scoped
- User explicitly requests speed over depth
- The fix is a known, verified pattern with zero ambiguity

### Escalation Path
```
RAPID STRIKE → DEEP THINK → ENSEMBLE → MEGAMIND → GRAND JURY
     ↑              ↑            ↑           ↑          ↑
  conf<8         conf<7       conf<7      conf<7    prior fail
```

---

## CONFIDENCE CALIBRATION

Your confidence score must be honest. Here's how to calibrate:

| Score | Meaning | Evidence Requirement |
|-------|---------|---------------------|
| 10 | Mathematically certain | Formal proof or deterministic output |
| 9 | Virtually certain | Multiple verified evidence sources agree |
| 8 | High confidence | Verified evidence supports, no contradictions found |
| 7 | Confident | Evidence supports, minor uncertainties remain |
| 6 | Likely correct | More evidence for than against, gaps exist |
| 5 | Coin flip | Equal evidence for and against |
| 4 | Uncertain | More gaps than evidence |
| 3 | Probably wrong | Significant contradictions |
| 2 | Likely wrong | Multiple evidence sources contradict |
| 1 | Almost certainly wrong | Making this up |

**If you rate yourself 8+ and turn out wrong, you calibrated badly.**
**If you rate yourself 5 and execute anyway without escalating, you violated protocol.**

---

## ANTI-SHORTCUT DETECTION

These are the ways AI tries to fake compliance. Reasoning Swarm blocks each one:

| Shortcut | Tell | Blocker |
|----------|------|---------|
| "I read the file" (didn't quote) | No verbatim excerpt | Per-file proof in Evidence Ledger |
| "Architecture is obvious" | Framework claims without citations | TDK = SUSPECT |
| "I searched" (didn't record) | No command/output shown | Search Ledger |
| Big patch to hide uncertainty | Touches many things "just in case" | Atomic change rule |
| Second try without learning | New patch, no new evidence | FRP: ≥2 new evidence entries |
| Hallucinated file path | Mentions file with no proof | File existence rule |
| Premature confidence | Rates 8+ without verification | Calibration table |
| Ritual completion | Fills templates without doing work | Evidence ID requirements |

---

## UNIFIED OUTPUT FORMAT

```
🧠 REASONING SWARM COMPLETE
╔═══════════════════════════════════════╗
║ Mode: [RAPID/DEEP/ENSEMBLE/MEGA/JURY]║
║ Escalations: [N]                      ║
║ Techniques Used: [list]               ║
║ Evidence Entries: [N] (if GRAND JURY) ║
║ Subprocess Calls: [N]                 ║
║ Final Confidence: [1-10]              ║
║ Key Uncertainties: [top 3]            ║
╠═══════════════════════════════════════╣
║ [RESPONSE]                            ║
╚═══════════════════════════════════════╝
```

---

## QUICK REFERENCE CARD

```
/reasoning-swarm          → auto-select mode based on task
/reasoning-swarm rapid    → force RAPID STRIKE
/reasoning-swarm deep     → force DEEP THINK (11 techniques)
/reasoning-swarm ensemble → force ENSEMBLE (5-way parallel)
/reasoning-swarm mega     → force MEGAMIND (10→3→1)
/reasoning-swarm jury     → force GRAND JURY (investigation)
/reasoning-swarm max      → MEGAMIND + GRAND JURY combined
/reasoning-swarm harder   → escalate current mode by one level

Legacy alias:
/ultrathink ...
```

---

**REASONING SWARM ACTIVATED. Beginning Phase 0: Intake Classification.**
