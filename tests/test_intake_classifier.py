"""
Intake classifier unit tests — validates the Phase 0 auto-select matrix
from skills/reasoning-swarm-SKILL.md.

The classify_task() function is reusable by other test files.
"""

import pytest

# ---------------------------------------------------------------------------
# classify_task — pure-Python intake classifier
# ---------------------------------------------------------------------------

MODES = ["RAPID STRIKE", "DEEP THINK", "ENSEMBLE", "MEGAMIND", "GRAND JURY"]


def _escalate(mode: str) -> str:
    """Escalate one level in the mode ladder."""
    idx = MODES.index(mode)
    return MODES[min(idx + 1, len(MODES) - 1)]


def classify_task(
    task_type: str | None,
    complexity: str | None,
    stakes: str | None,
    prior_fails: int,
    files_involved: int,
    framework_css: bool,
    production: bool,
    user_hint: str | None = None,
) -> str:
    """Return the reasoning-swarm mode string for a task.

    Pure-Python, no I/O.  Implements the AUTO-SELECT MATRIX and override
    rules from reasoning-swarm-SKILL.md Phase 0.
    """
    # Normalise
    task_type = (task_type or "").upper()
    complexity = (complexity or "UNKNOWN").upper()
    stakes = (stakes or "LOW").upper()
    prior_fails = prior_fails or 0
    files_involved = files_involved or 1
    framework_css = bool(framework_css)
    production = bool(production)
    user_hint = (user_hint or "").lower().strip()

    # Treat empty / None / UNKNOWN as UNKNOWN
    if not task_type or task_type == "UNKNOWN":
        task_type = "UNKNOWN"

    multi_file = files_involved >= 3
    is_bug_debug = task_type in ("BUG_FIX", "DEBUGGING")

    # ------------------------------------------------------------------
    # 1. GRAND JURY forced conditions  (checked first, override all)
    # ------------------------------------------------------------------
    if is_bug_debug and prior_fails >= 1:
        return "GRAND JURY"
    if is_bug_debug and framework_css and multi_file:
        return "GRAND JURY"
    if task_type == "INVESTIGATION":
        return "GRAND JURY"
    if production and stakes in ("MEDIUM", "HIGH", "CRITICAL"):
        return "GRAND JURY"

    # ------------------------------------------------------------------
    # 2. Base classification  (AUTO-SELECT MATRIX rows)
    # ------------------------------------------------------------------
    if task_type == "UNKNOWN":
        mode = "MEGAMIND"
    elif complexity == "EXTREME" or stakes == "CRITICAL":
        mode = "MEGAMIND"
    elif complexity == "HIGH" or stakes == "HIGH":
        mode = "ENSEMBLE"
    elif complexity == "MEDIUM" or stakes == "MEDIUM":
        mode = "DEEP THINK"
    elif complexity == "LOW" and stakes == "LOW":
        mode = "RAPID STRIKE"
    else:
        mode = "DEEP THINK"

    # ------------------------------------------------------------------
    # 3. User-hint overrides
    # ------------------------------------------------------------------
    if user_hint in ("quick", "just do it"):
        if stakes != "CRITICAL":
            mode = "RAPID STRIKE"

    if "think harder" in user_hint:
        mode = _escalate(mode)

    # ------------------------------------------------------------------
    # 4. Prior-failure floor  (minimum ENSEMBLE)
    # ------------------------------------------------------------------
    if prior_fails >= 1:
        if MODES.index(mode) < MODES.index("ENSEMBLE"):
            mode = "ENSEMBLE"

    return mode


# ======================================================================
# TESTS — 100 % matrix coverage
# ======================================================================


# ----------------------------------------------------------------------
# A. Base matrix: LOW complexity + LOW stakes + no prior fails → RAPID STRIKE
# ----------------------------------------------------------------------
class TestRapidStrike:
    def test_low_low_no_fails(self):
        assert classify_task("IMPLEMENTATION", "LOW", "LOW", 0, 1, False, False) == "RAPID STRIKE"

    def test_low_low_no_fails_bug_fix(self):
        assert classify_task("BUG_FIX", "LOW", "LOW", 0, 1, False, False) == "RAPID STRIKE"

    def test_low_low_no_fails_multiple_files_under_threshold(self):
        assert classify_task("OPTIMIZE", "LOW", "LOW", 0, 2, False, False) == "RAPID STRIKE"


# ----------------------------------------------------------------------
# B. Base matrix: MEDIUM complexity OR MEDIUM stakes → DEEP THINK
# ----------------------------------------------------------------------
class TestDeepThink:
    def test_medium_complexity_low_stakes(self):
        assert classify_task("IMPLEMENTATION", "MEDIUM", "LOW", 0, 1, False, False) == "DEEP THINK"

    def test_low_complexity_medium_stakes(self):
        assert classify_task("IMPLEMENTATION", "LOW", "MEDIUM", 0, 1, False, False) == "DEEP THINK"

    def test_medium_complexity_medium_stakes(self):
        assert classify_task("IMPLEMENTATION", "MEDIUM", "MEDIUM", 0, 1, False, False) == "DEEP THINK"

    def test_medium_complexity_high_stakes(self):
        """HIGH stakes alone would be ENSEMBLE; MEDIUM complexity + HIGH → ENSEMBLE wins."""
        assert classify_task("IMPLEMENTATION", "MEDIUM", "HIGH", 0, 1, False, False) == "ENSEMBLE"


# ----------------------------------------------------------------------
# C. Base matrix: HIGH complexity OR HIGH stakes → ENSEMBLE
# ----------------------------------------------------------------------
class TestEnsemble:
    def test_high_complexity_low_stakes(self):
        assert classify_task("ARCHITECTURE", "HIGH", "LOW", 0, 1, False, False) == "ENSEMBLE"

    def test_low_complexity_high_stakes(self):
        assert classify_task("IMPLEMENTATION", "LOW", "HIGH", 0, 1, False, False) == "ENSEMBLE"

    def test_high_complexity_high_stakes(self):
        assert classify_task("ARCHITECTURE", "HIGH", "HIGH", 0, 1, False, False) == "ENSEMBLE"

    def test_medium_complexity_high_stakes(self):
        """HIGH stakes overrides MEDIUM complexity → ENSEMBLE."""
        assert classify_task("DESIGN", "MEDIUM", "HIGH", 0, 1, False, False) == "ENSEMBLE"


# ----------------------------------------------------------------------
# D. Base matrix: EXTREME complexity OR CRITICAL stakes OR UNKNOWN → MEGAMIND
# ----------------------------------------------------------------------
class TestMegamind:
    def test_extreme_complexity_low_stakes(self):
        assert classify_task("ARCHITECTURE", "EXTREME", "LOW", 0, 1, False, False) == "MEGAMIND"

    def test_low_complexity_critical_stakes(self):
        assert classify_task("IMPLEMENTATION", "LOW", "CRITICAL", 0, 1, False, False) == "MEGAMIND"

    def test_unknown_task_type(self):
        assert classify_task("UNKNOWN", "LOW", "LOW", 0, 1, False, False) == "MEGAMIND"

    def test_empty_task_type_defaults_to_unknown(self):
        assert classify_task("", "LOW", "LOW", 0, 1, False, False) == "MEGAMIND"

    def test_none_task_type_defaults_to_unknown(self):
        assert classify_task(None, "LOW", "LOW", 0, 1, False, False) == "MEGAMIND"

    def test_extreme_and_critical(self):
        assert classify_task("DESIGN", "EXTREME", "CRITICAL", 0, 1, False, False) == "MEGAMIND"


# ----------------------------------------------------------------------
# E. GRAND JURY forced: BUG_FIX/DEBUG + prior fails ≥ 1
# ----------------------------------------------------------------------
class TestGrandJuryBugPriorFails:
    def test_bug_fix_one_prior_fail(self):
        assert classify_task("BUG_FIX", "LOW", "LOW", 1, 1, False, False) == "GRAND JURY"

    def test_debugging_one_prior_fail(self):
        assert classify_task("DEBUGGING", "LOW", "LOW", 1, 1, False, False) == "GRAND JURY"

    def test_bug_fix_two_prior_fails(self):
        assert classify_task("BUG_FIX", "LOW", "LOW", 2, 1, False, False) == "GRAND JURY"

    def test_bug_fix_prior_fails_overrides_extreme(self):
        """GRAND JURY forced takes precedence over EXTREME → MEGAMIND."""
        assert classify_task("BUG_FIX", "EXTREME", "CRITICAL", 1, 1, False, False) == "GRAND JURY"


# ----------------------------------------------------------------------
# F. GRAND JURY forced: BUG_FIX/DEBUG + framework/CSS + multi-file
# ----------------------------------------------------------------------
class TestGrandJuryBugFrameworkMultiFile:
    def test_bug_fix_framework_multi_file(self):
        assert classify_task("BUG_FIX", "LOW", "LOW", 0, 3, True, False) == "GRAND JURY"

    def test_debugging_framework_multi_file(self):
        assert classify_task("DEBUGGING", "MEDIUM", "MEDIUM", 0, 3, True, False) == "GRAND JURY"

    def test_bug_fix_framework_single_file_not_grand_jury(self):
        """Framework/CSS alone without multi-file does NOT trigger GRAND JURY."""
        assert classify_task("BUG_FIX", "LOW", "LOW", 0, 1, True, False) == "RAPID STRIKE"

    def test_bug_fix_multi_file_no_framework_not_grand_jury(self):
        """Multi-file alone without framework/CSS does NOT trigger GRAND JURY."""
        assert classify_task("BUG_FIX", "LOW", "LOW", 0, 3, False, False) == "RAPID STRIKE"


# ----------------------------------------------------------------------
# G. GRAND JURY forced: INVESTIGATION type
# ----------------------------------------------------------------------
class TestGrandJuryInvestigation:
    def test_investigation_low(self):
        assert classify_task("INVESTIGATION", "LOW", "LOW", 0, 1, False, False) == "GRAND JURY"

    def test_investigation_extreme(self):
        """INVESTIGATION always GRAND JURY regardless of complexity."""
        assert classify_task("INVESTIGATION", "EXTREME", "CRITICAL", 0, 6, True, True) == "GRAND JURY"


# ----------------------------------------------------------------------
# H. GRAND JURY forced: PRODUCTION + stakes ≥ MEDIUM
# ----------------------------------------------------------------------
class TestGrandJuryProduction:
    def test_production_medium_stakes(self):
        assert classify_task("IMPLEMENTATION", "LOW", "MEDIUM", 0, 1, False, True) == "GRAND JURY"

    def test_production_high_stakes(self):
        assert classify_task("IMPLEMENTATION", "LOW", "HIGH", 0, 1, False, True) == "GRAND JURY"

    def test_production_critical_stakes(self):
        assert classify_task("IMPLEMENTATION", "LOW", "CRITICAL", 0, 1, False, True) == "GRAND JURY"

    def test_production_low_stakes_not_grand_jury(self):
        """PRODUCTION + LOW stakes does NOT trigger GRAND JURY forced."""
        assert classify_task("IMPLEMENTATION", "LOW", "LOW", 0, 1, False, True) == "RAPID STRIKE"


# ----------------------------------------------------------------------
# I. Override: 'think harder' → escalate one level
# ----------------------------------------------------------------------
class TestThinkHarderOverride:
    def test_rapid_to_deep(self):
        assert classify_task("IMPLEMENTATION", "LOW", "LOW", 0, 1, False, False, "think harder") == "DEEP THINK"

    def test_deep_to_ensemble(self):
        assert classify_task("IMPLEMENTATION", "MEDIUM", "LOW", 0, 1, False, False, "think harder") == "ENSEMBLE"

    def test_ensemble_to_megamind(self):
        assert classify_task("IMPLEMENTATION", "HIGH", "LOW", 0, 1, False, False, "think harder") == "MEGAMIND"

    def test_megamind_to_grand_jury(self):
        assert classify_task("IMPLEMENTATION", "LOW", "CRITICAL", 0, 1, False, False, "think harder") == "GRAND JURY"

    def test_grand_jury_stays_grand_jury(self):
        """Already at the top of the ladder — no further escalation."""
        assert classify_task("INVESTIGATION", "LOW", "LOW", 0, 1, False, False, "think harder") == "GRAND JURY"

    def test_think_harder_with_medium_stakes(self):
        """MEDIUM stakes → DEEP THINK base, + think harder → ENSEMBLE."""
        assert classify_task("IMPLEMENTATION", "LOW", "MEDIUM", 0, 1, False, False, "think harder") == "ENSEMBLE"


# ----------------------------------------------------------------------
# J. Override: 'quick' / 'just do it' → RAPID STRIKE (unless CRITICAL)
# ----------------------------------------------------------------------
class TestQuickOverride:
    def test_quick_from_deep_think(self):
        assert classify_task("IMPLEMENTATION", "MEDIUM", "LOW", 0, 1, False, False, "quick") == "RAPID STRIKE"

    def test_just_do_it_from_ensemble(self):
        assert classify_task("IMPLEMENTATION", "HIGH", "LOW", 0, 1, False, False, "just do it") == "RAPID STRIKE"

    def test_quick_blocked_by_critical_stakes(self):
        """CRITICAL stakes prevent quick override."""
        assert classify_task("IMPLEMENTATION", "LOW", "CRITICAL", 0, 1, False, False, "quick") == "MEGAMIND"

    def test_just_do_it_blocked_by_critical_stakes(self):
        """CRITICAL stakes prevent just-do-it override."""
        assert classify_task("IMPLEMENTATION", "LOW", "CRITICAL", 0, 1, False, False, "just do it") == "MEGAMIND"


# ----------------------------------------------------------------------
# K. Override: prior failure → minimum ENSEMBLE
# ----------------------------------------------------------------------
class TestPriorFailFloor:
    def test_one_prior_fail_upgrades_rapid(self):
        """RAPID STRIKE base with prior fail → floor to ENSEMBLE."""
        assert classify_task("IMPLEMENTATION", "LOW", "LOW", 1, 1, False, False) == "ENSEMBLE"

    def test_two_prior_fails_upgrades_rapid(self):
        assert classify_task("IMPLEMENTATION", "LOW", "LOW", 2, 1, False, False) == "ENSEMBLE"

    def test_one_prior_fail_upgrades_deep_think(self):
        """DEEP THINK base with prior fail → floor to ENSEMBLE."""
        assert classify_task("IMPLEMENTATION", "MEDIUM", "LOW", 1, 1, False, False) == "ENSEMBLE"

    def test_prior_fail_does_not_downgrade_ensemble(self):
        """ENSEMBLE base stays ENSEMBLE (already above floor)."""
        assert classify_task("ARCHITECTURE", "HIGH", "LOW", 1, 1, False, False) == "ENSEMBLE"

    def test_prior_fail_does_not_downgrade_megamind(self):
        """MEGAMIND base stays MEGAMIND (above floor)."""
        assert classify_task("IMPLEMENTATION", "EXTREME", "LOW", 1, 1, False, False) == "MEGAMIND"

    def test_bug_fix_prior_fail_is_grand_jury(self):
        """BUG_FIX + prior fail → forced GRAND JURY (not just ENSEMBLE floor)."""
        assert classify_task("BUG_FIX", "LOW", "LOW", 1, 1, False, False) == "GRAND JURY"


# ----------------------------------------------------------------------
# L. Combined / interaction tests
# ----------------------------------------------------------------------
class TestInteractions:
    def test_think_harder_plus_prior_fail(self):
        """Think harder escalates RAPID → DEEP, then prior fail floor → ENSEMBLE."""
        assert classify_task("IMPLEMENTATION", "LOW", "LOW", 1, 1, False, False, "think harder") == "ENSEMBLE"

    def test_quick_plus_prior_fail(self):
        """Quick forces RAPID, then prior fail floor → ENSEMBLE."""
        assert classify_task("IMPLEMENTATION", "MEDIUM", "MEDIUM", 1, 1, False, False, "quick") == "ENSEMBLE"

    def test_production_high_stakes_trumps_high_complexity(self):
        """PRODUCTION + HIGH stakes → GRAND JURY forced (overrides HIGH → ENSEMBLE)."""
        assert classify_task("DESIGN", "HIGH", "HIGH", 0, 1, False, True) == "GRAND JURY"

    def test_extreme_complexity_with_medium_stakes(self):
        """EXTREME → MEGAMIND regardless of stakes being only MEDIUM."""
        assert classify_task("ARCHITECTURE", "EXTREME", "MEDIUM", 0, 1, False, False) == "MEGAMIND"

    def test_all_12_task_types_default_routing(self):
        """Every task type routes correctly with identical LOW/LOW/0 params."""
        expected_rapid = {"IMPLEMENTATION", "OPTIMIZE", "CREATIVE", "ANALYSIS",
                          "PLANNING", "DESIGN", "RESEARCH", "ARCHITECTURE"}
        expected_megamind = {"UNKNOWN"}
        expected_grand_jury = {"INVESTIGATION"}
        expected_rapid_bug = {"BUG_FIX", "DEBUGGING"}  # no prior fails → RAPID

        for tt in expected_rapid:
            assert classify_task(tt, "LOW", "LOW", 0, 1, False, False) == "RAPID STRIKE", tt
        for tt in expected_megamind:
            assert classify_task(tt, "LOW", "LOW", 0, 1, False, False) == "MEGAMIND", tt
        for tt in expected_grand_jury:
            assert classify_task(tt, "LOW", "LOW", 0, 1, False, False) == "GRAND JURY", tt
        for tt in expected_rapid_bug:
            assert classify_task(tt, "LOW", "LOW", 0, 1, False, False) == "RAPID STRIKE", tt

    def test_boundary_multi_file_threshold(self):
        """files_involved=2 is NOT multi-file; files_involved=3 IS."""
        assert classify_task("BUG_FIX", "LOW", "LOW", 0, 2, True, False) == "RAPID STRIKE"
        assert classify_task("BUG_FIX", "LOW", "LOW", 0, 3, True, False) == "GRAND JURY"

    def test_complexity_none_defaults_unknown(self):
        """None complexity defaults to UNKNOWN string, falls to DEEP THINK (safe default)."""
        assert classify_task("IMPLEMENTATION", None, "LOW", 0, 1, False, False) == "DEEP THINK"

    def test_stakes_none_defaults_low(self):
        """None stakes defaults to LOW."""
        assert classify_task("IMPLEMENTATION", "LOW", None, 0, 1, False, False) == "RAPID STRIKE"
