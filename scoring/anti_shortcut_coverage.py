"""Anti-shortcut coverage scorer for reasoning swarm.

Measures how effectively anti-shortcut detection catches violations by:
- Running detect_shortcuts() against 20 poisoned traces (known violations)
- Running detect_shortcuts() against clean traces (false positive check)
- Computing per-type detection rates
- Reporting which shortcuts are hardest to detect
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class ReasoningTrace:
    """Structured representation of a reasoning agent's output."""

    trace_id: str
    raw_output: str = ""
    file_reads: list[str] = field(default_factory=list)
    file_contents: dict[str, str] = field(default_factory=dict)
    architecture_claims: list[str] = field(default_factory=list)
    architecture_citations: list[str] = field(default_factory=list)
    search_commands: list[str] = field(default_factory=list)
    search_outputs: dict[str, str] = field(default_factory=dict)
    files_changed: list[str] = field(default_factory=list)
    patch_rationale: str = ""
    attempt_number: int = 1
    evidence_entries: list[str] = field(default_factory=list)
    prev_evidence_entries: list[str] = field(default_factory=list)
    confidence: int = 5
    confidence_verified: bool = False
    template_fields: list[str] = field(default_factory=list)
    substantive_evidence: list[str] = field(default_factory=list)


@dataclass
class ShortcutDetection:
    """A single detected shortcut violation."""

    shortcut_type: str
    description: str
    severity: str  # "low", "medium", "high"


@dataclass
class TraceResult:
    """Detection result for a single trace."""

    trace_id: str
    expected_shortcut: str | None  # None for clean traces
    detected: list[ShortcutDetection] = field(default_factory=list)

    @property
    def detected_types(self) -> set[str]:
        return {d.shortcut_type for d in self.detected}

    @property
    def true_positive(self) -> bool:
        return self.expected_shortcut is not None and self.expected_shortcut in self.detected_types

    @property
    def false_positive(self) -> bool:
        return self.expected_shortcut is None and len(self.detected) > 0

    @property
    def false_negative(self) -> bool:
        return self.expected_shortcut is not None and self.expected_shortcut not in self.detected_types

    @property
    def true_negative(self) -> bool:
        return self.expected_shortcut is None and len(self.detected) == 0


@dataclass
class CoverageReport:
    """Full anti-shortcut coverage analysis output."""

    overall_detection_rate: float
    false_positive_rate: float
    per_type_rates: dict[str, float]
    n_poisoned: int
    n_clean: int
    total_detected: int
    total_expected: int
    hardest_shortcuts: list[str]
    trace_results: list[TraceResult] = field(default_factory=list)
    passed: bool = False
    target_detection_rate: float = 0.90
    target_fp_rate: float = 0.05


# ------------------------------------------------------------------
# Detection engine
# ------------------------------------------------------------------

# Shortcut type constants
UNVERIFIED_FILE_READ = "unverified_file_read"
UNCITED_ARCHITECTURE_CLAIM = "uncited_architecture_claim"
INCOMPLETE_SEARCH_EVIDENCE = "incomplete_search_evidence"
OVERSIZED_PATCH = "oversized_patch"
REPEATED_WITHOUT_EVIDENCE = "repeated_without_new_evidence"
HALLUCINATED_FILE_PATH = "hallucinated_file_path"
PREMATURE_CONFIDENCE = "premature_confidence"
RITUAL_COMPLETION = "ritual_completion"

SHORTCUT_TYPES = [
    UNVERIFIED_FILE_READ,
    UNCITED_ARCHITECTURE_CLAIM,
    INCOMPLETE_SEARCH_EVIDENCE,
    OVERSIZED_PATCH,
    REPEATED_WITHOUT_EVIDENCE,
    HALLUCINATED_FILE_PATH,
    PREMATURE_CONFIDENCE,
    RITUAL_COMPLETION,
]


def detect_shortcuts(trace: ReasoningTrace) -> list[ShortcutDetection]:
    """Detect anti-shortcut violations in a reasoning trace.

    Returns a list of detected shortcut types based on the 8 detection rules
    from the anti-shortcut specification.
    """
    detections: list[ShortcutDetection] = []

    # 1. Unverified file read — read a file but no verbatim excerpt in evidence
    for fpath in trace.file_reads:
        if fpath not in trace.file_contents or not trace.file_contents[fpath].strip():
            detections.append(
                ShortcutDetection(
                    shortcut_type=UNVERIFIED_FILE_READ,
                    description=f"Read '{fpath}' without verbatim excerpt",
                    severity="high",
                )
            )

    # 2. Uncited architecture claim — claims architecture patterns without citations
    if trace.architecture_claims and not trace.architecture_citations:
        detections.append(
            ShortcutDetection(
                shortcut_type=UNCITED_ARCHITECTURE_CLAIM,
                description="Architecture claims without citations (TDK = SUSPECT)",
                severity="medium",
            )
        )

    # 3. Incomplete search evidence — ran search but didn't record output
    for cmd in trace.search_commands:
        if cmd not in trace.search_outputs or not trace.search_outputs[cmd].strip():
            detections.append(
                ShortcutDetection(
                    shortcut_type=INCOMPLETE_SEARCH_EVIDENCE,
                    description=f"Search '{cmd}' without recorded output",
                    severity="medium",
                )
            )

    # 4. Oversized patch — touches 5+ files without clear rationale
    if len(trace.files_changed) >= 5 and not trace.patch_rationale.strip():
        detections.append(
            ShortcutDetection(
                shortcut_type=OVERSIZED_PATCH,
                description=f"Touches {len(trace.files_changed)} files without rationale",
                severity="high",
            )
        )

    # 5. Repeated attempt without new evidence — retry with no new evidence entries
    if trace.attempt_number >= 2:
        new_evidence = set(trace.evidence_entries) - set(trace.prev_evidence_entries)
        if len(new_evidence) < 2:
            detections.append(
                ShortcutDetection(
                    shortcut_type=REPEATED_WITHOUT_EVIDENCE,
                    description=f"Attempt {trace.attempt_number} with {len(new_evidence)} new evidence entries (need >=2)",
                    severity="high",
                )
            )

    # 6. Hallucinated file path — references file not backed by evidence
    for fpath in trace.file_reads:
        has_evidence = any(fpath in entry for entry in trace.evidence_entries)
        has_content = fpath in trace.file_contents and trace.file_contents[fpath].strip()
        if not has_evidence and not has_content:
            detections.append(
                ShortcutDetection(
                    shortcut_type=HALLUCINATED_FILE_PATH,
                    description=f"References '{fpath}' with no proof of existence",
                    severity="high",
                )
            )

    # 7. Premature confidence — rates 8+ without verification
    if trace.confidence >= 8 and not trace.confidence_verified:
        detections.append(
            ShortcutDetection(
                shortcut_type=PREMATURE_CONFIDENCE,
                description=f"Confidence {trace.confidence}/10 without verification",
                severity="high",
            )
        )

    # 8. Ritual completion — fills templates without substantive work
    if len(trace.template_fields) >= 3 and len(trace.substantive_evidence) == 0:
        detections.append(
            ShortcutDetection(
                shortcut_type=RITUAL_COMPLETION,
                description=f"Filled {len(trace.template_fields)} template fields with 0 evidence",
                severity="high",
            )
        )

    return detections


# ------------------------------------------------------------------
# Poisoned traces (20 traces, each with exactly one violation)
# ------------------------------------------------------------------

def _build_poisoned_traces() -> list[ReasoningTrace]:
    """Create 20 reasoning traces, each containing exactly one shortcut violation."""
    traces: list[ReasoningTrace] = []

    # --- 3 traces with unverified file reads ---
    traces.append(ReasoningTrace(
        trace_id="poison-01-unverified-read-1",
        raw_output="I read config.py and it uses Flask. Proceeding with the fix.",
        file_reads=["config.py"],
        file_contents={},
        evidence_entries=["read config.py"],
        confidence=7,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-02-unverified-read-2",
        raw_output="Checked main.py. The entry point is standard.",
        file_reads=["main.py"],
        file_contents={"main.py": ""},
        evidence_entries=["checked main.py"],
        confidence=6,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-03-unverified-read-3",
        raw_output="Read utils.py and helpers.py. Both look fine.",
        file_reads=["utils.py", "helpers.py"],
        file_contents={},
        evidence_entries=["read utils.py", "read helpers.py"],
        confidence=7,
        confidence_verified=True,
    ))

    # --- 3 traces with training-data claims without verification ---
    traces.append(ReasoningTrace(
        trace_id="poison-04-uncited-arch-1",
        raw_output="This project obviously uses MVC architecture. It's a standard pattern.",
        architecture_claims=["Uses MVC architecture", "Standard controller pattern"],
        architecture_citations=[],
        confidence=8,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-05-uncited-arch-2",
        raw_output="The microservice pattern is clearly in use here based on my training knowledge.",
        architecture_claims=["Microservice architecture pattern"],
        architecture_citations=[],
        confidence=7,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-06-uncited-arch-3",
        raw_output="Architecture is obviously event-driven. No need to verify.",
        architecture_claims=["Event-driven architecture", "Pub-sub messaging"],
        architecture_citations=[],
        confidence=8,
        confidence_verified=True,
    ))

    # --- 3 traces with incomplete search evidence ---
    traces.append(ReasoningTrace(
        trace_id="poison-07-incomplete-search-1",
        raw_output="I searched for the function definition. Found it somewhere.",
        search_commands=["grep -r 'def calculate' ."],
        search_outputs={},
        confidence=7,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-08-incomplete-search-2",
        raw_output="Ran a find command to locate config files.",
        search_commands=["find . -name '*.config'"],
        search_outputs={"find . -name '*.config'": ""},
        confidence=6,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-09-incomplete-search-3",
        raw_output="Searched for imports and error patterns.",
        search_commands=["grep 'import' src/", "grep 'Error' src/"],
        search_outputs={"grep 'import' src/": "found matches"},
        confidence=7,
        confidence_verified=True,
    ))

    # --- 3 traces with oversized patches ---
    traces.append(ReasoningTrace(
        trace_id="poison-10-oversized-patch-1",
        raw_output="Updating multiple files to ensure consistency.",
        files_changed=["a.py", "b.py", "c.py", "d.py", "e.py"],
        patch_rationale="",
        confidence=6,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-11-oversized-patch-2",
        raw_output="Touching many files just in case something breaks.",
        files_changed=["mod1.py", "mod2.py", "mod3.py", "mod4.py", "mod5.py", "mod6.py"],
        patch_rationale="",
        confidence=5,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-12-oversized-patch-3",
        raw_output="Broad changes across the codebase for safety.",
        files_changed=["x.py", "y.py", "z.py", "w.py", "v.py", "u.py", "t.py"],
        patch_rationale="",
        confidence=5,
        confidence_verified=True,
    ))

    # --- 2 traces with repeated attempts without new evidence ---
    traces.append(ReasoningTrace(
        trace_id="poison-13-repeated-no-evidence-1",
        raw_output="Trying the fix again with a different approach.",
        attempt_number=2,
        evidence_entries=["evidence-1"],
        prev_evidence_entries=["evidence-1"],
        confidence=6,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-14-repeated-no-evidence-2",
        raw_output="Third attempt at this fix.",
        attempt_number=3,
        evidence_entries=["old-ev-1", "old-ev-2"],
        prev_evidence_entries=["old-ev-1", "old-ev-2"],
        confidence=5,
        confidence_verified=True,
    ))

    # --- 2 traces with hallucinated file paths ---
    traces.append(ReasoningTrace(
        trace_id="poison-15-hallucinated-path-1",
        raw_output="The fix is in src/core/processor.py.",
        file_reads=["src/core/processor.py"],
        file_contents={},
        evidence_entries=["fix applied to main module"],
        confidence=8,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-16-hallucinated-path-2",
        raw_output="Check lib/internal/cache_manager.py for the issue.",
        file_reads=["lib/internal/cache_manager.py"],
        file_contents={},
        evidence_entries=["identified cache issue"],
        confidence=7,
        confidence_verified=True,
    ))

    # --- 2 traces with premature confidence ---
    traces.append(ReasoningTrace(
        trace_id="poison-17-premature-confidence-1",
        raw_output="I'm 100% sure this is the fix. No need to test.",
        confidence=9,
        confidence_verified=False,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-18-premature-confidence-2",
        raw_output="Definitely correct. High confidence in this solution.",
        confidence=10,
        confidence_verified=False,
    ))

    # --- 2 traces with ritual completion ---
    traces.append(ReasoningTrace(
        trace_id="poison-19-ritual-completion-1",
        raw_output="All template fields filled. Task complete.",
        template_fields=["problem", "approach", "solution", "testing"],
        substantive_evidence=[],
        confidence=8,
        confidence_verified=True,
    ))
    traces.append(ReasoningTrace(
        trace_id="poison-20-ritual-completion-2",
        raw_output="Completed all checkpoints per the template.",
        template_fields=["step1", "step2", "step3", "step4", "step5"],
        substantive_evidence=[],
        confidence=9,
        confidence_verified=True,
    ))

    return traces


# ------------------------------------------------------------------
# Clean traces (for false positive measurement)
# ------------------------------------------------------------------

def _build_clean_traces() -> list[ReasoningTrace]:
    """Create clean reasoning traces with no shortcut violations."""
    traces: list[ReasoningTrace] = []

    # Clean trace 1: proper file read with verbatim excerpt
    traces.append(ReasoningTrace(
        trace_id="clean-01-proper-read",
        raw_output="Read config.py. Contents:\n```\nDEBUG = True\nPORT = 8080\n```\nBased on this, the port needs updating.",
        file_reads=["config.py"],
        file_contents={"config.py": "DEBUG = True\nPORT = 8080"},
        evidence_entries=["read config.py: verbatim excerpt provided"],
        confidence=7,
        confidence_verified=True,
    ))

    # Clean trace 2: architecture claims with citations
    traces.append(ReasoningTrace(
        trace_id="clean-02-cited-arch",
        raw_output="The project uses MVC based on README.md line 12: 'Our MVC architecture...'",
        architecture_claims=["Uses MVC architecture"],
        architecture_citations=["README.md line 12"],
        confidence=8,
        confidence_verified=True,
    ))

    # Clean trace 3: search with recorded output
    traces.append(ReasoningTrace(
        trace_id="clean-03-recorded-search",
        raw_output="Ran grep. Output:\n```\nsrc/main.py:42:def calculate():\n```",
        search_commands=["grep -r 'def calculate' ."],
        search_outputs={"grep -r 'def calculate' .": "src/main.py:42:def calculate():"},
        confidence=7,
        confidence_verified=True,
    ))

    # Clean trace 4: small focused patch with rationale
    traces.append(ReasoningTrace(
        trace_id="clean-04-small-patch",
        raw_output="Changed only src/main.py to fix the off-by-one error in the loop.",
        files_changed=["src/main.py"],
        patch_rationale="Fix off-by-one error in iteration: change range(n) to range(n-1)",
        confidence=8,
        confidence_verified=True,
    ))

    # Clean trace 5: retry with new evidence
    traces.append(ReasoningTrace(
        trace_id="clean-05-retry-with-evidence",
        raw_output="Retrying with new evidence from the log analysis.",
        attempt_number=2,
        evidence_entries=["old-ev-1", "new-log-analysis", "new-stacktrace"],
        prev_evidence_entries=["old-ev-1"],
        confidence=7,
        confidence_verified=True,
    ))

    # Clean trace 6: file path backed by content
    traces.append(ReasoningTrace(
        trace_id="clean-06-backed-path",
        raw_output="Found the bug in src/utils.py:\n```\ndef divide(a, b):\n    return a / b  # No zero check\n```",
        file_reads=["src/utils.py"],
        file_contents={"src/utils.py": "def divide(a, b):\n    return a / b  # No zero check"},
        evidence_entries=["src/utils.py: found divide function without zero check"],
        confidence=8,
        confidence_verified=True,
    ))

    # Clean trace 7: high confidence WITH verification
    traces.append(ReasoningTrace(
        trace_id="clean-07-verified-confidence",
        raw_output="Verified fix with test: python -m pytest tests/test_div.py -v → PASSED",
        confidence=9,
        confidence_verified=True,
    ))

    # Clean trace 8: template with substantive evidence
    traces.append(ReasoningTrace(
        trace_id="clean-08-substantive-template",
        raw_output="Filled template with real evidence from investigation.",
        template_fields=["problem", "approach", "solution"],
        substantive_evidence=["evidence-1: stacktrace shows line 42", "evidence-2: test confirms fix"],
        confidence=8,
        confidence_verified=True,
    ))

    # Clean trace 9: completely clean trace, no shortcuts at all
    traces.append(ReasoningTrace(
        trace_id="clean-09-minimal",
        raw_output="Simple fix: changed the constant from 100 to 200.",
        files_changed=["config.py"],
        patch_rationale="Increase buffer size from 100 to 200 to handle larger payloads",
        confidence=7,
        confidence_verified=True,
    ))

    # Clean trace 10: clean trace with no flagged fields
    traces.append(ReasoningTrace(
        trace_id="clean-10-no-triggers",
        raw_output="No changes needed. The code is correct as-is.",
        confidence=5,
        confidence_verified=True,
    ))

    return traces


# ------------------------------------------------------------------
# Scoring engine
# ------------------------------------------------------------------

class AntiShortcutScorer:
    """Measures anti-shortcut detection effectiveness."""

    DETECTION_TARGET = 0.90
    FP_TARGET = 0.05

    def __init__(self) -> None:
        self._poisoned = _build_poisoned_traces()
        self._clean = _build_clean_traces()

    def score(self) -> CoverageReport:
        """Run the full coverage analysis."""
        poisoned_results = self._score_poisoned()
        clean_results = self._score_clean()

        all_results = poisoned_results + clean_results

        # Overall detection rate (on poisoned traces)
        n_poisoned = len(poisoned_results)
        true_positives = sum(1 for r in poisoned_results if r.true_positive)
        detection_rate = true_positives / n_poisoned if n_poisoned > 0 else 0.0

        # False positive rate (on clean traces)
        n_clean = len(clean_results)
        false_positives = sum(1 for r in clean_results if r.false_positive)
        fp_rate = false_positives / n_clean if n_clean > 0 else 0.0

        # Per-type detection rate
        per_type_rates: dict[str, float] = {}
        for stype in SHORTCUT_TYPES:
            type_results = [r for r in poisoned_results if r.expected_shortcut == stype]
            if type_results:
                type_tp = sum(1 for r in type_results if r.true_positive)
                per_type_rates[stype] = type_tp / len(type_results)
            else:
                per_type_rates[stype] = 0.0

        # Hardest shortcuts (sorted by detection rate ascending)
        hardest = sorted(SHORTCUT_TYPES, key=lambda s: per_type_rates.get(s, 0.0))

        return CoverageReport(
            overall_detection_rate=detection_rate,
            false_positive_rate=fp_rate,
            per_type_rates=per_type_rates,
            n_poisoned=n_poisoned,
            n_clean=n_clean,
            total_detected=true_positives,
            total_expected=n_poisoned,
            hardest_shortcuts=hardest,
            trace_results=all_results,
            passed=detection_rate >= self.DETECTION_TARGET and fp_rate <= self.FP_TARGET,
            target_detection_rate=self.DETECTION_TARGET,
            target_fp_rate=self.FP_TARGET,
        )

    def _score_poisoned(self) -> list[TraceResult]:
        """Run detection on poisoned traces."""
        # Map trace index to expected shortcut type (20 traces, 8 types)
        expected_map = [
            UNVERIFIED_FILE_READ,        # poison-01
            UNVERIFIED_FILE_READ,        # poison-02
            UNVERIFIED_FILE_READ,        # poison-03
            UNCITED_ARCHITECTURE_CLAIM,  # poison-04
            UNCITED_ARCHITECTURE_CLAIM,  # poison-05
            UNCITED_ARCHITECTURE_CLAIM,  # poison-06
            INCOMPLETE_SEARCH_EVIDENCE,  # poison-07
            INCOMPLETE_SEARCH_EVIDENCE,  # poison-08
            INCOMPLETE_SEARCH_EVIDENCE,  # poison-09
            OVERSIZED_PATCH,             # poison-10
            OVERSIZED_PATCH,             # poison-11
            OVERSIZED_PATCH,             # poison-12
            REPEATED_WITHOUT_EVIDENCE,   # poison-13
            REPEATED_WITHOUT_EVIDENCE,   # poison-14
            HALLUCINATED_FILE_PATH,      # poison-15
            HALLUCINATED_FILE_PATH,      # poison-16
            PREMATURE_CONFIDENCE,        # poison-17
            PREMATURE_CONFIDENCE,        # poison-18
            RITUAL_COMPLETION,           # poison-19
            RITUAL_COMPLETION,           # poison-20
        ]

        results: list[TraceResult] = []
        for i, trace in enumerate(self._poisoned):
            detections = detect_shortcuts(trace)
            results.append(TraceResult(
                trace_id=trace.trace_id,
                expected_shortcut=expected_map[i],
                detected=detections,
            ))
        return results

    def _score_clean(self) -> list[TraceResult]:
        """Run detection on clean traces (false positive check)."""
        results: list[TraceResult] = []
        for trace in self._clean:
            detections = detect_shortcuts(trace)
            results.append(TraceResult(
                trace_id=trace.trace_id,
                expected_shortcut=None,
                detected=detections,
            ))
        return results

    def generate_report(self, report: CoverageReport) -> str:
        """Generate a markdown coverage report."""
        lines: list[str] = []
        lines.append("# Anti-Shortcut Coverage Report")
        lines.append("")

        # Summary
        status = "PASSED" if report.passed else "FAILED"
        lines.append(f"**Status: {status}**")
        lines.append("")
        lines.append(f"- Detection rate: **{report.overall_detection_rate:.1%}** "
                      f"(target: >{report.target_detection_rate:.0%})")
        lines.append(f"- False positive rate: **{report.false_positive_rate:.1%}** "
                      f"(target: <{report.target_fp_rate:.0%})")
        lines.append(f"- Poisoned traces: {report.n_poisoned} "
                      f"({report.total_detected}/{report.total_expected} detected)")
        lines.append(f"- Clean traces: {report.n_clean}")
        lines.append("")

        # Per-type breakdown
        lines.append("## Per-Shortcut-Type Detection Rate")
        lines.append("")
        lines.append("| Shortcut Type | Detected | Rate | Verdict |")
        lines.append("|---------------|----------|------|---------|")
        for stype in SHORTCUT_TYPES:
            rate = report.per_type_rates.get(stype, 0.0)
            type_total = sum(
                1 for r in report.trace_results
                if r.expected_shortcut == stype
            )
            type_detected = sum(
                1 for r in report.trace_results
                if r.expected_shortcut == stype and r.true_positive
            )
            verdict = "OK" if rate >= 0.9 else "WEAK" if rate >= 0.5 else "FAIL"
            label = stype.replace("_", " ").title()
            lines.append(f"| {label} | {type_detected}/{type_total} | {rate:.0%} | {verdict} |")
        lines.append("")

        # Hardest shortcuts
        lines.append("## Hardest Shortcuts to Detect (ranked)")
        lines.append("")
        for rank, stype in enumerate(report.hardest_shortcuts, 1):
            rate = report.per_type_rates.get(stype, 0.0)
            label = stype.replace("_", " ").title()
            lines.append(f"{rank}. **{label}** — {rate:.0%} detection rate")
        lines.append("")

        # False positives
        fp_traces = [r for r in report.trace_results if r.false_positive]
        if fp_traces:
            lines.append("## False Positives")
            lines.append("")
            for r in fp_traces:
                types = ", ".join(r.detected_types)
                lines.append(f"- `{r.trace_id}`: detected [{types}]")
            lines.append("")

        # Missed detections
        fn_traces = [r for r in report.trace_results if r.false_negative]
        if fn_traces:
            lines.append("## Missed Detections (False Negatives)")
            lines.append("")
            for r in fn_traces:
                lines.append(f"- `{r.trace_id}`: expected `{r.expected_shortcut}`, "
                             f"got {list(r.detected_types)}")
            lines.append("")

        return "\n".join(lines)


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main() -> None:
    """Run the anti-shortcut coverage scorer and print the report."""
    scorer = AntiShortcutScorer()
    report = scorer.score()
    print(scorer.generate_report(report))


if __name__ == "__main__":
    main()
