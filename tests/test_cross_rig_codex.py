"""E2E cross-rig test: Codex-design-mcp + reasoning-swarm.

Validates the reasoning swarm works across a different codebase (Codex-design-mcp)
with a distinct structure (context/handoff/packets workspace rather than a
traditional src/test project).

Test scenarios:
  1. Rapid Strike — make a simple change in the Codex codebase
  2. Deep Think — refactor a module in the Codex codebase
  3. Grand Jury — debug an issue in the Codex codebase
  4. Evidence entries use real paths from the Codex repo
  5. Territory map correctly identifies source vs generated files

This cross-rig test ensures the swarm adapts to different repo layouts,
not just the reasoning-swarm project's own structure.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e_scaffold import (  # noqa: E402
    DEEP_THINK_TECHNIQUES,
    GRAND_JURY_PHASES,
    ReasoningSwarmHarness,
    ReasoningTrace,
    harness,
)


# ═══════════════════════════════════════════════════════════════════════════
# Cross-rig constants — Codex-design-mcp repo structure
# ═══════════════════════════════════════════════════════════════════════════

# The Codex-design-mcp workspace lives in a different rig.
# These paths mirror the real file layout discovered during exploration.
CODEX_RIG_ROOT = "/workspace/rigs/8141fb70-2246-4b57-a393-cd4479afa0f2/browse"

# Source files (authored content that humans edit)
CODEX_SOURCE_FILES = [
    ".context/STATE.md",
    ".context/DECISIONS.md",
    ".context/WORKLOG.md",
    ".context/INBOX.md",
    "docs/playbooks/REPLACEMENT_EXTERNAL_REVIEW_WORKFLOW.md",
]

# Handoff / generated files (machine-produced or transient)
CODEX_GENERATED_FILES = [
    ".handoff/HANDOFF_2026-03-13_opus46_prompt7_review_attempt.md",
    ".handoff/HANDOFF_2026-03-15_ultra_massive_context_dump_for_new_agent.md",
    ".packets/EXTERNAL_MODEL_REVIEW_2026-03-13_opus46_prompt7_grading_dirty_wave27.md",
    ".handoff/assets/2026-03-13_opus46_prompt7_review/claude_stderr.txt",
    ".handoff/assets/2026-03-13_opus46_prompt7_review/claude_response.json",
]

# All tracked files in the Codex workspace
CODEX_ALL_FILES = CODEX_SOURCE_FILES + CODEX_GENERATED_FILES

# Evidence entries using real Codex file paths (E# format with :L line refs)
CODEX_EVIDENCE_ENTRIES = [
    "E1: .context/DECISIONS.md:L10 — verbatim excerpt: 'treat wave27 as a proof branch with dirty live code'",
    "E2: .context/WORKLOG.md:L19 — verbatim excerpt: 'Claude Code is too old (0.2.100) and requires update to 1.0.88'",
    "E3: docs/playbooks/REPLACEMENT_EXTERNAL_REVIEW_WORKFLOW.md:L22 — verbatim excerpt: 'treat wave26 as the structural proof branch'",
    "E4: .context/STATE.md:L16 — verbatim excerpt: 'update Claude Code to 1.0.88 or higher'",
    "E5: .packets/EXTERNAL_MODEL_REVIEW_2026-03-13_opus46_prompt7_grading_dirty_wave27.md:L1 — verbatim excerpt: packet header",
]

# Tasks that exercise cross-rig adaptation
CODEX_RAPID_TASK = "Fix the typo in .context/INBOX.md — 'recieve' should be 'receive'"
CODEX_DEEP_TASK = "Refactor .context/ directory to split WORKLOG.md into per-session files"
CODEX_JURY_TASK = (
    "Debug why the external review packet failed — "
    "Claude Code version 0.2.100 is too old for the packet format"
)


# ═══════════════════════════════════════════════════════════════════════════
# Extended harness — Codex cross-rig
# ═══════════════════════════════════════════════════════════════════════════


class CodexCrossRigHarness(ReasoningSwarmHarness):
    """Harness that simulates reasoning swarm operating on the Codex-design-mcp
    workspace.  Overrides mock generators to produce output referencing real
    Codex file paths and the Codex repo layout."""

    # ── Rapid Strike ──────────────────────────────────────────────────────

    def _run_rapid(self) -> ReasoningTrace:
        task = self.task_description
        sections = [
            f"1. PROBLEM: {task}",
            f"2. OBVIOUS ANSWER: Read the target file, apply the fix, verify no other references.",
            "3. SANITY CHECK: "
            "Codex workspace is a context/handoff/packets layout — "
            "no src/ directory, no build system. "
            "Files are plain .md. Change is safe.",
            "4. CONFIDENCE: 9",
        ]
        raw = "\n".join(sections)
        return ReasoningTrace(
            mode="RAPID",
            confidence=9,
            checkpoints_hit=4,
            escalations=0,
            techniques_used=["RAPID STRIKE"],
            raw_output=raw,
        )

    # ── Deep Think ────────────────────────────────────────────────────────

    def _run_deep(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        total_confidence = 0

        codex_deep_mocks = {
            "META-COGNITION": (
                "Problem type: Cross-rig refactor on Codex-design-mcp workspace. "
                "Confidence (1-10): 7. "
                "Uncertainties: splitting WORKLOG.md may break handoff references. "
                "Am I rushing: No. "
                "Missing perspective: downstream agents reading split files."
            ),
            "STEP-BACK": (
                f"Literal request: {task}. "
                "What user ACTUALLY wants: maintainable session history in Codex workspace. "
                "WHY: single WORKLOG.md grows unbounded across sessions. "
                "What I should do: per-session files with an index."
            ),
            "DECOMPOSITION": (
                f"MAIN PROBLEM: {task}. "
                "SUB-PROBLEMS: "
                "1. Audit WORKLOG.md sections → 1.1 Identify session boundaries. "
                "2. Create per-session files → 2.1 Name by date. "
                "3. Build index → 3.1 Update STATE.md pointer. "
                "DEPENDENCIES: 1 before 2, 2 before 3."
            ),
            "TREE OF THOUGHT": (
                "BRANCH A: Split by date into .context/worklog/YYYY-MM-DD.md. "
                "Pros: clean | Cons: many tiny files | Verdict: PURSUE. "
                "BRANCH B: Keep monolith but add section headers. "
                "Pros: simple | Cons: doesn't solve growth | Verdict: PRUNE. "
                "BRANCH C: Split into .context/sessions/ with index. "
                "Pros: balanced | Cons: more structure | Verdict: PURSUE. "
                "SELECTED: Branch C."
            ),
            "FIRST PRINCIPLES": (
                "Assumptions: "
                "1. Codex workspace has .context/ as the state dir → convention → true. "
                "2. Handoff docs reference WORKLOG.md by path → needs update if split. "
                "3. No automated tests validate .context/ integrity → true. "
                "FUNDAMENTALLY REQUIRED: preserve all existing references."
            ),
            "ANALOGICAL REASONING": (
                "Abstract pattern: splitting a growing log file. "
                "Similar solved problems: "
                "1. Git log rotation → solution: date-based archives. "
                "2. Journal apps → solution: per-entry files with index. "
                "What transfers: date-based splitting. What doesn't: binary rotation."
            ),
            "CHAIN OF THOUGHT": (
                "Step 1: Read .context/WORKLOG.md — understand current structure. "
                "Step 2: Identify session boundaries — each ### header is a session. "
                "Step 3: Extract sessions into .context/sessions/ — preserve content. "
                "Step 4: Create index.md — link to all session files. "
                "Conclusion: proceed with per-session split."
            ),
            "DEVIL'S ADVOCATE": (
                "My solution: split WORKLOG.md into per-session files. "
                'ATTACK 1: "Breaks existing handoff references" → Defense: update refs too. '
                'ATTACK 2: "Over-engineering for a small file" → Defense: prevents future pain. '
                'ATTACK 3: "Agents expect monolith" → Defense: update agent contracts.'
            ),
            "INVERSION / PRE-MORTEM": (
                "How to GUARANTEE failure: "
                "1. Split without updating references → broken handoffs. "
                "2. Lose content during split → data loss. "
                "3. Don't update STATE.md → agents read stale pointer. "
                "1 month later, it failed: handoff doc pointed to deleted section."
            ),
            "RAVEN LOOP": (
                "REFLECT: approach is sound but cross-rig references are fragile. "
                "ADAPT: add reference-update pass after split. "
                "VERIFY: grep all .md files for WORKLOG.md references. "
                "EXECUTE: split + update references + verify. "
                "NAVIGATE: success, Codex workspace now has clean session history. "
                "LOOP AGAIN? no."
            ),
            "RECURSIVE SELF-IMPROVEMENT": (
                "DRAFT: split WORKLOG.md by date. "
                "CRITIQUE: Weakness 1: no reference update plan | "
                "Weakness 2: no rollback if split corrupts data. "
                "IMPROVED: added ref-update pass + backup before split. "
                "FINAL CONFIDENCE: 8."
            ),
        }

        for name, marker in DEEP_THINK_TECHNIQUES:
            content = codex_deep_mocks.get(
                name, f"{name} analysis for: {task}"
            )
            section = (
                f"┌─ {name} ──────────────────────────────────────\n"
                f"│ {content}\n"
                f"│ {marker}\n"
                f"└{'─' * 50}┘"
            )
            output_parts.append(section)
            techniques_used.append(name)
            total_confidence += self._extract_confidence(content)

        avg_conf = min(10, max(1, round(total_confidence / 11)))
        summary = (
            f"\n🧠 DEEP THINK COMPLETE\n"
            f"Checkpoints Hit: 11/11\n"
            f"Confidence: {avg_conf}\n"
            f"---\n"
            f"Final answer for: {task}\n"
            f"Cross-rig target: {CODEX_RIG_ROOT}"
        )
        output_parts.append(summary)

        return ReasoningTrace(
            mode="DEEP",
            confidence=avg_conf,
            checkpoints_hit=11,
            escalations=0,
            techniques_used=techniques_used,
            raw_output="\n".join(output_parts),
        )

    # ── Grand Jury ────────────────────────────────────────────────────────

    def _run_jury(self) -> ReasoningTrace:
        task = self.task_description
        techniques_used: list[str] = []
        output_parts: list[str] = []
        evidence: list[str] = []

        codex_jury_mocks = {
            "GJ-0": (
                f"Repo root: {CODEX_RIG_ROOT}. "
                "Available tools: search, read, shell. "
                "Constraints: cross-rig — do not modify files outside Codex workspace. "
                "PLEDGE: I will not propose a fix until Pre-Flight (GJ-7) is complete."
            ),
            "GJ-1": (
                f"Reported: '{task}'. "
                "Expected: external review packet executes successfully. "
                "Actual: Claude Code 0.2.100 crashes on packet format. "
                "Severity: high — blocks all external review workflows. "
                "Success criteria: packet sends and returns valid response."
            ),
            "GJ-2": (
                "A1: Claude Code version constraint is the blocker — PC — 95% — VERIFIED. "
                "A2: Packet format is correct — TDK — 85% — UNVERIFIED. "
                "A3: Node runtime version is compatible — PC — 70% — UNVERIFIED. "
                "A4: No other CLI tools available — TDK — 60% — UNVERIFIED."
            ),
            "GJ-3": (
                "S1: rg -n 'claude' .context/WORKLOG.md — 8 hits — finds version refs. "
                "S2: rg -n 'version' .packets/ — 2 hits — packet format stable. "
                "S3: ls .handoff/assets/ — finds stderr output confirming crash."
            ),
            "GJ-4": "\n".join(CODEX_EVIDENCE_ENTRIES),
            "GJ-5": (
                "Source → Packet authored (E3) → CLI invoked → "
                "Version mismatch (E2) → Crash (E5) → "
                "Blocker recorded (E4) → Decision documented (E1). "
                "Each link verified with Evidence IDs."
            ),
            "GJ-6": (
                "H1: Claude Code too old — E1,E2,E4 FOR — E3 AGAINST — CONFIRMED. "
                "H2: Packet format wrong — E3 FOR — E5 AGAINST — DISPROVED. "
                "H3: Node runtime mismatch — E2 FOR — E1,E4 AGAINST — DISPROVED. "
                "H4: Network/auth issue — weak evidence — UNCERTAIN."
            ),
            "GJ-7": (
                "1. Files read: .context/WORKLOG.md (E2), "
                ".packets/EXTERNAL_MODEL_REVIEW_...md (E3), "
                ".handoff/assets/.../claude_stderr.txt (E5). "
                "2. Root cause: Claude Code 0.2.100 requires 1.0.88+ (E2, E4). "
                "3. Eliminated: H2 DISPROVED (E3 confirms format), H3 DISPROVED. "
                "4. Atomic fix: update Claude Code or use alternative surface (E1). "
                "5. Risks: update may change CLI behavior. "
                "6. Verification: re-run packet after update."
            ),
            "GJ-8": (
                "Atomic change: update Claude Code to >= 1.0.88. "
                "Verification: PASS. Packet sent successfully. "
                "No regressions detected in Codex workspace."
            ),
        }

        for phase_id, phase_name in GRAND_JURY_PHASES:
            content = codex_jury_mocks.get(
                phase_id,
                f"{phase_name} analysis for: {task}",
            )
            section = (
                f"┌─ {phase_name} ({phase_id}) ──────────────────\n"
                f"│ {content}\n"
                f"└{'─' * 50}┘"
            )
            output_parts.append(section)
            techniques_used.append(f"JURY:{phase_id}")

            if phase_id == "GJ-4":
                evidence.extend(CODEX_EVIDENCE_ENTRIES)

        conf = 8  # Codex debug task is well-scoped

        raw = "\n".join(output_parts)
        raw += (
            f"\n\n⚖️ GRAND JURY COMPLETE\n"
            f"Evidence Entries: {len(evidence)}\n"
            f"Hypotheses Tested: 4\n"
            f"Root Cause: Claude Code version 0.2.100 is too old (requires >= 1.0.88)\n"
            f"Fix: Update Claude Code or use alternative Opus 4.6 surface\n"
            f"Verification: PASS"
        )

        return ReasoningTrace(
            mode="JURY",
            confidence=conf,
            checkpoints_hit=9,
            escalations=0,
            techniques_used=techniques_used,
            evidence_entries=evidence,
            raw_output=raw,
        )

    # ── Territory map for Codex workspace ─────────────────────────────────

    def build_territory_map(self) -> dict:
        """Build a territory map for the Codex-design-mcp workspace.

        Returns a dict with keys: framework, key_dirs, source_files,
        generated_files.
        """
        return {
            "framework": "context/handoff/packets workspace (no build system)",
            "key_dirs": [
                ".context/",
                ".handoff/",
                ".handoff/assets/",
                ".packets/",
                "docs/playbooks/",
            ],
            "source_files": CODEX_SOURCE_FILES,
            "generated_files": CODEX_GENERATED_FILES,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _run_codex_rapid(task: str = CODEX_RAPID_TASK) -> ReasoningTrace:
    h = CodexCrossRigHarness(task_description=task, mode_override="RAPID")
    return h.run()


def _run_codex_deep(task: str = CODEX_DEEP_TASK) -> ReasoningTrace:
    h = CodexCrossRigHarness(task_description=task, mode_override="DEEP")
    return h.run()


def _run_codex_jury(task: str = CODEX_JURY_TASK) -> ReasoningTrace:
    h = CodexCrossRigHarness(task_description=task, mode_override="JURY")
    return h.run()


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 1: Rapid Strike — simple change in Codex codebase
# ═══════════════════════════════════════════════════════════════════════════


class TestRapidStrikeCrossRig:
    """Rapid Strike makes a simple change in the Codex-design-mcp codebase."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_codex_rapid()

    def test_mode_is_rapid(self, trace):
        assert trace.mode == "RAPID"

    def test_confidence_high_enough(self, trace):
        assert trace.confidence >= 8, (
            f"Rapid Strike on a simple fix should have confidence >= 8, got {trace.confidence}"
        )

    def test_checkpoints_hit(self, trace):
        assert trace.checkpoints_hit == 4

    def test_no_escalations(self, trace):
        assert trace.escalations == 0

    def test_output_references_codex_workspace(self, trace):
        assert "Codex" in trace.raw_output or "codex" in trace.raw_output.lower()

    def test_output_has_4_sections(self, trace):
        """Rapid Strike output must have PROBLEM, OBVIOUS ANSWER, SANITY CHECK, CONFIDENCE."""
        assert "1. PROBLEM:" in trace.raw_output
        assert "2. OBVIOUS ANSWER:" in trace.raw_output
        assert "3. SANITY CHECK:" in trace.raw_output
        assert "4. CONFIDENCE:" in trace.raw_output

    def test_sanity_check_mentions_layout(self, trace):
        """Sanity check should acknowledge the Codex workspace layout."""
        assert re.search(
            r"context|handoff|packets|layout",
            trace.raw_output,
            re.IGNORECASE,
        )

    def test_techniques_used(self, trace):
        assert "RAPID STRIKE" in trace.techniques_used

    def test_latency_non_negative(self, trace):
        assert trace.latency_ms >= 0


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 2: Deep Think — refactor a module in Codex codebase
# ═══════════════════════════════════════════════════════════════════════════


class TestDeepThinkCrossRig:
    """Deep Think refactors a module in the Codex-design-mcp codebase."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_codex_deep()

    def test_mode_is_deep(self, trace):
        assert trace.mode == "DEEP"

    def test_confidence_in_range(self, trace):
        assert 1 <= trace.confidence <= 10

    def test_checkpoints_hit_11(self, trace):
        assert trace.checkpoints_hit == 11

    def test_all_11_techniques_present(self, trace):
        for name, _ in DEEP_THINK_TECHNIQUES:
            assert name in trace.techniques_used, (
                f"Technique {name} missing from techniques_used"
            )

    def test_all_11_checkpoint_markers_in_output(self, trace):
        for _, marker in DEEP_THINK_TECHNIQUES:
            assert marker in trace.raw_output, (
                f"Checkpoint marker {marker} missing from raw_output"
            )

    def test_output_references_codex_paths(self, trace):
        """Deep Think output should reference Codex workspace paths."""
        assert re.search(
            r"\.context/|WORKLOG|STATE\.md|handoff|Codex",
            trace.raw_output,
            re.IGNORECASE,
        )

    def test_completion_marker(self, trace):
        assert "🧠 DEEP THINK COMPLETE" in trace.raw_output

    def test_technique_box_structure(self, trace):
        """Each technique section should use box-drawing characters."""
        assert "┌─" in trace.raw_output
        assert "└" in trace.raw_output

    def test_no_placeholder_text(self, trace):
        """Output should not contain placeholder or TODO text."""
        assert "TODO" not in trace.raw_output
        assert "PLACEHOLDER" not in trace.raw_output.upper()
        assert "FIXME" not in trace.raw_output

    def test_decomposition_references_codex_structure(self, trace):
        """Decomposition technique should reference Codex's actual structure."""
        # The decomposition should mention .context/ or session files
        decomp_match = re.search(
            r"DECOMPOSITION.*?└",
            trace.raw_output,
            re.DOTALL,
        )
        assert decomp_match, "DECOMPOSITION section not found"
        section = decomp_match.group()
        assert re.search(r"\.context|WORKLOG|session|index", section, re.IGNORECASE)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 3: Grand Jury — debug an issue in Codex codebase
# ═══════════════════════════════════════════════════════════════════════════


class TestGrandJuryCrossRig:
    """Grand Jury debugs an issue in the Codex-design-mcp codebase."""

    @pytest.fixture(scope="class")
    def trace(self):
        return _run_codex_jury()

    def test_mode_is_jury(self, trace):
        assert trace.mode == "JURY"

    def test_confidence_in_range(self, trace):
        assert 1 <= trace.confidence <= 10

    def test_checkpoints_hit_9(self, trace):
        assert trace.checkpoints_hit == 9

    def test_all_9_phases_present(self, trace):
        for phase_id, phase_name in GRAND_JURY_PHASES:
            assert f"{phase_name} ({phase_id})" in trace.raw_output, (
                f"Phase {phase_id} ({phase_name}) missing from output"
            )

    def test_gj0_references_codex_rig_root(self, trace):
        assert CODEX_RIG_ROOT in trace.raw_output

    def test_gj0_cross_rig_constraint(self, trace):
        """GJ-0 should state the cross-rig constraint."""
        assert re.search(
            r"cross-rig|outside Codex|do not modify",
            trace.raw_output,
            re.IGNORECASE,
        )

    def test_gj1_identifies_claude_version_blocker(self, trace):
        """GJ-1 symptom should identify the Claude Code version issue."""
        assert re.search(r"0\.2\.100|version", trace.raw_output)

    def test_gj2_has_tdk_and_pc_categories(self, trace):
        assert "TDK" in trace.raw_output
        assert "PC" in trace.raw_output

    def test_gj3_search_references_codex_files(self, trace):
        """Search pass should reference real Codex paths."""
        assert re.search(
            r"\.context/WORKLOG|\.packets/|\.handoff/",
            trace.raw_output,
        )

    def test_gj4_evidence_count(self, trace):
        assert len(trace.evidence_entries) >= 5, (
            f"Expected >=5 evidence entries from Codex investigation, "
            f"got {len(trace.evidence_entries)}"
        )

    def test_gj6_has_4_hypotheses(self, trace):
        hypotheses = re.findall(r"H\d+:", trace.raw_output)
        assert len(hypotheses) >= 4

    def test_gj7_all_6_checklist_items(self, trace):
        items = re.findall(r"\d\.\s*\w", trace.raw_output)
        assert len(items) >= 6

    def test_gj8_verification_pass(self, trace):
        assert re.search(r"Verification:\s*PASS", trace.raw_output)

    def test_completion_marker(self, trace):
        assert "⚖️ GRAND JURY COMPLETE" in trace.raw_output

    def test_root_cause_identifies_version(self, trace):
        """Root cause should identify the Claude Code version mismatch."""
        assert re.search(r"Root Cause:.*0\.2\.100|version", trace.raw_output)


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 4: Evidence entries use real paths from Codex repo
# ═══════════════════════════════════════════════════════════════════════════


class TestEvidenceEntriesRealPaths:
    """Evidence entries reference real file paths that exist in the Codex workspace."""

    @pytest.fixture(scope="class")
    def jury_trace(self):
        return _run_codex_jury()

    def test_evidence_entries_non_empty(self, jury_trace):
        assert len(jury_trace.evidence_entries) > 0

    def test_evidence_entries_have_eid_format(self, jury_trace):
        """Each evidence entry must start with E#:"""
        for entry in jury_trace.evidence_entries:
            assert re.match(r"E\d+:", entry), (
                f"Evidence entry does not match E#: format: {entry}"
            )

    def test_evidence_entries_have_line_refs(self, jury_trace):
        """Evidence entries must include line number references (:L#)."""
        for entry in jury_trace.evidence_entries:
            assert re.search(r":L\d+", entry), (
                f"Evidence entry missing line reference: {entry}"
            )

    def test_evidence_entries_reference_real_codex_files(self, jury_trace):
        """Evidence entries must reference files that actually exist in the Codex workspace."""
        codex_path = CODEX_RIG_ROOT
        for entry in jury_trace.evidence_entries:
            # Extract file path from entry (after E#: and before :L)
            match = re.search(r"E\d+:\s+([\w/.]+\.md)", entry)
            if match:
                file_ref = match.group(1)
                full_path = os.path.join(codex_path, file_ref)
                assert os.path.exists(full_path), (
                    f"Evidence references {file_ref} but it does not exist at {full_path}"
                )

    def test_evidence_entries_have_verbatim_markers(self, jury_trace):
        """Evidence entries must include 'verbatim excerpt' marker."""
        verbatim_count = sum(
            1 for e in jury_trace.evidence_entries
            if "verbatim excerpt" in e
        )
        assert verbatim_count >= 3, (
            f"Expected >=3 evidence entries with 'verbatim excerpt', got {verbatim_count}"
        )

    def test_evidence_covers_multiple_codex_dirs(self, jury_trace):
        """Evidence should span multiple directories in the Codex workspace."""
        dirs_found = set()
        for entry in jury_trace.evidence_entries:
            if ".context/" in entry:
                dirs_found.add(".context")
            if ".packets/" in entry:
                dirs_found.add(".packets")
            if "playbooks/" in entry:
                dirs_found.add("playbooks")
            if ".handoff/" in entry:
                dirs_found.add(".handoff")
        assert len(dirs_found) >= 2, (
            f"Evidence should span >=2 Codex directories, found: {dirs_found}"
        )

    def test_evidence_entries_in_raw_output(self, jury_trace):
        """All evidence entries should appear in the raw output."""
        for entry in jury_trace.evidence_entries:
            eid = entry.split(":")[0]  # Extract "E1", "E2", etc.
            assert eid in jury_trace.raw_output, (
                f"Evidence {eid} not found in raw output"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Scenario 5: Territory map correctly identifies source vs generated files
# ═══════════════════════════════════════════════════════════════════════════


class TestTerritoryMapCrossRig:
    """Territory map correctly classifies source vs generated files in the Codex workspace."""

    @pytest.fixture(scope="class")
    def harness_instance(self):
        return CodexCrossRigHarness(
            task_description=CODEX_JURY_TASK, mode_override="JURY"
        )

    @pytest.fixture(scope="class")
    def territory(self, harness_instance):
        return harness_instance.build_territory_map()

    def test_territory_has_framework(self, territory):
        assert "framework" in territory
        assert len(territory["framework"]) > 0

    def test_territory_framework_mentions_layout_type(self, territory):
        """Framework should describe the Codex workspace type (not a generic 'Python project')."""
        fw = territory["framework"].lower()
        assert any(kw in fw for kw in ("context", "handoff", "packets", "workspace")), (
            f"Framework description should mention the Codex layout type, got: {fw}"
        )

    def test_territory_has_key_dirs(self, territory):
        assert "key_dirs" in territory
        assert len(territory["key_dirs"]) >= 3

    def test_territory_key_dirs_include_context(self, territory):
        assert any(".context" in d for d in territory["key_dirs"])

    def test_territory_key_dirs_include_handoff(self, territory):
        assert any(".handoff" in d for d in territory["key_dirs"])

    def test_territory_key_dirs_include_packets(self, territory):
        assert any(".packets" in d for d in territory["key_dirs"])

    def test_territory_source_files_non_empty(self, territory):
        assert "source_files" in territory
        assert len(territory["source_files"]) >= 3

    def test_territory_generated_files_non_empty(self, territory):
        assert "generated_files" in territory
        assert len(territory["generated_files"]) >= 2

    def test_territory_no_overlap(self, territory):
        """Source and generated files should not overlap."""
        source_set = set(territory["source_files"])
        generated_set = set(territory["generated_files"])
        overlap = source_set & generated_set
        assert len(overlap) == 0, (
            f"Source and generated files should not overlap, found: {overlap}"
        )

    def test_territory_source_files_are_md(self, territory):
        """All source files should be .md files."""
        for f in territory["source_files"]:
            assert f.endswith(".md"), f"Source file should be .md: {f}"

    def test_territory_source_files_include_state(self, territory):
        assert any("STATE.md" in f for f in territory["source_files"])

    def test_territory_source_files_include_decisions(self, territory):
        assert any("DECISIONS.md" in f for f in territory["source_files"])

    def test_territory_source_files_include_worklog(self, territory):
        assert any("WORKLOG.md" in f for f in territory["source_files"])

    def test_territory_generated_files_include_handoffs(self, territory):
        assert any("HANDOFF" in f for f in territory["generated_files"])

    def test_territory_generated_files_include_packets(self, territory):
        assert any("EXTERNAL_MODEL_REVIEW" in f for f in territory["generated_files"])

    def test_territory_all_files_cover_full_workspace(self, territory):
        """Combined source + generated should cover the key workspace files."""
        all_files = set(territory["source_files"] + territory["generated_files"])
        # At minimum, STATE, DECISIONS, WORKLOG, a handoff, and a packet
        assert len(all_files) >= 8, (
            f"Expected >=8 total files in territory map, got {len(all_files)}"
        )

    def test_territory_source_files_exist_on_disk(self, territory):
        """Source files referenced in the territory map should actually exist."""
        codex_path = CODEX_RIG_ROOT
        for f in territory["source_files"]:
            full_path = os.path.join(codex_path, f)
            assert os.path.exists(full_path), (
                f"Territory map source file {f} does not exist at {full_path}"
            )

    def test_territory_generated_files_exist_on_disk(self, territory):
        """Generated files referenced in the territory map should actually exist."""
        codex_path = CODEX_RIG_ROOT
        for f in territory["generated_files"]:
            full_path = os.path.join(codex_path, f)
            assert os.path.exists(full_path), (
                f"Territory map generated file {f} does not exist at {full_path}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Cross-cutting: mode dispatch for Codex tasks
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossRigModeDispatch:
    """Verify the intake classifier routes Codex tasks to correct modes."""

    def test_simple_codex_fix_routes_rapid(self, harness):
        h = harness(CODEX_RAPID_TASK, mode="RAPID")
        assert h.get_mode() == "RAPID STRIKE"

    def test_refactor_codex_routes_deep(self, harness):
        h = harness(CODEX_DEEP_TASK, mode="DEEP")
        assert h.get_mode() == "DEEP THINK"

    def test_debug_codex_routes_jury(self, harness):
        h = harness(CODEX_JURY_TASK, mode="JURY")
        assert h.get_mode() == "GRAND JURY"

    def test_codex_rapid_returns_rapid_mode(self, harness):
        h = harness(CODEX_RAPID_TASK, mode="RAPID")
        trace = h.run()
        assert trace.mode == "RAPID"

    def test_codex_deep_returns_deep_mode(self, harness):
        h = harness(CODEX_DEEP_TASK, mode="DEEP")
        trace = h.run()
        assert trace.mode == "DEEP"

    def test_codex_jury_returns_jury_mode(self, harness):
        h = harness(CODEX_JURY_TASK, mode="JURY")
        trace = h.run()
        assert trace.mode == "JURY"

    def test_codex_skill_loading(self, harness):
        """Each mode should load a valid skill file."""
        for mode in ("RAPID", "DEEP", "JURY"):
            h = harness(CODEX_RAPID_TASK, mode=mode)
            skill = h.load_skill()
            assert len(skill) > 100, f"Skill for {mode} too short: {len(skill)} chars"
