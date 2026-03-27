"""Trace completeness scorer for reasoning swarm.

Evaluates reasoning trace quality across five dimensions:
1. Structure — Are all required sections/checkpoints present?
2. Substance — Are fields filled with real content (not placeholders)?
3. Coherence — Do later techniques reference earlier ones?
4. Specificity — Are recommendations concrete (file names, function names, line numbers)?
5. Honesty — Is confidence calibrated to evidence quality?
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from scoring.anti_shortcut_coverage import ReasoningTrace


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

GRADE_THRESHOLDS = [
    (9.0, "A"),
    (7.5, "B"),
    (6.0, "C"),
    (4.0, "D"),
    (0.0, "F"),
]

DIMENSION_WEIGHTS = {
    "structure": 0.20,
    "substance": 0.25,
    "coherence": 0.20,
    "specificity": 0.20,
    "honesty": 0.15,
}


@dataclass
class QualityReport:
    """Quality assessment of a reasoning trace."""

    trace_id: str
    dimensions: dict[str, float] = field(default_factory=dict)
    overall: float = 0.0
    issues: list[str] = field(default_factory=list)
    grade: str = "F"

    def __repr__(self) -> str:
        dims = ", ".join(f"{k}={v:.1f}" for k, v in self.dimensions.items())
        return (
            f"QualityReport({self.trace_id}, overall={self.overall:.1f}, "
            f"grade={self.grade}, dims=[{dims}], issues={len(self.issues)})"
        )


# ------------------------------------------------------------------
# Placeholder detection
# ------------------------------------------------------------------

PLACEHOLDER_PATTERNS = [
    re.compile(r"^\s*(TODO|TBD|FIXME|XXX|N/A|PLACEHOLDER|TBD)\s*$", re.IGNORECASE),
    re.compile(r"^\s*-\s*$"),
    re.compile(r"^\s*<.*?>\s*$"),
    re.compile(r"^\s*\.{3,}\s*$"),
]


def _is_placeholder(text: str) -> bool:
    """Check if a string is a placeholder rather than real content."""
    if not text or not text.strip():
        return True
    for pat in PLACEHOLDER_PATTERNS:
        if pat.match(text.strip()):
            return True
    return False


def _has_concrete_references(text: str) -> bool:
    """Check if text contains concrete references (file paths, line numbers, function names)."""
    if not text:
        return False
    # File path patterns
    if re.search(r'\b[\w/]+\.\w{1,5}\b', text):
        return True
    # Line number references
    if re.search(r'line\s+\d+|:\d+|#L\d+', text, re.IGNORECASE):
        return True
    # Function/method references
    if re.search(r'\b(def|function|class|method|fn)\s+\w+', text):
        return True
    return False


# ------------------------------------------------------------------
# Dimension scorers
# ------------------------------------------------------------------

def _score_structure(trace: ReasoningTrace) -> tuple[float, list[str]]:
    """Score structure: are required sections/checkpoints present?

    Checks for presence of key trace components that indicate
    a thorough reasoning process was followed.
    """
    score = 10.0
    issues: list[str] = []

    # Raw output must exist and be non-trivial
    if not trace.raw_output.strip():
        score -= 4.0
        issues.append("Structure: raw_output is empty")
    elif len(trace.raw_output.strip()) < 20:
        score -= 3.0
        issues.append("Structure: raw_output is suspiciously short (< 20 chars)")
    elif len(trace.raw_output.strip()) < 50:
        score -= 1.0
        issues.append("Structure: raw_output is brief (< 50 chars)")

    # Should have at least one form of investigation evidence
    has_investigation = bool(
        trace.file_reads or trace.search_commands or trace.evidence_entries
    )
    if not has_investigation:
        score -= 3.5
        issues.append("Structure: no investigation evidence (no file reads, searches, or evidence entries)")

    # If files were changed, there should be rationale or evidence
    if trace.files_changed and not trace.patch_rationale.strip() and not trace.evidence_entries:
        score -= 2.0
        issues.append("Structure: files changed but no patch rationale or evidence")

    # If template fields are used, substantive evidence should accompany them
    if trace.template_fields and not trace.substantive_evidence:
        score -= 2.0
        issues.append("Structure: template fields present without substantive evidence")

    # All placeholder evidence is structurally equivalent to no evidence
    real_evidence = [e for e in trace.evidence_entries if not _is_placeholder(e)]
    if trace.evidence_entries and not real_evidence:
        score -= 2.0
        issues.append("Structure: evidence entries are all placeholders")

    return max(0.0, score), issues


def _score_substance(trace: ReasoningTrace) -> tuple[float, list[str]]:
    """Score substance: are fields filled with real content, not placeholders?"""
    score = 10.0
    issues: list[str] = []

    # Check raw_output for placeholder patterns
    if _is_placeholder(trace.raw_output):
        score -= 4.0
        issues.append("Substance: raw_output is a placeholder")

    # Check file_contents values
    empty_contents = [
        fpath for fpath, content in trace.file_contents.items()
        if _is_placeholder(content)
    ]
    if empty_contents:
        penalty = min(3.0, 1.0 * len(empty_contents))
        score -= penalty
        issues.append(
            f"Substance: {len(empty_contents)} file_contents entries are empty/placeholder "
            f"({', '.join(empty_contents[:3])})"
        )

    # Check evidence entries — placeholders are penalized
    placeholder_evidence = [e for e in trace.evidence_entries if _is_placeholder(e)]
    if placeholder_evidence:
        penalty = min(3.0, 1.0 * len(placeholder_evidence))
        score -= penalty
        issues.append(f"Substance: {len(placeholder_evidence)} evidence entries are placeholders")

    # Having zero real evidence when the trace claims any investigation is hollow
    real_evidence = [e for e in trace.evidence_entries if not _is_placeholder(e)]
    has_investigation_claims = bool(trace.file_reads or trace.search_commands or trace.files_changed)
    if has_investigation_claims and not real_evidence:
        score -= 3.0
        issues.append("Substance: investigation claims made but no real evidence entries")

    # Check search outputs
    empty_search_outputs = [
        cmd for cmd in trace.search_commands
        if cmd not in trace.search_outputs or _is_placeholder(trace.search_outputs.get(cmd, ""))
    ]
    if empty_search_outputs:
        penalty = min(2.0, 0.5 * len(empty_search_outputs))
        score -= penalty
        issues.append(f"Substance: {len(empty_search_outputs)} search commands have empty outputs")

    # Check patch rationale
    if trace.files_changed and _is_placeholder(trace.patch_rationale):
        score -= 1.5
        issues.append("Substance: patch_rationale is empty despite files being changed")

    return max(0.0, score), issues


def _score_coherence(trace: ReasoningTrace) -> tuple[float, list[str]]:
    """Score coherence: do later techniques reference earlier ones?"""
    score = 10.0
    issues: list[str] = []

    # If files were read, evidence or output should reference them
    if trace.file_reads:
        referenced = set()
        for fpath in trace.file_reads:
            for entry in trace.evidence_entries:
                if fpath in entry:
                    referenced.add(fpath)
                    break
        unreferenced = set(trace.file_reads) - referenced
        # Also check file_contents as a form of reference
        unreferenced -= set(trace.file_contents.keys())
        if unreferenced:
            penalty = min(3.0, 1.0 * len(unreferenced))
            score -= penalty
            issues.append(
                f"Coherence: {len(unreferenced)} file reads not referenced in evidence "
                f"({', '.join(list(unreferenced)[:3])})"
            )

    # Architecture claims should cite sources
    if trace.architecture_claims and not trace.architecture_citations:
        score -= 2.5
        issues.append("Coherence: architecture claims lack citations")

    # Files changed should connect to search results or file reads
    if trace.files_changed:
        changed_set = set(trace.files_changed)
        read_set = set(trace.file_reads)
        search_hit = set()
        for cmd, output in trace.search_outputs.items():
            for fpath in changed_set:
                if fpath in output:
                    search_hit.add(fpath)
        connected = read_set | search_hit
        unconnected = changed_set - connected
        if unconnected and len(changed_set) >= 2:
            penalty = min(2.0, 0.5 * len(unconnected))
            score -= penalty
            issues.append(
                f"Coherence: {len(unconnected)} changed files not connected to reads/searches "
                f"({', '.join(list(unconnected)[:3])})"
            )

    # Retry should reference previous evidence
    if trace.attempt_number >= 2:
        overlap = set(trace.evidence_entries) & set(trace.prev_evidence_entries)
        new_evidence = set(trace.evidence_entries) - set(trace.prev_evidence_entries)
        if not overlap and trace.prev_evidence_entries:
            score -= 1.0
            issues.append("Coherence: retry has no overlap with previous evidence")

    return max(0.0, score), issues


def _score_specificity(trace: ReasoningTrace) -> tuple[float, list[str]]:
    """Score specificity: are recommendations concrete?"""
    score = 10.0
    issues: list[str] = []

    # Check raw_output for concrete references
    if trace.raw_output and not _has_concrete_references(trace.raw_output):
        score -= 3.0
        issues.append("Specificity: raw_output lacks concrete references (file names, line numbers, functions)")

    # Check patch rationale for specificity
    if trace.files_changed and trace.patch_rationale:
        if not _has_concrete_references(trace.patch_rationale):
            score -= 2.0
            issues.append("Specificity: patch_rationale lacks concrete references")

    # Check evidence entries for specificity
    if trace.evidence_entries:
        concrete_count = sum(1 for e in trace.evidence_entries if _has_concrete_references(e))
        concrete_ratio = concrete_count / len(trace.evidence_entries)
        if concrete_ratio < 0.3 and len(trace.evidence_entries) >= 2:
            score -= 2.0
            issues.append(
                f"Specificity: only {concrete_count}/{len(trace.evidence_entries)} "
                f"evidence entries contain concrete references"
            )

    # Architecture claims should be specific
    if trace.architecture_claims:
        specific_claims = sum(1 for c in trace.architecture_claims if _has_concrete_references(c))
        if specific_claims == 0:
            score -= 1.5
            issues.append("Specificity: architecture claims lack specific references")

    return max(0.0, score), issues


def _score_honesty(trace: ReasoningTrace) -> tuple[float, list[str]]:
    """Score honesty: is confidence calibrated to evidence quality?"""
    score = 10.0
    issues: list[str] = []

    evidence_strength = len(trace.evidence_entries) + len(trace.substantive_evidence)

    # High confidence (8+) requires strong evidence or verification
    if trace.confidence >= 8:
        if not trace.confidence_verified and evidence_strength < 2:
            score -= 4.0
            issues.append(
                f"Honesty: confidence {trace.confidence}/10 without verification "
                f"and only {evidence_strength} evidence entries"
            )
        elif not trace.confidence_verified:
            score -= 2.5
            issues.append(f"Honesty: confidence {trace.confidence}/10 without verification")
        elif not trace.substantive_evidence:
            # Verified but no substantive evidence
            real_entries = [e for e in trace.evidence_entries if not _is_placeholder(e)]
            if not real_entries:
                score -= 3.0
                issues.append(
                    f"Honesty: confidence {trace.confidence}/10 verified but no substantive evidence"
                )
            elif len(real_entries) < 2:
                score -= 1.5
                issues.append(
                    f"Honesty: confidence {trace.confidence}/10 with thin evidence ({len(real_entries)} real entries)"
                )

    # Medium-high confidence (6-7) should have some evidence
    elif trace.confidence >= 6:
        if evidence_strength == 0 and not trace.confidence_verified:
            score -= 2.5
            issues.append(
                f"Honesty: confidence {trace.confidence}/10 with no evidence and no verification"
            )
        elif evidence_strength == 0:
            score -= 1.0
            issues.append(
                f"Honesty: confidence {trace.confidence}/10 with no evidence entries"
            )

    # Very low confidence (1-3) with lots of evidence may indicate under-confidence
    # but that's not dishonest, so no penalty

    # Check for premature confidence using anti-shortcut heuristic
    if trace.confidence >= 8 and not trace.confidence_verified:
        has_real_investigation = bool(
            trace.file_contents or trace.search_outputs or trace.substantive_evidence
        )
        if not has_real_investigation:
            score -= 2.0
            issues.append(
                "Honesty: high confidence without any verifiable investigation results"
            )

    return max(0.0, score), issues


# ------------------------------------------------------------------
# Main scoring function
# ------------------------------------------------------------------

def score_trace(trace: ReasoningTrace) -> QualityReport:
    """Score a reasoning trace across five quality dimensions.

    Returns a QualityReport with per-dimension scores (0-10),
    a weighted overall score, specific issues found, and a letter grade.
    """
    all_issues: list[str] = []
    dimensions: dict[str, float] = {}

    struct_score, struct_issues = _score_structure(trace)
    dimensions["structure"] = struct_score
    all_issues.extend(struct_issues)

    sub_score, sub_issues = _score_substance(trace)
    dimensions["substance"] = sub_score
    all_issues.extend(sub_issues)

    coh_score, coh_issues = _score_coherence(trace)
    dimensions["coherence"] = coh_score
    all_issues.extend(coh_issues)

    spec_score, spec_issues = _score_specificity(trace)
    dimensions["specificity"] = spec_score
    all_issues.extend(spec_issues)

    hon_score, hon_issues = _score_honesty(trace)
    dimensions["honesty"] = hon_score
    all_issues.extend(hon_issues)

    overall = sum(
        dimensions[dim] * weight for dim, weight in DIMENSION_WEIGHTS.items()
    )

    grade = "F"
    for threshold, letter in GRADE_THRESHOLDS:
        if overall >= threshold:
            grade = letter
            break

    return QualityReport(
        trace_id=trace.trace_id,
        dimensions=dimensions,
        overall=round(overall, 2),
        issues=all_issues,
        grade=grade,
    )


# ------------------------------------------------------------------
# Sample traces
# ------------------------------------------------------------------

def _build_sample_traces() -> list[ReasoningTrace]:
    """Create 10 sample reasoning traces with varying quality levels."""
    traces: list[ReasoningTrace] = []

    # 1. Excellent trace — thorough investigation, specific, honest
    traces.append(ReasoningTrace(
        trace_id="sample-01-excellent",
        raw_output=(
            "Investigated src/handler.py:42 — the request validation is missing "
            "a bounds check on the 'limit' parameter. Verified by reading "
            "src/validators.py:15 which shows the schema accepts any integer. "
            "Fix: add `max(100)` clamp in handler.py:45."
        ),
        file_reads=["src/handler.py", "src/validators.py"],
        file_contents={
            "src/handler.py": "def handle_request(req):\n    limit = req.get('limit')\n    results = db.query(limit=limit)",
            "src/validators.py": "class RequestSchema:\n    fields = {'limit': Integer()}",
        },
        architecture_claims=["Uses request-validation pattern"],
        architecture_citations=["src/validators.py:1-20 shows centralized validation"],
        search_commands=["grep 'def handle' src/"],
        search_outputs={"grep 'def handle' src/": "src/handler.py:42:def handle_request(req):"},
        files_changed=["src/handler.py"],
        patch_rationale="Add max(100) clamp to limit parameter in src/handler.py:45 to prevent unbounded queries",
        evidence_entries=[
            "src/handler.py:42 — request handler reads limit without bounds check",
            "src/validators.py:15 — Integer() schema has no max constraint",
            "grep 'def handle' src/ — confirmed handler location",
        ],
        confidence=9,
        confidence_verified=True,
        substantive_evidence=["src/handler.py:42 investigation", "src/validators.py:15 schema check"],
    ))

    # 2. Good trace — solid but missing some specifics
    traces.append(ReasoningTrace(
        trace_id="sample-02-good",
        raw_output=(
            "Read config.py and main.py. The app uses Flask with a standard "
            "blueprint pattern. The timeout setting in config.py needs updating "
            "from 30 to 60 seconds."
        ),
        file_reads=["config.py", "main.py"],
        file_contents={
            "config.py": "TIMEOUT = 30\nDEBUG = True\nHOST = '0.0.0.0'",
            "main.py": "from flask import Flask\napp = Flask(__name__)",
        },
        architecture_claims=["Uses Flask blueprint pattern"],
        architecture_citations=["main.py:2 — Flask import confirms framework"],
        search_commands=["grep 'TIMEOUT' ."],
        search_outputs={"grep 'TIMEOUT' .": "config.py:1:TIMEOUT = 30"},
        files_changed=["config.py"],
        patch_rationale="Increase timeout from 30 to 60 to handle slow upstream responses",
        evidence_entries=[
            "config.py shows TIMEOUT = 30",
            "main.py confirms Flask framework",
        ],
        confidence=8,
        confidence_verified=True,
    ))

    # 3. Adequate trace — has evidence but lacks depth
    traces.append(ReasoningTrace(
        trace_id="sample-03-adequate",
        raw_output="Found the issue in the database module. Need to fix the connection pooling.",
        file_reads=["db.py"],
        file_contents={"db.py": "class ConnectionPool:\n    def get_conn(self): ..."},
        search_commands=["grep 'pool' src/"],
        search_outputs={"grep 'pool' src/": "db.py:10:class ConnectionPool:"},
        files_changed=["db.py", "models.py"],
        patch_rationale="Update connection pooling and related model references",
        evidence_entries=["db.py has ConnectionPool class"],
        confidence=7,
        confidence_verified=False,
    ))

    # 4. Low-quality trace — mostly empty
    traces.append(ReasoningTrace(
        trace_id="sample-04-minimal",
        raw_output="Fixed the bug.",
        files_changed=["app.py"],
        confidence=6,
        confidence_verified=False,
    ))

    # 5. Placeholder trace — filled with template but no real content
    traces.append(ReasoningTrace(
        trace_id="sample-05-placeholder",
        raw_output="Analysis complete. All checks passed.",
        template_fields=["problem", "approach", "solution", "testing", "deployment"],
        substantive_evidence=[],
        evidence_entries=["TBD", "TODO"],
        confidence=8,
        confidence_verified=True,
    ))

    # 6. Overconfident trace — high confidence without evidence
    traces.append(ReasoningTrace(
        trace_id="sample-06-overconfident",
        raw_output=(
            "I'm certain this is the right approach. The fix is trivial — "
            "just change the constant in settings.py."
        ),
        confidence=10,
        confidence_verified=False,
        files_changed=["settings.py"],
        patch_rationale="Change constant value",
    ))

    # 7. Good structure but incoherent — reads don't connect to changes
    traces.append(ReasoningTrace(
        trace_id="sample-07-incoherent",
        raw_output=(
            "Read auth.py and cache.py. The caching layer looks solid. "
            "However, I need to modify the routing logic in router.py "
            "to handle the new endpoint."
        ),
        file_reads=["auth.py", "cache.py"],
        file_contents={
            "auth.py": "def authenticate(token): return verify(token)",
            "cache.py": "cache = RedisCache(host='localhost')",
        },
        search_commands=["grep 'route' src/"],
        search_outputs={"grep 'route' src/": "router.py:15:@app.route('/api/v2/data')"},
        files_changed=["router.py", "middleware.py"],
        patch_rationale="Add new route handler and middleware for /api/v2/data",
        evidence_entries=[
            "auth.py — authentication logic is independent of routing",
            "cache.py — caching layer needs no changes",
        ],
        confidence=7,
        confidence_verified=True,
    ))

    # 8. Vague trace — no specifics at all
    traces.append(ReasoningTrace(
        trace_id="sample-08-vague",
        raw_output="The code has issues. Some files need updating. I've made the necessary changes.",
        files_changed=["file1.py", "file2.py", "file3.py"],
        patch_rationale="Various improvements across the codebase",
        confidence=7,
        confidence_verified=False,
        evidence_entries=["general code review completed"],
    ))

    # 9. Well-structured retry — new attempt with solid evidence
    traces.append(ReasoningTrace(
        trace_id="sample-09-retry",
        raw_output=(
            "Retry with new findings. Re-read error_handler.py and found "
            "the exception swallowing at line 88. Stack trace confirms "
            "the root cause is in the except block."
        ),
        file_reads=["error_handler.py"],
        file_contents={
            "error_handler.py": (
                "try:\n    process()\nexcept Exception:\n    pass  # line 88: swallowed"
            ),
        },
        search_commands=["grep 'except' src/", "grep 'pass' src/error_handler.py"],
        search_outputs={
            "grep 'except' src/": "error_handler.py:87:except Exception:",
            "grep 'pass' src/error_handler.py": "error_handler.py:88:    pass  # swallowed",
        },
        attempt_number=2,
        evidence_entries=[
            "error_handler.py:88 — exception silently swallowed",
            "stack trace from test run points to error_handler.py",
            "grep confirms pass statement at line 88",
        ],
        prev_evidence_entries=["initial test failure log"],
        confidence=8,
        confidence_verified=True,
        substantive_evidence=["error_handler.py:88 exception swallowing confirmed"],
    ))

    # 10. Mixed quality — some good, some bad
    traces.append(ReasoningTrace(
        trace_id="sample-10-mixed",
        raw_output=(
            "Checked the API layer. Found issues in response formatting. "
            "The serializer is not handling null values correctly in api/serializers.py:23."
        ),
        file_reads=["api/serializers.py", "api/views.py"],
        file_contents={
            "api/serializers.py": "def serialize(obj):\n    return json.dumps(obj)  # no null check",
            "api/views.py": "",
        },
        architecture_claims=["REST API with JSON serialization"],
        architecture_citations=[],
        search_commands=["grep 'serialize' api/"],
        search_outputs={},
        files_changed=["api/serializers.py", "api/views.py", "api/urls.py"],
        patch_rationale="Fix null handling in serializer and update related views and URLs",
        evidence_entries=[
            "api/serializers.py:23 — no null value handling",
        ],
        confidence=7,
        confidence_verified=False,
    ))

    return traces


# ------------------------------------------------------------------
# Report generation
# ------------------------------------------------------------------

def generate_report(reports: list[QualityReport]) -> str:
    """Generate a markdown trace completeness report."""
    lines: list[str] = []
    lines.append("# Trace Completeness Report")
    lines.append("")

    if not reports:
        lines.append("*No traces scored.*")
        return "\n".join(lines)

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Trace | Structure | Substance | Coherence | Specificity | Honesty | Overall | Grade |")
    lines.append("|-------|-----------|-----------|-----------|-------------|---------|---------|-------|")

    for r in reports:
        dims = r.dimensions
        lines.append(
            f"| `{r.trace_id}` "
            f"| {dims.get('structure', 0):.1f} "
            f"| {dims.get('substance', 0):.1f} "
            f"| {dims.get('coherence', 0):.1f} "
            f"| {dims.get('specificity', 0):.1f} "
            f"| {dims.get('honesty', 0):.1f} "
            f"| **{r.overall:.1f}** "
            f"| **{r.grade}** |"
        )
    lines.append("")

    # Aggregate statistics
    all_overalls = [r.overall for r in reports]
    avg_overall = sum(all_overalls) / len(all_overalls)
    grade_dist = {}
    for r in reports:
        grade_dist[r.grade] = grade_dist.get(r.grade, 0) + 1

    lines.append(f"**Average overall: {avg_overall:.2f}**")
    lines.append("")
    lines.append("**Grade distribution:**")
    for grade in ["A", "B", "C", "D", "F"]:
        count = grade_dist.get(grade, 0)
        bar = "#" * count
        lines.append(f"  {grade}: {bar} ({count})")
    lines.append("")

    # Per-dimension averages
    dim_names = ["structure", "substance", "coherence", "specificity", "honesty"]
    lines.append("## Dimension Averages")
    lines.append("")
    for dim in dim_names:
        vals = [r.dimensions.get(dim, 0) for r in reports]
        avg = sum(vals) / len(vals)
        lines.append(f"- **{dim.title()}**: {avg:.2f}")
    lines.append("")

    # Issues breakdown
    lines.append("## Issues Found")
    lines.append("")
    for r in reports:
        if r.issues:
            lines.append(f"### `{r.trace_id}` (grade {r.grade}, overall {r.overall:.1f})")
            for issue in r.issues:
                lines.append(f"- {issue}")
            lines.append("")

    return "\n".join(lines)


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

def main() -> None:
    """Run trace completeness scorer on 10 sample traces and print results."""
    traces = _build_sample_traces()
    reports = [score_trace(t) for t in traces]
    print(generate_report(reports))


if __name__ == "__main__":
    main()
