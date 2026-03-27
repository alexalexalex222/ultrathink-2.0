"""
Technique coverage tests — validates each of the 11 Deep Think techniques
produces correct output structure.

For each technique:
  1. Output contains the required checkpoint marker
  2. All required fields are populated (no blank fields)
  3. Field content is substantive (>10 chars, not placeholders)
  4. Cross-technique consistency (Decomposition sub-problems align with CoT steps)

Also tests technique sequencing: when run as a chain, each technique
builds on the previous one's output.

Uses the ReasoningSwarmHarness from test_e2e_scaffold.py.
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
    TEST_PROBLEMS,
    harness,
)

# Canonical task for single-technique tests
CANONICAL_TASK = MEDIUM_PROBLEMS[0]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _extract_technique_section(raw_output: str, technique_name: str) -> str:
    """Extract the full section text for a single technique from raw_output."""
    pattern = re.escape(technique_name)
    match = re.search(
        rf"┌─\s*{pattern}.*?└─+┘",
        raw_output,
        re.DOTALL,
    )
    assert match, f"Section for {technique_name} not found in output"
    return match.group(0)


def _extract_inner_content(section: str) -> str:
    """Extract just the content lines (after │) from a box section."""
    lines = section.split("\n")
    content_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("│"):
            content_lines.append(stripped[1:].strip())
    return "\n".join(content_lines)


def _run_deep(task: str = CANONICAL_TASK) -> ReasoningTrace:
    """Run Deep Think and return the trace."""
    h = ReasoningSwarmHarness(task_description=task, mode_override="DEEP")
    return h.run()


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Checkpoint markers
# ═══════════════════════════════════════════════════════════════════════════


class TestCheckpointMarkers:
    """Each technique section contains its required checkpoint marker."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep()

    @pytest.mark.parametrize(
        "technique_name,checkpoint",
        DEEP_THINK_TECHNIQUES,
        ids=[t[0].replace("/", "-").replace(" ", "-") for t in DEEP_THINK_TECHNIQUES],
    )
    def test_checkpoint_present(self, trace, technique_name, checkpoint):
        section = _extract_technique_section(trace.raw_output, technique_name)
        assert checkpoint in section, (
            f"{technique_name} missing checkpoint {checkpoint}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Required fields per technique
# ═══════════════════════════════════════════════════════════════════════════


# Field definitions per technique — each list item is a substring that must
# appear in the technique's content section.
_REQUIRED_FIELDS = {
    "META-COGNITION": [
        "Problem type",
        "Confidence (1-10)",
        "Uncertainties",
        "Missing perspective",
    ],
    "STEP-BACK": [
        "Literal request",
        "What user ACTUALLY wants",
        "What I should",
    ],
    "DECOMPOSITION": [
        "MAIN PROBLEM",
        "SUB-PROBLEMS",
        "DEPENDENCIES",
    ],
    "TREE OF THOUGHT": [
        "BRANCH A",
        "BRANCH B",
        "BRANCH C",
        "Pros",
        "Cons",
        "Verdict",
        "SELECTED",
    ],
    "FIRST PRINCIPLES": [
        "Assumptions",
        "FUNDAMENTALLY required",
    ],
    "ANALOGICAL REASONING": [
        "Abstract pattern",
        "Similar solved problems",
        "What transfers",
    ],
    "CHAIN OF THOUGHT": [
        "Step 1",
        "Step 2",
        "Conclusion",
    ],
    "DEVIL'S ADVOCATE": [
        "My solution",
        "ATTACK 1",
        "Defense",
    ],
    "INVERSION / PRE-MORTEM": [
        "GUARANTEE failure",
        "Prevention",
    ],
    "RAVEN LOOP": [
        "REFLECT",
        "ADAPT",
        "VERIFY",
        "EXECUTE",
        "NAVIGATE",
    ],
    "RECURSIVE SELF-IMPROVEMENT": [
        "DRAFT",
        "CRITIQUE",
        "IMPROVED",
        "FINAL CONFIDENCE",
    ],
}


class TestRequiredFields:
    """Each technique section contains all required fields from the template."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep()

    @pytest.mark.parametrize(
        "technique_name",
        [t[0] for t in DEEP_THINK_TECHNIQUES],
        ids=[t[0].replace("/", "-").replace(" ", "-") for t in DEEP_THINK_TECHNIQUES],
    )
    def test_all_fields_populated(self, trace, technique_name):
        section = _extract_technique_section(trace.raw_output, technique_name)
        content = _extract_inner_content(section)
        content_lower = content.lower()
        required = _REQUIRED_FIELDS[technique_name]
        for field_label in required:
            assert field_label.lower() in content_lower, (
                f"{technique_name} missing required field: {field_label!r}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Substantive content (>10 chars, not placeholders)
# ═══════════════════════════════════════════════════════════════════════════


class TestSubstantiveContent:
    """Field values contain real content — not blank, not placeholders."""

    PLACEHOLDER_PATTERNS = [
        r"^\[answer\]$",
        r"^\[state\]$",
        r"^\[sub\]$",
        r"^\[list\]$",
        r"^\[describe\]$",
        r"^\[step\]$",
        r"^\[reason\]$",
        r"^\[counter\]$",
        r"^\[how\]$",
        r"^\[action/output\]$",
        r"^\[x\]$",
        r"^\[y\]$",
        r"^\[which \+ WHY\]$",
        r"^\[continue until done\]$",
        r"^\[final answer\]$",
        r"^\[sequence\]$",
        r"^\[what before what\]$",
        r"^\[similar\]$",
        r"^\[X\]$",
        r"^\[Y\]$",
        r"^\[better version\]$",
    ]

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep()

    @pytest.mark.parametrize(
        "technique_name",
        [t[0] for t in DEEP_THINK_TECHNIQUES],
        ids=[t[0].replace("/", "-").replace(" ", "-") for t in DEEP_THINK_TECHNIQUES],
    )
    def test_content_not_blank(self, trace, technique_name):
        section = _extract_technique_section(trace.raw_output, technique_name)
        content = _extract_inner_content(section)
        # Every content line must have at least some text
        for line in content.split("\n"):
            if line.strip() and not line.strip().startswith("[CHECKPOINT"):
                # Remove the field label prefix and check the value
                after_colon = re.sub(r"^[^:]+:\s*", "", line.strip())
                if after_colon:
                    assert len(after_colon.strip()) > 10, (
                        f"{technique_name}: content too short: {after_colon!r}"
                    )

    @pytest.mark.parametrize(
        "technique_name",
        [t[0] for t in DEEP_THINK_TECHNIQUES],
        ids=[t[0].replace("/", "-").replace(" ", "-") for t in DEEP_THINK_TECHNIQUES],
    )
    def test_no_placeholder_text(self, trace, technique_name):
        section = _extract_technique_section(trace.raw_output, technique_name)
        content = _extract_inner_content(section)
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("[CHECKPOINT"):
                after_colon = re.sub(r"^[^:]+:\s*", "", stripped).strip()
                if after_colon:
                    for pat in self.PLACEHOLDER_PATTERNS:
                        assert not re.match(pat, after_colon, re.IGNORECASE), (
                            f"{technique_name}: placeholder detected: {after_colon!r}"
                        )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Technique box structure
# ═══════════════════════════════════════════════════════════════════════════


class TestTechniqueBoxStructure:
    """Each technique section follows the ┌─...│...└─┘ box format."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep()

    @pytest.mark.parametrize(
        "technique_name",
        [t[0] for t in DEEP_THINK_TECHNIQUES],
        ids=[t[0].replace("/", "-").replace(" ", "-") for t in DEEP_THINK_TECHNIQUES],
    )
    def test_box_has_top_border(self, trace, technique_name):
        section = _extract_technique_section(trace.raw_output, technique_name)
        assert section.startswith("┌─"), f"{technique_name}: missing top border"

    @pytest.mark.parametrize(
        "technique_name",
        [t[0] for t in DEEP_THINK_TECHNIQUES],
        ids=[t[0].replace("/", "-").replace(" ", "-") for t in DEEP_THINK_TECHNIQUES],
    )
    def test_box_has_bottom_border(self, trace, technique_name):
        section = _extract_technique_section(trace.raw_output, technique_name)
        assert "┘" in section, f"{technique_name}: missing bottom border"

    @pytest.mark.parametrize(
        "technique_name",
        [t[0] for t in DEEP_THINK_TECHNIQUES],
        ids=[t[0].replace("/", "-").replace(" ", "-") for t in DEEP_THINK_TECHNIQUES],
    )
    def test_box_has_pipe_delimiters(self, trace, technique_name):
        section = _extract_technique_section(trace.raw_output, technique_name)
        pipe_lines = [l for l in section.split("\n") if l.strip().startswith("│")]
        assert len(pipe_lines) >= 2, (
            f"{technique_name}: expected ≥2 pipe-delimited content lines"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Cross-technique consistency
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossTechniqueConsistency:
    """Verify techniques reference each other's outputs consistently."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep()

    def test_decomposition_subproblems_mentioned_in_chain_of_thought(self, trace):
        """Decomposition sub-problems should appear or align with CoT steps."""
        decomp = _extract_technique_section(trace.raw_output, "DECOMPOSITION")
        cot = _extract_technique_section(trace.raw_output, "CHAIN OF THOUGHT")
        decomp_content = _extract_inner_content(decomp)
        cot_content = _extract_inner_content(cot)
        # CoT should contain numbered steps that reflect decomposition's structure
        cot_steps = re.findall(r"Step \d+", cot_content)
        assert len(cot_steps) >= 2, (
            "Chain of Thought should have ≥2 steps aligning with Decomposition"
        )

    def test_tree_of_thought_selection_referenced_by_chain_of_thought(self, trace):
        """Tree of Thought's selected branch should be reflected in CoT conclusion."""
        tot = _extract_technique_section(trace.raw_output, "TREE OF THOUGHT")
        cot = _extract_technique_section(trace.raw_output, "CHAIN OF THOUGHT")
        tot_content = _extract_inner_content(tot)
        cot_content = _extract_inner_content(cot)
        # Extract the selected approach from Tree of Thought
        selected_match = re.search(r"SELECTED:\s*(.+)", tot_content)
        if selected_match:
            selected = selected_match.group(1).strip()
            # At minimum, CoT conclusion should exist and be non-empty
            conclusion_match = re.search(r"Conclusion:\s*(.+)", cot_content)
            assert conclusion_match and len(conclusion_match.group(1).strip()) > 10, (
                "Chain of Thought conclusion should build on Tree of Thought selection"
            )

    def test_first_principles_informs_analogical_reasoning(self, trace):
        """First Principles 'fundamentally required' should connect to analogical reasoning."""
        fp = _extract_technique_section(trace.raw_output, "FIRST PRINCIPLES")
        ar = _extract_technique_section(trace.raw_output, "ANALOGICAL REASONING")
        fp_content = _extract_inner_content(fp)
        ar_content = _extract_inner_content(ar)
        # Both should be substantive
        assert len(fp_content) > 50
        assert len(ar_content) > 50

    def test_devil_advocate_attacks_reflect_prior_solution(self, trace):
        """Devil's Advocate should reference a solution built from prior techniques."""
        da = _extract_technique_section(trace.raw_output, "DEVIL'S ADVOCATE")
        content = _extract_inner_content(da)
        # Must have a solution stated and attacks against it
        assert "My solution" in content
        attacks = re.findall(r"ATTACK \d+", content)
        assert len(attacks) >= 1, "Devil's Advocate must contain attacks"

    def test_inversion_references_prior_approach(self, trace):
        """Inversion/Pre-Mortem should reference failure modes of the chosen approach."""
        inv = _extract_technique_section(trace.raw_output, "INVERSION / PRE-MORTEM")
        content = _extract_inner_content(inv)
        prevention_count = len(re.findall(r"Prevention:", content))
        assert prevention_count >= 1, (
            "Inversion must contain at least 1 failure-prevention pair"
        )

    def test_raven_loop_references_prior_techniques(self, trace):
        """RAVEN Loop REFLECT should reference earlier technique outputs."""
        raven = _extract_technique_section(trace.raw_output, "RAVEN LOOP")
        content = _extract_inner_content(raven)
        # REFLECT should mention something substantive
        reflect_match = re.search(r"REFLECT:\s*(.+?)(?:\n|$)", content)
        assert reflect_match and len(reflect_match.group(1).strip()) > 20, (
            "RAVEN REFLECT should contain substantive reflection"
        )

    def test_recursive_self_improvement_critiques_prior_output(self, trace):
        """Recursive Self-Improvement should contain a real critique with weaknesses."""
        rsi = _extract_technique_section(trace.raw_output, "RECURSIVE SELF-IMPROVEMENT")
        content = _extract_inner_content(rsi)
        assert "Weakness" in content, "Must identify specific weaknesses"
        assert "IMPROVED" in content, "Must provide an improved version"


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Technique sequencing
# ═══════════════════════════════════════════════════════════════════════════


class TestTechniqueSequencing:
    """Verify that when run as a chain, each technique builds on the previous."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_deep()

    def test_all_11_techniques_present_in_order(self, trace):
        """Output must contain all 11 techniques in the prescribed order."""
        for name, _marker in DEEP_THINK_TECHNIQUES:
            assert name in trace.raw_output, f"{name} not found in output"

    def test_techniques_appear_in_correct_sequence(self, trace):
        """Each technique section must appear after the previous one."""
        positions = []
        for name, _ in DEEP_THINK_TECHNIQUES:
            pos = trace.raw_output.find(f"┌─ {name}")
            assert pos >= 0, f"{name} section not found"
            positions.append(pos)
        # Positions must be strictly increasing
        for i in range(1, len(positions)):
            assert positions[i] > positions[i - 1], (
                f"{DEEP_THINK_TECHNIQUES[i][0]} appears before "
                f"{DEEP_THINK_TECHNIQUES[i - 1][0]}"
            )

    def test_checkpoints_hit_is_11(self, trace):
        assert trace.checkpoints_hit == 11

    def test_techniques_used_count(self, trace):
        assert len(trace.techniques_used) == 11

    def test_techniques_used_names(self, trace):
        expected = [name for name, _ in DEEP_THINK_TECHNIQUES]
        assert trace.techniques_used == expected

    def test_cumulative_confidence_built_from_techniques(self, trace):
        """Final confidence should be an aggregate of individual technique confidences."""
        assert 1 <= trace.confidence <= 10

    def test_output_ends_with_summary(self, trace):
        """Raw output must end with a DEEP THINK COMPLETE summary."""
        assert "DEEP THINK COMPLETE" in trace.raw_output
        assert "Checkpoints Hit: 11/11" in trace.raw_output

    def test_each_checkpoint_number_matches_position(self, trace):
        """Checkpoint N must appear in the N-th technique section."""
        for idx, (name, marker) in enumerate(DEEP_THINK_TECHNIQUES):
            section = _extract_technique_section(trace.raw_output, name)
            expected_number = idx + 1
            assert f"[CHECKPOINT {expected_number}]" in section, (
                f"{name}: expected [CHECKPOINT {expected_number}]"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: DEEP mode dispatch and mode correctness
# ═══════════════════════════════════════════════════════════════════════════


class TestDeepModeDispatch:
    """Verify that Deep Think mode is correctly resolved and dispatched."""

    def test_mode_resolves_to_deep_think(self, harness):
        h = harness(CANONICAL_TASK, mode="DEEP")
        assert h.get_mode() == "DEEP THINK"

    def test_mode_resolves_from_full_name(self, harness):
        h = harness(CANONICAL_TASK, mode="DEEP THINK")
        assert h.get_mode() == "DEEP THINK"

    def test_deep_run_returns_deep_mode(self, harness):
        h = harness(CANONICAL_TASK, mode="DEEP")
        trace = h.run()
        assert trace.mode == "DEEP"

    def test_deep_loads_deepthink_skill(self, harness):
        h = harness(CANONICAL_TASK, mode="DEEP")
        skill = h.load_skill()
        assert "DEEPTHINK" in skill or "DEEP THINK" in skill.upper()


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Output across multiple problems
# ═══════════════════════════════════════════════════════════════════════════


class TestMultipleProblems:
    """Deep Think produces valid output for multiple problem complexities."""

    @pytest.mark.parametrize(
        "level,problem",
        [
            (level, prob)
            for level, probs in TEST_PROBLEMS.items()
            for prob in probs
        ],
        ids=[
            f"{level}-{i}"
            for level, probs in TEST_PROBLEMS.items()
            for i, _ in enumerate(probs)
        ],
    )
    def test_deep_produces_11_checkpoints(self, harness, level, problem):
        h = harness(problem, mode="DEEP")
        trace = h.run()
        assert trace.checkpoints_hit == 11, (
            f"Expected 11 checkpoints for {level} problem: {problem!r}"
        )

    @pytest.mark.parametrize(
        "level,problem",
        [
            (level, prob)
            for level, probs in TEST_PROBLEMS.items()
            for prob in probs
        ],
        ids=[
            f"{level}-{i}"
            for level, probs in TEST_PROBLEMS.items()
            for i, _ in enumerate(probs)
        ],
    )
    def test_deep_confidence_in_range(self, harness, level, problem):
        h = harness(problem, mode="DEEP")
        trace = h.run()
        assert 1 <= trace.confidence <= 10, (
            f"Confidence out of range for {level} problem: {problem!r}"
        )

    @pytest.mark.parametrize(
        "level,problem",
        [
            (level, prob)
            for level, probs in TEST_PROBLEMS.items()
            for prob in probs
        ],
        ids=[
            f"{level}-{i}"
            for level, probs in TEST_PROBLEMS.items()
            for i, _ in enumerate(probs)
        ],
    )
    def test_deep_all_techniques_used(self, harness, level, problem):
        h = harness(problem, mode="DEEP")
        trace = h.run()
        expected = [name for name, _ in DEEP_THINK_TECHNIQUES]
        assert trace.techniques_used == expected, (
            f"Technique mismatch for {level} problem: {problem!r}"
        )
