"""Benchmark: Deep Think technique coverage across 10 medium-complexity problems.

Verifies Deep Think mode hits all 11 checkpoints for each problem, with
proper field population, calibrated confidence, and proportional reasoning depth.

Metrics:
  - Average checkpoints hit per run
  - Confidence distribution histogram
  - Token estimate per run
  - Technique ordering compliance

Usage:
    python benchmarks/test_deep_coverage.py
"""

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_e2e_scaffold import (
    DEEP_THINK_TECHNIQUES,
    ReasoningSwarmHarness,
    ReasoningTrace,
)

# ═══════════════════════════════════════════════════════════════════════════
# 10 medium-complexity problems
# ═══════════════════════════════════════════════════════════════════════════

PROBLEMS = [
    {
        "id": "M01",
        "description": "Refactor this module to use dependency injection",
        "complexity": "MEDIUM",
    },
    {
        "id": "M02",
        "description": "Add retry logic with exponential backoff to the API client",
        "complexity": "MEDIUM",
    },
    {
        "id": "M03",
        "description": "Convert the monolithic config parser into separate validator and loader classes",
        "complexity": "MEDIUM",
    },
    {
        "id": "M04",
        "description": "Implement a connection pool manager with health checks and graceful shutdown",
        "complexity": "MEDIUM",
    },
    {
        "id": "M05",
        "description": "Add request validation middleware that supports JSON Schema and custom rules",
        "complexity": "MEDIUM",
    },
    {
        "id": "M06",
        "description": "Implement an event bus with typed subscriptions and dead-letter queue",
        "complexity": "MEDIUM",
    },
    {
        "id": "M07",
        "description": "Refactor the caching layer to support multiple backends with a unified interface",
        "complexity": "MEDIUM",
    },
    {
        "id": "M08",
        "description": "Add database migration tooling that handles schema versioning and rollback",
        "complexity": "MEDIUM",
    },
    {
        "id": "M09",
        "description": "Implement a background task scheduler with cron expressions and failure recovery",
        "complexity": "MEDIUM",
    },
    {
        "id": "M10",
        "description": "Build a feature flag system with gradual rollout and A/B testing support",
        "complexity": "MEDIUM",
    },
]

# ═══════════════════════════════════════════════════════════════════════════
# Required fields per technique (from skills/deepthink-SKILL.md)
# ═══════════════════════════════════════════════════════════════════════════

REQUIRED_FIELDS = {
    "META-COGNITION": [
        "Problem type", "Confidence (1-10)", "Uncertainties", "Missing perspective",
    ],
    "STEP-BACK": [
        "Literal request", "What user ACTUALLY wants", "What I should",
    ],
    "DECOMPOSITION": [
        "MAIN PROBLEM", "SUB-PROBLEMS", "DEPENDENCIES",
    ],
    "TREE OF THOUGHT": [
        "BRANCH A", "BRANCH B", "BRANCH C", "Pros", "Cons", "Verdict", "SELECTED",
    ],
    "FIRST PRINCIPLES": [
        "Assumptions", "FUNDAMENTALLY required",
    ],
    "ANALOGICAL REASONING": [
        "Abstract pattern", "Similar solved problems", "What transfers",
    ],
    "CHAIN OF THOUGHT": [
        "Step 1", "Step 2", "Conclusion",
    ],
    "DEVIL'S ADVOCATE": [
        "My solution", "ATTACK 1", "Defense",
    ],
    "INVERSION / PRE-MORTEM": [
        "GUARANTEE failure", "Prevention",
    ],
    "RAVEN LOOP": [
        "REFLECT", "ADAPT", "VERIFY", "EXECUTE", "NAVIGATE",
    ],
    "RECURSIVE SELF-IMPROVEMENT": [
        "DRAFT", "CRITIQUE", "IMPROVED", "FINAL CONFIDENCE",
    ],
}

TECHNIQUE_NAMES = [name for name, _ in DEEP_THINK_TECHNIQUES]
CHECKPOINT_MARKERS = [marker for _, marker in DEEP_THINK_TECHNIQUES]

# Token estimate heuristic: ~4 chars per token
CHARS_PER_TOKEN = 4


# ═══════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ProblemResult:
    """Per-problem benchmark result."""
    problem_id: str
    description: str
    checkpoints_hit: int
    all_checkpoints_present: bool
    fields_complete: bool
    confidence: int
    confidence_calibrated: bool
    reasoning_depth_chars: int
    estimated_tokens: int
    technique_order_correct: bool
    missing_fields: list[str] = field(default_factory=list)
    raw_output: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# Analysis helpers
# ═══════════════════════════════════════════════════════════════════════════


def _extract_section(raw_output: str, technique_name: str) -> str:
    """Extract a technique's box section from raw output."""
    pattern = re.escape(technique_name)
    match = re.search(rf"┌─\s*{pattern}.*?└─+┘", raw_output, re.DOTALL)
    return match.group(0) if match else ""


def _extract_inner_content(section: str) -> str:
    """Extract content lines (after │) from a box section."""
    lines = []
    for line in section.split("\n"):
        stripped = line.strip()
        if stripped.startswith("│"):
            lines.append(stripped[1:].strip())
    return "\n".join(lines)


def _check_all_checkpoints_present(raw_output: str) -> tuple[int, bool]:
    """Return (checkpoints_hit, all_present)."""
    hit = 0
    for marker in CHECKPOINT_MARKERS:
        if marker in raw_output:
            hit += 1
    return hit, hit == 11


def _check_fields_complete(raw_output: str) -> tuple[bool, list[str]]:
    """Verify all required fields are present and non-empty for each technique."""
    missing = []
    for name, _ in DEEP_THINK_TECHNIQUES:
        section = _extract_section(raw_output, name)
        if not section:
            missing.append(f"{name}: section missing")
            continue
        content = _extract_inner_content(section)
        content_lower = content.lower()
        for field_label in REQUIRED_FIELDS.get(name, []):
            if field_label.lower() not in content_lower:
                missing.append(f"{name}: missing field '{field_label}'")
    return len(missing) == 0, missing


def _check_technique_order(raw_output: str) -> bool:
    """Verify techniques appear in prescribed order."""
    positions = []
    for name in TECHNIQUE_NAMES:
        pos = raw_output.find(f"┌─ {name}")
        if pos < 0:
            return False
        positions.append(pos)
    return all(positions[i] < positions[i + 1] for i in range(len(positions) - 1))


def _estimate_tokens(raw_output: str) -> int:
    """Rough token estimate based on character count."""
    return len(raw_output) // CHARS_PER_TOKEN


def _is_confidence_calibrated(confidence: int) -> bool:
    """Confidence for medium-complexity should be 5-8 (not artificially high)."""
    return 5 <= confidence <= 8


# ═══════════════════════════════════════════════════════════════════════════
# Benchmark runner
# ═══════════════════════════════════════════════════════════════════════════


def run_benchmark() -> list[ProblemResult]:
    """Run Deep Think on all 10 problems and collect results."""
    results = []

    for prob in PROBLEMS:
        harness = ReasoningSwarmHarness(
            task_description=prob["description"],
            mode_override="DEEP",
        )
        trace = harness.run()

        checkpoints_hit, all_present = _check_all_checkpoints_present(trace.raw_output)
        fields_ok, missing = _check_fields_complete(trace.raw_output)
        conf_calibrated = _is_confidence_calibrated(trace.confidence)
        order_ok = _check_technique_order(trace.raw_output)
        depth_chars = len(trace.raw_output)
        est_tokens = _estimate_tokens(trace.raw_output)

        results.append(ProblemResult(
            problem_id=prob["id"],
            description=prob["description"],
            checkpoints_hit=checkpoints_hit,
            all_checkpoints_present=all_present,
            fields_complete=fields_ok,
            missing_fields=missing,
            confidence=trace.confidence,
            confidence_calibrated=conf_calibrated,
            reasoning_depth_chars=depth_chars,
            estimated_tokens=est_tokens,
            technique_order_correct=order_ok,
            raw_output=trace.raw_output,
        ))

    return results


# ═══════════════════════════════════════════════════════════════════════════
# Report
# ═══════════════════════════════════════════════════════════════════════════


def print_report(results: list[ProblemResult]) -> int:
    """Print aggregate statistics and return exit code (0=pass, 1=fail)."""
    n = len(results)

    # ── Aggregate metrics ────────────────────────────────────────────────
    avg_checkpoints = sum(r.checkpoints_hit for r in results) / n
    all_checkpoints_pass = all(r.all_checkpoints_present for r in results)
    all_fields_pass = all(r.fields_complete for r in results)
    all_order_pass = all(r.technique_order_correct for r in results)
    calibrated_count = sum(1 for r in results if r.confidence_calibrated)
    avg_tokens = sum(r.estimated_tokens for r in results) / n
    avg_depth_chars = sum(r.reasoning_depth_chars for r in results) / n

    confidences = [r.confidence for r in results]
    conf_counter = Counter(confidences)

    # ── Print ────────────────────────────────────────────────────────────
    W = 72
    print("=" * W)
    print("DEEP THINK TECHNIQUE COVERAGE BENCHMARK")
    print("=" * W)

    print(f"\nProblems tested: {n}")
    print(f"Mode:            DEEP THINK")
    print(f"Complexity:      MEDIUM")

    # Per-problem table
    print(f"\n{'─' * W}")
    print("PER-PROBLEM RESULTS")
    print(f"{'─' * W}")
    print(f"{'ID':<5} {'CP':>3} {'Fields':>7} {'Conf':>5} {'Calib':>6} "
          f"{'Order':>6} {'Tokens':>7}")
    print(f"{'─' * 45}")
    for r in results:
        cp_status = f"{r.checkpoints_hit}/11"
        fld = "OK" if r.fields_complete else "FAIL"
        cal = "YES" if r.confidence_calibrated else "NO"
        ord_ = "OK" if r.technique_order_correct else "FAIL"
        print(f"{r.problem_id:<5} {cp_status:>3} {fld:>7} {r.confidence:>5} "
              f"{cal:>6} {ord_:>6} {r.estimated_tokens:>7}")

    # Checkpoint coverage
    print(f"\n{'─' * W}")
    print("CHECKPOINT COVERAGE")
    print(f"{'─' * W}")
    print(f"  Average checkpoints hit: {avg_checkpoints:.1f} / 11")
    print(f"  All 11 present (every run): {'PASS' if all_checkpoints_pass else 'FAIL'}")

    # Field completeness
    print(f"\n{'─' * W}")
    print("FIELD COMPLETENESS")
    print(f"{'─' * W}")
    print(f"  All required fields populated: {'PASS' if all_fields_pass else 'FAIL'}")
    if not all_fields_pass:
        for r in results:
            if r.missing_fields:
                print(f"  {r.problem_id}:")
                for mf in r.missing_fields:
                    print(f"    - {mf}")

    # Confidence calibration
    print(f"\n{'─' * W}")
    print("CONFIDENCE CALIBRATION")
    print(f"{'─' * W}")
    print(f"  Calibrated (5-8): {calibrated_count}/{n} "
          f"({calibrated_count / n * 100:.0f}%)")
    print(f"  Distribution:")
    for score in sorted(conf_counter.keys()):
        count = conf_counter[score]
        bar = "#" * count
        label = " ◄ outside target" if not (5 <= score <= 8) else ""
        print(f"    {score:>2}: {bar} ({count}){label}")

    # Technique ordering
    print(f"\n{'─' * W}")
    print("TECHNIQUE ORDERING COMPLIANCE")
    print(f"{'─' * W}")
    print(f"  Correct sequence (all runs): {'PASS' if all_order_pass else 'FAIL'}")

    # Token / depth estimates
    print(f"\n{'─' * W}")
    print("REASONING DEPTH")
    print(f"{'─' * W}")
    print(f"  Avg output chars:  {avg_depth_chars:,.0f}")
    print(f"  Avg est. tokens:   {avg_tokens:,.0f}")
    min_tokens = min(r.estimated_tokens for r in results)
    max_tokens = max(r.estimated_tokens for r in results)
    print(f"  Token range:       {min_tokens:,} – {max_tokens:,}")

    # Proportionality check: medium problems should produce moderate depth
    # (not as shallow as RAPID, not as deep as MEGAMIND)
    depth_ok = all(500 < r.reasoning_depth_chars < 50000 for r in results)
    print(f"  Depth proportional: {'PASS' if depth_ok else 'FAIL'}"
          f"  (medium range: 500–50,000 chars)")

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'=' * W}")
    all_pass = (
        all_checkpoints_pass
        and all_fields_pass
        and all_order_pass
        and calibrated_count == n
        and depth_ok
    )
    print(f"  OVERALL: {'PASS' if all_pass else 'FAIL'}")
    print(f"{'=' * W}")

    # ── JSON report ──────────────────────────────────────────────────────
    report_path = Path(__file__).parent / "deep_coverage_report.json"
    report_data = {
        "problems_tested": n,
        "mode": "DEEP THINK",
        "complexity": "MEDIUM",
        "avg_checkpoints_hit": round(avg_checkpoints, 2),
        "all_checkpoints_present": all_checkpoints_pass,
        "all_fields_complete": all_fields_pass,
        "confidence_distribution": {str(k): v for k, v in sorted(conf_counter.items())},
        "calibrated_count": calibrated_count,
        "avg_estimated_tokens": round(avg_tokens),
        "technique_order_compliance": all_order_pass,
        "depth_proportional": depth_ok,
        "overall_pass": all_pass,
        "results": [
            {
                "id": r.problem_id,
                "description": r.description,
                "checkpoints_hit": r.checkpoints_hit,
                "all_checkpoints_present": r.all_checkpoints_present,
                "fields_complete": r.fields_complete,
                "missing_fields": r.missing_fields,
                "confidence": r.confidence,
                "confidence_calibrated": r.confidence_calibrated,
                "estimated_tokens": r.estimated_tokens,
                "technique_order_correct": r.technique_order_correct,
            }
            for r in results
        ],
    }
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)
    print(f"\n  JSON report saved to {report_path}")

    return 0 if all_pass else 1


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════


if __name__ == "__main__":
    results = run_benchmark()
    exit_code = print_report(results)
    sys.exit(exit_code)
