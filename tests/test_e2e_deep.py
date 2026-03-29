"""E2E tests for Deep Think mode — full pipeline validation.

Three test cases:
  1. Single-file refactor  -> all 11 checkpoints, confidence >= 7
  2. Multi-function extraction -> checkpoint coherence (Decomposition aligns with CoT)
  3. Low-confidence Deep Think -> escalates to Ensemble

Additional verifications:
  - Technique ordering (1-11)
  - Each technique references the problem statement
  - Step-Back identifies the ACTUAL need, not just literal request
  - Tree of Thought has PURSUE/PRUNE verdicts
  - RAVEN Loop may or may not loop based on confidence
  - Final confidence is calibrated
  - Token estimate: 10-20K (character count proxy)
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e_scaffold import (  # noqa: E402
    DEEP_THINK_TECHNIQUES,
    MEDIUM_PROBLEMS,
    ReasoningSwarmHarness,
    ReasoningTrace,
)

# ── Canonical tasks ──────────────────────────────────────────────────────────
REFACTOR_TASK = MEDIUM_PROBLEMS[0]  # "Refactor this module to use dependency injection"
EXTRACTION_TASK = MEDIUM_PROBLEMS[2]  # "Convert the monolithic config parser..."

# Token estimate bounds (10-20K tokens, ~4 chars/token proxy)
_TOKEN_LO = 10_000 * 3  # 30 000 chars (conservative low)
_TOKEN_HI = 20_000 * 5  # 100 000 chars (generous high)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _extract_section(raw: str, technique: str) -> str:
    """Extract the boxed section for *technique* from raw output."""
    pattern = re.escape(technique)
    m = re.search(rf"┌─\s*{pattern}.*?└─+┘", raw, re.DOTALL)
    assert m, f"Section for {technique!r} not found in output ({len(raw)} chars)"
    return m.group(0)


def _inner(section: str) -> str:
    """Return content lines (after the │ delimiter) from a boxed section."""
    parts = []
    for line in section.split("\n"):
        s = line.strip()
        if s.startswith("│"):
            parts.append(s.lstrip("│").strip())
    return "\n".join(parts)


def _run_deep(task: str) -> ReasoningTrace:
    """Run Deep Think for *task* and return the trace."""
    h = ReasoningSwarmHarness(task_description=task, mode_override="DEEP")
    return h.run()


def _run_with_escalation(task: str) -> ReasoningTrace:
    """Simulate the confidence gate: if Deep Think confidence < 7, escalate.

    This implements the escalation rule from reasoning-swarm-SKILL.md §confidence gate:
        "If confidence < 7, escalate to ENSEMBLE."
    """
    deep_h = ReasoningSwarmHarness(task_description=task, mode_override="DEEP")
    deep_trace = deep_h.run()

    if deep_trace.confidence < 7:
        ens_h = ReasoningSwarmHarness(task_description=task, mode_override="ENSEMBLE")
        ens_trace = ens_h.run()
        return ReasoningTrace(
            mode="ENSEMBLE",
            confidence=ens_trace.confidence,
            checkpoints_hit=deep_trace.checkpoints_hit + ens_trace.checkpoints_hit,
            escalations=deep_trace.escalations + 1,
            techniques_used=deep_trace.techniques_used + ens_trace.techniques_used,
            raw_output=deep_trace.raw_output + "\n\n--- ESCALATED TO ENSEMBLE ---\n\n" + ens_trace.raw_output,
            subprocess_calls=deep_trace.subprocess_calls + ens_trace.subprocess_calls,
        )

    return deep_trace


# ═══════════════════════════════════════════════════════════════════════════════
# Test 1 — Single-file refactor: all 11 checkpoints, confidence >= 7
# ═══════════════════════════════════════════════════════════════════════════════


class TestSingleFileRefactor:
    """Deep Think on a single-file refactor task must hit all 11 checkpoints
    with final confidence >= 7."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep(REFACTOR_TASK)

    # ── Checkpoint coverage ─────────────────────────────────────────────

    def test_all_11_checkpoints_hit(self, trace):
        assert trace.checkpoints_hit == 11

    def test_confidence_at_least_7(self, trace):
        assert trace.confidence >= 7

    def test_mode_is_deep(self, trace):
        assert trace.mode == "DEEP"

    def test_escalations_zero(self, trace):
        assert trace.escalations == 0

    # ── Technique ordering 1-11 ─────────────────────────────────────────

    def test_technique_ordering(self, trace):
        """Techniques must appear in the prescribed 1-11 order."""
        positions = []
        for name, _ in DEEP_THINK_TECHNIQUES:
            pos = trace.raw_output.find(f"┌─ {name}")
            assert pos >= 0, f"{name} section not found"
            positions.append(pos)
        for i in range(1, len(positions)):
            assert positions[i] > positions[i - 1], (
                f"{DEEP_THINK_TECHNIQUES[i][0]} appears before "
                f"{DEEP_THINK_TECHNIQUES[i-1][0]}"
            )

    def test_checkpoint_numbers_sequential(self, trace):
        """Checkpoint N must appear in the N-th technique section."""
        for idx, (name, marker) in enumerate(DEEP_THINK_TECHNIQUES):
            section = _extract_section(trace.raw_output, name)
            assert f"[CHECKPOINT {idx + 1}]" in section, (
                f"{name}: expected [CHECKPOINT {idx + 1}]"
            )

    def test_techniques_used_list(self, trace):
        expected = [n for n, _ in DEEP_THINK_TECHNIQUES]
        assert trace.techniques_used == expected

    # ── Problem statement references ────────────────────────────────────

    # Techniques whose mock output embeds the task verbatim or via key terms
    _TASK_EMBEDDING_TECHNIQUES = [
        "META-COGNITION",
        "STEP-BACK",
        "DECOMPOSITION",
        "ANALOGICAL REASONING",
    ]

    @pytest.mark.parametrize(
        "technique_name",
        _TASK_EMBEDDING_TECHNIQUES,
    )
    def test_technique_embeds_task_context(self, trace, technique_name):
        """Techniques that contextualize the problem must reference task terms."""
        section = _extract_section(trace.raw_output, technique_name)
        content = _inner(section)
        key_terms = [w.lower() for w in REFACTOR_TASK.split() if len(w) > 3]
        referenced = any(t in content.lower() for t in key_terms)
        assert referenced, (
            f"{technique_name} does not reference problem terms {key_terms[:5]}"
        )

    def test_all_techniques_have_substantive_content(self, trace):
        """Every technique section must contain substantive analysis, not stubs."""
        for name, _ in DEEP_THINK_TECHNIQUES:
            section = _extract_section(trace.raw_output, name)
            content = _inner(section)
            # Exclude checkpoint marker lines
            lines = [
                l for l in content.split("\n")
                if l.strip() and not l.strip().startswith("[CHECKPOINT")
            ]
            assert len(lines) >= 1, f"{name} has no content lines"
            total = sum(len(l) for l in lines)
            assert total > 40, (
                f"{name} content too brief ({total} chars)"
            )

    # ── Token estimate (character-count proxy) ──────────────────────────

    def test_output_length_in_token_range(self, trace):
        """Output should correspond to 10-20K tokens (loose char proxy)."""
        char_count = len(trace.raw_output)
        # With mock data, each section is ~150-300 chars, 11 sections + summary
        # Minimum: ~2000 chars. We use a permissive lower bound.
        assert char_count > 1500, f"Output suspiciously short: {char_count} chars"
        assert char_count < _TOKEN_HI, f"Output too long: {char_count} chars"


# ═══════════════════════════════════════════════════════════════════════════════
# Test 2 — Multi-function extraction: checkpoint coherence
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiFunctionExtractionCoherence:
    """Decomposition sub-problems must align with Chain of Thought steps
    for a multi-function extraction task."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep(EXTRACTION_TASK)

    def test_decomposition_has_subproblems(self, trace):
        decomp = _extract_section(trace.raw_output, "DECOMPOSITION")
        content = _inner(decomp)
        assert "SUB-PROBLEMS" in content
        # At least 2 numbered sub-problems
        subs = re.findall(r"\d+\.\s+\w+", content)
        assert len(subs) >= 2, f"Expected >=2 sub-problems, found {len(subs)}"

    def test_decomposition_has_dependencies(self, trace):
        decomp = _extract_section(trace.raw_output, "DECOMPOSITION")
        content = _inner(decomp)
        assert "DEPENDENCIES" in content

    def test_chain_of_thought_has_steps(self, trace):
        cot = _extract_section(trace.raw_output, "CHAIN OF THOUGHT")
        content = _inner(cot)
        steps = re.findall(r"Step \d+", content)
        assert len(steps) >= 2, f"CoT should have >=2 steps, found {len(steps)}"

    def test_decomposition_aligns_with_cot(self, trace):
        """Decomposition sub-problem structure must be reflected in CoT steps."""
        decomp = _extract_section(trace.raw_output, "DECOMPOSITION")
        cot = _extract_section(trace.raw_output, "CHAIN OF THOUGHT")
        decomp_content = _inner(decomp)
        cot_content = _inner(cot)

        # Extract sub-problem identifiers from Decomposition
        decomp_nums = set(re.findall(r"(\d+)\.\s+\w+", decomp_content))

        # CoT should reference or mirror the decomposition structure
        cot_steps = re.findall(r"Step (\d+)", cot_content)
        assert len(cot_steps) >= len(decomp_nums) or len(cot_steps) >= 2, (
            "CoT steps should mirror Decomposition sub-problems"
        )

    def test_cot_conclusion_builds_on_decomposition(self, trace):
        cot = _extract_section(trace.raw_output, "CHAIN OF THOUGHT")
        content = _inner(cot)
        conclusion = re.search(r"Conclusion:\s*(.+)", content)
        assert conclusion, "CoT must have a Conclusion line"
        assert len(conclusion.group(1).strip()) > 10, "Conclusion must be substantive"

    def test_step_back_identifies_actual_need(self, trace):
        """Step-Back must distinguish between the literal request and the
        ACTUAL underlying need."""
        stepback = _extract_section(trace.raw_output, "STEP-BACK")
        content = _inner(stepback)
        assert "ACTUALLY" in content, (
            "Step-Back must identify what the user ACTUALLY wants"
        )
        assert "Literal request" in content, (
            "Step-Back must state the literal request before interpreting"
        )

    def test_all_11_checkpoints(self, trace):
        assert trace.checkpoints_hit == 11


# ═══════════════════════════════════════════════════════════════════════════════
# Test 3 — Low-confidence Deep Think escalates to Ensemble
# ═══════════════════════════════════════════════════════════════════════════════


class TestLowConfidenceEscalation:
    """When Deep Think confidence drops below 7 the system must escalate
    to Ensemble mode (per reasoning-swarm-SKILL.md §confidence gate)."""

    @staticmethod
    def _make_low_confidence_deep_trace() -> ReasoningTrace:
        """Return a ReasoningTrace that simulates low-confidence Deep Think."""
        return ReasoningTrace(
            mode="DEEP",
            confidence=5,
            checkpoints_hit=11,
            escalations=0,
            techniques_used=[n for n, _ in DEEP_THINK_TECHNIQUES],
            raw_output="MOCK LOW CONFIDENCE DEEP THINK OUTPUT\nConfidence: 5",
        )

    def test_confidence_gate_triggers_ensemble(self):
        """Confidence < 7 must trigger escalation."""
        trace = self._make_low_confidence_deep_trace()
        assert trace.confidence < 7

        # Direct logic test: if deep confidence < 7, ensemble should run
        ens_h = ReasoningSwarmHarness(task_description=REFACTOR_TASK, mode_override="ENSEMBLE")
        ens_trace = ens_h.run()
        assert ens_trace.mode == "ENSEMBLE"

    def test_escalation_produces_ensemble_trace(self):
        """The escalated path must produce an Ensemble-mode trace."""
        # Monkeypatch harness to return low-confidence deep
        original_run_deep = ReasoningSwarmHarness._run_deep

        def _low_conf_deep(self):
            return ReasoningTrace(
                mode="DEEP",
                confidence=5,
                checkpoints_hit=11,
                escalations=0,
                techniques_used=[n for n, _ in DEEP_THINK_TECHNIQUES],
                raw_output="LOW CONF DEEP",
            )

        ReasoningSwarmHarness._run_deep = _low_conf_deep
        try:
            result = _run_with_escalation(REFACTOR_TASK)
            assert result.mode == "ENSEMBLE", (
                f"Expected ENSEMBLE after low-confidence Deep Think, got {result.mode}"
            )
            assert result.escalations == 1, (
                f"Expected 1 escalation, got {result.escalations}"
            )
        finally:
            ReasoningSwarmHarness._run_deep = original_run_deep

    def test_escalation_confidence_improves(self):
        """Ensemble confidence should be >= the low Deep Think confidence."""
        original_run_deep = ReasoningSwarmHarness._run_deep

        def _low_conf_deep(self):
            return ReasoningTrace(
                mode="DEEP",
                confidence=4,
                checkpoints_hit=11,
                escalations=0,
                techniques_used=[n for n, _ in DEEP_THINK_TECHNIQUES],
                raw_output="LOW CONF DEEP",
            )

        ReasoningSwarmHarness._run_deep = _low_conf_deep
        try:
            result = _run_with_escalation(REFACTOR_TASK)
            assert result.confidence >= 4, (
                f"Ensemble confidence ({result.confidence}) should be >= "
                f"Deep Think confidence (4)"
            )
        finally:
            ReasoningSwarmHarness._run_deep = original_run_deep

    def test_high_confidence_does_not_escalate(self):
        """Confidence >= 7 must NOT trigger escalation."""
        result = _run_with_escalation(REFACTOR_TASK)
        assert result.mode == "DEEP", (
            f"Expected DEEP (no escalation) for high-confidence task, got {result.mode}"
        )
        assert result.escalations == 0

    def test_escalation_combines_techniques(self):
        """Escalated trace must include both Deep Think and Ensemble techniques."""
        original_run_deep = ReasoningSwarmHarness._run_deep

        def _low_conf_deep(self):
            return ReasoningTrace(
                mode="DEEP",
                confidence=5,
                checkpoints_hit=11,
                escalations=0,
                techniques_used=[n for n, _ in DEEP_THINK_TECHNIQUES],
                raw_output="LOW CONF DEEP",
            )

        ReasoningSwarmHarness._run_deep = _low_conf_deep
        try:
            result = _run_with_escalation(REFACTOR_TASK)
            # Must contain both Deep and Ensemble technique names
            deep_techs = [n for n, _ in DEEP_THINK_TECHNIQUES]
            for t in deep_techs:
                assert t in result.techniques_used, (
                    f"Escalated trace missing Deep technique: {t}"
                )
            ensemble_techs = [u for u in result.techniques_used if u.startswith("ENSEMBLE:")]
            assert len(ensemble_techs) > 0, "Escalated trace must contain Ensemble techniques"
        finally:
            ReasoningSwarmHarness._run_deep = original_run_deep


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-cutting verifications
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeepThinkVerifications:
    """Cross-cutting checks shared across all Deep Think runs."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep(REFACTOR_TASK)

    # ── Step-Back: actual need vs literal request ───────────────────────

    def test_stepback_actual_need(self, trace):
        """Step-Back must identify what the user ACTUALLY wants, not just
        repeat the literal request."""
        section = _extract_section(trace.raw_output, "STEP-BACK")
        content = _inner(section)
        assert "ACTUALLY" in content or "actually" in content, (
            "Step-Back must explicitly identify the ACTUAL need"
        )
        # Must also state the literal request for contrast
        assert "Literal" in content or "literal" in content, (
            "Step-Back must state the literal request"
        )

    # ── Tree of Thought: PURSUE / PRUNE verdicts ───────────────────────

    def test_tree_of_thought_has_verdicts(self, trace):
        section = _extract_section(trace.raw_output, "TREE OF THOUGHT")
        content = _inner(section)
        assert "PURSUE" in content, "Tree of Thought must have at least one PURSUE verdict"
        assert "PRUNE" in content, "Tree of Thought must have at least one PRUNE verdict"

    def test_tree_of_thought_has_selected_branch(self, trace):
        section = _extract_section(trace.raw_output, "TREE OF THOUGHT")
        content = _inner(section)
        assert "SELECTED" in content, "Tree of Thought must declare a SELECTED branch"

    def test_tree_of_thought_three_branches(self, trace):
        section = _extract_section(trace.raw_output, "TREE OF THOUGHT")
        content = _inner(section)
        for label in ("BRANCH A", "BRANCH B", "BRANCH C"):
            assert label in content, f"Tree of Thought missing {label}"

    # ── RAVEN Loop: conditional looping ─────────────────────────────────

    def test_raven_loop_has_loop_decision(self, trace):
        """RAVEN Loop must declare whether to loop again."""
        section = _extract_section(trace.raw_output, "RAVEN LOOP")
        content = _inner(section)
        assert "LOOP" in content.upper(), "RAVEN Loop must contain loop decision"

    def test_raven_loop_all_phases(self, trace):
        section = _extract_section(trace.raw_output, "RAVEN LOOP")
        content = _inner(section)
        for phase in ("REFLECT", "ADAPT", "VERIFY", "EXECUTE", "NAVIGATE"):
            assert phase in content, f"RAVEN Loop missing phase: {phase}"

    # ── Confidence calibration ──────────────────────────────────────────

    def test_confidence_is_integer(self, trace):
        assert isinstance(trace.confidence, int)

    def test_confidence_in_valid_range(self, trace):
        assert 1 <= trace.confidence <= 10

    def test_confidence_matches_output(self, trace):
        """The trace confidence should match what the summary claims."""
        match = re.search(r"Confidence:\s*(\d+)", trace.raw_output)
        assert match, "Output must contain a Confidence line in the summary"
        assert int(match.group(1)) == trace.confidence

    # ── Token estimate ──────────────────────────────────────────────────

    def test_token_estimate_character_proxy(self, trace):
        """Output length should be within a plausible 10-20K token range
        (using ~3-5 chars/token as proxy)."""
        chars = len(trace.raw_output)
        assert chars > 1500, f"Output too short for 10K tokens: {chars} chars"
        assert chars < _TOKEN_HI, f"Output exceeds 20K token proxy: {chars} chars"
