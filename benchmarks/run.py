#!/usr/bin/env python3
"""CLI entry point for the Reasoning Swarm benchmark suite.

Usage:
    python benchmarks/run.py                   # run all benchmarks with auto-classifier
    python benchmarks/run.py --mode ENSEMBLE   # force ENSEMBLE mode for all problems
    python benchmarks/run.py --mode RAPID      # force RAPID STRIKE for all problems

Exit codes:
    0 — all benchmarks passed
    1 — one or more benchmarks failed
"""

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `benchmarks.framework` resolves
# when this file is executed directly (python benchmarks/run.py).
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from benchmarks.framework import main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reasoning Swarm Benchmark Runner",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default=None,
        choices=["RAPID", "DEEP", "ENSEMBLE", "MEGAMIND", "GRAND_JURY"],
        help="Force a specific reasoning mode for all problems",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(main(mode_override=args.mode))
