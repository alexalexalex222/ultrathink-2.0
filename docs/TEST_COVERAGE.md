# Test Coverage Report — Reasoning Swarm

## Overview

The test suite validates the Reasoning Swarm skill system across three categories:

| Category | Purpose | Files |
|----------|---------|-------|
| **Unit Tests** | Validate intake classifier logic, technique structure, and anti-shortcut rules | `tests/test_intake_classifier.py`, `tests/test_intake_classifier_edges.py`, `tests/test_techniques.py`, `tests/test_anti_shortcut.py` |
| **Benchmarks** | Measure accuracy, coverage, and consistency across modes | `benchmarks/test_classifier_accuracy.py`, `benchmarks/test_deep_coverage.py`, `benchmarks/test_ensemble_parallel.py`, `benchmarks/test_megamind_quality.py`, `benchmarks/test_grand_jury_evidence.py`, `benchmarks/test_cross_mode_consistency.py` |
| **E2E / Real Agent** | End-to-end validation with real or mock LLM calls | `tests/test_e2e_scaffold.py`, `tests/agent_harness.py`, `tests/test_real_rapid_strike.py`, `tests/test_real_deep_think.py`, `tests/test_real_ensemble.py` |

### Unit Tests

- **`tests/test_intake_classifier.py`** — Validates every row of the AUTO-SELECT MATRIX from `skills/reasoning-swarm-SKILL.md`. Tests the pure-Python `classify_task()` function that maps task parameters to reasoning modes. Covers all 8 routing rules and 3 override rules. 100% matrix coverage required.

- **`tests/test_intake_classifier_edges.py`** — Boundary condition tests for the classifier: UNKNOWN complexity routing, CRITICAL stakes override, conflicting override rules, null/empty defaults, all 12 task types, and production+stakes interactions. Targets 100% branch coverage of `classify_task()`.

- **`tests/test_techniques.py`** — Validates each of the 11 Deep Think techniques (Meta-Cognition through Recursive Self-Improvement) produces correct output structure: required checkpoint markers, populated fields, substantive content, and cross-technique consistency when run as a chain.

- **`tests/test_anti_shortcut.py`** — Validates all 8 anti-shortcut detection rules: unverified file reads, architecture claims without citations, unrecorded searches, oversized patches, retry without evidence, hallucinated paths, premature confidence, and ritual completion. Implements `detect_shortcuts()` function.

### Benchmarks

- **`benchmarks/test_classifier_accuracy.py`** — Runs `classify_task()` on 50+ labeled problems, compares actual vs expected mode, and reports accuracy percentage (target: >95%). Tracks mode distribution and misclassification analysis.

- **`benchmarks/test_deep_coverage.py`** — Runs 10 medium-complexity problems through Deep Think mode. Verifies all 11 checkpoints are present, fields are non-empty, and confidence is calibrated. Tracks average checkpoints hit, confidence distribution, and technique ordering compliance.

- **`benchmarks/test_ensemble_parallel.py`** — Validates 5-way parallel Ensemble mode: all 5 angles produce output, synthesis captures disagreements, confidence is a weighted average, and parallel execution timing is < 2x single angle. Tests angle independence and conflict resolution.

- **`benchmarks/test_megamind_quality.py`** — Validates the 10→3→1 Megamind architecture: all 10 angle-explorers produce output, all 3 synthesizers process all 10 outputs, final synthesis integrates all 3, and iteration loop triggers correctly when confidence < 7 (max 3 iterations).

- **`benchmarks/test_grand_jury_evidence.py`** — Validates the 9-phase investigation protocol: phases GJ-0 through GJ-8 execute in order, Evidence Ledger entries are verbatim with line numbers, Murder Board has 4+ hypotheses with evidence FOR and AGAINST, and atomic change rule is enforced.

- **`benchmarks/test_cross_mode_consistency.py`** — Runs the same problem through all 5 modes and verifies: all modes identify the same core problem, higher-complexity modes produce more detailed analysis, confidence scores increase monotonically with mode depth, and key conclusions are consistent across modes.

### E2E / Real Agent Tests

- **`tests/test_e2e_scaffold.py`** — Shared test harness: `ReasoningSwarmHarness` class for constructing and running reasoning prompts, `ReasoningTrace` dataclass for structured output capture, and shared test problems across all 4 complexity levels.

- **`tests/agent_harness.py`** — Framework for testing with real LLM API calls. `AgentHarness` class with `run_prompt()`, `SwarmRunner` for full pipeline execution, async support, token tracking, rate limiting with backoff, and model-agnostic design (any OpenAI-compatible API).

- **`tests/test_real_rapid_strike.py`** — 5 low-complexity problems through Rapid Strike with real agent. Verifies completion < 30s, correct output fields, confidence >= 8 for straightforward tasks, and no unnecessary escalation.

- **`tests/test_real_deep_think.py`** — 3 medium-complexity problems through Deep Think with real agent. Verifies completion < 120s, all 11 checkpoints present with substantive content (>50 chars per field), and calibrated confidence.

- **`tests/test_real_ensemble.py`** — 2 high-complexity problems through Ensemble with real agent. Verifies all 5 angles produce distinct output (>200 tokens each), angles genuinely disagree, synthesis resolves conflicts, and total time < 3x single angle.

### Supporting Infrastructure

- **`benchmarks/framework.py`** — Standalone benchmark runner that loads problems, runs classifiers, compares against golden values, and generates pass/fail reports.
- **`benchmarks/problems.json`** — 20 diverse benchmark problems spanning all complexity levels and task types.
- **`benchmarks/run.py`** — CLI entry point for running benchmarks.
- **`scoring/confidence_calibration.py`** — Measures calibration of confidence scores vs actual correctness (ECE, Brier score, calibration curve).
- **`scoring/report.py`** — Generates markdown calibration reports with ASCII charts.

---

## Test Matrix

### Unit Tests — Intake Classifier

| # | Test | Mode | Complexity | Stakes | Prior Fails | Expected Mode |
|---|------|------|-----------|--------|-------------|---------------|
| 1 | Low everything, no fails | — | LOW | LOW | 0 | RAPID STRIKE |
| 2 | Low complexity, medium stakes | — | LOW | MEDIUM | 0 | DEEP THINK |
| 3 | Low complexity, high stakes | — | LOW | HIGH | 0 | ENSEMBLE |
| 4 | Low complexity, critical stakes | — | LOW | CRITICAL | 0 | MEGAMIND |
| 5 | Medium complexity, low stakes | — | MEDIUM | LOW | 0 | DEEP THINK |
| 6 | Medium complexity, medium stakes | — | MEDIUM | MEDIUM | 0 | DEEP THINK |
| 7 | Medium complexity, high stakes | — | MEDIUM | HIGH | 0 | ENSEMBLE |
| 8 | Medium complexity, critical stakes | — | MEDIUM | CRITICAL | 0 | MEGAMIND |
| 9 | High complexity, low stakes | — | HIGH | LOW | 0 | ENSEMBLE |
| 10 | High complexity, medium stakes | — | HIGH | MEDIUM | 0 | ENSEMBLE |
| 11 | High complexity, high stakes | — | HIGH | HIGH | 0 | ENSEMBLE |
| 12 | High complexity, critical stakes | — | HIGH | CRITICAL | 0 | MEGAMIND |
| 13 | Extreme complexity, low stakes | — | EXTREME | LOW | 0 | MEGAMIND |
| 14 | Extreme complexity, critical stakes | — | EXTREME | CRITICAL | 0 | MEGAMIND |
| 15 | Bug fix + prior fails >= 1 | BUG_FIX | any | any | >= 1 | GRAND JURY |
| 16 | Debug + framework/CSS + multi-file | DEBUGGING | any | any | any | GRAND JURY |
| 17 | Investigation type | INVESTIGATION | any | any | any | GRAND JURY |
| 18 | Production + stakes >= MEDIUM | any | any | MEDIUM+ | any | GRAND JURY |
| 19 | Override: "think harder" on RAPID | any | LOW | LOW | 0 | DEEP THINK |
| 20 | Override: "quick" on DEEP | any | MEDIUM | MEDIUM | 0 | RAPID STRIKE |
| 21 | Override: "quick" + CRITICAL stakes | any | any | CRITICAL | 0 | (not RAPID) |
| 22 | Override: prior failure => min ENSEMBLE | any | LOW | LOW | 1 | ENSEMBLE |

### Unit Tests — Edge Cases

| # | Test | Input | Expected Mode |
|---|------|-------|---------------|
| 23 | UNKNOWN complexity | UNKNOWN | MEGAMIND |
| 24 | CRITICAL stakes alone overrides complexity | LOW + CRITICAL | MEGAMIND |
| 25 | Multiple overrides: "think harder" + CRITICAL | — | MEGAMIND (or higher) |
| 26 | Empty/null task_type defaults to UNKNOWN | null | MEGAMIND |
| 27 | Prior fails = 0 vs 1 vs 2+ routing | — | Varies per matrix |
| 28 | framework_css=True alone (not GRAND JURY) | — | Per matrix |
| 29 | All 12 task types route correctly | — | Per matrix |
| 30 | production=True with varying stakes | — | GRAND JURY if stakes >= MEDIUM |

### Unit Tests — Techniques

| # | Test | Validates |
|---|------|-----------|
| 31 | Technique 1: Meta-Cognition output structure | Required fields populated |
| 32 | Technique 2: Step-Back output structure | Required fields populated |
| 33 | Technique 3: Decomposition output structure | Sub-problems and dependencies |
| 34 | Technique 4: Tree of Thought structure | 3+ branches with PURSUE/PRUNE |
| 35 | Technique 5: First Principles structure | Assumptions with true/convention/false |
| 36 | Technique 6: Analogical Reasoning structure | Similar problems with solutions |
| 37 | Technique 7: Chain of Thought structure | Steps with reasons, conclusion |
| 38 | Technique 8: Devil's Advocate structure | 3+ attacks with defenses |
| 39 | Technique 9: Inversion/Pre-Mortem structure | Failure modes with preventions |
| 40 | Technique 10: RAVEN Loop structure | REFLECT→ADAPT→VERIFY→EXECUTE→NAVIGATE |
| 41 | Technique 11: Recursive Self-Improvement | DRAFT→CRITIQUE→IMPROVED→FINAL |
| 42 | Technique chaining consistency | Each builds on previous output |

### Unit Tests — Anti-Shortcut Detection

| # | Shortcut Type | Expected Detection |
|---|--------------|-------------------|
| 43 | "I read the file" without verbatim excerpt | Detected |
| 44 | "Architecture is obvious" without citations | Detected |
| 45 | "I searched" without command/output | Detected |
| 46 | Big patch touching many things "just in case" | Detected |
| 47 | Second try without new evidence | Detected |
| 48 | Hallucinated file path | Detected |
| 49 | Premature confidence (8+ without verification) | Detected |
| 50 | Ritual completion (templates without work) | Detected |

### Benchmarks

| # | Benchmark | Metric | Target |
|---|-----------|--------|--------|
| 51 | Classifier accuracy (50 problems) | Accuracy % | >95% |
| 52 | Deep Think checkpoint coverage | Avg checkpoints/run | 11/11 |
| 53 | Deep Think confidence calibration | Distribution | Not artificially high |
| 54 | Ensemble angle diversity | Distinct outputs | All 5 angles distinct |
| 55 | Ensemble parallelism | Total time vs single | <2x single angle |
| 56 | Ensemble synthesis quality | Conflicts resolved | All disagreements addressed |
| 57 | Megamind architecture completeness | 10+3+1 outputs | All produced |
| 58 | Megamind iteration loop | Loop on low conf | Triggers correctly, max 3 |
| 59 | Grand Jury phase order | GJ-0 through GJ-8 | Sequential execution |
| 60 | Grand Jury evidence quality | Verbatim excerpts | All entries verbatim |
| 61 | Grand Jury murder board | Hypothesis count | >= 4 with FOR/AGAINST |
| 62 | Cross-mode consistency | Core problem ID | All modes agree |
| 63 | Cross-mode depth scaling | Analysis detail | Higher modes > lower |
| 64 | Cross-mode confidence monotonicity | Confidence ordering | MEGA >= ENSEMBLE >= DEEP >= RAPID |

### E2E / Real Agent Tests

| # | Test | Mode | Problems | Latency Target |
|---|------|------|----------|---------------|
| 65 | Rapid Strike — docstring addition | RAPID | 1 | <30s |
| 66 | Rapid Strike — typo fix | RAPID | 1 | <30s |
| 67 | Rapid Strike — type hints | RAPID | 1 | <30s |
| 68 | Rapid Strike — version bump | RAPID | 1 | <30s |
| 69 | Rapid Strike — unused import removal | RAPID | 1 | <30s |
| 70 | Deep Think — connection pooling | DEEP | 1 | <120s |
| 71 | Deep Think — retry logic | DEEP | 1 | <120s |
| 72 | Deep Think — module decomposition | DEEP | 1 | <120s |
| 73 | Ensemble — rate limiter design | ENSEMBLE | 1 | <3x single |
| 74 | Ensemble — plugin system architecture | ENSEMBLE | 1 | <3x single |

---

## Running Tests

### Unit Tests (fast, no API calls)

```bash
# Run all unit tests
python -m pytest tests/test_intake_classifier.py tests/test_intake_classifier_edges.py tests/test_techniques.py tests/test_anti_shortcut.py -v

# Run classifier tests only
python -m pytest tests/test_intake_classifier.py -v

# Run edge case tests only
python -m pytest tests/test_intake_classifier_edges.py -v

# Run technique tests only
python -m pytest tests/test_techniques.py -v

# Run anti-shortcut tests only
python -m pytest tests/test_anti_shortcut.py -v
```

### Benchmarks (medium speed)

```bash
# Run all benchmarks via CLI
python benchmarks/run.py

# Run individual benchmark
python -m pytest benchmarks/test_classifier_accuracy.py -v
python -m pytest benchmarks/test_deep_coverage.py -v
python -m pytest benchmarks/test_ensemble_parallel.py -v
python -m pytest benchmarks/test_megamind_quality.py -v
python -m pytest benchmarks/test_grand_jury_evidence.py -v
python -m pytest benchmarks/test_cross_mode_consistency.py -v

# Run benchmarks with specific mode override
python benchmarks/run.py --mode rapid
python benchmarks/run.py --mode deep
python benchmarks/run.py --mode ensemble
python benchmarks/run.py --mode mega
python benchmarks/run.py --mode jury
```

### E2E / Real Agent Tests (requires API keys)

```bash
# Set environment variables
export REASONING_SWARM_API_URL="https://api.openai.com/v1"
export REASONING_SWARM_MODEL="gpt-4o"
export REASONING_SWARM_API_KEY="sk-..."

# Run with real agent
python -m pytest tests/test_real_rapid_strike.py -v
python -m pytest tests/test_real_deep_think.py -v
python -m pytest tests/test_real_ensemble.py -v

# Run with mock agent (CI mode)
python -m pytest tests/test_real_rapid_strike.py -v --mock-agent
python -m pytest tests/test_real_deep_think.py -v --mock-agent
python -m pytest tests/test_real_ensemble.py -v --mock-agent
```

### Quality Scoring

```bash
# Run confidence calibration scorer
python scoring/confidence_calibration.py

# Generate calibration report
python scoring/report.py --output docs/calibration_report.md
```

### All Tests

```bash
# Full suite (unit + benchmarks, skips real agent tests)
python -m pytest tests/ benchmarks/ -v --ignore=tests/test_real_rapid_strike.py --ignore=tests/test_real_deep_think.py --ignore=tests/test_real_ensemble.py

# Full suite including real agent tests (requires API keys)
REASONING_SWARM_API_KEY=sk-... python -m pytest tests/ benchmarks/ -v
```

---

## Quality Metrics

| Metric | Description | Target | Measurement |
|--------|-------------|--------|-------------|
| **Classifier Accuracy** | % of problems classified to correct mode | >95% | `benchmarks/test_classifier_accuracy.py` |
| **Branch Coverage** | % of `classify_task()` branches exercised | 100% | `pytest --cov` |
| **Checkpoint Coverage** | Avg Deep Think checkpoints hit per run | 11/11 | `benchmarks/test_deep_coverage.py` |
| **ECE (Expected Calibration Error)** | How well confidence predicts correctness | <0.1 | `scoring/confidence_calibration.py` |
| **Brier Score** | Probabilistic accuracy of confidence | <0.2 | `scoring/confidence_calibration.py` |
| **Ensemble Angle Diversity** | % of runs where all 5 angles produce distinct output | 100% | `benchmarks/test_ensemble_parallel.py` |
| **Parallelism Efficiency** | Total Ensemble time / single angle time | <2.0x | `benchmarks/test_ensemble_parallel.py` |
| **Megamind Completeness** | % of runs producing all 10+3+1 outputs | 100% | `benchmarks/test_megamind_quality.py` |
| **Grand Jury Phase Compliance** | % of runs completing all 9 phases in order | 100% | `benchmarks/test_grand_jury_evidence.py` |
| **Cross-Mode Consistency** | % of problems where all modes agree on core issue | 100% | `benchmarks/test_cross_mode_consistency.py` |
| **Confidence Monotonicity** | % of problems where MEGA >= ENSEMBLE >= DEEP >= RAPID | 100% | `benchmarks/test_cross_mode_consistency.py` |
| **Anti-Shortcut Detection Rate** | % of injected shortcuts detected | 100% | `tests/test_anti_shortcut.py` |
| **Rapid Strike Latency** | Avg time to complete low-complexity tasks | <30s | `tests/test_real_rapid_strike.py` |
| **Deep Think Latency** | Avg time to complete medium-complexity tasks | <120s | `tests/test_real_deep_think.py` |

---

## Known Limitations

1. **No runtime validation of actual skill execution.** The classifier unit tests validate the routing matrix, but the actual skill files (`skills/*.md`) are markdown prompts consumed by LLMs — they cannot be executed directly by Python. Real agent tests approximate this but depend on LLM behavior which is non-deterministic.

2. **Confidence scores are self-reported by LLMs.** The calibration scorer measures whether the LLM's confidence aligns with its actual accuracy, but the LLM may game the calibration table if instructed to always report 7+. Repeated testing across diverse problems mitigates this.

3. **Ensemble/Megamind parallelism is simulated in benchmarks.** Unit benchmarks cannot truly spawn parallel LLM subprocesses. The parallel execution timing tests validate the architectural claim using mock agents; real parallelism validation requires the real agent test suite with API keys.

4. **Anti-shortcut detection is heuristic.** The `detect_shortcuts()` function checks for patterns in output text. A sufficiently clever LLM could evade detection by paraphrasing shortcuts. The 8 rules cover the most common failure modes but are not exhaustive.

5. **Grand Jury evidence quality is structural, not semantic.** Tests verify that Evidence Ledger entries exist, are verbatim, and have line numbers — but cannot verify that the evidence actually supports the stated conclusion. Human review of Grand Jury outputs is recommended for critical debugging tasks.

6. **Cross-mode consistency assumes a "correct" answer.** The benchmark compares modes against each other, not against ground truth. If all modes produce the same incorrect answer, consistency appears perfect. Labeling benchmark problems with known-correct answers partially addresses this.

7. **Token cost estimates are approximate.** The ~2-5K / ~10-20K / ~20-40K / ~40-80K token ranges per mode are estimates based on typical output lengths. Actual costs depend on context size, code complexity, and LLM verbosity.

8. **No tests for de-escalation behavior.** The test suite validates escalation paths (confidence < threshold triggers next mode) but does not test de-escalation (high confidence allows dropping to a lighter mode). De-escalation is rare in practice and difficult to test without live agent interaction.

---

## Adding Tests

### Adding a Unit Test

1. Identify which component you're testing (classifier, technique, anti-shortcut).
2. Add test cases to the appropriate file:
   - Classifier routing → `tests/test_intake_classifier.py`
   - Classifier edge cases → `tests/test_intake_classifier_edges.py`
   - Technique output structure → `tests/test_techniques.py`
   - Shortcut detection → `tests/test_anti_shortcut.py`
3. Follow existing patterns: each test is a function named `test_<descriptive_name>`.
4. Use `classify_task()` for classifier tests — it's a pure function with no side effects.
5. Run `python -m pytest tests/<file>.py -v` to verify.

### Adding a Benchmark

1. Create a new file in `benchmarks/` following the pattern `test_<area>.py`.
2. Define test problems with expected outputs in a JSON file or inline.
3. Use `benchmarks/framework.py` for shared benchmark infrastructure.
4. Register the benchmark in `benchmarks/run.py` so it's included in `python benchmarks/run.py`.
5. Define target metrics in this document's Quality Metrics section.

### Adding an E2E / Real Agent Test

1. Create test file in `tests/` following `test_real_<mode>.py` naming.
2. Use `AgentHarness` from `tests/agent_harness.py` for API interaction.
3. Define test problems as a list of dicts with `description`, `expected_mode`, and `validation` fields.
4. Each test should verify: latency, output structure, confidence calibration, and mode correctness.
5. Support `--mock-agent` flag for CI environments without API keys.
6. Add to the CI workflow's skip list in `.github/workflows/swarm-ci.yml`.

### Updating the Auto-Select Matrix

If you add or change routing rules in `skills/reasoning-swarm-SKILL.md`:

1. Update `classify_task()` implementation to match the new rules.
2. Add corresponding test cases to `tests/test_intake_classifier.py`.
3. Add edge case tests to `tests/test_intake_classifier_edges.py`.
4. Update the Test Matrix table in this document.
5. Run the full classifier accuracy benchmark to verify no regressions: `python -m pytest benchmarks/test_classifier_accuracy.py -v`.
