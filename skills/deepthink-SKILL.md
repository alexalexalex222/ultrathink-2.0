---
name: deepthink
description: "Use when you need thorough sequential reasoning. Forces 11 reasoning techniques in order: meta-cognition, step-back, decomposition, tree of thought, first principles, analogical reasoning, chain of thought, devil's advocate, inversion, RAVEN loop, and recursive self-improvement."
---

# DEEPTHINK — Full Reasoning Protocol
### by @neuralwhisperer

Force all 11 reasoning techniques sequentially. No shortcuts. No sub-agents.
Built for Claude Code / Opus. Transfers to any model with system prompts.

---

## 1. META-COGNITION
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

## 2. STEP-BACK
```
┌─ STEP-BACK ───────────────────────────────────────────────────────┐
│ Literal request: [answer]                                         │
│ What user ACTUALLY wants: [answer]                                │
│ WHY they need this: [answer]                                      │
│ What I should ACTUALLY do: [answer]                               │
│ [CHECKPOINT 2]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

## 3. DECOMPOSITION
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

## 4. TREE OF THOUGHT
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

## 5. FIRST PRINCIPLES
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

## 6. ANALOGICAL REASONING
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

## 7. CHAIN OF THOUGHT
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

## 8. DEVIL'S ADVOCATE
```
┌─ DEVIL'S ADVOCATE ────────────────────────────────────────────────┐
│ My solution: [state]                                              │
│ ATTACK 1: "Wrong because..." → Defense: [counter]                 │
│ ATTACK 2: "Better approach..." → Defense: [counter or CHANGE]     │
│ ATTACK 3: "Ignoring..." → Defense: [counter]                      │
│ [CHECKPOINT 8]                                                    │
└───────────────────────────────────────────────────────────────────┘
```

## 9. INVERSION / PRE-MORTEM
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

## 10. RAVEN LOOP
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

## 11. RECURSIVE SELF-IMPROVEMENT
```
┌─ IMPROVE ─────────────────────────────────────────────────────────┐
│ DRAFT: [answer]                                                   │
│ CRITIQUE: Weakness 1: [x] | Weakness 2: [y]                       │
│ IMPROVED: [better version]                                        │
│ FINAL CONFIDENCE: [1-10]                                          │
└───────────────────────────────────────────────────────────────────┘
```

---

## Output Format
```
🧠 DEEPTHINK COMPLETE
Checkpoints Hit: [X/10]
Reasoning Depth: ~[X]K tokens
Confidence: [1-10]
Key Uncertainties: [top 3]
---
[RESPONSE]
```

---

**DEEPTHINK ACTIVE. Beginning meta-cognition.**
