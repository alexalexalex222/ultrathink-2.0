#!/usr/bin/env python3
"""CLI tool for running reasoning swarm from the command line.

Usage:
    python -m cli.run_swarm 'fix the login bug' --mode deep
    python -m cli.run_swarm 'design auth system' --mode mega --model opus
    python -m cli.run_swarm 'investigate crash' --mode jury --verbose

Modes:
    auto      — classify task and select optimal mode (default)
    rapid     — fast single-pass reasoning (2-5K tokens)
    deep      — full 11-technique sequential reasoning
    ensemble  — 5-way parallel reasoning with synthesis
    mega      — 10→3→1 ultra-meta reasoning
    jury      — investigation protocol with evidence gates
    max       — MEGAMIND + GRAND JURY combined
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"

# ---------------------------------------------------------------------------
# Mode ↔ skill file mapping
# ---------------------------------------------------------------------------

MODE_TO_SKILL: dict[str, list[str]] = {
    "rapid": [],
    "deep": ["deepthink-SKILL.md"],
    "ensemble": ["reasoning-swarm-SKILL.md"],
    "mega": ["megamind-SKILL.md"],
    "jury": ["diamondthink-SKILL.md"],
    "max": ["megamind-SKILL.md", "diamondthink-SKILL.md"],
}

MODE_LABELS: dict[str, str] = {
    "auto": "AUTO-SELECT",
    "rapid": "RAPID STRIKE",
    "deep": "DEEP THINK",
    "ensemble": "ENSEMBLE",
    "mega": "MEGAMIND",
    "jury": "GRAND JURY",
    "max": "MEGAMIND + GRAND JURY",
}

VALID_MODES = list(MODE_TO_SKILL) + ["auto"]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SwarmTrace:
    """A single reasoning trace entry."""
    technique: str
    content: str
    timestamp: str = ""


@dataclass
class SwarmResult:
    """Result of running a reasoning swarm."""
    problem: str
    mode: str
    model: str
    skill_files: list[str] = field(default_factory=list)
    prompt: str = ""
    traces: list[SwarmTrace] = field(default_factory=list)
    response: str = ""
    confidence: int = 0
    duration_s: float = 0.0
    token_estimate: int = 0
    timestamp: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["traces"] = [asdict(t) for t in self.traces]
        return d


# ---------------------------------------------------------------------------
# Skill loading
# ---------------------------------------------------------------------------


def load_skill(skill_filename: str) -> str:
    """Load a skill file by filename from the skills directory."""
    skill_path = SKILLS_DIR / skill_filename
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill file not found: {skill_path}")
    return skill_path.read_text(encoding="utf-8")


def load_skills_for_mode(mode: str) -> list[tuple[str, str]]:
    """Return list of (filename, content) for the given mode."""
    filenames = MODE_TO_SKILL.get(mode, [])
    return [(fn, load_skill(fn)) for fn in filenames]


# ---------------------------------------------------------------------------
# Auto-classification
# ---------------------------------------------------------------------------


def auto_classify(problem: str) -> str:
    """Use the intake classifier to select the optimal mode.

    Falls back to keyword heuristics when the classifier module is not
    available or cannot determine the mode.
    """
    try:
        from src.intake_classifier import classify_task

        task_type = _infer_task_type(problem)
        complexity = _infer_complexity(problem)
        stakes = _infer_stakes(problem)
        prior_fails = 0

        mode_str = classify_task(
            task_type=task_type,
            complexity=complexity,
            stakes=stakes,
            prior_fails=prior_fails,
        )
        # classify_task returns e.g. "RAPID STRIKE", "DEEP THINK", etc.
        return _label_to_mode(mode_str)
    except Exception:
        return _heuristic_classify(problem)


def _infer_task_type(problem: str) -> str:
    """Infer task type from the problem description."""
    p = problem.lower()
    if any(kw in p for kw in ("bug", "fix", "broken", "crash", "error", "fail")):
        return "BUG_FIX"
    if any(kw in p for kw in ("debug", "investigate", "why", "diagnose")):
        return "DEBUGGING"
    if any(kw in p for kw in ("design", "architect", "structure", "system")):
        return "ARCHITECTURE"
    if any(kw in p for kw in ("research", "explore", "find out", "investigate")):
        return "INVESTIGATION"
    if any(kw in p for kw in ("implement", "add", "create", "build", "write")):
        return "IMPLEMENTATION"
    if any(kw in p for kw in ("optimize", "speed up", "performance", "slow")):
        return "OPTIMIZE"
    if any(kw in p for kw in ("plan", "roadmap", "strategy")):
        return "PLANNING"
    return "UNKNOWN"


def _infer_complexity(problem: str) -> str:
    """Infer complexity from the problem description."""
    p = problem.lower()
    word_count = len(problem.split())
    if word_count > 20 or any(kw in p for kw in ("complex", "system", "multiple", "entire")):
        return "HIGH"
    if word_count > 10 or any(kw in p for kw in ("several", "multiple", "refactor")):
        return "MEDIUM"
    return "LOW"


def _infer_stakes(problem: str) -> str:
    """Infer stakes from the problem description."""
    p = problem.lower()
    if any(kw in p for kw in ("production", "critical", "urgent", "security", "auth")):
        return "HIGH"
    if any(kw in p for kw in ("important", "user-facing", "payment")):
        return "MEDIUM"
    return "LOW"


def _label_to_mode(label: str) -> str:
    """Convert classifier label to CLI mode string."""
    mapping = {
        "RAPID STRIKE": "rapid",
        "DEEP THINK": "deep",
        "ENSEMBLE": "ensemble",
        "MEGAMIND": "mega",
        "GRAND JURY": "jury",
    }
    return mapping.get(label, "deep")


def _heuristic_classify(problem: str) -> str:
    """Fallback heuristic classification when intake_classifier is unavailable."""
    p = problem.lower()
    if any(kw in p for kw in ("investigate", "debug", "why", "crash", "diagnose")):
        return "jury"
    if any(kw in p for kw in ("quick", "simple", "fix", "typo", "rename")):
        return "rapid"
    if any(kw in p for kw in ("design", "architect", "system", "complex", "security")):
        return "mega"
    if any(kw in p for kw in ("implement", "add", "create", "build")):
        return "deep"
    return "deep"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def build_prompt(
    problem: str,
    mode: str,
    skill_contents: list[tuple[str, str]],
    model: str = "",
) -> str:
    """Build the full prompt from skill contents and problem description."""
    parts: list[str] = []

    parts.append(f"# Reasoning Swarm — {MODE_LABELS.get(mode, mode.upper())}")
    parts.append("")
    parts.append(f"**Problem:** {problem}")
    parts.append("")

    if model:
        parts.append(f"**Model:** {model}")
        parts.append("")

    if skill_contents:
        parts.append("## Skill Instructions")
        parts.append("")
        for filename, content in skill_contents:
            parts.append(f"### {filename}")
            parts.append("")
            parts.append(content)
            parts.append("")
        parts.append("---")
        parts.append("")

    parts.append("## Task")
    parts.append("")
    parts.append("Apply the reasoning protocol above to solve the following problem.")
    parts.append("Return the result in the output format specified by the skill.")
    parts.append("")
    parts.append(f"**Problem statement:** {problem}")
    parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def format_result_markdown(result: SwarmResult) -> str:
    """Format the result as markdown."""
    lines: list[str] = []

    lines.append(f"# Reasoning Swarm Result")
    lines.append("")
    lines.append(f"**Mode:** {MODE_LABELS.get(result.mode, result.mode)}")
    lines.append(f"**Problem:** {result.problem}")
    if result.model:
        lines.append(f"**Model:** {result.model}")
    lines.append(f"**Duration:** {result.duration_s:.1f}s")
    lines.append(f"**Timestamp:** {result.timestamp}")
    if result.skill_files:
        lines.append(f"**Skills:** {', '.join(result.skill_files)}")
    if result.confidence:
        lines.append(f"**Confidence:** {result.confidence}/10")
    lines.append("")

    if result.traces:
        lines.append("## Reasoning Trace")
        lines.append("")
        for i, trace in enumerate(result.traces, 1):
            lines.append(f"### Step {i}: {trace.technique}")
            lines.append("")
            lines.append(trace.content)
            lines.append("")

    lines.append("## Response")
    lines.append("")
    lines.append(result.response or "*(No response — agent not connected)*")
    lines.append("")

    return "\n".join(lines)


def format_result_text(result: SwarmResult) -> str:
    """Format the result as plain text."""
    sep = "=" * 60
    lines: list[str] = []

    lines.append(sep)
    lines.append(f"  REASONING SWARM — {MODE_LABELS.get(result.mode, result.mode)}")
    lines.append(sep)
    lines.append(f"  Problem:    {result.problem}")
    if result.model:
        lines.append(f"  Model:      {result.model}")
    lines.append(f"  Duration:   {result.duration_s:.1f}s")
    lines.append(f"  Timestamp:  {result.timestamp}")
    if result.skill_files:
        lines.append(f"  Skills:     {', '.join(result.skill_files)}")
    if result.confidence:
        lines.append(f"  Confidence: {result.confidence}/10")
    lines.append(sep)

    if result.traces:
        lines.append("")
        lines.append("REASONING TRACE:")
        lines.append("-" * 40)
        for i, trace in enumerate(result.traces, 1):
            lines.append(f"[{i}] {trace.technique}")
            for tline in trace.content.splitlines():
                lines.append(f"    {tline}")
            lines.append("")

    lines.append("")
    lines.append("RESPONSE:")
    lines.append("-" * 40)
    lines.append(result.response or "(No response — agent not connected)")
    lines.append(sep)

    return "\n".join(lines)


def format_result_json(result: SwarmResult) -> str:
    """Format the result as JSON."""
    return json.dumps(result.to_dict(), indent=2)


FORMATTERS = {
    "markdown": format_result_markdown,
    "text": format_result_text,
    "json": format_result_json,
}

# ---------------------------------------------------------------------------
# Agent execution stub
# ---------------------------------------------------------------------------


def run_agent(
    prompt: str,
    mode: str,
    model: str = "",
    verbose: bool = False,
) -> SwarmResult:
    """Run the reasoning agent with the constructed prompt.

    This is the integration point for actual agent execution.
    Currently returns a structured result with the prompt for inspection.
    """
    skill_files = MODE_TO_SKILL.get(mode, [])
    skill_contents = load_skills_for_mode(mode) if mode != "auto" else []
    full_prompt = build_prompt(prompt, mode, skill_contents, model)

    result = SwarmResult(
        problem=prompt,
        mode=mode,
        model=model,
        skill_files=[fn for fn, _ in skill_contents],
        prompt=full_prompt,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

    t0 = time.perf_counter()

    # TODO: integrate with actual agent runtime
    # For now, construct the trace from the skill techniques
    if mode == "deep":
        techniques = [
            "META-COGNITION", "STEP-BACK", "DECOMPOSITION",
            "TREE OF THOUGHT", "FIRST PRINCIPLES", "ANALOGICAL REASONING",
            "CHAIN OF THOUGHT", "DEVIL'S ADVOCATE", "INVERSION",
            "RAVEN LOOP", "RECURSIVE SELF-IMPROVEMENT",
        ]
        for tech in techniques:
            result.traces.append(SwarmTrace(
                technique=tech,
                content=f"[{tech}] Pending agent execution",
                timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            ))
    elif mode == "ensemble":
        angles = ["PERFORMANCE", "SIMPLICITY", "SECURITY", "EDGE CASES", "DEVIL'S ADVOCATE"]
        for angle in angles:
            result.traces.append(SwarmTrace(
                technique=f"ENSEMBLE: {angle}",
                content=f"[{angle}] Pending agent execution",
                timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            ))
    elif mode == "mega":
        for i in range(1, 11):
            result.traces.append(SwarmTrace(
                technique=f"ANGLE-EXPLORER {i}",
                content=f"[Explorer {i}] Pending agent execution",
                timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            ))
        for label in ["CONSENSUS", "CONFLICT", "RISK"]:
            result.traces.append(SwarmTrace(
                technique=f"SYNTHESIZER: {label}",
                content=f"[{label}] Pending agent execution",
                timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            ))
    elif mode == "jury":
        phases = [
            "GJ-0: COMMITMENT", "GJ-1: SYMPTOM RECORD",
            "GJ-1.5: TERRITORY MAP", "GJ-2: ASSUMPTIONS LEDGER",
            "GJ-3: SEARCH PASS", "GJ-4: EVIDENCE LEDGER",
            "GJ-5: CHAIN-OF-CUSTODY", "GJ-6: MURDER BOARD",
            "GJ-7: PRE-FLIGHT", "GJ-8: ATOMIC CHANGE + VERIFY",
        ]
        for phase in phases:
            result.traces.append(SwarmTrace(
                technique=phase,
                content=f"[{phase}] Pending agent execution",
                timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
            ))
    elif mode == "max":
        result.traces.append(SwarmTrace(
            technique="MEGAMIND PHASE",
            content="[MEGAMIND] 10→3→1 ultra-meta reasoning. Pending agent execution.",
            timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        ))
        result.traces.append(SwarmTrace(
            technique="GRAND JURY PHASE",
            content="[GRAND JURY] Investigation protocol. Pending agent execution.",
            timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        ))
    elif mode == "rapid":
        result.traces.append(SwarmTrace(
            technique="RAPID STRIKE",
            content="[RAPID STRIKE] Single-pass reasoning. Pending agent execution.",
            timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        ))

    result.response = (
        f"Reasoning swarm prompt constructed for mode '{mode}'. "
        f"Connect an agent runtime to execute."
    )
    result.duration_s = time.perf_counter() - t0

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_swarm",
        description="Reasoning Swarm CLI — run adaptive reasoning from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m cli.run_swarm 'fix the login bug' --mode deep
  python -m cli.run_swarm 'design auth system' --mode mega --model opus
  python -m cli.run_swarm 'investigate crash' --mode jury --verbose
  python -m cli.run_swarm 'refactor auth module' --mode auto --format json
  python -m cli.run_swarm 'add unit tests' --mode ensemble --output trace.md
        """,
    )
    parser.add_argument(
        "problem",
        type=str,
        help="Problem description to reason about",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="auto",
        choices=VALID_MODES,
        help="Reasoning mode (default: auto)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="",
        help="Model override (e.g., opus, sonnet, mimo-v2-pro)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show full reasoning trace",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Save output trace to file",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="text",
        choices=list(FORMATTERS.keys()),
        help="Output format (default: text)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Resolve mode
    mode = args.mode
    if mode == "auto":
        mode = auto_classify(args.problem)
        if args.verbose:
            print(f"Auto-classified mode: {MODE_LABELS.get(mode, mode)}", file=sys.stderr)

    # Load skills
    try:
        skill_contents = load_skills_for_mode(mode) if mode != "auto" else []
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Run
    result = run_agent(
        prompt=args.problem,
        mode=mode,
        model=args.model,
        verbose=args.verbose,
    )

    # Filter traces if not verbose
    if not args.verbose:
        result.traces = []

    # Format output
    formatter = FORMATTERS[args.format]
    output = formatter(result)

    # Write output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"Output written to {output_path}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
