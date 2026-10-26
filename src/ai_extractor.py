"""
src/ai_extractor.py
===================
Groq Cloud LPU inference engine with Multi-Key Pool, automatic rate-limit failover,
round-robin load distribution, and JSON schema extraction.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        dotenv.load_dotenv(dotenv_path=_env_path, override=True)
    else:
        dotenv.load_dotenv(override=True)
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Default prompt template path
_DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "extract_candidate.txt"

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
FALLBACK_GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]


# ---------------------------------------------------------------------------
# Multi-Key Pool with Rate-Limit Failover
# ---------------------------------------------------------------------------


@dataclass
class GroqKeyStatus:
    """Status tracking for a single Groq API key."""

    key: str
    index: int
    is_active: bool = True
    rate_limited_until: float = 0.0
    total_calls: int = 0
    success_calls: int = 0
    rate_limit_hits: int = 0
    last_error: str = ""

    @property
    def masked_key(self) -> str:
        k = self.key.strip()
        if len(k) <= 8:
            return "gsk_***"
        return f"{k[:7]}...{k[-4:]}"

    @property
    def is_available(self) -> bool:
        return self.is_active and time.time() >= self.rate_limited_until


class GroqKeyPool:
    """Thread-safe multi-key manager for Groq API keys with round-robin and 429 failover."""

    def __init__(self, keys: Optional[list[str]] = None) -> None:
        self._lock = threading.Lock()
        self._current_idx = 0
        self.keys: list[GroqKeyStatus] = []
        if keys:
            self.set_keys(keys)
        else:
            self.reload_from_env()

    def reload_from_env(self) -> None:
        """Load all available Groq keys from environment variables."""
        discovered: list[str] = []

        # 1. Comma/space/newline-separated list
        env_multi = os.getenv("GROQ_API_KEYS", "").strip()
        if env_multi:
            for item in re.split(r"[,;\s\n]+", env_multi):
                k = item.strip()
                if k and k.startswith("gsk_") and k not in discovered:
                    discovered.append(k)

        # 2. Numbered keys: GROQ_API_KEY_1, GROQ_API_KEY_2, etc.
        for i in range(1, 11):
            k = os.getenv(f"GROQ_API_KEY_{i}", "").strip()
            if k and k not in discovered:
                discovered.append(k)

        # 3. Standard single key
        primary = os.getenv("GROQ_API_KEY", "").strip()
        if primary and primary not in discovered:
            discovered.insert(0, primary)

        self.set_keys(discovered)

    def set_keys(self, key_strings: list[str]) -> None:
        """Configure the key pool with a list of clean API keys."""
        with self._lock:
            self.keys = []
            seen = set()
            idx = 0
            for raw in key_strings:
                clean = raw.strip().strip("'\"")
                if clean and clean not in seen:
                    seen.add(clean)
                    self.keys.append(GroqKeyStatus(key=clean, index=idx))
                    idx += 1
            self._current_idx = 0

    @property
    def total_count(self) -> int:
        return len(self.keys)

    @property
    def active_count(self) -> int:
        now = time.time()
        return sum(1 for k in self.keys if k.is_active and now >= k.rate_limited_until)

    def get_key_for_request(self) -> Optional[GroqKeyStatus]:
        """Obtain the next available Groq key via round-robin."""
        with self._lock:
            if not self.keys:
                return None

            now = time.time()
            n = len(self.keys)

            # First pass: look for an immediately available key starting from current_idx
            for offset in range(n):
                idx = (self._current_idx + offset) % n
                status = self.keys[idx]
                if status.is_active and now >= status.rate_limited_until:
                    self._current_idx = (idx + 1) % n
                    return status

            # Second pass: if all are rate-limited, find the one expiring soonest
            active_keys = [k for k in self.keys if k.is_active]
            if active_keys:
                soonest = min(active_keys, key=lambda k: k.rate_limited_until)
                return soonest

            return None

    def record_success(self, key_status: GroqKeyStatus) -> None:
        """Mark a successful API call for the given key."""
        with self._lock:
            key_status.total_calls += 1
            key_status.success_calls += 1
            key_status.rate_limited_until = 0.0

    def record_rate_limit(self, key_status: GroqKeyStatus, backoff_seconds: float = 30.0) -> None:
        """Flag a key as rate-limited (HTTP 429) for backoff_seconds."""
        with self._lock:
            key_status.total_calls += 1
            key_status.rate_limit_hits += 1
            key_status.rate_limited_until = time.time() + backoff_seconds
            logger.warning(
                "Groq key %s (index %d) hit rate limit. Cooling down for %.1fs. Pool active: %d/%d",
                key_status.masked_key,
                key_status.index,
                backoff_seconds,
                self.active_count,
                self.total_count,
            )

    def record_failure(self, key_status: GroqKeyStatus, error_msg: str) -> None:
        with self._lock:
            key_status.total_calls += 1
            key_status.last_error = error_msg


# Global default key pool instance
_GLOBAL_KEY_POOL = GroqKeyPool()


# ---------------------------------------------------------------------------
# Configuration & Result Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AIConfig:
    """Configuration for Groq AI extraction."""

    model: str = DEFAULT_GROQ_MODEL
    key_pool: GroqKeyPool = field(default_factory=lambda: _GLOBAL_KEY_POOL)
    timeout: int = 45
    max_retries: int = 3
    retry_delay: float = 0.5
    temperature: float = 0.0
    num_predict: int = 4096
    prompt_path: Path = field(default_factory=lambda: _DEFAULT_PROMPT_PATH)


@dataclass
class AIExtractionResult:
    """Result of a Groq AI extraction attempt."""

    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""
    raw: str = ""
    model_used: str = ""
    key_used: str = ""
    key_index: Optional[int] = None
    duration_s: float = 0.0


# ---------------------------------------------------------------------------
# JSON Response Parsing Helpers
# ---------------------------------------------------------------------------


def extract_json_from_response(raw: str) -> tuple[dict, str]:
    """Parse JSON object from model response, handling fences, leading text, and trailing commas."""
    text = raw.strip()

    # Strip reasoning blocks if present
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Strip markdown fences ```json ... ```
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Find the outermost { ... }
    start = text.find("{")
    if start == -1:
        return {}, f"No JSON object found in response: {raw[:200]!r}"

    depth = 0
    end = -1
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end == -1:
        return {}, f"Unterminated JSON object in response: {raw[:200]!r}"

    json_str = text[start : end + 1]

    try:
        return json.loads(json_str), ""
    except json.JSONDecodeError:
        # Clean trailing commas
        cleaned_json = re.sub(r",\s*([}\]])", r"\1", json_str)
        try:
            return json.loads(cleaned_json), ""
        except json.JSONDecodeError as exc:
            return {}, f"JSON parse error: {exc}"


def list_groq_models(api_key: Optional[str] = None) -> list[str]:
    """Fetch active chat models available to the Groq API key."""
    key = (api_key or os.getenv("GROQ_API_KEY", "")).strip()
    if not key:
        return list(FALLBACK_GROQ_MODELS)
    try:
        import groq

        client = groq.Groq(api_key=key, timeout=10)
        models_resp = client.models.list()
        chat_models: list[str] = []
        for m in models_resp.data:
            mid = m.id.lower()
            if any(w in mid for w in ("whisper", "tts", "embed", "guard", "safeguard", "bge")):
                continue
            chat_models.append(m.id)

        if chat_models:
            preferred = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
            ordered = [p for p in preferred if p in chat_models]
            for m in chat_models:
                if m not in ordered:
                    ordered.append(m)
            return ordered
    except Exception as exc:
        logger.warning("Could not list Groq models: %s", exc)
    return list(FALLBACK_GROQ_MODELS)


def check_groq_available(pool: Optional[GroqKeyPool] = None) -> tuple[bool, str]:
    """Check whether at least one key in the pool is valid and reachable."""
    p = pool or _GLOBAL_KEY_POOL
    if p.total_count == 0:
        return False, "No Groq API keys configured. Set GROQ_API_KEY in .env or sidebar."

    key_status = p.get_key_for_request()
    if not key_status:
        return False, "All Groq API keys are currently rate-limited."

    try:
        import groq

        client = groq.Groq(api_key=key_status.key, timeout=10)
        client.models.list()
        return True, f"Groq connected ({p.active_count}/{p.total_count} keys active)"
    except Exception as exc:
        err_str = str(exc)
        if "401" in err_str or "AuthenticationError" in type(exc).__name__:
            return False, f"Invalid Groq key {key_status.masked_key}. Check console.groq.com/keys"
        return False, f"Could not connect to Groq: {exc}"


# ---------------------------------------------------------------------------
# Main Extractor Class
# ---------------------------------------------------------------------------


class AIExtractor:
    """Manages prompt rendering, multi-key Groq calls, 429 failover, and JSON parsing."""

    def __init__(self, config: Optional[AIConfig] = None) -> None:
        self.config = config or AIConfig()
        self._prompt_template: Optional[str] = None

    def _load_prompt(self) -> str:
        if self._prompt_template is None:
            path = self.config.prompt_path
            if path.exists():
                self._prompt_template = path.read_text(encoding="utf-8")
            else:
                self._prompt_template = (
                    "Extract resume data into JSON schema: "
                    "full_name, email, phone, location, education, work_experience, projects, "
                    "technical_skills, programming_languages, tools, certifications.\n"
                    "Resume text:\n{resume_text}"
                )
        return self._prompt_template

    def check_availability(self) -> tuple[bool, str]:
        return check_groq_available(self.config.key_pool)

    def extract(self, resume_text: str, filename: str = "") -> AIExtractionResult:
        """Extract candidate data with multi-key failover."""
        if not resume_text or not resume_text.strip():
            return AIExtractionResult(
                success=False,
                error="Empty resume text — skipping AI extraction.",
                model_used=self.config.model,
            )

        template = self._load_prompt()
        prompt = template.replace("{resume_text}", resume_text[:30000])

        start_time = time.monotonic()
        last_error = ""

        # Try up to max_retries attempts across the key pool
        for attempt in range(1, self.config.max_retries + 1):
            key_status = self.config.key_pool.get_key_for_request()
            if not key_status:
                last_error = "No active Groq keys available in the pool (all rate-limited)."
                time.sleep(self.config.retry_delay)
                continue

            try:
                import groq

                client = groq.Groq(api_key=key_status.key, timeout=self.config.timeout)
                system_msg = (
                    "You are a meticulous talent intelligence extraction AI. "
                    "Your objective is 100% extraction precision: never omit, truncate, or summarize "
                    "candidate contact details, work experience, responsibilities, education records, "
                    "projects, skills, or links. "
                    "Output must strictly adhere to the requested JSON schema without any markdown fences or commentary."
                )

                call_start = time.monotonic()
                completion = client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=self.config.temperature,
                    max_completion_tokens=self.config.num_predict,
                )

                raw = completion.choices[0].message.content or ""
                duration = time.monotonic() - call_start

                parsed, parse_error = extract_json_from_response(raw)
                if parse_error:
                    self.config.key_pool.record_failure(key_status, parse_error)
                    last_error = parse_error
                    continue

                # Success! Record metrics
                self.config.key_pool.record_success(key_status)
                logger.info(
                    "[%s] Groq success on key %s (index %d) in %.2fs",
                    filename,
                    key_status.masked_key,
                    key_status.index,
                    duration,
                )

                return AIExtractionResult(
                    success=True,
                    data=parsed,
                    raw=raw,
                    model_used=self.config.model,
                    key_used=key_status.masked_key,
                    key_index=key_status.index,
                    duration_s=time.monotonic() - start_time,
                )

            except Exception as exc:
                err_str = str(exc)
                err_type = type(exc).__name__

                # Check for HTTP 429 Rate Limit
                if "429" in err_str or "RateLimitError" in err_type:
                    self.config.key_pool.record_rate_limit(key_status, backoff_seconds=30.0)
                    last_error = f"Rate limit on key {key_status.masked_key} — rotating to next key"
                    logger.warning("[%s] %s", filename, last_error)
                    continue

                # Check for 401 Auth Error
                if "401" in err_str or "AuthenticationError" in err_type:
                    key_status.is_active = False
                    self.config.key_pool.record_failure(key_status, "Invalid API Key")
                    last_error = f"Invalid Groq key {key_status.masked_key} disabled"
                    continue

                # Transient model error
                self.config.key_pool.record_failure(key_status, err_str)
                last_error = f"Groq error: {exc}"
                time.sleep(self.config.retry_delay)

        return AIExtractionResult(
            success=False,
            error=f"Extraction failed after {self.config.max_retries} attempts: {last_error}",
            model_used=self.config.model,
            duration_s=time.monotonic() - start_time,
        )
