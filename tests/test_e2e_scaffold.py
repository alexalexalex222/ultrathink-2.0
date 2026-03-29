"""E2E test scaffolding and shared harness for reasoning swarm tests.

Provides ReasoningSwarmHarness (simulates reasoning flow per mode),
ReasoningTrace (structured output capture), and shared test problems
(importable by all subsequent test files).

Usage:
    from tests.test_e2e_scaffold import (
        ReasoningSwarmHarness,
        ReasoningTrace,
        TEST_PROBLEMS,
        LOW_PROBLEMS,
        MEDIUM_PROBLEMS,
        HIGH_PROBLEMS,
        EXTREME_PROBLEMS,
        harness,
    )
"""

from __future__ import annotations

import sys
import os
import time
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pytest

# ── Path bootstrap (matches project convention) ─────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.intake_classifier import classify_task  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ReasoningTrace:
    """Structured representation of a reasoning swarm execution."""

    mode: str  # RAPID / DEEP / ENSEMBLE / MEGA / JURY
    confidence: int  # 1-10
    checkpoints_hit: int
    escalations: int
    techniques_used: list[str] = field(default_factory=list)
    evidence_entries: list[str] = field(default_factory=list)  # GRAND JURY
    subprocess_calls: int = 0
    raw_output: str = ""
    latency_ms: float = 0.0
    # Megamind-specific fields
    iterations: int = 1
    agreement_level: str = ""
    conflicts: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

# 11 Deep Think techniques with their checkpoint markers
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

ENSEMBLE_ANGLES = [
    "PERFORMANCE",
    "SIMPLICITY",
    "SECURITY",
    "EDGE CASES",
    "DEVIL'S ADVOCATE",
]

MEGAMIND_ANGLES = [
    "PERFORMANCE",
    "SIMPLICITY",
    "SECURITY",
    "SCALABILITY",
    "EDGE CASES",
    "DEVIL'S ADVOCATE",
    "BEGINNER'S MIND",
    "FUTURE SELF",
    "USER PERSPECTIVE",
    "CONSTRAINT BREAKER",
]

MEGAMIND_SYNTHESIZERS = ["CONSENSUS", "CONFLICT", "RISK"]

# GRAND JURY phases (GJ-0 through GJ-8)
GRAND_JURY_PHASES = [
    ("GJ-0", "COMMITMENT"),
    ("GJ-1", "SYMPTOM RECORD"),
    ("GJ-2", "ASSUMPTIONS LEDGER"),
    ("GJ-3", "SEARCH PASS"),
    ("GJ-4", "EVIDENCE LEDGER"),
    ("GJ-5", "CHAIN-OF-CUSTODY"),
    ("GJ-6", "MURDER BOARD"),
    ("GJ-7", "PRE-FLIGHT CHECKLIST"),
    ("GJ-8", "ATOMIC CHANGE + VERIFY"),
]

# Mode abbreviation → canonical name used by intake classifier
_MODE_CANONICAL = {
    "RAPID": "RAPID STRIKE",
    "RAPID STRIKE": "RAPID STRIKE",
    "DEEP": "DEEP THINK",
    "DEEP THINK": "DEEP THINK",
    "ENSEMBLE": "ENSEMBLE",
    "MEGA": "MEGAMIND",
    "MEGAMIND": "MEGAMIND",
    "JURY": "GRAND JURY",
    "GRAND JURY": "GRAND JURY",
}

# Abbreviated mode names for ReasoningTrace.mode
_MODE_ABBREV = {
    "RAPID STRIKE": "RAPID",
    "DEEP THINK": "DEEP",
    "ENSEMBLE": "ENSEMBLE",
    "MEGAMIND": "MEGA",
    "GRAND JURY": "JURY",
}

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


# ═══════════════════════════════════════════════════════════════════════════
# Harness
# ═══════════════════════════════════════════════════════════════════════════


class ReasoningSwarmHarness:
    """Simulates the reasoning swarm flow for E2E testing.

    Constructs skill prompts, classifies tasks via the intake classifier,
    and generates structured ReasoningTrace outputs for each mode.
    """

    def __init__(self, task_description: str, mode_override: Optional[str] = None):
        self.task_description = task_description
        self.mode_override = mode_override
        self._skill_content: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────

    def run(self) -> ReasoningTrace:
        """Execute the full reasoning flow and return a ReasoningTrace."""
        start = time.time()
        trace = self._dispatch()
        trace.latency_ms = (time.time() - start) * 1000.0
        return trace

    def load_skill(self) -> str:
        """Load and return the appropriate SKILL.md content."""
        if self._skill_content is None:
            self._skill_content = self._load_skill_file()
        return self._skill_content

    def get_mode(self) -> str:
        """Return the resolved canonical mode name (e.g. 'DEEP THINK')."""
        if self.mode_override:
            return _MODE_CANONICAL[self.mode_override.upper()]
        return classify_task(
            task_type="IMPLEMENTATION",
            complexity="MEDIUM",
            stakes="MEDIUM",
        )

    # ── Skill loading ─────────────────────────────────────────────────────

    def _load_skill_file(self) -> str:
        mode = self.get_mode()
        skill_map = {
            "RAPID STRIKE": "reasoning-swarm-SKILL.md",
            "DEEP THINK": "deepthink-SKILL.md",
            "ENSEMBLE": "reasoning-swarm-SKILL.md",
            "MEGAMIND": "megamind-SKILL.md",
            "GRAND JURY": "diamondthink-SKILL.md",
        }
        filename = skill_map[mode]
        path = _SKILLS_DIR / filename
        if not path.exists():
            path = _SKILLS_DIR / "reasoning-swarm-SKILL.md"
        return path.read_text()

    # ── Dispatch ──────────────────────────────────────────────────────────

    def _dispatch(self) -> ReasoningTrace:
        mode = self.get_mode()
        self.load_skill()
        dispatch = {
            "RAPID STRIKE": self._run_rapid,
            "DEEP THINK": self._run_deep,
            "ENSEMBLE": self._run_ensemble,
            "MEGAMIND": self._run_megamind,
            "GRAND JURY": self._run_jury,
        }
        return dispatch[mode]()

    # ── RAPID STRIKE ──────────────────────────────────────────────────────

    def _run_rapid(self) -> ReasoningTrace:
        task = self.task_description
        sections = [
            f"1. PROBLEM: {task}",
            f"2. OBVIOUS ANSWER: Apply standard pattern for '{task[:50]}...'",
            f"3. SANITY CHECK: Verify assumptions hold for this specific case",
            "4. CONFIDENCE: 8",
        ]
        raw = "\n".join(sections)
        return ReasoningTrace(
            mode="RAPID",
            confidence=8,
            checkpoints_hit=4,
            escalations=0,
            techniques_used=["RAPID STRIKE"],
            raw_output=raw,
        )

    # ── DEEP THINK ────────────────────────────────────────────────────────

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
        summary = (
            f"\n🧠 DEEP THINK COMPLETE\n"
            f"Checkpoints Hit: 11/11\n"
            f"Confidence: {avg_conf}\n"
            f"---\n"
            f"Final answer for: {task}"
        )
        output_parts.append(summary)

        return ReasoningTrace(
            mode="DEEP",
            confidence=avg_conf,
            checkpoints_hit=11,
            escalations=0,
            techniques_used=techniques_used,
            raw_output="\n".join(output_parts),
        )

    # ── ENSEMBLE ──────────────────────────────────────────────────────────

    def _run_ensemble(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        subproc = 0
        confidences: list[int] = []

        for angle in ENSEMBLE_ANGLES:
            content = self._mock_angle_output(angle, task)
            output_parts.append(f"ANGLE: {angle}\n{content}")
            techniques_used.append(f"ENSEMBLE:{angle}")
            confidences.append(self._extract_confidence(content))
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
            escalations=0,
            techniques_used=techniques_used,
            subprocess_calls=subproc,
            raw_output=raw,
        )

    # ── MEGAMIND ──────────────────────────────────────────────────────────

    def _run_megamind(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        subproc = 0
        max_iterations = 3

        # Phase M1 — initial Deep Think pass (runs once)
        output_parts.append("PHASE M1: Initial Deep Think Pass")
        for name, marker in DEEP_THINK_TECHNIQUES:
            output_parts.append(f"  {name}: {marker}")
            techniques_used.append(f"MEGA:M1:{name}")

        # Phases M2 → M3 → M4 iterate up to 3 times
        conf = 0
        all_conflicts: list[str] = []
        all_risks: list[str] = []
        agreement_level = ""
        iteration = 0

        for iteration in range(1, max_iterations + 1):
            # Phase M2 — 10 angle-explorers
            output_parts.append(f"\nPHASE M2: 10 Angle-Explorers (iteration {iteration})")
            angle_confidences: list[int] = []
            for angle in MEGAMIND_ANGLES:
                content = self._mock_angle_output(angle, task)
                output_parts.append(f"  ANGLE: {angle}\n  {content}")
                tech_key = f"MEGA:M2:{angle}"
                if tech_key not in techniques_used:
                    techniques_used.append(tech_key)
                angle_confidences.append(self._angle_confidence(angle))
                subproc += 1

            # Phase M3 — 3 synthesizers (each receives all 10 outputs)
            output_parts.append(f"\nPHASE M3: 3 Synthesizers (iteration {iteration})")
            for synth in MEGAMIND_SYNTHESIZERS:
                output_parts.append(
                    f"  SYNTHESIZER {synth}: Analysis from {synth} perspective "
                    f"(processed {len(MEGAMIND_ANGLES)} angle outputs)"
                )
                tech_key = f"MEGA:M3:{synth}"
                if tech_key not in techniques_used:
                    techniques_used.append(tech_key)
                subproc += 1

            # Phase M4 — final synthesis with confidence gate
            aligned = sum(1 for c in angle_confidences if c >= 7)
            agreement_level = f"{aligned}/10"
            conf = self._complexity_confidence(task)

            conflicts = [
                "Performance vs simplicity tradeoff on caching strategy",
                "Security hardening conflicts with beginner-friendly UX",
                "Scalability requirements exceed current infrastructure assumptions",
            ]
            risks = [
                "Edge case handling under concurrent load",
                "Regression risk in backward compatibility layer",
                "Performance degradation at 10x scale",
            ]
            all_conflicts = conflicts
            all_risks = risks

            output_parts.append(
                f"\nPHASE M4: Final Synthesis (iteration {iteration})\n"
                f"  SYNTH A says: Strong consensus on core approach\n"
                f"  SYNTH B says: Conflicts identified and analyzed\n"
                f"  SYNTH C says: Risks assessed with mitigations\n"
                f"  AGREEMENT LEVEL: {agreement_level} aligned\n"
                f"  CONFLICTS RESOLVED: {'; '.join(all_conflicts)}\n"
                f"  RISKS MITIGATED: {'; '.join(all_risks)}\n"
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
            f"Conflicts Resolved: {'; '.join(all_conflicts)}\n"
            f"Risks Mitigated: {'; '.join(all_risks)}\n"
            f"Final Confidence: {conf}"
        )

        return ReasoningTrace(
            mode="MEGA",
            confidence=conf,
            checkpoints_hit=13,  # 10 angles + 3 synthesizers
            escalations=0,
            techniques_used=techniques_used,
            subprocess_calls=subproc,
            raw_output=raw,
            iterations=iteration,
            agreement_level=agreement_level,
            conflicts=all_conflicts,
            risks=all_risks,
        )

    # ── GRAND JURY ────────────────────────────────────────────────────────

    def _run_jury(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        evidence: list[str] = []

        for phase_id, phase_name in GRAND_JURY_PHASES:
            content = self._mock_jury_phase(phase_id, phase_name, task)
            section = f"┌─ {phase_name} ({phase_id}) ──────────────────\n"
            section += f"│ {content}\n"
            section += "└" + "─" * 50 + "┘"
            output_parts.append(section)
            techniques_used.append(f"JURY:{phase_id}")

            if phase_id == "GJ-4":
                evidence.extend([
                    "E1: main.py:L42 — verbatim excerpt of error handler",
                    "E2: config.py:L15 — verbatim excerpt of config loading",
                    "E3: test_output — raw command output from failing test",
                ])

        conf = self._complexity_confidence(task)

        raw = "\n".join(output_parts)
        raw += (
            f"\n\n⚖️ GRAND JURY COMPLETE\n"
            f"Evidence Entries: {len(evidence)}\n"
            f"Hypotheses Tested: 4\n"
            f"Root Cause: Identified via evidence chain\n"
            f"Fix: Atomic change applied\n"
            f"Verification: PASS"
        )

        return ReasoningTrace(
            mode="JURY",
            confidence=conf,
            checkpoints_hit=9,  # GJ-0 through GJ-8
            escalations=0,
            techniques_used=techniques_used,
            evidence_entries=evidence,
            raw_output=raw,
        )

    # ── Mock output generators ────────────────────────────────────────────

    def _mock_technique_output(self, technique: str, task: str) -> str:
        """Generate deterministic mock content for a Deep Think technique."""
        mocks = {
            "META-COGNITION": (
                f"Problem type: Implementation task. "
                f"Confidence (1-10): 7. "
                f"Uncertainties: scope boundary for '{task[:40]}'. "
                f"Am I rushing: No. "
                f"Missing perspective: integration testing impact."
            ),
            "STEP-BACK": (
                f"Literal request: {task}. "
                f"What user ACTUALLY wants: reliable, maintainable solution. "
                f"WHY: reduce future debugging time. "
                f"What I should do: implement with proper error handling."
            ),
            "DECOMPOSITION": (
                f"MAIN PROBLEM: {task}. "
                f"SUB-PROBLEMS: 1. Analyze current state → 1.1 Identify entry points. "
                f"2. Design change → 2.1 Define interface. "
                f"3. Implement → 3.1 Add tests. "
                f"DEPENDENCIES: 1 before 2, 2 before 3."
            ),
            "TREE OF THOUGHT": (
                "BRANCH A: Minimal change approach. "
                "Pros: low risk | Cons: limited improvement | Verdict: PURSUE. "
                "BRANCH B: Full refactor approach. "
                "Pros: thorough | Cons: high risk | Verdict: PRUNE. "
                "BRANCH C: Incremental approach. "
                "Pros: balanced | Cons: slower | Verdict: PURSUE. "
                "SELECTED: Branch C — balanced risk/reward."
            ),
            "FIRST PRINCIPLES": (
                "Assumptions: "
                "1. Current architecture supports change → convention → true. "
                "2. No external API constraints → needs verification. "
                "3. Test coverage is adequate → false — gaps exist. "
                "FUNDAMENTALLY REQUIRED: correct data flow and error handling."
            ),
            "ANALOGICAL REASONING": (
                "Abstract pattern: incremental module improvement. "
                "Similar solved problems: "
                "1. Config refactor → solution: adapter pattern. "
                "2. API versioning → solution: strategy pattern. "
                "What transfers: adapter pattern applies. What doesn't: versioning."
            ),
            "CHAIN OF THOUGHT": (
                "Step 1: Analyze current implementation — Why: understand baseline. "
                "Step 2: Design target state — Why: define success criteria. "
                "Step 3: Plan migration path — Why: minimize disruption. "
                "Conclusion: proceed with incremental approach."
            ),
            "DEVIL'S ADVOCATE": (
                "My solution: incremental approach with adapter pattern. "
                'ATTACK 1: "Too slow" → Defense: reliability over speed. '
                'ATTACK 2: "Pattern overkill" → Defense: future flexibility. '
                'ATTACK 3: "Ignoring simpler fix" → Defense: considered and rejected.'
            ),
            "INVERSION / PRE-MORTEM": (
                "How to GUARANTEE failure: "
                "1. Skip tests → Prevention: mandatory test gate. "
                "2. Big-bang change → Prevention: incremental commits. "
                "3. Ignore error handling → Prevention: error-first design. "
                "1 month later, it failed: missing integration test for edge case."
            ),
            "RAVEN LOOP": (
                "REFLECT: approach is sound, assumptions checked. "
                "ADAPT: add retry logic based on reflection. "
                "VERIFY: adapted approach passes all test scenarios. "
                "EXECUTE: implement with monitoring. "
                "NAVIGATE: success, lessons learned for next iteration. "
                "LOOP AGAIN? no."
            ),
            "RECURSIVE SELF-IMPROVEMENT": (
                "DRAFT: implement incremental approach. "
                "CRITIQUE: Weakness 1: no rollback plan | "
                "Weakness 2: missing performance validation. "
                "IMPROVED: added rollback + perf benchmarks. "
                "FINAL CONFIDENCE: 8."
            ),
        }
        return mocks.get(technique, f"{technique} analysis for: {task}")

    def _mock_angle_output(self, angle: str, task: str) -> str:
        """Generate deterministic mock content for an Ensemble/Megamind angle."""
        conf = self._angle_confidence(angle)
        return (
            f"ANGLE: {angle}. "
            f"Analysis of '{task[:50]}...' from {angle.lower()} perspective. "
            f"Recommendation: proceed with {angle.lower()}-optimized approach. "
            f"Key risk: {angle.lower()}-specific edge case. "
            f"Confidence: {conf}."
        )

    def _mock_jury_phase(self, phase_id: str, phase_name: str, task: str) -> str:
        """Generate deterministic mock content for a Grand Jury phase."""
        mocks = {
            "GJ-0": (
                f"Repo root: /workspace. "
                f"Available tools: search, read, shell, tests. "
                f"Constraints: no destructive operations. "
                f"PLEDGE: I will not propose a fix until Pre-Flight (GJ-7) is complete."
            ),
            "GJ-1": (
                f"Reported: '{task}'. "
                f"Expected: correct behavior. Actual: incorrect behavior. "
                f"Severity: moderate. Success criteria: tests pass."
            ),
            "GJ-2": (
                "A1: Architecture follows standard patterns — TDK — 70% — UNVERIFIED. "
                "A2: Test coverage is adequate — PC — 80% — UNVERIFIED."
            ),
            "GJ-3": (
                "S1: rg -n 'error' . — 5 hits — narrows error source. "
                "S2: rg -n 'config' . — 3 hits — finds config loading."
            ),
            "GJ-4": (
                "E1: main.py:L42 — verbatim excerpt — proves error handler location. "
                "E2: config.py:L15 — verbatim excerpt — proves config loading. "
                "E3: test_output — raw command — proves failure mode."
            ),
            "GJ-5": (
                "Source → Config load → Module init → Runtime behavior. "
                "Each link verified with Evidence IDs."
            ),
            "GJ-6": (
                "H1: Primary suspect — E1,E2 FOR — E3 AGAINST — CONFIRMED. "
                "H2: Challenger — E3 FOR — E1 AGAINST — DISPROVED. "
                "H3: Null hypothesis — E2 FOR — E1,E3 AGAINST — DISPROVED. "
                "H4: Model is wrong — weak — UNCERTAIN."
            ),
            "GJ-7": (
                "1. Files read: main.py (E1), config.py (E2). "
                "2. Root cause: misconfigured handler at main.py:42 (E1). "
                "3. Eliminated: H2 DISPROVED (E3 contradicts), H3 DISPROVED. "
                "4. Atomic fix: change handler config (E1). "
                "5. Risks: regression in related handlers. "
                "6. Verification: run test suite + manual check."
            ),
            "GJ-8": (
                "Atomic change applied. Verification: PASS. "
                "All tests green. No regressions detected."
            ),
        }
        return mocks.get(phase_id, f"{phase_name} analysis for: {task}")

    # ── Confidence helpers ────────────────────────────────────────────────

    @staticmethod
    def _extract_confidence(text: str) -> int:
        """Extract a confidence score from mock output text."""
        match = re.search(r"[Cc]onfidence[^:]*:\s*(\d+)", text)
        if match:
            return min(10, max(1, int(match.group(1))))
        return 7

    @staticmethod
    def _complexity_confidence(task: str) -> int:
        """Return a plausible confidence based on task complexity heuristics."""
        lower = task.lower()
        if any(w in lower for w in ("migrate", "50 endpoints", "redesign")):
            return 6
        if any(w in lower for w in ("refactor", "multi-tenant", "plugin")):
            return 7
        return 8

    @staticmethod
    def _angle_confidence(angle: str) -> int:
        """Return deterministic per-angle confidence for reproducible tests."""
        table = {
            "PERFORMANCE": 8,
            "SIMPLICITY": 7,
            "SECURITY": 8,
            "SCALABILITY": 6,
            "EDGE CASES": 5,
            "DEVIL'S ADVOCATE": 6,
            "BEGINNER'S MIND": 7,
            "FUTURE SELF": 7,
            "USER PERSPECTIVE": 8,
            "CONSTRAINT BREAKER": 5,
        }
        return table.get(angle, 7)


# ═══════════════════════════════════════════════════════════════════════════
# Shared test problems (≥ 3 per complexity level)
# ═══════════════════════════════════════════════════════════════════════════

LOW_PROBLEMS = [
    "Add a type hint to this function",
    "Fix a typo in a variable name",
    "Add a missing docstring to a public method",
]

MEDIUM_PROBLEMS = [
    "Refactor this module to use dependency injection",
    "Add retry logic with exponential backoff to the API client",
    "Convert the monolithic config parser into separate validator and loader classes",
]

HIGH_PROBLEMS = [
    "Redesign the authentication system for multi-tenant support",
    "Design a rate limiter that handles burst traffic, per-user quotas, and distributed coordination",
    "Architect a plugin system that supports hot-reloading, dependency injection, and sandboxed execution",
]

EXTREME_PROBLEMS = [
    "Migrate from REST to GraphQL across 50 endpoints",
    "Plan the migration of a monolithic Python application to microservices, considering data consistency, service discovery, backward compatibility, and zero-downtime deployment",
    "Redesign the entire CI/CD pipeline to support multi-cloud deployment with canary releases, feature flags, and automated rollback",
]

TEST_PROBLEMS: dict[str, list[str]] = {
    "LOW": LOW_PROBLEMS,
    "MEDIUM": MEDIUM_PROBLEMS,
    "HIGH": HIGH_PROBLEMS,
    "EXTREME": EXTREME_PROBLEMS,
}


# ═══════════════════════════════════════════════════════════════════════════
# Pytest fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def harness():
    """Provide a ReasoningSwarmHarness factory for test functions.

    Usage in tests:
        def test_something(harness):
            h = harness("Add a type hint", mode="DEEP")
            trace = h.run()
            assert trace.confidence >= 7
    """

    def _factory(task: str, mode: Optional[str] = None) -> ReasoningSwarmHarness:
        return ReasoningSwarmHarness(task_description=task, mode_override=mode)

    return _factory
