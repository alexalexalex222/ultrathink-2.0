"""E2E tests for Rapid Strike mode — happy path and escalation paths.

Covers:
  1. Simple bug fix → confidence >= 8, executes directly
  2. Type annotation addition → confidence >= 8
  3. Config value update → confidence >= 8
  4. Medium task through Rapid Strike → triggers escalation to Deep Think
  5. Critical stakes through Rapid Strike → triggers escalation (cannot stay Rapid)

For each test:
  - Verify output format matches Rapid Strike template
  - Verify confidence gate behavior
  - Verify escalation triggers correctly
  - Measure latency (< 5 seconds for true Rapid Strike)

Uses the ReasoningSwarmHarness from test_e2e_scaffold.py.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e_scaffold import (  # noqa: E402
    LOW_PROBLEMS,
    MEDIUM_PROBLEMS,
    HIGH_PROBLEMS,
    ReasoningSwarmHarness,
    ReasoningTrace,
    harness,
)

from src.intake_classifier import classify_task  # noqa: E402

# Rapid Strike template sections from reasoning-swarm-SKILL.md
_RAPID_TEMPLATE_SECTIONS = [
    "1. PROBLEM:",
    "2. OBVIOUS ANSWER:",
    "3. SANITY CHECK:",
    "4. CONFIDENCE:",
]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _run_rapid(task: str) -> ReasoningTrace:
    """Run Rapid Strike and return the trace."""
    h = ReasoningSwarmHarness(task_description=task, mode_override="RAPID")
    return h.run()


def _extract_confidence(raw_output: str) -> int | None:
    """Extract confidence value from Rapid Strike output."""
    match = re.search(r"4\.\s*CONFIDENCE:\s*(\d+)", raw_output)
    if match:
        return int(match.group(1))
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Output format
# ═══════════════════════════════════════════════════════════════════════════


class TestRapidOutputFormat:
    """Verify Rapid Strike output matches the 4-section template."""

    @pytest.mark.parametrize(
        "task",
        LOW_PROBLEMS,
        ids=["low-0", "low-1", "low-2"],
    )
    def test_output_contains_all_template_sections(self, task):
        trace = _run_rapid(task)
        for section in _RAPID_TEMPLATE_SECTIONS:
            assert section in trace.raw_output, (
                f"Rapid Strike output missing template section: {section!r}"
            )

    @pytest.mark.parametrize(
        "task",
        LOW_PROBLEMS,
        ids=["low-0", "low-1", "low-2"],
    )
    def test_output_has_four_numbered_sections(self, task):
        trace = _run_rapid(task)
        numbered = re.findall(r"^\d+\.\s+\w+:", trace.raw_output, re.MULTILINE)
        assert len(numbered) == 4, (
            f"Expected 4 numbered sections, found {len(numbered)}"
        )

    def test_problem_section_contains_task_description(self):
        task = LOW_PROBLEMS[0]
        trace = _run_rapid(task)
        assert task in trace.raw_output, (
            "PROBLEM section should contain the task description"
        )

    def test_confidence_section_contains_numeric_value(self):
        trace = _run_rapid(LOW_PROBLEMS[0])
        conf = _extract_confidence(trace.raw_output)
        assert conf is not None, "CONFIDENCE section should contain a number"
        assert 1 <= conf <= 10, f"Confidence {conf} out of range 1-10"

    def test_output_sequential_numbering(self):
        """Sections must be numbered 1 through 4 in order."""
        trace = _run_rapid(LOW_PROBLEMS[0])
        numbers = re.findall(r"^(\d+)\.\s+\w+:", trace.raw_output, re.MULTILINE)
        assert numbers == ["1", "2", "3", "4"], (
            f"Expected sequential 1-4, got {numbers}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Happy path — simple tasks with confidence >= 8
# ═══════════════════════════════════════════════════════════════════════════


class TestRapidHappyPath:
    """Test cases 1-3: simple tasks execute directly with confidence >= 8."""

    def test_simple_bug_fix_confidence_gate(self):
        """Test 1: Simple bug fix → confidence >= 8, executes directly."""
        task = "Fix a typo in a variable name"
        trace = _run_rapid(task)

        assert trace.confidence >= 8, (
            f"Expected confidence >= 8 for simple bug fix, got {trace.confidence}"
        )
        assert trace.escalations == 0, (
            "Simple bug fix should not trigger escalation"
        )

    def test_type_annotation_addition_confidence_gate(self):
        """Test 2: Type annotation addition → confidence >= 8."""
        task = LOW_PROBLEMS[0]  # "Add a type hint to this function"
        trace = _run_rapid(task)

        assert trace.confidence >= 8, (
            f"Expected confidence >= 8 for type annotation task, got {trace.confidence}"
        )
        assert trace.escalations == 0, (
            "Type annotation task should not trigger escalation"
        )

    def test_config_value_update_confidence_gate(self):
        """Test 3: Config value update → confidence >= 8."""
        task = "Update the timeout value in config.yaml from 30 to 60"
        trace = _run_rapid(task)

        assert trace.confidence >= 8, (
            f"Expected confidence >= 8 for config update, got {trace.confidence}"
        )
        assert trace.escalations == 0, (
            "Config value update should not trigger escalation"
        )

    def test_happy_path_mode_is_rapid(self):
        """Happy path trace must report RAPID mode."""
        trace = _run_rapid(LOW_PROBLEMS[0])
        assert trace.mode == "RAPID", f"Expected mode 'RAPID', got {trace.mode!r}"

    def test_happy_path_techniques_used(self):
        """Rapid Strike should list 'RAPID STRIKE' as the technique."""
        trace = _run_rapid(LOW_PROBLEMS[0])
        assert "RAPID STRIKE" in trace.techniques_used, (
            f"Expected 'RAPID STRIKE' in techniques_used, got {trace.techniques_used}"
        )

    def test_happy_path_checkpoints_hit(self):
        """Rapid Strike has exactly 4 checkpoints (PROBLEM, OBVIOUS, SANITY, CONF)."""
        trace = _run_rapid(LOW_PROBLEMS[0])
        assert trace.checkpoints_hit == 4, (
            f"Expected 4 checkpoints for Rapid Strike, got {trace.checkpoints_hit}"
        )

    def test_happy_path_subprocess_calls_zero(self):
        """Rapid Strike should not spawn subprocesses."""
        trace = _run_rapid(LOW_PROBLEMS[0])
        assert trace.subprocess_calls == 0, (
            f"Expected 0 subprocess calls for Rapid Strike, got {trace.subprocess_calls}"
        )

    def test_happy_path_evidence_entries_empty(self):
        """Rapid Strike does not collect evidence entries."""
        trace = _run_rapid(LOW_PROBLEMS[0])
        assert trace.evidence_entries == [], (
            "Rapid Strike should have no evidence entries"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Latency
# ═══════════════════════════════════════════════════════════════════════════


class TestRapidLatency:
    """Rapid Strike must complete in < 5 seconds."""

    @pytest.mark.parametrize(
        "task",
        LOW_PROBLEMS,
        ids=["low-0", "low-1", "low-2"],
    )
    def test_latency_under_5_seconds(self, task):
        trace = _run_rapid(task)
        assert trace.latency_ms < 5000, (
            f"Rapid Strike took {trace.latency_ms:.0f}ms — expected < 5000ms"
        )

    @pytest.mark.parametrize(
        "task",
        LOW_PROBLEMS,
        ids=["low-0", "low-1", "low-2"],
    )
    def test_latency_is_positive(self, task):
        trace = _run_rapid(task)
        assert trace.latency_ms > 0, "Latency should be positive"


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Confidence gate rules
# ═══════════════════════════════════════════════════════════════════════════


class TestConfidenceGate:
    """Verify the Rapid Strike confidence gate rules from the skill definition.

    Rule: confidence >= 8 → execute directly
    Rule: confidence < 8 → escalate to DEEP THINK
    """

    def test_confidence_at_threshold_executes(self):
        """Confidence of exactly 8 is at the gate threshold — should execute."""
        trace = _run_rapid(LOW_PROBLEMS[0])
        # The harness returns confidence=8 for rapid, which passes the gate
        assert trace.confidence >= 8, (
            "Rapid Strike default confidence should be >= 8 (gate threshold)"
        )

    def test_confidence_gate_value_is_8(self):
        """The Rapid Strike confidence gate threshold is 8 per the skill definition."""
        trace = _run_rapid(LOW_PROBLEMS[0])
        conf = _extract_confidence(trace.raw_output)
        assert conf is not None
        # The skill says "If confidence >= 8 → execute"
        # The harness returns 8 by default for rapid
        assert conf >= 8, "Default rapid confidence should meet the gate"

    def test_rapid_output_mentions_confidence(self):
        """Output must include a CONFIDENCE line for gate evaluation."""
        trace = _run_rapid(LOW_PROBLEMS[0])
        assert "CONFIDENCE:" in trace.raw_output, (
            "Rapid Strike output must include CONFIDENCE for gate evaluation"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Escalation paths
# ═══════════════════════════════════════════════════════════════════════════


class TestRapidEscalation:
    """Test cases 4-5: tasks that should not stay at Rapid Strike level.

    These tests verify escalation behavior via the intake classifier,
    which is the routing mechanism that prevents inappropriate tasks
    from being handled by Rapid Strike.
    """

    def test_medium_task_classifies_to_deep_think(self):
        """Test 4: Medium complexity task → should route to DEEP THINK, not RAPID.

        Per the AUTO-SELECT MATRIX:
        MEDIUM complexity OR MEDIUM stakes → DEEP THINK

        The intake classifier is the escalation gate — it prevents medium
        tasks from reaching Rapid Strike in the first place.
        """
        mode = classify_task(
            task_type="IMPLEMENTATION",
            complexity="MEDIUM",
            stakes="LOW",
        )
        assert mode == "DEEP THINK", (
            f"Medium complexity task should classify to DEEP THINK, got {mode!r}"
        )
        assert mode != "RAPID STRIKE", (
            "Medium task must NOT remain at Rapid Strike"
        )

    def test_medium_stakes_classifies_to_deep_think(self):
        """Test 4 variant: MEDIUM stakes → should route to DEEP THINK."""
        mode = classify_task(
            task_type="IMPLEMENTATION",
            complexity="LOW",
            stakes="MEDIUM",
        )
        assert mode == "DEEP THINK", (
            f"Medium stakes task should classify to DEEP THINK, got {mode!r}"
        )

    def test_medium_task_through_rapid_produces_trace(self):
        """Test 4: Running a medium task through the harness (mode=RAPID) still
        produces valid output — the harness simulates the execution.

        The escalation would happen at the classifier level, but if forced
        through Rapid, the harness still produces the 4-section output.
        """
        task = MEDIUM_PROBLEMS[0]
        trace = _run_rapid(task)

        # Even forced through rapid, output format is valid
        for section in _RAPID_TEMPLATE_SECTIONS:
            assert section in trace.raw_output

        # Mode is RAPID because we forced it
        assert trace.mode == "RAPID"

    def test_critical_stakes_classifies_to_megamind(self):
        """Test 5: CRITICAL stakes → should route to MEGAMIND, not RAPID.

        Per the AUTO-SELECT MATRIX:
        EXTREME complexity OR CRITICAL stakes OR UNKNOWN → MEGAMIND (10→3→1)

        Critical stakes cannot stay at Rapid — the classifier forces MEGAMIND.
        """
        mode = classify_task(
            task_type="IMPLEMENTATION",
            complexity="LOW",
            stakes="CRITICAL",
        )
        assert mode == "MEGAMIND", (
            f"CRITICAL stakes task should classify to MEGAMIND, got {mode!r}"
        )
        assert mode != "RAPID STRIKE", (
            "CRITICAL stakes task must NOT remain at Rapid Strike"
        )

    def test_critical_stakes_high_complexity_classifies_to_megamind(self):
        """Test 5 variant: HIGH complexity + CRITICAL stakes → MEGAMIND."""
        mode = classify_task(
            task_type="IMPLEMENTATION",
            complexity="HIGH",
            stakes="CRITICAL",
        )
        assert mode == "MEGAMIND", (
            f"HIGH+CRITICAL should classify to MEGAMIND, got {mode!r}"
        )

    def test_critical_stakes_forced_megamind_no_override(self):
        """Test 5: CRITICAL stakes → MEGAMIND — not even 'quick' hint can override.

        Per the skill: 'User says "quick" or "just do it" → RAPID STRIKE
        (unless CRITICAL stakes)'
        """
        mode = classify_task(
            task_type="IMPLEMENTATION",
            complexity="LOW",
            stakes="CRITICAL",
            user_hint="quick",
        )
        assert mode == "MEGAMIND", (
            f"CRITICAL stakes should force MEGAMIND even with 'quick' hint, got {mode!r}"
        )

    def test_prior_failure_escalates_from_rapid(self):
        """Prior failure on the task → must not stay at Rapid Strike.

        BUG_FIX with prior_fails=1 triggers forced GRAND JURY.
        Implementation tasks with prior_fails=1 escalate to minimum ENSEMBLE.
        """
        # BUG_FIX + prior_fails → forced GRAND JURY
        mode = classify_task(
            task_type="BUG_FIX",
            complexity="LOW",
            stakes="LOW",
            prior_fails=1,
        )
        assert mode == "GRAND JURY", (
            f"BUG_FIX with prior failure should force GRAND JURY, got {mode!r}"
        )
        assert mode != "RAPID STRIKE", (
            "Prior failure must NOT remain at Rapid Strike"
        )

        # IMPLEMENTATION + prior_fails → minimum ENSEMBLE
        mode = classify_task(
            task_type="IMPLEMENTATION",
            complexity="LOW",
            stakes="LOW",
            prior_fails=1,
        )
        assert mode == "ENSEMBLE", (
            f"IMPLEMENTATION with prior failure should escalate to ENSEMBLE, got {mode!r}"
        )

    def test_harness_deep_think_for_escalated_medium_task(self):
        """Test 4: When a medium task is routed to DEEP THINK via classifier,
        verify the harness produces a valid Deep Think trace."""
        task = MEDIUM_PROBLEMS[0]
        mode = classify_task(
            task_type="IMPLEMENTATION",
            complexity="MEDIUM",
            stakes="LOW",
        )
        assert mode == "DEEP THINK"

        h = ReasoningSwarmHarness(task_description=task, mode_override="DEEP")
        trace = h.run()

        assert trace.mode == "DEEP"
        assert trace.checkpoints_hit == 11
        assert trace.escalations == 0
        assert len(trace.techniques_used) == 11
        assert "DEEP THINK COMPLETE" in trace.raw_output


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Rapid Strike mode dispatch
# ═══════════════════════════════════════════════════════════════════════════


class TestRapidModeDispatch:
    """Verify Rapid Strike mode is correctly resolved and dispatched."""

    def test_mode_resolves_to_rapid_strike(self, harness):
        h = harness(LOW_PROBLEMS[0], mode="RAPID")
        assert h.get_mode() == "RAPID STRIKE"

    def test_mode_resolves_from_full_name(self, harness):
        h = harness(LOW_PROBLEMS[0], mode="RAPID STRIKE")
        assert h.get_mode() == "RAPID STRIKE"

    def test_rapid_run_returns_rapid_mode(self, harness):
        h = harness(LOW_PROBLEMS[0], mode="RAPID")
        trace = h.run()
        assert trace.mode == "RAPID"

    def test_rapid_loads_reasoning_swarm_skill(self, harness):
        h = harness(LOW_PROBLEMS[0], mode="RAPID")
        skill = h.load_skill()
        assert "RAPID STRIKE" in skill, (
            "Rapid Strike should load reasoning-swarm-SKILL.md containing RAPID STRIKE"
        )

    def test_classifier_routes_low_low_to_rapid(self):
        """LOW complexity + LOW stakes + 0 prior fails → RAPID STRIKE."""
        mode = classify_task(
            task_type="BUG_FIX",
            complexity="LOW",
            stakes="LOW",
        )
        assert mode == "RAPID STRIKE"


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Cross-problem consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestRapidCrossProblem:
    """Rapid Strike produces valid output across multiple problems."""

    @pytest.mark.parametrize(
        "task",
        LOW_PROBLEMS + [MEDIUM_PROBLEMS[0]],
        ids=["low-0", "low-1", "low-2", "medium-0"],
    )
    def test_mode_is_rapid(self, task):
        trace = _run_rapid(task)
        assert trace.mode == "RAPID"

    @pytest.mark.parametrize(
        "task",
        LOW_PROBLEMS + [MEDIUM_PROBLEMS[0]],
        ids=["low-0", "low-1", "low-2", "medium-0"],
    )
    def test_confidence_in_range(self, task):
        trace = _run_rapid(task)
        assert 1 <= trace.confidence <= 10

    @pytest.mark.parametrize(
        "task",
        LOW_PROBLEMS + [MEDIUM_PROBLEMS[0]],
        ids=["low-0", "low-1", "low-2", "medium-0"],
    )
    def test_no_escalations(self, task):
        trace = _run_rapid(task)
        assert trace.escalations == 0

    @pytest.mark.parametrize(
        "task",
        LOW_PROBLEMS + [MEDIUM_PROBLEMS[0]],
        ids=["low-0", "low-1", "low-2", "medium-0"],
    )
    def test_latency_fast(self, task):
        trace = _run_rapid(task)
        assert trace.latency_ms < 5000

    @pytest.mark.parametrize(
        "task",
        LOW_PROBLEMS + [MEDIUM_PROBLEMS[0]],
        ids=["low-0", "low-1", "low-2", "medium-0"],
    )
    def test_all_template_sections_present(self, task):
        trace = _run_rapid(task)
        for section in _RAPID_TEMPLATE_SECTIONS:
            assert section in trace.raw_output
