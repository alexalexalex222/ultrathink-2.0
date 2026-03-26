# Benchmark Report

## Run Summary

| Field | Value |
|-------|-------|
| **Date** | YYYY-MM-DD HH:MM UTC |
| **Commit** | `abc1234` |
| **Branch** | `main` |
| **Runner** | CI / Local |
| **Model** | `gpt-4o` / `mock` |
| **Total Duration** | Xs |

---

## Classifier Accuracy

**Benchmark:** `benchmarks/test_classifier_accuracy.py`
**Problems:** 50 labeled problems
**Target:** >95% accuracy

| Metric | Value | Status |
|--------|-------|--------|
| Accuracy | XX.X% | PASS / FAIL |
| Total Problems | 50 | — |
| Correct | N | — |
| Misclassified | N | — |

### Mode Distribution

| Mode | Count | Percentage |
|------|-------|------------|
| RAPID STRIKE | N | XX% |
| DEEP THINK | N | XX% |
| ENSEMBLE | N | XX% |
| MEGAMIND | N | XX% |
| GRAND JURY | N | XX% |

### Misclassifications

| # | Problem | Expected | Actual | Analysis |
|---|---------|----------|--------|----------|
| 1 | [description] | [mode] | [mode] | [why it was wrong] |
| 2 | [description] | [mode] | [mode] | [why it was wrong] |

---

## Deep Think Coverage

**Benchmark:** `benchmarks/test_deep_coverage.py`
**Problems:** 10 medium-complexity problems
**Target:** 11/11 checkpoints per run

| Metric | Value | Status |
|--------|-------|--------|
| Avg Checkpoints Hit | X.X / 11 | PASS / FAIL |
| Min Checkpoints | X | — |
| Max Checkpoints | X | — |
| Technique Ordering Compliance | XX% | PASS / FAIL |

### Confidence Distribution

| Score | Count | Percentage |
|-------|-------|------------|
| 10 | N | XX% |
| 9 | N | XX% |
| 8 | N | XX% |
| 7 | N | XX% |
| 6 | N | XX% |
| 5 | N | XX% |
| <5 | N | XX% |

### Per-Problem Results

| # | Problem | Checkpoints | Confidence | Est. Tokens |
|---|---------|-------------|------------|-------------|
| 1 | [description] | X/11 | X | ~XK |
| 2 | [description] | X/11 | X | ~XK |

---

## Ensemble Parallelism

**Benchmark:** `benchmarks/test_ensemble_parallel.py`
**Problems:** 5 test problems with controversial solutions
**Target:** All 5 angles produce distinct output, total time < 2x single angle

| Metric | Value | Status |
|--------|-------|--------|
| Angle Diversity | XX% (X/5 problems) | PASS / FAIL |
| Parallelism Ratio | X.XXx | PASS / FAIL |
| Conflicts Resolved | XX% | PASS / FAIL |
| Avg Confidence (weighted) | X.X | — |

### Per-Problem Results

| # | Problem | Angles Distinct | Time Ratio | Disagreements Found |
|---|---------|----------------|------------|---------------------|
| 1 | [description] | Yes/No | X.XXx | [list] |
| 2 | [description] | Yes/No | X.XXx | [list] |

---

## Megamind Quality

**Benchmark:** `benchmarks/test_megamind_quality.py`
**Problems:** 3 extreme-complexity problems
**Target:** All 10+3+1 outputs produced, iteration loop works correctly

| Metric | Value | Status |
|--------|-------|--------|
| Architecture Completeness | XX% | PASS / FAIL |
| Iteration Loop Triggered | X/3 problems | — |
| Avg Agreement Level | X/10 aligned | — |
| Conflicts Actually Resolved | XX% | PASS / FAIL |

### Per-Problem Results

| # | Problem | Angle-Explorers | Synthesizers | Iterations | Final Confidence |
|---|---------|-----------------|--------------|------------|------------------|
| 1 | [description] | 10/10 | 3/3 | X | X/10 |
| 2 | [description] | 10/10 | 3/3 | X | X/10 |
| 3 | [description] | 10/10 | 3/3 | X | X/10 |

---

## Grand Jury Evidence Completeness

**Benchmark:** `benchmarks/test_grand_jury_evidence.py`
**Problems:** 3 debugging scenarios with known root causes
**Target:** All 9 phases execute in order, evidence is verbatim

| Metric | Value | Status |
|--------|-------|--------|
| Phase Compliance | XX% | PASS / FAIL |
| Evidence Entries Verbatim | XX% | PASS / FAIL |
| Min Hypotheses (Murder Board) | X (target: 4+) | PASS / FAIL |
| Atomic Change Rule Enforced | Yes/No | PASS / FAIL |
| Root Cause Correct | X/3 problems | — |

### Per-Problem Results

| # | Problem | Phases Completed | Evidence Entries | Hypotheses | Root Cause Match |
|---|---------|-----------------|-----------------|------------|-----------------|
| 1 | [description] | 9/9 | X | X | Yes/No |
| 2 | [description] | 9/9 | X | X | Yes/No |
| 3 | [description] | 9/9 | X | X | Yes/No |

---

## Cross-Mode Consistency

**Benchmark:** `benchmarks/test_cross_mode_consistency.py`
**Problems:** 5 problems run through all 5 modes
**Target:** All modes agree on core issue, confidence is monotonically increasing

| Metric | Value | Status |
|--------|-------|--------|
| Core Problem Agreement | XX% | PASS / FAIL |
| Confidence Monotonicity | XX% | PASS / FAIL |
| Higher Modes Find More Risks | XX% | PASS / FAIL |
| No Contradictions | XX% | PASS / FAIL |

### Per-Problem Results

| # | Problem | RAPID Conf | DEEP Conf | ENSEMBLE Conf | MEGA Conf | JURY Conf | Monotonic |
|---|---------|-----------|-----------|---------------|-----------|-----------|-----------|
| 1 | [description] | X | X | X | X | X | Yes/No |
| 2 | [description] | X | X | X | X | X | Yes/No |
| 3 | [description] | X | X | X | X | X | Yes/No |
| 4 | [description] | X | X | X | X | X | Yes/No |
| 5 | [description] | X | X | X | X | X | Yes/No |

---

## Confidence Calibration

**Benchmark:** `scoring/confidence_calibration.py`
**Problems:** 20 problems with verified correctness
**Target:** ECE < 0.1

| Metric | Value | Status |
|--------|-------|--------|
| Expected Calibration Error (ECE) | X.XXX | PASS / FAIL |
| Brier Score | X.XXX | PASS / FAIL |
| Overconfidence Rate | XX% | — |
| Underconfidence Rate | XX% | — |

### Calibration Curve

```
Confidence │ Actual Accuracy
    10     │ ████████████████████  XX%  (N samples)
     9     │ ████████████████      XX%  (N samples)
     8     │ ████████████          XX%  (N samples)
     7     │ ██████████            XX%  (N samples)
     6     │ ████████              XX%  (N samples)
     5     │ ██████                XX%  (N samples)
     4     │ ████                  XX%  (N samples)
     3     │ ██                    XX%  (N samples)
     2     │ █                     XX%  (N samples)
     1     │                       XX%  (N samples)
           └────────────────────────────────────
             0%   20%   40%   60%   80%  100%
```

### Systematic Biases Detected

| Bias | Description | Severity |
|------|-------------|----------|
| [bias name] | [description] | Low / Medium / High |

---

## Anti-Shortcut Detection

**Benchmark:** `tests/test_anti_shortcut.py`
**Shortcuts Injected:** 8 types
**Target:** 100% detection rate

| # | Shortcut Type | Detected | Notes |
|---|--------------|----------|-------|
| 1 | "I read the file" without excerpt | Yes/No | — |
| 2 | "Architecture is obvious" without citations | Yes/No | — |
| 3 | "I searched" without command/output | Yes/No | — |
| 4 | Big patch touching many things | Yes/No | — |
| 5 | Second try without new evidence | Yes/No | — |
| 6 | Hallucinated file path | Yes/No | — |
| 7 | Premature confidence (8+) | Yes/No | — |
| 8 | Ritual completion | Yes/No | — |

**Detection Rate:** X/8 (XX%)

---

## Real Agent Performance

**Tests:** `tests/test_real_rapid_strike.py`, `tests/test_real_deep_think.py`, `tests/test_real_ensemble.py`

| Mode | Problems | Success Rate | Avg Latency | Avg Confidence |
|------|----------|-------------|-------------|----------------|
| Rapid Strike | 5 | XX% | XXs | X.X |
| Deep Think | 3 | XX% | XXs | X.X |
| Ensemble | 2 | XX% | XXs | X.X |

### Rapid Strike Detail

| # | Problem | Latency | Confidence | Correct | Escalated? |
|---|---------|---------|------------|---------|------------|
| 1 | [description] | Xs | X | Yes/No | Yes/No |
| 2 | [description] | Xs | X | Yes/No | Yes/No |
| 3 | [description] | Xs | X | Yes/No | Yes/No |
| 4 | [description] | Xs | X | Yes/No | Yes/No |
| 5 | [description] | Xs | X | Yes/No | Yes/No |

### Deep Think Detail

| # | Problem | Latency | Checkpoints | Confidence | Depth Score |
|---|---------|---------|-------------|------------|-------------|
| 1 | [description] | Xs | X/11 | X | X.X |
| 2 | [description] | Xs | X/11 | X | X.X |
| 3 | [description] | Xs | X/11 | X | X.X |

### Ensemble Detail

| # | Problem | Latency | Angles Distinct | Disagreements | Synthesis Quality |
|---|---------|---------|-----------------|---------------|-------------------|
| 1 | [description] | Xs | Yes/No | [list] | X/10 |
| 2 | [description] | Xs | Yes/No | [list] | X/10 |

---

## Overall Summary

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Classifier Accuracy | >95% | XX.X% | PASS / FAIL |
| Branch Coverage | 100% | XX% | PASS / FAIL |
| Deep Think Checkpoints | 11/11 | X.X | PASS / FAIL |
| ECE | <0.1 | X.XXX | PASS / FAIL |
| Ensemble Angle Diversity | 100% | XX% | PASS / FAIL |
| Parallelism Efficiency | <2.0x | X.XXx | PASS / FAIL |
| Megamind Completeness | 100% | XX% | PASS / FAIL |
| Grand Jury Phase Compliance | 100% | XX% | PASS / FAIL |
| Cross-Mode Consistency | 100% | XX% | PASS / FAIL |
| Anti-Shortcut Detection | 100% | XX% | PASS / FAIL |
| Rapid Strike Latency | <30s | XXs | PASS / FAIL |
| Deep Think Latency | <120s | XXs | PASS / FAIL |

**Overall: X/12 metrics passing**

---

## Notes

- [Any regressions from previous run]
- [New features tested]
- [Configuration differences from baseline]
- [Known issues or flaky tests]
