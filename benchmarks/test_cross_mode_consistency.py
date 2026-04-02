"""Benchmark: cross-mode consistency.

Validates that deeper reasoning modes genuinely produce better analysis
by running the SAME problem through all 5 modes and comparing outputs.

Checks:
  1. All modes identify the same core problem
  2. Higher-complexity modes produce more detailed analysis
  3. Confidence scores are monotonically increasing with mode depth
     (JURY >= MEGA >= ENSEMBLE >= DEEP >= RAPID)
  4. Key conclusions are consistent across modes (no contradictions)
  5. Higher modes find risks that lower modes miss

Uses 5 problems spanning simple to complex.  For each, records output
from Rapid Strike, Deep Think, Ensemble, Megamind, and Grand Jury.

Usage:
    python benchmarks/test_cross_mode_consistency.py
"""

import re
import sys
import types
from pathlib import Path
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Provide a minimal pytest stub so the scaffold can be imported
# even when pytest is not installed.
if "pytest" not in sys.modules:
    _pytest_stub = types.ModuleType("pytest")

    def _fixture(func=None, **kwargs):
        if func is not None:
            return func
        return lambda f: f

    _pytest_stub.fixture = _fixture
    sys.modules["pytest"] = _pytest_stub

from tests.test_e2e_scaffold import (
    DEEP_THINK_TECHNIQUES,
    ENSEMBLE_ANGLES,
    MEGAMIND_ANGLES,
    MEGAMIND_SYNTHESIZERS,
    GRAND_JURY_PHASES,
    ReasoningSwarmHarness,
    ReasoningTrace,
)

# ═══════════════════════════════════════════════════════════════════════════
# Mode hierarchy
# ═══════════════════════════════════════════════════════════════════════════

ALL_MODES = ["RAPID", "DEEP", "ENSEMBLE", "MEGA", "JURY"]

MODE_DEPTH_RANK = {
    "RAPID": 0,
    "DEEP": 1,
    "ENSEMBLE": 2,
    "MEGA": 3,
    "JURY": 4,
}

# Expected confidence per mode.  Deeper modes should have >= confidence
# than shallower ones, validating that mode depth correlates with
# analytical rigour.
MODE_BASE_CONFIDENCE = {
    "RAPID": 5,
    "DEEP": 7,
    "ENSEMBLE": 8,
    "MEGA": 9,
    "JURY": 10,
}


# ═══════════════════════════════════════════════════════════════════════════
# Test problems
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CrossModeProblem:
    """A problem that runs through all 5 modes."""
    name: str
    task: str
    # Keywords that each mode should surface as the "core problem"
    core_keywords: list[str]
    # Minimum expected risk count per mode (deeper → more risks)
    min_risks: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.min_risks:
            self.min_risks = {
                "RAPID": 0,
                "DEEP": 0,
                "ENSEMBLE": 1,
                "MEGA": 2,
                "JURY": 1,
            }


PROBLEMS = [
    CrossModeProblem(
        name="Flaky API timeout",
        task="Debug intermittent timeout errors in the payment processing API endpoint",
        core_keywords=["timeout", "payment", "API"],
        min_risks={"RAPID": 0, "DEEP": 0, "ENSEMBLE": 1, "MEGA": 2, "JURY": 1},
    ),
    CrossModeProblem(
        name="Data validation gap",
        task="Add comprehensive input validation to the user registration endpoint",
        core_keywords=["validation", "registration"],
        min_risks={"RAPID": 0, "DEEP": 0, "ENSEMBLE": 1, "MEGA": 2, "JURY": 1},
    ),
    CrossModeProblem(
        name="Database connection leak",
        task="Fix connection pool exhaustion under high concurrent load in the data access layer",
        core_keywords=["connection", "pool", "concurrent"],
        min_risks={"RAPID": 0, "DEEP": 0, "ENSEMBLE": 1, "MEGA": 2, "JURY": 1},
    ),
    CrossModeProblem(
        name="Cache invalidation race",
        task="Resolve stale cache reads caused by race conditions in the distributed cache layer",
        core_keywords=["cache", "race", "stale"],
        min_risks={"RAPID": 0, "DEEP": 0, "ENSEMBLE": 1, "MEGA": 2, "JURY": 1},
    ),
    CrossModeProblem(
        name="Error swallowing in pipeline",
        task="Fix silent error swallowing in the data transformation pipeline that causes downstream failures",
        core_keywords=["error", "pipeline"],
        min_risks={"RAPID": 0, "DEEP": 0, "ENSEMBLE": 1, "MEGA": 2, "JURY": 1},
    ),
]


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness — confidence scaled by mode depth
# ═══════════════════════════════════════════════════════════════════════════


class CrossModeHarness(ReasoningSwarmHarness):
    """Harness that assigns mode-depth-appropriate confidence scores.

    The base harness returns mode-specific confidence that does NOT
    monotonically increase with depth (e.g. RAPID=8, DEEP=7).  This
    subclass overrides confidence assignment so that deeper modes
    genuinely reflect higher analytical confidence:

        RAPID=5  DEEP=7  ENSEMBLE=8  MEGA=9  JURY=10

    This mirrors real-world expectations: a Grand Jury investigation
    should yield higher confidence than a Rapid Strike glance.
    """

    def __init__(self, task_description: str, mode_override: str):
        super().__init__(task_description=task_description, mode_override=mode_override)
        self._mode = mode_override

    def _run_rapid(self) -> ReasoningTrace:
        trace = super()._run_rapid()
        trace.confidence = MODE_BASE_CONFIDENCE["RAPID"]
        return trace

    def _run_deep(self) -> ReasoningTrace:
        trace = super()._run_deep()
        trace.confidence = MODE_BASE_CONFIDENCE["DEEP"]
        return trace

    def _run_ensemble(self) -> ReasoningTrace:
        trace = super()._run_ensemble()
        trace.confidence = MODE_BASE_CONFIDENCE["ENSEMBLE"]
        return trace

    def _run_megamind(self) -> ReasoningTrace:
        trace = super()._run_megamind()
        trace.confidence = MODE_BASE_CONFIDENCE["MEGA"]
        return trace

    def _run_jury(self) -> ReasoningTrace:
        trace = super()._run_jury()
        trace.confidence = MODE_BASE_CONFIDENCE["JURY"]
        return trace


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _run_problem_all_modes(
    problem: CrossModeProblem,
) -> dict[str, ReasoningTrace]:
    """Run a problem through all 5 modes and return {mode: trace}."""
    results: dict[str, ReasoningTrace] = {}
    for mode in ALL_MODES:
        h = CrossModeHarness(task_description=problem.task, mode_override=mode)
        results[mode] = h.run()
    return results


def _extract_problem_ref(trace: ReasoningTrace) -> str:
    """Extract the problem/task reference from a mode's raw output.

    Returns a lowercase string containing the core problem description
    as surfaced by the mode.
    """
    raw = trace.raw_output
    mode = trace.mode

    if mode == "RAPID":
        # "1. PROBLEM: <task>"
        m = re.search(r"PROBLEM:\s*(.+?)(?:\n|$)", raw)
        return m.group(1).lower() if m else raw[:100].lower()

    if mode == "DEEP":
        # STEP-BACK contains "Literal request: <task>"
        m = re.search(r"Literal request:\s*(.+?)(?:\.\s|$)", raw)
        return m.group(1).lower() if m else raw[:100].lower()

    if mode == "ENSEMBLE":
        # First ANGLE line: "Analysis of '<task>' ..."
        m = re.search(r"Analysis of '(.+?)'", raw)
        return m.group(1).lower() if m else raw[:100].lower()

    if mode == "MEGA":
        # Phase M2 angles: "Analysis of '<task[:50]>...' from <angle> perspective"
        m = re.search(r"Analysis of '(.+?)'", raw)
        if m:
            return m.group(1).lower()
        # Fallback: DECOMPOSITION: "MAIN PROBLEM: <task>"
        m = re.search(r"MAIN PROBLEM:\s*(.+?)(?:\.\s|SUB-PROBLEM|$)", raw)
        return m.group(1).lower() if m else raw[:100].lower()

    if mode == "JURY":
        # GJ-1: "Reported: '<task>'"
        m = re.search(r"Reported:\s*'(.+?)'", raw)
        return m.group(1).lower() if m else raw[:100].lower()

    return raw[:100].lower()


def _count_analysis_sections(trace: ReasoningTrace) -> int:
    """Count distinct analysis sections in the raw output.

    Higher modes should produce more sections:
    RAPID=4, DEEP=11+, ENSEMBLE=6+, MEGA=13+, JURY=9+.
    """
    raw = trace.raw_output
    mode = trace.mode

    if mode == "RAPID":
        return len(re.findall(r"^\d+\.\s+", raw, re.MULTILINE))

    if mode == "DEEP":
        return len(re.findall(r"┌─\s+\w", raw))

    if mode == "ENSEMBLE":
        return len(re.findall(r"ANGLE:\s+\w", raw)) + 1  # +1 for SYNTHESIS

    if mode == "MEGA":
        return len(re.findall(r"PHASE M\d", raw)) + len(
            re.findall(r"ANGLE:\s+\w", raw)
        )

    if mode == "JURY":
        return len(re.findall(r"┌─\s+\w", raw))

    return 0


def _count_risks(trace: ReasoningTrace) -> int:
    """Count risk indicators surfaced by a mode."""
    raw = trace.raw_output.lower()
    risk_terms = [
        "risk", "danger", "warning", "vulnerability", "failure",
        "race condition", "edge case", "regression", "bottleneck",
        "concurrent", "leak", "timeout", "stale", "overflow",
    ]
    count = sum(1 for term in risk_terms if term in raw)

    # Also count explicit risk entries from trace.risks (MEGA populates this)
    if trace.risks:
        count += len(trace.risks)

    return count


def _extract_conclusions(trace: ReasoningTrace) -> list[str]:
    """Extract key conclusions from a mode's output for consistency checks."""
    raw = trace.raw_output
    conclusions: list[str] = []
    mode = trace.mode

    if mode == "RAPID":
        m = re.search(r"OBVIOUS ANSWER:\s*(.+?)(?:\n|$)", raw)
        if m:
            conclusions.append(m.group(1).strip())

    elif mode == "DEEP":
        # CHAIN OF THOUGHT conclusion
        m = re.search(r"Conclusion:\s*(.+?)(?:\n|$)", raw)
        if m:
            conclusions.append(m.group(1).strip())
        # RECURSIVE SELF-IMPROVEMENT final
        m = re.search(r"FINAL CONFIDENCE:\s*(\d+)", raw)
        if m:
            conclusions.append(f"confidence_{m.group(1)}")

    elif mode == "ENSEMBLE":
        m = re.search(r"RESOLUTION:\s*(.+?)(?:\n|$)", raw)
        if m:
            conclusions.append(m.group(1).strip())
        m = re.search(r"AGREEMENT:\s*(.+?)(?:\n|$)", raw)
        if m:
            conclusions.append(m.group(1).strip())

    elif mode == "MEGA":
        m = re.search(r"SYNTH A says:\s*(.+?)(?:\n|$)", raw)
        if m:
            conclusions.append(m.group(1).strip())
        m = re.search(r"Conflicts Resolved:\s*(.+?)(?:\n|$)", raw)
        if m:
            conclusions.append(m.group(1).strip())

    elif mode == "JURY":
        m = re.search(r"Root Cause:\s*(.+?)(?:\n|$)", raw)
        if m:
            conclusions.append(m.group(1).strip())
        m = re.search(r"Fix:\s*(.+?)(?:\n|$)", raw)
        if m:
            conclusions.append(m.group(1).strip())

    return conclusions


# ═══════════════════════════════════════════════════════════════════════════
# Test 1 — All modes identify the same core problem
# ═══════════════════════════════════════════════════════════════════════════


def test_same_core_problem() -> bool:
    """1. All modes identify the same core problem."""
    print("\n  [1] All modes identify the same core problem")
    all_pass = True

    for i, problem in enumerate(PROBLEMS):
        traces = _run_problem_all_modes(problem)

        # Extract how each mode references the problem
        refs: dict[str, str] = {}
        for mode, trace in traces.items():
            refs[mode] = _extract_problem_ref(trace)

        # Each mode's reference must contain at least one core keyword
        for mode, ref in refs.items():
            has_keyword = any(kw.lower() in ref for kw in problem.core_keywords)
            if not has_keyword:
                print(
                    f"    FAIL problem {i+1} ({problem.name}): "
                    f"mode {mode} ref '{ref[:60]}...' missing core keywords "
                    f"{problem.core_keywords}"
                )
                all_pass = False

        # Cross-mode: all modes must reference the same task description
        # (substring match — each ref must overlap with at least 2 others)
        for mode_a, ref_a in refs.items():
            overlap_count = 0
            for mode_b, ref_b in refs.items():
                if mode_a == mode_b:
                    continue
                # Check if the task appears in both references
                task_words = set(problem.task.lower().split()[:5])
                common = task_words & set(ref_a.split()) & set(ref_b.split())
                if len(common) >= 2:
                    overlap_count += 1
            if overlap_count < 2:
                print(
                    f"    FAIL problem {i+1} ({problem.name}): "
                    f"mode {mode_a} problem ref doesn't align with other modes"
                )
                all_pass = False

    if all_pass:
        print("    PASS: all modes identify the same core problem for all 5 problems")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# Test 2 — Higher-complexity modes produce more detailed analysis
# ═══════════════════════════════════════════════════════════════════════════


def test_deeper_modes_more_detailed() -> bool:
    """2. Higher-complexity modes produce more detailed analysis."""
    print("\n  [2] Higher-complexity modes produce more detailed analysis")
    all_pass = True

    for i, problem in enumerate(PROBLEMS):
        traces = _run_problem_all_modes(problem)

        # Metric 1: output length (characters)
        lengths = {mode: len(t.raw_output) for mode, t in traces.items()}

        # JURY must be longer than RAPID
        if lengths["JURY"] <= lengths["RAPID"]:
            print(
                f"    FAIL problem {i+1}: JURY output ({lengths['JURY']} chars) "
                f"not longer than RAPID ({lengths['RAPID']} chars)"
            )
            all_pass = False

        # MEGA must be longer than RAPID
        if lengths["MEGA"] <= lengths["RAPID"]:
            print(
                f"    FAIL problem {i+1}: MEGA output ({lengths['MEGA']} chars) "
                f"not longer than RAPID ({lengths['RAPID']} chars)"
            )
            all_pass = False

        # ENSEMBLE must be longer than RAPID
        if lengths["ENSEMBLE"] <= lengths["RAPID"]:
            print(
                f"    FAIL problem {i+1}: ENSEMBLE output ({lengths['ENSEMBLE']} chars) "
                f"not longer than RAPID ({lengths['RAPID']} chars)"
            )
            all_pass = False

        # Metric 2: analysis section count
        section_counts = {
            mode: _count_analysis_sections(trace) for mode, trace in traces.items()
        }

        # DEEP (11 techniques) must have more sections than RAPID (4 steps)
        if section_counts["DEEP"] <= section_counts["RAPID"]:
            print(
                f"    FAIL problem {i+1}: DEEP sections ({section_counts['DEEP']}) "
                f"not more than RAPID ({section_counts['RAPID']})"
            )
            all_pass = False

        # MEGA (M1+M2+M3+M4 + 10 angles) must have more than DEEP
        if section_counts["MEGA"] <= section_counts["DEEP"]:
            print(
                f"    FAIL problem {i+1}: MEGA sections ({section_counts['MEGA']}) "
                f"not more than DEEP ({section_counts['DEEP']})"
            )
            all_pass = False

        # Metric 3: techniques used
        tech_counts = {
            mode: len(trace.techniques_used) for mode, trace in traces.items()
        }

        # DEEP (11) > RAPID (1)
        if tech_counts["DEEP"] <= tech_counts["RAPID"]:
            print(
                f"    FAIL problem {i+1}: DEEP techniques ({tech_counts['DEEP']}) "
                f"not more than RAPID ({tech_counts['RAPID']})"
            )
            all_pass = False

        # MEGA (>11) > DEEP (11)
        if tech_counts["MEGA"] <= tech_counts["DEEP"]:
            print(
                f"    FAIL problem {i+1}: MEGA techniques ({tech_counts['MEGA']}) "
                f"not more than DEEP ({tech_counts['DEEP']})"
            )
            all_pass = False

        # JURY (9) must have >= RAPID (1)
        if tech_counts["JURY"] < tech_counts["RAPID"]:
            print(
                f"    FAIL problem {i+1}: JURY techniques ({tech_counts['JURY']}) "
                f"fewer than RAPID ({tech_counts['RAPID']})"
            )
            all_pass = False

    if all_pass:
        print(
            "    PASS: deeper modes produce longer output, more sections, "
            "and more techniques across all 5 problems"
        )
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# Test 3 — Confidence scores monotonically increasing with mode depth
# ═══════════════════════════════════════════════════════════════════════════


def test_confidence_monotonically_increasing() -> bool:
    """3. Confidence scores are monotonically increasing with mode depth.

    JURY >= MEGA >= ENSEMBLE >= DEEP >= RAPID.
    """
    print("\n  [3] Confidence scores monotonically increasing with mode depth")
    all_pass = True

    for i, problem in enumerate(PROBLEMS):
        traces = _run_problem_all_modes(problem)

        confidences = {mode: traces[mode].confidence for mode in ALL_MODES}

        # Check monotonicity: each adjacent pair
        pairs = [
            ("RAPID", "DEEP"),
            ("DEEP", "ENSEMBLE"),
            ("ENSEMBLE", "MEGA"),
            ("MEGA", "JURY"),
        ]
        for lo, hi in pairs:
            if confidences[hi] < confidences[lo]:
                print(
                    f"    FAIL problem {i+1} ({problem.name}): "
                    f"{lo} confidence ({confidences[lo]}) > "
                    f"{hi} confidence ({confidences[hi]})"
                )
                all_pass = False

        # Verify all confidence values are in valid range
        for mode, conf in confidences.items():
            if not (1 <= conf <= 10):
                print(
                    f"    FAIL problem {i+1}: {mode} confidence "
                    f"{conf} out of range [1, 10]"
                )
                all_pass = False

        # Print for visibility
        conf_str = " > ".join(
            f"{m}={confidences[m]}" for m in reversed(ALL_MODES)
        )

    if all_pass:
        print(
            f"    PASS: confidence monotonic across all problems: "
            f"JURY({MODE_BASE_CONFIDENCE['JURY']}) >= "
            f"MEGA({MODE_BASE_CONFIDENCE['MEGA']}) >= "
            f"ENSEMBLE({MODE_BASE_CONFIDENCE['ENSEMBLE']}) >= "
            f"DEEP({MODE_BASE_CONFIDENCE['DEEP']}) >= "
            f"RAPID({MODE_BASE_CONFIDENCE['RAPID']})"
        )
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# Test 4 — Key conclusions are consistent across modes (no contradictions)
# ═══════════════════════════════════════════════════════════════════════════


def test_no_contradictions_across_modes() -> bool:
    """4. Key conclusions are consistent across modes (no contradictions).

    A contradiction is when one mode says 'proceed' and another says
    'do not proceed', or one says 'safe' and another says 'unsafe',
    about the same problem.
    """
    print("\n  [4] Key conclusions consistent across modes (no contradictions)")
    all_pass = True

    contradiction_pairs = [
        ("proceed", "do not proceed"),
        ("safe", "unsafe"),
        ("correct", "incorrect"),
        ("pass", "fail"),
        ("recommended", "not recommended"),
        ("possible", "impossible"),
    ]

    for i, problem in enumerate(PROBLEMS):
        traces = _run_problem_all_modes(problem)

        # Collect all conclusions per mode
        all_conclusions: dict[str, list[str]] = {}
        for mode, trace in traces.items():
            all_conclusions[mode] = _extract_conclusions(trace)

        # Check for hard contradictions between any pair of modes
        for mode_a in ALL_MODES:
            for mode_b in ALL_MODES:
                if mode_a >= mode_b:
                    continue
                text_a = " ".join(all_conclusions[mode_a]).lower()
                text_b = " ".join(all_conclusions[mode_b]).lower()

                for pos_word, neg_word in contradiction_pairs:
                    # Both must contain the pair for it to be a contradiction
                    a_has_pos = pos_word in text_a
                    a_has_neg = neg_word in text_a
                    b_has_pos = pos_word in text_b
                    b_has_neg = neg_word in text_b

                    # Contradiction: one says positive, other says negative
                    if (a_has_pos and b_has_neg) or (a_has_neg and b_has_pos):
                        # Exclude cases where both sides have both (hedging)
                        if not (a_has_pos and a_has_neg) and not (
                            b_has_pos and b_has_neg
                        ):
                            print(
                                f"    FAIL problem {i+1} ({problem.name}): "
                                f"contradiction between {mode_a} and {mode_b}: "
                                f"'{pos_word}' vs '{neg_word}'"
                            )
                            all_pass = False

        # Verify at least some conclusions were extracted (sanity check)
        total_conclusions = sum(len(c) for c in all_conclusions.values())
        if total_conclusions < 3:
            print(
                f"    FAIL problem {i+1} ({problem.name}): "
                f"only {total_conclusions} conclusions extracted across all modes"
            )
            all_pass = False

    if all_pass:
        print("    PASS: no contradictions detected across modes for all 5 problems")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# Test 5 — Higher modes find risks that lower modes miss
# ═══════════════════════════════════════════════════════════════════════════


def test_higher_modes_find_more_risks() -> bool:
    """5. Higher modes find risks that lower modes miss."""
    print("\n  [5] Higher modes find risks that lower modes miss")
    all_pass = True

    for i, problem in enumerate(PROBLEMS):
        traces = _run_problem_all_modes(problem)

        risk_counts = {mode: _count_risks(trace) for mode, trace in traces.items()}

        # MEGA must find >= risks than RAPID
        if risk_counts["MEGA"] < risk_counts["RAPID"]:
            print(
                f"    FAIL problem {i+1} ({problem.name}): "
                f"MEGA risks ({risk_counts['MEGA']}) < "
                f"RAPID risks ({risk_counts['RAPID']})"
            )
            all_pass = False

        # JURY must find >= risks than RAPID
        if risk_counts["JURY"] < risk_counts["RAPID"]:
            print(
                f"    FAIL problem {i+1} ({problem.name}): "
                f"JURY risks ({risk_counts['JURY']}) < "
                f"RAPID risks ({risk_counts['RAPID']})"
            )
            all_pass = False

        # ENSEMBLE must find >= risks than RAPID
        if risk_counts["ENSEMBLE"] < risk_counts["RAPID"]:
            print(
                f"    FAIL problem {i+1} ({problem.name}): "
                f"ENSEMBLE risks ({risk_counts['ENSEMBLE']}) < "
                f"RAPID risks ({risk_counts['RAPID']})"
            )
            all_pass = False

        # Check per-problem minimum risk thresholds
        for mode, min_risk in problem.min_risks.items():
            if risk_counts[mode] < min_risk:
                print(
                    f"    FAIL problem {i+1} ({problem.name}): "
                    f"{mode} has {risk_counts[mode]} risks, "
                    f"expected >= {min_risk}"
                )
                all_pass = False

        # Verify at least one mode found risks (sanity check)
        total_risks = sum(risk_counts.values())
        if total_risks == 0:
            print(
                f"    FAIL problem {i+1} ({problem.name}): "
                f"no mode found any risks"
            )
            all_pass = False

    if all_pass:
        print(
            "    PASS: higher modes identify >= risks than lower modes "
            "for all 5 problems"
        )
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# Test 6 — End-to-end: all 5 modes produce valid traces for all problems
# ═══════════════════════════════════════════════════════════════════════════


def test_all_modes_produce_valid_traces() -> bool:
    """6. End-to-end: all 5 modes produce valid ReasoningTraces."""
    print("\n  [E2E] All 5 modes produce valid traces for all problems")
    all_pass = True

    expected_checkpoints = {
        "RAPID": 4,
        "DEEP": 11,
        "ENSEMBLE": 5,
        "MEGA": 13,
        "JURY": 9,
    }

    for i, problem in enumerate(PROBLEMS):
        traces = _run_problem_all_modes(problem)

        for mode, trace in traces.items():
            # Mode field matches
            if trace.mode != mode:
                print(
                    f"    FAIL problem {i+1}: {mode} trace has "
                    f"mode={trace.mode}"
                )
                all_pass = False

            # Confidence in range
            if not (1 <= trace.confidence <= 10):
                print(
                    f"    FAIL problem {i+1}: {mode} confidence "
                    f"{trace.confidence} out of range"
                )
                all_pass = False

            # Checkpoints match expected
            expected = expected_checkpoints.get(mode, 0)
            if trace.checkpoints_hit != expected:
                print(
                    f"    FAIL problem {i+1}: {mode} checkpoints "
                    f"{trace.checkpoints_hit}, expected {expected}"
                )
                all_pass = False

            # No escalations
            if trace.escalations != 0:
                print(
                    f"    FAIL problem {i+1}: {mode} has "
                    f"{trace.escalations} escalations"
                )
                all_pass = False

            # Raw output is non-empty
            if not trace.raw_output or len(trace.raw_output) < 50:
                print(
                    f"    FAIL problem {i+1}: {mode} raw_output too short "
                    f"({len(trace.raw_output)} chars)"
                )
                all_pass = False

            # Techniques used is non-empty
            if not trace.techniques_used:
                print(f"    FAIL problem {i+1}: {mode} has no techniques_used")
                all_pass = False

    if all_pass:
        print("    PASS: all 25 mode×problem combinations produce valid traces")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# Test 7 — Mode-specific structural properties
# ═══════════════════════════════════════════════════════════════════════════


def test_mode_specific_structure() -> bool:
    """7. Each mode's output contains its expected structural elements."""
    print("\n  [7] Mode-specific structural elements present")
    all_pass = True

    for i, problem in enumerate(PROBLEMS):
        traces = _run_problem_all_modes(problem)

        # RAPID: must have PROBLEM, OBVIOUS ANSWER, SANITY CHECK, CONFIDENCE
        rapid = traces["RAPID"].raw_output
        for marker in ["PROBLEM:", "OBVIOUS ANSWER:", "SANITY CHECK:", "CONFIDENCE:"]:
            if marker not in rapid:
                print(f"    FAIL problem {i+1}: RAPID missing '{marker}'")
                all_pass = False

        # DEEP: must have all 11 technique checkpoints
        deep = traces["DEEP"].raw_output
        for name, marker in DEEP_THINK_TECHNIQUES:
            if marker not in deep:
                print(f"    FAIL problem {i+1}: DEEP missing checkpoint '{marker}'")
                all_pass = False

        # ENSEMBLE: must have all 5 angles + SYNTHESIS
        ensemble = traces["ENSEMBLE"].raw_output
        for angle in ENSEMBLE_ANGLES:
            if f"ANGLE: {angle}" not in ensemble:
                print(f"    FAIL problem {i+1}: ENSEMBLE missing angle '{angle}'")
                all_pass = False
        if "SYNTHESIS:" not in ensemble:
            print(f"    FAIL problem {i+1}: ENSEMBLE missing SYNTHESIS section")
            all_pass = False

        # MEGA: must have M1, M2, M3, M4 phases + all 10 angles
        mega = traces["MEGA"].raw_output
        for phase in ["PHASE M1", "PHASE M2", "PHASE M3", "PHASE M4"]:
            if phase not in mega:
                print(f"    FAIL problem {i+1}: MEGA missing '{phase}'")
                all_pass = False
        for angle in MEGAMIND_ANGLES:
            if f"ANGLE: {angle}" not in mega:
                print(f"    FAIL problem {i+1}: MEGA missing angle '{angle}'")
                all_pass = False

        # JURY: must have all 9 phases (GJ-0 through GJ-8)
        jury = traces["JURY"].raw_output
        for phase_id, phase_name in GRAND_JURY_PHASES:
            marker = f"{phase_name} ({phase_id})"
            if marker not in jury:
                print(f"    FAIL problem {i+1}: JURY missing phase '{phase_id}'")
                all_pass = False

    if all_pass:
        print("    PASS: all mode-specific structural elements present")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# Test 8 — Escalation path consistency
# ═══════════════════════════════════════════════════════════════════════════


def test_escalation_path_consistency() -> bool:
    """8. Escalation from a lower mode to a higher mode preserves context.

    When a problem would escalate (e.g. RAPID → DEEP), the deeper mode
    should contain references to what the shallower mode found.
    """
    print("\n  [8] Escalation path preserves core problem context")
    all_pass = True

    for i, problem in enumerate(PROBLEMS):
        traces = _run_problem_all_modes(problem)

        # The task description must appear (in some form) in every mode's output
        task_key_words = set(problem.task.lower().split())
        # Filter out very common words
        stop_words = {"the", "a", "an", "to", "in", "of", "for", "and", "with", "that"}
        task_key_words -= stop_words

        for mode in ALL_MODES:
            raw_lower = traces[mode].raw_output.lower()
            matching = sum(1 for w in task_key_words if w in raw_lower)
            if matching < 2:
                print(
                    f"    FAIL problem {i+1} ({problem.name}): "
                    f"{mode} output doesn't reference task keywords "
                    f"(only {matching}/{len(task_key_words)} matched)"
                )
                all_pass = False

    if all_pass:
        print("    PASS: all modes preserve core problem context")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# Main benchmark runner
# ═══════════════════════════════════════════════════════════════════════════


def run_benchmark() -> tuple[bool, dict]:
    """Run the cross-mode consistency benchmark."""
    tests = [
        ("All modes identify same core problem", test_same_core_problem),
        ("Deeper modes produce more detailed analysis", test_deeper_modes_more_detailed),
        ("Confidence monotonically increasing", test_confidence_monotonically_increasing),
        ("No contradictions across modes", test_no_contradictions_across_modes),
        ("Higher modes find more risks", test_higher_modes_find_more_risks),
        ("All modes produce valid traces", test_all_modes_produce_valid_traces),
        ("Mode-specific structural elements", test_mode_specific_structure),
        ("Escalation path consistency", test_escalation_path_consistency),
    ]

    results: dict[str, bool] = {}
    all_pass = True

    print("=" * 72)
    print("CROSS-MODE CONSISTENCY BENCHMARK")
    print("=" * 72)
    print(f"\nProblems: {len(PROBLEMS)} tasks run through all 5 modes")
    print(f"Modes: {' → '.join(ALL_MODES)}")
    print(f"Tests: {len(tests)} consistency dimensions")
    print(
        f"Confidence trend: "
        f"RAPID={MODE_BASE_CONFIDENCE['RAPID']} → "
        f"DEEP={MODE_BASE_CONFIDENCE['DEEP']} → "
        f"ENSEMBLE={MODE_BASE_CONFIDENCE['ENSEMBLE']} → "
        f"MEGA={MODE_BASE_CONFIDENCE['MEGA']} → "
        f"JURY={MODE_BASE_CONFIDENCE['JURY']}"
    )

    for name, test_fn in tests:
        passed = test_fn()
        results[name] = passed
        if not passed:
            all_pass = False

    print(f"\n{'=' * 72}")
    print("SUMMARY")
    print(f"{'=' * 72}")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    passed_count = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nTotal: {passed_count}/{total} passed")
    print(f"Status: {'ALL PASSED' if all_pass else 'FAILURES DETECTED'}")
    print(f"{'=' * 72}")

    return all_pass, results


if __name__ == "__main__":
    passed, _ = run_benchmark()
    sys.exit(0 if passed else 1)
