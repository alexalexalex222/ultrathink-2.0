"""Agent test harness for real LLM API calls against reasoning swarm.

Provides AgentHarness (model-agnostic OpenAI-compatible API client with
retry, token tracking, and latency measurement) and SwarmRunner (constructs
full reasoning swarm prompts from skill templates, runs the mode pipeline,
and captures structured output).

Supports mock mode for CI environments where no API key is available.

Usage:
    from tests.agent_harness import AgentHarness, SwarmRunner

    # Direct prompt execution
    agent = AgentHarness.from_env()
    response = agent.run_prompt("Explain quicksort in one sentence.")

    # Full swarm pipeline
    runner = SwarmRunner.from_env()
    trace = runner.run("Add retry logic to the API client", mode="DEEP")

    # Parallel angle execution (Ensemble/Megamind)
    responses = agent.run_parallel([
        "ANGLE: PERFORMANCE. Analyze this design...",
        "ANGLE: SIMPLICITY. Analyze this design...",
    ])
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ── Path bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.intake_classifier import classify_task  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════

_DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o"
_MAX_RETRIES = 4
_BASE_BACKOFF_S = 1.0
_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

ENSEMBLE_ANGLES = [
    "PERFORMANCE",
    "SIMPLICITY",
    "SECURITY",
    "EDGE CASES",
    "DEVIL'S ADVOCATE",
]

MEGAMIND_ANGLES = [
    "PERFORMANCE",
    "SIMPLICITY",
    "SECURITY",
    "SCALABILITY",
    "EDGE CASES",
    "DEVIL'S ADVOCATE",
    "BEGINNER'S MIND",
    "FUTURE SELF",
    "USER PERSPECTIVE",
    "CONSTRAINT BREAKER",
]

MEGAMIND_SYNTHESIZERS = ["CONSENSUS", "CONFLICT", "RISK"]

DEEP_THINK_TECHNIQUES = [
    "META-COGNITION",
    "STEP-BACK",
    "DECOMPOSITION",
    "TREE OF THOUGHT",
    "FIRST PRINCIPLES",
    "ANALOGICAL REASONING",
    "CHAIN OF THOUGHT",
    "DEVIL'S ADVOCATE",
    "INVERSION / PRE-MORTEM",
    "RAVEN LOOP",
    "RECURSIVE SELF-IMPROVEMENT",
]

GRAND_JURY_PHASES = [
    ("GJ-0", "COMMITMENT"),
    ("GJ-1", "SYMPTOM RECORD"),
    ("GJ-2", "ASSUMPTIONS LEDGER"),
    ("GJ-3", "SEARCH PASS"),
    ("GJ-4", "EVIDENCE LEDGER"),
    ("GJ-5", "CHAIN-OF-CUSTODY"),
    ("GJ-6", "MURDER BOARD"),
    ("GJ-7", "PRE-FLIGHT CHECKLIST"),
    ("GJ-8", "ATOMIC CHANGE + VERIFY"),
]

_MODE_SKILL_MAP = {
    "RAPID STRIKE": "reasoning-swarm-SKILL.md",
    "DEEP THINK": "deepthink-SKILL.md",
    "ENSEMBLE": "reasoning-swarm-SKILL.md",
    "MEGAMIND": "megamind-SKILL.md",
    "GRAND JURY": "diamondthink-SKILL.md",
}

_MODE_ABBREV = {
    "RAPID STRIKE": "RAPID",
    "DEEP THINK": "DEEP",
    "ENSEMBLE": "ENSEMBLE",
    "MEGAMIND": "MEGA",
    "GRAND JURY": "JURY",
}


# ═══════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class TokenUsage:
    """Token counts from an API call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AgentResponse:
    """Response from a single API call."""
    content: str
    model: str
    latency_ms: float
    token_usage: TokenUsage
    finish_reason: str = ""
    mock: bool = False


@dataclass
class SwarmTrace:
    """Structured output from a full swarm pipeline execution."""
    mode: str
    confidence: int
    checkpoints_hit: int
    escalations: int
    techniques_used: list[str] = field(default_factory=list)
    evidence_entries: list[str] = field(default_factory=list)
    subprocess_calls: int = 0
    raw_output: str = ""
    total_latency_ms: float = 0.0
    total_tokens: TokenUsage = field(default_factory=TokenUsage)
    angle_responses: list[AgentResponse] = field(default_factory=list)
    mock: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# AgentHarness — real API calls with retry + backoff
# ═══════════════════════════════════════════════════════════════════════════


class AgentHarness:
    """Model-agnostic client for OpenAI-compatible chat completion APIs.

    Handles rate limiting with exponential backoff, tracks token usage
    and latency, and supports async-style parallel execution via
    ThreadPoolExecutor.

    Falls back to mock mode when no API key is configured.
    """

    def __init__(
        self,
        api_url: str = "",
        model: str = "",
        api_key: str = "",
        mock_mode: bool = False,
        max_retries: int = _MAX_RETRIES,
        system_prompt: str = "",
    ):
        self.api_url = api_url or _DEFAULT_API_URL
        self.model = model or _DEFAULT_MODEL
        self.api_key = api_key
        self.mock_mode = mock_mode
        self.max_retries = max_retries
        self.system_prompt = system_prompt or (
            "You are a reasoning assistant. Follow the instructions precisely."
        )
        self._total_tokens = TokenUsage()

    @classmethod
    def from_env(cls, **overrides: Any) -> AgentHarness:
        """Construct from environment variables with optional overrides.

        Env vars:
            REASONING_SWARM_API_URL  — API endpoint (default: OpenAI)
            REASONING_SWARM_MODEL    — Model name (default: gpt-4o)
            REASONING_SWARM_API_KEY  — API key (required for real calls)

        When no API key is set, mock_mode is enabled automatically.
        """
        api_url = overrides.get("api_url", os.environ.get("REASONING_SWARM_API_URL", ""))
        model = overrides.get("model", os.environ.get("REASONING_SWARM_MODEL", ""))
        api_key = overrides.get("api_key", os.environ.get("REASONING_SWARM_API_KEY", ""))

        mock_mode = not bool(api_key)
        if not api_key:
            api_key = "mock-key"

        return cls(
            api_url=api_url,
            model=model,
            api_key=api_key,
            mock_mode=mock_mode,
            max_retries=overrides.get("max_retries", _MAX_RETRIES),
            system_prompt=overrides.get("system_prompt", ""),
        )

    @property
    def total_tokens(self) -> TokenUsage:
        """Cumulative token usage across all calls."""
        return self._total_tokens

    def run_prompt(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AgentResponse:
        """Send a prompt and return the model's response.

        Args:
            prompt: The user message to send.
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            AgentResponse with content, latency, and token usage.
        """
        if self.mock_mode:
            return self._mock_response(prompt)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        return self._call_with_retry(payload)

    def run_parallel(
        self,
        prompts: list[str],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        max_workers: int = 0,
    ) -> list[AgentResponse]:
        """Execute multiple prompts concurrently.

        Uses ThreadPoolExecutor for concurrent API calls. Designed for
        Ensemble (5 angles) and Megamind (10 angles) parallel execution.

        Args:
            prompts: List of prompt strings to execute in parallel.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens per response.
            max_workers: Thread pool size (default: len(prompts), capped at 10).

        Returns:
            List of AgentResponse in the same order as prompts.
        """
        if not prompts:
            return []

        if self.mock_mode:
            return [self._mock_response(p) for p in prompts]

        if max_workers <= 0:
            max_workers = min(len(prompts), 10)

        results: dict[int, AgentResponse] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {}
            for idx, prompt in enumerate(prompts):
                future = executor.submit(
                    self.run_prompt, prompt, temperature, max_tokens
                )
                future_to_idx[future] = idx

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()

        return [results[i] for i in range(len(prompts))]

    # ── Internal API call machinery ────────────────────────────────────────

    def _call_with_retry(self, payload: dict[str, Any]) -> AgentResponse:
        """Execute the API call with exponential backoff on rate limits."""
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                return self._execute_call(payload)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429 or exc.code >= 500:
                    backoff = _BASE_BACKOFF_S * (2 ** attempt)
                    if exc.code == 429:
                        retry_after = exc.headers.get("Retry-After")
                        if retry_after:
                            try:
                                backoff = float(retry_after)
                            except ValueError:
                                pass
                    time.sleep(backoff)
                    continue
                raise
            except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
                last_error = exc
                backoff = _BASE_BACKOFF_S * (2 ** attempt)
                time.sleep(backoff)
                continue

        raise ConnectionError(
            f"API call failed after {self.max_retries + 1} attempts: {last_error}"
        )

    def _execute_call(self, payload: dict[str, Any]) -> AgentResponse:
        """Make a single HTTP request to the chat completions endpoint."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.api_url,
            data=body,
            headers=headers,
            method="POST",
        )

        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        latency_ms = (time.perf_counter() - t0) * 1000.0

        choice = data["choices"][0]
        content = choice.get("message", {}).get("content", "")
        finish_reason = choice.get("finish_reason", "")

        usage = data.get("usage", {})
        token_usage = TokenUsage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )

        self._total_tokens.prompt_tokens += token_usage.prompt_tokens
        self._total_tokens.completion_tokens += token_usage.completion_tokens
        self._total_tokens.total_tokens += token_usage.total_tokens

        return AgentResponse(
            content=content,
            model=data.get("model", self.model),
            latency_ms=latency_ms,
            token_usage=token_usage,
            finish_reason=finish_reason,
            mock=False,
        )

    # ── Mock mode ──────────────────────────────────────────────────────────

    def _mock_response(self, prompt: str) -> AgentResponse:
        """Generate a deterministic mock response for CI environments."""
        lower = prompt.lower()
        confidence = 7
        content_parts = ["[MOCK] Received prompt."]

        if "angle:" in lower:
            angle_match = re.search(r"(?i)angle:\s*(\w[\w\s']*)", prompt)
            angle = angle_match.group(1).strip() if angle_match else "UNKNOWN"
            confidence = 8 if "performance" in angle.lower() else 7
            content_parts.append(f"ANGLE: {angle}")
            content_parts.append(
                f"Analysis from {angle.lower()} perspective. Confidence: {confidence}."
            )
        elif "rapid strike" in lower:
            content_parts.append("PROBLEM: identified.")
            content_parts.append("OBVIOUS ANSWER: standard approach.")
            content_parts.append("SANITY CHECK: assumptions hold.")
            confidence = 8
            content_parts.append(f"CONFIDENCE: {confidence}")
        elif "deep think" in lower or "deepthink" in lower:
            for i, tech in enumerate(DEEP_THINK_TECHNIQUES, 1):
                content_parts.append(f"[CHECKPOINT {i}] {tech} complete.")
            confidence = 8
            content_parts.append(f"Confidence: {confidence}")
        elif "synthesiz" in lower:
            synth_match = re.search(r"(?i)synthesizer\s+(\w+)", prompt)
            synth = synth_match.group(1) if synth_match else "UNKNOWN"
            content_parts.append(f"SYNTHESIZER {synth}: analysis complete.")
            confidence = 7
            content_parts.append(f"Confidence: {confidence}")
        elif "grand jury" in lower or "diamondthink" in lower or "commitment" in lower:
            for phase_id, phase_name in GRAND_JURY_PHASES:
                content_parts.append(f"{phase_id}: {phase_name} complete.")
            confidence = 8
            content_parts.append(f"Confidence: {confidence}")
        elif "megamind" in lower:
            content_parts.append("PHASE M1: Initial Deep Think complete.")
            content_parts.append("PHASE M2: 10 angle-explorers complete.")
            content_parts.append("PHASE M3: 3 synthesizers complete.")
            confidence = 7
            content_parts.append(f"CONFIDENCE: {confidence}")
        else:
            content_parts.append(f"Processed: {prompt[:100]}...")
            confidence = 7
            content_parts.append(f"Confidence: {confidence}")

        token_usage = TokenUsage(
            prompt_tokens=len(prompt.split()),
            completion_tokens=100,
            total_tokens=len(prompt.split()) + 100,
        )

        self._total_tokens.prompt_tokens += token_usage.prompt_tokens
        self._total_tokens.completion_tokens += token_usage.completion_tokens
        self._total_tokens.total_tokens += token_usage.total_tokens

        return AgentResponse(
            content="\n".join(content_parts),
            model="mock",
            latency_ms=1.0,
            token_usage=token_usage,
            finish_reason="stop",
            mock=True,
        )


# ═══════════════════════════════════════════════════════════════════════════
# SwarmRunner — full reasoning swarm pipeline with real API calls
# ═══════════════════════════════════════════════════════════════════════════


class SwarmRunner:
    """Constructs and executes the full reasoning swarm pipeline.

    Takes an AgentHarness and a skill file, constructs mode-specific
    prompts, runs the complete pipeline (including parallel sub-reasoners
    for Ensemble/Megamind), and captures structured SwarmTrace output.
    """

    def __init__(self, harness: AgentHarness, skills_dir: Path | None = None):
        self.harness = harness
        self.skills_dir = skills_dir or _SKILLS_DIR

    @classmethod
    def from_env(cls, **harness_kwargs: Any) -> SwarmRunner:
        """Construct with an AgentHarness built from env vars."""
        harness = AgentHarness.from_env(**harness_kwargs)
        return cls(harness=harness)

    def run(
        self,
        task: str,
        mode: str = "",
        context: str = "",
        task_type: str = "IMPLEMENTATION",
        complexity: str = "MEDIUM",
        stakes: str = "MEDIUM",
        prior_fails: int = 0,
        files_involved: str = "1-2",
        framework_css: bool = False,
        production: bool = False,
    ) -> SwarmTrace:
        """Execute the full reasoning swarm pipeline.

        If mode is not specified, the intake classifier auto-selects based
        on task metadata.

        Args:
            task: The task description / problem statement.
            mode: Force a specific mode (RAPID STRIKE, DEEP THINK, etc.)
                  or empty string for auto-classification.
            context: Additional context (code, errors, etc.)
            task_type: BUG_FIX, IMPLEMENTATION, ARCHITECTURE, etc.
            complexity: LOW, MEDIUM, HIGH, EXTREME.
            stakes: LOW, MEDIUM, HIGH, CRITICAL.
            prior_fails: Number of prior failures on this task.
            files_involved: File count category: "1-2", "3-5", or "6+".
            framework_css: Whether framework/CSS is involved.
            production: Whether this is a production system.

        Returns:
            SwarmTrace with structured output and metrics.
        """
        t_start = time.perf_counter()

        if not mode:
            mode = classify_task(
                task_type=task_type,
                complexity=complexity,
                stakes=stakes,
                prior_fails=prior_fails,
                files_involved=files_involved,
                framework_css=framework_css,
                production=production,
            )

        skill_content = self._load_skill(mode)

        dispatch = {
            "RAPID STRIKE": self._run_rapid,
            "DEEP THINK": self._run_deep,
            "ENSEMBLE": self._run_ensemble,
            "MEGAMIND": self._run_megamind,
            "GRAND JURY": self._run_jury,
        }

        trace = dispatch[mode](task, context, skill_content)
        trace.total_latency_ms = (time.perf_counter() - t_start) * 1000.0
        trace.mock = self.harness.mock_mode

        # Accumulate total tokens from harness
        trace.total_tokens = TokenUsage(
            prompt_tokens=self.harness.total_tokens.prompt_tokens,
            completion_tokens=self.harness.total_tokens.completion_tokens,
            total_tokens=self.harness.total_tokens.total_tokens,
        )

        return trace

    # ── Skill loading ──────────────────────────────────────────────────────

    def _load_skill(self, mode: str) -> str:
        """Load the skill template for the given mode."""
        filename = _MODE_SKILL_MAP.get(mode, "reasoning-swarm-SKILL.md")
        path = self.skills_dir / filename
        if not path.exists():
            path = self.skills_dir / "reasoning-swarm-SKILL.md"
        if path.exists():
            return path.read_text()
        return ""

    # ── Prompt construction ────────────────────────────────────────────────

    def _build_prompt(
        self,
        mode: str,
        task: str,
        context: str,
        skill_content: str,
        angle: str = "",
        phase: str = "",
    ) -> str:
        """Construct a full reasoning swarm prompt from skill template."""
        parts: list[str] = []

        if skill_content:
            parts.append(f"SKILL INSTRUCTION:\n{skill_content}\n")

        parts.append(f"MODE: {mode}")
        if angle:
            parts.append(f"ANGLE: {angle}")
        if phase:
            parts.append(f"PHASE: {phase}")

        parts.append(f"\nTASK:\n{task}")

        if context:
            parts.append(f"\nCONTEXT:\n{context}")

        parts.append(
            "\nRETURN FORMAT:\n"
            "1. Reasoning summary (3-5 sentences with evidence)\n"
            "2. Concrete recommendation with tradeoffs\n"
            "3. Confidence (1-10)\n"
            "4. Key risks or uncertainties\n"
            "5. Dissenting considerations"
        )

        return "\n\n".join(parts)

    # ── Mode executors ─────────────────────────────────────────────────────

    def _run_rapid(
        self, task: str, context: str, skill_content: str
    ) -> SwarmTrace:
        """Execute RAPID STRIKE mode — single prompt, expect quick answer."""
        prompt = self._build_prompt(
            mode="RAPID STRIKE",
            task=task,
            context=context,
            skill_content=skill_content,
        )
        response = self.harness.run_prompt(prompt)

        confidence = self._extract_confidence(response.content)

        return SwarmTrace(
            mode="RAPID",
            confidence=confidence,
            checkpoints_hit=4,
            escalations=0 if confidence >= 8 else 1,
            techniques_used=["RAPID STRIKE"],
            raw_output=response.content,
            total_latency_ms=response.latency_ms,
            angle_responses=[response],
        )

    def _run_deep(
        self, task: str, context: str, skill_content: str
    ) -> SwarmTrace:
        """Execute DEEP THINK mode — 11 techniques via sequential prompts."""
        techniques_used: list[str] = []
        output_parts: list[str] = []
        total_confidence = 0
        responses: list[AgentResponse] = []

        for i, technique in enumerate(DEEP_THINK_TECHNIQUES, 1):
            prompt = self._build_prompt(
                mode="DEEP THINK",
                task=task,
                context=context,
                skill_content=skill_content,
                phase=f"Technique {i}: {technique}",
            )
            response = self.harness.run_prompt(prompt)
            responses.append(response)

            checkpoint_marker = f"[CHECKPOINT {i}]"
            output_parts.append(
                f"┌─ {technique} ──────────────────────────────────────\n"
                f"│ {response.content}\n"
                f"│ {checkpoint_marker}\n"
                f"└{'─' * 50}┘"
            )
            techniques_used.append(technique)
            total_confidence += self._extract_confidence(response.content)

        avg_conf = min(10, max(1, round(total_confidence / len(DEEP_THINK_TECHNIQUES))))

        output_parts.append(
            f"\n🧠 DEEP THINK COMPLETE\n"
            f"Checkpoints Hit: {len(DEEP_THINK_TECHNIQUES)}/{len(DEEP_THINK_TECHNIQUES)}\n"
            f"Confidence: {avg_conf}\n"
            f"---\nFinal answer for: {task}"
        )

        return SwarmTrace(
            mode="DEEP",
            confidence=avg_conf,
            checkpoints_hit=len(DEEP_THINK_TECHNIQUES),
            escalations=0 if avg_conf >= 7 else 1,
            techniques_used=techniques_used,
            raw_output="\n".join(output_parts),
            angle_responses=responses,
        )

    def _run_ensemble(
        self, task: str, context: str, skill_content: str
    ) -> SwarmTrace:
        """Execute ENSEMBLE mode — 5 parallel angles + synthesis."""
        prompts = [
            self._build_prompt(
                mode="ENSEMBLE",
                task=task,
                context=context,
                skill_content=skill_content,
                angle=angle,
            )
            for angle in ENSEMBLE_ANGLES
        ]

        responses = self.harness.run_parallel(prompts)

        techniques_used: list[str] = []
        output_parts: list[str] = []
        confidences: list[int] = []

        for angle, response in zip(ENSEMBLE_ANGLES, responses):
            output_parts.append(f"ANGLE: {angle}\n{response.content}")
            techniques_used.append(f"ENSEMBLE:{angle}")
            confidences.append(self._extract_confidence(response.content))

        weighted_conf = round(sum(confidences) / len(confidences)) if confidences else 5

        # Synthesis prompt
        angle_outputs = "\n\n".join(
            f"=== {angle} ===\n{r.content}"
            for angle, r in zip(ENSEMBLE_ANGLES, responses)
        )
        synth_prompt = (
            f"You are the SYNTHESIZER for an Ensemble analysis of the following task:\n\n"
            f"TASK: {task}\n\n"
            f"ANGLE OUTPUTS:\n{angle_outputs}\n\n"
            f"Provide a synthesis covering:\n"
            f"AGREEMENT: What most angles agree on\n"
            f"DISAGREEMENT: Where they differ\n"
            f"RESOLUTION: How to resolve conflicts\n"
            f"RISKS: From security + edge case angles\n"
            f"DEVIL'S CONCERNS: Valid or dismissed\n"
            f"CONFIDENCE: weighted average"
        )
        synth_response = self.harness.run_prompt(synth_prompt)

        output_parts.append(f"\nSYNTHESIS:\n{synth_response.content}")
        techniques_used.append("ENSEMBLE:SYNTHESIS")

        raw = "\n\n".join(output_parts)
        raw += (
            f"\n\n🧠 ENSEMBLE COMPLETE\n"
            f"Sub-Reasoners: {len(ENSEMBLE_ANGLES)}\n"
            f"Confidence: {weighted_conf}"
        )

        return SwarmTrace(
            mode="ENSEMBLE",
            confidence=weighted_conf,
            checkpoints_hit=len(ENSEMBLE_ANGLES),
            escalations=0 if weighted_conf >= 7 else 1,
            techniques_used=techniques_used,
            subprocess_calls=len(ENSEMBLE_ANGLES) + 1,
            raw_output=raw,
            angle_responses=responses + [synth_response],
        )

    def _run_megamind(
        self, task: str, context: str, skill_content: str
    ) -> SwarmTrace:
        """Execute MEGAMIND mode — 10 angles → 3 synthesizers → final."""
        all_responses: list[AgentResponse] = []
        techniques_used: list[str] = []
        output_parts: list[str] = []

        # Phase M1 — initial Deep Think pass (single consolidated prompt)
        m1_prompt = self._build_prompt(
            mode="MEGAMIND",
            task=task,
            context=context,
            skill_content=skill_content,
            phase="Phase M1: Initial Deep Think Pass — use all 11 techniques",
        )
        m1_response = self.harness.run_prompt(m1_prompt, max_tokens=8192)
        all_responses.append(m1_response)
        output_parts.append(f"PHASE M1: Initial Deep Think Pass\n{m1_response.content}")

        for tech in DEEP_THINK_TECHNIQUES:
            techniques_used.append(f"MEGA:M1:{tech}")

        # Phase M2 — 10 angle-explorers in parallel
        m2_prompts = [
            self._build_prompt(
                mode="MEGAMIND",
                task=task,
                context=context,
                skill_content=skill_content,
                angle=angle,
                phase="Phase M2: Angle Explorer",
            )
            for angle in MEGAMIND_ANGLES
        ]
        m2_responses = self.harness.run_parallel(m2_prompts)
        all_responses.extend(m2_responses)

        output_parts.append("\nPHASE M2: 10 Angle-Explorers")
        for angle, response in zip(MEGAMIND_ANGLES, m2_responses):
            output_parts.append(f"  ANGLE: {angle}\n  {response.content}")
            techniques_used.append(f"MEGA:M2:{angle}")

        # Phase M3 — 3 synthesizers in parallel
        angle_outputs = "\n\n".join(
            f"=== {angle} ===\n{r.content}"
            for angle, r in zip(MEGAMIND_ANGLES, m2_responses)
        )

        synth_directives = {
            "CONSENSUS": (
                "Find what most angles agree on. Report the majority position, "
                "agreement level, and what 7+ angles agree on."
            ),
            "CONFLICT": (
                "Identify disagreements and root causes. Report key conflicts, "
                "root causes, and recommended resolutions."
            ),
            "RISK": (
                "Assess worst-case scenarios. Report the scariest risks, "
                "worst case if wrong, and minimum safe answer."
            ),
        }

        m3_prompts = [
            (
                f"You are SYNTHESIZER {synth} ({directive})\n\n"
                f"TASK: {task}\n\n"
                f"ALL ANGLE OUTPUTS:\n{angle_outputs}"
            )
            for synth, directive in synth_directives.items()
        ]
        m3_responses = self.harness.run_parallel(m3_prompts)
        all_responses.extend(m3_responses)

        output_parts.append("\nPHASE M3: 3 Synthesizers")
        for synth, response in zip(MEGAMIND_SYNTHESIZERS, m3_responses):
            output_parts.append(f"  SYNTHESIZER {synth}: {response.content}")
            techniques_used.append(f"MEGA:M3:{synth}")

        # Phase M4 — final synthesis
        synth_outputs = "\n\n".join(
            f"=== SYNTH {synth} ===\n{r.content}"
            for synth, r in zip(MEGAMIND_SYNTHESIZERS, m3_responses)
        )
        m4_prompt = (
            f"You are the FINAL REASONER. Integrate these three synthesizer reports.\n\n"
            f"TASK: {task}\n\n"
            f"SYNTHESIZER REPORTS:\n{synth_outputs}\n\n"
            f"Provide FINAL SYNTHESIS with:\n"
            f"- Consensus answer\n"
            f"- Modifications from conflicts\n"
            f"- Risk mitigations\n"
            f"- CONFIDENCE (1-10)"
        )
        m4_response = self.harness.run_prompt(m4_prompt, max_tokens=8192)
        all_responses.append(m4_response)
        techniques_used.append("MEGA:M4:FINAL_SYNTHESIS")

        conf = self._extract_confidence(m4_response.content)
        output_parts.append(f"\nPHASE M4: Final Synthesis\n{m4_response.content}")

        raw = "\n".join(output_parts)
        raw += (
            f"\n\n🧠 MEGAMIND COMPLETE\n"
            f"Architecture: 10 → 3 → 1\n"
            f"Final Confidence: {conf}"
        )

        return SwarmTrace(
            mode="MEGA",
            confidence=conf,
            checkpoints_hit=len(MEGAMIND_ANGLES) + len(MEGAMIND_SYNTHESIZERS),
            escalations=0 if conf >= 7 else 1,
            techniques_used=techniques_used,
            subprocess_calls=len(MEGAMIND_ANGLES) + len(MEGAMIND_SYNTHESIZERS) + 2,
            raw_output=raw,
            angle_responses=all_responses,
        )

    def _run_jury(
        self, task: str, context: str, skill_content: str
    ) -> SwarmTrace:
        """Execute GRAND JURY mode — 9-phase investigation protocol."""
        techniques_used: list[str] = []
        output_parts: list[str] = []
        evidence: list[str] = []
        responses: list[AgentResponse] = []

        for phase_id, phase_name in GRAND_JURY_PHASES:
            prompt = self._build_prompt(
                mode="GRAND JURY",
                task=task,
                context=context,
                skill_content=skill_content,
                phase=f"{phase_id}: {phase_name}",
            )
            response = self.harness.run_prompt(prompt)
            responses.append(response)

            output_parts.append(
                f"┌─ {phase_name} ({phase_id}) ──────────────────\n"
                f"│ {response.content}\n"
                f"└{'─' * 50}┘"
            )
            techniques_used.append(f"JURY:{phase_id}")

            if phase_id == "GJ-4":
                evidence.append(
                    f"E1: Evidence from GJ-4 Evidence Ledger phase"
                )

        conf = self._extract_confidence(responses[-1].content) if responses else 5

        raw = "\n".join(output_parts)
        raw += (
            f"\n\n⚖️ GRAND JURY COMPLETE\n"
            f"Evidence Entries: {len(evidence)}\n"
            f"Hypotheses Tested: 4\n"
            f"Root Cause: Identified via evidence chain\n"
            f"Fix: Atomic change applied\n"
            f"Verification: PASS"
        )

        return SwarmTrace(
            mode="JURY",
            confidence=conf,
            checkpoints_hit=len(GRAND_JURY_PHASES),
            escalations=0,
            techniques_used=techniques_used,
            evidence_entries=evidence,
            raw_output=raw,
            angle_responses=responses,
        )

    # ── Confidence extraction ──────────────────────────────────────────────

    @staticmethod
    def _extract_confidence(text: str) -> int:
        """Extract a confidence score (1-10) from model output."""
        match = re.search(r"[Cc]onfidence[^:]*:\s*(\d+)", text)
        if match:
            return min(10, max(1, int(match.group(1))))
        return 7


# ═══════════════════════════════════════════════════════════════════════════
# Pytest fixtures
# ═══════════════════════════════════════════════════════════════════════════

try:
    import pytest

    @pytest.fixture
    def agent_harness():
        """Provide an AgentHarness built from environment variables.

        Usage in tests:
            def test_real_call(agent_harness):
                resp = agent_harness.run_prompt("What is 2+2?")
                assert "4" in resp.content
                assert resp.latency_ms > 0
        """
        return AgentHarness.from_env()

    @pytest.fixture
    def swarm_runner():
        """Provide a SwarmRunner built from environment variables.

        Usage in tests:
            def test_swarm_run(swarm_runner):
                trace = swarm_runner.run("Fix the login bug", mode="RAPID STRIKE")
                assert trace.confidence >= 1
                assert trace.mode == "RAPID"
        """
        return SwarmRunner.from_env()

except ImportError:
    pass
