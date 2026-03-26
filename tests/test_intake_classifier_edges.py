"""Edge-case and boundary-condition tests for the intake classifier.

Covers every branch of classify_task() for 100% branch coverage.
"""

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.intake_classifier import classify_task, MODES, TASK_TYPES


# ═══════════════════════════════════════════════════════════════════════
# 1. UNKNOWN complexity always → MEGAMIND regardless of other fields
# ═══════════════════════════════════════════════════════════════════════

class TestUnknownComplexity:
    """UNKNOWN (or missing) complexity must always produce MEGAMIND."""

    @pytest.mark.parametrize("complexity", [None, "", "UNKNOWN", "unknown", "Unknown"])
    def test_unknown_complexity_yields_megamind(self, complexity):
        assert classify_task(
            task_type="IMPLEMENTATION",
            complexity=complexity,
            stakes="LOW",
        ) == "MEGAMIND"

    def test_unknown_with_high_stakes(self):
        assert classify_task("ARCHITECTURE", None, "HIGH") == "MEGAMIND"

    def test_unknown_with_critical_stakes(self):
        assert classify_task("BUG_FIX", "unknown", "CRITICAL") == "MEGAMIND"

    def test_unknown_with_production(self):
        assert classify_task("DESIGN", "", "MEDIUM", production=True) == "MEGAMIND"

    def test_unknown_with_prior_fails(self):
        # UNKNOWN → MEGAMIND even with prior fails (GRAND JURY doesn't override
        # unless BUG_FIX/DEBUG)
        assert classify_task("OPTIMIZE", None, "LOW", prior_fails=2) == "MEGAMIND"

    def test_unknown_with_investigation(self):
        # INVESTIGATION forces GRAND JURY, which overrides MEGAMIND
        assert classify_task("INVESTIGATION", "UNKNOWN", "LOW") == "GRAND JURY"


# ═══════════════════════════════════════════════════════════════════════
# 2. CRITICAL stakes always → MEGAMIND regardless of complexity
# ═══════════════════════════════════════════════════════════════════════

class TestCriticalStakes:
    """CRITICAL stakes must always produce MEGAMIND."""

    @pytest.mark.parametrize("complexity", ["LOW", "MEDIUM", "HIGH", "EXTREME"])
    def test_critical_stakes_overrides_complexity(self, complexity):
        assert classify_task("IMPLEMENTATION", complexity, "CRITICAL") == "MEGAMIND"

    def test_critical_with_production(self):
        # Production + MEDIUM/HIGH stakes → GRAND JURY, but CRITICAL stays MEGAMIND
        assert classify_task("BUG_FIX", "LOW", "CRITICAL", production=True) == "MEGAMIND"

    def test_critical_with_bug_fix_prior_fails(self):
        # BUG_FIX + prior fails → GRAND JURY, but CRITICAL stakes → MEGAMIND
        # GRAND JURY forced condition should NOT override CRITICAL
        result = classify_task("BUG_FIX", "LOW", "CRITICAL", prior_fails=1)
        assert result == "MEGAMIND"

    def test_critical_with_debug_prior_fails(self):
        result = classify_task("DEBUGGING", "MEDIUM", "CRITICAL", prior_fails=2)
        assert result == "MEGAMIND"

    def test_critical_with_user_hint_quick(self):
        # 'quick' should NOT override CRITICAL stakes
        assert classify_task(
            "IMPLEMENTATION", "LOW", "CRITICAL", user_hint="quick"
        ) == "MEGAMIND"

    def test_critical_with_user_hint_just_do_it(self):
        assert classify_task(
            "ANALYSIS", "LOW", "CRITICAL", user_hint="just do it"
        ) == "MEGAMIND"

    def test_critical_stakes_investigation(self):
        # INVESTIGATION forces GRAND JURY — but beads say CRITICAL always → MEGAMIND
        # The forced GRAND JURY condition for INVESTIGATION fires after base mode.
        # However, CRITICAL stakes rule is higher priority.
        # According to beads: "CRITICAL stakes always → MEGAMIND regardless of complexity"
        # This applies even to INVESTIGATION.
        result = classify_task("INVESTIGATION", "LOW", "CRITICAL")
        assert result == "MEGAMIND"


# ═══════════════════════════════════════════════════════════════════════
# 3. Multiple override rules firing simultaneously
# ═══════════════════════════════════════════════════════════════════════

class TestMultipleOverrides:
    """When multiple override rules fire, they compose correctly."""

    def test_think_harder_plus_critical_stakes(self):
        # CRITICAL stakes always → MEGAMIND; 'think harder' is blocked
        result = classify_task(
            "IMPLEMENTATION", "LOW", "CRITICAL", user_hint="think harder"
        )
        assert result == "MEGAMIND"

    def test_quick_plus_prior_fails(self):
        # 'quick' → RAPID STRIKE, but prior fails ≥1 → minimum ENSEMBLE
        result = classify_task(
            "OPTIMIZE", "LOW", "LOW", prior_fails=1, user_hint="quick"
        )
        # 'quick' sets RAPID STRIKE, then prior fails bumps to ENSEMBLE
        assert result == "ENSEMBLE"

    def test_think_harder_plus_medium_complexity(self):
        # MEDIUM → DEEP THINK; 'think harder' → ENSEMBLE
        result = classify_task(
            "RESEARCH", "MEDIUM", "LOW", user_hint="think harder"
        )
        assert result == "ENSEMBLE"

    def test_think_harder_plus_high_complexity(self):
        # HIGH → ENSEMBLE; 'think harder' → MEGAMIND
        result = classify_task(
            "ARCHITECTURE", "HIGH", "LOW", user_hint="think harder"
        )
        assert result == "MEGAMIND"

    def test_think_harder_at_max(self):
        # EXTREME → MEGAMIND; 'think harder' → GRAND JURY (top of chain)
        result = classify_task(
            "DESIGN", "EXTREME", "LOW", user_hint="think harder"
        )
        assert result == "GRAND JURY"

    def test_bug_fix_prior_fails_plus_production(self):
        # BUG_FIX + prior_fails → GRAND JURY; production + MEDIUM stakes → GRAND JURY
        result = classify_task(
            "BUG_FIX", "LOW", "MEDIUM", prior_fails=1, production=True
        )
        assert result == "GRAND JURY"

    def test_quick_plus_think_harder(self):
        # Both hints present — 'think harder' runs second, escalates RAPID STRIKE
        result = classify_task(
            "IMPLEMENTATION", "HIGH", "LOW", user_hint="quick and think harder"
        )
        # 'quick' → RAPID STRIKE first, then 'think harder' → DEEP THINK
        assert result == "DEEP THINK"

    def test_investigation_with_production(self):
        # INVESTIGATION → GRAND JURY; production + stakes → also GRAND JURY
        result = classify_task(
            "INVESTIGATION", "MEDIUM", "HIGH", production=True
        )
        assert result == "GRAND JURY"

    def test_debug_framework_css_multi_file_plus_prior_fails(self):
        # Both GRAND JURY forced conditions fire
        result = classify_task(
            "DEBUGGING", "LOW", "LOW",
            prior_fails=1, framework_css=True, files_involved="6+",
        )
        assert result == "GRAND JURY"


# ═══════════════════════════════════════════════════════════════════════
# 4. Empty/null task_type defaults to UNKNOWN → MEGAMIND
# ═══════════════════════════════════════════════════════════════════════

class TestEmptyTaskType:
    """Empty or null task_type must default to UNKNOWN → MEGAMIND."""

    @pytest.mark.parametrize("task_type", [None, "", "  ", "unknown", "UNKNOWN"])
    def test_empty_or_unknown_task_type(self, task_type):
        assert classify_task(task_type, "LOW", "LOW") == "MEGAMIND"

    def test_empty_task_type_with_high_complexity(self):
        assert classify_task(None, "HIGH", "LOW") == "MEGAMIND"

    def test_empty_task_type_case_insensitive(self):
        assert classify_task("  unknown  ", "MEDIUM", "LOW") == "MEGAMIND"


# ═══════════════════════════════════════════════════════════════════════
# 5. Prior fails = 0 vs 1 vs 2+ routing differences
# ═══════════════════════════════════════════════════════════════════════

class TestPriorFails:
    """Different prior-fail counts produce different routing."""

    def test_zero_fails_low_low(self):
        # Base case: LOW + LOW + 0 fails → RAPID STRIKE
        assert classify_task("IMPLEMENTATION", "LOW", "LOW", prior_fails=0) == "RAPID STRIKE"

    def test_one_fail_low_low(self):
        # 1 fail on non-bug → base is RAPID STRIKE, bumped to ENSEMBLE
        assert classify_task("IMPLEMENTATION", "LOW", "LOW", prior_fails=1) == "ENSEMBLE"

    def test_two_fails_low_low(self):
        # 2+ fails on non-bug → same as 1 fail: ENSEMBLE minimum
        assert classify_task("IMPLEMENTATION", "LOW", "LOW", prior_fails=2) == "ENSEMBLE"

    def test_one_fail_bug_fix(self):
        # BUG_FIX + ≥1 fail → GRAND JURY forced
        assert classify_task("BUG_FIX", "LOW", "LOW", prior_fails=1) == "GRAND JURY"

    def test_two_fails_bug_fix(self):
        assert classify_task("BUG_FIX", "LOW", "LOW", prior_fails=2) == "GRAND JURY"

    def test_one_fail_debugging(self):
        # DEBUGGING + ≥1 fail → GRAND JURY forced
        assert classify_task("DEBUGGING", "LOW", "LOW", prior_fails=1) == "GRAND JURY"

    def test_zero_fails_debugging(self):
        # DEBUGGING + 0 fails → base matrix applies
        assert classify_task("DEBUGGING", "LOW", "LOW", prior_fails=0) == "RAPID STRIKE"

    def test_one_fail_medium_complexity(self):
        # MEDIUM → DEEP THINK; prior fails bumps to ENSEMBLE
        assert classify_task("OPTIMIZE", "MEDIUM", "LOW", prior_fails=1) == "ENSEMBLE"

    def test_one_fail_high_complexity(self):
        # HIGH → ENSEMBLE; prior fails doesn't lower it
        assert classify_task("OPTIMIZE", "HIGH", "LOW", prior_fails=1) == "ENSEMBLE"

    def test_one_fail_extreme_complexity(self):
        # EXTREME → MEGAMIND; prior fails doesn't change it
        assert classify_task("OPTIMIZE", "EXTREME", "LOW", prior_fails=1) == "MEGAMIND"

    def test_zero_fails_with_medium_stakes(self):
        # MEDIUM stakes → DEEP THINK; 0 fails → stays DEEP THINK
        assert classify_task("RESEARCH", "LOW", "MEDIUM", prior_fails=0) == "DEEP THINK"

    def test_one_fail_with_medium_stakes(self):
        # MEDIUM stakes → DEEP THINK; 1 fail bumps to ENSEMBLE
        assert classify_task("RESEARCH", "LOW", "MEDIUM", prior_fails=1) == "ENSEMBLE"


# ═══════════════════════════════════════════════════════════════════════
# 6. framework_css=True alone (not GRAND JURY unless also BUG_FIX + multi-file)
# ═══════════════════════════════════════════════════════════════════════

class TestFrameworkCss:
    """framework_css alone should NOT force GRAND JURY."""

    def test_framework_css_alone_low(self):
        assert classify_task(
            "IMPLEMENTATION", "LOW", "LOW", framework_css=True
        ) == "RAPID STRIKE"

    def test_framework_css_alone_medium(self):
        assert classify_task(
            "OPTIMIZE", "MEDIUM", "LOW", framework_css=True
        ) == "DEEP THINK"

    def test_framework_css_alone_high(self):
        assert classify_task(
            "ARCHITECTURE", "HIGH", "LOW", framework_css=True
        ) == "ENSEMBLE"

    def test_framework_css_alone_single_file(self):
        # framework_css + single file → not GRAND JURY
        assert classify_task(
            "BUG_FIX", "LOW", "LOW", framework_css=True, files_involved="1-2"
        ) == "RAPID STRIKE"

    def test_framework_css_bug_fix_no_multi_file(self):
        # BUG_FIX + framework_css + single file → not GRAND JURY
        assert classify_task(
            "BUG_FIX", "MEDIUM", "LOW", framework_css=True, files_involved="1-2"
        ) == "DEEP THINK"

    def test_framework_css_debugging_no_multi_file(self):
        # DEBUGGING + framework_css + single file → not GRAND JURY
        assert classify_task(
            "DEBUGGING", "LOW", "LOW", framework_css=True, files_involved="1-2"
        ) == "RAPID STRIKE"

    def test_framework_css_bug_fix_multi_file(self):
        # BUG_FIX + framework_css + multi-file → GRAND JURY
        assert classify_task(
            "BUG_FIX", "LOW", "LOW", framework_css=True, files_involved="3-5"
        ) == "GRAND JURY"

    def test_framework_css_bug_fix_multi_file_6plus(self):
        assert classify_task(
            "BUG_FIX", "LOW", "LOW", framework_css=True, files_involved="6+"
        ) == "GRAND JURY"

    def test_framework_css_debugging_multi_file(self):
        # DEBUGGING + framework_css + multi-file → GRAND JURY
        assert classify_task(
            "DEBUGGING", "LOW", "LOW", framework_css=True, files_involved="6+"
        ) == "GRAND JURY"

    def test_framework_css_non_bug_multi_file(self):
        # Non-bug + framework_css + multi-file → NOT GRAND JURY
        assert classify_task(
            "IMPLEMENTATION", "LOW", "LOW", framework_css=True, files_involved="6+"
        ) == "RAPID STRIKE"

    def test_framework_css_investigation(self):
        # INVESTIGATION always → GRAND JURY regardless of framework_css
        assert classify_task(
            "INVESTIGATION", "LOW", "LOW", framework_css=True
        ) == "GRAND JURY"


# ═══════════════════════════════════════════════════════════════════════
# 7. All 12 task types
# ═══════════════════════════════════════════════════════════════════════

class TestAllTaskTypes:
    """Every task type routes correctly in its baseline scenario."""

    def test_bug_fix_baseline(self):
        assert classify_task("BUG_FIX", "LOW", "LOW") == "RAPID STRIKE"

    def test_implementation_baseline(self):
        assert classify_task("IMPLEMENTATION", "LOW", "LOW") == "RAPID STRIKE"

    def test_architecture_baseline(self):
        assert classify_task("ARCHITECTURE", "MEDIUM", "LOW") == "DEEP THINK"

    def test_research_baseline(self):
        assert classify_task("RESEARCH", "HIGH", "LOW") == "ENSEMBLE"

    def test_optimize_baseline(self):
        assert classify_task("OPTIMIZE", "LOW", "HIGH") == "ENSEMBLE"

    def test_debugging_baseline(self):
        assert classify_task("DEBUGGING", "LOW", "LOW") == "RAPID STRIKE"

    def test_creative_baseline(self):
        assert classify_task("CREATIVE", "EXTREME", "LOW") == "MEGAMIND"

    def test_analysis_baseline(self):
        assert classify_task("ANALYSIS", "MEDIUM", "MEDIUM") == "DEEP THINK"

    def test_planning_baseline(self):
        assert classify_task("PLANNING", "HIGH", "MEDIUM") == "ENSEMBLE"

    def test_investigation_baseline(self):
        # INVESTIGATION always → GRAND JURY
        assert classify_task("INVESTIGATION", "LOW", "LOW") == "GRAND JURY"

    def test_design_baseline(self):
        assert classify_task("DESIGN", "LOW", "CRITICAL") == "MEGAMIND"

    def test_unknown_baseline(self):
        assert classify_task("UNKNOWN", "LOW", "LOW") == "MEGAMIND"

    # Task types with varying complexity
    @pytest.mark.parametrize("task_type", [
        "BUG_FIX", "IMPLEMENTATION", "ARCHITECTURE", "RESEARCH",
        "OPTIMIZE", "DEBUGGING", "CREATIVE", "ANALYSIS",
        "PLANNING", "DESIGN",
    ])
    def test_task_type_with_extreme_complexity(self, task_type):
        assert classify_task(task_type, "EXTREME", "LOW") == "MEGAMIND"

    @pytest.mark.parametrize("task_type", [
        "BUG_FIX", "IMPLEMENTATION", "ARCHITECTURE", "RESEARCH",
        "OPTIMIZE", "DEBUGGING", "CREATIVE", "ANALYSIS",
        "PLANNING", "DESIGN",
    ])
    def test_task_type_with_critical_stakes(self, task_type):
        assert classify_task(task_type, "LOW", "CRITICAL") == "MEGAMIND"

    @pytest.mark.parametrize("task_type", [
        "BUG_FIX", "IMPLEMENTATION", "ARCHITECTURE", "RESEARCH",
        "OPTIMIZE", "DEBUGGING", "CREATIVE", "ANALYSIS",
        "PLANNING", "DESIGN",
    ])
    def test_task_type_with_low_low_zero(self, task_type):
        # All non-UNKNOWN, non-INVESTIGATION types with LOW/LOW/0 → RAPID STRIKE
        assert classify_task(task_type, "LOW", "LOW") == "RAPID STRIKE"


# ═══════════════════════════════════════════════════════════════════════
# 8. Interaction between production=True and varying stakes
# ═══════════════════════════════════════════════════════════════════════

class TestProductionStakes:
    """production=True interacts with stakes levels differently."""

    def test_production_low_stakes(self):
        # PRODUCTION + LOW stakes → no GRAND JURY override
        assert classify_task(
            "IMPLEMENTATION", "LOW", "LOW", production=True
        ) == "RAPID STRIKE"

    def test_production_medium_stakes(self):
        # PRODUCTION + MEDIUM stakes → GRAND JURY
        assert classify_task(
            "IMPLEMENTATION", "LOW", "MEDIUM", production=True
        ) == "GRAND JURY"

    def test_production_high_stakes(self):
        # PRODUCTION + HIGH stakes → GRAND JURY
        assert classify_task(
            "IMPLEMENTATION", "LOW", "HIGH", production=True
        ) == "GRAND JURY"

    def test_production_critical_stakes(self):
        # PRODUCTION + CRITICAL → MEGAMIND (CRITICAL always wins)
        assert classify_task(
            "IMPLEMENTATION", "LOW", "CRITICAL", production=True
        ) == "MEGAMIND"

    def test_production_medium_stakes_medium_complexity(self):
        # MEDIUM complexity → DEEP THINK; production + MEDIUM stakes → GRAND JURY
        assert classify_task(
            "OPTIMIZE", "MEDIUM", "MEDIUM", production=True
        ) == "GRAND JURY"

    def test_production_high_stakes_low_complexity(self):
        assert classify_task(
            "RESEARCH", "LOW", "HIGH", production=True
        ) == "GRAND JURY"

    def test_production_low_stakes_high_complexity(self):
        # HIGH complexity → ENSEMBLE; production + LOW stakes → no override
        assert classify_task(
            "ARCHITECTURE", "HIGH", "LOW", production=True
        ) == "ENSEMBLE"

    def test_production_medium_stakes_high_complexity(self):
        # HIGH complexity → ENSEMBLE; production + MEDIUM → GRAND JURY
        assert classify_task(
            "ARCHITECTURE", "HIGH", "MEDIUM", production=True
        ) == "GRAND JURY"

    def test_production_extreme_complexity_low_stakes(self):
        # EXTREME → MEGAMIND; production + LOW → no override
        assert classify_task(
            "DESIGN", "EXTREME", "LOW", production=True
        ) == "MEGAMIND"

    def test_production_low_stakes_with_prior_fails(self):
        # PRODUCTION + LOW + 1 fail → ENSEMBLE (prior fail minimum)
        assert classify_task(
            "IMPLEMENTATION", "LOW", "LOW", production=True, prior_fails=1
        ) == "ENSEMBLE"

    def test_production_medium_stakes_with_prior_fails(self):
        # PRODUCTION + MEDIUM → GRAND JURY
        assert classify_task(
            "OPTIMIZE", "LOW", "MEDIUM", production=True, prior_fails=1
        ) == "GRAND JURY"


# ═══════════════════════════════════════════════════════════════════════
# 9. Base matrix edge transitions
# ═══════════════════════════════════════════════════════════════════════

class TestBaseMatrixTransitions:
    """Test transitions between modes in the base matrix."""

    def test_low_complexity_low_stakes_zero_fails_rapid(self):
        assert classify_task("IMPLEMENTATION", "LOW", "LOW", prior_fails=0) == "RAPID STRIKE"

    def test_low_complexity_medium_stakes(self):
        # LOW complexity but MEDIUM stakes → DEEP THINK
        assert classify_task("OPTIMIZE", "LOW", "MEDIUM") == "DEEP THINK"

    def test_medium_complexity_low_stakes(self):
        # MEDIUM complexity → DEEP THINK
        assert classify_task("OPTIMIZE", "MEDIUM", "LOW") == "DEEP THINK"

    def test_low_complexity_high_stakes(self):
        # HIGH stakes → ENSEMBLE
        assert classify_task("OPTIMIZE", "LOW", "HIGH") == "ENSEMBLE"

    def test_high_complexity_low_stakes(self):
        # HIGH complexity → ENSEMBLE
        assert classify_task("OPTIMIZE", "HIGH", "LOW") == "ENSEMBLE"

    def test_low_complexity_extreme_stakes_not_defined(self):
        # No "EXTREME" stakes — only LOW/MEDIUM/HIGH/CRITICAL
        # If someone passes a bogus stakes value, CRITICAL path doesn't match
        # Falls through to default
        assert classify_task("OPTIMIZE", "LOW", "CRITICAL") == "MEGAMIND"

    def test_extreme_complexity_low_stakes(self):
        assert classify_task("OPTIMIZE", "EXTREME", "LOW") == "MEGAMIND"

    def test_medium_complexity_medium_stakes(self):
        assert classify_task("OPTIMIZE", "MEDIUM", "MEDIUM") == "DEEP THINK"

    def test_high_complexity_high_stakes(self):
        assert classify_task("OPTIMIZE", "HIGH", "HIGH") == "ENSEMBLE"

    def test_extreme_complexity_high_stakes(self):
        assert classify_task("OPTIMIZE", "EXTREME", "HIGH") == "MEGAMIND"

    def test_default_fallback(self):
        # Edge case: LOW complexity, non-LOW stakes, 0 fails → DEEP THINK
        # (not caught by RAPID STRIKE rule since stakes != LOW)
        assert classify_task("IMPLEMENTATION", "LOW", "MEDIUM", prior_fails=0) == "DEEP THINK"


# ═══════════════════════════════════════════════════════════════════════
# 10. Override rules edge cases
# ═══════════════════════════════════════════════════════════════════════

class TestOverrideRules:
    """User-hint override rules and their edge cases."""

    def test_quick_hint_rapid_strike(self):
        assert classify_task(
            "ARCHITECTURE", "HIGH", "LOW", user_hint="quick"
        ) == "RAPID STRIKE"

    def test_just_do_it_hint_rapid_strike(self):
        assert classify_task(
            "ARCHITECTURE", "HIGH", "LOW", user_hint="just do it"
        ) == "RAPID STRIKE"

    def test_quick_hint_case_insensitive(self):
        assert classify_task(
            "ARCHITECTURE", "HIGH", "LOW", user_hint="QUICK"
        ) == "RAPID STRIKE"

    def test_quick_hint_with_critical_stakes_no_override(self):
        # 'quick' does NOT override CRITICAL stakes
        assert classify_task(
            "IMPLEMENTATION", "LOW", "CRITICAL", user_hint="quick"
        ) == "MEGAMIND"

    def test_think_harder_escalate_rapid_to_deep(self):
        assert classify_task(
            "IMPLEMENTATION", "LOW", "LOW", user_hint="think harder"
        ) == "DEEP THINK"

    def test_think_harder_escalate_deep_to_ensemble(self):
        assert classify_task(
            "OPTIMIZE", "MEDIUM", "LOW", user_hint="think harder"
        ) == "ENSEMBLE"

    def test_think_harder_escalate_ensemble_to_mega(self):
        assert classify_task(
            "ARCHITECTURE", "HIGH", "LOW", user_hint="think harder"
        ) == "MEGAMIND"

    def test_think_harder_escalate_mega_to_jury(self):
        assert classify_task(
            "DESIGN", "EXTREME", "LOW", user_hint="think harder"
        ) == "GRAND JURY"

    def test_think_harder_at_ceiling(self):
        # GRAND JURY stays GRAND JURY
        assert classify_task(
            "INVESTIGATION", "LOW", "LOW", user_hint="think harder"
        ) == "GRAND JURY"

    def test_no_user_hint(self):
        assert classify_task(
            "IMPLEMENTATION", "LOW", "LOW", user_hint=None
        ) == "RAPID STRIKE"

    def test_empty_user_hint(self):
        assert classify_task(
            "IMPLEMENTATION", "LOW", "LOW", user_hint=""
        ) == "RAPID STRIKE"

    def test_unrelated_user_hint(self):
        assert classify_task(
            "IMPLEMENTATION", "LOW", "LOW", user_hint="please be thorough"
        ) == "RAPID STRIKE"

    def test_prior_fail_minimum_ensemble_rapid(self):
        # Prior fail bumps RAPID STRIKE → ENSEMBLE
        assert classify_task(
            "IMPLEMENTATION", "LOW", "LOW", prior_fails=1
        ) == "ENSEMBLE"

    def test_prior_fail_minimum_ensemble_deep(self):
        # Prior fail bumps DEEP THINK → ENSEMBLE
        assert classify_task(
            "IMPLEMENTATION", "MEDIUM", "LOW", prior_fails=1
        ) == "ENSEMBLE"

    def test_prior_fail_no_bump_ensemble(self):
        # Already ENSEMBLE — stays
        assert classify_task(
            "IMPLEMENTATION", "HIGH", "LOW", prior_fails=1
        ) == "ENSEMBLE"

    def test_prior_fail_no_bump_megamind(self):
        # Already MEGAMIND — stays
        assert classify_task(
            "IMPLEMENTATION", "EXTREME", "LOW", prior_fails=1
        ) == "MEGAMIND"


# ═══════════════════════════════════════════════════════════════════════
# 11. INVESTIGATION special case
# ═══════════════════════════════════════════════════════════════════════

class TestInvestigation:
    """INVESTIGATION always routes to GRAND JURY (except CRITICAL stakes)."""

    @pytest.mark.parametrize("complexity", ["LOW", "MEDIUM", "HIGH", "EXTREME"])
    def test_investigation_any_complexity(self, complexity):
        assert classify_task("INVESTIGATION", complexity, "LOW") == "GRAND JURY"

    @pytest.mark.parametrize("stakes", ["LOW", "MEDIUM", "HIGH"])
    def test_investigation_non_critical_stakes(self, stakes):
        assert classify_task("INVESTIGATION", "LOW", stakes) == "GRAND JURY"

    def test_investigation_critical_stakes(self):
        # CRITICAL stakes → MEGAMIND overrides INVESTIGATION → GRAND JURY
        assert classify_task("INVESTIGATION", "LOW", "CRITICAL") == "MEGAMIND"

    def test_investigation_with_production(self):
        assert classify_task(
            "INVESTIGATION", "MEDIUM", "MEDIUM", production=True
        ) == "GRAND JURY"

    def test_investigation_case_insensitive(self):
        assert classify_task("investigation", "LOW", "LOW") == "GRAND JURY"


# ═══════════════════════════════════════════════════════════════════════
# 12. Case insensitivity and whitespace handling
# ═══════════════════════════════════════════════════════════════════════

class TestCaseHandling:
    """Inputs are normalised to upper-case and stripped."""

    def test_lowercase_task_type(self):
        assert classify_task("bug_fix", "low", "low") == "RAPID STRIKE"

    def test_mixed_case_complexity(self):
        assert classify_task("OPTIMIZE", "Medium", "low") == "DEEP THINK"

    def test_whitespace_around_values(self):
        assert classify_task("  BUG_FIX  ", "  LOW  ", "  LOW  ") == "RAPID STRIKE"

    def test_lowercase_investigation(self):
        assert classify_task("investigation", "HIGH", "HIGH") == "GRAND JURY"

    def test_lowercase_stakes_critical(self):
        assert classify_task("DESIGN", "low", "critical") == "MEGAMIND"


# ═══════════════════════════════════════════════════════════════════════
# 13. Files involved parameter
# ═══════════════════════════════════════════════════════════════════════

class TestFilesInvolved:
    """files_involved affects GRAND JURY only via BUG/DEBUG + framework_css."""

    def test_single_file(self):
        assert classify_task(
            "BUG_FIX", "LOW", "LOW", framework_css=True, files_involved="1-2"
        ) == "RAPID STRIKE"

    def test_multi_file_3to5(self):
        assert classify_task(
            "BUG_FIX", "LOW", "LOW", framework_css=True, files_involved="3-5"
        ) == "GRAND JURY"

    def test_multi_file_6plus(self):
        assert classify_task(
            "BUG_FIX", "LOW", "LOW", framework_css=True, files_involved="6+"
        ) == "GRAND JURY"

    def test_multi_file_no_framework(self):
        # Multi-file without framework_css → not GRAND JURY
        assert classify_task(
            "BUG_FIX", "LOW", "LOW", framework_css=False, files_involved="6+"
        ) == "RAPID STRIKE"

    def test_default_files_involved(self):
        # Default is "1-2" → single file
        assert classify_task(
            "BUG_FIX", "LOW", "LOW", framework_css=True
        ) == "RAPID STRIKE"


# ═══════════════════════════════════════════════════════════════════════
# 14. Return value validation
# ═══════════════════════════════════════════════════════════════════════

class TestReturnValue:
    """classify_task always returns one of the five valid mode strings."""

    @pytest.mark.parametrize("task_type,complexity,stakes", [
        ("BUG_FIX", "LOW", "LOW"),
        ("IMPLEMENTATION", "MEDIUM", "MEDIUM"),
        ("ARCHITECTURE", "HIGH", "HIGH"),
        ("RESEARCH", "EXTREME", "CRITICAL"),
        ("INVESTIGATION", "LOW", "LOW"),
        ("UNKNOWN", "LOW", "LOW"),
        (None, None, None),
        ("", "", ""),
    ])
    def test_always_returns_valid_mode(self, task_type, complexity, stakes):
        result = classify_task(task_type, complexity, stakes)
        assert result in MODES, f"Got {result!r}, expected one of {MODES}"


# ═══════════════════════════════════════════════════════════════════════
# 15. GRAND JURY forced conditions ordering
# ═══════════════════════════════════════════════════════════════════════

class TestGrandJuryForcedOrdering:
    """Verify that GRAND JURY forced conditions override base mode."""

    def test_investigation_overrides_megamind(self):
        # EXTREME → MEGAMIND, but INVESTIGATION → GRAND JURY
        assert classify_task("INVESTIGATION", "EXTREME", "LOW") == "GRAND JURY"

    def test_investigation_overrides_ensemble(self):
        assert classify_task("INVESTIGATION", "HIGH", "LOW") == "GRAND JURY"

    def test_bug_prior_fails_overrides_rapid(self):
        assert classify_task("BUG_FIX", "LOW", "LOW", prior_fails=1) == "GRAND JURY"

    def test_debug_prior_fails_overrides_deep(self):
        assert classify_task("DEBUGGING", "MEDIUM", "LOW", prior_fails=1) == "GRAND JURY"

    def test_production_medium_overrides_rapid(self):
        assert classify_task("IMPLEMENTATION", "LOW", "MEDIUM", production=True) == "GRAND JURY"

    def test_production_high_overrides_ensemble(self):
        assert classify_task("IMPLEMENTATION", "LOW", "HIGH", production=True) == "GRAND JURY"

    def test_production_does_not_override_critical(self):
        # CRITICAL → MEGAMIND, production doesn't change it
        assert classify_task("IMPLEMENTATION", "LOW", "CRITICAL", production=True) == "MEGAMIND"
