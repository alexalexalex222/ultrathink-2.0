"""Reasoning Swarm benchmarks package."""


def classify_task(
    task_type="UNKNOWN",
    complexity="LOW",
    stakes="LOW",
    prior_fails=0,
    files_involved="1-2",
    framework_css=False,
    production=False,
    user_hint=None,
):
    """Classify a task into a reasoning mode based on the AUTO-SELECT MATRIX.

    Implements the classification rules from skills/reasoning-swarm-SKILL.md lines 66-87.

    Args:
        task_type: One of BUG_FIX, IMPLEMENTATION, ARCHITECTURE, RESEARCH, OPTIMIZE,
                   DEBUGGING, CREATIVE, ANALYSIS, PLANNING, INVESTIGATION, DESIGN, UNKNOWN
        complexity: LOW, MEDIUM, HIGH, or EXTREME
        stakes: LOW, MEDIUM, HIGH, or CRITICAL
        prior_fails: 0, 1, or 2+ (use int, 2 means "2+")
        files_involved: "1-2", "3-5", or "6+"
        framework_css: Whether framework/CSS is involved
        production: Whether this is a production system
        user_hint: Optional string like "think harder", "quick", "just do it"

    Returns:
        Mode string: RAPID, DEEP, ENSEMBLE, MEGA, or JURY
    """
    task_type = (task_type or "UNKNOWN").upper()
    complexity = (complexity or "LOW").upper()
    stakes = (stakes or "LOW").upper()
    prior_fails = prior_fails or 0
    multi_file = files_involved in ("3-5", "6+")
    hint = (user_hint or "").lower().strip()

    mode = None

    # --- Forced rules (highest priority) ---

    # UNKNOWN task type -> MEGAMIND
    if task_type == "UNKNOWN":
        mode = "MEGA"

    # --- GRAND JURY forced rules ---

    # BUG_FIX/DEBUG + prior fails >= 1 -> GRAND JURY
    if task_type in ("BUG_FIX", "DEBUGGING") and prior_fails >= 1:
        mode = "JURY"

    # BUG_FIX/DEBUG + framework/CSS + multi-file -> GRAND JURY
    if mode is None and task_type in ("BUG_FIX", "DEBUGGING") and framework_css and multi_file:
        mode = "JURY"

    # INVESTIGATION type -> GRAND JURY
    if mode is None and task_type == "INVESTIGATION":
        mode = "JURY"

    # PRODUCTION + stakes >= MEDIUM -> GRAND JURY
    if mode is None and production and stakes in ("MEDIUM", "HIGH", "CRITICAL"):
        mode = "JURY"

    # --- Auto-select matrix ---
    if mode is None:
        if complexity == "LOW" and stakes == "LOW" and prior_fails == 0:
            mode = "RAPID"
        elif complexity == "MEDIUM" or stakes == "MEDIUM":
            mode = "DEEP"
        elif complexity == "HIGH" or stakes == "HIGH":
            mode = "ENSEMBLE"
        elif complexity == "EXTREME" or stakes == "CRITICAL":
            mode = "MEGA"
        else:
            mode = "DEEP"  # safe default

    # --- Override rules (do NOT override forced GRAND JURY) ---

    # "think harder" -> escalate one level
    if "think harder" in hint and mode != "JURY":
        mode = _escalate(mode)

    # "quick" / "just do it" -> RAPID STRIKE (unless CRITICAL stakes)
    if ("quick" in hint or "just do it" in hint) and stakes != "CRITICAL" and mode != "JURY":
        mode = "RAPID"

    # Prior failure on task -> minimum ENSEMBLE
    if prior_fails >= 1 and mode in ("RAPID", "DEEP"):
        mode = "ENSEMBLE"

    return mode


def _escalate(mode):
    """Escalate one level up the hierarchy."""
    hierarchy = ["RAPID", "DEEP", "ENSEMBLE", "MEGA", "JURY"]
    idx = hierarchy.index(mode)
    return hierarchy[min(idx + 1, len(hierarchy) - 1)]
