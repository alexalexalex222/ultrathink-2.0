from __future__ import annotations

MODES = ["RAPID STRIKE", "DEEP THINK", "ENSEMBLE", "MEGAMIND", "GRAND JURY"]

TASK_TYPES = [
    "BUG_FIX", "IMPLEMENTATION", "ARCHITECTURE", "RESEARCH",
    "OPTIMIZE", "DEBUGGING", "CREATIVE", "ANALYSIS",
    "PLANNING", "INVESTIGATION", "DESIGN", "UNKNOWN",
]

COMPLEXITY_LEVELS = ["LOW", "MEDIUM", "HIGH", "EXTREME"]
STAKES_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def classify_task(
    task_type: str | None,
    complexity: str | None,
    stakes: str | None,
    prior_fails: int = 0,
    files_involved: str = "1-2",
    framework_css: bool = False,
    production: bool = False,
    user_hint: str | None = None,
) -> str:
    """Classify a task and return the reasoning mode string.

    Implements the AUTO-SELECT MATRIX from reasoning-swarm-SKILL.md.
    """
    # Normalise task_type — empty/None/whitespace defaults to UNKNOWN
    task_type = (task_type or "").strip()
    if not task_type:
        task_type = "UNKNOWN"
    task_type = task_type.upper()

    # Normalise complexity — empty/None defaults to UNKNOWN
    if not complexity:
        complexity = "UNKNOWN"
    complexity = complexity.upper().strip()

    stakes = (stakes or "LOW").upper().strip()
    files_involved = (files_involved or "1-2").strip()
    user_hint_l = (user_hint or "").lower().strip()

    multi_file = files_involved in ("3-5", "6+")
    is_bug_debug = task_type in ("BUG_FIX", "DEBUGGING")

    # ── Base mode from the auto-select matrix ──────────────────────
    if task_type == "UNKNOWN":
        mode = "MEGAMIND"
    elif complexity == "UNKNOWN":
        mode = "MEGAMIND"
    elif stakes == "CRITICAL":
        mode = "MEGAMIND"
    elif complexity == "EXTREME":
        mode = "MEGAMIND"
    elif complexity == "HIGH" or stakes == "HIGH":
        mode = "ENSEMBLE"
    elif complexity == "MEDIUM" or stakes == "MEDIUM":
        mode = "DEEP THINK"
    elif complexity == "LOW" and stakes == "LOW" and prior_fails == 0:
        mode = "RAPID STRIKE"
    else:
        # LOW complexity, non-LOW stakes, 0 prior fails → DEEP THINK
        mode = "DEEP THINK"

    # ── Forced GRAND JURY conditions ───────────────────────────────
    # CRITICAL stakes always → MEGAMIND (no override possible)
    if stakes != "CRITICAL":
        # INVESTIGATION always → GRAND JURY (overrides UNKNOWN complexity)
        if task_type == "INVESTIGATION":
            mode = "GRAND JURY"

        # Remaining forced conditions do NOT override UNKNOWN task_type
        # or UNKNOWN complexity (both map to MEGAMIND as hard rules)
        if task_type != "UNKNOWN" and complexity != "UNKNOWN":
            if is_bug_debug and prior_fails >= 1:
                mode = "GRAND JURY"

            if is_bug_debug and framework_css and multi_file:
                mode = "GRAND JURY"

            # PRODUCTION + stakes >= MEDIUM
            if production and stakes in ("MEDIUM", "HIGH"):
                mode = "GRAND JURY"

    # ── Override rules ─────────────────────────────────────────────
    # 'quick' / 'just do it' → RAPID STRIKE unless CRITICAL stakes
    if user_hint_l and any(kw in user_hint_l for kw in ("quick", "just do it")):
        if stakes != "CRITICAL":
            mode = "RAPID STRIKE"

    # 'think harder' → escalate one level (but CRITICAL stakes stays MEGAMIND)
    if user_hint_l and "think harder" in user_hint_l:
        if stakes != "CRITICAL":
            idx = MODES.index(mode)
            mode = MODES[min(idx + 1, len(MODES) - 1)]

    # Prior failure → minimum ENSEMBLE
    if prior_fails >= 1 and mode in ("RAPID STRIKE", "DEEP THINK"):
        mode = "ENSEMBLE"

    return mode
