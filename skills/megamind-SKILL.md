---
name: megamind
description: "Use for maximum reasoning depth on extreme complexity tasks. Spawns 10 angle-explorers (performance, simplicity, security, scalability, edge cases, devil's advocate, beginner's mind, future self, user perspective, constraint breaker), feeds outputs to 3 synthesizers (consensus, conflict, risk), then integrates into one final decision. Loops until confident."
---

# MEGAMIND — Ultra-Meta Reasoning Protocol
### by @neuralwhisperer

Maximum reasoning depth. 10 angle-explorers → 3 synthesizers → main reasoner.
Can iterate multiple times until confident.
Built for Claude Code / Opus. Transfers to any model.

---

## Architecture
```
                    ┌─────────────────────┐
                    │   MAIN REASONER     │
                    │  (Full techniques)  │
                    └──────────┬──────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
   ┌───────────┐         ┌───────────┐         ┌───────────┐
   │ ANGLE 1-4 │   ...   │ ANGLE 5-7 │   ...   │ ANGLE 8-10│
   └─────┬─────┘         └─────┬─────┘         └─────┬─────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                    [ALL 10 OUTPUTS]
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
   ┌───────────┐         ┌───────────┐         ┌───────────┐
   │ SYNTH A   │         │ SYNTH B   │         │ SYNTH C   │
   │ Consensus │         │ Conflict  │         │ Risk      │
   └─────┬─────┘         └─────┬─────┘         └─────┬─────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   MAIN REASONER     │
                    │  Compare + Decide   │
                    │  Loop if needed     │
                    └─────────────────────┘
```

---

## Phase 0: Problem Definition
```
┌─ PROBLEM ─────────────────────────────────────────────────────────┐
│ STATEMENT: [clear problem statement]                              │
│ CONTEXT: [background, constraints, requirements]                  │
│ SUCCESS CRITERIA: [how do we know we solved it]                   │
│ STAKES: [what happens if we get this wrong]                       │
└───────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Main Reasoner — Initial Pass
Execute full reasoning protocol (all techniques from DeepThink).
This establishes baseline understanding before spawning sub-reasoners.
```
[INITIAL REASONING COMPLETE]
Preliminary Answer: [X]
Confidence: [N/10]
Proceed to Phase 2 if confidence < 9
```

---

## Phase 2: Spawn 10 Angle-Explorers
Each angle uses full reasoning but from a specific perspective.

```
┌────┬─────────────────────┬────────────────────────────────────────┐
│ #  │ ANGLE               │ DIRECTIVE                              │
├────┼─────────────────────┼────────────────────────────────────────┤
│ 1  │ PERFORMANCE         │ Optimize for speed/efficiency          │
│ 2  │ SIMPLICITY          │ Optimize for maintainability           │
│ 3  │ SECURITY            │ Optimize for safety/security           │
│ 4  │ SCALABILITY         │ What if this scales 100x?              │
│ 5  │ EDGE CASES          │ Find what breaks                       │
│ 6  │ DEVIL'S ADVOCATE    │ Why is obvious answer WRONG?           │
│ 7  │ BEGINNER'S MIND     │ What's actually confusing here?        │
│ 8  │ FUTURE SELF         │ What will we regret in 6 months?       │
│ 9  │ USER PERSPECTIVE    │ What does end user actually need?      │
│ 10 │ CONSTRAINT BREAKER  │ What if we removed key constraint?     │
└────┴─────────────────────┴────────────────────────────────────────┘
```

Each returns: Conclusion, Confidence, Key Insight, Concerns

---

## Phase 3: Spawn 3 Synthesizers
Each synthesizer receives ALL 10 angle outputs.

### Synthesizer A: Consensus Builder
- Find what most angles agree on
- Confidence based on agreement level
- What 7+ angles agree on vs what's split

### Synthesizer B: Conflict Analyzer
- Identify and analyze disagreements
- Root cause of each disagreement
- Which conflicts matter most
- Recommended resolution for each

### Synthesizer C: Risk Assessor
- Scariest risks identified across all angles
- Worst case if we're wrong
- Minimum viable safe answer
- What must be true for main answer to be safe

---

## Phase 4: Main Reasoner — Final Synthesis
```
┌─ FINAL SYNTHESIS ─────────────────────────────────────────────────┐
│                                                                   │
│ SYNTH A says: [consensus view]                                    │
│ SYNTH B says: [conflict analysis]                                 │
│ SYNTH C says: [risk assessment]                                   │
│                                                                   │
│ INTEGRATION:                                                      │
│ - Consensus answer: [X]                                           │
│ - Modified by conflicts: [adjustments]                            │
│ - Risk mitigations added: [safeguards]                            │
│                                                                   │
│ CONFIDENCE CHECK: [1-10]                                          │
│                                                                   │
│ If confidence < 7: LOOP BACK TO PHASE 2 with refined question     │
│ Max iterations: 3                                                 │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## Phase 5: Output
```
🧠 MEGAMIND COMPLETE
Architecture: 10 → 3 → 1
Iterations: [N]
Agreement Level: [X/10 angles aligned]
Conflicts Resolved: [list]
Risks Mitigated: [list]
Final Confidence: [1-10]
Key Uncertainties:
1. [uncertainty]
2. [uncertainty]
3. [uncertainty]
---
[FINAL SYNTHESIZED RESPONSE]
---
REASONING TRACE AVAILABLE:
- 10 angle analyses
- 3 synthesizer reports
- Main reasoner integration notes
```

---

## Iteration Rules
- Loop if confidence < 7 after Phase 4
- Maximum 3 iterations
- Each iteration refines the question based on learnings
- If still < 7 after 3 iterations, output with explicit uncertainty flags

---

**MEGAMIND ACTIVATED. Beginning Phase 0: Problem Definition.**
