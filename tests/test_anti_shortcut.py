"""
Anti-shortcut detection unit tests — validates all 8 detection rules
from the anti-shortcut specification.

Each test class covers one detection rule with both a positive case
(shortcut present → detected) and a negative case (clean → not detected).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring import ReasoningTrace, ShortcutDetection
from scoring.anti_shortcut_coverage import (
    HALLUCINATED_FILE_PATH,
    INCOMPLETE_SEARCH_EVIDENCE,
    OVERSIZED_PATCH,
    PREMATURE_CONFIDENCE,
    REPEATED_WITHOUT_EVIDENCE,
    RITUAL_COMPLETION,
    UNCITED_ARCHITECTURE_CLAIM,
    UNVERIFIED_FILE_READ,
    detect_shortcuts as _detect_shortcuts,
)


def detect_shortcuts(trace: ReasoningTrace) -> list[str]:
    """Return detected shortcut type strings for a reasoning trace."""
    return [d.shortcut_type for d in _detect_shortcuts(trace)]


# ---------------------------------------------------------------------------
# Rule 1 — Unverified file read
# ---------------------------------------------------------------------------

class TestUnverifiedFileRead:
    """'I read the file' without verbatim excerpt → detected."""

    def test_detected_when_no_file_contents(self):
        trace = ReasoningTrace(
            trace_id="test-ufr-1",
            file_reads=["config.py"],
            file_contents={},
        )
        types = detect_shortcuts(trace)
        assert UNVERIFIED_FILE_READ in types

    def test_detected_when_file_contents_empty(self):
        trace = ReasoningTrace(
            trace_id="test-ufr-2",
            file_reads=["main.py"],
            file_contents={"main.py": ""},
        )
        types = detect_shortcuts(trace)
        assert UNVERIFIED_FILE_READ in types

    def test_detected_when_file_contents_whitespace_only(self):
        trace = ReasoningTrace(
            trace_id="test-ufr-3",
            file_reads=["utils.py"],
            file_contents={"utils.py": "   \n  \t  "},
        )
        types = detect_shortcuts(trace)
        assert UNVERIFIED_FILE_READ in types

    def test_not_detected_with_verbatim_excerpt(self):
        trace = ReasoningTrace(
            trace_id="test-ufr-clean",
            file_reads=["config.py"],
            file_contents={"config.py": "DEBUG = True\nPORT = 8080"},
        )
        types = detect_shortcuts(trace)
        assert UNVERIFIED_FILE_READ not in types

    def test_not_detected_when_no_file_reads(self):
        trace = ReasoningTrace(trace_id="test-ufr-none")
        types = detect_shortcuts(trace)
        assert UNVERIFIED_FILE_READ not in types


# ---------------------------------------------------------------------------
# Rule 2 — Uncited architecture claim
# ---------------------------------------------------------------------------

class TestUncitedArchitectureClaim:
    """'Architecture is obvious' without citations → detected."""

    def test_detected_when_claims_without_citations(self):
        trace = ReasoningTrace(
            trace_id="test-uac-1",
            architecture_claims=["Uses MVC architecture"],
            architecture_citations=[],
        )
        types = detect_shortcuts(trace)
        assert UNCITED_ARCHITECTURE_CLAIM in types

    def test_detected_multiple_claims_no_citations(self):
        trace = ReasoningTrace(
            trace_id="test-uac-2",
            architecture_claims=["MVC pattern", "Repository layer"],
            architecture_citations=[],
        )
        types = detect_shortcuts(trace)
        assert UNCITED_ARCHITECTURE_CLAIM in types

    def test_not_detected_with_citations(self):
        trace = ReasoningTrace(
            trace_id="test-uac-clean",
            architecture_claims=["Uses MVC architecture"],
            architecture_citations=["README.md line 12"],
        )
        types = detect_shortcuts(trace)
        assert UNCITED_ARCHITECTURE_CLAIM not in types

    def test_not_detected_when_no_claims(self):
        trace = ReasoningTrace(trace_id="test-uac-none")
        types = detect_shortcuts(trace)
        assert UNCITED_ARCHITECTURE_CLAIM not in types


# ---------------------------------------------------------------------------
# Rule 3 — Incomplete search evidence
# ---------------------------------------------------------------------------

class TestIncompleteSearchEvidence:
    """'I searched' without command/output → detected."""

    def test_detected_when_search_output_missing(self):
        trace = ReasoningTrace(
            trace_id="test-ise-1",
            search_commands=["grep -r 'def calculate' ."],
            search_outputs={},
        )
        types = detect_shortcuts(trace)
        assert INCOMPLETE_SEARCH_EVIDENCE in types

    def test_detected_when_search_output_empty(self):
        trace = ReasoningTrace(
            trace_id="test-ise-2",
            search_commands=["find . -name '*.config'"],
            search_outputs={"find . -name '*.config'": ""},
        )
        types = detect_shortcuts(trace)
        assert INCOMPLETE_SEARCH_EVIDENCE in types

    def test_detected_partial_output(self):
        trace = ReasoningTrace(
            trace_id="test-ise-3",
            search_commands=["grep 'import' src/", "grep 'Error' src/"],
            search_outputs={"grep 'import' src/": "found matches"},
        )
        types = detect_shortcuts(trace)
        assert INCOMPLETE_SEARCH_EVIDENCE in types

    def test_not_detected_with_recorded_output(self):
        trace = ReasoningTrace(
            trace_id="test-ise-clean",
            search_commands=["grep -r 'def calculate' ."],
            search_outputs={"grep -r 'def calculate' .": "src/main.py:42:def calculate():"},
        )
        types = detect_shortcuts(trace)
        assert INCOMPLETE_SEARCH_EVIDENCE not in types

    def test_not_detected_when_no_searches(self):
        trace = ReasoningTrace(trace_id="test-ise-none")
        types = detect_shortcuts(trace)
        assert INCOMPLETE_SEARCH_EVIDENCE not in types


# ---------------------------------------------------------------------------
# Rule 4 — Oversized patch
# ---------------------------------------------------------------------------

class TestOversizedPatch:
    """Big patch touching many things 'just in case' → detected."""

    def test_detected_at_threshold(self):
        trace = ReasoningTrace(
            trace_id="test-op-1",
            files_changed=["a.py", "b.py", "c.py", "d.py", "e.py"],
            patch_rationale="",
        )
        types = detect_shortcuts(trace)
        assert OVERSIZED_PATCH in types

    def test_detected_above_threshold(self):
        trace = ReasoningTrace(
            trace_id="test-op-2",
            files_changed=["m1.py", "m2.py", "m3.py", "m4.py", "m5.py", "m6.py"],
            patch_rationale="",
        )
        types = detect_shortcuts(trace)
        assert OVERSIZED_PATCH in types

    def test_detected_whitespace_only_rationale(self):
        trace = ReasoningTrace(
            trace_id="test-op-3",
            files_changed=["a.py", "b.py", "c.py", "d.py", "e.py"],
            patch_rationale="   ",
        )
        types = detect_shortcuts(trace)
        assert OVERSIZED_PATCH in types

    def test_not_detected_with_rationale(self):
        trace = ReasoningTrace(
            trace_id="test-op-clean",
            files_changed=["a.py", "b.py", "c.py", "d.py", "e.py"],
            patch_rationale="Updating all modules to match new API contract",
        )
        types = detect_shortcuts(trace)
        assert OVERSIZED_PATCH not in types

    def test_not_detected_small_patch(self):
        trace = ReasoningTrace(
            trace_id="test-op-small",
            files_changed=["main.py"],
            patch_rationale="",
        )
        types = detect_shortcuts(trace)
        assert OVERSIZED_PATCH not in types


# ---------------------------------------------------------------------------
# Rule 5 — Repeated attempt without new evidence
# ---------------------------------------------------------------------------

class TestRepeatedWithoutEvidence:
    """Second try without new evidence → detected."""

    def test_detected_retry_no_new_evidence(self):
        trace = ReasoningTrace(
            trace_id="test-rwe-1",
            attempt_number=2,
            evidence_entries=["evidence-1"],
            prev_evidence_entries=["evidence-1"],
        )
        types = detect_shortcuts(trace)
        assert REPEATED_WITHOUT_EVIDENCE in types

    def test_detected_third_attempt_no_new_evidence(self):
        trace = ReasoningTrace(
            trace_id="test-rwe-2",
            attempt_number=3,
            evidence_entries=["old-1", "old-2"],
            prev_evidence_entries=["old-1", "old-2"],
        )
        types = detect_shortcuts(trace)
        assert REPEATED_WITHOUT_EVIDENCE in types

    def test_detected_retry_only_one_new(self):
        trace = ReasoningTrace(
            trace_id="test-rwe-3",
            attempt_number=2,
            evidence_entries=["old-1", "new-1"],
            prev_evidence_entries=["old-1"],
        )
        types = detect_shortcuts(trace)
        assert REPEATED_WITHOUT_EVIDENCE in types

    def test_not_detected_with_two_new_entries(self):
        trace = ReasoningTrace(
            trace_id="test-rwe-clean",
            attempt_number=2,
            evidence_entries=["old-1", "new-log", "new-trace"],
            prev_evidence_entries=["old-1"],
        )
        types = detect_shortcuts(trace)
        assert REPEATED_WITHOUT_EVIDENCE not in types

    def test_not_detected_first_attempt(self):
        trace = ReasoningTrace(
            trace_id="test-rwe-first",
            attempt_number=1,
            evidence_entries=["evidence-1"],
            prev_evidence_entries=[],
        )
        types = detect_shortcuts(trace)
        assert REPEATED_WITHOUT_EVIDENCE not in types


# ---------------------------------------------------------------------------
# Rule 6 — Hallucinated file path
# ---------------------------------------------------------------------------

class TestHallucinatedFilePath:
    """Hallucinated file path → detected."""

    def test_detected_no_evidence_no_content(self):
        trace = ReasoningTrace(
            trace_id="test-hfp-1",
            file_reads=["src/core/processor.py"],
            file_contents={},
            evidence_entries=["fix applied to main module"],
        )
        types = detect_shortcuts(trace)
        assert HALLUCINATED_FILE_PATH in types

    def test_detected_evidence_does_not_mention_file(self):
        trace = ReasoningTrace(
            trace_id="test-hfp-2",
            file_reads=["lib/internal/cache_manager.py"],
            file_contents={},
            evidence_entries=["identified cache issue"],
        )
        types = detect_shortcuts(trace)
        assert HALLUCINATED_FILE_PATH in types

    def test_not_detected_backed_by_content(self):
        trace = ReasoningTrace(
            trace_id="test-hfp-content",
            file_reads=["src/utils.py"],
            file_contents={"src/utils.py": "def divide(a, b):\n    return a / b"},
            evidence_entries=["some evidence"],
        )
        types = detect_shortcuts(trace)
        assert HALLUCINATED_FILE_PATH not in types

    def test_not_detected_backed_by_evidence(self):
        trace = ReasoningTrace(
            trace_id="test-hfp-evidence",
            file_reads=["src/utils.py"],
            file_contents={},
            evidence_entries=["src/utils.py: found divide function"],
        )
        types = detect_shortcuts(trace)
        assert HALLUCINATED_FILE_PATH not in types

    def test_not_detected_no_file_reads(self):
        trace = ReasoningTrace(trace_id="test-hfp-none")
        types = detect_shortcuts(trace)
        assert HALLUCINATED_FILE_PATH not in types


# ---------------------------------------------------------------------------
# Rule 7 — Premature confidence
# ---------------------------------------------------------------------------

class TestPrematureConfidence:
    """Premature confidence (8+ without verification) → detected."""

    def test_detected_confidence_8_unverified(self):
        trace = ReasoningTrace(
            trace_id="test-pc-1",
            confidence=8,
            confidence_verified=False,
        )
        types = detect_shortcuts(trace)
        assert PREMATURE_CONFIDENCE in types

    def test_detected_confidence_10_unverified(self):
        trace = ReasoningTrace(
            trace_id="test-pc-2",
            confidence=10,
            confidence_verified=False,
        )
        types = detect_shortcuts(trace)
        assert PREMATURE_CONFIDENCE in types

    def test_not_detected_high_confidence_verified(self):
        trace = ReasoningTrace(
            trace_id="test-pc-verified",
            confidence=9,
            confidence_verified=True,
        )
        types = detect_shortcuts(trace)
        assert PREMATURE_CONFIDENCE not in types

    def test_not_detected_low_confidence_unverified(self):
        trace = ReasoningTrace(
            trace_id="test-pc-low",
            confidence=7,
            confidence_verified=False,
        )
        types = detect_shortcuts(trace)
        assert PREMATURE_CONFIDENCE not in types

    def test_not_detected_at_boundary_7(self):
        trace = ReasoningTrace(
            trace_id="test-pc-boundary",
            confidence=7,
            confidence_verified=False,
        )
        types = detect_shortcuts(trace)
        assert PREMATURE_CONFIDENCE not in types


# ---------------------------------------------------------------------------
# Rule 8 — Ritual completion
# ---------------------------------------------------------------------------

class TestRitualCompletion:
    """Ritual completion (filled templates without work) → detected."""

    def test_detected_3_fields_no_evidence(self):
        trace = ReasoningTrace(
            trace_id="test-rc-1",
            template_fields=["problem", "approach", "solution"],
            substantive_evidence=[],
        )
        types = detect_shortcuts(trace)
        assert RITUAL_COMPLETION in types

    def test_detected_many_fields_no_evidence(self):
        trace = ReasoningTrace(
            trace_id="test-rc-2",
            template_fields=["step1", "step2", "step3", "step4", "step5"],
            substantive_evidence=[],
        )
        types = detect_shortcuts(trace)
        assert RITUAL_COMPLETION in types

    def test_not_detected_with_substantive_evidence(self):
        trace = ReasoningTrace(
            trace_id="test-rc-clean",
            template_fields=["problem", "approach", "solution"],
            substantive_evidence=["stacktrace shows line 42", "test confirms fix"],
        )
        types = detect_shortcuts(trace)
        assert RITUAL_COMPLETION not in types

    def test_not_detected_few_fields(self):
        trace = ReasoningTrace(
            trace_id="test-rc-few",
            template_fields=["problem", "approach"],
            substantive_evidence=[],
        )
        types = detect_shortcuts(trace)
        assert RITUAL_COMPLETION not in types

    def test_not_detected_no_templates(self):
        trace = ReasoningTrace(trace_id="test-rc-none")
        types = detect_shortcuts(trace)
        assert RITUAL_COMPLETION not in types


# ---------------------------------------------------------------------------
# Integration: multiple shortcuts in one trace
# ---------------------------------------------------------------------------

class TestMultipleShortcuts:
    """A single trace can trigger multiple detection rules."""

    def test_two_shortcuts_detected(self):
        trace = ReasoningTrace(
            trace_id="test-multi-1",
            file_reads=["missing.py"],
            file_contents={},
            confidence=9,
            confidence_verified=False,
        )
        types = detect_shortcuts(trace)
        assert UNVERIFIED_FILE_READ in types
        assert PREMATURE_CONFIDENCE in types

    def test_three_shortcuts_detected(self):
        trace = ReasoningTrace(
            trace_id="test-multi-2",
            file_reads=["ghost.py"],
            file_contents={},
            architecture_claims=["Uses microservices"],
            architecture_citations=[],
            confidence=10,
            confidence_verified=False,
        )
        types = detect_shortcuts(trace)
        assert UNVERIFIED_FILE_READ in types
        assert UNCITED_ARCHITECTURE_CLAIM in types
        assert PREMATURE_CONFIDENCE in types

    def test_clean_trace_returns_empty(self):
        trace = ReasoningTrace(
            trace_id="test-clean-all",
            raw_output="Simple fix.",
            files_changed=["main.py"],
            patch_rationale="Fix null pointer on line 42",
            confidence=5,
            confidence_verified=True,
        )
        types = detect_shortcuts(trace)
        assert types == []
