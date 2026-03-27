"""Real agent tests for Deep Think mode — runs all 11 checkpoints against live LLM.

Requires:
    pip install openai
    export REASONING_API_KEY=<your-api-key>
    export REASONING_MODEL=<model-name>          # default: gpt-4o
    export REASONING_BASE_URL=<api-base-url>     # default: https://api.openai.com/v1

Run:
    pytest tests/test_real_deep_think.py -v -m real_agent
    python -m cli.batch_test --suite real-agent
"""

from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

# ── Path bootstrap (project convention) ──────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoring.confidence_calibration import (
    CalibrationResult,
    ConfidenceCalibrator,
    ProblemResult,
)

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

DEEP_THINK_TECHNIQUES = [
    ("META-COGNITION", "[CHECKPOINT 1]"),
    ("STEP-BACK", "[CHECKPOINT 2]"),
    ("DECOMPOSITION", "[CHECKPOINT 3]"),
    ("TREE OF THOUGHT", "[CHECKPOINT 4]"),
    ("FIRST PRINCIPLES", "[CHECKPOINT 5]"),
    ("ANALOGICAL REASONING", "[CHECKPOINT 6]"),
    ("CHAIN OF THOUGHT", "[CHECKPOINT 7]"),
    ("DEVIL'S ADVOCATE", "[CHECKPOINT 8]"),
    ("INVERSION / PRE-MORTEM", "[CHECKPOINT 9]"),
    ("RAVEN LOOP", "[CHECKPOINT 10]"),
    ("RECURSIVE SELF-IMPROVEMENT", "[CHECKPOINT 11]"),
]

PROBLEMS = [
    "Refactor the database connection module to use connection pooling",
    "Add retry logic with exponential backoff to the API client",
    "Convert the monolithic config parser into separate validator and loader classes",
]

MAX_LATENCY_S = 120
MIN_FIELD_CHARS = 50

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


# ═══════════════════════════════════════════════════════════════════════════
# LLM client (OpenAI-compatible)
# ═══════════════════════════════════════════════════════════════════════════


def _get_client():
    """Lazily import openai and construct a client from env vars."""
    try:
        from openai import OpenAI
    except ImportError:
        pytest.skip("openai package not installed — pip install openai")

    api_key = os.environ.get("REASONING_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip(
            "REASONING_API_KEY or OPENAI_API_KEY not set — skipping real agent test"
        )

    base_url = os.environ.get("REASONING_BASE_URL", "https://api.openai.com/v1")
    return OpenAI(api_key=api_key, base_url=base_url)


def _get_model() -> str:
    return os.environ.get("REASONING_MODEL", "gpt-4o")


def _load_deepthink_prompt() -> str:
    skill_path = _SKILLS_DIR / "deepthink-SKILL.md"
    if skill_path.exists():
        return skill_path.read_text()
    # Fallback: inline the checkpoint structure
    return (
        "Follow the DEEPTHINK protocol. Complete ALL 11 checkpoints in order:\n"
        + "\n".join(f"{marker} — {name}" for name, marker in DEEP_THINK_TECHNIQUES)
    )


def _call_deep_think(problem: str) -> tuple[str, float]:
    """Call the LLM with the Deep Think protocol. Returns (output, latency_s)."""
    client = _get_client()
    model = _get_model()
    skill_prompt = _load_deepthink_prompt()

    system_msg = (
        "You are a reasoning agent. You MUST follow the DEEPTHINK protocol exactly. "
        "Complete every checkpoint. Use the box-drawing templates provided. "
        "Do NOT skip any checkpoint. After all 11 checkpoints, write:\n"
        "🧠 DEEPTHINK COMPLETE\n"
        "Checkpoints Hit: 11/11\n"
        "Confidence: <1-10>\n"
    )

    user_msg = (
        f"{skill_prompt}\n\n"
        f"---\n\n"
        f"TASK: {problem}\n\n"
        f"Begin DEEPTHINK now."
    )

    start = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=8192,
    )
    latency = time.time() - start

    output = response.choices[0].message.content or ""
    return output, latency


# ═══════════════════════════════════════════════════════════════════════════
# Parsed output structures
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class CheckpointResult:
    """Parsed result for a single Deep Think checkpoint."""

    name: str
    marker: str
    present: bool = False
    content: str = ""
    field_texts: list[str] = field(default_factory=list)
    min_field_chars_met: bool = False


@dataclass
class DeepThinkResult:
    """Full parsed result of a Deep Think execution."""

    problem: str
    raw_output: str
    latency_s: float
    checkpoints: list[CheckpointResult] = field(default_factory=list)
    confidence: Optional[int] = None

    @property
    def checkpoints_present(self) -> int:
        return sum(1 for c in self.checkpoints if c.present)

    @property
    def technique_coverage_pct(self) -> float:
        return (self.checkpoints_present / 11) * 100.0

    @property
    def all_checkpoints_present(self) -> bool:
        return self.checkpoints_present == 11

    @property
    def substantive_content(self) -> bool:
        return all(c.min_field_chars_met for c in self.checkpoints if c.present)


# ═══════════════════════════════════════════════════════════════════════════
# Parsing
# ═══════════════════════════════════════════════════════════════════════════


def _extract_box_content(output: str, checkpoint_marker: str) -> str:
    """Extract the content between ┌─ and └─── boxes surrounding a checkpoint."""
    # Find the box that contains this checkpoint marker
    pattern = r"┌[─-].*?┐(.*?)└[─-]+┘"
    boxes = re.findall(pattern, output, re.DOTALL)
    for box_content in boxes:
        if checkpoint_marker in box_content:
            return box_content.strip()

    # Fallback: find lines around the marker
    lines = output.split("\n")
    for i, line in enumerate(lines):
        if checkpoint_marker in line:
            start = max(0, i - 15)
            end = min(len(lines), i + 3)
            return "\n".join(lines[start:end])
    return ""


def _extract_field_texts(content: str) -> list[str]:
    """Extract field values from box content (lines starting with │)."""
    texts = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("│"):
            field_text = stripped.lstrip("│").strip()
            # Skip lines that are just the checkpoint marker
            if field_text and not re.match(r"\[CHECKPOINT \d+\]", field_text):
                texts.append(field_text)
    return texts


def _extract_confidence(output: str) -> Optional[int]:
    """Extract final confidence from DEEPTHINK COMPLETE summary."""
    match = re.search(r"[Cc]onfidence[:\s]*(\d+)", output)
    if match:
        val = int(match.group(1))
        if 1 <= val <= 10:
            return val
    return None


def _count_branches(content: str) -> int:
    """Count BRANCH entries in Tree of Thought."""
    return len(re.findall(r"BRANCH\s+[A-Z]", content, re.IGNORECASE))


def _count_verdicts(content: str, verdict: str) -> int:
    """Count PURSUE or PRUNE verdicts."""
    return len(re.findall(rf"\b{verdict}\b", content, re.IGNORECASE))


def _count_attacks(content: str) -> int:
    """Count ATTACK entries in Devil's Advocate."""
    return len(re.findall(r"ATTACK\s+\d+", content, re.IGNORECASE))


def _count_defenses(content: str) -> int:
    """Count Defense entries in Devil's Advocate."""
    return len(re.findall(r"[Dd]efense:", content))


def _count_failure_modes(content: str) -> int:
    """Count failure mode entries in Inversion / Pre-Mortem."""
    # Lines matching "N. [description] → Prevention: [how]"
    return len(re.findall(r"\d+\.\s+.+?→\s*Prevention:", content, re.IGNORECASE))


def _count_preventions(content: str) -> int:
    """Count Prevention entries in Inversion."""
    return len(re.findall(r"Prevention:", content, re.IGNORECASE))


def parse_deep_think_output(
    problem: str, raw_output: str, latency_s: float
) -> DeepThinkResult:
    """Parse raw LLM output into a structured DeepThinkResult."""
    result = DeepThinkResult(
        problem=problem,
        raw_output=raw_output,
        latency_s=latency_s,
    )

    for name, marker in DEEP_THINK_TECHNIQUES:
        cp = CheckpointResult(name=name, marker=marker)
        content = _extract_box_content(raw_output, marker)
        cp.present = bool(content) and marker in raw_output
        cp.content = content
        cp.field_texts = _extract_field_texts(content)
        cp.min_field_chars_met = all(
            len(ft) >= MIN_FIELD_CHARS for ft in cp.field_texts
        ) if cp.field_texts else False
        result.checkpoints.append(cp)

    result.confidence = _extract_confidence(raw_output)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Depth score computation
# ═══════════════════════════════════════════════════════════════════════════


def compute_depth_score(parsed: DeepThinkResult) -> float:
    """Compute a 0-100 depth score based on checkpoint quality.

    Weights:
        - Checkpoint presence:         33 pts (3 per checkpoint × 11)
        - Substantive content:         22 pts (2 per checkpoint × 11)
        - Tree of Thought branches:    15 pts
        - Devil's Advocate attacks:    15 pts
        - Inversion failure modes:     15 pts
    """
    score = 0.0

    # Checkpoint presence
    score += parsed.checkpoints_present * 3.0

    # Substantive content
    for cp in parsed.checkpoints:
        if cp.present and cp.min_field_chars_met:
            score += 2.0

    # Tree of Thought quality
    tot = next(
        (c for c in parsed.checkpoints if c.name == "TREE OF THOUGHT"), None
    )
    if tot and tot.present:
        branches = _count_branches(tot.content)
        pursue = _count_verdicts(tot.content, "PURSUE")
        prune = _count_verdicts(tot.content, "PRUNE")
        if branches >= 3:
            score += 5.0
        if pursue + prune >= 3:
            score += 5.0
        if pursue >= 1 and prune >= 1:
            score += 5.0

    # Devil's Advocate quality
    da = next(
        (c for c in parsed.checkpoints if c.name == "DEVIL'S ADVOCATE"), None
    )
    if da and da.present:
        attacks = _count_attacks(da.content)
        defenses = _count_defenses(da.content)
        if attacks >= 3:
            score += 7.5
        if defenses >= 3:
            score += 7.5

    # Inversion quality
    inv = next(
        (c for c in parsed.checkpoints if "INVERSION" in c.name), None
    )
    if inv and inv.present:
        failure_modes = _count_failure_modes(inv.content)
        preventions = _count_preventions(inv.content)
        if failure_modes >= 3:
            score += 7.5
        if preventions >= 3:
            score += 7.5

    return min(100.0, score)


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.real_agent
class TestDeepThinkRealAgent:
    """Run Deep Think mode with real LLM calls and validate all 11 checkpoints."""

    @pytest.fixture(scope="class")
    def deep_think_results(self) -> list[DeepThinkResult]:
        """Execute Deep Think for all 3 problems (cached per class)."""
        results: list[DeepThinkResult] = []
        for problem in PROBLEMS:
            raw, latency = _call_deep_think(problem)
            parsed = parse_deep_think_output(problem, raw, latency)
            results.append(parsed)
        return results

    # ── Timing ────────────────────────────────────────────────────────────

    @pytest.mark.parametrize("problem_idx", range(3), ids=[p[:30] for p in PROBLEMS])
    def test_completes_within_timeout(self, deep_think_results, problem_idx):
        """Agent completes in < 120 seconds."""
        result = deep_think_results[problem_idx]
        assert result.latency_s < MAX_LATENCY_S, (
            f"Problem '{result.problem[:50]}...' took {result.latency_s:.1f}s "
            f"(limit: {MAX_LATENCY_S}s)"
        )

    # ── Checkpoint presence ───────────────────────────────────────────────

    @pytest.mark.parametrize("problem_idx", range(3), ids=[p[:30] for p in PROBLEMS])
    def test_all_11_checkpoints_present(self, deep_think_results, problem_idx):
        """All 11 checkpoints present in output."""
        result = deep_think_results[problem_idx]
        missing = [
            cp.name for cp in result.checkpoints if not cp.present
        ]
        assert result.all_checkpoints_present, (
            f"Missing checkpoints for '{result.problem[:40]}...': {missing}"
        )

    @pytest.mark.parametrize(
        "cp_idx,cp_name",
        enumerate(n for n, _ in DEEP_THINK_TECHNIQUES),
        ids=[n for n, _ in DEEP_THINK_TECHNIQUES],
    )
    def test_checkpoint_present_across_problems(self, deep_think_results, cp_idx, cp_name):
        """Each checkpoint is present across all 3 problems."""
        for result in deep_think_results:
            cp = result.checkpoints[cp_idx]
            assert cp.present, (
                f"{cp_name} missing in '{result.problem[:40]}...'"
            )

    # ── Substantive content ───────────────────────────────────────────────

    @pytest.mark.parametrize("problem_idx", range(3), ids=[p[:30] for p in PROBLEMS])
    def test_substantive_content_per_checkpoint(self, deep_think_results, problem_idx):
        """Each checkpoint has substantive content (>50 chars per field)."""
        result = deep_think_results[problem_idx]
        failures = []
        for cp in result.checkpoints:
            if cp.present and not cp.min_field_chars_met:
                short_fields = [
                    ft for ft in cp.field_texts if len(ft) < MIN_FIELD_CHARS
                ]
                failures.append(
                    f"  {cp.name}: {len(short_fields)} fields < {MIN_FIELD_CHARS} chars"
                )
        assert not failures, (
            f"Insufficient content for '{result.problem[:40]}...':\n"
            + "\n".join(failures)
        )

    # ── Confidence calibration ────────────────────────────────────────────

    @pytest.mark.parametrize("problem_idx", range(3), ids=[p[:30] for p in PROBLEMS])
    def test_confidence_calibrated(self, deep_think_results, problem_idx):
        """Confidence is calibrated (not 10 without mathematical proof)."""
        result = deep_think_results[problem_idx]
        if result.confidence is None:
            pytest.fail("Could not extract confidence from output")

        if result.confidence == 10:
            has_proof = bool(
                re.search(
                    r"(proof|QED|theorem|mathematical|formal verification|proved)",
                    result.raw_output,
                    re.IGNORECASE,
                )
            )
            assert has_proof, (
                f"Confidence 10/10 without mathematical proof "
                f"for '{result.problem[:40]}...'"
            )

        assert 1 <= result.confidence <= 10, (
            f"Confidence {result.confidence} out of range for "
            f"'{result.problem[:40]}...'"
        )

    # ── Tree of Thought ───────────────────────────────────────────────────

    @pytest.mark.parametrize("problem_idx", range(3), ids=[p[:30] for p in PROBLEMS])
    def test_tree_of_thought_branches(self, deep_think_results, problem_idx):
        """Tree of Thought has 3+ branches with PURSUE/PRUNE verdicts."""
        result = deep_think_results[problem_idx]
        tot = next(
            (c for c in result.checkpoints if c.name == "TREE OF THOUGHT"), None
        )
        assert tot is not None and tot.present, "Tree of Thought checkpoint missing"

        branches = _count_branches(tot.content)
        pursue = _count_verdicts(tot.content, "PURSUE")
        prune = _count_verdicts(tot.content, "PRUNE")

        assert branches >= 3, (
            f"Tree of Thought has {branches} branches (need >= 3) "
            f"for '{result.problem[:40]}...'"
        )
        assert pursue + prune >= 3, (
            f"Tree of Thought has {pursue + prune} verdicts (need >= 3) "
            f"for '{result.problem[:40]}...'"
        )

    # ── Devil's Advocate ──────────────────────────────────────────────────

    @pytest.mark.parametrize("problem_idx", range(3), ids=[p[:30] for p in PROBLEMS])
    def test_devils_advocate_attacks(self, deep_think_results, problem_idx):
        """Devil's Advocate has 3+ attacks with defenses."""
        result = deep_think_results[problem_idx]
        da = next(
            (c for c in result.checkpoints if c.name == "DEVIL'S ADVOCATE"), None
        )
        assert da is not None and da.present, "Devil's Advocate checkpoint missing"

        attacks = _count_attacks(da.content)
        defenses = _count_defenses(da.content)

        assert attacks >= 3, (
            f"Devil's Advocate has {attacks} attacks (need >= 3) "
            f"for '{result.problem[:40]}...'"
        )
        assert defenses >= 3, (
            f"Devil's Advocate has {defenses} defenses (need >= 3) "
            f"for '{result.problem[:40]}...'"
        )

    # ── Inversion / Pre-Mortem ────────────────────────────────────────────

    @pytest.mark.parametrize("problem_idx", range(3), ids=[p[:30] for p in PROBLEMS])
    def test_inversion_failure_modes(self, deep_think_results, problem_idx):
        """Inversion lists 3+ failure modes with preventions."""
        result = deep_think_results[problem_idx]
        inv = next(
            (c for c in result.checkpoints if "INVERSION" in c.name), None
        )
        assert inv is not None and inv.present, "Inversion checkpoint missing"

        failure_modes = _count_failure_modes(inv.content)
        preventions = _count_preventions(inv.content)

        assert failure_modes >= 3, (
            f"Inversion has {failure_modes} failure modes (need >= 3) "
            f"for '{result.problem[:40]}...'"
        )
        assert preventions >= 3, (
            f"Inversion has {preventions} preventions (need >= 3) "
            f"for '{result.problem[:40]}...'"
        )

    # ── Tracking metrics ──────────────────────────────────────────────────

    def test_technique_coverage_tracked(self, deep_think_results):
        """Track technique coverage % across all problems."""
        for result in deep_think_results:
            coverage = result.technique_coverage_pct
            assert coverage == 100.0, (
                f"Technique coverage {coverage:.0f}% for "
                f"'{result.problem[:40]}...' (need 100%)"
            )

    def test_confidence_calibration_tracked(self, deep_think_results):
        """Track confidence calibration using ConfidenceCalibrator."""
        calibrator = ConfidenceCalibrator(num_bins=5, target_ece=0.3)

        problem_results = []
        for result in deep_think_results:
            # Treat presence of all checkpoints as "correct" for calibration
            correct = result.all_checkpoints_present
            # Normalize confidence from 1-10 scale to 0-1 scale
            conf_normalized = (
                result.confidence / 10.0 if result.confidence is not None else 0.5
            )
            problem_results.append(
                ProblemResult(
                    problem_id=result.problem[:40],
                    confidence=conf_normalized,
                    correct=correct,
                    mode="DEEP",
                    difficulty="medium",
                )
            )

        calibration = calibrator.analyze(problem_results)
        # With only 3 samples, ECE is not statistically meaningful,
        # but we verify the calibrator runs without error
        assert calibration.n_samples == 3
        assert isinstance(calibration.ece, float)
        assert 0.0 <= calibration.brier_score <= 1.0

    def test_depth_score_tracked(self, deep_think_results):
        """Track depth score (0-100) for each problem."""
        for result in deep_think_results:
            depth = compute_depth_score(result)
            # Minimum viable depth: all checkpoints present (33) +
            # at least some substantive content
            assert depth >= 33.0, (
                f"Depth score {depth:.1f} too low for "
                f"'{result.problem[:40]}...' (need >= 33)"
            )

    def test_summary_report(self, deep_think_results):
        """Print a summary report of all Deep Think runs."""
        lines = [
            "",
            "=" * 72,
            "DEEP THINK REAL AGENT TEST — SUMMARY REPORT",
            "=" * 72,
        ]

        for result in deep_think_results:
            depth = compute_depth_score(result)
            lines.append(f"\nProblem: {result.problem}")
            lines.append(f"  Latency:     {result.latency_s:.1f}s")
            lines.append(f"  Checkpoints: {result.checkpoints_present}/11")
            lines.append(
                f"  Coverage:    {result.technique_coverage_pct:.0f}%"
            )
            lines.append(
                f"  Confidence:  {result.confidence}/10"
            )
            lines.append(f"  Depth Score: {depth:.1f}/100")
            lines.append(f"  Substantive: {'YES' if result.substantive_content else 'NO'}")

            # Per-checkpoint detail
            for cp in result.checkpoints:
                status = "OK" if cp.present and cp.min_field_chars_met else (
                    "SHALLOW" if cp.present else "MISSING"
                )
                n_fields = len(cp.field_texts)
                lines.append(f"    {cp.name:30s} [{status}] ({n_fields} fields)")

        lines.append("\n" + "=" * 72)

        report = "\n".join(lines)
        print(report)

        # Verify all problems completed successfully
        for result in deep_think_results:
            assert result.all_checkpoints_present
