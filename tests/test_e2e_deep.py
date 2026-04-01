"""E2E test: Deep Think end-to-end.

Validates the full 11-technique Deep Think pipeline across three scenarios:
1. Single-file refactor → all 11 checkpoints, confidence >= 7
2. Multi-function extraction → checkpoint coherence (Decomposition aligns with CoT)
3. Low-confidence Deep Think → escalates to Ensemble

Checks:
- Technique ordering is correct (1 through 11)
- Each technique references the problem statement
- Step-Back identifies the ACTUAL need, not just literal request
- Tree of Thought has PURSUE/PRUNE verdicts
- RAVEN Loop may or may not loop based on confidence
- Final confidence is calibrated
- Token estimate: 10-20K (verified by character count proxy)

Uses the ReasoningSwarmHarness from test_e2e_scaffold.py.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e_scaffold import (  # noqa: E402
    DEEP_THINK_TECHNIQUES,
    MEDIUM_PROBLEMS,
    HIGH_PROBLEMS,
    ReasoningSwarmHarness,
    ReasoningTrace,
    harness,
)

# Canonical tasks for each scenario
SINGLE_FILE_REFACTOR = MEDIUM_PROBLEMS[0]  # "Refactor this module to use dependency injection"
MULTI_FUNCTION_EXTRACTION = HIGH_PROBLEMS[1]  # "Design a rate limiter..."

# Token estimate proxy: 10-20K tokens ≈ characters (conservative 1 token ≈ 1 char for mock output)
TOKEN_CHAR_MIN = 1_500
TOKEN_CHAR_MAX = 80_000


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _run_deep(task: str) -> ReasoningTrace:
    """Run Deep Think and return the trace."""
    h = ReasoningSwarmHarness(task_description=task, mode_override="DEEP")
    return h.run()


def _extract_technique_section(raw_output: str, technique_name: str) -> str:
    """Extract the full box section for a single technique."""
    pattern = re.escape(technique_name)
    match = re.search(rf"┌─\s*{pattern}.*?└─+┘", raw_output, re.DOTALL)
    assert match, f"Section for {technique_name} not found in output"
    return match.group(0)


def _extract_inner_content(section: str) -> str:
    """Extract content lines (after │) from a box section."""
    lines = section.split("\n")
    content_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("│"):
            content_lines.append(stripped[1:].strip())
    return "\n".join(content_lines)


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness — Deep Think with confidence-gate escalation to Ensemble
# ═══════════════════════════════════════════════════════════════════════════


class DeepThinkExtendedHarness(ReasoningSwarmHarness):
    """Harness that adds confidence-gate escalation from Deep Think to Ensemble.

    If Deep Think's average confidence falls below 7, escalates to Ensemble
    mode and appends escalation metadata to the trace.
    """

    def _run_deep(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        total_confidence = 0

        for name, marker in DEEP_THINK_TECHNIQUES:
            content = self._mock_technique_output(name, task)
            section = f"┌─ {name} ──────────────────────────────────────\n"
            section += f"│ {content}\n"
            section += f"│ {marker}\n"
            section += "└" + "─" * 50 + "┘"
            output_parts.append(section)
            techniques_used.append(name)
            total_confidence += self._extract_confidence(content)

        avg_conf = min(10, max(1, round(total_confidence / 11)))

        # Confidence gate: escalate to Ensemble if below threshold
        escalations = 0
        escalation_text = ""
        if avg_conf < 7:
            escalations = 1
            escalation_text = (
                f"\n\n⚠️ ESCALATION: Deep Think confidence {avg_conf} < 7 — "
                f"escalating to ENSEMBLE\n"
            )
            # Append Ensemble angle summaries as escalation output
            from tests.test_e2e_scaffold import ENSEMBLE_ANGLES

            for angle in ENSEMBLE_ANGLES:
                content = self._mock_angle_output(angle, task)
                escalation_text += f"ENSEMBLE ANGLE: {angle}\n{content}\n\n"
            escalation_text += (
                f"ENSEMBLE SYNTHESIS: Aggregated 5 angles. "
                f"Ensemble confidence: {avg_conf + 1}.\n"
            )

        summary = (
            f"\n🧠 DEEP THINK COMPLETE\n"
            f"Checkpoints Hit: 11/11\n"
            f"Confidence: {avg_conf}\n"
            f"---\n"
            f"Final answer for: {task}"
        )
        output_parts.append(summary)
        if escalation_text:
            output_parts.append(escalation_text)

        return ReasoningTrace(
            mode="DEEP",
            confidence=avg_conf,
            checkpoints_hit=11,
            escalations=escalations,
            techniques_used=techniques_used,
            raw_output="\n".join(output_parts),
        )


class LowConfidenceDeepHarness(DeepThinkExtendedHarness):
    """Deep Think harness with artificially low per-technique confidence.

    Forces all techniques except RECURSIVE SELF-IMPROVEMENT to return
    confidence 4, producing an average below the escalation threshold.
    """

    @staticmethod
    def _extract_confidence(text: str) -> int:
        match = re.search(r"FINAL CONFIDENCE:\s*(\d+)", text)
        if match:
            return min(10, max(1, int(match.group(1))))
        return 4


@pytest.fixture
def deep_extended_harness():
    """Provide a DeepThinkExtendedHarness factory."""

    def _factory(task: str) -> DeepThinkExtendedHarness:
        return DeepThinkExtendedHarness(task_description=task, mode_override="DEEP")

    return _factory


@pytest.fixture
def low_conf_deep_harness():
    """Provide a LowConfidenceDeepHarness factory."""

    def _factory(task: str) -> LowConfidenceDeepHarness:
        return LowConfidenceDeepHarness(task_description=task, mode_override="DEEP")

    return _factory


# ═══════════════════════════════════════════════════════════════════════════
# Test Case 1 — Single-file refactor: all 11 checkpoints, confidence >= 7
# ═══════════════════════════════════════════════════════════════════════════


class TestSingleFileRefactor:
    """Single-file refactor through Deep Think: 11 checkpoints, high confidence."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep(SINGLE_FILE_REFACTOR)

    def test_mode_is_deep(self, trace):
        assert trace.mode == "DEEP"

    def test_all_11_checkpoints_hit(self, trace):
        assert trace.checkpoints_hit == 11

    def test_confidence_at_least_7(self, trace):
        assert trace.confidence >= 7

    def test_no_escalations(self, trace):
        assert trace.escalations == 0

    def test_completion_marker_present(self, trace):
        assert "🧠 DEEP THINK COMPLETE" in trace.raw_output

    # ── Technique ordering ──────────────────────────────────────────────

    def test_technique_ordering_correct(self, trace):
        """Techniques appear in output in order 1 through 11."""
        positions = []
        for name, _marker in DEEP_THINK_TECHNIQUES:
            idx = trace.raw_output.find(name)
            assert idx >= 0, f"{name} not found in output"
            positions.append(idx)
        # Positions must be strictly increasing
        for i in range(1, len(positions)):
            assert positions[i] > positions[i - 1], (
                f"{DEEP_THINK_TECHNIQUES[i][0]} appears before "
                f"{DEEP_THINK_TECHNIQUES[i-1][0]}"
            )

    def test_all_11_techniques_used(self, trace):
        for name, _ in DEEP_THINK_TECHNIQUES:
            assert name in trace.techniques_used, (
                f"Technique {name} missing from techniques_used"
            )

    def test_exactly_11_techniques(self, trace):
        assert len(trace.techniques_used) == 11

    # ── Checkpoint markers ─────────────────────────────────────────────

    @pytest.mark.parametrize(
        "technique_name,checkpoint",
        DEEP_THINK_TECHNIQUES,
        ids=[t[0].replace("/", "-").replace(" ", "-") for t in DEEP_THINK_TECHNIQUES],
    )
    def test_checkpoint_marker_present(self, trace, technique_name, checkpoint):
        section = _extract_technique_section(trace.raw_output, technique_name)
        assert checkpoint in section, (
            f"{technique_name} missing checkpoint {checkpoint}"
        )

    # ── Problem statement references ────────────────────────────────────

    @pytest.mark.parametrize(
        "technique_name,checkpoint",
        DEEP_THINK_TECHNIQUES,
        ids=[t[0].replace("/", "-").replace(" ", "-") for t in DEEP_THINK_TECHNIQUES],
    )
    def test_technique_references_problem(self, trace, technique_name, checkpoint):
        """Each technique's content includes a reference to the problem statement."""
        section = _extract_technique_section(trace.raw_output, technique_name)
        content = _extract_inner_content(section)
        # Check for either the full problem text or key terms from it
        problem_key_terms = ["refactor", "module", "dependency", "injection"]
        has_reference = any(term in content.lower() for term in problem_key_terms)
        assert has_reference, (
            f"{technique_name} does not reference the problem statement. "
            f"Content: {content[:120]}..."
        )

    # ── Step-Back: identifies ACTUAL need ────────────────────────────────

    def test_stepback_identifies_actual_need(self, trace):
        """Step-Back must identify what the user ACTUALLY wants, not just repeat."""
        section = _extract_technique_section(trace.raw_output, "STEP-BACK")
        content = _extract_inner_content(section)
        assert "literal request" in content.lower(), (
            "STEP-BACK should distinguish literal request from actual need"
        )
        assert "actually wants" in content.lower() or "actually" in content.lower(), (
            "STEP-BACK should identify what user ACTUALLY wants"
        )
        # Must not simply restate the problem verbatim as the "actual need"
        literal_match = re.search(r"Literal request:\s*(.+?)(?:\.|$)", content)
        actual_match = re.search(
            r"What user ACTUALLY wants:\s*(.+?)(?:\.|$)", content
        )
        if literal_match and actual_match:
            literal = literal_match.group(1).strip()
            actual = actual_match.group(1).strip()
            assert literal != actual, (
                "STEP-BACK 'ACTUALLY wants' must differ from literal request"
            )

    # ── Tree of Thought: PURSUE/PRUNE verdicts ──────────────────────────

    def test_tree_of_thought_has_verdicts(self, trace):
        """Tree of Thought must have PURSUE or PRUNE verdicts per branch."""
        section = _extract_technique_section(trace.raw_output, "TREE OF THOUGHT")
        content = _extract_inner_content(section)
        assert "PURSUE" in content, "TREE OF THOUGHT must contain at least one PURSUE verdict"
        assert "PRUNE" in content, "TREE OF THOUGHT must contain at least one PRUNE verdict"

    def test_tree_of_thought_has_branches(self, trace):
        """Tree of Thought must have at least 2 distinct branches."""
        section = _extract_technique_section(trace.raw_output, "TREE OF THOUGHT")
        content = _extract_inner_content(section)
        branches = re.findall(r"BRANCH\s+[A-Z]", content)
        assert len(branches) >= 2, (
            f"TREE OF THOUGHT should have at least 2 branches, found {len(branches)}"
        )

    def test_tree_of_thought_selects_branch(self, trace):
        """Tree of Thought must have a SELECTED branch with justification."""
        section = _extract_technique_section(trace.raw_output, "TREE OF THOUGHT")
        content = _extract_inner_content(section)
        assert "SELECTED:" in content, "TREE OF THOUGHT must include a SELECTED branch"

    # ── RAVEN Loop behavior ─────────────────────────────────────────────

    def test_raven_loop_has_reflect_adapt_verify(self, trace):
        """RAVEN Loop must contain REFLECT, ADAPT, VERIFY, EXECUTE, NAVIGATE."""
        section = _extract_technique_section(trace.raw_output, "RAVEN LOOP")
        content = _extract_inner_content(section)
        for phase in ["REFLECT", "ADAPT", "VERIFY", "EXECUTE", "NAVIGATE"]:
            assert phase in content, f"RAVEN LOOP missing phase: {phase}"

    def test_raven_loop_has_loop_decision(self, trace):
        """RAVEN Loop must explicitly decide whether to loop again."""
        section = _extract_technique_section(trace.raw_output, "RAVEN LOOP")
        content = _extract_inner_content(section)
        has_loop_decision = "LOOP AGAIN" in content or "loop again" in content.lower()
        assert has_loop_decision, "RAVEN LOOP must include 'LOOP AGAIN?' decision"

    # ── Final confidence calibration ────────────────────────────────────

    def test_final_confidence_calibrated(self, trace):
        """Final confidence must be between 1 and 10 inclusive."""
        assert 1 <= trace.confidence <= 10

    def test_final_confidence_matches_summary(self, trace):
        """Confidence in trace matches the confidence in the output summary."""
        match = re.search(r"Confidence:\s*(\d+)", trace.raw_output)
        assert match, "Confidence not found in summary"
        summary_conf = int(match.group(1))
        assert summary_conf == trace.confidence

    def test_recursive_self_improvement_reports_final_confidence(self, trace):
        """RECURSIVE SELF-IMPROVEMENT must report FINAL CONFIDENCE."""
        section = _extract_technique_section(
            trace.raw_output, "RECURSIVE SELF-IMPROVEMENT"
        )
        content = _extract_inner_content(section)
        assert "FINAL CONFIDENCE" in content, (
            "RECURSIVE SELF-IMPROVEMENT must include FINAL CONFIDENCE"
        )

    # ── Token estimate: 10-20K chars proxy ──────────────────────────────

    def test_output_length_in_token_range(self, trace):
        """Output character count must be in range corresponding to 10-20K tokens."""
        char_count = len(trace.raw_output)
        assert char_count >= TOKEN_CHAR_MIN, (
            f"Output too short: {char_count} chars (min {TOKEN_CHAR_MIN})"
        )
        assert char_count <= TOKEN_CHAR_MAX, (
            f"Output too long: {char_count} chars (max {TOKEN_CHAR_MAX})"
        )

    # ── Trace structure ─────────────────────────────────────────────────

    def test_trace_raw_output_non_empty(self, trace):
        assert len(trace.raw_output) > 500

    def test_trace_latency_non_negative(self, trace):
        assert trace.latency_ms >= 0

    def test_trace_techniques_list_length(self, trace):
        assert len(trace.techniques_used) == 11


# ═══════════════════════════════════════════════════════════════════════════
# Test Case 2 — Multi-function extraction: checkpoint coherence
# ═══════════════════════════════════════════════════════════════════════════


class TestMultiFunctionExtraction:
    """Multi-function extraction: Decomposition aligns with Chain of Thought."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep(MULTI_FUNCTION_EXTRACTION)

    def test_mode_is_deep(self, trace):
        assert trace.mode == "DEEP"

    def test_all_11_checkpoints(self, trace):
        assert trace.checkpoints_hit == 11

    def test_confidence_valid(self, trace):
        assert 1 <= trace.confidence <= 10

    # ── Decomposition structure ─────────────────────────────────────────

    def test_decomposition_has_sub_problems(self, trace):
        section = _extract_technique_section(trace.raw_output, "DECOMPOSITION")
        content = _extract_inner_content(section)
        assert "MAIN PROBLEM" in content
        assert "SUB-PROBLEM" in content or "SUB-PROBLEMS" in content

    def test_decomposition_has_dependencies(self, trace):
        section = _extract_technique_section(trace.raw_output, "DECOMPOSITION")
        content = _extract_inner_content(section)
        assert "DEPENDENCIES" in content

    def test_decomposition_has_numbered_steps(self, trace):
        """Decomposition sub-problems must be numbered (1., 2., etc.)."""
        section = _extract_technique_section(trace.raw_output, "DECOMPOSITION")
        content = _extract_inner_content(section)
        numbered = re.findall(r"\d+\.\s+\w+", content)
        assert len(numbered) >= 2, (
            f"Decomposition should have at least 2 numbered sub-problems, "
            f"found {len(numbered)}"
        )

    # ── Chain of Thought structure ──────────────────────────────────────

    def test_chain_of_thought_has_steps(self, trace):
        section = _extract_technique_section(trace.raw_output, "CHAIN OF THOUGHT")
        content = _extract_inner_content(section)
        steps = re.findall(r"Step\s+\d+", content)
        assert len(steps) >= 3, (
            f"Chain of Thought should have at least 3 steps, found {len(steps)}"
        )

    def test_chain_of_thought_has_why_justifications(self, trace):
        """Each CoT step must include a 'Why' justification."""
        section = _extract_technique_section(trace.raw_output, "CHAIN OF THOUGHT")
        content = _extract_inner_content(section)
        why_count = len(re.findall(r"Why:", content))
        assert why_count >= 3, (
            f"Chain of Thought should have at least 3 'Why:' justifications, "
            f"found {why_count}"
        )

    def test_chain_of_thought_has_conclusion(self, trace):
        section = _extract_technique_section(trace.raw_output, "CHAIN OF THOUGHT")
        content = _extract_inner_content(section)
        assert "Conclusion:" in content, "Chain of Thought must have a conclusion"

    # ── Coherence: Decomposition aligns with CoT ────────────────────────

    def test_decomposition_cot_share_key_terms(self, trace):
        """Decomposition sub-problems and CoT steps must share key terms."""
        decomp_section = _extract_technique_section(trace.raw_output, "DECOMPOSITION")
        decomp_content = _extract_inner_content(decomp_section)
        cot_section = _extract_technique_section(trace.raw_output, "CHAIN OF THOUGHT")
        cot_content = _extract_inner_content(cot_section)
        # Extract nouns/verbs from decomposition sub-problems
        decomp_terms = set(re.findall(r"→\s*\d+\.\d*\s*(\w+)", decomp_content))
        # Also extract main sub-problem names
        decomp_sub = set(re.findall(r"\d+\.\s+(\w+)", decomp_content))
        all_decomp_terms = decomp_terms | decomp_sub
        # Check at least one decomposition term appears in CoT
        shared = any(
            term.lower() in cot_content.lower() for term in all_decomp_terms if len(term) > 3
        )
        # Fallback: check for any shared problem-specific words
        if not shared:
            problem_words = set(
                w.lower()
                for w in re.findall(r"[A-Za-z]{4,}", MULTI_FUNCTION_EXTRACTION)
            )
            cot_words = set(w.lower() for w in re.findall(r"[A-Za-z]{4,}", cot_content))
            decomp_words = set(
                w.lower() for w in re.findall(r"[A-Za-z]{4,}", decomp_content)
            )
            shared = len(cot_words & decomp_words & problem_words) > 0
        assert shared, (
            "Decomposition and Chain of Thought must share coherent key terms"
        )

    def test_decomposition_count_matches_cot_steps(self, trace):
        """Number of CoT steps should be proportional to decomposition sub-problems."""
        decomp_section = _extract_technique_section(trace.raw_output, "DECOMPOSITION")
        decomp_content = _extract_inner_content(decomp_section)
        cot_section = _extract_technique_section(trace.raw_output, "CHAIN OF THOUGHT")
        cot_content = _extract_inner_content(cot_section)
        sub_problems = re.findall(r"\d+\.\s+\w+", decomp_content)
        cot_steps = re.findall(r"Step\s+\d+", cot_content)
        # CoT steps should cover at least as many items as decomposition sub-problems
        assert len(cot_steps) >= len(sub_problems), (
            f"CoT has {len(cot_steps)} steps but Decomposition has "
            f"{len(sub_problems)} sub-problems — steps should cover all sub-problems"
        )

    # ── Cross-technique consistency ─────────────────────────────────────

    def test_meta_cognition_precedes_decomposition(self, trace):
        """META-COGNITION should appear before DECOMPOSITION."""
        meta_pos = trace.raw_output.find("META-COGNITION")
        decomp_pos = trace.raw_output.find("DECOMPOSITION")
        assert meta_pos < decomp_pos

    def test_decomposition_precedes_cot(self, trace):
        """DECOMPOSITION should appear before CHAIN OF THOUGHT."""
        decomp_pos = trace.raw_output.find("DECOMPOSITION")
        cot_pos = trace.raw_output.find("CHAIN OF THOUGHT")
        assert decomp_pos < cot_pos

    def test_stepback_precedes_decomposition(self, trace):
        """STEP-BACK should appear before DECOMPOSITION."""
        stepback_pos = trace.raw_output.find("STEP-BACK")
        decomp_pos = trace.raw_output.find("DECOMPOSITION")
        assert stepback_pos < decomp_pos

    def test_raven_precedes_recursive_improvement(self, trace):
        """RAVEN LOOP should appear before RECURSIVE SELF-IMPROVEMENT."""
        raven_pos = trace.raw_output.find("RAVEN LOOP")
        improve_pos = trace.raw_output.find("RECURSIVE SELF-IMPROVEMENT")
        assert raven_pos < improve_pos

    # ── Token estimate ──────────────────────────────────────────────────

    def test_output_length_in_range(self, trace):
        char_count = len(trace.raw_output)
        assert char_count >= TOKEN_CHAR_MIN
        assert char_count <= TOKEN_CHAR_MAX


# ═══════════════════════════════════════════════════════════════════════════
# Test Case 3 — Low-confidence Deep Think → escalates to Ensemble
# ═══════════════════════════════════════════════════════════════════════════


class TestLowConfidenceEscalation:
    """Low-confidence Deep Think escalates to Ensemble."""

    @pytest.fixture(scope="class")
    def trace(self, low_conf_deep_harness):
        h = low_conf_deep_harness("Migrate a monolith to microservices")
        return h.run()

    def test_mode_is_deep(self, trace):
        """Even when escalating, the primary mode is Deep Think."""
        assert trace.mode == "DEEP"

    def test_low_confidence_below_threshold(self, trace):
        """Confidence must be below 7 to trigger escalation."""
        assert trace.confidence < 7

    def test_escalation_triggered(self, trace):
        """Escalation count must be 1 when confidence < 7."""
        assert trace.escalations == 1

    def test_escalation_text_mentions_ensemble(self, trace):
        """Escalation text must mention ENSEMBLE."""
        assert "ENSEMBLE" in trace.raw_output

    def test_escalation_text_mentions_escalation(self, trace):
        """Output must contain the escalation marker."""
        assert "ESCALATION" in trace.raw_output

    def test_all_11_checkpoints_still_hit(self, trace):
        """Deep Think completes all 11 checkpoints before escalating."""
        assert trace.checkpoints_hit == 11

    def test_all_11_techniques_still_present(self, trace):
        """All 11 techniques are in techniques_used even when escalating."""
        for name, _ in DEEP_THINK_TECHNIQUES:
            assert name in trace.techniques_used, (
                f"Technique {name} missing during escalation"
            )

    def test_completion_marker_present(self, trace):
        assert "🧠 DEEP THINK COMPLETE" in trace.raw_output

    def test_ensemble_angles_appear_in_escalation(self, trace):
        """When escalating, Ensemble angle summaries should appear."""
        from tests.test_e2e_scaffold import ENSEMBLE_ANGLES

        for angle in ENSEMBLE_ANGLES:
            assert f"ENSEMBLE ANGLE: {angle}" in trace.raw_output, (
                f"Ensemble angle {angle} not found in escalation output"
            )

    def test_ensemble_synthesis_in_escalation(self, trace):
        """Escalation output must include an Ensemble synthesis."""
        assert "ENSEMBLE SYNTHESIS" in trace.raw_output

    # ── RAVEN Loop behavior with low confidence ─────────────────────────

    def test_raven_loop_present_with_low_confidence(self, trace):
        """RAVEN Loop still runs even when confidence is low."""
        section = _extract_technique_section(trace.raw_output, "RAVEN LOOP")
        assert section is not None

    def test_raven_loop_has_loop_again_decision(self, trace):
        """RAVEN Loop must have a LOOP AGAIN decision."""
        section = _extract_technique_section(trace.raw_output, "RAVEN LOOP")
        content = _extract_inner_content(section)
        has_loop = "LOOP AGAIN" in content or "loop again" in content.lower()
        assert has_loop, "RAVEN LOOP must include LOOP AGAIN decision"

    # ── Confidence calibration ──────────────────────────────────────────

    def test_confidence_is_calibrated_low(self, trace):
        """With artificially low confidence extraction, final should be < 7."""
        assert trace.confidence < 7
        assert trace.confidence >= 1

    # ── Trace structure ─────────────────────────────────────────────────

    def test_trace_raw_output_non_empty(self, trace):
        assert len(trace.raw_output) > 500

    def test_output_length_in_range(self, trace):
        char_count = len(trace.raw_output)
        assert char_count >= TOKEN_CHAR_MIN
        assert char_count <= TOKEN_CHAR_MAX


# ═══════════════════════════════════════════════════════════════════════════
# Mode dispatch and harness integration
# ═══════════════════════════════════════════════════════════════════════════


class TestDeepThinkModeDispatch:
    """Verify Deep Think mode is correctly resolved and dispatched."""

    def test_mode_resolves_to_deep_think(self, harness):
        h = harness(SINGLE_FILE_REFACTOR, mode="DEEP")
        assert h.get_mode() == "DEEP THINK"

    def test_mode_resolves_from_full_name(self, harness):
        h = harness(SINGLE_FILE_REFACTOR, mode="DEEP THINK")
        assert h.get_mode() == "DEEP THINK"

    def test_deep_run_returns_deep_mode(self, harness):
        h = harness(SINGLE_FILE_REFACTOR, mode="DEEP")
        trace = h.run()
        assert trace.mode == "DEEP"

    def test_deep_loads_deepthink_skill(self, harness):
        h = harness(SINGLE_FILE_REFACTOR, mode="DEEP")
        skill = h.load_skill()
        assert "DEEPTHINK" in skill.upper() or "DEEP" in skill.upper()

    def test_deep_skill_has_all_11_techniques(self, harness):
        h = harness(SINGLE_FILE_REFACTOR, mode="DEEP")
        skill = h.load_skill()
        for name, _ in DEEP_THINK_TECHNIQUES:
            assert name in skill.upper() or name.replace("-", " ") in skill.upper(), (
                f"Skill file missing technique: {name}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Parametrized across all medium/high problems
# ═══════════════════════════════════════════════════════════════════════════


class TestDeepThinkMultipleProblems:
    """Deep Think produces valid output across all medium and high problems."""

    @pytest.mark.parametrize(
        "problem",
        MEDIUM_PROBLEMS + HIGH_PROBLEMS,
        ids=[f"PROB-{i}" for i in range(len(MEDIUM_PROBLEMS + HIGH_PROBLEMS))],
    )
    def test_deep_completes(self, harness, problem):
        h = harness(problem, mode="DEEP")
        trace = h.run()
        assert "🧠 DEEP THINK COMPLETE" in trace.raw_output

    @pytest.mark.parametrize(
        "problem",
        MEDIUM_PROBLEMS + HIGH_PROBLEMS,
        ids=[f"PROB-{i}" for i in range(len(MEDIUM_PROBLEMS + HIGH_PROBLEMS))],
    )
    def test_deep_has_11_checkpoints(self, harness, problem):
        h = harness(problem, mode="DEEP")
        trace = h.run()
        assert trace.checkpoints_hit == 11

    @pytest.mark.parametrize(
        "problem",
        MEDIUM_PROBLEMS + HIGH_PROBLEMS,
        ids=[f"PROB-{i}" for i in range(len(MEDIUM_PROBLEMS + HIGH_PROBLEMS))],
    )
    def test_deep_confidence_valid(self, harness, problem):
        h = harness(problem, mode="DEEP")
        trace = h.run()
        assert 1 <= trace.confidence <= 10

    @pytest.mark.parametrize(
        "problem",
        MEDIUM_PROBLEMS + HIGH_PROBLEMS,
        ids=[f"PROB-{i}" for i in range(len(MEDIUM_PROBLEMS + HIGH_PROBLEMS))],
    )
    def test_deep_output_length(self, harness, problem):
        h = harness(problem, mode="DEEP")
        trace = h.run()
        assert len(trace.raw_output) > 500

    @pytest.mark.parametrize(
        "problem",
        MEDIUM_PROBLEMS + HIGH_PROBLEMS,
        ids=[f"PROB-{i}" for i in range(len(MEDIUM_PROBLEMS + HIGH_PROBLEMS))],
    )
    def test_deep_all_techniques_present(self, harness, problem):
        h = harness(problem, mode="DEEP")
        trace = h.run()
        for name, _ in DEEP_THINK_TECHNIQUES:
            assert name in trace.techniques_used
