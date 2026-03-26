#!/usr/bin/env python3
"""CLI batch test runner for the Reasoning Swarm test suite.

Usage:
    python -m cli.batch_test --suite all
    python -m cli.batch_test --suite real-agent --model mimo-v2-pro
    python -m cli.batch_test --suite benchmarks --parallel
    python -m cli.batch_test --suite unit --report
    python -m cli.batch_test --suite all --ci --timeout 120

Exit codes:
    0 — all tests passed
    1 — one or more tests failed
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Suite definitions — maps suite names to test discovery patterns
# ---------------------------------------------------------------------------

SUITES: dict[str, dict] = {
    "unit": {
        "description": "Unit tests (intake classifier, techniques, anti-shortcut)",
        "paths": ["tests/"],
        "markers": None,
        "k": "not real_agent and not e2e",
        "glob": "test_intake_classifier.py|test_techniques.py|test_anti_shortcut.py",
    },
    "benchmarks": {
        "description": "Benchmark tests (classifier accuracy, deep coverage, ensemble parallel)",
        "paths": ["benchmarks/"],
        "markers": None,
        "k": None,
        "glob": "test_*.py",
    },
    "e2e": {
        "description": "End-to-end tests (scaffold, mock agent flows)",
        "paths": ["tests/"],
        "markers": None,
        "k": "e2e",
        "glob": "test_e2e_*.py",
    },
    "real-agent": {
        "description": "Real agent tests (requires API keys)",
        "paths": ["tests/"],
        "markers": None,
        "k": "real_agent",
        "glob": "test_real_*.py",
    },
    "quality": {
        "description": "Quality scorer tests (calibration, report generation)",
        "paths": ["scoring/"],
        "markers": None,
        "k": None,
        "glob": "test_*.py",
    },
    "cross-rig": {
        "description": "Cross-rig integration tests",
        "paths": ["tests/"],
        "markers": None,
        "k": "cross_rig",
        "glob": "test_cross_rig*.py",
    },
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    """Result of running a single test file or module."""
    suite: str
    name: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    warnings: int = 0
    duration_s: float = 0.0
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    failures: list[dict] = field(default_factory=list)
    mode: str = ""
    confidence: float = 0.0
    latency_ms: float = 0.0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors + self.skipped

    @property
    def success(self) -> bool:
        return self.failed == 0 and self.errors == 0


@dataclass
class SuiteResult:
    """Aggregate result for a test suite."""
    suite_name: str
    description: str
    tests: list[TestResult] = field(default_factory=list)
    duration_s: float = 0.0

    @property
    def total(self) -> int:
        return sum(t.total for t in self.tests)

    @property
    def passed(self) -> int:
        return sum(t.passed for t in self.tests)

    @property
    def failed(self) -> int:
        return sum(t.failed for t in self.tests)

    @property
    def errors(self) -> int:
        return sum(t.errors for t in self.tests)

    @property
    def skipped(self) -> int:
        return sum(t.skipped for t in self.tests)

    @property
    def success(self) -> bool:
        return self.failed == 0 and self.errors == 0


@dataclass
class BatchReport:
    """Full batch test report across all suites."""
    suites: list[SuiteResult] = field(default_factory=list)
    model: str = ""
    timestamp: str = ""
    total_duration_s: float = 0.0

    @property
    def total(self) -> int:
        return sum(s.total for s in self.suites)

    @property
    def passed(self) -> int:
        return sum(s.passed for s in self.suites)

    @property
    def failed(self) -> int:
        return sum(s.failed for s in self.suites)

    @property
    def errors(self) -> int:
        return sum(s.errors for s in self.suites)

    @property
    def skipped(self) -> int:
        return sum(s.skipped for s in self.suites)

    @property
    def success(self) -> bool:
        return all(s.success for s in self.suites)

    @property
    def mode_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for suite in self.suites:
            for test in suite.tests:
                if test.mode:
                    dist[test.mode] = dist.get(test.mode, 0) + 1
        return dict(sorted(dist.items()))

    @property
    def avg_confidence(self) -> float:
        confs = [t.confidence for s in self.suites for t in s.tests if t.confidence > 0]
        return sum(confs) / len(confs) if confs else 0.0

    @property
    def avg_latency_ms(self) -> float:
        lats = [t.latency_ms for s in self.suites for t in s.tests if t.latency_ms > 0]
        return sum(lats) / len(lats) if lats else 0.0


# ---------------------------------------------------------------------------
# Test discovery
# ---------------------------------------------------------------------------

def discover_tests(suite_name: str) -> list[Path]:
    """Discover test files for a given suite."""
    suite_cfg = SUITES[suite_name]
    test_files: list[Path] = []

    for rel_path in suite_cfg["paths"]:
        search_dir = PROJECT_ROOT / rel_path
        if not search_dir.exists():
            continue

        if search_dir.is_file():
            test_files.append(search_dir)
            continue

        for py_file in sorted(search_dir.glob("*.py")):
            if not py_file.name.startswith("test_"):
                continue
            if py_file.name == "__init__.py":
                continue

            # Apply glob filter if specified
            glob_pattern = suite_cfg.get("glob")
            if glob_pattern:
                patterns = glob_pattern.split("|")
                if not any(py_file.name == p or py_file.match(p) for p in patterns):
                    continue

            test_files.append(py_file)

    return test_files


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

def _parse_pytest_output(
    stdout: str,
    stderr: str,
    exit_code: int,
    duration_s: float,
) -> TestResult:
    """Parse pytest output into a TestResult."""
    result = TestResult(
        suite="",
        name="",
        exit_code=exit_code,
        duration_s=duration_s,
        stdout=stdout,
        stderr=stderr,
    )

    # Parse the summary line: "X passed, Y failed, Z errors, W skipped"
    summary_match = re.search(
        r"=+\s*\n?(.*?)\s+in\s+[\d.]+s\s*\n?\s*=+",
        stdout,
        re.DOTALL,
    )
    if not summary_match:
        # Try alternative format
        summary_match = re.search(
            r"(\d+)\s+passed.*?in\s+[\d.]+s",
            stdout,
        )

    summary_text = summary_match.group(0) if summary_match else stdout

    passed_m = re.search(r"(\d+)\s+passed", summary_text)
    failed_m = re.search(r"(\d+)\s+failed", summary_text)
    errors_m = re.search(r"(\d+)\s+error", summary_text)
    skipped_m = re.search(r"(\d+)\s+skipped", summary_text)
    warnings_m = re.search(r"(\d+)\s+warning", summary_text)

    result.passed = int(passed_m.group(1)) if passed_m else 0
    result.failed = int(failed_m.group(1)) if failed_m else 0
    result.errors = int(errors_m.group(1)) if errors_m else 0
    result.skipped = int(skipped_m.group(1)) if skipped_m else 0
    result.warnings = int(warnings_m.group(1)) if warnings_m else 0

    # If no summary found but exit code is 0 and we got output, assume all passed
    if result.total == 0 and exit_code == 0 and "collected" in stdout:
        collected_m = re.search(r"collected\s+(\d+)\s+item", stdout)
        if collected_m:
            result.passed = int(collected_m.group(1))

    # Parse FAILED lines for failure details
    for line in stdout.splitlines():
        if line.startswith("FAILED "):
            test_name = line.split("FAILED ")[1].strip().split(" - ")[0]
            result.failures.append({"test": test_name, "detail": line})

    # Extract mode from output (look for mode indicators)
    mode_patterns = {
        "RAPID": r"(?i)(rapid.strike|mode.*rapid)",
        "DEEP": r"(?i)(deep.think|mode.*deep)",
        "ENSEMBLE": r"(?i)(mode.*ensemble)",
        "MEGAMIND": r"(?i)(mode.*megamind)",
        "GRAND JURY": r"(?i)(grand.jury|mode.*jury)",
    }
    for mode, pattern in mode_patterns.items():
        if re.search(pattern, stdout):
            result.mode = mode
            break

    # Extract confidence if present in output
    conf_match = re.search(r"confidence[:\s]+(\d+(?:\.\d+)?)", stdout, re.IGNORECASE)
    if conf_match:
        result.confidence = float(conf_match.group(1))

    # Extract latency if present
    lat_match = re.search(r"latency[:\s]+(\d+(?:\.\d+)?)\s*ms", stdout, re.IGNORECASE)
    if lat_match:
        result.latency_ms = float(lat_match.group(1))

    return result


def run_test_file(
    test_file: Path,
    suite_name: str,
    timeout: int = 300,
    model: str = "",
    verbose: bool = True,
) -> TestResult:
    """Run a single test file via pytest subprocess."""
    rel_path = test_file.relative_to(PROJECT_ROOT)
    test_name = str(rel_path)

    cmd = [
        sys.executable, "-m", "pytest",
        str(test_file),
        "-v",
        "--tb=short",
        "--no-header",
        "-q",
    ]

    # Add suite-specific -k filter
    suite_cfg = SUITES.get(suite_name, {})
    k_filter = suite_cfg.get("k")
    if k_filter and suite_name in ("e2e", "real-agent", "cross-rig"):
        cmd.extend(["-k", k_filter])

    env = os.environ.copy()
    if model:
        env["REASONING_SWARM_MODEL"] = model

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        duration = time.perf_counter() - t0
        result = _parse_pytest_output(proc.stdout, proc.stderr, proc.returncode, duration)
    except subprocess.TimeoutExpired:
        duration = time.perf_counter() - t0
        result = TestResult(
            suite=suite_name,
            name=test_name,
            exit_code=-1,
            duration_s=duration,
            stderr=f"TIMEOUT after {timeout}s",
        )
        result.failures.append({"test": test_name, "detail": f"Timed out after {timeout}s"})

    result.suite = suite_name
    result.name = test_name
    result.latency_ms = duration * 1000

    return result


def run_suite(
    suite_name: str,
    timeout: int = 300,
    model: str = "",
    verbose: bool = True,
) -> SuiteResult:
    """Run all tests in a suite."""
    suite_cfg = SUITES[suite_name]
    test_files = discover_tests(suite_name)

    suite_result = SuiteResult(
        suite_name=suite_name,
        description=suite_cfg["description"],
    )

    if not test_files:
        if verbose:
            print(f"  [{suite_name}] No test files found, skipping.")
        return suite_result

    t0 = time.perf_counter()
    for test_file in test_files:
        if verbose:
            print(f"  [{suite_name}] Running {test_file.name}...")
        result = run_test_file(test_file, suite_name, timeout=timeout, model=model, verbose=verbose)
        suite_result.tests.append(result)

        status = "PASS" if result.success else "FAIL"
        if verbose:
            print(
                f"  [{suite_name}] {status} {result.name}: "
                f"{result.passed} passed, {result.failed} failed, "
                f"{result.errors} errors ({result.duration_s:.1f}s)"
            )

    suite_result.duration_s = time.perf_counter() - t0
    return suite_result


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------

def run_suites_parallel(
    suite_names: list[str],
    timeout: int = 300,
    model: str = "",
    verbose: bool = True,
) -> list[SuiteResult]:
    """Run multiple suites concurrently."""
    results: list[SuiteResult] = [None] * len(suite_names)  # type: ignore

    with ThreadPoolExecutor(max_workers=min(len(suite_names), 4)) as executor:
        future_to_idx = {}
        for idx, suite_name in enumerate(suite_names):
            future = executor.submit(run_suite, suite_name, timeout, model, verbose)
            future_to_idx[future] = idx

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()

    return results


# ---------------------------------------------------------------------------
# Markdown report generation
# ---------------------------------------------------------------------------

def generate_markdown_report(report: BatchReport) -> str:
    """Generate a markdown summary report."""
    now = report.timestamp
    lines: list[str] = []

    # Header
    status_icon = "PASS" if report.success else "FAIL"
    lines.append(f"# Reasoning Swarm Batch Test Report")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    if report.model:
        lines.append(f"**Model:** {report.model}")
    lines.append(f"**Status:** {status_icon}")
    lines.append(f"**Duration:** {report.total_duration_s:.1f}s")
    lines.append("")

    # Overall summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Tests | {report.total} |")
    lines.append(f"| Passed | {report.passed} |")
    lines.append(f"| Failed | {report.failed} |")
    lines.append(f"| Errors | {report.errors} |")
    lines.append(f"| Skipped | {report.skipped} |")
    pass_rate = (report.passed / report.total * 100) if report.total > 0 else 0
    lines.append(f"| Pass Rate | {pass_rate:.1f}% |")
    lines.append("")

    # Suite breakdown
    lines.append("## Suite Breakdown")
    lines.append("")
    lines.append("| Suite | Tests | Passed | Failed | Errors | Duration | Status |")
    lines.append("|-------|-------|--------|--------|--------|----------|--------|")
    for suite in report.suites:
        status = "PASS" if suite.success else "FAIL"
        lines.append(
            f"| {suite.suite_name} | {suite.total} | {suite.passed} | "
            f"{suite.failed} | {suite.errors} | {suite.duration_s:.1f}s | {status} |"
        )
    lines.append("")

    # Mode distribution
    mode_dist = report.mode_distribution
    if mode_dist:
        lines.append("## Mode Distribution")
        lines.append("")
        lines.append("| Mode | Count |")
        lines.append("|------|-------|")
        for mode, count in mode_dist.items():
            lines.append(f"| {mode} | {count} |")
        lines.append("")

    # Average confidence
    avg_conf = report.avg_confidence
    if avg_conf > 0:
        lines.append("## Confidence")
        lines.append("")
        lines.append(f"**Average Confidence:** {avg_conf:.2f}")
        lines.append("")

    # Average latency
    avg_lat = report.avg_latency_ms
    if avg_lat > 0:
        lines.append("## Latency")
        lines.append("")
        lines.append(f"**Average Latency:** {avg_lat:.1f}ms")
        lines.append("")

    # Quality scores (per-suite pass rates)
    lines.append("## Quality Scores")
    lines.append("")
    lines.append("| Suite | Pass Rate | Quality |")
    lines.append("|-------|-----------|---------|")
    for suite in report.suites:
        if suite.total > 0:
            rate = suite.passed / suite.total * 100
            if rate >= 95:
                quality = "Excellent"
            elif rate >= 80:
                quality = "Good"
            elif rate >= 60:
                quality = "Fair"
            else:
                quality = "Poor"
            lines.append(f"| {suite.suite_name} | {rate:.1f}% | {quality} |")
    lines.append("")

    # Failure analysis
    all_failures = []
    for suite in report.suites:
        for test in suite.tests:
            for failure in test.failures:
                all_failures.append({
                    "suite": suite.suite_name,
                    "test_file": test.name,
                    **failure,
                })

    if all_failures:
        lines.append("## Failure Analysis")
        lines.append("")
        lines.append(f"**Total Failures:** {len(all_failures)}")
        lines.append("")
        for i, f in enumerate(all_failures, 1):
            lines.append(f"### Failure {i}: {f['test_file']}")
            lines.append("")
            lines.append(f"- **Suite:** {f['suite']}")
            lines.append(f"- **Test:** {f['test']}")
            if f.get("detail"):
                lines.append(f"- **Detail:** {f['detail']}")
            lines.append("")

    # Verdict
    lines.append("## Verdict")
    lines.append("")
    if report.success:
        lines.append(f"All **{report.total}** tests passed across **{len(report.suites)}** suites.")
    else:
        lines.append(
            f"**{report.failed + report.errors}** failures/errors "
            f"out of **{report.total}** tests across **{len(report.suites)}** suites."
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reasoning Swarm Batch Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cli.batch_test --suite all
  python -m cli.batch_test --suite real-agent --model mimo-v2-pro
  python -m cli.batch_test --suite benchmarks --parallel
  python -m cli.batch_test --suite unit --report
  python -m cli.batch_test --suite all --ci --timeout 120
        """,
    )
    parser.add_argument(
        "--suite",
        type=str,
        default="all",
        choices=["all"] + list(SUITES.keys()),
        help="Test suite to run (default: all)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        default=False,
        help="Run test suites concurrently where possible",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="",
        help="Model name for real-agent tests (e.g., mimo-v2-pro)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        default=False,
        help="Generate markdown summary report",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        default=False,
        help="CI mode: exit code only (suppress detailed output)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Per-test timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Path to write the markdown report (default: stdout)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verbose = not args.ci

    if verbose:
        print("=" * 60)
        print("  Reasoning Swarm Batch Test Runner")
        print("=" * 60)
        if args.model:
            print(f"  Model: {args.model}")
        print(f"  Timeout: {args.timeout}s")
        print(f"  Parallel: {args.parallel}")
        print()

    # Determine which suites to run
    if args.suite == "all":
        suite_names = list(SUITES.keys())
    else:
        suite_names = [args.suite]

    t0 = time.perf_counter()

    # Run suites
    if args.parallel and len(suite_names) > 1:
        if verbose:
            print(f"Running {len(suite_names)} suites in parallel...")
            print()
        suite_results = run_suites_parallel(
            suite_names,
            timeout=args.timeout,
            model=args.model,
            verbose=verbose,
        )
    else:
        suite_results = []
        for suite_name in suite_names:
            if verbose:
                print(f"Running suite: {suite_name}")
            result = run_suite(
                suite_name,
                timeout=args.timeout,
                model=args.model,
                verbose=verbose,
            )
            suite_results.append(result)
            if verbose:
                print()

    total_duration = time.perf_counter() - t0

    # Build report
    report = BatchReport(
        suites=suite_results,
        model=args.model,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        total_duration_s=total_duration,
    )

    # Generate and output report
    if args.report or args.output:
        md_report = generate_markdown_report(report)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(md_report)
            if verbose:
                print(f"Report written to {output_path}")
        else:
            print(md_report)

    # Print summary to stdout (unless --ci)
    if verbose:
        print()
        print("=" * 60)
        print(f"  RESULTS: {report.passed}/{report.total} passed "
              f"({report.failed} failed, {report.errors} errors)")
        print(f"  Duration: {total_duration:.1f}s")
        if report.success:
            print("  Status: ALL PASSED")
        else:
            print("  Status: FAILURES DETECTED")
        print("=" * 60)

    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())
