#!/usr/bin/env python3
"""CLI runner for the Reasoning Swarm.

Usage:
    python -m cli.run_swarm 'fix the login bug' --mode deep
    python -m cli.run_swarm 'design auth system' --mode mega --model opus
    python -m cli.run_swarm 'investigate crash' --mode jury --verbose
    python -m cli.run_swarm 'refactor parser' --output trace.md --format markdown

When KILO_API_KEY (or KILOCODE_TOKEN) is set, the CLI executes the prompt
against the LLM.  Otherwise it prints the constructed prompt for manual use.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"

VALID_MODES = ["auto", "rapid", "deep", "ensemble", "mega", "jury", "max"]

_MODE_CANONICAL = {
    "rapid": "RAPID STRIKE",
    "deep": "DEEP THINK",
    "ensemble": "ENSEMBLE",
    "mega": "MEGAMIND",
    "jury": "GRAND JURY",
    "max": "MEGAMIND",
}

_SKILL_FILES = {
    "RAPID STRIKE": ["reasoning-swarm-SKILL.md"],
    "DEEP THINK": ["deepthink-SKILL.md"],
    "ENSEMBLE": ["reasoning-swarm-SKILL.md"],
    "MEGAMIND": ["megamind-SKILL.md"],
    "GRAND JURY": ["diamondthink-SKILL.md"],
}

MODE_LABELS = {
    "auto": "AUTO-SELECT",
    "rapid": "RAPID STRIKE",
    "deep": "DEEP THINK",
    "ensemble": "ENSEMBLE",
    "mega": "MEGAMIND",
    "jury": "GRAND JURY",
    "max": "MEGAMIND + GRAND JURY",
}

_CONFIDENCE_DEFAULTS = {
    "RAPID STRIKE": 8,
    "DEEP THINK": 7,
    "ENSEMBLE": 7,
    "MEGAMIND": 6,
    "GRAND JURY": 7,
}


@dataclass
class SwarmTrace:
    """A single reasoning trace entry."""

    technique: str
    content: str
    timestamp: str = ""


@dataclass
class SwarmResult:
    """Structured result of a reasoning swarm execution."""

    mode: str
    confidence: int
    skill_files: list[str] = field(default_factory=list)
    prompt: str = ""
    model: str = ""
    trace: str = ""
    traces: list[SwarmTrace] = field(default_factory=list)
    elapsed_ms: float = 0.0
    executed: bool = False
    metadata: dict = field(default_factory=dict)


# ── LLM execution ──────────────────────────────────────────────────────────


def _get_api_config() -> tuple[str, str, str]:
    """Return (base_url, api_key, model) from environment."""
    base_url = os.environ.get(
        "KILO_OPENROUTER_BASE",
        os.environ.get("KILO_API_URL", "https://api.kilo.ai"),
    ).rstrip("/")
    api_key = os.environ.get("KILO_API_KEY", os.environ.get("KILOCODE_TOKEN", ""))
    model = os.environ.get("REASONING_SWARM_MODEL", "kilo/xiaomi/mimo-v2-pro:free")
    return base_url, api_key, model


def _call_llm(prompt: str, model: str = "", timeout: int = 300) -> str:
    """Make a chat completion call to the Kilo API.

    Returns the assistant message content string.
    Raises RuntimeError on API or network errors.
    """
    base_url, api_key, default_model = _get_api_config()
    if not api_key:
        raise RuntimeError(
            "No API key found. Set KILO_API_KEY or KILOCODE_TOKEN environment variable."
        )

    model = model or default_model
    endpoint = f"{base_url}/api/chat/completions"

    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "temperature": 0.7,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"API error {exc.code}: {body}") from exc
    except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"LLM call failed: {exc}") from exc


# ── Mode resolution ────────────────────────────────────────────────────────


def resolve_mode(mode_arg: str, problem: str) -> str:
    """Resolve the '--mode' argument to a canonical mode name."""
    if mode_arg == "auto":
        return auto_classify(problem)
    return _MODE_CANONICAL.get(mode_arg, mode_arg.upper())


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
    if any(kw in p for kw in ("research", "explore", "find out")):
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
    if any(kw in p for kw in ("investigate", "audit", "forensic", "root cause")):
        return "jury"
    if any(kw in p for kw in ("quick", "simple", "typo", "fix", "just")):
        return "rapid"
    if any(kw in p for kw in ("redesign", "architect", "migrate", "overhaul", "scalab")):
        return "mega"
    if any(kw in p for kw in ("compare", "evaluate", "trade-off", "pros and cons")):
        return "ensemble"
    if any(kw in p for kw in ("design", "implement", "refactor", "build", "add")):
        return "deep"
    return "ensemble"


# ── Skill loading ──────────────────────────────────────────────────────────


def load_skill(filename: str) -> str:
    """Load a skill file by filename from the skills directory."""
    path = SKILLS_DIR / filename
    if not path.exists():
        path = SKILLS_DIR / "reasoning-swarm-SKILL.md"
    return path.read_text()


def load_skills_for_mode(mode: str) -> list[tuple[str, str]]:
    """Return list of (filename, content) for the given canonical mode."""
    filenames = _SKILL_FILES.get(mode, ["reasoning-swarm-SKILL.md"])
    results = []
    for fn in filenames:
        try:
            results.append((fn, load_skill(fn)))
        except FileNotFoundError:
            pass
    return results


def get_skill_filenames(mode: str) -> list[str]:
    """Return the skill filenames for the given canonical mode."""
    return _SKILL_FILES.get(mode, ["reasoning-swarm-SKILL.md"])


# ── Prompt construction ────────────────────────────────────────────────────


def construct_prompt(
    problem: str,
    mode: str,
    skill_contents: list[tuple[str, str]],
    model: str = "",
) -> str:
    """Build the full prompt combining skill instructions with the problem."""
    parts: list[str] = []

    mode_label = MODE_LABELS.get(mode, mode)
    parts.append(f"# Reasoning Swarm — {mode_label}")
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


# ── Agent execution ────────────────────────────────────────────────────────


def _build_stub_traces(mode: str) -> list[SwarmTrace]:
    """Build placeholder traces for prompt-only mode."""
    now = datetime.now(timezone.utc).strftime("%H:%M:%S")
    traces: list[SwarmTrace] = []

    if mode == "deep":
        techniques = [
            "META-COGNITION", "STEP-BACK", "DECOMPOSITION",
            "TREE OF THOUGHT", "FIRST PRINCIPLES", "ANALOGICAL REASONING",
            "CHAIN OF THOUGHT", "DEVIL'S ADVOCATE", "INVERSION",
            "RAVEN LOOP", "RECURSIVE SELF-IMPROVEMENT",
        ]
        for tech in techniques:
            traces.append(SwarmTrace(tech, f"[{tech}] Pending agent execution", now))
    elif mode == "ensemble":
        for angle in ["PERFORMANCE", "SIMPLICITY", "SECURITY", "EDGE CASES", "DEVIL'S ADVOCATE"]:
            traces.append(SwarmTrace(f"ENSEMBLE: {angle}", f"[{angle}] Pending agent execution", now))
    elif mode == "mega":
        for i in range(1, 11):
            traces.append(SwarmTrace(f"ANGLE-EXPLORER {i}", f"[Explorer {i}] Pending agent execution", now))
        for label in ["CONSENSUS", "CONFLICT", "RISK"]:
            traces.append(SwarmTrace(f"SYNTHESIZER: {label}", f"[{label}] Pending agent execution", now))
    elif mode == "jury":
        phases = [
            "GJ-0: COMMITMENT", "GJ-1: SYMPTOM RECORD",
            "GJ-1.5: TERRITORY MAP", "GJ-2: ASSUMPTIONS LEDGER",
            "GJ-3: SEARCH PASS", "GJ-4: EVIDENCE LEDGER",
            "GJ-5: CHAIN-OF-CUSTODY", "GJ-6: MURDER BOARD",
            "GJ-7: PRE-FLIGHT", "GJ-8: ATOMIC CHANGE + VERIFY",
        ]
        for phase in phases:
            traces.append(SwarmTrace(phase, f"[{phase}] Pending agent execution", now))
    elif mode == "max":
        traces.append(SwarmTrace(
            "MEGAMIND PHASE",
            "[MEGAMIND] 10→3→1 ultra-meta reasoning. Pending agent execution.",
            now,
        ))
        traces.append(SwarmTrace(
            "GRAND JURY PHASE",
            "[GRAND JURY] Investigation protocol. Pending agent execution.",
            now,
        ))
    elif mode == "rapid":
        traces.append(SwarmTrace(
            "RAPID STRIKE",
            "[RAPID STRIKE] Single-pass reasoning. Pending agent execution.",
            now,
        ))

    return traces


def run_agent(
    prompt: str,
    mode: str,
    model: str = "",
    execute: bool = True,
    verbose: bool = False,
) -> SwarmResult:
    """Run the reasoning swarm on the given prompt.

    When execute=True and an API key is available, calls the LLM.
    Otherwise returns a structured result with the constructed prompt.
    """
    canonical_mode = _MODE_CANONICAL.get(mode, mode) if mode != mode.upper() else mode
    skill_contents = load_skills_for_mode(canonical_mode)
    skill_filenames = get_skill_filenames(canonical_mode)
    full_prompt = construct_prompt(prompt, canonical_mode, skill_contents, model)

    result = SwarmResult(
        mode=canonical_mode,
        confidence=_CONFIDENCE_DEFAULTS.get(canonical_mode, 7),
        skill_files=skill_filenames,
        prompt=full_prompt,
        model=model,
        traces=_build_stub_traces(canonical_mode.lower() if canonical_mode != "GRAND JURY" else "jury"),
        metadata={
            "problem": prompt,
            "mode_requested": mode,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
    )

    t0 = time.perf_counter()

    _, api_key, default_model = _get_api_config()
    should_execute = execute and bool(api_key)

    if should_execute:
        try:
            exec_model = model or default_model
            result.model = exec_model
            trace = _call_llm(full_prompt, model=model)
            result.trace = trace
            result.executed = True
        except RuntimeError as exc:
            print(f"Execution failed: {exc}", file=sys.stderr)
            print("Falling back to prompt-only mode.", file=sys.stderr)
            result.metadata["error"] = str(exc)

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    return result


# ── Output formatting ─────────────────────────────────────────────────────


def format_output(result: SwarmResult, fmt: str, verbose: bool) -> str:
    """Format the result for display."""
    if fmt == "json":
        return format_result_json(result, verbose)
    if fmt == "markdown":
        return format_result_markdown(result, verbose)
    return format_result_text(result, verbose)


def format_result_json(result: SwarmResult, verbose: bool = False) -> str:
    """Format the result as JSON."""
    data = {
        "mode": result.mode,
        "confidence": result.confidence,
        "skill_files": result.skill_files,
        "model": result.model,
        "elapsed_ms": round(result.elapsed_ms, 2),
        "executed": result.executed,
        "metadata": result.metadata,
    }
    if verbose:
        data["prompt"] = result.prompt
    if result.trace:
        data["trace"] = result.trace
    if result.traces:
        data["traces"] = [asdict(t) for t in result.traces]
    return json.dumps(data, indent=2)


def format_result_markdown(result: SwarmResult, verbose: bool = False) -> str:
    """Format the result as markdown."""
    lines = [
        f"# Reasoning Swarm — {result.mode}",
        "",
        f"**Confidence:** {result.confidence}/10",
        f"**Skills:** {', '.join(result.skill_files)}",
    ]
    if result.model:
        lines.append(f"**Model:** {result.model}")
    lines.append(f"**Elapsed:** {result.elapsed_ms:.0f}ms")
    if result.executed:
        lines.append("**Executed:** yes")
    lines.append("")

    if result.traces and verbose:
        lines.append("## Reasoning Trace")
        lines.append("")
        for i, trace in enumerate(result.traces, 1):
            lines.append(f"### Step {i}: {trace.technique}")
            lines.append("")
            lines.append(trace.content)
            lines.append("")

    if result.trace:
        lines.append("## Result")
        lines.append("")
        lines.append(result.trace)
        lines.append("")
    elif verbose:
        lines.append("## Prompt")
        lines.append("")
        lines.append(result.prompt)
        lines.append("")

    return "\n".join(lines)


def format_result_text(result: SwarmResult, verbose: bool = False) -> str:
    """Format the result as plain text."""
    parts = [
        f"Mode:       {result.mode}",
        f"Confidence: {result.confidence}/10",
        f"Skills:     {', '.join(result.skill_files)}",
    ]
    if result.model:
        parts.append(f"Model:      {result.model}")
    parts.append(f"Elapsed:    {result.elapsed_ms:.0f}ms")
    if result.executed:
        parts.append("Executed:   yes")

    if result.traces and verbose:
        parts.append("")
        parts.append("─── Reasoning Trace ───")
        for i, trace in enumerate(result.traces, 1):
            parts.append(f"[{i}] {trace.technique}")
            for line in trace.content.splitlines():
                parts.append(f"    {line}")

    if result.trace:
        parts.append("")
        parts.append("─── Result ───")
        parts.append(result.trace)
    elif verbose:
        parts.append("")
        parts.append("─── Prompt ───")
        parts.append(result.prompt)

    return "\n".join(parts)


# ── Argument parsing ───────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Reasoning Swarm on a problem description",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment variables:
  KILO_API_KEY              API key (or KILOCODE_TOKEN)
  KILO_OPENROUTER_BASE      API base URL (default: https://api.kilo.ai)
  REASONING_SWARM_MODEL     Default model (default: kilo/xiaomi/mimo-v2-pro:free)

Examples:
  python -m cli.run_swarm 'fix the login bug' --mode deep
  python -m cli.run_swarm 'design auth system' --mode mega --model opus
  python -m cli.run_swarm 'investigate crash' --mode jury --verbose
  python -m cli.run_swarm 'refactor parser' --output trace.md --format markdown
  python -m cli.run_swarm 'quick fix typo' --no-execute
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
        help="Override the default model (e.g. opus, sonnet, haiku)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show full reasoning trace and prompt",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Save trace output to a file",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="text",
        choices=["json", "markdown", "text"],
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        default=False,
        help="Skip LLM execution — only construct and display the prompt",
    )
    return parser.parse_args(argv)


# ── Main ───────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    mode = resolve_mode(args.mode, args.problem)

    result = run_agent(
        prompt=args.problem,
        mode=mode,
        model=args.model,
        execute=not args.no_execute,
        verbose=args.verbose,
    )

    formatted = format_output(result, args.format, args.verbose)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(formatted)
        print(f"Output saved to {output_path}", file=sys.stderr)
    else:
        print(formatted)

    if args.verbose and not args.output:
        exec_status = "executed" if result.executed else "prompt-only"
        print(
            f"\n[mode={mode} | skills={','.join(result.skill_files)} | "
            f"confidence={result.confidence}/10 | {exec_status}]",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
