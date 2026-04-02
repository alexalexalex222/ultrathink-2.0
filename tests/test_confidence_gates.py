"""Confidence gate integration tests.

Tests the confidence gating system across all mode transitions:

| From        | To          | Trigger                         |
|-------------|-------------|---------------------------------|
| Rapid Strike| Deep Think  | confidence < 8                  |
| Deep Think  | Ensemble    | confidence < 7                  |
| Ensemble    | Megamind    | confidence < 7                  |
| Megamind    | Grand Jury  | confidence < 7 + prior fail     |
| Megamind    | Loop        | confidence < 7, iterations < 3  |
| Megamind    | Output      | confidence >= 7 OR iterations=3 |

For each transition:
1. Construct a trace with specific confidence score
2. Verify the gate evaluates correctly
3. Verify context is preserved across escalation
4. Verify de-escalation works (confidence 9+ can skip modes)

Also tests override rules interacting with confidence gates:
- 'think harder' + confidence 8 → still escalates
- 'quick' + confidence 4 → RAPID STRIKE (unless CRITICAL stakes)
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from tests.test_e2e_scaffold import (
    ReasoningSwarmHarness,
    ReasoningTrace,
    DEEP_THINK_TECHNIQUES,
    ENSEMBLE_ANGLES,
    MEGAMIND_ANGLES,
    MEGAMIND_SYNTHESIZERS,
    LOW_PROBLEMS,
    MEDIUM_PROBLEMS,
    HIGH_PROBLEMS,
    EXTREME_PROBLEMS,
    harness,
)
from src.intake_classifier import classify_task


# ═══════════════════════════════════════════════════════════════════════════
# Confidence gate evaluator
# ═══════════════════════════════════════════════════════════════════════════


MODE_LADDER = ["RAPID STRIKE", "DEEP THINK", "ENSEMBLE", "MEGAMIND", "GRAND JURY"]


def evaluate_confidence_gate(
    current_mode: str,
    confidence: int,
    prior_fails: int = 0,
    iterations: int = 1,
    max_iterations: int = 3,
) -> str:
    """Evaluate the confidence gate and return the next action.

    Returns one of: the next mode to escalate to, 'LOOP', or 'OUTPUT'.
    """
    if current_mode == "RAPID STRIKE":
        if confidence < 8:
            return "DEEP THINK"
        return "OUTPUT"

    if current_mode == "DEEP THINK":
        if confidence < 7:
            return "ENSEMBLE"
        return "OUTPUT"

    if current_mode == "ENSEMBLE":
        if confidence < 7:
            return "MEGAMIND"
        return "OUTPUT"

    if current_mode == "MEGAMIND":
        if confidence >= 7:
            return "OUTPUT"
        # confidence < 7
        if prior_fails >= 1:
            return "GRAND JURY"
        if iterations < max_iterations:
            return "LOOP"
        # iterations == max_iterations, output with uncertainty
        return "OUTPUT"

    # GRAND JURY always outputs
    return "OUTPUT"


def can_skip_to_output(confidence: int) -> bool:
    """De-escalation check: confidence 9+ can skip modes and go straight to output."""
    return confidence >= 9


# ═══════════════════════════════════════════════════════════════════════════
# Custom harness subclasses for controlled confidence
# ═══════════════════════════════════════════════════════════════════════════


class LowConfidenceRapidHarness(ReasoningSwarmHarness):
    """Rapid Strike harness with configurable confidence below 8."""

    def __init__(self, *args, rapid_confidence: int = 6, **kwargs):
        super().__init__(*args, **kwargs)
        self._rapid_confidence = rapid_confidence

    def _run_rapid(self) -> ReasoningTrace:
        task = self.task_description
        conf = self._rapid_confidence
        sections = [
            f"1. PROBLEM: {task}",
            f"2. OBVIOUS ANSWER: Apply standard pattern for '{task[:50]}...'",
            f"3. SANITY CHECK: Verify assumptions hold for this specific case",
            f"4. CONFIDENCE: {conf}",
        ]
        raw = "\n".join(sections)
        return ReasoningTrace(
            mode="RAPID",
            confidence=conf,
            checkpoints_hit=4,
            escalations=1 if conf < 8 else 0,
            techniques_used=["RAPID STRIKE"],
            raw_output=raw,
        )


class LowConfidenceDeepHarness(ReasoningSwarmHarness):
    """Deep Think harness with controlled per-technique confidence."""

    def __init__(self, *args, technique_confidence: int = 5, **kwargs):
        super().__init__(*args, **kwargs)
        self._tech_confidence = technique_confidence

    def _run_deep(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        conf = self._tech_confidence

        for name, marker in DEEP_THINK_TECHNIQUES:
            section = (
                f"┌─ {name} ──────────────────────────────────────\n"
                f"│ Analysis of '{task[:40]}' — confidence: {conf}.\n"
                f"│ {marker}\n"
                f"└{'─' * 50}┘"
            )
            output_parts.append(section)
            techniques_used.append(name)

        summary = (
            f"\n🧠 DEEP THINK COMPLETE\n"
            f"Checkpoints Hit: 11/11\n"
            f"Confidence: {conf}\n"
            f"---\n"
            f"Final answer for: {task}"
        )
        output_parts.append(summary)

        return ReasoningTrace(
            mode="DEEP",
            confidence=conf,
            checkpoints_hit=11,
            escalations=1 if conf < 7 else 0,
            techniques_used=techniques_used,
            raw_output="\n".join(output_parts),
        )


class ControlledEnsembleHarness(ReasoningSwarmHarness):
    """Ensemble harness with controlled per-angle confidence."""

    def __init__(self, *args, angle_confidence: int | dict[str, int] = 4, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(angle_confidence, int):
            self._angle_conf = {a: angle_confidence for a in ENSEMBLE_ANGLES}
        else:
            self._angle_conf = angle_confidence

    def _run_ensemble(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        confidences: list[int] = []

        for angle in ENSEMBLE_ANGLES:
            conf = self._angle_conf.get(angle, 4)
            content = (
                f"ANGLE: {angle}. "
                f"Analysis of '{task}' from {angle.lower()} perspective. "
                f"Confidence: {conf}."
            )
            output_parts.append(f"ANGLE: {angle}\n{content}")
            techniques_used.append(f"ENSEMBLE:{angle}")
            confidences.append(conf)

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

        return ReasoningTrace(
            mode="ENSEMBLE",
            confidence=weighted_conf,
            checkpoints_hit=5,
            escalations=escalations,
            techniques_used=techniques_used,
            subprocess_calls=5,
            raw_output=raw,
        )


class ControlledMegamindHarness(ReasoningSwarmHarness):
    """Megamind harness with controlled per-iteration confidence."""

    def __init__(self, *args, iteration_confidence: list[int] | int = 5, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(iteration_confidence, int):
            self._iter_conf = [iteration_confidence] * 3
        else:
            self._iter_conf = list(iteration_confidence)

    def _run_megamind(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        max_iterations = 3

        output_parts.append(f"PHASE M1: Initial Deep Think Pass — task: {task}")
        for name, marker in DEEP_THINK_TECHNIQUES:
            output_parts.append(f"  {name}: {marker}")
            techniques_used.append(f"MEGA:M1:{name}")

        conf = 0
        agreement_level = ""
        iteration = 0

        for iteration in range(1, max_iterations + 1):
            output_parts.append(
                f"\nPHASE M2: 10 Angle-Explorers (iteration {iteration})"
            )
            for angle in MEGAMIND_ANGLES:
                output_parts.append(f"  ANGLE: {angle}")
                tech_key = f"MEGA:M2:{angle}"
                if tech_key not in techniques_used:
                    techniques_used.append(tech_key)

            output_parts.append(
                f"\nPHASE M3: 3 Synthesizers (iteration {iteration})"
            )
            for synth in MEGAMIND_SYNTHESIZERS:
                output_parts.append(f"  SYNTHESIZER {synth}")
                tech_key = f"MEGA:M3:{synth}"
                if tech_key not in techniques_used:
                    techniques_used.append(tech_key)

            conf = self._iter_conf[min(iteration - 1, len(self._iter_conf) - 1)]
            agreement_level = "7/10"

            output_parts.append(
                f"\nPHASE M4: Final Synthesis (iteration {iteration})\n"
                f"  CONFIDENCE: {conf}"
            )
            if "MEGA:M4:FINAL_SYNTHESIS" not in techniques_used:
                techniques_used.append("MEGA:M4:FINAL_SYNTHESIS")

            if conf >= 7:
                output_parts.append(f"  → Output (conf >= 7)")
                break
            elif iteration < max_iterations:
                output_parts.append(
                    f"  → Confidence {conf} < 7, looping back to Phase M2 "
                    f"(iteration {iteration + 1})"
                )
            else:
                output_parts.append(
                    f"  → Max iterations ({max_iterations}) reached with "
                    f"confidence {conf} < 7. Outputting with uncertainty flags."
                )

        raw = "\n".join(output_parts)
        raw += (
            f"\n\n🧠 MEGAMIND COMPLETE\n"
            f"Architecture: 10 → 3 → 1\n"
            f"Iterations: {iteration}\n"
            f"Agreement Level: {agreement_level} aligned\n"
            f"Final Confidence: {conf}"
        )

        return ReasoningTrace(
            mode="MEGA",
            confidence=conf,
            checkpoints_hit=13,
            escalations=0,
            techniques_used=techniques_used,
            subprocess_calls=13,
            raw_output=raw,
            iterations=iteration,
            agreement_level=agreement_level,
            conflicts=["Performance vs simplicity"],
            risks=["Edge case handling"],
        )


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def gate_evaluator():
    """Provide the confidence gate evaluator."""
    return evaluate_confidence_gate


@pytest.fixture
def rapid_low_harness():
    """Rapid Strike harness with confidence 6 (< 8 threshold)."""
    def _factory(task: str = "Fix typo") -> LowConfidenceRapidHarness:
        return LowConfidenceRapidHarness(
            task_description=task, mode_override="RAPID", rapid_confidence=6
        )
    return _factory


@pytest.fixture
def rapid_high_harness():
    """Rapid Strike harness with confidence 8 (>= 8 threshold)."""
    def _factory(task: str = "Fix typo") -> LowConfidenceRapidHarness:
        return LowConfidenceRapidHarness(
            task_description=task, mode_override="RAPID", rapid_confidence=8
        )
    return _factory


@pytest.fixture
def deep_low_harness():
    """Deep Think harness with confidence 5 (< 7 threshold)."""
    def _factory(task: str = "Refactor module") -> LowConfidenceDeepHarness:
        return LowConfidenceDeepHarness(
            task_description=task, mode_override="DEEP", technique_confidence=5
        )
    return _factory


@pytest.fixture
def ensemble_low_harness():
    """Ensemble harness with all angles at confidence 4 (< 7 threshold)."""
    def _factory(task: str = "Redesign auth") -> ControlledEnsembleHarness:
        return ControlledEnsembleHarness(
            task_description=task, mode_override="ENSEMBLE", angle_confidence=4
        )
    return _factory


@pytest.fixture
def megamind_low_harness():
    """Megamind harness with all iterations at confidence 5 (< 7 threshold)."""
    def _factory(
        task: str = "Migrate to microservices",
        conf: list[int] | int = 5,
    ) -> ControlledMegamindHarness:
        return ControlledMegamindHarness(
            task_description=task, mode_override="MEGA", iteration_confidence=conf
        )
    return _factory


# ═══════════════════════════════════════════════════════════════════════════
# Transition 1: Rapid Strike → Deep Think (confidence < 8)
# ═══════════════════════════════════════════════════════════════════════════


class TestRapidStrikeToDeepThinkGate:
    """Gate: Rapid Strike escalates to Deep Think when confidence < 8."""

    def test_gate_triggers_below_threshold(self, gate_evaluator):
        """Confidence 6 < 8 → escalate to DEEP THINK."""
        result = gate_evaluator("RAPID STRIKE", confidence=6)
        assert result == "DEEP THINK"

    def test_gate_triggers_at_7(self, gate_evaluator):
        """Confidence 7 < 8 → escalate to DEEP THINK."""
        result = gate_evaluator("RAPID STRIKE", confidence=7)
        assert result == "DEEP THINK"

    def test_gate_no_escalation_at_8(self, gate_evaluator):
        """Confidence 8 >= 8 → output directly."""
        result = gate_evaluator("RAPID STRIKE", confidence=8)
        assert result == "OUTPUT"

    def test_gate_no_escalation_at_9(self, gate_evaluator):
        """Confidence 9 >= 8 → output directly."""
        result = gate_evaluator("RAPID STRIKE", confidence=9)
        assert result == "OUTPUT"

    def test_gate_no_escalation_at_10(self, gate_evaluator):
        """Confidence 10 >= 8 → output directly."""
        result = gate_evaluator("RAPID STRIKE", confidence=10)
        assert result == "OUTPUT"

    @pytest.mark.parametrize("conf", [1, 3, 5, 6, 7])
    def test_all_below_threshold_escalate(self, gate_evaluator, conf):
        result = gate_evaluator("RAPID STRIKE", confidence=conf)
        assert result == "DEEP THINK", f"confidence={conf} should escalate"

    @pytest.mark.parametrize("conf", [8, 9, 10])
    def test_all_at_or_above_threshold_output(self, gate_evaluator, conf):
        result = gate_evaluator("RAPID STRIKE", confidence=conf)
        assert result == "OUTPUT", f"confidence={conf} should output"

    def test_harness_produces_confidence_below_8(self, rapid_low_harness):
        """Verify the low-confidence harness actually produces confidence < 8."""
        trace = rapid_low_harness().run()
        assert trace.confidence < 8
        assert trace.mode == "RAPID"

    def test_harness_produces_confidence_at_8(self, rapid_high_harness):
        """Verify the high-confidence harness produces confidence >= 8."""
        trace = rapid_high_harness().run()
        assert trace.confidence >= 8

    def test_escalation_preserves_task_context(self, rapid_low_harness):
        """Task description survives the rapid strike execution."""
        task = "Fix the off-by-one error in pagination"
        trace = rapid_low_harness(task).run()
        assert task in trace.raw_output

    def test_trace_shows_escalation_marker(self, rapid_low_harness):
        """Low-confidence rapid trace has escalation marker."""
        trace = rapid_low_harness().run()
        assert trace.escalations == 1


# ═══════════════════════════════════════════════════════════════════════════
# Transition 2: Deep Think → Ensemble (confidence < 7)
# ═══════════════════════════════════════════════════════════════════════════


class TestDeepThinkToEnsembleGate:
    """Gate: Deep Think escalates to Ensemble when confidence < 7."""

    def test_gate_triggers_below_threshold(self, gate_evaluator):
        """Confidence 6 < 7 → escalate to ENSEMBLE."""
        result = gate_evaluator("DEEP THINK", confidence=6)
        assert result == "ENSEMBLE"

    def test_gate_triggers_at_6(self, gate_evaluator):
        """Confidence 6 < 7 → escalate to ENSEMBLE."""
        result = gate_evaluator("DEEP THINK", confidence=6)
        assert result == "ENSEMBLE"

    def test_gate_no_escalation_at_7(self, gate_evaluator):
        """Confidence 7 >= 7 → output directly."""
        result = gate_evaluator("DEEP THINK", confidence=7)
        assert result == "OUTPUT"

    def test_gate_no_escalation_at_8(self, gate_evaluator):
        """Confidence 8 >= 7 → output directly."""
        result = gate_evaluator("DEEP THINK", confidence=8)
        assert result == "OUTPUT"

    @pytest.mark.parametrize("conf", [1, 3, 5, 6])
    def test_all_below_threshold_escalate(self, gate_evaluator, conf):
        result = gate_evaluator("DEEP THINK", confidence=conf)
        assert result == "ENSEMBLE", f"confidence={conf} should escalate"

    @pytest.mark.parametrize("conf", [7, 8, 9, 10])
    def test_all_at_or_above_threshold_output(self, gate_evaluator, conf):
        result = gate_evaluator("DEEP THINK", confidence=conf)
        assert result == "OUTPUT", f"confidence={conf} should output"

    def test_harness_produces_low_confidence(self, deep_low_harness):
        """Verify the controlled deep harness produces confidence < 7."""
        trace = deep_low_harness().run()
        assert trace.confidence < 7
        assert trace.mode == "DEEP"

    def test_all_techniques_present_on_escalation(self, deep_low_harness):
        """Even when escalating, all 11 techniques are present."""
        trace = deep_low_harness().run()
        for name, _ in DEEP_THINK_TECHNIQUES:
            assert name in trace.techniques_used

    def test_escalation_preserves_task_context(self, deep_low_harness):
        """Task description survives deep think execution."""
        task = "Add rate limiting to the API gateway"
        trace = deep_low_harness(task).run()
        assert task in trace.raw_output

    def test_checkpoint_count_preserved(self, deep_low_harness):
        """All 11 checkpoints hit regardless of confidence."""
        trace = deep_low_harness().run()
        assert trace.checkpoints_hit == 11


# ═══════════════════════════════════════════════════════════════════════════
# Transition 3: Ensemble → Megamind (confidence < 7)
# ═══════════════════════════════════════════════════════════════════════════


class TestEnsembleToMegamindGate:
    """Gate: Ensemble escalates to Megamind when confidence < 7."""

    def test_gate_triggers_below_threshold(self, gate_evaluator):
        """Confidence 6 < 7 → escalate to MEGAMIND."""
        result = gate_evaluator("ENSEMBLE", confidence=6)
        assert result == "MEGAMIND"

    def test_gate_no_escalation_at_7(self, gate_evaluator):
        """Confidence 7 >= 7 → output directly."""
        result = gate_evaluator("ENSEMBLE", confidence=7)
        assert result == "OUTPUT"

    def test_gate_no_escalation_at_8(self, gate_evaluator):
        """Confidence 8 >= 7 → output directly."""
        result = gate_evaluator("ENSEMBLE", confidence=8)
        assert result == "OUTPUT"

    @pytest.mark.parametrize("conf", [1, 3, 5, 6])
    def test_all_below_threshold_escalate(self, gate_evaluator, conf):
        result = gate_evaluator("ENSEMBLE", confidence=conf)
        assert result == "MEGAMIND", f"confidence={conf} should escalate"

    @pytest.mark.parametrize("conf", [7, 8, 9, 10])
    def test_all_at_or_above_threshold_output(self, gate_evaluator, conf):
        result = gate_evaluator("ENSEMBLE", confidence=conf)
        assert result == "OUTPUT", f"confidence={conf} should output"

    def test_low_confidence_harness_triggers_escalation(self, ensemble_low_harness):
        """Controlled ensemble with all angles at 4 → weighted avg = 4 → escalates."""
        trace = ensemble_low_harness().run()
        assert trace.confidence < 7
        assert trace.escalations == 1
        assert "ESCALATION" in trace.raw_output

    def test_escalation_text_mentions_megamind(self, ensemble_low_harness):
        """Escalation text explicitly mentions MEGAMIND."""
        trace = ensemble_low_harness().run()
        assert "MEGAMIND" in trace.raw_output

    def test_all_angles_complete_on_escalation(self, ensemble_low_harness):
        """All 5 angles still execute even when escalating."""
        trace = ensemble_low_harness().run()
        for angle in ENSEMBLE_ANGLES:
            assert f"ENSEMBLE:{angle}" in trace.techniques_used

    def test_synthesis_still_produced_on_escalation(self, ensemble_low_harness):
        """Synthesis section is present even when escalating."""
        trace = ensemble_low_harness().run()
        assert "SYNTHESIS:" in trace.raw_output

    def test_escalation_preserves_task_context(self, ensemble_low_harness):
        """Task description survives ensemble execution."""
        task = "Design a distributed caching strategy"
        trace = ensemble_low_harness(task).run()
        assert task in trace.raw_output

    def test_weighted_confidence_calculation(self):
        """Verify weighted confidence with mixed angles."""
        h = ControlledEnsembleHarness(
            task_description="test",
            mode_override="ENSEMBLE",
            angle_confidence={
                "PERFORMANCE": 8,
                "SIMPLICITY": 8,
                "SECURITY": 8,
                "EDGE CASES": 8,
                "DEVIL'S ADVOCATE": 8,
            },
        )
        trace = h.run()
        assert trace.confidence == 8
        assert trace.escalations == 0

    def test_borderline_confidence_6(self):
        """Confidence averaging exactly 6 → escalates."""
        h = ControlledEnsembleHarness(
            task_description="test",
            mode_override="ENSEMBLE",
            angle_confidence={
                "PERFORMANCE": 6,
                "SIMPLICITY": 6,
                "SECURITY": 6,
                "EDGE CASES": 6,
                "DEVIL'S ADVOCATE": 6,
            },
        )
        trace = h.run()
        assert trace.confidence == 6
        assert trace.escalations == 1


# ═══════════════════════════════════════════════════════════════════════════
# Transition 4: Megamind → Grand Jury (confidence < 7 + prior fail)
# ═══════════════════════════════════════════════════════════════════════════


class TestMegamindToGrandJuryGate:
    """Gate: Megamind escalates to Grand Jury when confidence < 7 AND prior_fails >= 1."""

    def test_gate_triggers_with_prior_fail(self, gate_evaluator):
        """Confidence 5 < 7 + prior_fails=1 → GRAND JURY."""
        result = gate_evaluator("MEGAMIND", confidence=5, prior_fails=1)
        assert result == "GRAND JURY"

    def test_gate_triggers_with_multiple_prior_fails(self, gate_evaluator):
        """Confidence 6 < 7 + prior_fails=2 → GRAND JURY."""
        result = gate_evaluator("MEGAMIND", confidence=6, prior_fails=2)
        assert result == "GRAND JURY"

    def test_no_escalation_without_prior_fail(self, gate_evaluator):
        """Confidence 5 < 7 but no prior fail → LOOP (not GRAND JURY)."""
        result = gate_evaluator("MEGAMIND", confidence=5, prior_fails=0)
        assert result == "LOOP"

    def test_no_escalation_high_confidence_with_prior_fail(self, gate_evaluator):
        """Confidence 8 >= 7 → OUTPUT even with prior fails."""
        result = gate_evaluator("MEGAMIND", confidence=8, prior_fails=1)
        assert result == "OUTPUT"

    def test_no_escalation_high_confidence_no_prior_fail(self, gate_evaluator):
        """Confidence 7 >= 7 → OUTPUT without prior fails."""
        result = gate_evaluator("MEGAMIND", confidence=7, prior_fails=0)
        assert result == "OUTPUT"

    @pytest.mark.parametrize("prior_fails", [1, 2, 5])
    def test_any_positive_prior_fail_triggers(self, gate_evaluator, prior_fails):
        """Any prior_fails >= 1 with confidence < 7 → GRAND JURY."""
        result = gate_evaluator("MEGAMIND", confidence=5, prior_fails=prior_fails)
        assert result == "GRAND JURY"

    @pytest.mark.parametrize("conf", [1, 3, 5, 6])
    def test_all_below_threshold_with_prior_fail(self, gate_evaluator, conf):
        result = gate_evaluator("MEGAMIND", confidence=conf, prior_fails=1)
        assert result == "GRAND JURY", f"confidence={conf} + prior_fail should go to GRAND JURY"

    def test_prior_fail_routing_via_intake_classifier(self):
        """BUG_FIX + prior_fails >= 1 routes to GRAND JURY via intake classifier."""
        mode = classify_task(
            "BUG_FIX", "LOW", "LOW", prior_fails=1,
        )
        assert mode == "GRAND JURY"

    def test_prior_fail_floor_ensemble_via_intake(self):
        """IMPLEMENTATION + prior_fails >= 1 → floor to ENSEMBLE (not GRAND JURY)."""
        mode = classify_task(
            "IMPLEMENTATION", "LOW", "LOW", prior_fails=1,
        )
        assert mode == "ENSEMBLE"


# ═══════════════════════════════════════════════════════════════════════════
# Transition 5: Megamind → Loop (confidence < 7, iterations < 3)
# ═══════════════════════════════════════════════════════════════════════════


class TestMegamindLoopGate:
    """Gate: Megamind loops back when confidence < 7 AND iterations < 3."""

    def test_gate_loops_on_iteration_1(self, gate_evaluator):
        """Confidence 5 < 7, iteration 1 < 3 → LOOP."""
        result = gate_evaluator("MEGAMIND", confidence=5, iterations=1, max_iterations=3)
        assert result == "LOOP"

    def test_gate_loops_on_iteration_2(self, gate_evaluator):
        """Confidence 5 < 7, iteration 2 < 3 → LOOP."""
        result = gate_evaluator("MEGAMIND", confidence=5, iterations=2, max_iterations=3)
        assert result == "LOOP"

    def test_gate_stops_on_iteration_3(self, gate_evaluator):
        """Confidence 5 < 7, iteration 3 == 3 → OUTPUT (cap reached)."""
        result = gate_evaluator("MEGAMIND", confidence=5, iterations=3, max_iterations=3)
        assert result == "OUTPUT"

    def test_no_loop_when_confidence_high(self, gate_evaluator):
        """Confidence 8 >= 7 → OUTPUT even on iteration 1."""
        result = gate_evaluator("MEGAMIND", confidence=8, iterations=1, max_iterations=3)
        assert result == "OUTPUT"

    def test_no_loop_when_confidence_exactly_7(self, gate_evaluator):
        """Confidence 7 >= 7 → OUTPUT (threshold met)."""
        result = gate_evaluator("MEGAMIND", confidence=7, iterations=1, max_iterations=3)
        assert result == "OUTPUT"

    def test_harness_loops_with_low_confidence(self, megamind_low_harness):
        """Megamind harness with confidence 5 across all iterations loops 3 times."""
        trace = megamind_low_harness().run()
        assert trace.iterations == 3
        assert trace.confidence == 5
        assert "looping back to Phase M2" in trace.raw_output

    def test_harness_stops_on_high_confidence(self):
        """Megamind harness with confidence 8 stops at iteration 1."""
        h = ControlledMegamindHarness(
            task_description="Simple refactor",
            mode_override="MEGA",
            iteration_confidence=8,
        )
        trace = h.run()
        assert trace.iterations == 1
        assert trace.confidence >= 7

    def test_harness_early_stop_on_confidence_increase(self):
        """Megamind with rising confidence: 5, 5, 8 → stops at iteration 3."""
        h = ControlledMegamindHarness(
            task_description="Evolving task",
            mode_override="MEGA",
            iteration_confidence=[5, 5, 8],
        )
        trace = h.run()
        assert trace.iterations == 3
        assert trace.confidence == 8

    def test_harness_early_stop_at_iteration_2(self):
        """Megamind with rising confidence: 4, 8 → stops at iteration 2."""
        h = ControlledMegamindHarness(
            task_description="Quick convergence",
            mode_override="MEGA",
            iteration_confidence=[4, 8, 5],
        )
        trace = h.run()
        assert trace.iterations == 2
        assert trace.confidence == 8

    def test_max_iterations_message_on_cap(self, megamind_low_harness):
        """When capped at 3 iterations, output mentions max iterations."""
        trace = megamind_low_harness().run()
        assert "Max iterations (3) reached" in trace.raw_output
        assert "uncertainty flags" in trace.raw_output.lower()

    def test_all_phases_present_per_iteration(self, megamind_low_harness):
        """Each iteration has M2, M3, M4 phases."""
        trace = megamind_low_harness().run()
        import re
        for phase in ["M2", "M3", "M4"]:
            matches = re.findall(
                rf"PHASE {phase}.*?iteration\s+\d", trace.raw_output
            )
            assert len(matches) >= 3, f"Expected 3+ {phase} phases, got {len(matches)}"

    def test_no_prior_fail_means_loop_not_jury(self, gate_evaluator):
        """Low confidence without prior fail → LOOP, not GRAND JURY."""
        result = gate_evaluator("MEGAMIND", confidence=5, prior_fails=0, iterations=1)
        assert result == "LOOP"


# ═══════════════════════════════════════════════════════════════════════════
# Transition 6: Megamind → Output (confidence >= 7 OR iterations = 3)
# ═══════════════════════════════════════════════════════════════════════════


class TestMegamindOutputGate:
    """Gate: Megamind outputs when confidence >= 7 OR iterations = 3."""

    def test_output_on_high_confidence(self, gate_evaluator):
        """Confidence 7 >= 7 → OUTPUT."""
        result = gate_evaluator("MEGAMIND", confidence=7)
        assert result == "OUTPUT"

    def test_output_on_confidence_8(self, gate_evaluator):
        """Confidence 8 >= 7 → OUTPUT."""
        result = gate_evaluator("MEGAMIND", confidence=8)
        assert result == "OUTPUT"

    def test_output_on_confidence_10(self, gate_evaluator):
        """Confidence 10 >= 7 → OUTPUT."""
        result = gate_evaluator("MEGAMIND", confidence=10)
        assert result == "OUTPUT"

    def test_output_on_max_iterations(self, gate_evaluator):
        """Confidence 5 < 7 but iterations == 3 → OUTPUT."""
        result = gate_evaluator("MEGAMIND", confidence=5, iterations=3, max_iterations=3)
        assert result == "OUTPUT"

    def test_no_output_below_7_under_3_iters(self, gate_evaluator):
        """Confidence 5 < 7, iterations 1 < 3 → LOOP (not OUTPUT)."""
        result = gate_evaluator("MEGAMIND", confidence=5, iterations=1, max_iterations=3)
        assert result == "LOOP"

    def test_harness_completes_with_confidence_7(self):
        """Megamind with confidence 7 completes in 1 iteration."""
        h = ControlledMegamindHarness(
            task_description="Balanced task",
            mode_override="MEGA",
            iteration_confidence=7,
        )
        trace = h.run()
        assert trace.confidence == 7
        assert trace.iterations == 1

    def test_harness_completes_with_confidence_9(self):
        """Megamind with confidence 9 completes immediately."""
        h = ControlledMegamindHarness(
            task_description="Easy task",
            mode_override="MEGA",
            iteration_confidence=9,
        )
        trace = h.run()
        assert trace.confidence == 9
        assert trace.iterations == 1
        assert "looping back" not in trace.raw_output

    @pytest.mark.parametrize("conf", [7, 8, 9, 10])
    def test_all_high_confidences_output_immediately(self, gate_evaluator, conf):
        result = gate_evaluator("MEGAMIND", confidence=conf, iterations=1)
        assert result == "OUTPUT"

    def test_trace_has_megamind_complete_marker(self):
        """Completed megamind trace has the completion marker."""
        h = ControlledMegamindHarness(
            task_description="test",
            mode_override="MEGA",
            iteration_confidence=8,
        )
        trace = h.run()
        assert "🧠 MEGAMIND COMPLETE" in trace.raw_output


# ═══════════════════════════════════════════════════════════════════════════
# Context preservation across escalations
# ═══════════════════════════════════════════════════════════════════════════


class TestContextPreservation:
    """Verify task context is preserved across each escalation transition."""

    TASK = "Implement OAuth2 token refresh with automatic retry"

    def test_rapid_to_deep_preserves_context(self, rapid_low_harness):
        trace = rapid_low_harness(self.TASK).run()
        assert self.TASK in trace.raw_output

    def test_deep_to_ensemble_preserves_context(self, deep_low_harness):
        trace = deep_low_harness(self.TASK).run()
        assert self.TASK in trace.raw_output

    def test_ensemble_to_megamind_preserves_context(self, ensemble_low_harness):
        trace = ensemble_low_harness(self.TASK).run()
        assert self.TASK in trace.raw_output

    def test_megamind_loop_preserves_context(self, megamind_low_harness):
        """Context survives through all 3 loop iterations."""
        trace = megamind_low_harness(self.TASK).run()
        assert self.TASK in trace.raw_output
        # Each iteration should reference the task
        assert trace.raw_output.count(self.TASK) >= 1

    def test_techniques_preserved_through_escalation(self, ensemble_low_harness):
        """Technique list is complete even when escalating."""
        trace = ensemble_low_harness().run()
        assert len(trace.techniques_used) == 6  # 5 angles + synthesis

    def test_checkpoints_preserved_through_escalation(self, deep_low_harness):
        """Checkpoint count is maintained when escalating."""
        trace = deep_low_harness().run()
        assert trace.checkpoints_hit == 11

    def test_evidence_structure_preserved(self, ensemble_low_harness):
        """Raw output has both angle sections and synthesis when escalating."""
        trace = ensemble_low_harness().run()
        for angle in ENSEMBLE_ANGLES:
            assert f"ANGLE: {angle}" in trace.raw_output
        assert "SYNTHESIS:" in trace.raw_output

    def test_megamind_phases_preserved_on_loop(self, megamind_low_harness):
        """M1 phase present even after looping."""
        trace = megamind_low_harness().run()
        assert "PHASE M1" in trace.raw_output
        # M1 should appear exactly once
        assert trace.raw_output.count("PHASE M1") == 1

    def test_intake_classifier_context_preserved_through_modes(self):
        """classify_task preserves mode selection across parameter variations."""
        base = classify_task("IMPLEMENTATION", "MEDIUM", "MEDIUM")
        assert base == "DEEP THINK"

        escalated = classify_task("IMPLEMENTATION", "MEDIUM", "MEDIUM", user_hint="think harder")
        assert escalated == "ENSEMBLE"

        # Original mode unchanged
        assert classify_task("IMPLEMENTATION", "MEDIUM", "MEDIUM") == "DEEP THINK"


# ═══════════════════════════════════════════════════════════════════════════
# De-escalation: confidence 9+ can skip modes
# ═══════════════════════════════════════════════════════════════════════════


class TestDeEscalation:
    """Verify that high confidence (9+) allows skipping escalation modes."""

    def test_can_skip_check(self):
        assert can_skip_to_output(9) is True
        assert can_skip_to_output(10) is True
        assert can_skip_to_output(8) is False
        assert can_skip_to_output(7) is False

    def test_rapid_confidence_9_skips_deep_think(self, gate_evaluator):
        """Rapid Strike with confidence 9 → direct OUTPUT, no Deep Think."""
        result = gate_evaluator("RAPID STRIKE", confidence=9)
        assert result == "OUTPUT"

    def test_rapid_confidence_10_skips_deep_think(self, gate_evaluator):
        """Rapid Strike with confidence 10 → direct OUTPUT."""
        result = gate_evaluator("RAPID STRIKE", confidence=10)
        assert result == "OUTPUT"

    def test_deep_confidence_9_skips_ensemble(self, gate_evaluator):
        """Deep Think with confidence 9 → OUTPUT, no Ensemble."""
        result = gate_evaluator("DEEP THINK", confidence=9)
        assert result == "OUTPUT"

    def test_ensemble_confidence_9_skips_megamind(self, gate_evaluator):
        """Ensemble with confidence 9 → OUTPUT, no Megamind."""
        result = gate_evaluator("ENSEMBLE", confidence=9)
        assert result == "OUTPUT"

    def test_megamind_confidence_9_skips_loop(self, gate_evaluator):
        """Megamind with confidence 9 → OUTPUT, no looping."""
        result = gate_evaluator("MEGAMIND", confidence=9)
        assert result == "OUTPUT"

    def test_high_confidence_harness_no_escalation(self):
        """Ensemble with all angles at 8 → no escalation."""
        h = ControlledEnsembleHarness(
            task_description="test",
            mode_override="ENSEMBLE",
            angle_confidence=8,
        )
        trace = h.run()
        assert trace.confidence == 8
        assert trace.escalations == 0
        assert "ESCALATION" not in trace.raw_output

    def test_megamind_high_confidence_no_loop(self):
        """Megamind with confidence 9 completes in 1 iteration without looping."""
        h = ControlledMegamindHarness(
            task_description="test",
            mode_override="MEGA",
            iteration_confidence=9,
        )
        trace = h.run()
        assert trace.iterations == 1
        assert "looping back" not in trace.raw_output

    def test_deescalation_preserves_full_output(self):
        """Even when de-escalating (skipping), output is complete."""
        h = ControlledEnsembleHarness(
            task_description="Simple task with high confidence",
            mode_override="ENSEMBLE",
            angle_confidence=9,
        )
        trace = h.run()
        assert "ENSEMBLE COMPLETE" in trace.raw_output
        assert "SYNTHESIS:" in trace.raw_output
        for angle in ENSEMBLE_ANGLES:
            assert f"ANGLE: {angle}" in trace.raw_output

    @pytest.mark.parametrize("mode", ["RAPID STRIKE", "DEEP THINK", "ENSEMBLE", "MEGAMIND"])
    def test_all_modes_skip_at_confidence_9(self, gate_evaluator, mode):
        """Every mode outputs directly at confidence 9."""
        result = gate_evaluator(mode, confidence=9)
        assert result == "OUTPUT"

    @pytest.mark.parametrize("mode", ["RAPID STRIKE", "DEEP THINK", "ENSEMBLE", "MEGAMIND"])
    def test_all_modes_skip_at_confidence_10(self, gate_evaluator, mode):
        """Every mode outputs directly at confidence 10."""
        result = gate_evaluator(mode, confidence=10)
        assert result == "OUTPUT"


# ═══════════════════════════════════════════════════════════════════════════
# Override: 'think harder' + confidence 8 → still escalates
# ═══════════════════════════════════════════════════════════════════════════


class TestThinkHarderOverrideWithConfidence:
    """'think harder' override escalates mode regardless of confidence score."""

    def test_think_harder_rapid_to_deep(self):
        """LOW/LOW → RAPID STRIKE base, 'think harder' → DEEP THINK."""
        mode = classify_task(
            "IMPLEMENTATION", "LOW", "LOW", user_hint="think harder"
        )
        assert mode == "DEEP THINK"

    def test_think_harder_deep_to_ensemble(self):
        """MEDIUM/LOW → DEEP THINK base, 'think harder' → ENSEMBLE."""
        mode = classify_task(
            "IMPLEMENTATION", "MEDIUM", "LOW", user_hint="think harder"
        )
        assert mode == "ENSEMBLE"

    def test_think_harder_ensemble_to_megamind(self):
        """HIGH/LOW → ENSEMBLE base, 'think harder' → MEGAMIND."""
        mode = classify_task(
            "IMPLEMENTATION", "HIGH", "LOW", user_hint="think harder"
        )
        assert mode == "MEGAMIND"

    def test_think_harder_blocked_by_critical_stakes_for_escalation(self):
        """LOW/CRITICAL → MEGAMIND base. 'think harder' is blocked by CRITICAL stakes → stays MEGAMIND."""
        mode = classify_task(
            "IMPLEMENTATION", "LOW", "CRITICAL", user_hint="think harder"
        )
        assert mode == "MEGAMIND"

    def test_think_harder_grand_jury_stays(self):
        """GRAND JURY → stays GRAND JURY (top of ladder)."""
        mode = classify_task(
            "INVESTIGATION", "LOW", "LOW", user_hint="think harder"
        )
        assert mode == "GRAND JURY"

    def test_think_harder_overrides_high_confidence(self):
        """Even though MEDIUM complexity yields DEEP THINK (confident choice),
        'think harder' forces escalation to ENSEMBLE.

        This tests that the override operates at the intake level,
        independent of how confident the initial classification was.
        """
        mode = classify_task(
            "IMPLEMENTATION", "MEDIUM", "MEDIUM", user_hint="think harder"
        )
        assert mode == "ENSEMBLE"

    def test_think_harder_blocked_by_critical_stakes(self):
        """CRITICAL stakes always → MEGAMIND, 'think harder' override is blocked."""
        mode = classify_task(
            "IMPLEMENTATION", "LOW", "CRITICAL", user_hint="think harder"
        )
        # CRITICAL → MEGAMIND base, think harder is blocked → stays MEGAMIND
        assert mode == "MEGAMIND"

    def test_think_harder_with_high_complexity(self):
        """HIGH complexity → ENSEMBLE, 'think harder' → MEGAMIND."""
        mode = classify_task(
            "ARCHITECTURE", "HIGH", "HIGH", user_hint="think harder"
        )
        assert mode == "MEGAMIND"

    def test_think_harder_rapid_strike_confidence_8(self):
        """RAPID STRIKE base with 'think harder' → DEEP THINK.
        This is the core test: intake override escalates even though
        the base classification was confident (RAPID STRIKE).
        """
        mode = classify_task(
            "IMPLEMENTATION", "LOW", "LOW", user_hint="think harder"
        )
        assert mode == "DEEP THINK"
        # The gate evaluator confirms that at confidence 8, RAPID STRIKE
        # would normally output without escalation
        assert evaluate_confidence_gate("RAPID STRIKE", confidence=8) == "OUTPUT"
        # But 'think harder' forces the escalation at intake level
        # So the system runs DEEP THINK instead of RAPID STRIKE

    def test_think_harder_case_insensitive(self):
        """'think harder' works regardless of case."""
        mode = classify_task(
            "IMPLEMENTATION", "LOW", "LOW", user_hint="THINK HARDER"
        )
        assert mode == "DEEP THINK"

    def test_think_harder_substring_match(self):
        """'think harder' matches as substring in longer hint."""
        mode = classify_task(
            "IMPLEMENTATION", "LOW", "LOW", user_hint="please think harder about this"
        )
        assert mode == "DEEP THINK"


# ═══════════════════════════════════════════════════════════════════════════
# Override: 'quick' + confidence 4 → RAPID STRIKE (unless CRITICAL)
# ═══════════════════════════════════════════════════════════════════════════


class TestQuickOverrideWithConfidence:
    """'quick' override forces RAPID STRIKE regardless of complexity/confidence."""

    def test_quick_overrides_medium_complexity(self):
        """MEDIUM → DEEP THINK base, 'quick' → RAPID STRIKE."""
        mode = classify_task(
            "IMPLEMENTATION", "MEDIUM", "LOW", user_hint="quick"
        )
        assert mode == "RAPID STRIKE"

    def test_quick_overrides_high_complexity(self):
        """HIGH → ENSEMBLE base, 'quick' → RAPID STRIKE."""
        mode = classify_task(
            "IMPLEMENTATION", "HIGH", "LOW", user_hint="quick"
        )
        assert mode == "RAPID STRIKE"

    def test_quick_overrides_extreme_complexity(self):
        """EXTREME → MEGAMIND base, 'quick' → RAPID STRIKE."""
        mode = classify_task(
            "ARCHITECTURE", "EXTREME", "LOW", user_hint="quick"
        )
        assert mode == "RAPID STRIKE"

    def test_quick_blocked_by_critical_stakes(self):
        """CRITICAL stakes prevents 'quick' override — stays MEGAMIND."""
        mode = classify_task(
            "IMPLEMENTATION", "LOW", "CRITICAL", user_hint="quick"
        )
        assert mode == "MEGAMIND"

    def test_just_do_it_overrides_ensemble(self):
        """'just do it' works same as 'quick'."""
        mode = classify_task(
            "IMPLEMENTATION", "HIGH", "LOW", user_hint="just do it"
        )
        assert mode == "RAPID STRIKE"

    def test_just_do_it_blocked_by_critical(self):
        """'just do it' blocked by CRITICAL stakes."""
        mode = classify_task(
            "IMPLEMENTATION", "LOW", "CRITICAL", user_hint="just do it"
        )
        assert mode == "MEGAMIND"

    def test_quick_with_low_confidence_problem(self):
        """'quick' forces RAPID STRIKE even for a complex problem.
        The harness produces confidence 8 for RAPID STRIKE, which passes
        the gate (>= 8). But 'quick' overrides the mode selection entirely.
        """
        mode = classify_task(
            "ARCHITECTURE", "HIGH", "HIGH", user_hint="quick"
        )
        assert mode == "RAPID STRIKE"
        # RAPID STRIKE gate: confidence 8 >= 8 → OUTPUT
        assert evaluate_confidence_gate("RAPID STRIKE", confidence=8) == "OUTPUT"

    def test_quick_with_prior_fail_gets_floored(self):
        """'quick' forces RAPID STRIKE, but prior fail floor → ENSEMBLE."""
        mode = classify_task(
            "IMPLEMENTATION", "MEDIUM", "MEDIUM", prior_fails=1, user_hint="quick"
        )
        assert mode == "ENSEMBLE"

    def test_quick_case_insensitive(self):
        """'quick' works regardless of case."""
        mode = classify_task(
            "IMPLEMENTATION", "MEDIUM", "LOW", user_hint="QUICK"
        )
        assert mode == "RAPID STRIKE"

    def test_quick_substring_match(self):
        """'quick' matches as substring."""
        mode = classify_task(
            "IMPLEMENTATION", "MEDIUM", "LOW", user_hint="do a quick fix"
        )
        assert mode == "RAPID STRIKE"

    def test_quick_stakes_medium_allowed(self):
        """'quick' works with MEDIUM stakes (only CRITICAL is blocked)."""
        mode = classify_task(
            "IMPLEMENTATION", "HIGH", "MEDIUM", user_hint="quick"
        )
        assert mode == "RAPID STRIKE"

    def test_quick_stakes_high_allowed(self):
        """'quick' works with HIGH stakes (only CRITICAL is blocked)."""
        mode = classify_task(
            "IMPLEMENTATION", "HIGH", "HIGH", user_hint="quick"
        )
        assert mode == "RAPID STRIKE"


# ═══════════════════════════════════════════════════════════════════════════
# Override interaction: 'think harder' + 'quick' together
# ═══════════════════════════════════════════════════════════════════════════


class TestOverrideInteractions:
    """Test how multiple override rules interact."""

    def test_quick_then_think_harder(self):
        """Both 'quick' and 'think harder' in hint:
        'quick' fires first → RAPID STRIKE, then 'think harder' → DEEP THINK.
        """
        mode = classify_task(
            "IMPLEMENTATION", "HIGH", "LOW",
            user_hint="quick think harder",
        )
        assert mode == "DEEP THINK"

    def test_think_harder_with_prior_fail(self):
        """'think harder' escalates RAPID → DEEP, then prior fail floor → ENSEMBLE."""
        mode = classify_task(
            "IMPLEMENTATION", "LOW", "LOW", prior_fails=1,
            user_hint="think harder",
        )
        assert mode == "ENSEMBLE"

    def test_quick_with_prior_fail(self):
        """'quick' forces RAPID, then prior fail floor → ENSEMBLE."""
        mode = classify_task(
            "IMPLEMENTATION", "MEDIUM", "MEDIUM", prior_fails=1,
            user_hint="quick",
        )
        assert mode == "ENSEMBLE"

    def test_critical_stakes_blocks_all_overrides(self):
        """CRITICAL stakes → MEGAMIND, blocks 'quick' override.
        'think harder' is also blocked by CRITICAL stakes → stays MEGAMIND.
        """
        mode_quick = classify_task(
            "IMPLEMENTATION", "LOW", "CRITICAL", user_hint="quick"
        )
        assert mode_quick == "MEGAMIND"

        mode_think = classify_task(
            "IMPLEMENTATION", "LOW", "CRITICAL", user_hint="think harder"
        )
        assert mode_think == "MEGAMIND"

    def test_investigation_overrides_complexity(self):
        """INVESTIGATION type always → GRAND JURY regardless of complexity."""
        mode = classify_task(
            "INVESTIGATION", "LOW", "LOW"
        )
        assert mode == "GRAND JURY"

    def test_unknown_task_always_megamind(self):
        """UNKNOWN task type always → MEGAMIND."""
        mode = classify_task("UNKNOWN", "LOW", "LOW")
        assert mode == "MEGAMIND"

    def test_override_order_preserved(self):
        """Verify the order: quick → think harder → prior fail floor.
        quick sets RAPID, think harder escalates to DEEP, no prior fail.
        """
        mode = classify_task(
            "IMPLEMENTATION", "MEDIUM", "LOW", prior_fails=0,
            user_hint="quick think harder",
        )
        assert mode == "DEEP THINK"

    def test_override_order_with_prior_fail(self):
        """quick → RAPID, think harder → DEEP, prior fail → ENSEMBLE."""
        mode = classify_task(
            "IMPLEMENTATION", "MEDIUM", "LOW", prior_fails=1,
            user_hint="quick think harder",
        )
        assert mode == "ENSEMBLE"


# ═══════════════════════════════════════════════════════════════════════════
# Full chain simulation: intake → gate → escalation
# ═══════════════════════════════════════════════════════════════════════════


class TestFullChainSimulation:
    """Simulate the complete flow: intake classification → confidence gate → escalation."""

    def test_low_complexity_rapid_strike_outputs(self):
        """LOW/LOW → RAPID STRIKE → confidence 8 → OUTPUT."""
        mode = classify_task("IMPLEMENTATION", "LOW", "LOW")
        assert mode == "RAPID STRIKE"
        action = evaluate_confidence_gate(mode, confidence=8)
        assert action == "OUTPUT"

    def test_medium_complexity_deep_think_outputs(self):
        """MEDIUM → DEEP THINK → confidence 7 → OUTPUT."""
        mode = classify_task("IMPLEMENTATION", "MEDIUM", "LOW")
        assert mode == "DEEP THINK"
        action = evaluate_confidence_gate(mode, confidence=7)
        assert action == "OUTPUT"

    def test_high_complexity_escalates_to_megamind(self):
        """HIGH → ENSEMBLE → confidence 5 → MEGAMIND."""
        mode = classify_task("IMPLEMENTATION", "HIGH", "LOW")
        assert mode == "ENSEMBLE"
        action = evaluate_confidence_gate(mode, confidence=5)
        assert action == "MEGAMIND"

    def test_extreme_complexity_megamind_loops(self):
        """EXTREME → MEGAMIND → confidence 5, iter 1 → LOOP."""
        mode = classify_task("IMPLEMENTATION", "EXTREME", "LOW")
        assert mode == "MEGAMIND"
        action = evaluate_confidence_gate(mode, confidence=5, iterations=1)
        assert action == "LOOP"

    def test_extreme_complexity_megamind_caps(self):
        """EXTREME → MEGAMIND → confidence 5, iter 3 → OUTPUT (cap)."""
        mode = classify_task("IMPLEMENTATION", "EXTREME", "LOW")
        assert mode == "MEGAMIND"
        action = evaluate_confidence_gate(mode, confidence=5, iterations=3)
        assert action == "OUTPUT"

    def test_critical_stakes_full_chain(self):
        """CRITICAL → MEGAMIND → confidence 8 → OUTPUT."""
        mode = classify_task("IMPLEMENTATION", "LOW", "CRITICAL")
        assert mode == "MEGAMIND"
        action = evaluate_confidence_gate(mode, confidence=8)
        assert action == "OUTPUT"

    def test_bug_prior_fail_grand_jury_chain(self):
        """BUG_FIX + prior_fails → GRAND JURY (always outputs)."""
        mode = classify_task("BUG_FIX", "LOW", "LOW", prior_fails=1)
        assert mode == "GRAND JURY"
        action = evaluate_confidence_gate(mode, confidence=5)
        assert action == "OUTPUT"

    def test_quick_override_full_chain(self):
        """HIGH/LOW + 'quick' → RAPID STRIKE → confidence 8 → OUTPUT."""
        mode = classify_task("IMPLEMENTATION", "HIGH", "LOW", user_hint="quick")
        assert mode == "RAPID STRIKE"
        action = evaluate_confidence_gate(mode, confidence=8)
        assert action == "OUTPUT"

    def test_think_harder_full_chain(self):
        """LOW/LOW + 'think harder' → DEEP THINK → confidence 6 → ENSEMBLE."""
        mode = classify_task("IMPLEMENTATION", "LOW", "LOW", user_hint="think harder")
        assert mode == "DEEP THINK"
        action = evaluate_confidence_gate(mode, confidence=6)
        assert action == "ENSEMBLE"

    def test_full_escalation_chain(self):
        """Trace the complete escalation: DEEP → ENSEMBLE → MEGAMIND → OUTPUT."""
        # Start at DEEP THINK
        mode = "DEEP THINK"
        action1 = evaluate_confidence_gate(mode, confidence=5)
        assert action1 == "ENSEMBLE"

        # Escalate to ENSEMBLE
        action2 = evaluate_confidence_gate("ENSEMBLE", confidence=4)
        assert action2 == "MEGAMIND"

        # Escalate to MEGAMIND, gets high confidence on iteration 2
        action3 = evaluate_confidence_gate("MEGAMIND", confidence=8, iterations=2)
        assert action3 == "OUTPUT"

    def test_prior_fail_escalation_chain(self):
        """ENSEMBLE → MEGAMIND (low conf) → GRAND JURY (prior fail)."""
        action1 = evaluate_confidence_gate("ENSEMBLE", confidence=5)
        assert action1 == "MEGAMIND"

        action2 = evaluate_confidence_gate("MEGAMIND", confidence=5, prior_fails=1)
        assert action2 == "GRAND JURY"

    def test_megamind_loop_to_output_chain(self):
        """MEGAMIND loops 3 times then outputs."""
        for i in range(1, 3):
            action = evaluate_confidence_gate(
                "MEGAMIND", confidence=5, iterations=i, max_iterations=3
            )
            assert action == "LOOP", f"Iteration {i} should loop"

        action = evaluate_confidence_gate(
            "MEGAMIND", confidence=5, iterations=3, max_iterations=3
        )
        assert action == "OUTPUT"

    def test_deescalation_chain(self):
        """High confidence skips escalation entirely."""
        for mode in ["RAPID STRIKE", "DEEP THINK", "ENSEMBLE", "MEGAMIND"]:
            action = evaluate_confidence_gate(mode, confidence=9)
            assert action == "OUTPUT", f"{mode} with conf 9 should output"
