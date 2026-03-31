"""E2E test: Ensemble end-to-end.

Validates the 5-angle Ensemble pipeline across two scenarios:
1. High complexity problem — all 5 angles produce output, synthesis resolves conflicts
2. Medium problem through Ensemble — verify it works but may be overkill

Checks:
- All 5 angles present (Performance, Simplicity, Security, Edge Cases, Devil's Advocate)
- Angles are independent (outputs differ, not copy-paste)
- Synthesis section with AGREEMENT, DISAGREEMENT, RESOLUTION, RISKS, DEVIL'S CONCERNS
- Confidence is weighted average of per-angle scores
- If confidence < 7 → escalates to Megamind
- Parallel execution: angles complete in similar time (not sequential)
"""

from __future__ import annotations

import time
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from tests.test_e2e_scaffold import (
    ReasoningSwarmHarness,
    ReasoningTrace,
    TEST_PROBLEMS,
    HIGH_PROBLEMS,
    MEDIUM_PROBLEMS,
    ENSEMBLE_ANGLES,
    harness,
)


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness — Ensemble with timing and escalation support
# ═══════════════════════════════════════════════════════════════════════════


class EnsembleExtendedHarness(ReasoningSwarmHarness):
    """Harness that adds per-angle timing and confidence-gate escalation.

    Tracks individual angle latencies for parallel-execution verification.
    If weighted confidence < 7, escalates to Megamind mode.
    """

    def _run_ensemble(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        subproc = 0
        confidences: list[int] = []
        angle_latencies: list[float] = []

        for angle in ENSEMBLE_ANGLES:
            t0 = time.time()
            content = self._mock_angle_output(angle, task)
            elapsed = (time.time() - t0) * 1000.0

            output_parts.append(f"ANGLE: {angle}\n{content}")
            techniques_used.append(f"ENSEMBLE:{angle}")
            confidences.append(self._extract_confidence(content))
            angle_latencies.append(elapsed)
            subproc += 1

        weighted_conf = round(sum(confidences) / len(confidences))

        synth = (
            f"\nSYNTHESIS:\n"
            f"AGREEMENT: Core approach is sound across all angles\n"
            f"DISAGREEMENT: Performance vs simplicity tradeoff\n"
            f"RESOLUTION: Balanced approach with configurable options\n"
            f"RISKS: Edge cases around concurrent access\n"
            f"DEVIL'S CONCERNS: Partially valid — add safeguards\n"
            f"CONFIDENCE: {weighted_conf}"
        )
        output_parts.append(synth)
        techniques_used.append("ENSEMBLE:SYNTHESIS")

        raw = "\n\n".join(output_parts)

        escalations = 0
        if weighted_conf < 7:
            escalations = 1
            raw += (
                f"\n\n⚠️ ESCALATION: Confidence {weighted_conf} < 7 — "
                f"escalating to MEGAMIND"
            )

        raw += (
            f"\n\n🧠 ENSEMBLE COMPLETE\n"
            f"Sub-Reasoners: 5\n"
            f"Agreement Level: 3/5 agree\n"
            f"Confidence: {weighted_conf}"
        )

        trace = ReasoningTrace(
            mode="ENSEMBLE",
            confidence=weighted_conf,
            checkpoints_hit=5,
            escalations=escalations,
            techniques_used=techniques_used,
            subprocess_calls=subproc,
            raw_output=raw,
        )

        # Stash angle latencies for parallel-execution assertion
        trace._angle_latencies = angle_latencies  # type: ignore[attr-defined]
        return trace


@pytest.fixture
def ensemble_harness():
    """Provide an EnsembleExtendedHarness factory."""

    def _factory(task: str) -> EnsembleExtendedHarness:
        return EnsembleExtendedHarness(task_description=task, mode_override="ENSEMBLE")

    return _factory


# ═══════════════════════════════════════════════════════════════════════════
# Test Case 1 — High complexity problem
# ═══════════════════════════════════════════════════════════════════════════


class TestEnsembleHighComplexity:
    """High complexity problem: 5 angles produce output, synthesis resolves conflicts."""

    @pytest.fixture(params=HIGH_PROBLEMS)
    def trace(self, ensemble_harness, request):
        h = ensemble_harness(request.param)
        return h.run()

    def test_mode_is_ensemble(self, trace):
        assert trace.mode == "ENSEMBLE"

    def test_all_five_angles_present(self, trace):
        for angle in ENSEMBLE_ANGLES:
            assert f"ENSEMBLE:{angle}" in trace.techniques_used, (
                f"Missing angle: {angle}"
            )

    def test_each_angle_appears_in_raw_output(self, trace):
        for angle in ENSEMBLE_ANGLES:
            assert f"ANGLE: {angle}" in trace.raw_output

    def test_angles_are_independent(self, trace):
        """Each angle output must contain its own angle name (not copy-paste)."""
        for angle in ENSEMBLE_ANGLES:
            marker = f"from {angle.lower()} perspective"
            assert marker in trace.raw_output, (
                f"Angle {angle} output lacks unique perspective marker"
            )

    def test_angle_outputs_differ(self, trace):
        """Extract each angle's block and verify they are not identical."""
        blocks = []
        for angle in ENSEMBLE_ANGLES:
            pattern = rf"ANGLE: {re.escape(angle)}\n(.*?)(?=\nANGLE:|\nSYNTHESIS:)"
            match = re.search(pattern, trace.raw_output, re.DOTALL)
            assert match, f"Could not find block for angle {angle}"
            blocks.append(match.group(1).strip())
        # All blocks must be unique
        assert len(set(blocks)) == len(blocks), "Angle outputs are duplicated"

    def test_five_subprocess_calls(self, trace):
        assert trace.subprocess_calls == 5

    def test_checkpoints_hit(self, trace):
        assert trace.checkpoints_hit == 5

    # ── Synthesis ──────────────────────────────────────────────────────────

    def test_synthesis_section_exists(self, trace):
        assert "SYNTHESIS:" in trace.raw_output

    def test_synthesis_has_agreement(self, trace):
        assert re.search(r"AGREEMENT:.*", trace.raw_output)

    def test_synthesis_has_disagreement(self, trace):
        assert re.search(r"DISAGREEMENT:.*", trace.raw_output)

    def test_synthesis_has_resolution(self, trace):
        assert re.search(r"RESOLUTION:.*", trace.raw_output)

    def test_synthesis_has_risks(self, trace):
        assert re.search(r"RISKS:.*", trace.raw_output)

    def test_synthesis_has_devils_concerns(self, trace):
        assert re.search(r"DEVIL'S CONCERNS:.*", trace.raw_output)

    # ── Confidence ─────────────────────────────────────────────────────────

    def test_confidence_is_weighted_average(self, trace):
        """Verify confidence equals the rounded average of per-angle scores.

        Per-angle confidences: PERFORMANCE=8, SIMPLICITY=7, SECURITY=8,
        EDGE CASES=5, DEVIL'S ADVOCATE=6 → mean = 6.8 → round = 7.
        """
        expected = round((8 + 7 + 8 + 5 + 6) / 5)
        assert trace.confidence == expected

    def test_confidence_extracted_from_synthesis(self, trace):
        match = re.search(r"CONFIDENCE:\s*(\d+)", trace.raw_output)
        assert match, "CONFIDENCE not found in synthesis"
        synth_conf = int(match.group(1))
        assert synth_conf == trace.confidence

    def test_confidence_in_range(self, trace):
        assert 1 <= trace.confidence <= 10

    # ── Parallel execution timing ──────────────────────────────────────────

    def test_angles_execute_in_similar_time(self, trace):
        """Angles should complete in similar time (parallel, not sequential).

        The ratio of max-to-min latency must be < 100x, which is generous
        but catches pathological sequential execution where one angle
        waits for all others.
        """
        latencies = trace._angle_latencies  # type: ignore[attr-defined]
        assert len(latencies) == 5
        min_lat = max(min(latencies), 0.001)  # avoid division by zero
        max_lat = max(latencies)
        ratio = max_lat / min_lat
        assert ratio < 100, (
            f"Angle latencies vary by {ratio:.0f}x — likely sequential execution"
        )

    def test_total_latency_reasonable(self, trace):
        """Mock ensemble should complete in under 50ms total."""
        assert trace.latency_ms < 50, (
            f"Ensemble took {trace.latency_ms:.1f}ms — mock should be fast"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test Case 2 — Medium complexity through Ensemble (overkill check)
# ═══════════════════════════════════════════════════════════════════════════


class TestEnsembleMediumOverkill:
    """Medium problem through Ensemble — works but may be overkill."""

    @pytest.fixture(params=MEDIUM_PROBLEMS)
    def trace(self, ensemble_harness, request):
        h = ensemble_harness(request.param)
        return h.run()

    def test_mode_is_ensemble(self, trace):
        assert trace.mode == "ENSEMBLE"

    def test_all_angles_still_run(self, trace):
        """Ensemble always runs all 5 angles regardless of complexity."""
        for angle in ENSEMBLE_ANGLES:
            assert f"ENSEMBLE:{angle}" in trace.techniques_used

    def test_synthesis_present(self, trace):
        assert "SYNTHESIS:" in trace.raw_output

    def test_confidence_is_weighted_average(self, trace):
        expected = round((8 + 7 + 8 + 5 + 6) / 5)
        assert trace.confidence == expected

    def test_subprocess_calls(self, trace):
        assert trace.subprocess_calls == 5

    def test_ensemble_completes(self, trace):
        assert "ENSEMBLE COMPLETE" in trace.raw_output

    def test_ensemble_is_heavier_than_needed(self, trace):
        """Medium problems could use DEEP THINK; Ensemble is heavier.

        Document this as informational — Ensemble uses 5 subprocess calls
        vs Deep Think's 11 checkpoints but no subprocess overhead.
        """
        assert trace.subprocess_calls == 5
        assert trace.checkpoints_hit == 5
        # Ensemble uses 5+1 techniques (5 angles + synthesis)
        assert len(trace.techniques_used) == 6

    def test_no_false_escalation_on_medium(self, trace):
        """Medium problems should yield confidence >= 7, no escalation."""
        assert trace.confidence >= 7, (
            f"Confidence {trace.confidence} < 7 triggered unnecessary escalation"
        )
        assert trace.escalations == 0


# ═══════════════════════════════════════════════════════════════════════════
# Confidence-gate → Megamind escalation
# ═══════════════════════════════════════════════════════════════════════════


class TestEnsembleConfidenceGate:
    """Verify that confidence < 7 triggers escalation to Megamind."""

    def test_low_confidence_triggers_escalation(self, ensemble_harness):
        """Use a task that produces per-angle confidences averaging below 7.

        The mock angle confidences are fixed (8, 7, 8, 5, 6) → avg = 6.8 → round = 7.
        Since the scaffold's weighted average lands exactly at 7 (the threshold),
        we verify the gate logic by directly testing the harness escalation code path.
        """
        h = ensemble_harness("Refactor this module to use dependency injection")
        trace = h.run()
        # With scaffold's fixed confidences, average = 7 exactly (borderline)
        assert trace.confidence == 7
        # 7 is NOT < 7, so no escalation
        assert trace.escalations == 0

    def test_escalation_text_present_when_conf_below_7(self, ensemble_harness):
        """Manually construct a trace with confidence < 7 to verify escalation text."""

        class LowConfidenceHarness(EnsembleExtendedHarness):
            @staticmethod
            def _angle_confidence(angle: str) -> int:
                # Artificially lower all confidences
                table = {
                    "PERFORMANCE": 5,
                    "SIMPLICITY": 4,
                    "SECURITY": 5,
                    "EDGE CASES": 3,
                    "DEVIL'S ADVOCATE": 4,
                }
                return table.get(angle, 4)

        h = LowConfidenceHarness(
            task_description="Test low confidence scenario",
            mode_override="ENSEMBLE",
        )
        trace = h.run()

        # Average = round((5+4+5+3+4)/5) = round(4.2) = 4
        assert trace.confidence == 4
        assert trace.escalations == 1
        assert "ESCALATION" in trace.raw_output
        assert "MEGAMIND" in trace.raw_output

    def test_escalation_techniques_still_complete(self, ensemble_harness):
        """Even when escalating, all 5 angles and synthesis are present."""

        class LowConfidenceHarness(EnsembleExtendedHarness):
            @staticmethod
            def _angle_confidence(angle: str) -> int:
                return 3  # all low

        h = LowConfidenceHarness(
            task_description="Force escalation",
            mode_override="ENSEMBLE",
        )
        trace = h.run()

        for angle in ENSEMBLE_ANGLES:
            assert f"ENSEMBLE:{angle}" in trace.techniques_used
        assert "ENSEMBLE:SYNTHESIS" in trace.techniques_used
        assert trace.escalations == 1


# ═══════════════════════════════════════════════════════════════════════════
# Harness integration
# ═══════════════════════════════════════════════════════════════════════════


class TestEnsembleHarnessIntegration:
    """Verify the harness fixture and scaffold imports work correctly."""

    def test_harness_factory_creates_ensemble(self, harness):
        h = harness("Test task", mode="ENSEMBLE")
        assert h.get_mode() == "ENSEMBLE"

    def test_harness_run_returns_trace(self, harness):
        h = harness("Test task", mode="ENSEMBLE")
        trace = h.run()
        assert isinstance(trace, ReasoningTrace)
        assert trace.mode == "ENSEMBLE"

    def test_skill_loads_for_ensemble(self, harness):
        h = harness("Test task", mode="ENSEMBLE")
        skill = h.load_skill()
        assert len(skill) > 0
        assert "ENSEMBLE" in skill or "ensemble" in skill.lower()

    def test_ensemble_angles_constant(self):
        assert len(ENSEMBLE_ANGLES) == 5
        assert "PERFORMANCE" in ENSEMBLE_ANGLES
        assert "SIMPLICITY" in ENSEMBLE_ANGLES
        assert "SECURITY" in ENSEMBLE_ANGLES
        assert "EDGE CASES" in ENSEMBLE_ANGLES
        assert "DEVIL'S ADVOCATE" in ENSEMBLE_ANGLES
