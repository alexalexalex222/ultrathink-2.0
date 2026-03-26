"""Markdown calibration report generator with ASCII art charts.

Produces a self-contained markdown report from a CalibrationResult,
including calibration curve, distribution histogram, and bias analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from scoring.confidence_calibration import (
    CalibrationBin,
    CalibrationResult,
    ConfidenceCalibrator,
    ProblemResult,
)


def generate_report(
    results: Sequence[ProblemResult],
    calibrator: ConfidenceCalibrator | None = None,
    title: str = "Confidence Calibration Report",
) -> str:
    """Generate a full markdown calibration report."""
    if calibrator is None:
        calibrator = ConfidenceCalibrator()

    analysis = calibrator.analyze(results)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sections: list[str] = []
    sections.append(_render_header(title, now, analysis))
    sections.append(_render_summary(analysis))
    sections.append(_render_calibration_curve(analysis.bins, calibrator.num_bins))
    sections.append(_render_confidence_histogram(results))
    sections.append(_render_bin_table(analysis.bins))
    sections.append(_render_bias_section(analysis.bias_flags))
    sections.append(_render_verdict(analysis))

    return "\n\n".join(sections) + "\n"


# ------------------------------------------------------------------
# Section renderers
# ------------------------------------------------------------------


def _render_header(title: str, timestamp: str, analysis: CalibrationResult) -> str:
    status = "WELL CALIBRATED" if analysis.well_calibrated else "NEEDS IMPROVEMENT"
    icon = "[PASS]" if analysis.well_calibrated else "[FAIL]"
    return (
        f"# {title}\n"
        f"\n"
        f"Generated: {timestamp}\n"
        f"Samples: {analysis.n_samples}\n"
        f"Verdict: {icon} {status} (ECE={analysis.ece:.4f}, target<{analysis.target_ece})"
    )


def _render_summary(analysis: CalibrationResult) -> str:
    lines = [
        "## Summary Metrics",
        "",
        "| Metric | Value | Target |",
        "|--------|-------|--------|",
        f"| Expected Calibration Error (ECE) | {analysis.ece:.4f} | < {analysis.target_ece:.2f} |",
        f"| Brier Score | {analysis.brier_score:.4f} | < 0.25 |",
        f"| Overconfidence Rate | {analysis.overconfidence_rate:.1%} | < 20% |",
        f"| Underconfidence Rate | {analysis.underconfidence_rate:.1%} | < 20% |",
        f"| Biases Detected | {len(analysis.bias_flags)} | 0 |",
    ]
    return "\n".join(lines)


def _render_calibration_curve(bins: list[CalibrationBin], num_bins: int) -> str:
    lines = [
        "## Calibration Curve",
        "",
        "Each row shows a confidence bin. `#` marks actual accuracy, `|` marks mean confidence.",
        "A well-calibrated system has `|` close to `#` in every bin.",
        "",
    ]

    if not bins:
        lines.append("No data available.")
        return "\n".join(lines)

    # Use a 50-character wide chart
    width = 50
    lines.append(
        f"{'Bin':>11s}  {'n':>4s}  {'Conf':>5s}  {'Acc':>5s}  "
        f"{'Gap':>6s}  Accuracy"
    )
    lines.append("-" * (11 + 2 + 4 + 2 + 5 + 2 + 5 + 2 + 6 + 2 + width + 2))

    for b in bins:
        bar_len = int(round(b.mean_accuracy * width))
        conf_pos = int(round(b.mean_confidence * width))
        bar = ["."] * width
        for i in range(bar_len):
            bar[i] = "#"
        if 0 <= conf_pos < width:
            bar[conf_pos] = "|"

        lines.append(
            f"{b.bin_lo:5.2f}-{b.bin_hi:5.2f}  {b.count:4d}  "
            f"{b.mean_confidence:5.2f}  {b.mean_accuracy:5.2f}  "
            f"{b.gap:+6.3f}  [{''.join(bar)}]"
        )

    lines.append("")
    lines.append(f"{'0%':>{11 + 2 + 4 + 2 + 5 + 2 + 5 + 2 + 6 + 2}s}"
                 f"{'50%':>{width // 2}s}"
                 f"{'100%':>{width // 2}s}")
    lines.append("")
    lines.append("Legend: `#` = actual accuracy, `|` = mean confidence, `.` = empty region")

    return "\n".join(lines)


def _render_confidence_histogram(results: Sequence[ProblemResult]) -> str:
    lines = [
        "## Confidence Distribution",
        "",
    ]

    if not results:
        lines.append("No data available.")
        return "\n".join(lines)

    # Bin confidence values (0-1 scale) into 10 buckets
    n_buckets = 10
    buckets = [0] * n_buckets
    for r in results:
        c = max(0.0, min(1.0, r.confidence))
        idx = min(int(c * n_buckets), n_buckets - 1)
        buckets[idx] += 1

    max_count = max(buckets) if buckets else 1
    bar_width = 40

    for i, count in enumerate(buckets):
        lo = i / n_buckets
        hi = (i + 1) / n_buckets
        bar_len = int(round(count / max_count * bar_width)) if max_count > 0 else 0
        bar = "=" * bar_len
        lines.append(f"  {lo:.1f}-{hi:.1f} | {bar} {count}")

    lines.append("")
    return "\n".join(lines)


def _render_bin_table(bins: list[CalibrationBin]) -> str:
    lines = [
        "## Bin Details",
        "",
        "| Bin Range | Count | Mean Confidence | Mean Accuracy | Gap |",
        "|-----------|-------|-----------------|---------------|-----|",
    ]

    for b in bins:
        lines.append(
            f"| {b.bin_lo:.2f}-{b.bin_hi:.2f} | {b.count} | "
            f"{b.mean_confidence:.3f} | {b.mean_accuracy:.3f} | {b.gap:+.3f} |"
        )

    return "\n".join(lines)


def _render_bias_section(biases: list) -> str:
    lines = [
        "## Bias Analysis",
        "",
    ]

    if not biases:
        lines.append("No systematic biases detected.")
        return "\n".join(lines)

    for b in biases:
        severity_tag = b.severity.upper()
        lines.append(f"### [{severity_tag}] {b.name}")
        lines.append("")
        lines.append(f"**Description:** {b.description}")
        lines.append(f"**Evidence:** {b.evidence}")
        lines.append("")

    return "\n".join(lines)


def _render_verdict(analysis: CalibrationResult) -> str:
    lines = [
        "## Verdict",
        "",
    ]

    if analysis.well_calibrated:
        lines.append(
            f"The confidence scorer is **well-calibrated** with ECE={analysis.ece:.4f} "
            f"(target: < {analysis.target_ece})."
        )
    else:
        lines.append(
            f"The confidence scorer **needs improvement**. ECE={analysis.ece:.4f} "
            f"exceeds target of {analysis.target_ece}."
        )

    lines.append("")

    # Recommendations
    lines.append("### Recommendations")
    lines.append("")

    if analysis.overconfidence_rate > 0.5:
        lines.append("- Reduce confidence scores — system is systematically overconfident")
    if analysis.underconfidence_rate > 0.5:
        lines.append("- Increase confidence scores — system is systematically underconfident")
    if analysis.brier_score > 0.25:
        lines.append("- Improve discrimination between correct and incorrect answers")

    for b in analysis.bias_flags:
        if b.name == "flat_confidence":
            lines.append("- Calibrate confidence to respond to task difficulty variations")
        elif b.name == "confidence_compression":
            lines.append("- Use a wider range of confidence scores to better differentiate certainty")
        elif b.name == "difficulty_blind":
            lines.append("- Adjust confidence based on problem difficulty level")
        elif b.name == "mode_insensitive":
            lines.append("- Vary confidence based on reasoning mode depth")

    if analysis.well_calibrated and not analysis.bias_flags:
        lines.append("No action needed — scorer is performing well.")

    return "\n".join(lines)
