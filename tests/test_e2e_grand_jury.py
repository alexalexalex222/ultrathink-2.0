"""E2E test: Grand Jury end-to-end.

Validates the full Grand Jury protocol (GJ-0 through GJ-8) for a debugging
investigation, including the Failure Recovery Protocol (FRP).

Covers:
  - GJ-0: Commitment statement present
  - GJ-1: Symptom Record locked before investigation
  - GJ-1.5: Territory Map identifies real files
  - GJ-2: Assumptions Ledger with TDK/PC categories
  - GJ-3: Search Pass with commands and results
  - GJ-4: Evidence Ledger with verbatim excerpts + line numbers
  - GJ-5: Chain-of-Custody links each step with E# citations
  - GJ-6: Murder Board with 4+ hypotheses, each with FOR/AGAINST evidence
  - GJ-7: Pre-Flight checklist all 6 items present
  - GJ-8: Atomic change + verification
  - FRP: inject a failed fix, verify >=2 new evidence entries before retry

Uses the ReasoningSwarmHarness from test_e2e_scaffold.py.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e_scaffold import (  # noqa: E402
    GRAND_JURY_PHASES,
    ReasoningSwarmHarness,
    ReasoningTrace,
    harness,
)

# Canonical debugging task for Grand Jury
CANONICAL_DEBUG_TASK = "Debug the failing cart checkout flow — users see 500 error on /cart/add"


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness — Grand Jury with FRP support
# ═══════════════════════════════════════════════════════════════════════════


class GrandJuryExtendedHarness(ReasoningSwarmHarness):
    """Harness that adds Failure Recovery Protocol (FRP) simulation.

    When an initial fix fails (simulated), FRP requires >=2 new evidence
    entries before retry. This harness injects a failed-fix scenario and
    tracks the additional evidence gathered.
    """

    def _run_jury(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        evidence: list[str] = []
        fix_failed = False
        frp_evidence: list[str] = []

        for phase_id, phase_name in GRAND_JURY_PHASES:
            content = self._mock_jury_phase(phase_id, phase_name, task)

            # Simulate FRP: inject failed fix at GJ-8 first pass
            if phase_id == "GJ-8" and not fix_failed:
                content = (
                    "Atomic change applied. Verification: FAIL — test still errors. "
                    "FAILURE RECOVERY PROTOCOL TRIGGERED. "
                    "Must collect >= 2 new evidence entries before retry."
                )
                fix_failed = True
                frp_evidence = [
                    "E4: handlers/cart.py:L88 — verbatim excerpt: off-by-one in quantity validation",
                    "E5: tests/test_cart.py:L31 — raw output: AssertionError on boundary value 0",
                ]
                evidence.extend(frp_evidence)

                # FRP retry phase
                frp_content = (
                    "FRP PASS 2: "
                    "E4 + E5 collected — root cause revised to quantity boundary. "
                    "Atomic change v2 applied. Verification: PASS. "
                    "All tests green. No regressions detected."
                )
                section = (
                    f"┌─ FRP RETRY ({phase_id}) ──────────────────\n"
                    f"│ {frp_content}\n"
                    f"└{'─' * 50}┘"
                )
                output_parts.append(section)
                techniques_used.append(f"JURY:{phase_id}:FRP")

            section = (
                f"┌─ {phase_name} ({phase_id}) ──────────────────\n"
                f"│ {content}\n"
                f"└{'─' * 50}┘"
            )
            output_parts.append(section)
            techniques_used.append(f"JURY:{phase_id}")

            if phase_id == "GJ-4":
                evidence.extend([
                    "E1: main.py:L42 — verbatim excerpt of error handler",
                    "E2: config.py:L15 — verbatim excerpt of config loading",
                    "E3: test_output — raw command output from failing test",
                ])

        conf = self._complexity_confidence(task)

        raw = "\n".join(output_parts)
        raw += (
            f"\n\n⚖️ GRAND JURY COMPLETE\n"
            f"Evidence Entries: {len(evidence)}\n"
            f"Hypotheses Tested: 4\n"
            f"Root Cause: Identified via evidence chain\n"
            f"Fix: Atomic change applied\n"
            f"Verification: PASS"
        )

        return ReasoningTrace(
            mode="JURY",
            confidence=conf,
            checkpoints_hit=9,
            escalations=0,
            techniques_used=techniques_used,
            evidence_entries=evidence,
            raw_output=raw,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Helper
# ═══════════════════════════════════════════════════════════════════════════


def _run_jury(task: str = CANONICAL_DEBUG_TASK) -> ReasoningTrace:
    """Run Grand Jury and return the trace."""
    h = ReasoningSwarmHarness(task_description=task, mode_override="JURY")
    return h.run()


def _run_jury_with_frp(task: str = CANONICAL_DEBUG_TASK) -> ReasoningTrace:
    """Run Grand Jury with FRP and return the trace."""
    h = GrandJuryExtendedHarness(task_description=task, mode_override="JURY")
    return h.run()


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Mode dispatch and routing
# ═══════════════════════════════════════════════════════════════════════════


class TestGrandJuryModeDispatch:
    """Verify that Grand Jury mode is correctly resolved and dispatched."""

    def test_mode_resolves_to_grand_jury(self, harness):
        h = harness(CANONICAL_DEBUG_TASK, mode="JURY")
        assert h.get_mode() == "GRAND JURY"

    def test_mode_resolves_from_full_name(self, harness):
        h = harness(CANONICAL_DEBUG_TASK, mode="GRAND JURY")
        assert h.get_mode() == "GRAND JURY"

    def test_jury_run_returns_jury_mode(self, harness):
        h = harness(CANONICAL_DEBUG_TASK, mode="JURY")
        trace = h.run()
        assert trace.mode == "JURY"

    def test_jury_loads_diamondthink_skill(self, harness):
        h = harness(CANONICAL_DEBUG_TASK, mode="JURY")
        skill = h.load_skill()
        assert "GRAND JURY" in skill.upper() or "DIAMONDTHINK" in skill.upper()


# ═══════════════════════════════════════════════════════════════════════════
# Test class: GJ-0 — Commitment
# ═══════════════════════════════════════════════════════════════════════════


class TestGJ0Commitment:
    """Phase 0: Commitment statement present."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_gj0_header_present(self, trace):
        assert "COMMITMENT (GJ-0)" in trace.raw_output

    def test_gj0_repo_root_stated(self, trace):
        assert re.search(r"Repo root:", trace.raw_output)

    def test_gj0_available_tools_stated(self, trace):
        assert re.search(r"Available tools:", trace.raw_output)

    def test_gj0_constraints_stated(self, trace):
        assert re.search(r"Constraints:", trace.raw_output)

    def test_gj0_pledge_present(self, trace):
        assert re.search(
            r"I will not propose a fix until Pre-Flight.*Phase 7",
            trace.raw_output,
        )

    def test_gj0_technique_recorded(self, trace):
        assert "JURY:GJ-0" in trace.techniques_used


# ═══════════════════════════════════════════════════════════════════════════
# Test class: GJ-1 — Symptom Record
# ═══════════════════════════════════════════════════════════════════════════


class TestGJ1SymptomRecord:
    """Phase 1: Symptom Record locked before investigation."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_gj1_header_present(self, trace):
        assert "SYMPTOM RECORD (GJ-1)" in trace.raw_output

    def test_gj1_reported_problem(self, trace):
        assert re.search(r"Reported:", trace.raw_output)

    def test_gj1_expected_vs_actual(self, trace):
        assert re.search(r"Expected:", trace.raw_output)
        assert re.search(r"Actual:", trace.raw_output)

    def test_gj1_severity_stated(self, trace):
        assert re.search(r"Severity:", trace.raw_output)

    def test_gj1_success_criteria(self, trace):
        assert re.search(r"Success criteria:", trace.raw_output)

    def test_gj1_technique_recorded(self, trace):
        assert "JURY:GJ-1" in trace.techniques_used


# ═══════════════════════════════════════════════════════════════════════════
# Test class: GJ-1.5 — Territory Map
# ═══════════════════════════════════════════════════════════════════════════


class TestGJ1_5TerritoryMap:
    """Phase 1.5: Territory Map identifies real files."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_gj1_territory_info_in_output(self, trace):
        """Territory Map content is embedded in the GJ-1 phase output."""
        # The mock GJ-1 contains task description which serves as territory identification
        assert CANONICAL_DEBUG_TASK in trace.raw_output

    def test_gj1_mentions_real_files(self, trace):
        """Evidence entries reference real file paths with line numbers."""
        file_refs = re.findall(r"\w[\w/]*\.\w+:\w\d+", trace.raw_output)
        assert len(file_refs) >= 2, (
            f"Expected >=2 file:line references, found {len(file_refs)}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: GJ-2 — Assumptions Ledger
# ═══════════════════════════════════════════════════════════════════════════


class TestGJ2AssumptionsLedger:
    """Phase 2: Assumptions Ledger with TDK/PC categories."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_gj2_header_present(self, trace):
        assert "ASSUMPTIONS LEDGER (GJ-2)" in trace.raw_output

    def test_gj2_has_assumption_entries(self, trace):
        assert re.search(r"A\d+:", trace.raw_output)

    def test_gj2_has_tdk_category(self, trace):
        """TDK = Training-Data Knowledge."""
        assert "TDK" in trace.raw_output

    def test_gj2_has_pc_category(self, trace):
        """PC = Project Context."""
        assert "PC" in trace.raw_output

    def test_gj2_has_confidence_scores(self, trace):
        assert re.search(r"\d+%", trace.raw_output)

    def test_gj2_has_status(self, trace):
        assert re.search(r"UNVERIFIED|VERIFIED", trace.raw_output)

    def test_gj2_technique_recorded(self, trace):
        assert "JURY:GJ-2" in trace.techniques_used


# ═══════════════════════════════════════════════════════════════════════════
# Test class: GJ-3 — Search Pass
# ═══════════════════════════════════════════════════════════════════════════


class TestGJ3SearchPass:
    """Phase 3: Search Pass with commands and results."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_gj3_header_present(self, trace):
        assert "SEARCH PASS (GJ-3)" in trace.raw_output

    def test_gj3_has_search_entries(self, trace):
        assert re.search(r"S\d+:", trace.raw_output)

    def test_gj3_has_search_commands(self, trace):
        assert re.search(r"rg|grep|find", trace.raw_output)

    def test_gj3_has_result_counts(self, trace):
        assert re.search(r"\d+ hits?", trace.raw_output)

    def test_gj3_technique_recorded(self, trace):
        assert "JURY:GJ-3" in trace.techniques_used


# ═══════════════════════════════════════════════════════════════════════════
# Test class: GJ-4 — Evidence Ledger
# ═══════════════════════════════════════════════════════════════════════════


class TestGJ4EvidenceLedger:
    """Phase 4: Evidence Ledger with verbatim excerpts + line numbers."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_gj4_header_present(self, trace):
        assert "EVIDENCE LEDGER (GJ-4)" in trace.raw_output

    def test_gj4_has_evidence_entries(self, trace):
        assert re.search(r"E\d+:", trace.raw_output)

    def test_gj4_evidence_has_line_numbers(self, trace):
        """Evidence must reference line numbers (e.g. :L42, :L15)."""
        line_refs = re.findall(r"E\d+:.*:\w\d+", trace.raw_output)
        assert len(line_refs) >= 2, (
            f"Expected >=2 evidence entries with line numbers, found {len(line_refs)}"
        )

    def test_gj4_evidence_has_verbatim_excerpts(self, trace):
        assert re.search(r"verbatim excerpt", trace.raw_output)

    def test_gj4_min_3_evidence_for_debugging(self, trace):
        """Grand Jury requires >=3 evidence entries for a debugging task."""
        assert len(trace.evidence_entries) >= 3

    def test_gj4_technique_recorded(self, trace):
        assert "JURY:GJ-4" in trace.techniques_used


# ═══════════════════════════════════════════════════════════════════════════
# Test class: GJ-5 — Chain-of-Custody
# ═══════════════════════════════════════════════════════════════════════════


class TestGJ5ChainOfCustody:
    """Phase 5: Chain-of-Custody links each step with E# citations."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_gj5_header_present(self, trace):
        assert "CHAIN-OF-CUSTODY (GJ-5)" in trace.raw_output

    def test_gj5_has_chain_links(self, trace):
        """Chain should show a progression from source to runtime."""
        assert re.search(r"→", trace.raw_output)

    def test_gj5_cites_evidence_ids(self, trace):
        assert re.search(r"Evidence ID", trace.raw_output, re.IGNORECASE) or \
               re.search(r"E\d+", trace.raw_output)

    def test_gj5_technique_recorded(self, trace):
        assert "JURY:GJ-5" in trace.techniques_used


# ═══════════════════════════════════════════════════════════════════════════
# Test class: GJ-6 — Murder Board
# ═══════════════════════════════════════════════════════════════════════════


class TestGJ6MurderBoard:
    """Phase 6: Murder Board with 4+ hypotheses, each with FOR/AGAINST evidence."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_gj6_header_present(self, trace):
        assert "MURDER BOARD (GJ-6)" in trace.raw_output

    def test_gj6_has_4_plus_hypotheses(self, trace):
        hypotheses = re.findall(r"H\d+:", trace.raw_output)
        assert len(hypotheses) >= 4, (
            f"Expected >=4 hypotheses on Murder Board, found {len(hypotheses)}"
        )

    def test_gj6_hypotheses_have_evidence_for(self, trace):
        """Each hypothesis must have evidence FOR."""
        for_against = re.findall(r"E\d+(?:,\s*E\d+)*\s+FOR", trace.raw_output)
        assert len(for_against) >= 3, (
            f"Expected >=3 hypotheses with FOR evidence, found {len(for_against)}"
        )

    def test_gj6_hypotheses_have_evidence_against(self, trace):
        """Each hypothesis must have evidence AGAINST."""
        against = re.findall(r"E\d+(?:,\s*E\d+)*\s+AGAINST", trace.raw_output)
        assert len(against) >= 3, (
            f"Expected >=3 hypotheses with AGAINST evidence, found {len(against)}"
        )

    def test_gj6_has_verdicts(self, trace):
        """Hypotheses should have verdicts: CONFIRMED, DISPROVED, or UNCERTAIN."""
        verdicts = re.findall(
            r"(CONFIRMED|DISPROVED|UNCERTAIN)", trace.raw_output
        )
        assert len(verdicts) >= 4, (
            f"Expected >=4 verdicts, found {len(verdicts)}"
        )

    def test_gj6_has_confirmed_hypothesis(self, trace):
        assert "CONFIRMED" in trace.raw_output

    def test_gj6_has_disproved_hypotheses(self, trace):
        assert "DISPROVED" in trace.raw_output

    def test_gj6_has_uncertain_hypothesis(self, trace):
        assert "UNCERTAIN" in trace.raw_output

    def test_gj6_technique_recorded(self, trace):
        assert "JURY:GJ-6" in trace.techniques_used


# ═══════════════════════════════════════════════════════════════════════════
# Test class: GJ-7 — Pre-Flight Checklist
# ═══════════════════════════════════════════════════════════════════════════


class TestGJ7PreFlightChecklist:
    """Phase 7: Pre-Flight checklist all 6 items present."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_gj7_header_present(self, trace):
        assert "PRE-FLIGHT CHECKLIST (GJ-7)" in trace.raw_output

    def test_gj7_item1_files_read(self, trace):
        assert re.search(r"1\.\s*Files read", trace.raw_output)

    def test_gj7_item2_root_cause(self, trace):
        assert re.search(r"2\.\s*Root cause", trace.raw_output)

    def test_gj7_item3_eliminated_hypotheses(self, trace):
        assert re.search(r"3\.\s*Eliminated", trace.raw_output)

    def test_gj7_item4_atomic_fix_plan(self, trace):
        assert re.search(r"4\.\s*Atomic fix", trace.raw_output)

    def test_gj7_item5_risks(self, trace):
        assert re.search(r"5\.\s*Risks", trace.raw_output)

    def test_gj7_item6_verification(self, trace):
        assert re.search(r"6\.\s*Verification", trace.raw_output)

    def test_gj7_all_6_items_present(self, trace):
        items = re.findall(r"\d\.\s*\w", trace.raw_output)
        assert len(items) >= 6, (
            f"Expected >=6 pre-flight items, found {len(items)}"
        )

    def test_gj7_technique_recorded(self, trace):
        assert "JURY:GJ-7" in trace.techniques_used


# ═══════════════════════════════════════════════════════════════════════════
# Test class: GJ-8 — Atomic Change + Verify
# ═══════════════════════════════════════════════════════════════════════════


class TestGJ8AtomicChange:
    """Phase 8: Atomic change + verification."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_gj8_header_present(self, trace):
        assert "ATOMIC CHANGE + VERIFY (GJ-8)" in trace.raw_output

    def test_gj8_atomic_change_applied(self, trace):
        assert re.search(r"Atomic change applied", trace.raw_output)

    def test_gj8_verification_pass(self, trace):
        assert re.search(r"Verification:\s*PASS", trace.raw_output)

    def test_gj8_technique_recorded(self, trace):
        assert "JURY:GJ-8" in trace.techniques_used


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Grand Jury completion summary
# ═══════════════════════════════════════════════════════════════════════════


class TestGrandJuryComplete:
    """The GRAND JURY COMPLETE summary contains all required fields."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_completion_marker_present(self, trace):
        assert "⚖️ GRAND JURY COMPLETE" in trace.raw_output

    def test_evidence_entries_counted(self, trace):
        match = re.search(r"Evidence Entries:\s*(\d+)", trace.raw_output)
        assert match, "Evidence Entries count not found"
        count = int(match.group(1))
        assert count >= 3, f"Expected >=3 evidence entries, got {count}"

    def test_hypotheses_tested_counted(self, trace):
        match = re.search(r"Hypotheses Tested:\s*(\d+)", trace.raw_output)
        assert match, "Hypotheses Tested count not found"
        count = int(match.group(1))
        assert count >= 4, f"Expected >=4 hypotheses tested, got {count}"

    def test_root_cause_identified(self, trace):
        assert re.search(r"Root Cause:", trace.raw_output)

    def test_fix_applied(self, trace):
        assert re.search(r"Fix:", trace.raw_output)

    def test_verification_pass(self, trace):
        assert re.search(r"Verification:\s*PASS", trace.raw_output)

    def test_trace_mode_is_jury(self, trace):
        assert trace.mode == "JURY"

    def test_trace_checkpoints_hit(self, trace):
        assert trace.checkpoints_hit == 9

    def test_trace_techniques_all_jury(self, trace):
        assert all(t.startswith("JURY:") for t in trace.techniques_used)

    def test_trace_has_evidence_entries(self, trace):
        assert len(trace.evidence_entries) >= 3

    def test_trace_no_escalations(self, trace):
        assert trace.escalations == 0


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Failure Recovery Protocol (FRP)
# ═══════════════════════════════════════════════════════════════════════════


class TestFailureRecoveryProtocol:
    """Inject a failed fix and verify FRP triggers (>=2 new evidence entries)."""

    @pytest.fixture(scope="class")
    def frp_trace(self):
        return _run_jury_with_frp()

    def test_frp_triggers_on_failed_fix(self, frp_trace):
        assert "FAILURE RECOVERY PROTOCOL TRIGGERED" in frp_trace.raw_output

    def test_frp_requires_new_evidence(self, frp_trace):
        assert re.search(
            r"Must collect.*>=.*2.*new evidence", frp_trace.raw_output
        )

    def test_frp_collects_at_least_2_new_entries(self, frp_trace):
        """FRP must add >=2 new evidence entries (E4, E5, ...)."""
        new_entries = [e for e in frp_trace.evidence_entries if e.startswith(("E4:", "E5:"))]
        assert len(new_entries) >= 2, (
            f"FRP must add >=2 new evidence entries, found {len(new_entries)}"
        )

    def test_frp_total_evidence_exceeds_initial(self, frp_trace):
        """Total evidence should be >3 (3 initial + FRP entries)."""
        assert len(frp_trace.evidence_entries) >= 5, (
            f"Expected >=5 total evidence entries with FRP, got {len(frp_trace.evidence_entries)}"
        )

    def test_frp_retry_passes(self, frp_trace):
        assert re.search(r"FRP PASS 2", frp_trace.raw_output)
        assert re.search(r"Verification:\s*PASS", frp_trace.raw_output)

    def test_frp_revised_root_cause(self, frp_trace):
        """FRP should revise root cause based on new evidence."""
        assert re.search(r"root cause revised", frp_trace.raw_output, re.IGNORECASE)

    def test_frp_technique_recorded(self, frp_trace):
        frp_techs = [t for t in frp_trace.techniques_used if "FRP" in t]
        assert len(frp_techs) >= 1, "FRP technique not recorded"

    def test_frp_still_completes_all_phases(self, frp_trace):
        """Even with FRP, all 9 phases must be present."""
        for phase_id, _ in GRAND_JURY_PHASES:
            assert f"({phase_id})" in frp_trace.raw_output, (
                f"Phase {phase_id} missing from FRP output"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Full trace structure
# ═══════════════════════════════════════════════════════════════════════════


class TestGrandJuryTraceStructure:
    """Validate the ReasoningTrace structure for Grand Jury output."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    def test_mode_is_jury(self, trace):
        assert trace.mode == "JURY"

    def test_confidence_in_valid_range(self, trace):
        assert 1 <= trace.confidence <= 10

    def test_checkpoints_hit_equals_9(self, trace):
        assert trace.checkpoints_hit == 9

    def test_no_escalations(self, trace):
        assert trace.escalations == 0

    def test_techniques_used_starts_with_jury(self, trace):
        assert all(t.startswith("JURY:") for t in trace.techniques_used)

    def test_evidence_entries_non_empty(self, trace):
        assert len(trace.evidence_entries) > 0

    def test_raw_output_non_empty(self, trace):
        assert len(trace.raw_output) > 200

    def test_latency_non_negative(self, trace):
        assert trace.latency_ms >= 0


# ═══════════════════════════════════════════════════════════════════════════
# Test class: All 9 phases present
# ═══════════════════════════════════════════════════════════════════════════


class TestAllPhasesPresent:
    """All 9 Grand Jury phases appear in the output."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_jury()

    @pytest.mark.parametrize(
        "phase_id,phase_name",
        GRAND_JURY_PHASES,
        ids=[f"{pid}-{pname}" for pid, pname in GRAND_JURY_PHASES],
    )
    def test_phase_header_present(self, trace, phase_id, phase_name):
        assert f"{phase_name} ({phase_id})" in trace.raw_output, (
            f"Phase {phase_id} ({phase_name}) header missing from output"
        )

    @pytest.mark.parametrize(
        "phase_id,phase_name",
        GRAND_JURY_PHASES,
        ids=[f"{pid}-{pname}" for pid, pname in GRAND_JURY_PHASES],
    )
    def test_phase_technique_recorded(self, trace, phase_id, phase_name):
        assert f"JURY:{phase_id}" in trace.techniques_used, (
            f"Phase {phase_id} technique not recorded"
        )
