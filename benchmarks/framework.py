"""Benchmark framework for the Reasoning Swarm intake classifier.

Standalone runner that loads benchmark problems, runs the classifier,
compares against golden expected values, and generates a report.
"""

import json
import time
import sys
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Classifier: implements the AUTO-SELECT MATRIX from reasoning-swarm-SKILL.md
# ---------------------------------------------------------------------------

VALID_TASK_TYPES = frozenset({
    "BUG_FIX", "IMPLEMENTATION", "ARCHITECTURE", "RESEARCH",
    "OPTIMIZE", "DEBUGGING", "CREATIVE", "ANALYSIS",
    "PLANNING", "INVESTIGATION", "DESIGN", "UNKNOWN",
})

VALID_COMPLEXITY = ("LOW", "MEDIUM", "HIGH", "EXTREME")
VALID_STAKES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")

MODE_RAPID = "RAPID"
MODE_DEEP = "DEEP"
MODE_ENSEMBLE = "ENSEMBLE"
MODE_MEGAMIND = "MEGAMIND"
MODE_GRAND_JURY = "GRAND_JURY"

_MODE_ORDER = {
    MODE_RAPID: 0,
    MODE_DEEP: 1,
    MODE_ENSEMBLE: 2,
    MODE_MEGAMIND: 3,
    MODE_GRAND_JURY: 4,
}


def _mode_rank(mode: str) -> int:
    return _MODE_ORDER.get(mode, -1)


def _escalate(current: str) -> str:
    rank = _mode_rank(current)
    if rank < 0 or rank >= 4:
        return current
    return {v: k for k, v in _MODE_ORDER.items()}[rank + 1]


def classify_task(
    task_type: str,
    complexity: str,
    stakes: str,
    prior_fails: int = 0,
    files_involved: str = "1-2",
    framework_css: bool = False,
    production: bool = False,
    user_hint: Optional[str] = None,
) -> str:
    """Return the reasoning-swarm mode for the given task parameters.

    Implements the AUTO-SELECT MATRIX and override rules from
    skills/reasoning-swarm-SKILL.md.
    """
    task_type = (task_type or "UNKNOWN").upper()
    if task_type not in VALID_TASK_TYPES:
        task_type = "UNKNOWN"

    complexity = (complexity or "UNKNOWN").upper()
    stakes = (stakes or "LOW").upper()
    prior_fails = max(0, int(prior_fails))
    hint = (user_hint or "").strip().lower()
    multi_file = files_involved in ("3-5", "6+")

    # --- GRAND JURY forced rules (highest priority) ---
    bug_debug = task_type in ("BUG_FIX", "DEBUGGING")

    if bug_debug and prior_fails >= 1:
        return MODE_GRAND_JURY

    if bug_debug and framework_css and multi_file:
        return MODE_GRAND_JURY

    if task_type == "INVESTIGATION":
        return MODE_GRAND_JURY

    if production and stakes in ("MEDIUM", "HIGH", "CRITICAL"):
        return MODE_GRAND_JURY

    # --- Base matrix ---
    if complexity == "EXTREME" or stakes == "CRITICAL" or task_type == "UNKNOWN":
        mode = MODE_MEGAMIND
    elif complexity == "HIGH" or stakes == "HIGH":
        mode = MODE_ENSEMBLE
    elif complexity == "MEDIUM" or stakes == "MEDIUM":
        mode = MODE_DEEP
    elif complexity == "LOW" and stakes == "LOW" and prior_fails == 0:
        mode = MODE_RAPID
    else:
        # Fallback for edge cases
        if prior_fails >= 2:
            mode = MODE_ENSEMBLE
        elif prior_fails >= 1:
            mode = MODE_DEEP
        else:
            mode = MODE_RAPID

    # --- Override rules ---
    if hint == "think harder":
        mode = _escalate(mode)

    if hint in ("quick", "just do it"):
        if stakes != "CRITICAL":
            mode = MODE_RAPID

    if prior_fails >= 1 and _mode_rank(mode) < _mode_rank(MODE_ENSEMBLE):
        mode = MODE_ENSEMBLE

    return mode


# ---------------------------------------------------------------------------
# Benchmark data structures
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkResult:
    problem_id: str
    description: str
    expected_mode: str
    actual_mode: str
    confidence: int
    latency_ms: float
    passed: bool

    @property
    def summary_line(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"  [{status}] {self.problem_id}: {self.description[:60]}"
            f"  expected={self.expected_mode} actual={self.actual_mode}"
            f"  conf={self.confidence}  {self.latency_ms:.1f}ms"
        )


@dataclass
class BenchmarkReport:
    results: list[BenchmarkResult] = field(default_factory=list)
    mode_override: Optional[str] = None

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total

    @property
    def mode_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for r in self.results:
            dist[r.actual_mode] = dist.get(r.actual_mode, 0) + 1
        return dict(sorted(dist.items()))

    def as_dict(self) -> dict:
        return {
            "mode_override": self.mode_override,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "accuracy": round(self.accuracy * 100, 1),
            "mode_distribution": self.mode_distribution,
            "results": [
                {
                    "id": r.problem_id,
                    "description": r.description,
                    "expected": r.expected_mode,
                    "actual": r.actual_mode,
                    "confidence": r.confidence,
                    "latency_ms": round(r.latency_ms, 2),
                    "passed": r.passed,
                }
                for r in self.results
            ],
        }

    def format_text(self) -> str:
        lines: list[str] = []
        lines.append("=" * 72)
        lines.append("  REASONING SWARM BENCHMARK REPORT")
        lines.append("=" * 72)

        if self.mode_override:
            lines.append(f"  Mode override: {self.mode_override}")
            lines.append("")

        lines.append(f"  Total:   {self.total}")
        lines.append(f"  Passed:  {self.passed}")
        lines.append(f"  Failed:  {self.failed}")
        lines.append(f"  Accuracy: {self.accuracy * 100:.1f}%")
        lines.append("")

        lines.append("  --- Per-Problem Results ---")
        for r in self.results:
            lines.append(r.summary_line)
        lines.append("")

        lines.append("  --- Mode Distribution ---")
        for mode, count in self.mode_distribution.items():
            bar = "#" * count
            lines.append(f"    {mode:12s}  {count:3d}  {bar}")
        lines.append("")

        lines.append(f"  Status: {'ALL PASSED' if self.failed == 0 else 'FAILURES DETECTED'}")
        lines.append("=" * 72)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def load_problems(path: str | Path) -> list[dict]:
    """Load benchmark problems from a JSON file."""
    path = Path(path)
    with open(path, "r") as f:
        problems = json.load(f)
    if not isinstance(problems, list) or len(problems) == 0:
        raise ValueError(f"Expected non-empty list in {path}, got {type(problems)}")
    return problems


def run_benchmark(
    problems: list[dict],
    mode_override: Optional[str] = None,
) -> BenchmarkReport:
    """Run the classifier on each problem and compare to expected mode."""
    report = BenchmarkReport(mode_override=mode_override)

    for prob in problems:
        pid = prob.get("id", "unknown")
        desc = prob.get("description", "")
        expected = prob.get("expected_mode", MODE_RAPID)
        hint = prob.get("user_hint")

        t0 = time.perf_counter()
        actual = classify_task(
            task_type=prob.get("task_type", "UNKNOWN"),
            complexity=prob.get("complexity", "LOW"),
            stakes=prob.get("stakes", "LOW"),
            prior_fails=prob.get("prior_fails", 0),
            files_involved=prob.get("files_involved", "1-2"),
            framework_css=prob.get("framework_css", False),
            production=prob.get("production", False),
            user_hint=hint,
        )
        latency = (time.perf_counter() - t0) * 1000  # ms

        if mode_override:
            actual = mode_override

        passed = actual == expected

        # Confidence: heuristic based on mode depth
        confidence_map = {
            MODE_RAPID: 8,
            MODE_DEEP: 7,
            MODE_ENSEMBLE: 7,
            MODE_MEGAMIND: 6,
            MODE_GRAND_JURY: 7,
        }
        confidence = confidence_map.get(actual, 7)

        report.results.append(BenchmarkResult(
            problem_id=pid,
            description=desc,
            expected_mode=expected,
            actual_mode=actual,
            confidence=confidence,
            latency_ms=latency,
            passed=passed,
        ))

    return report


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _default_problems_path() -> Path:
    return Path(__file__).parent / "problems.json"


def main(mode_override: Optional[str] = None) -> int:
    """Entry point: load problems, run benchmark, print report, return exit code."""
    problems_path = _default_problems_path()
    if not problems_path.exists():
        print(f"ERROR: problems file not found: {problems_path}", file=sys.stderr)
        return 1

    problems = load_problems(problems_path)
    report = run_benchmark(problems, mode_override=mode_override)

    print(report.format_text())

    # Save JSON report alongside
    report_path = Path(__file__).parent / "report.json"
    with open(report_path, "w") as f:
        json.dump(report.as_dict(), f, indent=2)
    print(f"  JSON report saved to {report_path}")

    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
