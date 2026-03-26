"""Benchmark: Intake classifier accuracy across 50+ labeled problems.

Measures classify_task() accuracy against a golden set of labeled problems.
Target: >95% accuracy.

Usage:
    python benchmarks/test_classifier_accuracy.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

# Add project root to path so we can import benchmarks
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks import classify_task


GOLDENS_PATH = Path(__file__).resolve().parent / "classifier_goldens.json"
MODE_NAMES = {"RAPID": "Rapid Strike", "DEEP": "Deep Think", "ENSEMBLE": "Ensemble", "MEGA": "Megamind", "JURY": "Grand Jury"}


def load_goldens():
    with open(GOLDENS_PATH) as f:
        return json.load(f)


def run_benchmark():
    goldens = load_goldens()
    total = len(goldens)
    correct = 0
    misclassifications = []
    actual_modes = Counter()
    expected_modes = Counter()

    for problem in goldens:
        actual = classify_task(
            task_type=problem["task_type"],
            complexity=problem["complexity"],
            stakes=problem["stakes"],
            prior_fails=problem["prior_fails"],
            files_involved=problem.get("files_involved", "1-2"),
            framework_css=problem.get("framework_css", False),
            production=problem.get("production", False),
            user_hint=problem.get("user_hint"),
        )
        expected = problem["expected_mode"]

        actual_modes[actual] += 1
        expected_modes[expected] += 1

        if actual == expected:
            correct += 1
        else:
            misclassifications.append({
                "id": problem["id"],
                "description": problem["task_description"],
                "task_type": problem["task_type"],
                "complexity": problem["complexity"],
                "stakes": problem["stakes"],
                "prior_fails": problem["prior_fails"],
                "files_involved": problem.get("files_involved", "1-2"),
                "framework_css": problem.get("framework_css", False),
                "production": problem.get("production", False),
                "user_hint": problem.get("user_hint"),
                "expected": expected,
                "actual": actual,
            })

    accuracy = (correct / total) * 100

    # --- Report ---
    print("=" * 72)
    print("INTAKE CLASSIFIER ACCURACY BENCHMARK")
    print("=" * 72)
    print(f"\nTotal problems: {total}")
    print(f"Correct:        {correct}")
    print(f"Misclassified:  {len(misclassifications)}")
    print(f"Accuracy:       {accuracy:.1f}%")
    print(f"Target:         >95%")
    print(f"Status:         {'PASS' if accuracy >= 95 else 'FAIL'}")

    # Mode distribution
    print(f"\n{'─' * 72}")
    print("MODE DISTRIBUTION")
    print(f"{'─' * 72}")
    print(f"{'Mode':<15} {'Actual':>8} {'Expected':>10} {'Match':>8}")
    print(f"{'─' * 42}")
    for mode in ["RAPID", "DEEP", "ENSEMBLE", "MEGA", "JURY"]:
        actual_count = actual_modes.get(mode, 0)
        expected_count = expected_modes.get(mode, 0)
        actual_pct = (actual_count / total) * 100
        expected_pct = (expected_count / total) * 100
        print(f"{MODE_NAMES[mode]:<15} {actual_count:>4} ({actual_pct:4.1f}%)  {expected_count:>4} ({expected_pct:4.1f}%)")

    # Misclassifications
    if misclassifications:
        print(f"\n{'─' * 72}")
        print("MISCLASSIFICATIONS")
        print(f"{'─' * 72}")
        for mc in misclassifications:
            print(f"\n  #{mc['id']}: {mc['description']}")
            print(f"    type={mc['task_type']}  complexity={mc['complexity']}  "
                  f"stakes={mc['stakes']}  prior_fails={mc['prior_fails']}")
            extras = []
            if mc.get("files_involved"):
                extras.append(f"files={mc['files_involved']}")
            if mc.get("framework_css"):
                extras.append("framework_css=True")
            if mc.get("production"):
                extras.append("production=True")
            if mc.get("user_hint"):
                extras.append(f'hint="{mc["user_hint"]}"')
            if extras:
                print(f"    {', '.join(extras)}")
            print(f"    Expected: {MODE_NAMES[mc['expected']]} ({mc['expected']})")
            print(f"    Actual:   {MODE_NAMES[mc['actual']]} ({mc['actual']})")
            print(f"    Analysis: Mode mismatch — {mc['actual']} returned where {mc['expected']} was expected")
    else:
        print(f"\n{'─' * 72}")
        print("No misclassifications found.")

    print(f"\n{'=' * 72}")

    return accuracy, misclassifications


if __name__ == "__main__":
    accuracy, misses = run_benchmark()
    sys.exit(0 if accuracy >= 95 else 1)
