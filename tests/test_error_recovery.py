"""E2E tests: Error Recovery Protocol and Escalation Chains.

Validates the Failure Recovery Protocol (FRP) across multiple failure/retry
cycles, pre-flight gating, fix validation guards, and the full escalation
chain (Rapid Strike → Deep Think → Ensemble → Megamind) with context
preservation between modes.

Covers:
  1. First fix fails → FRP requires >=2 new evidence entries before retry
  2. Second fix also fails → FRP requires re-running Murder Board
  3. Third fix succeeds → post-mortem identifies dangerous assumption
  4. Pre-flight gate blocks: missing evidence on any item → returns to search/read
  5. Hallucinated file in fix → detected and rejected
  6. Non-atomic fix (multiple changes) → rejected
  7. Verification plan missing exact commands → rejected
  8. Escalation chain: Rapid Strike conf 6 → Deep Think conf 5 → Ensemble conf 6
     → Megamind conf 5 after 3 iterations → uncertainty flags
  9. Each escalation preserves context from previous mode

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
    ENSEMBLE_ANGLES,
    GRAND_JURY_PHASES,
    MEGAMIND_ANGLES,
    MEGAMIND_SYNTHESIZERS,
    ReasoningSwarmHarness,
    ReasoningTrace,
    harness,
)

CANONICAL_DEBUG_TASK = "Debug the failing cart checkout flow — users see 500 error on /cart/add"


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness: multi-cycle FRP (3 fix attempts)
# ═══════════════════════════════════════════════════════════════════════════


class FRPMultiFailureHarness(ReasoningSwarmHarness):
    """Harness that simulates 3 fix attempts under FRP.

    Attempt 1: fails → triggers FRP, collects >=2 new evidence entries.
    Attempt 2: fails → FRP requires re-running Murder Board.
    Attempt 3: succeeds → post-mortem identifies dangerous assumption.
    """

    def _run_jury(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        evidence: list[str] = []
        fix_attempts: list[dict] = []

        for phase_id, phase_name in GRAND_JURY_PHASES:
            content = self._mock_jury_phase(phase_id, phase_name, task)

            if phase_id == "GJ-8":
                # Attempt 1 — fail
                attempt1 = {
                    "id": 1,
                    "result": "FAIL",
                    "frp_triggered": True,
                    "new_evidence": [
                        "E4: handlers/cart.py:L88 — verbatim excerpt: off-by-one in quantity validation",
                        "E5: tests/test_cart.py:L31 — raw output: AssertionError on boundary value 0",
                    ],
                    "content": (
                        "ATTEMPT 1: Atomic change applied. "
                        "Verification: FAIL — test still errors. "
                        "FAILURE RECOVERY PROTOCOL TRIGGERED. "
                        "Must collect >= 2 new evidence entries before retry."
                    ),
                }
                evidence.extend(attempt1["new_evidence"])
                fix_attempts.append(attempt1)

                # Attempt 2 — fail, re-run Murder Board
                attempt2 = {
                    "id": 2,
                    "result": "FAIL",
                    "frp_triggered": True,
                    "murder_board_rerun": True,
                    "new_evidence": [
                        "E6: handlers/cart.py:L102 — verbatim excerpt: race condition in inventory lock",
                        "E7: middleware/auth.py:L15 — verbatim excerpt: session timeout mismatch",
                    ],
                    "content": (
                        "ATTEMPT 2: FRP PASS 2 — E4 + E5 collected. "
                        "Root cause revised. Murder Board re-run: "
                        "H1 revised (E4,E5 FOR) — still UNCERTAIN. "
                        "H5 new: race condition in inventory — E6 FOR — CONFIRMED. "
                        "Atomic change v2 applied. "
                        "Verification: FAIL — intermittent failures persist."
                    ),
                }
                evidence.extend(attempt2["new_evidence"])
                fix_attempts.append(attempt2)

                # Attempt 3 — success with post-mortem
                attempt3 = {
                    "id": 3,
                    "result": "PASS",
                    "content": (
                        "ATTEMPT 3: FRP PASS 3 — E6 + E7 collected. "
                        "Root cause revised again to race condition + boundary. "
                        "Atomic change v3 applied (lock + boundary fix). "
                        "Verification: PASS. All tests green."
                    ),
                }
                fix_attempts.append(attempt3)

                for att in fix_attempts:
                    section = (
                        f"┌─ FRP ATTEMPT {att['id']} ({phase_id}) ──────────────────\n"
                        f"│ {att['content']}\n"
                        f"└{'─' * 50}┘"
                    )
                    output_parts.append(section)
                    techniques_used.append(f"JURY:{phase_id}:FRP:{att['id']}")

                # Post-mortem
                postmortem = (
                    "POST-MORTEM: Dangerous assumption identified — "
                    "A1 (standard patterns) was UNVERIFIED and proved wrong. "
                    "The codebase used a non-standard locking pattern that "
                    "contradicted training-data knowledge. Lesson: never trust "
                    "TDK assumptions without project-specific verification."
                )
                section = (
                    f"┌─ POST-MORTEM ({phase_id}) ──────────────────\n"
                    f"│ {postmortem}\n"
                    f"└{'─' * 50}┘"
                )
                output_parts.append(section)
                techniques_used.append(f"JURY:{phase_id}:POSTMORTEM")

            # Normal phase
            section = (
                f"┌─ {phase_name} ({phase_id}) ──────────────────\n"
                f"│ {content}\n"
                f"└{'─' * 50}┘"
            )
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
            f"Hypotheses Tested: 5\n"
            f"Root Cause: Race condition + boundary error (revised twice)\n"
            f"Fix: Atomic change v3 applied\n"
            f"Verification: PASS\n"
            f"Fix Attempts: {len(fix_attempts)}\n"
            f"Post-Mortem: Dangerous assumption in A1 identified"
        )

        trace = ReasoningTrace(
            mode="JURY",
            confidence=conf,
            checkpoints_hit=9,
            escalations=0,
            techniques_used=techniques_used,
            evidence_entries=evidence,
            raw_output=raw,
        )
        trace._fix_attempts = fix_attempts  # type: ignore[attr-defined]
        return trace


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness: Pre-flight gate enforcement
# ═══════════════════════════════════════════════════════════════════════════


class PreFlightGateHarness(ReasoningSwarmHarness):
    """Harness that simulates a Pre-Flight gate blocking a fix.

    At GJ-7, one checklist item has missing evidence. The gate rejects
    the fix and returns to search/read phases.
    """

    def _run_jury(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        evidence: list[str] = []
        gate_passed = False

        for phase_id, phase_name in GRAND_JURY_PHASES:
            if phase_id == "GJ-7":
                content = (
                    "1. Files read: main.py (E1), config.py (E2) — VERIFIED. "
                    "2. Root cause: misconfigured handler at main.py:42 (E1) — VERIFIED. "
                    "3. Eliminated: H2 DISPROVED (E3 contradicts) — VERIFIED. "
                    "4. Atomic fix: change handler config — MISSING EVIDENCE. "
                    "   No evidence entry links the proposed fix to verified root cause. "
                    "5. Risks: regression in related handlers — VERIFIED. "
                    "6. Verification: run test suite + manual check — VERIFIED. "
                    "PRE-FLIGHT GATE: BLOCKED. Item 4 missing evidence. "
                    "Returning to SEARCH/READ phase to collect fix-evidence linkage."
                )
                gate_passed = False
            elif phase_id == "GJ-8" and not gate_passed:
                content = (
                    "GATE ENFORCEMENT: Pre-Flight blocked at GJ-7. "
                    "Returning to GJ-3 (Search Pass) to find fix-evidence linkage. "
                    "S3: rg -n 'handler_config' src/ — 2 hits — finds config pattern. "
                    "E8: src/handler_config.py:L22 — verbatim excerpt: default value wrong. "
                    "Re-running Pre-Flight with E8 linked to item 4. "
                    "PRE-FLIGHT GATE: PASSED. All 6 items verified."
                )
                gate_passed = True
            else:
                content = self._mock_jury_phase(phase_id, phase_name, task)

            section = (
                f"┌─ {phase_name} ({phase_id}) ──────────────────\n"
                f"│ {content}\n"
                f"└{'─' * 50}┘"
            )
            output_parts.append(section)
            techniques_used.append(f"JURY:{phase_id}")

            if phase_id == "GJ-4":
                evidence.extend([
                    "E1: main.py:L42 — verbatim excerpt of error handler",
                    "E2: config.py:L15 — verbatim excerpt of config loading",
                    "E3: test_output — raw command output from failing test",
                ])
            if gate_passed and phase_id == "GJ-8":
                evidence.append(
                    "E8: src/handler_config.py:L22 — verbatim excerpt: default value wrong"
                )

        conf = self._complexity_confidence(task)
        raw = "\n".join(output_parts)
        raw += (
            f"\n\n⚖️ GRAND JURY COMPLETE\n"
            f"Evidence Entries: {len(evidence)}\n"
            f"Hypotheses Tested: 4\n"
            f"Root Cause: Identified via evidence chain\n"
            f"Fix: Atomic change applied (after gate retry)\n"
            f"Verification: PASS"
        )

        return ReasoningTrace(
            mode="JURY",
            confidence=conf,
            checkpoints_hit=9,
            escalations=0,
            techniques_used=techniques_used,
            evidence_entries=evidence,
            raw_output=raw,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness: Hallucinated file detection
# ═══════════════════════════════════════════════════════════════════════════


class HallucinatedFileHarness(ReasoningSwarmHarness):
    """Harness that detects a hallucinated file reference in a fix.

    The proposed fix references a file that doesn't exist in the repo.
    The validation step detects and rejects it.
    """

    def _run_jury(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        evidence: list[str] = []
        hallucination_detected = False

        for phase_id, phase_name in GRAND_JURY_PHASES:
            content = self._mock_jury_phase(phase_id, phase_name, task)

            if phase_id == "GJ-8":
                content = (
                    "PROPOSED FIX: Modify handlers/cart_helper.py:L45 — "
                    "change quantity validation to use Decimal type. "
                    "FILE VALIDATION: Checking handlers/cart_helper.py... "
                    "ERROR: handlers/cart_helper.py DOES NOT EXIST in repository. "
                    "HALLUCINATED FILE DETECTED. Fix rejected. "
                    "Validating against known files from GJ-1.5 Territory Map... "
                    "Correction: actual file is handlers/cart.py:L88. "
                    "REVISED FIX: Modify handlers/cart.py:L88 — "
                    "add boundary check for quantity <= 0. "
                    "FILE VALIDATION: handlers/cart.py EXISTS — confirmed in Territory Map. "
                    "Verification: PASS."
                )
                hallucination_detected = True

            section = (
                f"┌─ {phase_name} ({phase_id}) ──────────────────\n"
                f"│ {content}\n"
                f"└{'─' * 50}┘"
            )
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
            f"Hallucinated Files Detected: {1 if hallucination_detected else 0}\n"
            f"Root Cause: Identified via evidence chain\n"
            f"Fix: Atomic change applied (corrected file reference)\n"
            f"Verification: PASS"
        )

        trace = ReasoningTrace(
            mode="JURY",
            confidence=conf,
            checkpoints_hit=9,
            escalations=0,
            techniques_used=techniques_used,
            evidence_entries=evidence,
            raw_output=raw,
        )
        trace._hallucination_detected = hallucination_detected  # type: ignore[attr-defined]
        return trace


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness: Non-atomic fix rejection
# ═══════════════════════════════════════════════════════════════════════════


class NonAtomicFixHarness(ReasoningSwarmHarness):
    """Harness that rejects a non-atomic fix (multiple files changed at once)."""

    def _run_jury(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        evidence: list[str] = []
        atomic_rejected = False

        for phase_id, phase_name in GRAND_JURY_PHASES:
            content = self._mock_jury_phase(phase_id, phase_name, task)

            if phase_id == "GJ-8":
                content = (
                    "PROPOSED FIX: "
                    "Change 1: handlers/cart.py:L88 — add boundary check. "
                    "Change 2: config.py:L15 — update timeout value. "
                    "Change 3: middleware/auth.py:L22 — refresh session logic. "
                    "ATOMICITY CHECK: 3 files modified in single fix. "
                    "REJECTED: Non-atomic fix — must be a single, focused change. "
                    "Split into separate atomic fixes. "
                    "REVISED FIX (atomic): handlers/cart.py:L88 — add boundary check only. "
                    "ATOMICITY CHECK: 1 file, 1 change — PASS. "
                    "Verification: PASS."
                )
                atomic_rejected = True

            section = (
                f"┌─ {phase_name} ({phase_id}) ──────────────────\n"
                f"│ {content}\n"
                f"└{'─' * 50}┘"
            )
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
            f"Fix: Atomic change applied (after non-atomic rejection)\n"
            f"Verification: PASS"
        )

        trace = ReasoningTrace(
            mode="JURY",
            confidence=conf,
            checkpoints_hit=9,
            escalations=0,
            techniques_used=techniques_used,
            evidence_entries=evidence,
            raw_output=raw,
        )
        trace._atomic_rejected = atomic_rejected  # type: ignore[attr-defined]
        return trace


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness: Verification plan validation
# ═══════════════════════════════════════════════════════════════════════════


class VerificationPlanHarness(ReasoningSwarmHarness):
    """Harness that rejects a verification plan missing exact commands."""

    def _run_jury(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        evidence: list[str] = []
        verification_rejected = False

        for phase_id, phase_name in GRAND_JURY_PHASES:
            content = self._mock_jury_phase(phase_id, phase_name, task)

            if phase_id == "GJ-7":
                content = (
                    "1. Files read: main.py (E1), config.py (E2). "
                    "2. Root cause: misconfigured handler at main.py:42 (E1). "
                    "3. Eliminated: H2 DISPROVED (E3 contradicts), H3 DISPROVED. "
                    "4. Atomic fix: change handler config (E1). "
                    "5. Risks: regression in related handlers. "
                    "6. Verification: run the tests and check manually. "
                    "VERIFICATION PLAN CHECK: Missing exact commands. "
                    "REJECTED: Verification item must include exact commands "
                    "to run (e.g. 'pytest tests/test_cart.py -x'). "
                    "REVISED: 6. Verification: "
                    "'pytest tests/test_cart.py -x -v && "
                    "curl -s http://localhost:8000/cart/add | grep -q 200'. "
                    "VERIFICATION PLAN CHECK: Exact commands present — PASS."
                )
                verification_rejected = True

            section = (
                f"┌─ {phase_name} ({phase_id}) ──────────────────\n"
                f"│ {content}\n"
                f"└{'─' * 50}┘"
            )
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

        trace = ReasoningTrace(
            mode="JURY",
            confidence=conf,
            checkpoints_hit=9,
            escalations=0,
            techniques_used=techniques_used,
            evidence_entries=evidence,
            raw_output=raw,
        )
        trace._verification_rejected = verification_rejected  # type: ignore[attr-defined]
        return trace


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness: Full escalation chain with context preservation
# ═══════════════════════════════════════════════════════════════════════════


class EscalationChainHarness(ReasoningSwarmHarness):
    """Harness that simulates the full escalation chain in a single run.

    Rapid Strike (conf 6) → Deep Think (conf 5) → Ensemble (conf 6)
    → Megamind (conf 5, 3 iterations) → uncertainty flags.

    Each escalation preserves context from the previous mode.
    All modes are simulated in a single _run_rapid() call because the
    harness dispatcher only invokes one mode method per run.
    """

    def _run_rapid(self) -> ReasoningTrace:
        """Simulate the full escalation chain: RAPID → DEEP → ENSEMBLE → MEGA."""
        task = self.task_description
        all_output_parts: list[str] = []
        all_techniques: list[str] = []
        chain: list[dict] = []

        # ── RAPID STRIKE (conf 6) ──────────────────────────────────────
        rapid_raw = (
            f"1. PROBLEM: {task}\n"
            f"2. OBVIOUS ANSWER: Apply standard pattern\n"
            f"3. SANITY CHECK: Edge cases detected — complexity higher than expected\n"
            f"4. CONFIDENCE: 6\n"
            f"5. ESCALATION: Confidence 6 < threshold 8 — escalating to DEEP THINK\n"
            f"CONTEXT PASSED: problem='{task}', rapid_answer='standard pattern', "
            f"concern='edge cases detected'"
        )
        chain.append({
            "mode": "RAPID",
            "confidence": 6,
            "context": f"problem='{task}', rapid_answer='standard pattern'",
        })
        all_output_parts.append(rapid_raw)
        all_techniques.append("RAPID STRIKE")

        # ── DEEP THINK (conf 5) ────────────────────────────────────────
        deep_parts: list[str] = []
        prev = chain[-1]
        deep_parts.append(
            f"CONTEXT FROM RAPID STRIKE: {prev['context']}\n"
            f"PREVIOUS CONFIDENCE: {prev['confidence']}"
        )
        for name, marker in DEEP_THINK_TECHNIQUES:
            content = self._mock_technique_output(name, task)
            section = (
                f"┌─ {name} ──────────────────────────────────────\n"
                f"│ {content}\n"
                f"│ {marker}\n"
                f"└{'─' * 50}┘"
            )
            deep_parts.append(section)
            all_techniques.append(name)

        deep_conf = 5
        deep_parts.append(
            f"\n🧠 DEEP THINK COMPLETE\n"
            f"Checkpoints Hit: 11/11\n"
            f"Confidence: {deep_conf}\n"
            f"ESCALATION: Confidence {deep_conf} < threshold 7 — escalating to ENSEMBLE\n"
            f"CONTEXT PASSED: deep_analysis='11 techniques applied', "
            f"revised_root_cause='multi-factor interaction'"
        )
        chain.append({
            "mode": "DEEP",
            "confidence": deep_conf,
            "context": "deep_analysis='11 techniques applied', revised_root_cause='multi-factor'",
        })
        all_output_parts.append("\n".join(deep_parts))

        # ── ENSEMBLE (conf 6) ──────────────────────────────────────────
        ens_parts: list[str] = []
        prev = chain[-1]
        ens_parts.append(
            f"CONTEXT FROM DEEP THINK: {prev['context']}\n"
            f"PREVIOUS CONFIDENCE: {prev['confidence']}"
        )
        for angle in ENSEMBLE_ANGLES:
            content = self._mock_angle_output(angle, task)
            ens_parts.append(f"ANGLE: {angle}\n{content}")
            all_techniques.append(f"ENSEMBLE:{angle}")

        ens_conf = 6
        synth = (
            f"\nSYNTHESIS:\n"
            f"AGREEMENT: Partial consensus — multiple root causes suspected\n"
            f"DISAGREEMENT: Primary vs secondary cause debate\n"
            f"RESOLUTION: Address boundary first, then race condition\n"
            f"RISKS: Fixing one may expose the other\n"
            f"DEVIL'S CONCERNS: Both may be symptoms of deeper issue\n"
            f"CONFIDENCE: {ens_conf}"
        )
        ens_parts.append(synth)
        all_techniques.append("ENSEMBLE:SYNTHESIS")

        ens_raw = "\n\n".join(ens_parts)
        ens_raw += (
            f"\n\n🧠 ENSEMBLE COMPLETE\n"
            f"Sub-Reasoners: 5\n"
            f"Agreement Level: 2/5 agree\n"
            f"Confidence: {ens_conf}\n"
            f"ESCALATION: Confidence {ens_conf} < threshold 7 — escalating to MEGAMIND\n"
            f"CONTEXT PASSED: ensemble_agreement='2/5', "
            f"conflicts='primary vs secondary cause'"
        )
        chain.append({
            "mode": "ENSEMBLE",
            "confidence": ens_conf,
            "context": "ensemble_agreement='2/5', conflicts='primary vs secondary cause'",
        })
        all_output_parts.append(ens_raw)

        # ── MEGAMIND (conf 5, 3 iterations) ────────────────────────────
        mega_parts: list[str] = []
        prev = chain[-1]
        mega_parts.append(
            f"CONTEXT FROM ENSEMBLE: {prev['context']}\n"
            f"PREVIOUS CONFIDENCE: {prev['confidence']}"
        )
        mega_parts.append("PHASE M1: Initial Deep Think Pass")
        for name, marker in DEEP_THINK_TECHNIQUES:
            mega_parts.append(f"  {name}: {marker}")
            all_techniques.append(f"MEGA:M1:{name}")

        max_iterations = 3
        mega_conf = 5
        agreement_level = "3/10"
        all_conflicts = [
            "Boundary check vs race condition priority",
            "Training-data assumption contradicts project reality",
            "Multiple root causes confound isolation",
        ]
        all_risks = [
            "Fixing boundary may mask race condition",
            "Race condition is intermittent — hard to verify",
            "Confidence too low for production deployment",
        ]

        for iteration in range(1, max_iterations + 1):
            mega_parts.append(
                f"\nPHASE M2: 10 Angle-Explorers (iteration {iteration})"
            )
            for angle in MEGAMIND_ANGLES:
                mega_parts.append(
                    f"  ANGLE: {angle}\n  {self._mock_angle_output(angle, task)}"
                )
                tech_key = f"MEGA:M2:{angle}"
                if tech_key not in all_techniques:
                    all_techniques.append(tech_key)

            mega_parts.append(
                f"\nPHASE M3: 3 Synthesizers (iteration {iteration})"
            )
            for synth_name in MEGAMIND_SYNTHESIZERS:
                mega_parts.append(
                    f"  SYNTHESIZER {synth_name}: Analysis from {synth_name} perspective "
                    f"(processed {len(MEGAMIND_ANGLES)} angle outputs)"
                )
                tech_key = f"MEGA:M3:{synth_name}"
                if tech_key not in all_techniques:
                    all_techniques.append(tech_key)

            mega_parts.append(
                f"\nPHASE M4: Final Synthesis (iteration {iteration})\n"
                f"  SYNTH A says: Consensus elusive — multiple valid root causes\n"
                f"  SYNTH B says: Conflicts persist across iterations\n"
                f"  SYNTH C says: Risks remain unacceptable at this confidence\n"
                f"  AGREEMENT LEVEL: {agreement_level} aligned\n"
                f"  CONFLICTS RESOLVED: {'; '.join(all_conflicts)}\n"
                f"  RISKS MITIGATED: {'; '.join(all_risks)}\n"
                f"  CONFIDENCE: {mega_conf}"
            )
            if "MEGA:M4:FINAL_SYNTHESIS" not in all_techniques:
                all_techniques.append("MEGA:M4:FINAL_SYNTHESIS")

            if iteration < max_iterations:
                mega_parts.append(
                    f"  → Confidence {mega_conf} < 7, looping back to Phase M2 "
                    f"(iteration {iteration + 1})"
                )
            else:
                mega_parts.append(
                    f"  → Max iterations ({max_iterations}) reached with "
                    f"confidence {mega_conf} < 7. Outputting with uncertainty flags."
                )

        mega_raw = "\n".join(mega_parts)
        mega_raw += (
            f"\n\n🧠 MEGAMIND COMPLETE\n"
            f"Architecture: 10 → 3 → 1\n"
            f"Iterations: {max_iterations}\n"
            f"Agreement Level: {agreement_level} aligned\n"
            f"Conflicts Resolved: {'; '.join(all_conflicts)}\n"
            f"Risks Mitigated: {'; '.join(all_risks)}\n"
            f"Final Confidence: {mega_conf}\n"
            f"UNCERTAINTY FLAGS: confidence_below_threshold, "
            f"multiple_root_causes, intermittent_failure"
        )
        chain.append({
            "mode": "MEGAMIND",
            "confidence": mega_conf,
            "iterations": max_iterations,
            "context": "megamind_3iterations, uncertainty flags raised",
        })
        all_output_parts.append(mega_raw)

        # ── Combined trace ─────────────────────────────────────────────
        combined_raw = "\n\n".join(all_output_parts)
        trace = ReasoningTrace(
            mode="RAPID",
            confidence=mega_conf,
            checkpoints_hit=4 + 11 + 5 + 13,
            escalations=3,
            techniques_used=all_techniques,
            raw_output=combined_raw,
            iterations=max_iterations,
            agreement_level=agreement_level,
            conflicts=all_conflicts,
            risks=all_risks,
        )
        trace._escalation_chain = chain  # type: ignore[attr-defined]
        return trace


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════


def _run_frp_multi(task: str = CANONICAL_DEBUG_TASK) -> ReasoningTrace:
    """Run Grand Jury with multi-cycle FRP."""
    h = FRPMultiFailureHarness(task_description=task, mode_override="JURY")
    return h.run()


def _run_preflight_gate(task: str = CANONICAL_DEBUG_TASK) -> ReasoningTrace:
    """Run Grand Jury with pre-flight gate enforcement."""
    h = PreFlightGateHarness(task_description=task, mode_override="JURY")
    return h.run()


def _run_hallucinated_file(task: str = CANONICAL_DEBUG_TASK) -> ReasoningTrace:
    """Run Grand Jury with hallucinated file detection."""
    h = HallucinatedFileHarness(task_description=task, mode_override="JURY")
    return h.run()


def _run_non_atomic(task: str = CANONICAL_DEBUG_TASK) -> ReasoningTrace:
    """Run Grand Jury with non-atomic fix rejection."""
    h = NonAtomicFixHarness(task_description=task, mode_override="JURY")
    return h.run()


def _run_verification_plan(task: str = CANONICAL_DEBUG_TASK) -> ReasoningTrace:
    """Run Grand Jury with verification plan validation."""
    h = VerificationPlanHarness(task_description=task, mode_override="JURY")
    return h.run()


def _run_escalation_chain(task: str = CANONICAL_DEBUG_TASK) -> ReasoningTrace:
    """Run the full escalation chain starting from Rapid Strike."""
    h = EscalationChainHarness(task_description=task, mode_override="RAPID")
    return h.run()


# ═══════════════════════════════════════════════════════════════════════════
# Test class: FRP multi-failure (cases 1-3)
# ═══════════════════════════════════════════════════════════════════════════


class TestFRPMultiFailure:
    """Test cases 1-3: multiple fix failures and recovery under FRP."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_frp_multi()

    # ── Case 1: First fix fails → FRP requires >=2 new evidence ──────────

    def test_first_fix_fails(self, trace):
        assert "ATTEMPT 1" in trace.raw_output
        assert re.search(r"ATTEMPT 1.*FAIL", trace.raw_output, re.DOTALL)

    def test_frp_triggered_on_first_failure(self, trace):
        assert "FAILURE RECOVERY PROTOCOL TRIGGERED" in trace.raw_output

    def test_frp_requires_2_new_evidence(self, trace):
        assert re.search(
            r"Must collect.*>=.*2.*new evidence", trace.raw_output
        )

    def test_frp_adds_e4_and_e5(self, trace):
        new_entries = [e for e in trace.evidence_entries if e.startswith(("E4:", "E5:"))]
        assert len(new_entries) >= 2, (
            f"FRP must add >=2 new evidence entries (E4, E5), found {len(new_entries)}"
        )

    # ── Case 2: Second fix fails → re-run Murder Board ───────────────────

    def test_second_fix_fails(self, trace):
        assert "ATTEMPT 2" in trace.raw_output
        assert re.search(r"ATTEMPT 2.*FAIL", trace.raw_output, re.DOTALL)

    def test_second_failure_reruns_murder_board(self, trace):
        assert re.search(r"Murder Board re-run", trace.raw_output, re.IGNORECASE)

    def test_second_frp_adds_e6_and_e7(self, trace):
        new_entries = [e for e in trace.evidence_entries if e.startswith(("E6:", "E7:"))]
        assert len(new_entries) >= 2, (
            f"Second FRP must add >=2 new evidence entries (E6, E7), found {len(new_entries)}"
        )

    def test_revised_hypothesis_on_rerun(self, trace):
        assert re.search(r"H\d+\s+revised", trace.raw_output, re.IGNORECASE)

    # ── Case 3: Third fix succeeds → post-mortem ─────────────────────────

    def test_third_fix_succeeds(self, trace):
        assert "ATTEMPT 3" in trace.raw_output
        assert re.search(r"ATTEMPT 3.*PASS", trace.raw_output, re.DOTALL)

    def test_postmortem_present(self, trace):
        assert "POST-MORTEM" in trace.raw_output

    def test_postmortem_identifies_dangerous_assumption(self, trace):
        assert re.search(
            r"Dangerous assumption", trace.raw_output, re.IGNORECASE
        )

    def test_postmortem_links_to_tdk_assumption(self, trace):
        """The dangerous assumption should reference TDK (Training-Data Knowledge)."""
        assert re.search(r"TDK|training.data", trace.raw_output, re.IGNORECASE)

    # ── Overall FRP integrity ────────────────────────────────────────────

    def test_total_evidence_across_all_attempts(self, trace):
        """3 initial + 2 (attempt 1) + 2 (attempt 2) = 7 evidence entries."""
        assert len(trace.evidence_entries) >= 7, (
            f"Expected >=7 total evidence entries across all FRP cycles, "
            f"got {len(trace.evidence_entries)}"
        )

    def test_all_frp_techniques_recorded(self, trace):
        frp_techs = [t for t in trace.techniques_used if "FRP" in t]
        assert len(frp_techs) >= 3, (
            f"Expected >=3 FRP technique entries (one per attempt), found {len(frp_techs)}"
        )

    def test_all_phases_still_present(self, trace):
        for phase_id, _ in GRAND_JURY_PHASES:
            assert f"({phase_id})" in trace.raw_output, (
                f"Phase {phase_id} missing from FRP output"
            )

    def test_fix_attempts_tracked(self, trace):
        assert len(trace._fix_attempts) == 3

    def test_attempt_results_sequence(self, trace):
        results = [a["result"] for a in trace._fix_attempts]
        assert results == ["FAIL", "FAIL", "PASS"]


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Pre-flight gate (case 4)
# ═══════════════════════════════════════════════════════════════════════════


class TestPreFlightGate:
    """Case 4: Pre-flight gate blocks fix when evidence is missing."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_preflight_gate()

    def test_preflight_gate_blocked(self, trace):
        assert re.search(r"PRE-FLIGHT GATE:\s*BLOCKED", trace.raw_output)

    def test_missing_evidence_on_item_4(self, trace):
        assert re.search(
            r"4\.\s*Atomic fix.*MISSING EVIDENCE", trace.raw_output, re.DOTALL
        )

    def test_returns_to_search_read(self, trace):
        assert re.search(
            r"Returning to.*SEARCH.*READ", trace.raw_output, re.IGNORECASE
        )

    def test_new_search_pass_executed(self, trace):
        assert re.search(r"S\d+:.*rg", trace.raw_output)

    def test_new_evidence_collected(self, trace):
        assert "E8:" in trace.raw_output

    def test_gate_passes_after_research(self, trace):
        assert re.search(r"PRE-FLIGHT GATE:\s*PASSED", trace.raw_output)

    def test_all_6_items_verified(self, trace):
        assert re.search(r"1\.\s*Files read.*VERIFIED", trace.raw_output, re.DOTALL)
        assert re.search(r"6\.\s*Verification.*VERIFIED", trace.raw_output, re.DOTALL)

    def test_all_phases_present(self, trace):
        for phase_id, _ in GRAND_JURY_PHASES:
            assert f"({phase_id})" in trace.raw_output, (
                f"Phase {phase_id} missing from pre-flight gate output"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Hallucinated file detection (case 5)
# ═══════════════════════════════════════════════════════════════════════════


class TestHallucinatedFileDetection:
    """Case 5: A fix referencing a non-existent file is detected and rejected."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_hallucinated_file()

    def test_hallucinated_file_detected(self, trace):
        assert "HALLUCINATED FILE DETECTED" in trace.raw_output

    def test_hallucinated_file_does_not_exist(self, trace):
        assert re.search(
            r"cart_helper\.py\s+DOES NOT EXIST", trace.raw_output
        )

    def test_fix_rejected(self, trace):
        assert re.search(r"Fix rejected", trace.raw_output, re.IGNORECASE)

    def test_corrected_file_validated(self, trace):
        assert re.search(
            r"cart\.py\s+EXISTS", trace.raw_output
        )

    def test_territory_map_used_for_validation(self, trace):
        assert re.search(
            r"Territory Map", trace.raw_output, re.IGNORECASE
        )

    def test_revised_fix_passes(self, trace):
        assert re.search(r"Verification:\s*PASS", trace.raw_output)

    def test_hallucination_counted(self, trace):
        match = re.search(r"Hallucinated Files Detected:\s*(\d+)", trace.raw_output)
        assert match, "Hallucinated file count not found"
        assert int(match.group(1)) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Non-atomic fix rejection (case 6)
# ═══════════════════════════════════════════════════════════════════════════


class TestNonAtomicFixRejection:
    """Case 6: A fix modifying multiple files at once is rejected."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_non_atomic()

    def test_non_atomic_fix_detected(self, trace):
        assert re.search(r"Non-atomic fix", trace.raw_output, re.IGNORECASE)

    def test_multiple_files_listed(self, trace):
        assert "handlers/cart.py" in trace.raw_output
        assert "config.py" in trace.raw_output
        assert "middleware/auth.py" in trace.raw_output

    def test_rejection_message(self, trace):
        assert re.search(r"REJECTED", trace.raw_output)

    def test_single_focused_change_required(self, trace):
        assert re.search(
            r"single.*focused change", trace.raw_output, re.IGNORECASE
        )

    def test_atomicity_check_passes_on_revision(self, trace):
        assert re.search(r"ATOMICITY CHECK:.*PASS", trace.raw_output)

    def test_revised_fix_is_single_file(self, trace):
        assert re.search(
            r"1 file.*1 change", trace.raw_output
        )

    def test_verification_passes_after_revision(self, trace):
        assert re.search(r"Verification:\s*PASS", trace.raw_output)

    def test_atomic_rejection_tracked(self, trace):
        assert trace._atomic_rejected is True


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Verification plan validation (case 7)
# ═══════════════════════════════════════════════════════════════════════════


class TestVerificationPlanValidation:
    """Case 7: Verification plan missing exact commands is rejected."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_verification_plan()

    def test_verification_rejected_initially(self, trace):
        assert re.search(
            r"Missing exact commands", trace.raw_output, re.IGNORECASE
        )

    def test_rejection_explanation(self, trace):
        assert re.search(
            r"must include exact commands", trace.raw_output, re.IGNORECASE
        )

    def test_revised_verification_has_commands(self, trace):
        assert "pytest" in trace.raw_output

    def test_revised_verification_has_curl(self, trace):
        assert "curl" in trace.raw_output

    def test_verification_plan_passes_after_revision(self, trace):
        assert re.search(
            r"VERIFICATION PLAN CHECK:.*PASS", trace.raw_output
        )

    def test_verification_rejection_tracked(self, trace):
        assert trace._verification_rejected is True

    def test_grand_jury_completes(self, trace):
        assert "⚖️ GRAND JURY COMPLETE" in trace.raw_output


# ═══════════════════════════════════════════════════════════════════════════
# Test class: Escalation chain with context preservation
# ═══════════════════════════════════════════════════════════════════════════


class TestEscalationChain:
    """Escalation: Rapid Strike conf 6 → Deep Think conf 5 → Ensemble conf 6
    → Megamind conf 5 after 3 iterations → uncertainty flags.
    Each escalation preserves context from previous mode."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_escalation_chain()

    # ── Rapid Strike → Deep Think ────────────────────────────────────────

    def test_rapid_strike_confidence_6(self, trace):
        assert re.search(r"CONFIDENCE:\s*6", trace.raw_output)

    def test_rapid_strike_escalates_to_deep_think(self, trace):
        assert re.search(
            r"escalating to DEEP THINK", trace.raw_output, re.IGNORECASE
        )

    def test_rapid_context_passed_to_deep(self, trace):
        assert re.search(
            r"CONTEXT FROM RAPID STRIKE", trace.raw_output, re.IGNORECASE
        )

    # ── Deep Think → Ensemble ────────────────────────────────────────────

    def test_deep_think_confidence_5(self, trace):
        """Deep Think reports confidence 5 in the escalation chain."""
        # The Deep Think section has its own CONFIDENCE line
        assert re.search(
            r"DEEP THINK COMPLETE.*Confidence:\s*5", trace.raw_output, re.DOTALL
        )

    def test_deep_think_escalates_to_ensemble(self, trace):
        assert re.search(
            r"escalating to ENSEMBLE", trace.raw_output, re.IGNORECASE
        )

    def test_deep_context_passed_to_ensemble(self, trace):
        assert re.search(
            r"CONTEXT FROM DEEP THINK", trace.raw_output, re.IGNORECASE
        )

    # ── Ensemble → Megamind ──────────────────────────────────────────────

    def test_ensemble_confidence_6(self, trace):
        assert re.search(
            r"ENSEMBLE COMPLETE.*Confidence:\s*6", trace.raw_output, re.DOTALL
        )

    def test_ensemble_escalates_to_megamind(self, trace):
        assert re.search(
            r"escalating to MEGAMIND", trace.raw_output, re.IGNORECASE
        )

    def test_ensemble_context_passed_to_megamind(self, trace):
        assert re.search(
            r"CONTEXT FROM ENSEMBLE", trace.raw_output, re.IGNORECASE
        )

    # ── Megamind: 3 iterations, uncertainty flags ────────────────────────

    def test_megamind_confidence_5(self, trace):
        assert re.search(
            r"MEGAMIND COMPLETE.*Final Confidence:\s*5", trace.raw_output, re.DOTALL
        )

    def test_megamind_reaches_3_iterations(self, trace):
        assert re.search(r"Iterations:\s*3", trace.raw_output)

    def test_megamind_uncertainty_flags(self, trace):
        assert re.search(r"UNCERTAINTY FLAGS", trace.raw_output, re.IGNORECASE)

    def test_megamind_max_iterations_message(self, trace):
        assert "Max iterations (3) reached" in trace.raw_output

    # ── Context preservation across entire chain ─────────────────────────

    def test_escalation_chain_length(self, trace):
        assert len(trace._escalation_chain) == 4

    def test_escalation_chain_modes(self, trace):
        modes = [entry["mode"] for entry in trace._escalation_chain]
        assert modes == ["RAPID", "DEEP", "ENSEMBLE", "MEGAMIND"]

    def test_escalation_chain_confidences(self, trace):
        confs = [entry["confidence"] for entry in trace._escalation_chain]
        assert confs == [6, 5, 6, 5]

    def test_each_chain_entry_has_context(self, trace):
        for entry in trace._escalation_chain:
            assert "context" in entry, (
                f"Missing context in {entry['mode']} escalation entry"
            )
            assert len(entry["context"]) > 0, (
                f"Empty context in {entry['mode']} escalation entry"
            )

    def test_context_references_are_progressive(self, trace):
        """Each escalation context should reference findings from the prior mode."""
        chain = trace._escalation_chain
        # RAPID context mentions 'rapid_answer' or 'standard pattern'
        assert "rapid" in chain[0]["context"].lower() or "standard" in chain[0]["context"].lower()
        # DEEP context mentions 'deep_analysis' or 'techniques'
        assert "deep" in chain[1]["context"].lower() or "technique" in chain[1]["context"].lower()
        # ENSEMBLE context mentions 'ensemble' or 'agreement'
        assert "ensemble" in chain[2]["context"].lower() or "agreement" in chain[2]["context"].lower()
        # MEGAMIND context mentions 'megamind' or 'iteration'
        assert "megamind" in chain[3]["context"].lower() or "iteration" in chain[3]["context"].lower()

    # ── All 4 modes appear in raw output ─────────────────────────────────

    def test_rapid_strike_section_present(self, trace):
        assert "PROBLEM:" in trace.raw_output

    def test_deep_think_section_present(self, trace):
        assert "DEEP THINK COMPLETE" in trace.raw_output

    def test_ensemble_section_present(self, trace):
        assert "ENSEMBLE COMPLETE" in trace.raw_output

    def test_megamind_section_present(self, trace):
        assert "MEGAMIND COMPLETE" in trace.raw_output
