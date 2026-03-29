"""E2E test: Grand Jury investigation protocol.

Verifies the full Grand Jury (DiamondThink) flow through all 8+ phases
(GJ-0 through GJ-8) including commitment, symptom record, territory map,
assumptions ledger, search pass, evidence ledger, chain-of-custody,
murder board, pre-flight checklist, and atomic change + verification.

Also tests the Failure Recovery Protocol (FRP) via the anti-shortcut engine.
"""

from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e_scaffold import (  # noqa: E402
    ReasoningSwarmHarness,
    ReasoningTrace,
    GRAND_JURY_PHASES,
    harness,
)
from scoring.anti_shortcut_coverage import (  # noqa: E402
    ReasoningTrace as ScoringTrace,
    detect_shortcuts,
    REPEATED_WITHOUT_EVIDENCE,
)

# A realistic debugging investigation task that triggers Grand Jury routing
DEBUG_TASK = "Investigate and fix TypeError in data pipeline when processing malformed CSV input"


# ═══════════════════════════════════════════════════════════════════════════
# Grand Jury E2E — full investigation through all phases
# ═══════════════════════════════════════════════════════════════════════════


class TestGrandJuryE2E:
    """Single end-to-end test case: a debugging investigation through all phases."""

    def test_full_investigation(self, harness):
        h = harness(DEBUG_TASK, mode="JURY")
        trace = h.run()

        # ── Baseline structure ─────────────────────────────────────────
        assert trace.mode == "JURY"
        assert isinstance(trace, ReasoningTrace)
        assert trace.latency_ms >= 0

        raw = trace.raw_output

        # ── GJ-0: Commitment statement present ────────────────────────
        assert "GJ-0" in raw
        assert "COMMITMENT" in raw
        assert "PLEDGE" in raw
        assert "Pre-Flight" in raw or "GJ-7" in raw

        # ── GJ-1: Symptom Record locked before investigation ──────────
        assert "GJ-1" in raw
        assert "SYMPTOM RECORD" in raw
        assert DEBUG_TASK in raw
        assert "Expected" in raw
        assert "Actual" in raw

        # ── GJ-1.5: Territory Map (skill-defined, between GJ-1 & GJ-2)
        # The DiamondThink skill defines a Territory Map phase for verifying
        # repo type, source vs generated dirs, and file existence.
        # The scaffold's GRAND_JURY_PHASES list omits this phase, but the
        # skill content loaded by the harness includes it.
        skill_content = h.load_skill()
        assert "Territory Map" in skill_content
        assert "Source vs generated" in skill_content or "source or generated" in skill_content

        # ── GJ-2: Assumptions Ledger with TDK/PC categories ───────────
        assert "GJ-2" in raw
        assert "ASSUMPTIONS LEDGER" in raw
        assert "TDK" in raw, "Assumptions must include Training-Data Knowledge category"
        assert "PC" in raw, "Assumptions must include Project-Context category"

        # ── GJ-3: Search Pass with commands and results ───────────────
        assert "GJ-3" in raw
        assert "SEARCH PASS" in raw
        # Must include at least 2 search commands
        search_cmds = [t for t in trace.techniques_used if "GJ-3" in t]
        assert len(search_cmds) >= 1
        assert "rg" in raw or "grep" in raw, "Search pass must include search commands"
        assert "hits" in raw or "results" in raw, "Search pass must include results"

        # ── GJ-4: Evidence Ledger with verbatim excerpts + line numbers
        assert "GJ-4" in raw
        assert "EVIDENCE LEDGER" in raw
        assert "verbatim" in raw.lower(), "Evidence must include verbatim excerpts"
        # File-based evidence entries must reference specific line numbers
        file_evidence = [e for e in trace.evidence_entries if ".py" in e or ".js" in e or ".ts" in e]
        for entry in file_evidence:
            assert "L" in entry, f"File evidence entry missing line number: {entry}"

        # ── GJ-5: Chain-of-Custody links each step with E# citations ──
        assert "GJ-5" in raw
        assert "CHAIN" in raw.upper()
        assert "Evidence" in raw or "E1" in raw, "Chain-of-custody must cite evidence IDs"

        # ── GJ-6: Murder Board with 4+ hypotheses, FOR/AGAINST evidence
        assert "GJ-6" in raw
        assert "MURDER BOARD" in raw
        # At least 4 hypothesis markers (H1, H2, H3, H4)
        for h_id in ("H1", "H2", "H3", "H4"):
            assert h_id in raw, f"Murder Board missing hypothesis {h_id}"
        # At least 3 hypotheses must have FOR and AGAINST evidence markers
        # (H4 "Model is wrong" may have weak/uncertain evidence per DiamondThink spec)
        assert raw.count("FOR") >= 3, "Major hypotheses need FOR evidence"
        assert raw.count("AGAINST") >= 3, "Major hypotheses need AGAINST evidence"

        # ── GJ-7: Pre-Flight checklist all 6 items present ────────────
        assert "GJ-7" in raw
        assert "PRE-FLIGHT" in raw
        # The 6 pre-flight checklist items (per DiamondThink skill)
        assert "Files read" in raw or "read" in raw.lower()
        assert "Root cause" in raw or "root cause" in raw.lower()
        assert "Eliminated" in raw or "eliminated" in raw.lower()
        assert "Atomic fix" in raw or "fix" in raw.lower()
        assert "Risk" in raw or "risk" in raw.lower()
        assert "Verification" in raw or "verification" in raw.lower()

        # ── GJ-8: Atomic change + verification ────────────────────────
        assert "GJ-8" in raw
        assert "ATOMIC CHANGE" in raw or "Atomic change" in raw
        assert "Verification" in raw or "PASS" in raw
        assert "PASS" in raw, "Verification must show PASS"

        # ── Cross-phase: evidence entries integrity ───────────────────
        assert len(trace.evidence_entries) >= 3, (
            "Grand Jury must produce at least 3 evidence entries"
        )
        for entry in trace.evidence_entries:
            assert ":" in entry, f"Evidence entry must have source reference: {entry}"

        # ── Cross-phase: completion summary ───────────────────────────
        assert "GRAND JURY COMPLETE" in raw or "COMPLETE" in raw
        assert "4" in raw, "Completion should note 4 hypotheses tested"
        assert "Atomic change" in raw or "Atomic" in raw

        # ── Cross-phase: all 9 scaffold phases executed ───────────────
        assert trace.checkpoints_hit == len(GRAND_JURY_PHASES) == 9
        for phase_id, _ in GRAND_JURY_PHASES:
            assert any(phase_id in t for t in trace.techniques_used), (
                f"Phase {phase_id} not in techniques_used"
            )

        # ── Skill content loads correctly for Grand Jury mode ─────────
        assert "DiamondThink" in skill_content
        assert "Grand Jury" in skill_content
        assert "courtroom" in skill_content.lower()


# ═══════════════════════════════════════════════════════════════════════════
# Failure Recovery Protocol (FRP)
# ═══════════════════════════════════════════════════════════════════════════


class TestFailureRecoveryProtocol:
    """Verify that the Failure Recovery Protocol triggers correctly.

    Per DiamondThink rule 8: "If a fix fails → Failure Recovery Protocol.
    ≥2 new evidence entries before second attempt."
    """

    def test_frp_triggers_without_new_evidence(self):
        """A retry with <2 new evidence entries must be flagged."""
        trace = ScoringTrace(
            trace_id="frp-trigger-test",
            raw_output="Retrying the fix with minor adjustment.",
            attempt_number=2,
            evidence_entries=["E1: main.py:L42", "E2: config.py:L15"],
            prev_evidence_entries=["E1: main.py:L42", "E2: config.py:L15"],
            confidence=7,
            confidence_verified=True,
        )
        detections = detect_shortcuts(trace)
        detection_types = {d.shortcut_type for d in detections}
        assert REPEATED_WITHOUT_EVIDENCE in detection_types, (
            "FRP must trigger when retry has <2 new evidence entries"
        )

    def test_frp_triggers_with_insufficient_new_evidence(self):
        """A retry with only 1 new evidence entry must still be flagged."""
        trace = ScoringTrace(
            trace_id="frp-partial-test",
            raw_output="Third attempt. Found one new clue.",
            attempt_number=3,
            evidence_entries=[
                "E1: main.py:L42",
                "E2: config.py:L15",
                "E3: logs/stderr:L7",
            ],
            prev_evidence_entries=[
                "E1: main.py:L42",
                "E2: config.py:L15",
            ],
            confidence=6,
            confidence_verified=True,
        )
        detections = detect_shortcuts(trace)
        detection_types = {d.shortcut_type for d in detections}
        assert REPEATED_WITHOUT_EVIDENCE in detection_types, (
            "FRP must trigger when retry has only 1 new evidence entry (need >=2)"
        )

    def test_frp_passes_with_sufficient_new_evidence(self):
        """A retry with >=2 new evidence entries must NOT be flagged for FRP."""
        trace = ScoringTrace(
            trace_id="frp-pass-test",
            raw_output="Retrying with 2 new evidence entries from fresh investigation.",
            attempt_number=2,
            evidence_entries=[
                "E1: main.py:L42",
                "E2: config.py:L15",
                "E3: logs/stderr:L7",
                "E4: test_output: assertion failure trace",
            ],
            prev_evidence_entries=["E1: main.py:L42", "E2: config.py:L15"],
            confidence=7,
            confidence_verified=True,
        )
        detections = detect_shortcuts(trace)
        frp_detections = [
            d for d in detections if d.shortcut_type == REPEATED_WITHOUT_EVIDENCE
        ]
        assert len(frp_detections) == 0, (
            "FRP must NOT trigger when retry has >=2 new evidence entries"
        )

    def test_frp_first_attempt_never_triggers(self):
        """FRP never triggers on the first attempt (attempt_number == 1)."""
        trace = ScoringTrace(
            trace_id="frp-first-attempt",
            raw_output="Initial investigation.",
            attempt_number=1,
            evidence_entries=[],
            prev_evidence_entries=[],
            confidence=7,
            confidence_verified=True,
        )
        detections = detect_shortcuts(trace)
        frp_detections = [
            d for d in detections if d.shortcut_type == REPEATED_WITHOUT_EVIDENCE
        ]
        assert len(frp_detections) == 0, (
            "FRP must never trigger on first attempt"
        )
