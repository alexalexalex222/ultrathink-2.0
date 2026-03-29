"""
E2E tests for Megamind mode — validates the full 10→3→1 architecture.

Covers:
  - Phase M1: Initial Deep Think pass
  - Phase M2: 10 angle-explorers produce output
  - Phase M3: 3 synthesizers receive and process 10 outputs
  - Phase M4: Final synthesis integrates all three
  - Iteration loop: confidence < 7 triggers re-loop (max 3 iterations)
  - Agreement level, conflicts resolved, risks mitigated
  - Max 3 iteration cap with low-confidence problem

Uses the ReasoningSwarmHarness from test_e2e_scaffold.py.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e_scaffold import (  # noqa: E402
    DEEP_THINK_TECHNIQUES,
    EXTREME_PROBLEMS,
    MEGAMIND_ANGLES,
    MEGAMIND_SYNTHESIZERS,
    ReasoningSwarmHarness,
    ReasoningTrace,
    harness,
)

# Canonical extreme-complexity task for Megamind
CANONICAL_EXTREME = EXTREME_PROBLEMS[0]

# A problem that provokes low confidence (contains "migrate" and "50 endpoints")
LOW_CONFIDENCE_PROBLEM = EXTREME_PROBLEMS[0]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _run_mega(task: str = CANONICAL_EXTREME) -> ReasoningTrace:
    """Run Megamind and return the trace."""
    h = ReasoningSwarmHarness(task_description=task, mode_override="MEGA")
    return h.run()


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Phase M1 — Initial Deep Think pass
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseM1:
    """Phase M1 runs the full Deep Think pass as baseline."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_mega()

    def test_m1_header_present(self, trace):
        assert "PHASE M1" in trace.raw_output

    def test_m1_all_11_techniques_appear(self, trace):
        for name, marker in DEEP_THINK_TECHNIQUES:
            assert name in trace.raw_output, (
                f"M1: Deep Think technique {name} missing from output"
            )

    def test_m1_checkpoint_markers_present(self, trace):
        for name, marker in DEEP_THINK_TECHNIQUES:
            assert marker in trace.raw_output, (
                f"M1: checkpoint marker {marker} for {name} missing"
            )

    def test_m1_techniques_recorded(self, trace):
        m1_techs = [t for t in trace.techniques_used if t.startswith("MEGA:M1:")]
        assert len(m1_techs) == 11, (
            f"Expected 11 M1 techniques, got {len(m1_techs)}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Phase M2 — 10 angle-explorers
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseM2:
    """All 10 angle-explorers produce output."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_mega()

    def test_m2_header_present(self, trace):
        assert "PHASE M2" in trace.raw_output

    @pytest.mark.parametrize(
        "angle",
        MEGAMIND_ANGLES,
        ids=[a.replace(" ", "-") for a in MEGAMIND_ANGLES],
    )
    def test_angle_produces_output(self, trace, angle):
        assert f"ANGLE: {angle}" in trace.raw_output, (
            f"Angle {angle} not found in output"
        )

    @pytest.mark.parametrize(
        "angle",
        MEGAMIND_ANGLES,
        ids=[a.replace(" ", "-") for a in MEGAMIND_ANGLES],
    )
    def test_angle_has_substantive_content(self, trace, angle):
        pattern = rf"ANGLE:\s*{re.escape(angle)}\s*\n\s*(ANGLE:.*?Confidence:\s*\d+)"
        match = re.search(pattern, trace.raw_output, re.DOTALL)
        assert match, f"Angle {angle} output missing substantive content"
        content = match.group(1)
        assert len(content) > 30, f"Angle {angle} content too short"

    @pytest.mark.parametrize(
        "angle",
        MEGAMIND_ANGLES,
        ids=[a.replace(" ", "-") for a in MEGAMIND_ANGLES],
    )
    def test_angle_confidence_scored(self, trace, angle):
        pattern = rf"ANGLE:\s*{re.escape(angle)}.*?Confidence:\s*(\d+)"
        match = re.search(pattern, trace.raw_output, re.DOTALL)
        assert match, f"Angle {angle} missing confidence score"
        conf = int(match.group(1))
        assert 1 <= conf <= 10, f"Angle {angle} confidence {conf} out of range"

    def test_m2_exactly_10_angles(self, trace):
        angle_matches = re.findall(r"ANGLE:\s*(" + "|".join(
            re.escape(a) for a in MEGAMIND_ANGLES
        ) + r")", trace.raw_output)
        assert len(angle_matches) >= 10, (
            f"Expected at least 10 angle outputs, got {len(angle_matches)}"
        )

    def test_m2_subprocess_calls_counted(self, trace):
        # Each angle explorer is a subprocess call
        assert trace.subprocess_calls >= 10


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Phase M3 — 3 synthesizers
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseM3:
    """All 3 synthesizers receive and process 10 outputs."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_mega()

    def test_m3_header_present(self, trace):
        assert "PHASE M3" in trace.raw_output

    @pytest.mark.parametrize(
        "synth",
        MEGAMIND_SYNTHESIZERS,
        ids=[s for s in MEGAMIND_SYNTHESIZERS],
    )
    def test_synth_present_in_output(self, trace, synth):
        assert f"SYNTHESIZER {synth}" in trace.raw_output, (
            f"Synthesizer {synth} not found in output"
        )

    @pytest.mark.parametrize(
        "synth",
        MEGAMIND_SYNTHESIZERS,
        ids=[s for s in MEGAMIND_SYNTHESIZERS],
    )
    def test_synth_processes_all_10_angles(self, trace, synth):
        pattern = rf"SYNTHESIZER {synth}.*?processed\s+{len(MEGAMIND_ANGLES)}\s+angle"
        match = re.search(pattern, trace.raw_output, re.DOTALL)
        assert match, (
            f"Synthesizer {synth} did not process {len(MEGAMIND_ANGLES)} angle outputs"
        )

    def test_m3_exactly_3_synthesizers(self, trace):
        synth_count = sum(
            1 for s in MEGAMIND_SYNTHESIZERS
            if f"SYNTHESIZER {s}" in trace.raw_output
        )
        assert synth_count == 3, f"Expected 3 synthesizers, got {synth_count}"

    def test_m3_techniques_recorded(self, trace):
        m3_techs = [t for t in trace.techniques_used if t.startswith("MEGA:M3:")]
        assert len(m3_techs) >= 3, (
            f"Expected at least 3 M3 techniques, got {len(m3_techs)}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Phase M4 — Final synthesis
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseM4:
    """Final synthesis integrates all three synthesizer outputs."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_mega()

    def test_m4_header_present(self, trace):
        assert "PHASE M4" in trace.raw_output

    def test_m4_references_synth_a(self, trace):
        assert "SYNTH A says:" in trace.raw_output

    def test_m4_references_synth_b(self, trace):
        assert "SYNTH B says:" in trace.raw_output

    def test_m4_references_synth_c(self, trace):
        assert "SYNTH C says:" in trace.raw_output

    def test_m4_confidence_score_present(self, trace):
        match = re.search(r"CONFIDENCE:\s*(\d+)", trace.raw_output)
        assert match, "M4 confidence score not found"
        conf = int(match.group(1))
        assert 1 <= conf <= 10, f"Confidence {conf} out of range"

    def test_m4_final_synthesis_technique_recorded(self, trace):
        assert "MEGA:M4:FINAL_SYNTHESIS" in trace.techniques_used


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Megamind completion summary
# ═══════════════════════════════════════════════════════════════════════════


class TestMegamindComplete:
    """The MEGAMIND COMPLETE summary contains all required fields."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_mega()

    def test_completion_marker_present(self, trace):
        assert "🧠 MEGAMIND COMPLETE" in trace.raw_output

    def test_architecture_label(self, trace):
        assert "Architecture: 10 → 3 → 1" in trace.raw_output

    def test_iterations_reported(self, trace):
        match = re.search(r"Iterations:\s*(\d+)", trace.raw_output)
        assert match, "Iterations not reported in summary"
        iterations = int(match.group(1))
        assert 1 <= iterations <= 3, f"Iterations {iterations} out of range [1,3]"

    def test_agreement_level_reported(self, trace):
        match = re.search(r"Agreement Level:\s*(\d+/10)", trace.raw_output)
        assert match, "Agreement level not reported in summary"
        numerator, _ = match.group(1).split("/")
        assert 0 <= int(numerator) <= 10

    def test_conflicts_resolved_reported(self, trace):
        assert "Conflicts Resolved:" in trace.raw_output
        match = re.search(r"Conflicts Resolved:\s*(.+)", trace.raw_output)
        assert match and len(match.group(1).strip()) > 10, (
            "Conflicts Resolved should contain substantive content"
        )

    def test_risks_mitigated_reported(self, trace):
        assert "Risks Mitigated:" in trace.raw_output
        match = re.search(r"Risks Mitigated:\s*(.+)", trace.raw_output)
        assert match and len(match.group(1).strip()) > 10, (
            "Risks Mitigated should contain substantive content"
        )

    def test_final_confidence_reported(self, trace):
        match = re.search(r"Final Confidence:\s*(\d+)", trace.raw_output)
        assert match, "Final confidence not reported in summary"
        conf = int(match.group(1))
        assert 1 <= conf <= 10

    def test_trace_mode_is_mega(self, trace):
        assert trace.mode == "MEGA"

    def test_trace_has_iterations(self, trace):
        assert 1 <= trace.iterations <= 3

    def test_trace_has_agreement_level(self, trace):
        assert re.match(r"\d+/10", trace.agreement_level), (
            f"Agreement level '{trace.agreement_level}' not in X/10 format"
        )

    def test_trace_has_conflicts(self, trace):
        assert len(trace.conflicts) > 0, "Trace should contain resolved conflicts"

    def test_trace_has_risks(self, trace):
        assert len(trace.risks) > 0, "Trace should contain mitigated risks"


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Iteration behavior — max 3 cap
# ═══════════════════════════════════════════════════════════════════════════


class TestIterationCap:
    """Verify the max-3 iteration cap when confidence stays below 7."""

    @pytest.fixture(scope="class")
    def low_conf_trace(self):
        """Run with a problem that provokes low confidence (contains 'migrate' and '50 endpoints')."""
        return _run_mega(LOW_CONFIDENCE_PROBLEM)

    def test_low_confidence_problem_triggers_iterations(self, low_conf_trace):
        """A problem with 'migrate' and '50 endpoints' should yield confidence 6."""
        assert low_conf_trace.confidence == 6

    def test_stops_at_max_3_iterations(self, low_conf_trace):
        """Even with low confidence, must stop at iteration 3."""
        assert low_conf_trace.iterations == 3

    def test_max_iteration_message_present(self, low_conf_trace):
        """Output should contain the 'Max iterations' cap message."""
        assert "Max iterations (3) reached" in low_conf_trace.raw_output

    def test_uncertainty_flags_mentioned(self, low_conf_trace):
        """When capped, output should mention uncertainty flags."""
        assert "uncertainty flags" in low_conf_trace.raw_output.lower()

    def test_all_3_iterations_have_m2_phase(self, low_conf_trace):
        """Each iteration should have its own Phase M2 entry."""
        m2_phases = re.findall(r"PHASE M2.*?iteration\s+(\d+)", low_conf_trace.raw_output)
        assert len(m2_phases) >= 3, (
            f"Expected M2 phases for 3 iterations, found {len(m2_phases)}"
        )

    def test_all_3_iterations_have_m3_phase(self, low_conf_trace):
        """Each iteration should have its own Phase M3 entry."""
        m3_phases = re.findall(r"PHASE M3.*?iteration\s+(\d+)", low_conf_trace.raw_output)
        assert len(m3_phases) >= 3, (
            f"Expected M3 phases for 3 iterations, found {len(m3_phases)}"
        )

    def test_all_3_iterations_have_m4_phase(self, low_conf_trace):
        """Each iteration should have its own Phase M4 entry."""
        m4_phases = re.findall(r"PHASE M4.*?iteration\s+(\d+)", low_conf_trace.raw_output)
        assert len(m4_phases) >= 3, (
            f"Expected M4 phases for 3 iterations, found {len(m4_phases)}"
        )

    def test_loop_back_message_present(self, low_conf_trace):
        """Output should contain 'looping back to Phase M2' messages."""
        assert "looping back to Phase M2" in low_conf_trace.raw_output


# ═══════════════════════════════════════════════════════════════════════════
# Test class: High-confidence problem completes in 1 iteration
# ═══════════════════════════════════════════════════════════════════════════


class TestSingleIteration:
    """A problem that yields confidence >= 7 should complete in 1 iteration."""

    @pytest.fixture(scope="class")
    def high_conf_trace(self):
        """Run with a problem that yields high confidence (no trigger words)."""
        return _run_mega("Design a new caching layer for the application")

    def test_completes_in_one_iteration(self, high_conf_trace):
        assert high_conf_trace.iterations == 1

    def test_confidence_at_least_7(self, high_conf_trace):
        assert high_conf_trace.confidence >= 7

    def test_no_loop_back(self, high_conf_trace):
        assert "looping back" not in high_conf_trace.raw_output


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Mode dispatch and routing
# ═══════════════════════════════════════════════════════════════════════════


class TestMegamindModeDispatch:
    """Verify that Megamind mode is correctly resolved and dispatched."""

    def test_mode_resolves_to_megamind(self, harness):
        h = harness(CANONICAL_EXTREME, mode="MEGA")
        assert h.get_mode() == "MEGAMIND"

    def test_mode_resolves_from_full_name(self, harness):
        h = harness(CANONICAL_EXTREME, mode="MEGAMIND")
        assert h.get_mode() == "MEGAMIND"

    def test_mega_run_returns_mega_mode(self, harness):
        h = harness(CANONICAL_EXTREME, mode="MEGA")
        trace = h.run()
        assert trace.mode == "MEGA"

    def test_mega_loads_megamind_skill(self, harness):
        h = harness(CANONICAL_EXTREME, mode="MEGA")
        skill = h.load_skill()
        assert "MEGAMIND" in skill.upper()


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Full trace structure
# ═══════════════════════════════════════════════════════════════════════════


class TestMegamindTraceStructure:
    """Validate the ReasoningTrace structure for Megamind output."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_mega()

    def test_mode_is_mega(self, trace):
        assert trace.mode == "MEGA"

    def test_confidence_in_valid_range(self, trace):
        assert 1 <= trace.confidence <= 10

    def test_checkpoints_hit(self, trace):
        assert trace.checkpoints_hit == 13  # 10 angles + 3 synthesizers

    def test_no_escalations(self, trace):
        assert trace.escalations == 0

    def test_techniques_used_starts_with_mega(self, trace):
        assert all(t.startswith("MEGA:") for t in trace.techniques_used)

    def test_subprocess_calls_positive(self, trace):
        assert trace.subprocess_calls > 0

    def test_raw_output_non_empty(self, trace):
        assert len(trace.raw_output) > 200

    def test_latency_positive(self, trace):
        assert trace.latency_ms >= 0


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Extreme problems across Megamind
# ═══════════════════════════════════════════════════════════════════════════


class TestExtremeProblems:
    """Megamind produces valid output for all extreme-complexity problems."""

    @pytest.mark.parametrize(
        "problem",
        EXTREME_PROBLEMS,
        ids=[f"EXTREME-{i}" for i in range(len(EXTREME_PROBLEMS))],
    )
    def test_megamind_completes(self, harness, problem):
        h = harness(problem, mode="MEGA")
        trace = h.run()
        assert "🧠 MEGAMIND COMPLETE" in trace.raw_output

    @pytest.mark.parametrize(
        "problem",
        EXTREME_PROBLEMS,
        ids=[f"EXTREME-{i}" for i in range(len(EXTREME_PROBLEMS))],
    )
    def test_megamind_has_all_phases(self, harness, problem):
        h = harness(problem, mode="MEGA")
        trace = h.run()
        assert "PHASE M1" in trace.raw_output
        assert "PHASE M2" in trace.raw_output
        assert "PHASE M3" in trace.raw_output
        assert "PHASE M4" in trace.raw_output

    @pytest.mark.parametrize(
        "problem",
        EXTREME_PROBLEMS,
        ids=[f"EXTREME-{i}" for i in range(len(EXTREME_PROBLEMS))],
    )
    def test_megamind_confidence_valid(self, harness, problem):
        h = harness(problem, mode="MEGA")
        trace = h.run()
        assert 1 <= trace.confidence <= 10
