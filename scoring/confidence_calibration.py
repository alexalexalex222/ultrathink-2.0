"""Confidence calibration scorer for reasoning swarm.

Measures how well confidence scores predict actual correctness using:
- Expected Calibration Error (ECE)
- Brier Score
- Over/underconfidence rates
- Systematic bias detection
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence


@dataclass
class ProblemResult:
    """A single problem's confidence vs correctness record."""

    problem_id: str
    confidence: float
    correct: bool
    mode: str = ""
    difficulty: str = ""
    description: str = ""

    @property
    def correctness_int(self) -> int:
        return 1 if self.correct else 0


@dataclass
class CalibrationBin:
    """Aggregated stats for one confidence bin."""

    bin_lo: float
    bin_hi: float
    mean_confidence: float
    mean_accuracy: float
    count: int
    gap: float  # |mean_confidence - mean_accuracy|


@dataclass
class BiasFlag:
    """A detected systematic bias."""

    name: str
    description: str
    severity: str  # "low", "medium", "high"
    evidence: str


@dataclass
class CalibrationResult:
    """Full calibration analysis output."""

    ece: float
    brier_score: float
    overconfidence_rate: float
    underconfidence_rate: float
    n_samples: int
    bins: list[CalibrationBin] = field(default_factory=list)
    bias_flags: list[BiasFlag] = field(default_factory=list)
    well_calibrated: bool = False
    target_ece: float = 0.1


class ConfidenceCalibrator:
    """Compute calibration metrics from a set of problem results."""

    DEFAULT_NUM_BINS = 10
    TARGET_ECE = 0.1

    def __init__(self, num_bins: int = DEFAULT_NUM_BINS, target_ece: float = TARGET_ECE) -> None:
        self.num_bins = num_bins
        self.target_ece = target_ece

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, results: Sequence[ProblemResult]) -> CalibrationResult:
        """Run full calibration analysis on a sequence of problem results."""
        if not results:
            return CalibrationResult(
                ece=0.0,
                brier_score=0.0,
                overconfidence_rate=0.0,
                underconfidence_rate=0.0,
                n_samples=0,
                well_calibrated=True,
                target_ece=self.target_ece,
            )

        bins = self._bin_results(results)
        ece = self._compute_ece(bins, len(results))
        brier = self._compute_brier(results)
        over_rate = self._compute_overconfidence_rate(results)
        under_rate = self._compute_underconfidence_rate(results)
        biases = self._detect_biases(results, bins)

        return CalibrationResult(
            ece=ece,
            brier_score=brier,
            overconfidence_rate=over_rate,
            underconfidence_rate=under_rate,
            n_samples=len(results),
            bins=bins,
            bias_flags=biases,
            well_calibrated=ece < self.target_ece,
            target_ece=self.target_ece,
        )

    def compute_ece(self, results: Sequence[ProblemResult]) -> float:
        """Return the Expected Calibration Error."""
        bins = self._bin_results(results)
        return self._compute_ece(bins, len(results))

    def compute_brier_score(self, results: Sequence[ProblemResult]) -> float:
        """Return the Brier score (lower is better)."""
        return self._compute_brier(results)

    def generate_calibration_curve(
        self, results: Sequence[ProblemResult], width: int = 60
    ) -> list[str]:
        """Return ASCII-art calibration curve lines (confidence bins vs actual accuracy).

        Each line represents one bin.  The x-axis shows accuracy (0-1).
        """
        bins = self._bin_results(results)
        if not bins:
            return ["(no data)"]

        lines: list[str] = []
        header = (
            f"{'Bin':>12s}  {'n':>4s}  {'Conf':>5s}  {'Acc':>5s}  "
            f"{'Gap':>6s}  Calibration Curve"
        )
        lines.append(header)
        lines.append("-" * len(header) + "-" * (width + 2))

        for b in bins:
            bar_len = int(round(b.mean_accuracy * width))
            conf_marker = int(round(b.mean_confidence * width))
            bar = list("." * width)
            for i in range(bar_len):
                bar[i] = "#"
            if 0 <= conf_marker < width:
                bar[conf_marker] = "|"
            bar_str = "".join(bar)

            lines.append(
                f"{b.bin_lo:5.2f}-{b.bin_hi:5.2f}  {b.count:4d}  "
                f"{b.mean_confidence:5.2f}  {b.mean_accuracy:5.2f}  "
                f"{b.gap:+6.3f}  [{bar_str}]"
            )

        lines.append("")
        lines.append("Legend: # = accuracy, | = mean confidence, . = empty region")
        return lines

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bin_results(self, results: Sequence[ProblemResult]) -> list[CalibrationBin]:
        """Assign results to confidence bins and compute per-bin stats."""
        n_bins = self.num_bins
        bin_width = 1.0 / n_bins

        # Collect items per bin
        bin_items: list[list[ProblemResult]] = [[] for _ in range(n_bins)]
        for r in results:
            # Clamp confidence to [0, 1]
            c = max(0.0, min(1.0, r.confidence))
            idx = min(int(c * n_bins), n_bins - 1)
            bin_items[idx].append(r)

        bins: list[CalibrationBin] = []
        for i, items in enumerate(bin_items):
            if not items:
                continue
            lo = i * bin_width
            hi = (i + 1) * bin_width
            mean_conf = sum(r.confidence for r in items) / len(items)
            mean_acc = sum(r.correctness_int for r in items) / len(items)
            bins.append(
                CalibrationBin(
                    bin_lo=lo,
                    bin_hi=hi,
                    mean_confidence=mean_conf,
                    mean_accuracy=mean_acc,
                    count=len(items),
                    gap=abs(mean_conf - mean_acc),
                )
            )
        return bins

    def _compute_ece(self, bins: list[CalibrationBin], n_total: int) -> float:
        """Expected Calibration Error = weighted average of |conf - acc| per bin."""
        if n_total == 0:
            return 0.0
        return sum(b.count * b.gap for b in bins) / n_total

    def _compute_brier(self, results: Sequence[ProblemResult]) -> float:
        """Brier score = mean of (confidence - correctness)^2."""
        if not results:
            return 0.0
        return sum((r.confidence - r.correctness_int) ** 2 for r in results) / len(results)

    def _compute_overconfidence_rate(
        self, results: Sequence[ProblemResult]
    ) -> float:
        """Fraction of results where confidence > actual correctness (1 or 0)."""
        if not results:
            return 0.0
        over = sum(1 for r in results if r.confidence > r.correctness_int)
        return over / len(results)

    def _compute_underconfidence_rate(
        self, results: Sequence[ProblemResult]
    ) -> float:
        """Fraction of results where confidence < actual correctness."""
        if not results:
            return 0.0
        under = sum(1 for r in results if r.confidence < r.correctness_int)
        return under / len(results)

    def _detect_biases(
        self, results: Sequence[ProblemResult], bins: list[CalibrationBin]
    ) -> list[BiasFlag]:
        """Detect systematic biases in confidence scoring."""
        flags: list[BiasFlag] = []
        if len(results) < 3:
            return flags

        # 1. Flat confidence — always rates the same value
        confidences = [r.confidence for r in results]
        unique_confs = set(confidences)
        if len(unique_confs) <= 2:
            most_common = max(set(confidences), key=confidences.count)
            flags.append(
                BiasFlag(
                    name="flat_confidence",
                    description=(
                        f"System assigns nearly identical confidence "
                        f"({most_common:.2f}) regardless of difficulty"
                    ),
                    severity="high",
                    evidence=f"{len(unique_confs)} unique values out of {len(results)} results",
                )
            )

        # 2. Overconfidence — ECE driven by overconfidence
        over_rate = self._compute_overconfidence_rate(results)
        if over_rate > 0.7:
            flags.append(
                BiasFlag(
                    name="systematic_overconfidence",
                    description="System is overconfident in most cases",
                    severity="high" if over_rate > 0.85 else "medium",
                    evidence=f"overconfidence rate = {over_rate:.1%}",
                )
            )

        # 3. Underconfidence
        under_rate = self._compute_underconfidence_rate(results)
        if under_rate > 0.7:
            flags.append(
                BiasFlag(
                    name="systematic_underconfidence",
                    description="System is underconfident in most cases",
                    severity="high" if under_rate > 0.85 else "medium",
                    evidence=f"underconfidence rate = {under_rate:.1%}",
                )
            )

        # 4. Difficulty-blindness — confidence doesn't correlate with difficulty
        difficulty_levels = {"low": 0, "medium": 1, "high": 2, "extreme": 3}
        has_difficulty = any(r.difficulty for r in results)
        if has_difficulty:
            diff_groups: dict[str, list[float]] = {}
            for r in results:
                if r.difficulty:
                    key = r.difficulty.lower()
                    diff_groups.setdefault(key, []).append(r.confidence)
            if len(diff_groups) >= 2:
                means = {k: sum(v) / len(v) for k, v in diff_groups.items()}
                # Check if confidence doesn't decrease with difficulty
                ordered_keys = [
                    k for k in ["low", "medium", "high", "extreme"] if k in means
                ]
                if len(ordered_keys) >= 3:
                    monotonic_decrease = all(
                        means[ordered_keys[i]] >= means[ordered_keys[i + 1]]
                        for i in range(len(ordered_keys) - 1)
                    )
                    if not monotonic_decrease:
                        flags.append(
                            BiasFlag(
                                name="difficulty_blind",
                                description="Confidence does not correlate with difficulty level",
                                severity="medium",
                                evidence=", ".join(
                                    f"{k}: {means[k]:.2f}" for k in ordered_keys
                                ),
                            )
                        )

        # 5. Confidence compression — confidence range too narrow
        conf_range = max(confidences) - min(confidences)
        if len(results) >= 5 and conf_range < 0.3:
            flags.append(
                BiasFlag(
                    name="confidence_compression",
                    description="Confidence scores are compressed into a narrow range",
                    severity="medium",
                    evidence=f"range = {conf_range:.2f} "
                             f"[{min(confidences):.2f}, {max(confidences):.2f}]",
                )
            )

        # 6. Mode-insensitivity — same confidence across different modes
        mode_groups: dict[str, list[float]] = {}
        for r in results:
            if r.mode:
                mode_groups.setdefault(r.mode, []).append(r.confidence)
        if len(mode_groups) >= 3:
            mode_means = {k: sum(v) / len(v) for k, v in mode_groups.items()}
            mode_range = max(mode_means.values()) - min(mode_means.values())
            if mode_range < 0.15:
                flags.append(
                    BiasFlag(
                        name="mode_insensitive",
                        description="Confidence does not vary across reasoning modes",
                        severity="low",
                        evidence=", ".join(
                            f"{k}: {v:.2f}" for k, v in mode_means.items()
                        ),
                    )
                )

        return flags


def classify_confidence(
    confidence: float, correct: bool, tol: float = 0.1
) -> str:
    """Classify a single result as well-calibrated, overconfident, or underconfident."""
    if correct:
        diff = confidence - 1.0
    else:
        diff = confidence - 0.0

    if abs(diff) <= tol:
        return "well_calibrated"
    return "overconfident" if diff > 0 else "underconfident"
