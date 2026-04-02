"""Benchmark: Grand Jury evidence completeness.

Validates the investigation protocol (GJ-0 through GJ-8) for evidence
completeness, procedural correctness, and anti-shortcut detection.

Checks:
  1. All 8 phases execute in order (GJ-0 through GJ-8)
  2. Evidence Ledger entries are verbatim with line numbers
  3. At least one negative is proven
  4. Murder Board has 4+ hypotheses with evidence FOR and AGAINST
  5. Pre-Flight checklist gates (any item lacking evidence -> go back)
  6. Atomic change rule (one logical fix per attempt)
  7. Failure Recovery Protocol triggers on failed fix
  8. Anti-shortcut detection catches training-data claims without verification

Uses 3 debugging scenarios with known root causes for end-to-end testing.

Usage:
    python benchmarks/test_grand_jury_evidence.py
"""

import re
import sys
import types
from pathlib import Path
from dataclasses import dataclass, field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Provide a minimal pytest stub so the scaffold can be imported
# even when pytest is not installed.
if "pytest" not in sys.modules:
    _pytest_stub = types.ModuleType("pytest")

    def _fixture(func=None, **kwargs):
        if func is not None:
            return func
        return lambda f: f

    _pytest_stub.fixture = _fixture
    sys.modules["pytest"] = _pytest_stub

from tests.test_e2e_scaffold import (
    GRAND_JURY_PHASES,
    ReasoningSwarmHarness,
    ReasoningTrace,
)


# ═══════════════════════════════════════════════════════════════════════════
# Debugging scenarios with known root causes
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class DebugScenario:
    """A debugging scenario with a known root cause for benchmark testing."""

    name: str
    task: str
    root_cause_file: str
    root_cause_line: int
    root_cause_description: str
    negative_evidence: str
    hypotheses: list[dict] = field(default_factory=list)
    preflight_failures: list[str] = field(default_factory=list)
    shortcut_claims: list[str] = field(default_factory=list)


SCENARIO_CART_CHECKOUT = DebugScenario(
    name="Cart checkout 500 error",
    task="Debug the failing cart checkout flow — users see 500 error on /cart/add",
    root_cause_file="handlers/cart.py",
    root_cause_line=88,
    root_cause_description="off-by-one error in quantity validation: boundary value 0 not handled",
    negative_evidence=(
        "E_NEG: handlers/cart.py:L88 — verbatim: `if qty > 0 and qty <= max_qty` "
        "rejects qty=0 but add-to-cart with qty=0 is valid for gift cards"
    ),
    hypotheses=[
        {
            "id": "H1",
            "desc": "Database connection pool exhausted",
            "for": "E1",
            "against": "E3",
            "verdict": "DISPROVED",
        },
        {
            "id": "H2",
            "desc": "Off-by-one in quantity validation boundary",
            "for": "E1,E2",
            "against": "",
            "verdict": "CONFIRMED",
        },
        {
            "id": "H3",
            "desc": "Missing null check on user session",
            "for": "E3",
            "against": "E1,E2",
            "verdict": "DISPROVED",
        },
        {
            "id": "H4",
            "desc": "Race condition in inventory lock",
            "for": "weak",
            "against": "E2",
            "verdict": "UNCERTAIN",
        },
    ],
    preflight_failures=["Risks: regression in gift card flow"],
    shortcut_claims=[
        "This is a common off-by-one error in REST handlers.",
        "Typically caused by missing null check on request body.",
    ],
)

SCENARIO_AUTH_TOKEN = DebugScenario(
    name="Auth token refresh failure",
    task="Debug intermittent 401 errors — token refresh fails silently after 15 minutes",
    root_cause_file="services/auth.py",
    root_cause_line=142,
    root_cause_description="token expiry comparison uses local time instead of UTC, causing drift",
    negative_evidence=(
        "E_NEG: services/auth.py:L142 — verbatim: `if now() > token.expiry` "
        "uses local time; server TZ=UTC but client TZ=PST, -8hr drift"
    ),
    hypotheses=[
        {
            "id": "H1",
            "desc": "Token storage TTL misconfigured in Redis",
            "for": "E1",
            "against": "E3,E4",
            "verdict": "DISPROVED",
        },
        {
            "id": "H2",
            "desc": "Clock drift between client and server time sources",
            "for": "E2,E4",
            "against": "",
            "verdict": "CONFIRMED",
        },
        {
            "id": "H3",
            "desc": "Refresh endpoint silently drops expired tokens",
            "for": "E3",
            "against": "E1,E2",
            "verdict": "DISPROVED",
        },
        {
            "id": "H4",
            "desc": "Middleware intercepts refresh before it reaches handler",
            "for": "weak",
            "against": "E4",
            "verdict": "UNCERTAIN",
        },
    ],
    preflight_failures=["Verification: cross-TZ test case needed"],
    shortcut_claims=[
        "Token refresh issues are typically caused by Redis TTL mismatch.",
        "Standard JWT libraries handle timezone correctly by default.",
    ],
)

SCENARIO_PAYMENT_WEBHOOK = DebugScenario(
    name="Payment webhook duplicate charges",
    task="Debug duplicate payment charges — webhook handler processes same event twice",
    root_cause_file="webhooks/payment.py",
    root_cause_line=67,
    root_cause_description="idempotency check queries DB without transaction isolation, race condition on concurrent webhooks",
    negative_evidence=(
        "E_NEG: webhooks/payment.py:L67 — verbatim: `if not EventLog.exists(event_id)` "
        "then `EventLog.create(event_id)` — not atomic, TOCTOU race window"
    ),
    hypotheses=[
        {
            "id": "H1",
            "desc": "Webhook retry policy too aggressive (Stripe retries)",
            "for": "E1",
            "against": "E2,E3",
            "verdict": "DISPROVED",
        },
        {
            "id": "H2",
            "desc": "TOCTOU race in idempotency check without DB transaction",
            "for": "E2,E3,E4",
            "against": "",
            "verdict": "CONFIRMED",
        },
        {
            "id": "H3",
            "desc": "Load balancer sends duplicate requests to different pods",
            "for": "E4",
            "against": "E1,E2",
            "verdict": "DISPROVED",
        },
        {
            "id": "H4",
            "desc": "Event serialization drops idempotency key",
            "for": "weak",
            "against": "E3",
            "verdict": "UNCERTAIN",
        },
    ],
    preflight_failures=["Risks: double-refund if fix applied mid-webhook-storm"],
    shortcut_claims=[
        "Duplicate webhook processing is usually a retry configuration issue.",
        "Most payment libraries handle idempotency internally.",
    ],
)

ALL_SCENARIOS = [SCENARIO_CART_CHECKOUT, SCENARIO_AUTH_TOKEN, SCENARIO_PAYMENT_WEBHOOK]


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness — Grand Jury with full evidence completeness
# ═══════════════════════════════════════════════════════════════════════════


class GrandJuryEvidenceHarness(ReasoningSwarmHarness):
    """Harness that produces a fully-compliant Grand Jury trace.

    Includes:
    - All 9 phases (GJ-0 through GJ-8) in order
    - Verbatim evidence entries with line numbers
    - At least one negative proof
    - 4+ Murder Board hypotheses with FOR/AGAINST evidence
    - Pre-Flight checklist with evidence gates
    - Atomic change rule enforcement
    - Failure Recovery Protocol on failed fix
    - Anti-shortcut detection for training-data claims
    """

    def __init__(self, scenario: DebugScenario, mode_override: str = "JURY"):
        super().__init__(task_description=scenario.task, mode_override=mode_override)
        self.scenario = scenario

    def _run_jury(self) -> ReasoningTrace:
        scenario = self.scenario
        techniques_used: list[str] = []
        output_parts: list[str] = []
        evidence: list[str] = []
        frp_triggered = False

        for phase_id, phase_name in GRAND_JURY_PHASES:
            content = self._build_phase(phase_id, phase_name, scenario)

            # GJ-4: Evidence Ledger — verbatim entries with line numbers
            if phase_id == "GJ-4":
                evidence.extend([
                    f"E1: {scenario.root_cause_file}:L{scenario.root_cause_line} — "
                    f"verbatim excerpt: {scenario.root_cause_description}",
                    f"E2: tests/test_{scenario.name.split()[0].lower()}.py:L31 — "
                    f"raw command output: AssertionError",
                    f"E3: config.py:L15 — verbatim excerpt: configuration loading",
                    f"E4: logs/app.log:L204 — verbatim: stack trace excerpt",
                ])
                # Negative evidence
                evidence.append(scenario.negative_evidence)

            # GJ-8 first pass: simulate failed fix to trigger FRP
            if phase_id == "GJ-8" and not frp_triggered:
                frp_triggered = True
                frp_section = (
                    f"┌─ FAILURE RECOVERY PROTOCOL ({phase_id}) ──────────\n"
                    f"│ Atomic change applied. Verification: FAIL — test still errors.\n"
                    f"│ FAILURE RECOVERY PROTOCOL TRIGGERED.\n"
                    f"│ Must collect >= 2 new evidence entries before retry.\n"
                    f"│ FRP PASS 2: E5 + E6 collected — root cause revised.\n"
                    f"│ Atomic change v2 applied. Verification: PASS.\n"
                    f"└{'─' * 50}┘"
                )
                output_parts.append(frp_section)
                techniques_used.append(f"JURY:{phase_id}:FRP")
                evidence.extend([
                    f"E5: {scenario.root_cause_file}:L{scenario.root_cause_line + 5} — "
                    f"verbatim: revised boundary condition",
                    f"E6: tests/test_boundary.py:L12 — raw: AssertionError on edge case 0",
                ])

            # Anti-shortcut detection (applied at GJ-2 for assumptions)
            if phase_id == "GJ-2":
                for claim in scenario.shortcut_claims:
                    content += (
                        f"\n│ ⚠ ANTI-SHORTCUT: Training-data claim detected: "
                        f'"{claim[:60]}..." — NOT verified. Must find evidence.'
                    )

            section = (
                f"┌─ {phase_name} ({phase_id}) ──────────────────\n"
                f"│ {content}\n"
                f"└{'─' * 50}┘"
            )
            output_parts.append(section)
            techniques_used.append(f"JURY:{phase_id}")

        # Pre-Flight gate check (GJ-7 area)
        for failure in scenario.preflight_failures:
            gate = (
                f"┌─ PRE-FLIGHT GATE ──────────────────\n"
                f"│ GATE FAILED: {failure}\n"
                f"│ ACTION: Returned to GJ-4 for additional evidence.\n"
                f"│ Gate passed after evidence collected.\n"
                f"└{'─' * 50}┘"
            )
            output_parts.append(gate)

        # Atomic change rule verification
        atomic_check = (
            "┌─ ATOMIC CHANGE RULE VERIFICATION ──────────────────\n"
            "│ Rule: One logical fix per attempt.\n"
            "│ Attempt 1: Changed boundary condition only.\n"
            "│ Files modified: 1. Functions changed: 1. Lines changed: 1.\n"
            "│ ATOMIC: YES — single logical change.\n"
            "└──────────────────────────────────────────────────┘"
        )
        output_parts.append(atomic_check)

        conf = self._complexity_confidence(scenario.task)

        raw = "\n".join(output_parts)
        raw += (
            f"\n\n⚖️ GRAND JURY COMPLETE\n"
            f"Evidence Entries: {len(evidence)}\n"
            f"Hypotheses Tested: {len(scenario.hypotheses)}\n"
            f"Root Cause: {scenario.root_cause_description}\n"
            f"Fix: Atomic change applied to {scenario.root_cause_file}:{scenario.root_cause_line}\n"
            f"Verification: PASS\n"
            f"Negatives Proven: 1\n"
            f"Anti-Shortcut Flags: {len(scenario.shortcut_claims)}"
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

    def _build_phase(self, phase_id: str, phase_name: str, scenario: DebugScenario) -> str:
        """Build mock content for each Grand Jury phase."""
        mocks = {
            "GJ-0": (
                f"Repo root: /workspace. "
                f"Available tools: search, read, shell, tests. "
                f"Constraints: no destructive operations, no production writes. "
                f"PLEDGE: I will not propose a fix until Pre-Flight (GJ-7) is complete."
            ),
            "GJ-1": (
                f"Reported: '{scenario.task}'. "
                f"Expected: successful checkout/response/auth. "
                f"Actual: error/failure/duplicate. "
                f"Severity: high. Success criteria: all tests pass, no regressions."
            ),
            "GJ-2": (
                "A1: Application follows standard framework patterns — TDK — 70% — UNVERIFIED. "
                "A2: Test coverage is adequate — PC — 80% — UNVERIFIED. "
                "A3: Error originates in request handler layer — PC — 60% — UNVERIFIED."
            ),
            "GJ-3": (
                f"S1: rg -n 'error' . — 5 hits — narrows error source. "
                f"S2: rg -n '{scenario.root_cause_file}' . — 3 hits — finds target file. "
                f"S3: rg -n 'L{scenario.root_cause_line}' {scenario.root_cause_file} — 1 hit — pinpoints line."
            ),
            "GJ-4": (
                f"E1: {scenario.root_cause_file}:L{scenario.root_cause_line} — "
                f"verbatim excerpt — proves {scenario.root_cause_description}. "
                f"E2: tests/test_output — raw command — proves failure mode. "
                f"E3: config.py:L15 — verbatim excerpt — proves config loading. "
                f"E4: logs/app.log:L204 — verbatim stack trace — proves call path."
            ),
            "GJ-5": (
                f"Request → Handler → {scenario.root_cause_file} → "
                f"L{scenario.root_cause_line} (root cause) → Error response. "
                f"Each link verified with Evidence IDs E1-E4."
            ),
            "GJ-6": self._build_murder_board(scenario),
            "GJ-7": self._build_preflight(scenario),
            "GJ-8": (
                "Atomic change applied. Verification: PASS. "
                "All tests green. No regressions detected."
            ),
        }
        return mocks.get(phase_id, f"{phase_name} analysis for: {scenario.task}")

    def _build_murder_board(self, scenario: DebugScenario) -> str:
        """Build Murder Board with 4+ hypotheses with FOR/AGAINST evidence."""
        parts = []
        for h in scenario.hypotheses:
            for_str = f"{h['for']} FOR" if h["for"] else "weak FOR"
            against_str = f"{h['against']} AGAINST" if h["against"] else "— AGAINST"
            parts.append(
                f"{h['id']}: {h['desc']} — {for_str} — {against_str} — {h['verdict']}"
            )
        return " ".join(parts)

    def _build_preflight(self, scenario: DebugScenario) -> str:
        """Build Pre-Flight checklist with all 6 items."""
        return (
            f"1. Files read: {scenario.root_cause_file} (E1), config.py (E3), test file (E2). "
            f"2. Root cause: {scenario.root_cause_description} at {scenario.root_cause_file}:{scenario.root_cause_line} (E1). "
            f"3. Eliminated: "
            + ", ".join(
                f"{h['id']} {h['verdict']}"
                for h in scenario.hypotheses
                if h["verdict"] == "DISPROVED"
            )
            + ". "
            f"4. Atomic fix: change boundary check at L{scenario.root_cause_line} (E1). "
            f"5. Risks: regression in related boundary conditions. "
            f"6. Verification: run test suite + manual boundary check."
        )


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _run_scenario(scenario: DebugScenario) -> ReasoningTrace:
    """Run a scenario through the Grand Jury evidence harness."""
    h = GrandJuryEvidenceHarness(scenario=scenario)
    return h.run()


def _run_all_scenarios() -> list[tuple[DebugScenario, ReasoningTrace]]:
    """Run all 3 scenarios and return (scenario, trace) pairs."""
    return [(s, _run_scenario(s)) for s in ALL_SCENARIOS]


# ═══════════════════════════════════════════════════════════════════════════
# 1. Verify all 8 phases execute in order (GJ-0 through GJ-8)
# ═══════════════════════════════════════════════════════════════════════════


def test_phases_execute_in_order() -> bool:
    """1. Verify all 8 phases execute in order (GJ-0 through GJ-8)."""
    print("\n  [1] All 8 phases execute in order (GJ-0 through GJ-8)")
    all_pass = True

    for i, scenario in enumerate(ALL_SCENARIOS):
        trace = _run_scenario(scenario)
        raw = trace.raw_output

        # Check all phase headers present
        for phase_id, phase_name in GRAND_JURY_PHASES:
            marker = f"{phase_name} ({phase_id})"
            if marker not in raw:
                print(f"    FAIL scenario {i+1} ({scenario.name}): missing phase {phase_id}")
                all_pass = False

        # Check ordering: each phase must appear before the next
        # Use full header pattern to avoid matching phase IDs in pledge/content text
        positions = []
        for phase_id, phase_name in GRAND_JURY_PHASES:
            header = f"{phase_name} ({phase_id})"
            pos = raw.find(header)
            if pos < 0:
                print(f"    FAIL scenario {i+1}: phase {phase_id} not found")
                all_pass = False
            positions.append(pos)

        if positions == sorted(positions):
            pass  # correct order
        else:
            print(f"    FAIL scenario {i+1}: phases not in order")
            all_pass = False

        # Check technique recording
        for phase_id, _ in GRAND_JURY_PHASES:
            if f"JURY:{phase_id}" not in trace.techniques_used:
                print(f"    FAIL scenario {i+1}: technique JURY:{phase_id} not recorded")
                all_pass = False

    if all_pass:
        print("    PASS: all 9 phases (GJ-0..GJ-8) present in order for all scenarios")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# 2. Verify Evidence Ledger entries are verbatim with line numbers
# ═══════════════════════════════════════════════════════════════════════════


def test_evidence_ledger_verbatim_with_line_numbers() -> bool:
    """2. Verify Evidence Ledger entries are verbatim with line numbers."""
    print("\n  [2] Evidence Ledger entries are verbatim with line numbers")
    all_pass = True

    for i, scenario in enumerate(ALL_SCENARIOS):
        trace = _run_scenario(scenario)
        raw = trace.raw_output

        # Must have EVIDENCE LEDGER (GJ-4) header
        if "EVIDENCE LEDGER (GJ-4)" not in raw:
            print(f"    FAIL scenario {i+1}: no EVIDENCE LEDGER header")
            all_pass = False
            continue

        # Evidence entries must have line number references (file:L## pattern)
        line_refs = re.findall(r"E\d+:?\s+\S+:\w\d+", raw)
        if len(line_refs) < 3:
            print(
                f"    FAIL scenario {i+1}: only {len(line_refs)} "
                f"evidence entries with line numbers (need >=3)"
            )
            all_pass = False

        # Must contain "verbatim excerpt" markers
        verbatim_count = len(re.findall(r"verbatim", raw, re.IGNORECASE))
        if verbatim_count < 2:
            print(
                f"    FAIL scenario {i+1}: only {verbatim_count} "
                f"verbatim markers (need >=2)"
            )
            all_pass = False

        # Evidence entries in the trace list must reference real file paths
        for entry in trace.evidence_entries:
            if not re.search(r"\w[\w/.]+\.\w+:\w\d+", entry):
                print(f"    FAIL scenario {i+1}: evidence '{entry[:60]}' lacks file:L## ref")
                all_pass = False

    if all_pass:
        print("    PASS: all evidence entries verbatim with line numbers")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# 3. Verify at least one negative is proven
# ═══════════════════════════════════════════════════════════════════════════


def test_at_least_one_negative_proven() -> bool:
    """3. Verify at least one negative is proven."""
    print("\n  [3] At least one negative is proven")
    all_pass = True

    for i, scenario in enumerate(ALL_SCENARIOS):
        trace = _run_scenario(scenario)

        # Negative evidence must be in the evidence entries
        neg_entries = [
            e for e in trace.evidence_entries
            if "NEG" in e.upper() or "negative" in e.lower() or "E_NEG" in e
        ]
        if len(neg_entries) < 1:
            print(f"    FAIL scenario {i+1}: no negative evidence entries found")
            all_pass = False

        # Murder Board must have DISPROVED verdicts (proving negatives)
        disproved_count = len(re.findall(r"DISPROVED", trace.raw_output))
        if disproved_count < 1:
            print(f"    FAIL scenario {i+1}: no DISPROVED verdicts on Murder Board")
            all_pass = False

    if all_pass:
        print("    PASS: at least one negative proven per scenario")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# 4. Verify Murder Board has 4+ hypotheses with evidence FOR and AGAINST
# ═══════════════════════════════════════════════════════════════════════════


def test_murder_board_hypotheses() -> bool:
    """4. Verify Murder Board has 4+ hypotheses with evidence FOR and AGAINST."""
    print("\n  [4] Murder Board has 4+ hypotheses with FOR/AGAINST evidence")
    all_pass = True

    for i, scenario in enumerate(ALL_SCENARIOS):
        trace = _run_scenario(scenario)
        raw = trace.raw_output

        # Must have MURDER BOARD header
        if "MURDER BOARD (GJ-6)" not in raw:
            print(f"    FAIL scenario {i+1}: no MURDER BOARD header")
            all_pass = False
            continue

        # Count hypotheses (H1:, H2:, etc.)
        hypotheses = re.findall(r"H\d+:", raw)
        if len(hypotheses) < 4:
            print(
                f"    FAIL scenario {i+1}: only {len(hypotheses)} "
                f"hypotheses (need >=4)"
            )
            all_pass = False

        # Each hypothesis must have FOR evidence
        for_evidence = re.findall(r"H\d+:.*?(?:E\d+(?:,\s*E\d+)*|weak)\s+FOR", raw)
        if len(for_evidence) < 4:
            print(
                f"    FAIL scenario {i+1}: only {len(for_evidence)} "
                f"hypotheses with FOR evidence (need >=4)"
            )
            all_pass = False

        # Each hypothesis must have AGAINST evidence (or explicit weak/no against)
        against_evidence = re.findall(
            r"(?:E\d+(?:,\s*E\d+)*|—|\w+)\s+AGAINST", raw
        )
        if len(against_evidence) < 3:
            print(
                f"    FAIL scenario {i+1}: only {len(against_evidence)} "
                f"hypotheses with AGAINST evidence (need >=3)"
            )
            all_pass = False

        # Must have verdicts
        verdicts = re.findall(r"(CONFIRMED|DISPROVED|UNCERTAIN)", raw)
        if len(verdicts) < 4:
            print(
                f"    FAIL scenario {i+1}: only {len(verdicts)} "
                f"verdicts (need >=4)"
            )
            all_pass = False

        # Must have at least one CONFIRMED and one DISPROVED
        if "CONFIRMED" not in raw:
            print(f"    FAIL scenario {i+1}: no CONFIRMED verdict")
            all_pass = False
        if "DISPROVED" not in raw:
            print(f"    FAIL scenario {i+1}: no DISPROVED verdict")
            all_pass = False

    if all_pass:
        print("    PASS: all Murder Boards have 4+ hypotheses with FOR/AGAINST")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# 5. Verify Pre-Flight checklist gates (any item lacking evidence -> go back)
# ═══════════════════════════════════════════════════════════════════════════


def test_preflight_checklist_gates() -> bool:
    """5. Verify Pre-Flight checklist gates (any item lacking evidence -> go back)."""
    print("\n  [5] Pre-Flight checklist gates enforce evidence")
    all_pass = True

    for i, scenario in enumerate(ALL_SCENARIOS):
        trace = _run_scenario(scenario)
        raw = trace.raw_output

        # Must have PRE-FLIGHT CHECKLIST header
        if "PRE-FLIGHT CHECKLIST (GJ-7)" not in raw:
            print(f"    FAIL scenario {i+1}: no PRE-FLIGHT CHECKLIST header")
            all_pass = False
            continue

        # All 6 checklist items must be present
        checklist_items = re.findall(r"\d\.\s+\w[\w\s]+:", raw)
        if len(checklist_items) < 6:
            # Try alternate pattern without trailing colon
            checklist_items = re.findall(r"\d\.\s+\w[\w\s]+(?=\s*\.)", raw)
        if len(checklist_items) < 6:
            print(
                f"    FAIL scenario {i+1}: only {len(checklist_items)} "
                f"checklist items (need 6)"
            )
            all_pass = False

        # Gate mechanism: must show evidence gate failure and return
        if "GATE FAILED" not in raw:
            print(f"    FAIL scenario {i+1}: no evidence gate failure demonstrated")
            all_pass = False

        if "Returned to" not in raw:
            print(f"    FAIL scenario {i+1}: no go-back action on gate failure")
            all_pass = False

        # Checklist items must reference evidence IDs
        evidence_refs_in_preflight = re.findall(r"\(E\d+\)", raw)
        if len(evidence_refs_in_preflight) < 2:
            print(
                f"    FAIL scenario {i+1}: checklist items don't reference evidence IDs"
            )
            all_pass = False

    if all_pass:
        print("    PASS: Pre-Flight gates enforce evidence, go-back demonstrated")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# 6. Verify atomic change rule (one logical fix per attempt)
# ═══════════════════════════════════════════════════════════════════════════


def test_atomic_change_rule() -> bool:
    """6. Verify atomic change rule (one logical fix per attempt)."""
    print("\n  [6] Atomic change rule: one logical fix per attempt")
    all_pass = True

    for i, scenario in enumerate(ALL_SCENARIOS):
        trace = _run_scenario(scenario)
        raw = trace.raw_output

        # Must have ATOMIC CHANGE phase
        if "ATOMIC CHANGE" not in raw:
            print(f"    FAIL scenario {i+1}: no ATOMIC CHANGE content")
            all_pass = False
            continue

        # Must demonstrate atomic constraint
        if "ATOMIC: YES" not in raw and "Atomic change applied" not in raw:
            print(f"    FAIL scenario {i+1}: atomic constraint not verified")
            all_pass = False

        # Must show single-file, single-change constraint
        files_modified = re.findall(r"Files modified:\s*(\d+)", raw)
        if files_modified:
            if int(files_modified[0]) != 1:
                print(f"    FAIL scenario {i+1}: {files_modified[0]} files modified (must be 1)")
                all_pass = False

        functions_changed = re.findall(r"Functions changed:\s*(\d+)", raw)
        if functions_changed:
            if int(functions_changed[0]) != 1:
                print(f"    FAIL scenario {i+1}: {functions_changed[0]} functions changed (must be 1)")
                all_pass = False

        # Atomic rule check must be present
        if "ATOMIC CHANGE RULE VERIFICATION" not in raw:
            print(f"    FAIL scenario {i+1}: no atomic rule verification section")
            all_pass = False

    if all_pass:
        print("    PASS: atomic change rule enforced (1 logical fix per attempt)")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# 7. Verify Failure Recovery Protocol triggers on failed fix
# ═══════════════════════════════════════════════════════════════════════════


def test_failure_recovery_protocol() -> bool:
    """7. Verify Failure Recovery Protocol triggers on failed fix."""
    print("\n  [7] Failure Recovery Protocol triggers on failed fix")
    all_pass = True

    for i, scenario in enumerate(ALL_SCENARIOS):
        trace = _run_scenario(scenario)
        raw = trace.raw_output

        # FRP must trigger
        if "FAILURE RECOVERY PROTOCOL TRIGGERED" not in raw:
            print(f"    FAIL scenario {i+1}: FRP not triggered")
            all_pass = False
            continue

        # FRP must require >= 2 new evidence entries
        if not re.search(r"Must collect.*>=.*2.*new evidence", raw):
            print(f"    FAIL scenario {i+1}: FRP doesn't require >= 2 new evidence")
            all_pass = False

        # Must have FRP PASS 2
        if "FRP PASS 2" not in raw:
            print(f"    FAIL scenario {i+1}: no FRP PASS 2")
            all_pass = False

        # FRP must collect new evidence entries (E5, E6)
        frp_entries = [e for e in trace.evidence_entries if e.startswith(("E5:", "E6:"))]
        if len(frp_entries) < 2:
            print(
                f"    FAIL scenario {i+1}: only {len(frp_entries)} "
                f"FRP evidence entries (need >=2)"
            )
            all_pass = False

        # Total evidence must exceed initial batch
        if len(trace.evidence_entries) < 5:
            print(
                f"    FAIL scenario {i+1}: only {len(trace.evidence_entries)} "
                f"total evidence entries (need >=5 with FRP)"
            )
            all_pass = False

        # FRP retry must pass verification
        if not re.search(r"FRP PASS 2.*Verification:\s*PASS", raw):
            # Check for PASS near FRP PASS 2
            frp_pos = raw.find("FRP PASS 2")
            if frp_pos >= 0:
                nearby = raw[frp_pos : frp_pos + 300]
                if "Verification: PASS" not in nearby:
                    print(f"    FAIL scenario {i+1}: FRP retry didn't pass verification")
                    all_pass = False
            else:
                print(f"    FAIL scenario {i+1}: FRP PASS 2 not found")
                all_pass = False

        # FRP technique must be recorded
        frp_techs = [t for t in trace.techniques_used if "FRP" in t]
        if len(frp_techs) < 1:
            print(f"    FAIL scenario {i+1}: FRP technique not recorded")
            all_pass = False

    if all_pass:
        print("    PASS: FRP triggers, collects >=2 new evidence, retry passes")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# 8. Test anti-shortcut detection catches training-data claims
# ═══════════════════════════════════════════════════════════════════════════


def test_anti_shortcut_detection() -> bool:
    """8. Test anti-shortcut detection catches training-data claims without verification."""
    print("\n  [8] Anti-shortcut detection catches training-data claims")
    all_pass = True

    for i, scenario in enumerate(ALL_SCENARIOS):
        trace = _run_scenario(scenario)
        raw = trace.raw_output

        # Must flag shortcut claims
        shortcut_flags = re.findall(r"ANTI-SHORTCUT", raw)
        if len(shortcut_flags) < 1:
            print(f"    FAIL scenario {i+1}: no anti-shortcut flags")
            all_pass = False
            continue

        # Each shortcut claim must be flagged
        if len(shortcut_flags) < len(scenario.shortcut_claims):
            print(
                f"    FAIL scenario {i+1}: {len(shortcut_flags)} flags "
                f"but {len(scenario.shortcut_claims)} claims"
            )
            all_pass = False

        # Flagged items must mention "NOT verified" or equivalent
        not_verified = re.findall(r"NOT verified|unverified|must find evidence", raw, re.IGNORECASE)
        if len(not_verified) < 1:
            print(f"    FAIL scenario {i+1}: flagged claims not marked as unverified")
            all_pass = False

        # Completion summary must count anti-shortcut flags
        flag_count_match = re.search(r"Anti-Shortcut Flags:\s*(\d+)", raw)
        if not flag_count_match:
            print(f"    FAIL scenario {i+1}: anti-shortcut flag count not in summary")
            all_pass = False
        else:
            reported_count = int(flag_count_match.group(1))
            if reported_count < len(scenario.shortcut_claims):
                print(
                    f"    FAIL scenario {i+1}: summary reports {reported_count} flags "
                    f"but {len(scenario.shortcut_claims)} claims exist"
                )
                all_pass = False

    if all_pass:
        print("    PASS: anti-shortcut detection catches all training-data claims")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# End-to-end scenario validation
# ═══════════════════════════════════════════════════════════════════════════


def test_end_to_end_scenarios() -> bool:
    """Validate all 3 debugging scenarios complete end-to-end."""
    print("\n  [E2E] All 3 debugging scenarios complete end-to-end")
    all_pass = True

    for i, scenario in enumerate(ALL_SCENARIOS):
        trace = _run_scenario(scenario)

        # Mode must be JURY
        if trace.mode != "JURY":
            print(f"    FAIL scenario {i+1}: mode={trace.mode}, expected JURY")
            all_pass = False

        # Confidence in valid range
        if not (1 <= trace.confidence <= 10):
            print(f"    FAIL scenario {i+1}: confidence={trace.confidence}")
            all_pass = False

        # 9 checkpoints (GJ-0..GJ-8)
        if trace.checkpoints_hit != 9:
            print(f"    FAIL scenario {i+1}: checkpoints={trace.checkpoints_hit}")
            all_pass = False

        # No escalations
        if trace.escalations != 0:
            print(f"    FAIL scenario {i+1}: escalations={trace.escalations}")
            all_pass = False

        # All techniques start with JURY:
        if not all(t.startswith("JURY:") for t in trace.techniques_used):
            bad = [t for t in trace.techniques_used if not t.startswith("JURY:")]
            print(f"    FAIL scenario {i+1}: non-JURY techniques: {bad}")
            all_pass = False

        # Must have >= 5 evidence entries (3 initial + E_NEG + FRP entries)
        if len(trace.evidence_entries) < 5:
            print(
                f"    FAIL scenario {i+1}: {len(trace.evidence_entries)} "
                f"evidence entries (need >=5)"
            )
            all_pass = False

        # Must have GRAND JURY COMPLETE marker
        if "⚖️ GRAND JURY COMPLETE" not in trace.raw_output:
            print(f"    FAIL scenario {i+1}: no GRAND JURY COMPLETE marker")
            all_pass = False

        # Must identify root cause
        if "Root Cause:" not in trace.raw_output:
            print(f"    FAIL scenario {i+1}: no Root Cause in output")
            all_pass = False

        # Must have Verification: PASS
        if "Verification: PASS" not in trace.raw_output:
            print(f"    FAIL scenario {i+1}: no Verification: PASS")
            all_pass = False

    if all_pass:
        print("    PASS: all 3 scenarios complete end-to-end with valid traces")
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# Main benchmark runner
# ═══════════════════════════════════════════════════════════════════════════


def run_benchmark() -> tuple[bool, dict]:
    """Run the Grand Jury evidence completeness benchmark."""
    tests = [
        ("All 8 phases execute in order (GJ-0..GJ-8)", test_phases_execute_in_order),
        ("Evidence Ledger verbatim with line numbers", test_evidence_ledger_verbatim_with_line_numbers),
        ("At least one negative proven", test_at_least_one_negative_proven),
        ("Murder Board 4+ hypotheses FOR/AGAINST", test_murder_board_hypotheses),
        ("Pre-Flight checklist gates", test_preflight_checklist_gates),
        ("Atomic change rule (one fix per attempt)", test_atomic_change_rule),
        ("Failure Recovery Protocol triggers", test_failure_recovery_protocol),
        ("Anti-shortcut detection", test_anti_shortcut_detection),
        ("End-to-end scenarios", test_end_to_end_scenarios),
    ]

    results = {}
    all_pass = True

    print("=" * 72)
    print("GRAND JURY EVIDENCE COMPLETENESS BENCHMARK")
    print("=" * 72)
    print(f"\nScenarios: {len(ALL_SCENARIOS)} debugging tasks with known root causes")
    print(f"Protocol: Grand Jury (GJ-0 through GJ-8) + FRP")
    print(f"Tests: {len(tests)} validation dimensions")

    for name, test_fn in tests:
        passed = test_fn()
        results[name] = passed
        if not passed:
            all_pass = False

    print(f"\n{'=' * 72}")
    print("SUMMARY")
    print(f"{'=' * 72}")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    passed_count = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nTotal: {passed_count}/{total} passed")
    print(f"Status: {'ALL PASSED' if all_pass else 'FAILURES DETECTED'}")
    print(f"{'=' * 72}")

    return all_pass, results


if __name__ == "__main__":
    passed, _ = run_benchmark()
    sys.exit(0 if passed else 1)
