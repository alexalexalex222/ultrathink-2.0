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
    "RAPID STRIKE": "reasoning-swarm-SKILL.md",
    "DEEP THINK": "deepthink-SKILL.md",
    "ENSEMBLE": "reasoning-swarm-SKILL.md",
    "MEGAMIND": "megamind-SKILL.md",
    "GRAND JURY": "diamondthink-SKILL.md",
}

_CONFIDENCE_DEFAULTS = {
    "RAPID STRIKE": 8,
    "DEEP THINK": 7,
    "ENSEMBLE": 7,
    "MEGAMIND": 6,
    "GRAND JURY": 7,
}


@dataclass
class SwarmResult:
    """Structured result of a reasoning swarm execution."""

    mode: str
    confidence: int
    skill_file: str
    prompt: str
    model: str = ""
    trace: str = ""
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
        return _auto_classify(problem)
    return _MODE_CANONICAL[mode_arg]


def _auto_classify(problem: str) -> str:
    """Heuristic auto-classification from problem description text."""
    lower = problem.lower()

    if any(w in lower for w in ("investigate", "audit", "forensic", "root cause")):
        return "GRAND JURY"
    if any(w in lower for w in ("quick", "simple", "typo", "fix the", "just")):
        return "RAPID STRIKE"
    if any(w in lower for w in ("redesign", "architect", "migrate", "overhaul", "scalab")):
        return "MEGAMIND"
    if any(w in lower for w in ("compare", "evaluate", "trade-off", "pros and cons")):
        return "ENSEMBLE"
    if any(w in lower for w in ("design", "implement", "refactor", "build", "add")):
        return "DEEP THINK"
    return "ENSEMBLE"


# ── Skill loading ──────────────────────────────────────────────────────────


def load_skill(mode: str) -> str:
    """Load the skill file for the given canonical mode."""
    filename = _SKILL_FILES[mode]
    path = SKILLS_DIR / filename
    if not path.exists():
        path = SKILLS_DIR / "reasoning-swarm-SKILL.md"
    return path.read_text()


def get_skill_filename(mode: str) -> str:
    """Return the skill filename for the given canonical mode."""
    return _SKILL_FILES[mode]


# ── Prompt construction ────────────────────────────────────────────────────


def construct_prompt(problem: str, mode: str, skill_content: str, model: str = "") -> str:
    """Build the full prompt combining skill instructions with the problem."""
    model_line = f"\nModel: {model}" if model else ""
    return (
        f"# Reasoning Swarm — {mode}{model_line}\n\n"
        f"## Task\n\n{problem}\n\n"
        f"## Skill Instructions\n\n{skill_content}\n"
    )


# ── Output formatting ─────────────────────────────────────────────────────


def format_output(result: SwarmResult, fmt: str, verbose: bool) -> str:
    """Format the result for display."""
    if fmt == "json":
        data = {
            "mode": result.mode,
            "confidence": result.confidence,
            "skill_file": result.skill_file,
            "model": result.model,
            "elapsed_ms": round(result.elapsed_ms, 2),
            "executed": result.executed,
            "metadata": result.metadata,
        }
        if verbose:
            data["prompt"] = result.prompt
        if result.trace:
            data["trace"] = result.trace
        return json.dumps(data, indent=2)

    if fmt == "markdown":
        lines = [
            f"# Reasoning Swarm — {result.mode}",
            "",
            f"**Confidence:** {result.confidence}/10",
            f"**Skill:** {result.skill_file}",
        ]
        if result.model:
            lines.append(f"**Model:** {result.model}")
        lines.append(f"**Elapsed:** {result.elapsed_ms:.0f}ms")
        if result.executed:
            lines.append(f"**Executed:** yes")
        lines.append("")
        if result.trace:
            lines.append("## Result")
            lines.append("")
            lines.append(result.trace)
            lines.append("")
        if verbose:
            lines.append("## Prompt")
            lines.append("")
            lines.append(result.prompt)
            lines.append("")
        return "\n".join(lines)

    # text format (default)
    parts = [
        f"Mode:       {result.mode}",
        f"Confidence: {result.confidence}/10",
        f"Skill:      {result.skill_file}",
    ]
    if result.model:
        parts.append(f"Model:      {result.model}")
    parts.append(f"Elapsed:    {result.elapsed_ms:.0f}ms")
    if result.executed:
        parts.append(f"Executed:   yes")
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

    t0 = time.perf_counter()

    mode = resolve_mode(args.mode, args.problem)
    skill_content = load_skill(mode)
    skill_file = get_skill_filename(mode)
    prompt = construct_prompt(args.problem, mode, skill_content, args.model)

    result = SwarmResult(
        mode=mode,
        confidence=_CONFIDENCE_DEFAULTS[mode],
        skill_file=skill_file,
        prompt=prompt,
        model=args.model,
        metadata={
            "problem": args.problem,
            "mode_requested": args.mode,
        },
    )

    # Execute against LLM unless --no-execute is set
    _, api_key, default_model = _get_api_config()
    should_execute = not args.no_execute and bool(api_key)

    if should_execute:
        try:
            exec_model = args.model or default_model
            result.model = exec_model
            trace = _call_llm(prompt, model=args.model)
            result.trace = trace
            result.executed = True
        except RuntimeError as exc:
            print(f"Execution failed: {exc}", file=sys.stderr)
            print("Falling back to prompt-only mode.", file=sys.stderr)
            result.metadata["error"] = str(exc)

    elapsed = (time.perf_counter() - t0) * 1000
    result.elapsed_ms = elapsed

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
            f"\n[mode={mode} | skill={skill_file} | "
            f"confidence={result.confidence}/10 | {exec_status}]",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
