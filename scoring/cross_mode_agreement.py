"""Cross-mode agreement analysis for reasoning swarm.

Analyzes agreement patterns across reasoning modes (Rapid Strike, Deep Think,
Ensemble, Megamind) to measure how each mode adds value over the previous one.

Metrics:
- Agreement rate: % of shared conclusions across modes
- Discovery rate: new insights per mode escalation
- Contradiction rate: conflicting conclusions between modes
- Risk identification: risks found per mode
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Sequence


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODE_HIERARCHY = ["RAPID", "DEEP", "ENSEMBLE", "MEGAMIND"]

RISK_KEYWORDS = frozenset({
    "risk", "danger", "warning", "caution", "vulnerability", "failure",
    "break", "crash", "overflow", "leak", "race condition", "deadlock",
    "security", "injection", "exploit", "timeout", "edge case", "corner case",
    "regression", "side effect", "memory leak", "data loss", "corruption",
    "bottleneck", "scalability", "contention", "single point of failure",
    "dependency", "coupling", "fragile", "brittle", "deprecat", "breaking change",
    "backwards compat", "migration", "downtime", "latency spike",
})

NEGATION_WORDS = frozenset({
    "not", "no", "never", "neither", "nor", "cannot", "can't", "won't",
    "don't", "doesn't", "isn't", "aren't", "wasn't", "weren't", "shouldn't",
    "wouldn't", "couldn't", "mustn't", "impossible", "incorrect", "wrong",
    "false", "avoid", "never", "do not", "should not", "must not",
})

CONTRADICTION_PAIRS = [
    ("should", "should not"), ("must", "must not"), ("will", "will not"),
    ("safe", "unsafe"), ("correct", "incorrect"), ("fast", "slow"),
    ("simple", "complex"), ("secure", "insecure"), ("scalable", "not scalable"),
    ("reliable", "unreliable"), ("necessary", "unnecessary"),
    ("recommended", "not recommended"), ("possible", "impossible"),
    ("efficient", "inefficient"), ("optimal", "suboptimal"),
    ("increase", "decrease"), ("add", "remove"), ("use", "avoid"),
    ("enable", "disable"), ("include", "exclude"),
]

CLAIM_MIN_LENGTH = 15
SIMILARITY_THRESHOLD = 0.65


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Claim:
    """A single extracted claim from a mode's output."""
    text: str
    normalized: str
    source_mode: str
    is_risk: bool = False
    category: str = "conclusion"  # conclusion | risk | recommendation | observation


@dataclass
class ModeAnalysis:
    """Analysis results for a single mode."""
    mode: str
    claims: list[Claim] = field(default_factory=list)
    risk_claims: list[Claim] = field(default_factory=list)
    unique_claims: list[Claim] = field(default_factory=list)
    claim_count: int = 0
    risk_count: int = 0
    unique_count: int = 0


@dataclass
class Contradiction:
    """A detected contradiction between two modes."""
    mode_a: str
    mode_b: str
    claim_a: str
    claim_b: str
    severity: str  # "hard" (explicit negation) | "soft" (directional conflict)
    description: str = ""


@dataclass
class AgreementResult:
    """Full cross-mode agreement analysis output."""
    # Per-mode analysis
    mode_analyses: dict[str, ModeAnalysis] = field(default_factory=dict)

    # Core metrics
    agreement_rate: float = 0.0
    total_unique_claims: int = 0
    shared_claims: int = 0

    # Discovery metrics
    discovery_rate_per_mode: dict[str, float] = field(default_factory=dict)
    cumulative_discovery_rate: list[tuple[str, float]] = field(default_factory=list)

    # Contradiction metrics
    contradictions: list[Contradiction] = field(default_factory=list)
    contradiction_rate: float = 0.0

    # Risk metrics
    risks_per_mode: dict[str, int] = field(default_factory=dict)
    cumulative_risks: list[tuple[str, int]] = field(default_factory=list)

    # Value-add analysis
    mode_value_add: list[dict] = field(default_factory=list)

    # Agreement clusters (groups of claims found across modes)
    agreement_clusters: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------

class ClaimExtractor:
    """Extract structured claims from mode output text."""

    # Patterns that indicate conclusion sentences
    CONCLUSION_PATTERNS = [
        r"(?:the\s+)?(?:best|optimal|recommended|correct|right)\s+(?:approach|solution|way|pattern)\s+is",
        r"(?:I|we)\s+(?:recommend|suggest|advise|propose)",
        r"(?:this|that)\s+(?:will|would|should|could)\s+\w+",
        r"(?:the\s+)?(?:key|main|primary|critical)\s+(?:issue|problem|concern|point|takeaway)",
        r"in\s+(?:conclusion|summary|short)",
        r"(?:overall|ultimately|fundamentally)",
        r"(?:use|prefer|choose|select|pick)\s+\w+\s+(?:because|since|as)",
        r"(?:avoid|don't|do\s+not)\s+\w+\s+(?:because|since|as)",
    ]

    # Patterns that indicate risk/warning sentences
    RISK_PATTERNS = [
        r"(?:risk|danger|warning|caution|watch\s+out|be\s+careful)",
        r"(?:could|might|may)\s+(?:fail|break|crash|leak|overflow)",
        r"(?:edge|corner)\s+case",
        r"(?:race\s+condition|deadlock|contention|bottleneck)",
        r"(?:security|vulnerability|exploit|injection)",
        r"(?:single\s+point\s+of\s+failure|SPOF)",
        r"(?:watch|beware|note|notice)\s+(?:that|the|for|out)",
        r"(?:downside|drawback|trade[-\s]?off|limitation|caveat)",
    ]

    # Patterns for field extraction from structured output
    FIELD_PATTERNS = [
        # CONCLUSION: ... or Key takeaway: ...
        r"(?:conclusion|key\s+takeaway|recommendation|resolution|verdict|answer|recommendation|selected)\s*:\s*(.+)",
        # Structured box fields like "PROBLEM: [text]"
        r"^(?:problem|answer|solution|approach|action|recommendation|finding)\s*:\s*(.+)",
    ]

    def extract(self, text: str, mode: str) -> list[Claim]:
        """Extract claims from mode output text."""
        claims: list[Claim] = []
        seen_normalized: set[str] = set()

        sentences = self._split_sentences(text)

        for sent in sentences:
            if len(sent.strip()) < CLAIM_MIN_LENGTH:
                continue

            normalized = self._normalize(sent)
            if normalized in seen_normalized:
                continue

            is_risk = self._is_risk(sent)
            category = self._classify_category(sent, is_risk)

            claim = Claim(
                text=sent.strip(),
                normalized=normalized,
                source_mode=mode,
                is_risk=is_risk,
                category=category,
            )
            claims.append(claim)
            seen_normalized.add(normalized)

        # Also extract from structured fields
        for pattern in self.FIELD_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                field_text = match.group(1).strip()
                if len(field_text) < CLAIM_MIN_LENGTH:
                    continue
                normalized = self._normalize(field_text)
                if normalized in seen_normalized:
                    continue
                is_risk = self._is_risk(field_text)
                category = self._classify_category(field_text, is_risk)
                claim = Claim(
                    text=field_text.strip(),
                    normalized=normalized,
                    source_mode=mode,
                    is_risk=is_risk,
                    category=category,
                )
                claims.append(claim)
                seen_normalized.add(normalized)

        return claims

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences, including structured field values."""
        # First, handle lines that are part of structured output
        lines = text.split("\n")
        sentences: list[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Strip markdown formatting
            line = re.sub(r"^#+\s*", "", line)
            line = re.sub(r"^\s*[-*]\s*", "", line)
            line = re.sub(r"^\d+\.\s*", "", line)
            line = re.sub(r"^>\s*", "", line)
            # Strip box-drawing characters
            line = re.sub(r"[│┌┐└┘─├┤┬┴┼]", "", line).strip()

            if not line:
                continue

            # Split on sentence boundaries
            parts = re.split(r"(?<=[.!?])\s+", line)
            for part in parts:
                part = part.strip()
                if part and len(part) >= CLAIM_MIN_LENGTH:
                    sentences.append(part)

        return sentences

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        text = text.lower().strip()
        # Remove punctuation
        text = re.sub(r"[^\w\s]", "", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text

    def _is_risk(self, text: str) -> bool:
        """Check if text describes a risk or warning."""
        lower = text.lower()
        return any(kw in lower for kw in RISK_KEYWORDS)

    def _classify_category(self, text: str, is_risk: bool) -> str:
        """Classify claim into a category."""
        if is_risk:
            return "risk"
        lower = text.lower()
        if any(p in lower for p in ["recommend", "suggest", "should", "use ", "avoid",
                                      "choose", "prefer", "implement", "adopt"]):
            return "recommendation"
        if any(p in lower for p in ["observe", "notice", "appears", "seems", "tends",
                                      "pattern", "typically"]):
            return "observation"
        return "conclusion"


# ---------------------------------------------------------------------------
# Agreement analysis
# ---------------------------------------------------------------------------

class CrossModeAgreementScorer:
    """Analyze agreement patterns across reasoning modes."""

    def __init__(self, similarity_threshold: float = SIMILARITY_THRESHOLD) -> None:
        self.similarity_threshold = similarity_threshold
        self.extractor = ClaimExtractor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        mode_outputs: dict[str, str],
    ) -> AgreementResult:
        """Run full cross-mode agreement analysis.

        Args:
            mode_outputs: Mapping of mode name to raw output text.
                         Keys should be from MODE_HIERARCHY (RAPID, DEEP, ENSEMBLE, MEGAMIND).

        Returns:
            AgreementResult with all metrics populated.
        """
        # Step 1: Extract claims from each mode
        mode_claims: dict[str, list[Claim]] = {}
        for mode in MODE_HIERARCHY:
            text = mode_outputs.get(mode, "")
            if text:
                mode_claims[mode] = self.extractor.extract(text, mode)
            else:
                mode_claims[mode] = []

        # Step 2: Build agreement clusters (groups of similar claims across modes)
        clusters = self._build_agreement_clusters(mode_claims)

        # Step 3: Identify mode-specific discoveries
        mode_unique = self._find_unique_claims(mode_claims, clusters)

        # Step 4: Detect contradictions
        contradictions = self._detect_contradictions(mode_claims)

        # Step 5: Build per-mode analysis
        mode_analyses: dict[str, ModeAnalysis] = {}
        for mode in MODE_HIERARCHY:
            claims = mode_claims.get(mode, [])
            risks = [c for c in claims if c.is_risk]
            unique = mode_unique.get(mode, [])
            mode_analyses[mode] = ModeAnalysis(
                mode=mode,
                claims=claims,
                risk_claims=risks,
                unique_claims=unique,
                claim_count=len(claims),
                risk_count=len(risks),
                unique_count=len(unique),
            )

        # Step 6: Compute metrics
        total_claims = sum(ma.claim_count for ma in mode_analyses.values())
        shared_clusters = [c for c in clusters if len(c["modes"]) >= 2]
        shared_claim_count = sum(len(c["claims"]) for c in shared_clusters)

        agreement_rate = (
            shared_claim_count / total_claims if total_claims > 0 else 0.0
        )

        # Discovery rate per mode
        discovery_rate_per_mode: dict[str, float] = {}
        for mode in MODE_HIERARCHY:
            ma = mode_analyses.get(mode)
            if ma and ma.claim_count > 0:
                discovery_rate_per_mode[mode] = ma.unique_count / ma.claim_count
            else:
                discovery_rate_per_mode[mode] = 0.0

        # Cumulative discovery
        cumulative_discovery: list[tuple[str, float]] = []
        all_seen_normalized: set[str] = set()
        for mode in MODE_HIERARCHY:
            claims = mode_claims.get(mode, [])
            new_count = 0
            for c in claims:
                if c.normalized not in all_seen_normalized:
                    new_count += 1
                    all_seen_normalized.add(c.normalized)
            total_so_far = len(all_seen_normalized)
            cumulative_discovery.append(
                (mode, new_count / total_so_far if total_so_far > 0 else 0.0)
            )

        # Risk metrics
        risks_per_mode = {
            mode: mode_analyses[mode].risk_count for mode in MODE_HIERARCHY
            if mode in mode_analyses
        }
        cumulative_risks: list[tuple[str, int]] = []
        total_risks = 0
        for mode in MODE_HIERARCHY:
            if mode in mode_analyses:
                total_risks += mode_analyses[mode].risk_count
                cumulative_risks.append((mode, total_risks))

        # Contradiction rate
        contradiction_rate = (
            len(contradictions) / total_claims if total_claims > 0 else 0.0
        )

        # Value-add analysis
        mode_value_add = self._compute_value_add(mode_claims, clusters, mode_unique)

        return AgreementResult(
            mode_analyses=mode_analyses,
            agreement_rate=agreement_rate,
            total_unique_claims=len(all_seen_normalized),
            shared_claims=shared_claim_count,
            discovery_rate_per_mode=discovery_rate_per_mode,
            cumulative_discovery_rate=cumulative_discovery,
            contradictions=contradictions,
            contradiction_rate=contradiction_rate,
            risks_per_mode=risks_per_mode,
            cumulative_risks=cumulative_risks,
            mode_value_add=mode_value_add,
            agreement_clusters=shared_clusters,
        )

    def analyze_problems(
        self,
        problems: list[dict[str, dict[str, str]]],
    ) -> list[AgreementResult]:
        """Analyze agreement across multiple problems.

        Args:
            problems: List of dicts, each mapping mode name to output text.
                      e.g. [{"RAPID": "...", "DEEP": "...", ...}, ...]

        Returns:
            List of AgreementResult, one per problem.
        """
        return [self.analyze(p) for p in problems]

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(self, result: AgreementResult, title: str = "Cross-Mode Agreement Report") -> str:
        """Generate a markdown report from agreement analysis."""
        sections: list[str] = []
        sections.append(self._report_header(result, title))
        sections.append(self._report_overview(result))
        sections.append(self._report_mode_details(result))
        sections.append(self._report_agreement_clusters(result))
        sections.append(self._report_discovery_analysis(result))
        sections.append(self._report_risk_analysis(result))
        sections.append(self._report_contradictions(result))
        sections.append(self._report_value_add(result))
        sections.append(self._report_verdict(result))
        return "\n\n".join(sections) + "\n"

    # ------------------------------------------------------------------
    # Internal: agreement clusters
    # ------------------------------------------------------------------

    def _build_agreement_clusters(
        self,
        mode_claims: dict[str, list[Claim]],
    ) -> list[dict]:
        """Group claims from different modes that are semantically similar."""
        all_claims: list[Claim] = []
        for mode in MODE_HIERARCHY:
            all_claims.extend(mode_claims.get(mode, []))

        if not all_claims:
            return []

        # Greedy clustering: for each claim, check if it fits an existing cluster
        clusters: list[dict] = []
        claim_to_cluster: dict[int, int] = {}  # claim index -> cluster index

        for i, claim in enumerate(all_claims):
            best_cluster_idx = -1
            best_similarity = 0.0

            for ci, cluster in enumerate(clusters):
                # Compare against representative claim in cluster
                rep = cluster["representative"]
                sim = SequenceMatcher(None, claim.normalized, rep.normalized).ratio()
                if sim > best_similarity:
                    best_similarity = sim
                    best_cluster_idx = ci

            if best_similarity >= self.similarity_threshold and best_cluster_idx >= 0:
                cluster = clusters[best_cluster_idx]
                cluster["claims"].append(claim)
                cluster["modes"].add(claim.source_mode)
                # Keep the longest claim as representative
                if len(claim.text) > len(cluster["representative"].text):
                    cluster["representative"] = claim
                claim_to_cluster[i] = best_cluster_idx
            else:
                clusters.append({
                    "representative": claim,
                    "claims": [claim],
                    "modes": {claim.source_mode},
                })
                claim_to_cluster[i] = len(clusters) - 1

        # Convert sets to sorted lists for serialization
        for cluster in clusters:
            cluster["modes"] = sorted(cluster["modes"])

        # Sort by number of modes (descending) then number of claims
        clusters.sort(key=lambda c: (len(c["modes"]), len(c["claims"])), reverse=True)

        return clusters

    def _find_unique_claims(
        self,
        mode_claims: dict[str, list[Claim]],
        clusters: list[dict],
    ) -> dict[str, list[Claim]]:
        """Find claims that appear in only one mode (mode-specific discoveries)."""
        unique: dict[str, list[Claim]] = {mode: [] for mode in MODE_HIERARCHY}

        for cluster in clusters:
            if len(cluster["modes"]) == 1:
                mode = cluster["modes"][0]
                unique[mode].extend(cluster["claims"])

        return unique

    # ------------------------------------------------------------------
    # Internal: contradiction detection
    # ------------------------------------------------------------------

    def _detect_contradictions(
        self,
        mode_claims: dict[str, list[Claim]],
    ) -> list[Contradiction]:
        """Detect contradictory claims between modes."""
        contradictions: list[Contradiction] = []

        modes_with_claims = [m for m in MODE_HIERARCHY if mode_claims.get(m)]

        for i, mode_a in enumerate(modes_with_claims):
            for mode_b in modes_with_claims[i + 1:]:
                for claim_a in mode_claims[mode_a]:
                    for claim_b in mode_claims[mode_b]:
                        contradiction = self._check_contradiction(
                            claim_a, claim_b, mode_a, mode_b
                        )
                        if contradiction:
                            contradictions.append(contradiction)

        # Deduplicate by claim text pairs
        seen: set[tuple[str, str]] = set()
        unique_contradictions: list[Contradiction] = []
        for c in contradictions:
            key = (c.claim_a[:80], c.claim_b[:80])
            if key not in seen:
                seen.add(key)
                unique_contradictions.append(c)

        return unique_contradictions

    def _check_contradiction(
        self,
        claim_a: Claim,
        claim_b: Claim,
        mode_a: str,
        mode_b: str,
    ) -> Contradiction | None:
        """Check if two claims contradict each other."""
        norm_a = claim_a.normalized
        norm_b = claim_b.normalized

        # Check for explicit negation pairs
        for pos, neg in CONTRADICTION_PAIRS:
            # Both must share significant context (subject overlap)
            if pos in norm_a and neg in norm_b:
                if self._share_subject(norm_a, norm_b):
                    return Contradiction(
                        mode_a=mode_a,
                        mode_b=mode_b,
                        claim_a=claim_a.text,
                        claim_b=claim_b.text,
                        severity="hard",
                        description=f"'{pos}' vs '{neg}' detected",
                    )
            if neg in norm_a and pos in norm_b:
                if self._share_subject(norm_a, norm_b):
                    return Contradiction(
                        mode_a=mode_a,
                        mode_b=mode_b,
                        claim_a=claim_a.text,
                        claim_b=claim_b.text,
                        severity="hard",
                        description=f"'{neg}' vs '{pos}' detected",
                    )

        # Check for soft contradictions via high similarity + negation
        similarity = SequenceMatcher(None, norm_a, norm_b).ratio()
        if similarity > 0.5:
            has_negation_a = any(neg in norm_a for neg in NEGATION_WORDS)
            has_negation_b = any(neg in norm_b for neg in NEGATION_WORDS)
            if has_negation_a != has_negation_b:
                return Contradiction(
                    mode_a=mode_a,
                    mode_b=mode_b,
                    claim_a=claim_a.text,
                    claim_b=claim_b.text,
                    severity="soft",
                    description="Similar claims with negation difference",
                )

        return None

    def _share_subject(self, text_a: str, text_b: str) -> bool:
        """Check if two texts share significant content words (subject overlap)."""
        stopwords = frozenset({
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "can", "shall",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "this", "that", "it", "its", "we", "you", "they", "i",
        })
        words_a = set(text_a.split()) - stopwords
        words_b = set(text_b.split()) - stopwords
        if not words_a or not words_b:
            return False
        overlap = words_a & words_b
        # At least 30% overlap of the shorter set
        min_size = min(len(words_a), len(words_b))
        return len(overlap) >= max(2, int(min_size * 0.3))

    # ------------------------------------------------------------------
    # Internal: value-add analysis
    # ------------------------------------------------------------------

    def _compute_value_add(
        self,
        mode_claims: dict[str, list[Claim]],
        clusters: list[dict],
        mode_unique: dict[str, list[Claim]],
    ) -> list[dict]:
        """Compute how each mode adds value over the previous one."""
        value_add: list[dict] = []

        for idx, mode in enumerate(MODE_HIERARCHY):
            claims = mode_claims.get(mode, [])
            unique = mode_unique.get(mode, [])
            risks = [c for c in claims if c.is_risk]

            # Previous modes' claims
            prev_modes = MODE_HIERARCHY[:idx]
            prev_claim_count = sum(len(mode_claims.get(m, [])) for m in prev_modes)

            # New risks found by this mode
            new_risks = [c for c in unique if c.is_risk]

            # Recommendations unique to this mode
            new_recs = [c for c in unique if c.category == "recommendation"]

            entry = {
                "mode": mode,
                "total_claims": len(claims),
                "unique_claims": len(unique),
                "total_risks": len(risks),
                "new_risks": len(new_risks),
                "new_recommendations": len(new_recs),
                "cumulative_claims": prev_claim_count + len(claims),
                "incremental_value": (
                    len(unique) / len(claims) if claims else 0.0
                ),
            }
            value_add.append(entry)

        return value_add

    # ------------------------------------------------------------------
    # Report section renderers
    # ------------------------------------------------------------------

    def _report_header(self, result: AgreementResult, title: str) -> str:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        modes_present = [m for m in MODE_HIERARCHY if m in result.mode_analyses]
        total = result.total_unique_claims
        return (
            f"# {title}\n"
            f"\n"
            f"Generated: {now}\n"
            f"Modes analyzed: {', '.join(modes_present)}\n"
            f"Total unique claims: {total}\n"
            f"Agreement rate: {result.agreement_rate:.1%}\n"
            f"Contradictions found: {len(result.contradictions)}"
        )

    def _report_overview(self, result: AgreementResult) -> str:
        lines = [
            "## Overview",
            "",
            "| Mode | Total Claims | Unique | Risks | New Risks | Discovery Rate |",
            "|------|-------------|--------|-------|-----------|----------------|",
        ]
        for entry in result.mode_value_add:
            lines.append(
                f"| {entry['mode']:10s} | {entry['total_claims']:13d} | "
                f"{entry['unique_claims']:6d} | {entry['total_risks']:5d} | "
                f"{entry['new_risks']:9d} | {entry['incremental_value']:14.1%} |"
            )

        lines.append("")
        lines.append(f"**Shared conclusions** (found in 2+ modes): {result.shared_claims}")
        lines.append(f"**Contradiction rate**: {result.contradiction_rate:.2%}")
        return "\n".join(lines)

    def _report_mode_details(self, result: AgreementResult) -> str:
        lines = ["## Per-Mode Claim Details", ""]

        for mode in MODE_HIERARCHY:
            ma = result.mode_analyses.get(mode)
            if not ma or ma.claim_count == 0:
                lines.append(f"### {mode}")
                lines.append("")
                lines.append("No output provided for this mode.")
                lines.append("")
                continue

            lines.append(f"### {mode} ({ma.claim_count} claims, {ma.unique_count} unique)")
            lines.append("")

            if ma.unique_claims:
                lines.append("**Mode-specific discoveries:**")
                for claim in ma.unique_claims[:10]:
                    prefix = "[RISK] " if claim.is_risk else ""
                    lines.append(f"- {prefix}{claim.text[:120]}")
                if len(ma.unique_claims) > 10:
                    lines.append(f"  ... and {len(ma.unique_claims) - 10} more")
                lines.append("")

            if ma.risk_claims:
                lines.append("**Risks identified:**")
                for claim in ma.risk_claims[:5]:
                    lines.append(f"- {claim.text[:120]}")
                if len(ma.risk_claims) > 5:
                    lines.append(f"  ... and {len(ma.risk_claims) - 5} more")
                lines.append("")

        return "\n".join(lines)

    def _report_agreement_clusters(self, result: AgreementResult) -> str:
        lines = ["## Agreement Clusters", ""]
        shared = [c for c in result.agreement_clusters if len(c["modes"]) >= 2]

        if not shared:
            lines.append("No shared conclusions found across modes.")
            return "\n".join(lines)

        lines.append(
            f"Found {len(shared)} agreement clusters (claims shared by 2+ modes):"
        )
        lines.append("")

        for i, cluster in enumerate(shared[:20], 1):
            modes_str = ", ".join(cluster["modes"])
            rep = cluster["representative"]
            lines.append(f"**Cluster {i}** [{modes_str}] ({len(cluster['claims'])} claims)")
            lines.append(f"  {rep.text[:150]}")
            lines.append("")

        if len(shared) > 20:
            lines.append(f"... and {len(shared) - 20} more clusters")

        return "\n".join(lines)

    def _report_discovery_analysis(self, result: AgreementResult) -> str:
        lines = [
            "## Discovery Analysis",
            "",
            "How each mode adds new insights not found in previous modes:",
            "",
            "| Mode | New Claims | Cumulative Total | New/Total |",
            "|------|-----------|------------------|-----------|",
        ]

        for mode, rate in result.cumulative_discovery_rate:
            ma = result.mode_analyses.get(mode)
            if ma:
                new = ma.unique_count
                cum = sum(
                    result.mode_analyses[m].claim_count
                    for m in MODE_HIERARCHY[:MODE_HIERARCHY.index(mode) + 1]
                    if m in result.mode_analyses
                )
                lines.append(
                    f"| {mode:10s} | {new:10d} | {cum:16d} | {rate:8.1%} |"
                )

        return "\n".join(lines)

    def _report_risk_analysis(self, result: AgreementResult) -> str:
        lines = [
            "## Risk Identification by Mode",
            "",
            "Verifies that deeper modes find more risks/edge cases:",
            "",
            "| Mode | Risks | Cumulative | New Risks |",
            "|------|-------|------------|-----------|",
        ]

        for mode, cum_risks in result.cumulative_risks:
            ma = result.mode_analyses.get(mode)
            if ma:
                new_risks = len([c for c in ma.unique_claims if c.is_risk])
                lines.append(
                    f"| {mode:10s} | {ma.risk_count:5d} | {cum_risks:10d} | {new_risks:9d} |"
                )

        lines.append("")

        # Check monotonic increase
        risk_counts = [result.risks_per_mode.get(m, 0) for m in MODE_HIERARCHY]
        cumulative_monotonic = all(
            result.cumulative_risks[i][1] <= result.cumulative_risks[i + 1][1]
            for i in range(len(result.cumulative_risks) - 1)
        ) if len(result.cumulative_risks) >= 2 else True

        if cumulative_monotonic:
            lines.append(
                "**Verdict:** Risk identification is monotonically increasing across modes."
            )
        else:
            lines.append(
                "**Verdict:** Risk identification does NOT increase monotonically. "
                "Some deeper modes may be missing risks found by simpler modes."
            )

        return "\n".join(lines)

    def _report_contradictions(self, result: AgreementResult) -> str:
        lines = [
            "## Contradictions",
            "",
        ]

        if not result.contradictions:
            lines.append("No contradictions detected between modes.")
            return "\n".join(lines)

        lines.append(f"Found {len(result.contradictions)} contradictions:")
        lines.append("")

        for i, c in enumerate(result.contradictions[:15], 1):
            severity_tag = c.severity.upper()
            lines.append(f"### Contradiction {i} [{severity_tag}] — {c.mode_a} vs {c.mode_b}")
            lines.append(f"")
            lines.append(f"**{c.mode_a}:** {c.claim_a[:150]}")
            lines.append(f"**{c.mode_b}:** {c.claim_b[:150]}")
            lines.append(f"**Type:** {c.description}")
            lines.append("")

        if len(result.contradictions) > 15:
            lines.append(f"... and {len(result.contradictions) - 15} more")

        return "\n".join(lines)

    def _report_value_add(self, result: AgreementResult) -> str:
        lines = [
            "## Value-Add Analysis: How Each Mode Adds Value",
            "",
        ]

        for idx, entry in enumerate(result.mode_value_add):
            mode = entry["mode"]
            if idx == 0:
                lines.append(f"### {mode} (Baseline)")
                lines.append(
                    f"- Establishes {entry['total_claims']} initial claims "
                    f"({entry['total_risks']} risks)"
                )
            else:
                prev = result.mode_value_add[idx - 1]
                lines.append(f"### {mode} (over {prev['mode']})")
                lines.append(
                    f"- Adds {entry['unique_claims']} new claims "
                    f"({entry['new_risks']} new risks, {entry['new_recommendations']} new recommendations)"
                )
                lines.append(
                    f"- Incremental value: {entry['incremental_value']:.1%} of output is new"
                )

                # Check if deeper mode found more risks
                if entry['total_risks'] > prev['total_risks']:
                    lines.append(
                        f"- Found {entry['total_risks'] - prev['total_risks']} additional risks"
                    )
                elif entry['total_risks'] == prev['total_risks'] and entry['total_risks'] > 0:
                    lines.append("- Risk count unchanged from previous mode")
                else:
                    lines.append("- Fewer risks identified than previous mode")
            lines.append("")

        return "\n".join(lines)

    def _report_verdict(self, result: AgreementResult) -> str:
        lines = ["## Verdict", ""]

        # Determine if deeper modes add value
        modes_present = [m for m in MODE_HIERARCHY if m in result.mode_analyses]
        if len(modes_present) < 2:
            lines.append("Insufficient modes present for cross-mode analysis.")
            return "\n".join(lines)

        # Check if deeper modes consistently find more risks
        risk_counts = [
            result.mode_analyses[m].risk_count
            for m in modes_present
        ]
        risks_increase = all(
            risk_counts[i] <= risk_counts[i + 1]
            for i in range(len(risk_counts) - 1)
        )

        # Check if each mode adds unique value
        has_unique_in_deep = any(
            result.mode_analyses[m].unique_count > 0
            for m in modes_present[1:]
        )

        # Check agreement level
        if result.agreement_rate > 0.5:
            lines.append(
                f"**Strong agreement** ({result.agreement_rate:.1%}): "
                "Modes converge on key conclusions, suggesting robust analysis."
            )
        elif result.agreement_rate > 0.2:
            lines.append(
                f"**Moderate agreement** ({result.agreement_rate:.1%}): "
                "Modes share some conclusions but each brings distinct perspective."
            )
        else:
            lines.append(
                f"**Low agreement** ({result.agreement_rate:.1%}): "
                "Modes produce largely independent analyses. This may indicate "
                "high diversity of perspective or lack of convergence."
            )

        lines.append("")

        if risks_increase:
            lines.append(
                "**Risk identification improves monotonically** — deeper modes "
                "consistently find more risks, validating mode escalation."
            )
        else:
            lines.append(
                "**Risk identification does NOT improve monotonically** — some "
                "deeper modes miss risks found by simpler modes."
            )

        lines.append("")

        if has_unique_in_deep:
            lines.append(
                "**Each mode contributes unique insights** — deeper modes are "
                "not merely repeating simpler mode analysis."
            )
        else:
            lines.append(
                "**Deeper modes add little unique insight** — most conclusions "
                "already present in simpler modes."
            )

        lines.append("")

        if result.contradiction_rate > 0.1:
            lines.append(
                f"**High contradiction rate** ({result.contradiction_rate:.1%}) — "
                "modes frequently disagree. Review contradictions for potential issues."
            )
        elif result.contradictions:
            lines.append(
                f"**Minor contradictions** ({result.contradiction_rate:.1%}) — "
                f"{len(result.contradictions)} disagreement(s) found. "
                "Most are soft contradictions (directional differences)."
            )
        else:
            lines.append(
                "**No contradictions** — all modes are internally consistent."
            )

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def score_cross_mode_agreement(
    mode_outputs: dict[str, str],
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> AgreementResult:
    """Run cross-mode agreement analysis and return result.

    Args:
        mode_outputs: Mapping of mode name (RAPID/DEEP/ENSEMBLE/MEGAMIND) to output text.
        similarity_threshold: Minimum similarity ratio for claim matching (0.0-1.0).

    Returns:
        AgreementResult with all metrics.
    """
    scorer = CrossModeAgreementScorer(similarity_threshold=similarity_threshold)
    return scorer.analyze(mode_outputs)


def generate_agreement_report(
    mode_outputs: dict[str, str],
    title: str = "Cross-Mode Agreement Report",
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> str:
    """Run analysis and generate a markdown report.

    Args:
        mode_outputs: Mapping of mode name to output text.
        title: Report title.
        similarity_threshold: Minimum similarity ratio for claim matching.

    Returns:
        Markdown-formatted report string.
    """
    scorer = CrossModeAgreementScorer(similarity_threshold=similarity_threshold)
    result = scorer.analyze(mode_outputs)
    return scorer.generate_report(result, title=title)
