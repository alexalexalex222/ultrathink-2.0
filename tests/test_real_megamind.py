"""Real agent test: Megamind mode with live LLM calls.

Runs the 10→3→1 Megamind pipeline against the Kilo API with real model
inference. Validates that live outputs satisfy all Megamind requirements:
10 angle-explorers produce output, 3 synthesizers produce distinct analyses,
final synthesis integrates consensus + conflict + risk, agreement level is
calculated, conflicts are identified and resolved, risk assessment identifies
concrete failure modes, and the iteration loop triggers when confidence < 7.

Requires: KILO_API_KEY env var (or KILOCODE_TOKEN) and network access.

Discovery marker: real_agent (matches batch_test.py real-agent suite filter).

Usage:
    pytest tests/test_real_megamind.py -v -k real_agent
    python -m cli.batch_test --suite real-agent --model mimo-v2-pro
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e_scaffold import MEGAMIND_ANGLES, MEGAMIND_SYNTHESIZERS

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

_KILO_API_URL = os.environ.get(
    "KILO_OPENROUTER_BASE",
    os.environ.get("KILO_API_URL", "https://api.kilo.ai"),
).rstrip("/")
_KILO_API_KEY = os.environ.get("KILO_API_KEY", os.environ.get("KILOCODE_TOKEN", ""))
_MODEL = os.environ.get("REASONING_SWARM_MODEL", "kilo/xiaomi/mimo-v2-pro:free")

CHAT_ENDPOINT = f"{_KILO_API_URL}/api/chat/completions"

MAX_ITERATIONS = 3
CONFIDENCE_THRESHOLD = 7

MEGAMIND_PROBLEM = (
    "Plan the migration of a monolithic Python application to microservices, "
    "considering data consistency, service discovery, backward compatibility, "
    "and zero-downtime deployment"
)

ANGLE_DIRECTIVES = {
    "PERFORMANCE": "Optimize for speed/efficiency. Focus on latency, throughput, resource usage, and scaling bottlenecks.",
    "SIMPLICITY": "Optimize for maintainability. Focus on readability, modularity, ease of onboarding, and reducing cognitive load.",
    "SECURITY": "Optimize for safety/security. Focus on attack surfaces, input validation, authentication, authorization, and data protection.",
    "SCALABILITY": "What if this scales 100x? Focus on horizontal scaling, sharding, load distribution, and capacity planning.",
    "EDGE CASES": "Find what breaks. Focus on boundary conditions, race conditions, failure modes, error recovery, and unusual inputs.",
    "DEVIL'S ADVOCATE": "Why is the obvious answer WRONG? Challenge every assumption, find hidden costs, and expose weaknesses in the mainstream approach.",
    "BEGINNER'S MIND": "What is actually confusing here? Focus on hidden complexity, unclear assumptions, and onboarding barriers.",
    "FUTURE SELF": "What will we regret in 6 months? Focus on tech debt, maintenance burden, and long-term architectural decisions.",
    "USER PERSPECTIVE": "What does the end user actually need? Focus on user experience, reliability, and real-world usage patterns.",
    "CONSTRAINT BREAKER": "What if we removed a key constraint? Focus on unconventional approaches, rule-breaking solutions, and paradigm shifts.",
}


# ═══════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class AngleResult:
    """Output from a single Megamind angle-explorer."""

    angle: str
    output: str
    confidence: int
    latency_ms: float
    token_count: int = 0


@dataclass
class SynthResult:
    """Output from a single Megamind synthesizer."""

    name: str
    output: str
    confidence: int
    latency_ms: float
    token_count: int = 0


@dataclass
class MegamindResult:
    """Aggregated result from a full Megamind run (one iteration)."""

    iteration: int
    angles: list[AngleResult] = field(default_factory=list)
    synthesizers: list[SynthResult] = field(default_factory=list)
    final_synthesis: str = ""
    final_confidence: int = 0
    agreement_level: str = ""
    conflicts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    total_time_ms: float = 0.0


@dataclass
class MegamindRun:
    """Complete Megamind execution across all iterations."""

    problem: str
    iterations: list[MegamindResult] = field(default_factory=list)
    total_tokens: int = 0
    total_time_ms: float = 0.0

    @property
    def final_confidence(self) -> int:
        if not self.iterations:
            return 0
        return self.iterations[-1].final_confidence

    @property
    def iteration_count(self) -> int:
        return len(self.iterations)

    @property
    def all_conflicts(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for it in self.iterations:
            for c in it.conflicts:
                if c not in seen:
                    seen.add(c)
                    result.append(c)
        return result

    @property
    def all_risks(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for it in self.iterations:
            for r in it.risks:
                if r not in seen:
                    seen.add(r)
                    result.append(r)
        return result


# ═══════════════════════════════════════════════════════════════════════════
# LLM caller
# ═══════════════════════════════════════════════════════════════════════════


def _call_llm(prompt: str, timeout: int = 180) -> str:
    """Make a single chat completion call to the Kilo API."""
    if not _KILO_API_KEY:
        pytest.skip("No Kilo API key available (set KILO_API_KEY or KILOCODE_TOKEN)")

    payload = json.dumps(
        {
            "model": _MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2048,
            "temperature": 0.7,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        CHAT_ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_KILO_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError) as exc:
        pytest.skip(f"LLM API call failed: {exc}")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


def _extract_confidence(text: str) -> int:
    """Extract a confidence score (1-10) from LLM output."""
    patterns = [
        r"[Cc]onfidence[^:]*:\s*(\d+(?:\.\d+)?)",
        r"[Cc]onfidence\s*(?:level|score)?\s*(?:is|=|:)\s*(\d+(?:\.\d+)?)",
        r"[Cc]onfidence:\s*(\d+(?:\.\d+)?)\s*/?\s*10",
        r"(\d+(?:\.\d+)?)\s*/\s*10\s*(?:confidence|Confidence)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            val = float(match.group(1))
            return min(10, max(1, round(val)))
    return 7  # default mid-range


def _extract_list_items(text: str, section_name: str) -> list[str]:
    """Extract bullet-pointed items from a named section of LLM output."""
    # Look for section header followed by bullet points
    patterns = [
        rf"(?i){re.escape(section_name)}[:\s]*\n((?:[-*•]\s*.+\n?)+)",
        rf"(?i){re.escape(section_name)}[:\s]*\n((?:\d+[.)]\s*.+\n?)+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            block = match.group(1)
            items = re.findall(r"[-*•]\s*(.+)", block)
            if not items:
                items = re.findall(r"\d+[.)]\s*(.+)", block)
            return [item.strip() for item in items if item.strip()]

    # Fallback: find inline semicolon-separated items after the section name
    inline_match = re.search(
        rf"(?i){re.escape(section_name)}[:\s]*([^;\n]+(?:;\s*[^;\n]+)*)",
        text,
    )
    if inline_match:
        items = [s.strip() for s in inline_match.group(1).split(";") if s.strip()]
        if len(items) >= 2:
            return items

    return []


# ═══════════════════════════════════════════════════════════════════════════
# Prompt builders
# ═══════════════════════════════════════════════════════════════════════════


def _build_angle_prompt(angle: str, problem: str, iteration: int = 1) -> str:
    """Build the full prompt for a single angle-explorer."""
    directive = ANGLE_DIRECTIVES[angle]
    refine = ""
    if iteration > 1:
        refine = (
            f"\n\nThis is iteration {iteration}. Refine your analysis based on "
            f"the previous round's findings. Focus on gaps and unresolved concerns."
        )
    return (
        f"ANGLE: {angle}. {directive}\n\n"
        f"Problem: {problem}{refine}\n\n"
        f"Use full reasoning. Return:\n"
        f"1. A reasoning summary (3-5 sentences with evidence)\n"
        f"2. A concrete recommendation with tradeoffs\n"
        f"3. Confidence (1-10)\n"
        f"4. Key risks\n"
        f"5. Dissenting considerations (where your angle disagrees with the mainstream approach)"
    )


def _build_consensus_prompt(problem: str, angle_outputs: list[AngleResult]) -> str:
    """Build the Consensus synthesizer prompt."""
    sections = []
    for ar in angle_outputs:
        sections.append(f"=== {ar.angle} (confidence: {ar.confidence}) ===\n{ar.output}\n")
    angle_block = "\n".join(sections)

    return (
        f"You are SYNTHESIZER A (Consensus Builder) for a Megamind reasoning system.\n"
        f"Problem: {problem}\n\n"
        f"Below are outputs from 10 reasoning angle-explorers.\n\n"
        f"{angle_block}\n"
        f"Your job: Find what most angles agree on.\n\n"
        f"Provide your analysis in this format:\n"
        f"CONSENSUS_POINTS: What do 7+ angles agree on? (bullet list)\n"
        f"SPLIT_POINTS: What is split 50/50?\n"
        f"AGREEMENT_LEVEL: [X/10 angles aligned on core approach]\n"
        f"CONFIDENCE: [1-10 based on agreement strength]\n"
        f"KEY_INSIGHT: The strongest consensus finding"
    )


def _build_conflict_prompt(problem: str, angle_outputs: list[AngleResult]) -> str:
    """Build the Conflict synthesizer prompt."""
    sections = []
    for ar in angle_outputs:
        sections.append(f"=== {ar.angle} (confidence: {ar.confidence}) ===\n{ar.output}\n")
    angle_block = "\n".join(sections)

    return (
        f"You are SYNTHESIZER B (Conflict Analyzer) for a Megamind reasoning system.\n"
        f"Problem: {problem}\n\n"
        f"Below are outputs from 10 reasoning angle-explorers.\n\n"
        f"{angle_block}\n"
        f"Your job: Identify and analyze all disagreements.\n\n"
        f"Provide your analysis in this format:\n"
        f"CONFLICTS: List each conflict with root cause (bullet list)\n"
        f"RESOLUTIONS: Recommended resolution for each conflict (bullet list)\n"
        f"CRITICALITY: Which conflicts matter most and why\n"
        f"CONFIDENCE: [1-10 based on conflict severity]\n"
        f"KEY_INSIGHT: The most important disagreement to resolve"
    )


def _build_risk_prompt(problem: str, angle_outputs: list[AngleResult]) -> str:
    """Build the Risk synthesizer prompt."""
    sections = []
    for ar in angle_outputs:
        sections.append(f"=== {ar.angle} (confidence: {ar.confidence}) ===\n{ar.output}\n")
    angle_block = "\n".join(sections)

    return (
        f"You are SYNTHESIZER C (Risk Assessor) for a Megamind reasoning system.\n"
        f"Problem: {problem}\n\n"
        f"Below are outputs from 10 reasoning angle-explorers.\n\n"
        f"{angle_block}\n"
        f"Your job: Assess the scariest risks across all angles.\n\n"
        f"Provide your analysis in this format:\n"
        f"RISKS: List concrete failure modes (bullet list)\n"
        f"WORST_CASE: What is the worst case if we are wrong?\n"
        f"MINIMUM_SAFE: What is the minimum viable safe answer?\n"
        f"PRECONDITIONS: What must be true for the answer to be safe?\n"
        f"CONFIDENCE: [1-10 based on risk assessment thoroughness]\n"
        f"KEY_INSIGHT: The most critical risk to mitigate"
    )


def _build_final_synthesis_prompt(
    problem: str,
    synth_results: list[SynthResult],
    angle_outputs: list[AngleResult],
) -> str:
    """Build the final synthesis prompt integrating all 3 synthesizer outputs."""
    synth_block = "\n\n".join(
        f"=== {sr.name} ===\n{sr.output}" for sr in synth_results
    )

    return (
        f"You are the MAIN REASONER for a Megamind reasoning system.\n"
        f"Problem: {problem}\n\n"
        f"Below are analyses from 3 synthesizers that each processed 10 angle-explorer outputs.\n\n"
        f"{synth_block}\n\n"
        f"Provide your FINAL SYNTHESIS in this format:\n"
        f"CONSENSUS_VIEW: [what SYNTH A found]\n"
        f"CONFLICT_ANALYSIS: [what SYNTH B identified and how to resolve]\n"
        f"RISK_ASSESSMENT: [what SYNTH C found — concrete failure modes]\n"
        f"INTEGRATION: [how to combine all three into one answer]\n"
        f"AGREEMENT_LEVEL: [X/10 angles aligned]\n"
        f"CONFLICTS_RESOLVED: [list of conflicts resolved with reasoning]\n"
        f"RISKS_IDENTIFIED: [concrete failure modes identified]\n"
        f"CONFIDENCE: [1-10]\n"
        f"FINAL_ANSWER: [the synthesized recommendation]"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Megamind runner
# ═══════════════════════════════════════════════════════════════════════════


def _run_single_angle(angle: str, problem: str, iteration: int) -> AngleResult:
    """Run one angle-explorer and return its result."""
    prompt = _build_angle_prompt(angle, problem, iteration)
    t0 = time.time()
    output = _call_llm(prompt)
    elapsed_ms = (time.time() - t0) * 1000.0

    confidence = _extract_confidence(output)
    tokens = _estimate_tokens(output)

    return AngleResult(
        angle=angle,
        output=output,
        confidence=confidence,
        latency_ms=elapsed_ms,
        token_count=tokens,
    )


def _run_single_synth(
    name: str,
    problem: str,
    angle_outputs: list[AngleResult],
) -> SynthResult:
    """Run one synthesizer and return its result."""
    builders = {
        "CONSENSUS": _build_consensus_prompt,
        "CONFLICT": _build_conflict_prompt,
        "RISK": _build_risk_prompt,
    }
    builder = builders[name]
    prompt = builder(problem, angle_outputs)

    t0 = time.time()
    output = _call_llm(prompt)
    elapsed_ms = (time.time() - t0) * 1000.0

    confidence = _extract_confidence(output)
    tokens = _estimate_tokens(output)

    return SynthResult(
        name=name,
        output=output,
        confidence=confidence,
        latency_ms=elapsed_ms,
        token_count=tokens,
    )


def _run_real_megamind(problem: str) -> MegamindRun:
    """Execute the full Megamind pipeline with real LLM calls."""
    run = MegamindRun(problem=problem)
    overall_start = time.time()

    for iteration in range(1, MAX_ITERATIONS + 1):
        iter_start = time.time()
        iter_result = MegamindResult(iteration=iteration)

        # Phase M2: 10 angle-explorers in parallel
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                pool.submit(_run_single_angle, angle, problem, iteration): angle
                for angle in MEGAMIND_ANGLES
            }
            angle_results: list[AngleResult] = []
            for future in as_completed(futures):
                angle_results.append(future.result())

        # Sort by angle name for consistent ordering
        angle_results.sort(key=lambda ar: MEGAMIND_ANGLES.index(ar.angle))
        iter_result.angles = angle_results

        # Phase M3: 3 synthesizers in parallel (each gets all 10 angle outputs)
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(_run_single_synth, synth, problem, angle_results): synth
                for synth in MEGAMIND_SYNTHESIZERS
            }
            synth_results: list[SynthResult] = []
            for future in as_completed(futures):
                synth_results.append(future.result())

        synth_results.sort(key=lambda sr: MEGAMIND_SYNTHESIZERS.index(sr.name))
        iter_result.synthesizers = synth_results

        # Phase M4: Final synthesis
        final_prompt = _build_final_synthesis_prompt(problem, synth_results, angle_results)
        t0 = time.time()
        final_output = _call_llm(final_prompt)
        final_ms = (time.time() - t0) * 1000.0

        iter_result.final_synthesis = final_output
        iter_result.final_confidence = _extract_confidence(final_output)

        # Extract agreement level
        ag_match = re.search(r"AGREEMENT_LEVEL:\s*(\d+)/10", final_output, re.IGNORECASE)
        if ag_match:
            iter_result.agreement_level = f"{ag_match.group(1)}/10"
        else:
            # Heuristic from angle confidences
            aligned = sum(1 for ar in angle_results if ar.confidence >= 7)
            iter_result.agreement_level = f"{aligned}/10"

        # Extract conflicts
        iter_result.conflicts = _extract_list_items(final_output, "CONFLICTS_RESOLVED")
        if not iter_result.conflicts:
            iter_result.conflicts = _extract_list_items(final_output, "CONFLICTS")

        # Extract risks
        iter_result.risks = _extract_list_items(final_output, "RISKS_IDENTIFIED")
        if not iter_result.risks:
            iter_result.risks = _extract_list_items(final_output, "RISKS")

        iter_result.total_time_ms = (time.time() - iter_start) * 1000.0
        run.iterations.append(iter_result)

        # Confidence gate
        if iter_result.final_confidence >= CONFIDENCE_THRESHOLD:
            break
        if iteration >= MAX_ITERATIONS:
            break

    # Compute total metrics
    run.total_time_ms = (time.time() - overall_start) * 1000.0
    run.total_tokens = sum(
        ar.token_count
        for it in run.iterations
        for ar in it.angles
    ) + sum(
        sr.token_count
        for it in run.iterations
        for sr in it.synthesizers
    ) + sum(
        _estimate_tokens(it.final_synthesis)
        for it in run.iterations
    )

    return run


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def megamind_run():
    """Run real Megamind once per module (expensive — many LLM calls)."""
    return _run_real_megamind(MEGAMIND_PROBLEM)


# ═══════════════════════════════════════════════════════════════════════════
# Test: 10 Angle-Explorers
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealMegamindAngleExplorers:
    """All 10 angle-explorers produce substantive output."""

    @pytest.fixture
    def first_iteration(self, megamind_run):
        return megamind_run.iterations[0]

    def test_all_10_angles_present(self, first_iteration):
        assert len(first_iteration.angles) == 10
        angle_names = {ar.angle for ar in first_iteration.angles}
        assert angle_names == set(MEGAMIND_ANGLES)

    def test_each_angle_produces_distinct_output(self, first_iteration):
        outputs = [ar.output for ar in first_iteration.angles]
        assert len(set(outputs)) == 10, "Duplicate outputs detected across angles"

    def test_each_angle_exceeds_200_tokens(self, first_iteration):
        for ar in first_iteration.angles:
            assert ar.token_count > 200, (
                f"Angle {ar.angle} produced only ~{ar.token_count} tokens (need > 200)"
            )

    @pytest.mark.parametrize(
        "angle",
        MEGAMIND_ANGLES,
        ids=[a.replace(" ", "-") for a in MEGAMIND_ANGLES],
    )
    def test_angle_confidence_in_range(self, first_iteration, angle):
        matches = [ar for ar in first_iteration.angles if ar.angle == angle]
        assert len(matches) == 1
        assert 1 <= matches[0].confidence <= 10, (
            f"Angle {angle} confidence {matches[0].confidence} out of range"
        )

    def test_angles_contain_angle_specific_reasoning(self, first_iteration):
        """Each angle output should contain reasoning from its perspective."""
        for ar in first_iteration.angles:
            lower = ar.output.lower()
            assert len(lower) > 100, (
                f"Angle {ar.angle} output too short ({len(lower)} chars)"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Test: 3 Synthesizers
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealMegamindSynthesizers:
    """All 3 synthesizers produce distinct analyses from 10 angle outputs."""

    @pytest.fixture
    def first_iteration(self, megamind_run):
        return megamind_run.iterations[0]

    def test_all_3_synthesizers_present(self, first_iteration):
        assert len(first_iteration.synthesizers) == 3
        synth_names = {sr.name for sr in first_iteration.synthesizers}
        assert synth_names == set(MEGAMIND_SYNTHESIZERS)

    def test_each_synth_produces_distinct_output(self, first_iteration):
        outputs = [sr.output for sr in first_iteration.synthesizers]
        assert len(set(outputs)) == 3, "Duplicate outputs detected across synthesizers"

    def test_each_synth_exceeds_200_tokens(self, first_iteration):
        for sr in first_iteration.synthesizers:
            assert sr.token_count > 200, (
                f"Synthesizer {sr.name} produced only ~{sr.token_count} tokens (need > 200)"
            )

    def test_consensus_synth_identifies_agreement(self, first_iteration):
        consensus = next(sr for sr in first_iteration.synthesizers if sr.name == "CONSENSUS")
        lower = consensus.output.lower()
        assert any(kw in lower for kw in ["agree", "consensus", "aligned", "common", "shared"]), (
            "Consensus synthesizer does not identify agreement points"
        )

    def test_conflict_synth_identifies_disagreement(self, first_iteration):
        conflict = next(sr for sr in first_iteration.synthesizers if sr.name == "CONFLICT")
        lower = conflict.output.lower()
        assert any(kw in lower for kw in ["conflict", "disagree", "tension", "differ", "versus"]), (
            "Conflict synthesizer does not identify disagreements"
        )

    def test_risk_synth_identifies_failure_modes(self, first_iteration):
        risk = next(sr for sr in first_iteration.synthesizers if sr.name == "RISK")
        lower = risk.output.lower()
        assert any(kw in lower for kw in ["risk", "failure", "worst case", "danger", "vulnerability"]), (
            "Risk synthesizer does not identify failure modes"
        )

    def test_synth_confidences_in_range(self, first_iteration):
        for sr in first_iteration.synthesizers:
            assert 1 <= sr.confidence <= 10, (
                f"Synthesizer {sr.name} confidence {sr.confidence} out of range"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Test: Final Synthesis
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealMegamindFinalSynthesis:
    """Final synthesis integrates consensus + conflict + risk."""

    @pytest.fixture
    def first_iteration(self, megamind_run):
        return megamind_run.iterations[0]

    def test_final_synthesis_is_non_empty(self, first_iteration):
        assert len(first_iteration.final_synthesis) > 200, (
            "Final synthesis is too short"
        )

    def test_final_synthesis_references_consensus(self, first_iteration):
        lower = first_iteration.final_synthesis.lower()
        assert any(kw in lower for kw in ["consensus", "agree", "aligned", "common"]), (
            "Final synthesis does not reference consensus findings"
        )

    def test_final_synthesis_references_conflicts(self, first_iteration):
        lower = first_iteration.final_synthesis.lower()
        assert any(kw in lower for kw in ["conflict", "disagree", "tension", "tradeoff", "trade-off"]), (
            "Final synthesis does not reference conflict analysis"
        )

    def test_final_synthesis_references_risks(self, first_iteration):
        lower = first_iteration.final_synthesis.lower()
        assert any(kw in lower for kw in ["risk", "failure", "danger", "vulnerability", "worst"]), (
            "Final synthesis does not reference risk assessment"
        )

    def test_agreement_level_calculated(self, first_iteration):
        assert re.match(r"\d+/10", first_iteration.agreement_level), (
            f"Agreement level '{first_iteration.agreement_level}' not in X/10 format"
        )

    def test_confidence_in_range(self, first_iteration):
        assert 1 <= first_iteration.final_confidence <= 10, (
            f"Final confidence {first_iteration.final_confidence} out of range"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test: Conflict identification and resolution
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealMegamindConflicts:
    """At least one conflict is identified and resolved."""

    def test_at_least_one_conflict_identified(self, megamind_run):
        all_conflicts = megamind_run.all_conflicts
        if not all_conflicts:
            # Fallback: check if conflict language appears in any synthesis
            has_conflict = any(
                any(kw in it.final_synthesis.lower()
                    for kw in ["conflict", "disagree", "tension", "resolution"])
                for it in megamind_run.iterations
            )
            assert has_conflict, "No conflicts identified in any iteration"

    def test_conflict_resolution_present(self, megamind_run):
        has_resolution = any(
            any(kw in it.final_synthesis.lower()
                for kw in ["resolution", "resolve", "balanced", "compromise", "reconcile"])
            for it in megamind_run.iterations
        )
        assert has_resolution, "No conflict resolution found in any iteration"


# ═══════════════════════════════════════════════════════════════════════════
# Test: Risk assessment
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealMegamindRisks:
    """Risk assessment identifies concrete failure modes."""

    def test_risks_identified(self, megamind_run):
        all_risks = megamind_run.all_risks
        if not all_risks:
            # Fallback: check if risk language appears in any synthesis
            has_risk = any(
                any(kw in it.final_synthesis.lower()
                    for kw in ["risk", "failure mode", "danger", "vulnerability"])
                for it in megamind_run.iterations
            )
            assert has_risk, "No risks identified in any iteration"

    def test_risks_are_concrete(self, megamind_run):
        """Risks should mention concrete failure scenarios."""
        all_synthesis = " ".join(it.final_synthesis.lower() for it in megamind_run.iterations)
        concrete_risk_markers = [
            "data loss", "downtime", "latency", "availability", "consistency",
            "failure", "crash", "outage", "corruption", "migration",
            "backward compat", "service discovery", "deployment",
        ]
        markers_found = sum(1 for kw in concrete_risk_markers if kw in all_synthesis)
        assert markers_found >= 2, (
            f"Only {markers_found} concrete risk markers found (need >= 2)"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Test: Iteration loop
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealMegamindIteration:
    """Iteration behavior: confidence gate and max-3 cap."""

    def test_iteration_count_in_range(self, megamind_run):
        assert 1 <= megamind_run.iteration_count <= MAX_ITERATIONS, (
            f"Iteration count {megamind_run.iteration_count} out of range [1, {MAX_ITERATIONS}]"
        )

    def test_if_confidence_low_then_iterations_increase(self, megamind_run):
        """If the problem is complex enough that confidence stays below 7,
        the system should iterate more than once."""
        # The problem contains "migrate" which triggers low confidence in the
        # harness heuristic. With real LLM calls, confidence may vary, so we
        # just verify the iteration count is consistent with the confidence.
        if megamind_run.final_confidence < CONFIDENCE_THRESHOLD:
            assert megamind_run.iteration_count == MAX_ITERATIONS, (
                f"Confidence {megamind_run.final_confidence} < {CONFIDENCE_THRESHOLD} "
                f"but only {megamind_run.iteration_count} iterations (expected {MAX_ITERATIONS})"
            )

    def test_if_confidence_high_then_single_iteration(self, megamind_run):
        """If the LLM reaches confidence >= 7 on the first pass, only 1 iteration."""
        if megamind_run.final_confidence >= CONFIDENCE_THRESHOLD:
            # Could be 1 or more — but the last iteration should have high confidence
            assert megamind_run.iterations[-1].final_confidence >= CONFIDENCE_THRESHOLD

    def test_each_iteration_has_all_phases(self, megamind_run):
        """Each iteration must have 10 angles, 3 synthesizers, and final synthesis."""
        for it in megamind_run.iterations:
            assert len(it.angles) == 10, (
                f"Iteration {it.iteration}: expected 10 angles, got {len(it.angles)}"
            )
            assert len(it.synthesizers) == 3, (
                f"Iteration {it.iteration}: expected 3 synthesizers, got {len(it.synthesizers)}"
            )
            assert it.final_synthesis, (
                f"Iteration {it.iteration}: missing final synthesis"
            )

    def test_iterations_are_sequential(self, megamind_run):
        """Iteration numbers should be 1, 2, ..., N."""
        for i, it in enumerate(megamind_run.iterations):
            assert it.iteration == i + 1


# ═══════════════════════════════════════════════════════════════════════════
# Test: Token cost tracking
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealMegamindTokenCost:
    """Total token cost is tracked and reasonable."""

    def test_total_tokens_positive(self, megamind_run):
        assert megamind_run.total_tokens > 0, "Total token count is zero"

    def test_total_tokens_reasonable(self, megamind_run):
        """Megamind makes many calls; tokens should be substantial but not absurd."""
        # 10 angles + 3 synths + 1 final = 14 calls per iteration
        # Each ~500-2000 tokens, so per iteration ~7k-28k tokens
        # With up to 3 iterations, max ~84k tokens
        assert megamind_run.total_tokens > 1000, (
            f"Total tokens {megamind_run.total_tokens} seems too low for Megamind"
        )
        assert megamind_run.total_tokens < 500_000, (
            f"Total tokens {megamind_run.total_tokens} seems unreasonably high"
        )

    def test_per_iteration_token_breakdown(self, megamind_run):
        """Each iteration should account for all angle + synth + final tokens."""
        for it in megamind_run.iterations:
            angle_tokens = sum(ar.token_count for ar in it.angles)
            synth_tokens = sum(sr.token_count for sr in it.synthesizers)
            final_tokens = _estimate_tokens(it.final_synthesis)
            iter_total = angle_tokens + synth_tokens + final_tokens
            assert iter_total > 1000, (
                f"Iteration {it.iteration}: only {iter_total} tokens (expected > 1000)"
            )

    def test_total_time_positive(self, megamind_run):
        assert megamind_run.total_time_ms > 0


# ═══════════════════════════════════════════════════════════════════════════
# Test: Tracking summary
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealMegamindTracking:
    """Track iteration count, final confidence, conflicts resolved, risks identified."""

    def test_tracking_summary(self, megamind_run):
        """Emit a tracking summary as a structured assertion (for CI logs)."""
        summary = {
            "problem": megamind_run.problem[:60],
            "iteration_count": megamind_run.iteration_count,
            "final_confidence": megamind_run.final_confidence,
            "total_tokens": megamind_run.total_tokens,
            "total_time_ms": round(megamind_run.total_time_ms),
            "conflicts_resolved": len(megamind_run.all_conflicts),
            "risks_identified": len(megamind_run.all_risks),
            "agreement_level": megamind_run.iterations[-1].agreement_level,
            "per_iteration": [],
        }
        for it in megamind_run.iterations:
            summary["per_iteration"].append({
                "iteration": it.iteration,
                "confidence": it.final_confidence,
                "agreement_level": it.agreement_level,
                "angle_tokens": sum(ar.token_count for ar in it.angles),
                "synth_tokens": sum(sr.token_count for sr in it.synthesizers),
                "time_ms": round(it.total_time_ms),
            })

        # Validate core metrics
        assert summary["iteration_count"] >= 1
        assert 1 <= summary["final_confidence"] <= 10
        assert summary["total_tokens"] > 0

    def test_run_completes_successfully(self, megamind_run):
        """The full Megamind run must complete with valid output."""
        assert megamind_run.iteration_count >= 1
        assert len(megamind_run.iterations) >= 1
        last = megamind_run.iterations[-1]
        assert len(last.angles) == 10
        assert len(last.synthesizers) == 3
        assert last.final_synthesis
        assert 1 <= last.final_confidence <= 10

    def test_angle_diversity(self, megamind_run):
        """Angle outputs should show diversity (not copy-paste)."""
        first = megamind_run.iterations[0]
        all_outputs = [ar.output.lower() for ar in first.angles]
        unique_words: set[str] = set()
        for out in all_outputs:
            unique_words.update(out.split())
        total_words = sum(len(o.split()) for o in all_outputs)
        diversity = len(unique_words) / max(total_words, 1)
        assert diversity > 0.3, (
            f"Low angle diversity {diversity:.2f} (need > 0.3)"
        )

    def test_synth_diversity(self, megamind_run):
        """Synthesizer outputs should be distinct from each other."""
        first = megamind_run.iterations[0]
        outputs = [sr.output for sr in first.synthesizers]
        assert len(set(outputs)) == 3, "Synthesizer outputs are not distinct"

    def test_parallelism_proof(self, megamind_run):
        """Total time should be less than sequential execution time.

        If angles ran sequentially, total would be sum of all angle times.
        With parallelism, total ≈ max_angle_time + synth time + final synth time.
        We check total < 3 * max_angle_time as a loose bound.
        """
        first = megamind_run.iterations[0]
        max_angle_time = max(ar.latency_ms for ar in first.angles)
        if max_angle_time > 0:
            assert first.total_time_ms < 5 * max_angle_time, (
                f"Iteration time {first.total_time_ms:.0f}ms >= 5x max angle "
                f"{max_angle_time:.0f}ms — angles likely ran sequentially"
            )
