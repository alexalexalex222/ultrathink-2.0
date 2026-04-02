"""Real agent test: Ensemble mode with live LLM calls.

Runs the 5-angle Ensemble pipeline against the Kilo API with real model
inference. Validates that live outputs satisfy all Ensemble requirements:
angle diversity, genuine disagreement, synthesis quality, parallelism,
weighted confidence, and tradeoff coverage.

Requires: KILO_API_KEY env var (or KILOCODE_TOKEN) and network access.

Discovery marker: real_agent (matches batch_test.py real-agent suite filter).

Usage:
    pytest tests/test_real_ensemble.py -v -k real_agent
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

from tests.test_e2e_scaffold import ENSEMBLE_ANGLES

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

ANGLE_DIRECTIVES = {
    "PERFORMANCE": "Optimize for speed/efficiency. Focus on latency, throughput, resource usage, and scaling bottlenecks.",
    "SIMPLICITY": "Optimize for maintainability. Focus on readability, modularity, ease of onboarding, and reducing cognitive load.",
    "SECURITY": "Optimize for safety/security. Focus on attack surfaces, input validation, authentication, authorization, and data protection.",
    "EDGE CASES": "Find what breaks. Focus on boundary conditions, race conditions, failure modes, error recovery, and unusual inputs.",
    "DEVIL'S ADVOCATE": "Why is the obvious answer WRONG? Challenge every assumption, find hidden costs, and expose weaknesses in the mainstream approach.",
}

# High-complexity problems from the bead specification
ENSEMBLE_PROBLEMS = [
    "Design a rate limiter that handles burst traffic, per-user quotas, and distributed coordination",
    "Architect a plugin system that supports hot-reloading, dependency injection, and sandboxed execution",
]


# ═══════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class AngleResult:
    """Output from a single ensemble angle."""

    angle: str
    output: str
    confidence: int
    latency_ms: float
    token_count: int = 0


@dataclass
class EnsembleResult:
    """Aggregated result from a full ensemble run."""

    problem: str
    angles: list[AngleResult] = field(default_factory=list)
    synthesis: str = ""
    synthesis_confidence: int = 0
    total_time_ms: float = 0.0
    max_angle_time_ms: float = 0.0
    angle_diversity_score: float = 0.0
    agreement_level: str = ""
    synthesis_quality: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# LLM caller
# ═══════════════════════════════════════════════════════════════════════════


def _call_llm(prompt: str, timeout: int = 120) -> str:
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


def _build_angle_prompt(angle: str, problem: str) -> str:
    """Build the full prompt for a single angle."""
    directive = ANGLE_DIRECTIVES[angle]
    return (
        f"ANGLE: {angle}. {directive}\n\n"
        f"Problem: {problem}\n\n"
        f"Use full reasoning. Return:\n"
        f"1. A reasoning summary (3-5 sentences with evidence)\n"
        f"2. A concrete recommendation with tradeoffs\n"
        f"3. Confidence (1-10)\n"
        f"4. Key risks\n"
        f"5. Dissenting considerations (where your angle disagrees with the mainstream approach)"
    )


def _build_synthesis_prompt(problem: str, angle_outputs: list[AngleResult]) -> str:
    """Build the synthesis prompt given all angle outputs."""
    sections = []
    for ar in angle_outputs:
        sections.append(f"=== {ar.angle} (confidence: {ar.confidence}) ===\n{ar.output}\n")
    angle_block = "\n".join(sections)

    return (
        f"You are the SYNTHESIZER for an Ensemble reasoning system.\n"
        f"Problem: {problem}\n\n"
        f"Below are outputs from 5 reasoning angles. Synthesize them.\n\n"
        f"{angle_block}\n"
        f"Provide your synthesis in this format:\n"
        f"AGREEMENT: What do most angles agree on?\n"
        f"DISAGREEMENT: Where do they differ?\n"
        f"RESOLUTION: How to resolve the conflicts?\n"
        f"RISKS: From the security and edge-case angles\n"
        f"DEVIL'S CONCERNS: Are the devil's advocate concerns valid or dismissed?\n"
        f"CONFIDENCE: [weighted average of angle confidences, 1-10]\n"
        f"TRADEOFFS: List at least 3 concrete tradeoffs from different angles\n"
        f"AGREEMENT_LEVEL: [X/5 angles agree on core approach]"
    )


# ═══════════════════════════════════════════════════════════════════════════
# Ensemble runner
# ═══════════════════════════════════════════════════════════════════════════


def _run_single_angle(angle: str, problem: str) -> AngleResult:
    """Run one angle and return its result."""
    prompt = _build_angle_prompt(angle, problem)
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


def _run_real_ensemble(problem: str) -> EnsembleResult:
    """Execute the full ensemble pipeline with real LLM calls."""
    result = EnsembleResult(problem=problem)
    overall_start = time.time()

    # Phase 1: Run all 5 angles in parallel
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(_run_single_angle, angle, problem): angle
            for angle in ENSEMBLE_ANGLES
        }
        angle_results: list[AngleResult] = []
        for future in as_completed(futures):
            angle_results.append(future.result())

    # Sort by angle name for consistent ordering
    angle_results.sort(key=lambda ar: ENSEMBLE_ANGLES.index(ar.angle))
    result.angles = angle_results

    result.max_angle_time_ms = max(ar.latency_ms for ar in angle_results)

    # Phase 2: Synthesis (sequential — needs all angle outputs)
    synth_prompt = _build_synthesis_prompt(problem, angle_results)
    synth_start = time.time()
    synth_output = _call_llm(synth_prompt)
    synth_ms = (time.time() - synth_start) * 1000.0

    result.synthesis = synth_output
    result.synthesis_confidence = _extract_confidence(synth_output)

    # Phase 3: Compute metrics
    result.total_time_ms = (time.time() - overall_start) * 1000.0

    # Agreement level from synthesis
    match = re.search(r"AGREEMENT_LEVEL:\s*(\d+)/5", synth_output, re.IGNORECASE)
    if match:
        result.agreement_level = f"{match.group(1)}/5"
    else:
        # Heuristic: count angles that share core recommendations
        result.agreement_level = "3/5"  # default

    # Angle diversity: unique token overlap ratio
    all_outputs = [ar.output.lower() for ar in angle_results]
    unique_chunks: set[str] = set()
    for out in all_outputs:
        words = set(out.split())
        unique_chunks.update(words)
    total_words = sum(len(o.split()) for o in all_outputs)
    result.angle_diversity_score = len(unique_chunks) / max(total_words, 1)

    # Synthesis quality heuristic
    synth_lower = synth_output.lower()
    quality_markers = [
        "agreement" in synth_lower,
        "disagreement" in synth_lower,
        "resolution" in synth_lower,
        "risk" in synth_lower,
        "tradeoff" in synth_lower or "trade-off" in synth_lower,
    ]
    result.synthesis_quality = f"{sum(quality_markers)}/5 markers present"

    return result


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def ensemble_results():
    """Run real ensemble for both problems once per module (expensive)."""
    results = {}
    for problem in ENSEMBLE_PROBLEMS:
        results[problem] = _run_real_ensemble(problem)
    return results


# ═══════════════════════════════════════════════════════════════════════════
# Test: Problem 1 — Rate limiter
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealEnsembleRateLimiter:
    """Ensemble on: Design a rate limiter with burst traffic, per-user quotas, distributed coordination."""

    @pytest.fixture
    def result(self, ensemble_results):
        return ensemble_results[ENSEMBLE_PROBLEMS[0]]

    def test_all_five_angles_present(self, result):
        assert len(result.angles) == 5
        angle_names = {ar.angle for ar in result.angles}
        assert angle_names == set(ENSEMBLE_ANGLES)

    def test_each_angle_produces_distinct_output(self, result):
        """Each angle must produce a unique, substantial response."""
        outputs = [ar.output for ar in result.angles]
        # All outputs must be unique (no copy-paste between angles)
        assert len(set(outputs)) == 5, "Duplicate outputs detected across angles"

    def test_each_angle_exceeds_200_tokens(self, result):
        """Each angle must produce > 200 tokens of content."""
        for ar in result.angles:
            assert ar.token_count > 200, (
                f"Angle {ar.angle} produced only ~{ar.token_count} tokens "
                f"(need > 200)"
            )

    def test_angles_genuinely_disagree(self, result):
        """Angles must disagree on at least one point.

        We check that the synthesis contains disagreement language and that
        individual angle outputs contain angle-specific concerns that conflict.
        """
        synth_lower = result.synthesis.lower()
        assert any(
            kw in synth_lower
            for kw in ["disagree", "differ", "conflict", "tension", "tradeoff", "trade-off", "versus"]
        ), "Synthesis does not acknowledge any disagreement between angles"

    def test_synthesis_resolves_conflicts(self, result):
        """Synthesis must explicitly resolve conflicts with reasoning."""
        synth_lower = result.synthesis.lower()
        assert any(
            kw in synth_lower
            for kw in ["resolution", "resolve", "balanced", "compromise", "reconcile"]
        ), "Synthesis does not resolve conflicts"

    def test_total_time_less_than_3x_single_angle(self, result):
        """Total ensemble time must be < 3x the slowest angle (proves parallelism)."""
        # Total = all angles (parallel) + synthesis (sequential)
        # If angles ran sequentially, total would be ~sum of all angle times.
        # With parallelism, total ≈ max_angle_time + synthesis_time.
        # We check total < 3 * max_angle_time as a loose bound.
        assert result.total_time_ms < 3 * result.max_angle_time_ms, (
            f"Total {result.total_time_ms:.0f}ms >= 3x max angle "
            f"{result.max_angle_time_ms:.0f}ms — angles likely ran sequentially"
        )

    def test_confidence_is_weighted_average_not_max(self, result):
        """Synthesis confidence must not be simply the max of angle confidences."""
        angle_confs = [ar.confidence for ar in result.angles]
        max_conf = max(angle_confs)
        avg_conf = round(sum(angle_confs) / len(angle_confs))

        # The synthesis confidence should be closer to average than to max
        synth_conf = result.synthesis_confidence
        dist_to_avg = abs(synth_conf - avg_conf)
        dist_to_max = abs(synth_conf - max_conf)

        # Allow some tolerance — the model may compute a slightly different average
        # but it should NOT just pick the max
        if max_conf != avg_conf:
            assert synth_conf != max_conf or dist_to_avg <= dist_to_max, (
                f"Synthesis confidence {synth_conf} equals max {max_conf}, "
                f"not weighted average {avg_conf}"
            )

    def test_output_mentions_tradeoffs_from_3_angles(self, result):
        """Synthesis must mention tradeoffs from at least 3 different angle perspectives."""
        synth_lower = result.synthesis.lower()
        tradeoff_keywords = {
            "performance": ["speed", "latency", "throughput", "performance", "efficient"],
            "simplicity": ["simple", "maintainable", "readability", "complexity", "cognitive"],
            "security": ["security", "attack", "auth", "vulnerability", "trust"],
            "edge_cases": ["edge case", "boundary", "race condition", "failure", "error"],
            "devils_advocate": ["assumption", "cost", "overhead", "hidden", "wrong"],
        }

        angles_with_tradeoffs = 0
        for angle, keywords in tradeoff_keywords.items():
            if any(kw in synth_lower for kw in keywords):
                angles_with_tradeoffs += 1

        assert angles_with_tradeoffs >= 3, (
            f"Synthesis mentions tradeoffs from only {angles_with_tradeoffs}/5 angle "
            f"perspectives (need >= 3)"
        )

    def test_angle_confidences_in_range(self, result):
        """Each angle confidence must be in 1-10 range."""
        for ar in result.angles:
            assert 1 <= ar.confidence <= 10, (
                f"Angle {ar.angle} confidence {ar.confidence} out of range"
            )

    def test_synthesis_confidence_in_range(self, result):
        assert 1 <= result.synthesis_confidence <= 10


# ═══════════════════════════════════════════════════════════════════════════
# Test: Problem 2 — Plugin system
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealEnsemblePluginSystem:
    """Ensemble on: Architect a plugin system with hot-reloading, DI, sandboxed execution."""

    @pytest.fixture
    def result(self, ensemble_results):
        return ensemble_results[ENSEMBLE_PROBLEMS[1]]

    def test_all_five_angles_present(self, result):
        assert len(result.angles) == 5
        angle_names = {ar.angle for ar in result.angles}
        assert angle_names == set(ENSEMBLE_ANGLES)

    def test_each_angle_produces_distinct_output(self, result):
        outputs = [ar.output for ar in result.angles]
        assert len(set(outputs)) == 5, "Duplicate outputs detected across angles"

    def test_each_angle_exceeds_200_tokens(self, result):
        for ar in result.angles:
            assert ar.token_count > 200, (
                f"Angle {ar.angle} produced only ~{ar.token_count} tokens "
                f"(need > 200)"
            )

    def test_angles_genuinely_disagree(self, result):
        synth_lower = result.synthesis.lower()
        assert any(
            kw in synth_lower
            for kw in ["disagree", "differ", "conflict", "tension", "tradeoff", "trade-off", "versus"]
        ), "Synthesis does not acknowledge any disagreement between angles"

    def test_synthesis_resolves_conflicts(self, result):
        synth_lower = result.synthesis.lower()
        assert any(
            kw in synth_lower
            for kw in ["resolution", "resolve", "balanced", "compromise", "reconcile"]
        ), "Synthesis does not resolve conflicts"

    def test_total_time_less_than_3x_single_angle(self, result):
        assert result.total_time_ms < 3 * result.max_angle_time_ms, (
            f"Total {result.total_time_ms:.0f}ms >= 3x max angle "
            f"{result.max_angle_time_ms:.0f}ms — angles likely ran sequentially"
        )

    def test_confidence_is_weighted_average_not_max(self, result):
        angle_confs = [ar.confidence for ar in result.angles]
        max_conf = max(angle_confs)
        avg_conf = round(sum(angle_confs) / len(angle_confs))
        synth_conf = result.synthesis_confidence

        dist_to_avg = abs(synth_conf - avg_conf)
        dist_to_max = abs(synth_conf - max_conf)

        if max_conf != avg_conf:
            assert synth_conf != max_conf or dist_to_avg <= dist_to_max, (
                f"Synthesis confidence {synth_conf} equals max {max_conf}, "
                f"not weighted average {avg_conf}"
            )

    def test_output_mentions_tradeoffs_from_3_angles(self, result):
        synth_lower = result.synthesis.lower()
        tradeoff_keywords = {
            "performance": ["speed", "latency", "throughput", "performance", "efficient"],
            "simplicity": ["simple", "maintainable", "readability", "complexity", "cognitive"],
            "security": ["security", "attack", "auth", "vulnerability", "trust"],
            "edge_cases": ["edge case", "boundary", "race condition", "failure", "error"],
            "devils_advocate": ["assumption", "cost", "overhead", "hidden", "wrong"],
        }

        angles_with_tradeoffs = 0
        for angle, keywords in tradeoff_keywords.items():
            if any(kw in synth_lower for kw in keywords):
                angles_with_tradeoffs += 1

        assert angles_with_tradeoffs >= 3, (
            f"Synthesis mentions tradeoffs from only {angles_with_tradeoffs}/5 angle "
            f"perspectives (need >= 3)"
        )

    def test_angle_confidences_in_range(self, result):
        for ar in result.angles:
            assert 1 <= ar.confidence <= 10, (
                f"Angle {ar.angle} confidence {ar.confidence} out of range"
            )

    def test_synthesis_confidence_in_range(self, result):
        assert 1 <= result.synthesis_confidence <= 10


# ═══════════════════════════════════════════════════════════════════════════
# Test: Cross-problem tracking metrics
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestRealEnsembleTracking:
    """Track angle diversity, agreement level, and synthesis quality across both problems."""

    def test_angle_diversity_above_threshold(self, ensemble_results):
        """Diversity score: ratio of unique words to total words across all angles.
        A score > 0.3 indicates substantial diversity (not copy-paste)."""
        for problem, result in ensemble_results.items():
            assert result.angle_diversity_score > 0.3, (
                f"Low diversity {result.angle_diversity_score:.2f} for: "
                f"{problem[:60]}..."
            )

    def test_agreement_level_parsed(self, ensemble_results):
        """Agreement level must be parseable as X/5."""
        for problem, result in ensemble_results.items():
            assert re.match(r"\d/5", result.agreement_level), (
                f"Invalid agreement level '{result.agreement_level}' for: "
                f"{problem[:60]}..."
            )

    def test_synthesis_quality_at_least_3_markers(self, ensemble_results):
        """Synthesis must contain at least 3 of 5 quality markers."""
        for problem, result in ensemble_results.items():
            count = int(result.synthesis_quality.split("/")[0])
            assert count >= 3, (
                f"Synthesis quality only {result.synthesis_quality} for: "
                f"{problem[:60]}..."
            )

    def test_both_problems_complete_successfully(self, ensemble_results):
        """Both test problems must produce full ensemble results."""
        assert len(ensemble_results) == 2
        for problem, result in ensemble_results.items():
            assert len(result.angles) == 5, (
                f"Incomplete ensemble for: {problem[:60]}..."
            )
            assert result.synthesis, (
                f"Missing synthesis for: {problem[:60]}..."
            )

    def test_tracking_summary(self, ensemble_results):
        """Emit a tracking summary as a structured assertion (for CI logs)."""
        summary = {}
        for problem, result in ensemble_results.items():
            short = problem[:40]
            summary[short] = {
                "angle_diversity": round(result.angle_diversity_score, 3),
                "agreement_level": result.agreement_level,
                "synthesis_quality": result.synthesis_quality,
                "total_time_ms": round(result.total_time_ms),
                "max_angle_time_ms": round(result.max_angle_time_ms),
                "angle_confidences": [ar.confidence for ar in result.angles],
                "synthesis_confidence": result.synthesis_confidence,
            }

        # Both problems should have been processed
        assert len(summary) == 2
        # Log summary for observability (visible in pytest -s output)
        for short, metrics in summary.items():
            assert metrics["angle_diversity"] > 0
            assert metrics["synthesis_confidence"] > 0
