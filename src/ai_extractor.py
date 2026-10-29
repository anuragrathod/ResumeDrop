"""
src/ai_extractor.py
===================
NVIDIA NIM (NVIDIA Inference Microservices) AI extraction engine.

Features:
- OpenAI-compatible client targeting https://integrate.api.nvidia.com/v1.
- Multi-Key Pool managing 3 NVIDIA API keys (NVIDIA_API_KEY_1, NVIDIA_API_KEY_2, NVIDIA_API_KEY_3).
- Concurrency-safe shared rate limiter enforcing <= 40 requests/minute globally across all keys.
- Safe parallel execution across independent worker threads.
- Robust HTTP 429 rate-limit handling, Retry-After header parsing, exponential backoff, and temporary cooldowns.
- Automatic key rotation, credential masking (nvapi-***), and clean JSON schema extraction.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime
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

NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
DEFAULT_NVIDIA_MODEL = os.getenv("DEFAULT_NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
FALLBACK_NVIDIA_MODELS = [
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "deepseek-ai/deepseek-r1",
    "mistralai/mistral-large-2-instruct",
]
DEFAULT_RATE_LIMIT_RPM = int(os.getenv("NVIDIA_RATE_LIMIT_RPM", "40"))
DEFAULT_REQUEST_TIMEOUT = 180


def get_default_timeout() -> int:
    """
    Get the default per-request timeout in seconds.
    Prioritizes NVIDIA_API_TIMEOUT, then REQUEST_TIMEOUT (if > 60s), defaulting to 180s
    to prevent premature timeouts on deep reasoning models and multi-page resumes.
    """
    nv_val = os.getenv("NVIDIA_API_TIMEOUT")
    if nv_val:
        try:
            return int(nv_val)
        except ValueError:
            pass
    req_val = os.getenv("REQUEST_TIMEOUT")
    if req_val:
        try:
            v = int(req_val)
            if v > 60:
                return v
        except ValueError:
            pass
    return DEFAULT_REQUEST_TIMEOUT


# ---------------------------------------------------------------------------
# Shared Concurrency-Safe Rate Limiter (Max 40 RPM across all keys)
# ---------------------------------------------------------------------------


class NvidiaRateLimiter:
    """
    Thread-safe sliding-window rate limiter.
    Ensures that aggregate outgoing API calls across all keys and worker threads
    never exceed max_requests in any rolling 60-second window.
    Also handles global account-level cooldowns upon receiving HTTP 429s.
    """

    def __init__(self, max_requests_per_minute: int = DEFAULT_RATE_LIMIT_RPM) -> None:
        self.max_requests = max(1, max_requests_per_minute)
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._request_timestamps: list[float] = []
        self._global_cooldown_until: float = 0.0

    @property
    def current_load_last_minute(self) -> int:
        with self._lock:
            now = time.time()
            cutoff = now - 60.0
            return sum(1 for t in self._request_timestamps if t >= cutoff)

    def set_rate_limit(self, max_rpm: int) -> None:
        with self._lock:
            self.max_requests = max(1, max_rpm)
            self._condition.notify_all()

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Block safely until an API call can proceed without violating the 60-second rate limit
        or account-level cooldown.
        Returns True if permit was granted, False if timeout elapsed.
        """
        start_wait = time.monotonic()

        with self._condition:
            while True:
                now = time.time()

                # 1. Prune timestamps older than 60 seconds
                cutoff = now - 60.0
                self._request_timestamps = [t for t in self._request_timestamps if t >= cutoff]

                # 2. Check if a global account-level cooldown is in effect
                if now < self._global_cooldown_until:
                    sleep_needed = self._global_cooldown_until - now
                    if timeout is not None:
                        remaining_timeout = timeout - (time.monotonic() - start_wait)
                        if remaining_timeout <= 0:
                            return False
                        sleep_needed = min(sleep_needed, remaining_timeout)
                    self._condition.wait(timeout=max(0.01, sleep_needed))
                    continue

                # 3. Check if we have capacity under the rolling-minute limit
                if len(self._request_timestamps) < self.max_requests:
                    self._request_timestamps.append(time.time())
                    return True

                # 4. Limit reached: wait until the oldest recorded timestamp expires
                oldest_timestamp = self._request_timestamps[0]
                sleep_needed = (oldest_timestamp + 60.0) - now + 0.02
                if sleep_needed <= 0:
                    sleep_needed = 0.02

                if timeout is not None:
                    remaining_timeout = timeout - (time.monotonic() - start_wait)
                    if remaining_timeout <= 0:
                        return False
                    sleep_needed = min(sleep_needed, remaining_timeout)

                logger.debug(
                    "Rate limit reached (%d/%d RPM). Throttling request for %.2fs",
                    len(self._request_timestamps),
                    self.max_requests,
                    sleep_needed,
                )
                self._condition.wait(timeout=max(0.01, sleep_needed))

    def record_global_cooldown(self, cooldown_seconds: float = 30.0) -> None:
        """Enforce account-level pause across all keys upon receiving 429."""
        with self._lock:
            now = time.time()
            self._global_cooldown_until = max(self._global_cooldown_until, now + cooldown_seconds)
            logger.warning(
                "NVIDIA API rate limit triggered. Pausing all worker requests for %.1fs (until %.1f)",
                cooldown_seconds,
                self._global_cooldown_until,
            )
            self._condition.notify_all()

    def reset(self) -> None:
        with self._lock:
            self._request_timestamps.clear()
            self._global_cooldown_until = 0.0
            self._condition.notify_all()


# Global rate limiter instance
_GLOBAL_RATE_LIMITER = NvidiaRateLimiter(DEFAULT_RATE_LIMIT_RPM)


# ---------------------------------------------------------------------------
# API Call Logging (In-Memory Thread-Safe Ring Buffer)
# ---------------------------------------------------------------------------


@dataclass
class ApiCallRecord:
    """Detailed record of an outgoing NVIDIA NIM API call."""

    id: str
    timestamp: str  # "HH:MM:SS"
    document_name: str  # e.g. "resume.pdf" or "Connectivity Ping"
    model: str  # e.g. "meta/llama-3.3-70b-instruct"
    key_masked: str  # e.g. "Key #1 (nvap...sU8P)"
    key_index: int  # 0, 1, 2 or -1
    status: str  # "SUCCESS", "RATE_LIMITED", "AUTH_ERROR", "FAILED", "PARSE_ERROR"
    http_status: int  # 200, 429, 401, 500
    latency_ms: float
    error_detail: str = ""


_API_CALL_LOGS_LOCK = threading.Lock()
_API_CALL_LOGS: list[ApiCallRecord] = []
_MAX_LOG_ENTRIES = 500


def record_api_call_log(
    document_name: str,
    model: str,
    key_status: Optional[NvidiaKeyStatus],
    status: str,
    http_status: int,
    latency_ms: float,
    error_detail: str = "",
) -> ApiCallRecord:
    """Record an API call into the thread-safe ring buffer."""
    now = datetime.now()
    if key_status:
        masked = f"Key #{key_status.index + 1} ({key_status.masked_key})"
        key_idx = key_status.index
    else:
        masked = "None / Rate Limited"
        key_idx = -1

    entry = ApiCallRecord(
        id=f"call_{int(time.time() * 1000)}_{len(_API_CALL_LOGS)}",
        timestamp=now.strftime("%H:%M:%S"),
        document_name=document_name or "System Call",
        model=model or DEFAULT_NVIDIA_MODEL,
        key_masked=masked,
        key_index=key_idx,
        status=status,
        http_status=http_status,
        latency_ms=round(latency_ms, 1),
        error_detail=(error_detail or "")[:240],
    )
    with _API_CALL_LOGS_LOCK:
        _API_CALL_LOGS.insert(0, entry)
        if len(_API_CALL_LOGS) > _MAX_LOG_ENTRIES:
            _API_CALL_LOGS.pop()
    return entry


def get_api_call_logs() -> list[ApiCallRecord]:
    """Retrieve all logged API calls (newest first)."""
    with _API_CALL_LOGS_LOCK:
        return list(_API_CALL_LOGS)


def clear_api_call_logs() -> None:
    """Clear in-memory API call logs."""
    with _API_CALL_LOGS_LOCK:
        _API_CALL_LOGS.clear()


# ---------------------------------------------------------------------------
# Key Pool Manager with 3 NVIDIA API Keys
# ---------------------------------------------------------------------------


@dataclass
class NvidiaKeyStatus:
    """Status tracking for an individual NVIDIA API key."""

    key: str
    index: int
    is_active: bool = True
    rate_limited_until: float = 0.0
    total_calls: int = 0
    success_calls: int = 0
    rate_limit_hits: int = 0
    last_error: str = ""
    in_flight_calls: int = 0

    @property
    def masked_key(self) -> str:
        k = self.key.strip()
        if len(k) <= 10:
            return "nvapi-***"
        # Always mask middle secret tokens
        prefix = k[:8]
        suffix = k[-4:]
        return f"{prefix}...{suffix}"

    @property
    def is_available(self) -> bool:
        return self.is_active and time.time() >= self.rate_limited_until


class NvidiaKeyPool:
    """
    Thread-safe multi-key manager for NVIDIA API keys.
    Distributes requests across 3 configured keys using round-robin and least-concurrency
    with automatic failover and per-key / shared cooldown tracking.
    """

    def __init__(
        self,
        keys: Optional[list[str]] = None,
        rate_limiter: Optional[NvidiaRateLimiter] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._current_idx = 0
        self.keys: list[NvidiaKeyStatus] = []
        self.rate_limiter = rate_limiter or _GLOBAL_RATE_LIMITER
        if keys is not None:
            self.set_keys(keys)
        else:
            self.reload_from_env()

    @classmethod
    def from_env(cls) -> NvidiaKeyPool:
        pool = cls()
        pool.reload_from_env()
        return pool

    def reload_from_env(self) -> None:
        """
        Load NVIDIA API keys from environment variables.
        Explicitly discovers NVIDIA_API_KEY_1, NVIDIA_API_KEY_2, NVIDIA_API_KEY_3,
        as well as comma-separated NVIDIA_API_KEYS and single NVIDIA_API_KEY.
        """
        discovered: list[str] = []

        # 1. Numbered keys 1, 2, 3 (Primary specification)
        for i in range(1, 11):
            k = os.getenv(f"NVIDIA_API_KEY_{i}", "").strip()
            if k and k not in discovered:
                discovered.append(k)

        # 2. Comma/space/newline-separated list
        env_multi = os.getenv("NVIDIA_API_KEYS", "").strip()
        if env_multi:
            for item in re.split(r"[,;\s\n]+", env_multi):
                k = item.strip()
                if k and k not in discovered:
                    discovered.append(k)

        # 3. Standard single key
        primary = os.getenv("NVIDIA_API_KEY", "").strip()
        if primary and primary not in discovered:
            discovered.insert(0, primary)

        self.set_keys(discovered)

    def set_keys(self, key_strings: list[str]) -> None:
        """Configure the key pool with a list of sanitized API keys."""
        with self._lock:
            self.keys = []
            seen = set()
            idx = 0
            for raw in key_strings:
                clean = raw.strip().strip("'\"")
                if clean and clean not in seen:
                    seen.add(clean)
                    self.keys.append(NvidiaKeyStatus(key=clean, index=idx))
                    idx += 1
            self._current_idx = 0

    @property
    def total_count(self) -> int:
        return len(self.keys)

    @property
    def active_count(self) -> int:
        now = time.time()
        return sum(1 for k in self.keys if k.is_active and now >= k.rate_limited_until)

    def get_key_for_request(self) -> Optional[NvidiaKeyStatus]:
        """
        Select the best available key:
        1. Exclude inactive or currently rate-limited keys.
        2. Prefer keys with fewest in-flight requests.
        3. Break ties using round-robin rotation.
        """
        with self._lock:
            if not self.keys:
                return None

            now = time.time()
            available = [k for k in self.keys if k.is_active and now >= k.rate_limited_until]

            if available:
                # Find minimum in-flight calls among available keys
                min_in_flight = min(k.in_flight_calls for k in available)
                best_candidates = [k for k in available if k.in_flight_calls == min_in_flight]

                # Select next via round-robin among best candidates
                n = len(self.keys)
                for offset in range(n):
                    cand_idx = (self._current_idx + offset) % n
                    status = self.keys[cand_idx]
                    if status in best_candidates:
                        self._current_idx = (cand_idx + 1) % n
                        status.in_flight_calls += 1
                        return status

                # Fallback to first best candidate
                selected = best_candidates[0]
                selected.in_flight_calls += 1
                return selected

            # If all are temporarily rate-limited, find the one cooling down soonest
            active_keys = [k for k in self.keys if k.is_active]
            if active_keys:
                soonest = min(active_keys, key=lambda k: k.rate_limited_until)
                soonest.in_flight_calls += 1
                return soonest

            return None

    def release_key(self, key_status: NvidiaKeyStatus) -> None:
        """Decrement in-flight calls safely."""
        with self._lock:
            key_status.in_flight_calls = max(0, key_status.in_flight_calls - 1)

    def record_success(self, key_status: NvidiaKeyStatus) -> None:
        """Record successful invocation."""
        with self._lock:
            key_status.in_flight_calls = max(0, key_status.in_flight_calls - 1)
            key_status.total_calls += 1
            key_status.success_calls += 1
            key_status.rate_limited_until = 0.0

    def record_rate_limit(
        self,
        key_status: NvidiaKeyStatus,
        backoff_seconds: float = 30.0,
        account_wide: bool = True,
    ) -> None:
        """
        Flag key and optionally whole pool as rate limited.
        Because all 3 keys belong to the same NVIDIA account, 429 errors typically
        reflect account-level or model-level quotas.
        """
        with self._lock:
            key_status.in_flight_calls = max(0, key_status.in_flight_calls - 1)
            key_status.total_calls += 1
            key_status.rate_limit_hits += 1
            key_status.rate_limited_until = time.time() + backoff_seconds
            logger.warning(
                "NVIDIA key %s (index %d) hit rate limit (HTTP 429). Cooldown: %.1fs. Pool active: %d/%d",
                key_status.masked_key,
                key_status.index,
                backoff_seconds,
                self.active_count,
                self.total_count,
            )

        if account_wide and self.rate_limiter:
            self.rate_limiter.record_global_cooldown(backoff_seconds)

    def record_failure(self, key_status: NvidiaKeyStatus, error_msg: str) -> None:
        """Record general error."""
        with self._lock:
            key_status.in_flight_calls = max(0, key_status.in_flight_calls - 1)
            key_status.total_calls += 1
            key_status.last_error = error_msg


# Global default key pool instance
_GLOBAL_KEY_POOL = NvidiaKeyPool()


# ---------------------------------------------------------------------------
# Configuration & Result Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AIConfig:
    """Configuration for NVIDIA NIM AI extraction."""

    model: str = DEFAULT_NVIDIA_MODEL
    base_url: str = NVIDIA_BASE_URL
    key_pool: NvidiaKeyPool = field(default_factory=lambda: _GLOBAL_KEY_POOL)
    rate_limiter: NvidiaRateLimiter = field(default_factory=lambda: _GLOBAL_RATE_LIMITER)
    timeout: int = field(default_factory=get_default_timeout)
    max_retries: int = 3
    retry_delay: float = 2.0
    temperature: float = 0.1
    num_predict: int = 4096
    prompt_path: Path = field(default_factory=lambda: _DEFAULT_PROMPT_PATH)


@dataclass
class AIExtractionResult:
    """Result of an NVIDIA NIM AI extraction attempt."""

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
    """Parse JSON object from model response, handling fences, reasoning blocks, and formatting quirks."""
    text = raw.strip()

    # Strip reasoning blocks (e.g., DeepSeek-R1 <think>...</think>)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # Strip markdown fences ```json ... ```
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Find outermost { ... }
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


def parse_retry_after(error_str: str, headers: Optional[dict] = None) -> float:
    """Extract retry-after seconds from response headers or error messages."""
    if headers and "retry-after" in headers:
        try:
            return float(headers["retry-after"])
        except (ValueError, TypeError):
            pass

    # Regex parse "try again in X seconds" or "retry after X"
    m = re.search(r"(?:retry[- ]after|try again in|wait)\s*[:=]?\s*(\d+(?:\.\d+)?)", error_str, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 15.0


def list_nvidia_models(api_key: Optional[str] = None, base_url: str = NVIDIA_BASE_URL) -> list[str]:
    """Fetch active chat models available to the NVIDIA API key from integrate.api.nvidia.com."""
    key = (api_key or os.getenv("NVIDIA_API_KEY_1") or os.getenv("NVIDIA_API_KEY") or "").strip()
    if not key:
        return list(FALLBACK_NVIDIA_MODELS)
    try:
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=key, timeout=30.0, max_retries=0)
        models_resp = client.models.list()
        chat_models: list[str] = []
        for m in models_resp.data:
            mid = m.id.lower()
            if any(w in mid for w in ("embed", "clip", "whisper", "tts", "rerank", "guard")):
                continue
            chat_models.append(m.id)

        if chat_models:
            preferred = [
                "meta/llama-3.3-70b-instruct",
                "nvidia/llama-3.1-nemotron-70b-instruct",
                "deepseek-ai/deepseek-r1",
                "mistralai/mistral-large-2-instruct",
            ]
            ordered = [p for p in preferred if p in chat_models]
            for m in chat_models:
                if m not in ordered:
                    ordered.append(m)
            return ordered
    except Exception as exc:
        logger.warning("Could not list NVIDIA models: %s", exc)
    return list(FALLBACK_NVIDIA_MODELS)


def check_nvidia_available(
    pool: Optional[NvidiaKeyPool] = None,
    base_url: str = NVIDIA_BASE_URL,
) -> tuple[bool, str]:
    """Check whether at least one key in the pool is valid and reachable on NVIDIA NIM."""
    p = pool or _GLOBAL_KEY_POOL
    if p.total_count == 0:
        return False, "No NVIDIA API keys configured. Set NVIDIA_API_KEY_1, NVIDIA_API_KEY_2, NVIDIA_API_KEY_3 in .env."

    key_status = p.get_key_for_request()
    if not key_status:
        return False, "All NVIDIA API keys are currently cooling down under rate limits."

    t0 = time.monotonic()
    try:
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=key_status.key, timeout=30.0, max_retries=0)
        client.models.list()
        latency_ms = (time.monotonic() - t0) * 1000
        p.release_key(key_status)
        record_api_call_log(
            document_name="Connectivity Check (models.list)",
            model="system/models",
            key_status=key_status,
            status="SUCCESS",
            http_status=200,
            latency_ms=latency_ms,
        )
        return True, f"NVIDIA NIM connected ({p.active_count}/{p.total_count} keys active · max {p.rate_limiter.max_requests} RPM)"
    except Exception as exc:
        latency_ms = (time.monotonic() - t0) * 1000
        p.release_key(key_status)
        err_str = str(exc)
        err_type = type(exc).__name__
        is_auth = "401" in err_str or "AuthenticationError" in err_type
        is_timeout = "timeout" in err_str.lower() or "timed out" in err_str.lower() or "APITimeoutError" in err_type or "Timeout" in err_type
        http_code = 401 if is_auth else (504 if is_timeout else 500)
        status_name = "AUTH_ERROR" if is_auth else ("TIMEOUT" if is_timeout else "FAILED")
        record_api_call_log(
            document_name="Connectivity Check (models.list)",
            model="system/models",
            key_status=key_status,
            status=status_name,
            http_status=http_code,
            latency_ms=latency_ms,
            error_detail=err_str,
        )
        if is_auth:
            return False, f"Invalid NVIDIA key {key_status.masked_key}. Check build.nvidia.com/models"
        if is_timeout:
            return False, f"Connection timed out after 30s. NVIDIA NIM endpoint may be busy or slow."
        return False, f"Could not connect to NVIDIA NIM: {exc}"


def make_test_api_call(
    pool: Optional[NvidiaKeyPool] = None,
    model: Optional[str] = None,
    base_url: str = NVIDIA_BASE_URL,
) -> tuple[bool, str]:
    """
    Execute an on-demand test completion ping to NVIDIA NIM through the rate limiter and key pool,
    logging the exact call, latency, and status in the API call log.
    """
    p = pool or _GLOBAL_KEY_POOL
    m = model or DEFAULT_NVIDIA_MODEL

    if p.total_count == 0:
        return False, "No NVIDIA API keys configured."

    # Shared rate limit check
    if not p.rate_limiter.acquire(timeout=5.0):
        record_api_call_log(
            document_name="Ping Test",
            model=m,
            key_status=None,
            status="RATE_LIMITED",
            http_status=429,
            latency_ms=0.0,
            error_detail="Exceeded aggregate 40 RPM budget",
        )
        return False, "Rate limit exceeded (40 RPM budget)"

    key_status = p.get_key_for_request()
    if not key_status:
        record_api_call_log(
            document_name="Ping Test",
            model=m,
            key_status=None,
            status="RATE_LIMITED",
            http_status=429,
            latency_ms=0.0,
            error_detail="All keys currently cooling down",
        )
        return False, "All keys cooling down"

    t0 = time.monotonic()
    try:
        from openai import OpenAI

        client = OpenAI(base_url=base_url, api_key=key_status.key, timeout=45.0, max_retries=0)
        resp = client.chat.completions.create(
            model=m,
            messages=[
                {"role": "system", "content": "You are a test assistant. Reply with one word: pong."},
                {"role": "user", "content": "ping"},
            ],
            max_tokens=6,
            temperature=0.0,
        )
        latency_ms = (time.monotonic() - t0) * 1000
        p.record_success(key_status)
        p.release_key(key_status)
        reply = resp.choices[0].message.content.strip() if resp.choices else "OK"
        record_api_call_log(
            document_name="Ping Test",
            model=m,
            key_status=key_status,
            status="SUCCESS",
            http_status=200,
            latency_ms=latency_ms,
            error_detail=f"Response: {reply}",
        )
        return True, f"Success on Key #{key_status.index + 1} ({key_status.masked_key}) in {latency_ms:.0f}ms · Response: '{reply}'"
    except Exception as exc:
        latency_ms = (time.monotonic() - t0) * 1000
        p.release_key(key_status)
        err_str = str(exc)
        err_type = type(exc).__name__
        if "429" in err_str or "RateLimitError" in err_type:
            p.record_rate_limit(key_status, backoff_seconds=10.0)
            record_api_call_log(
                document_name="Ping Test",
                model=m,
                key_status=key_status,
                status="RATE_LIMITED",
                http_status=429,
                latency_ms=latency_ms,
                error_detail=err_str,
            )
            return False, f"HTTP 429 Rate Limited: {err_str}"
        elif "401" in err_str or "AuthenticationError" in err_type:
            key_status.is_active = False
            record_api_call_log(
                document_name="Ping Test",
                model=m,
                key_status=key_status,
                status="AUTH_ERROR",
                http_status=401,
                latency_ms=latency_ms,
                error_detail="Invalid API Key",
            )
            return False, f"HTTP 401 Auth Error: {err_str}"
        elif "timeout" in err_str.lower() or "timed out" in err_str.lower() or "APITimeoutError" in err_type or "Timeout" in err_type:
            record_api_call_log(
                document_name="Ping Test",
                model=m,
                key_status=key_status,
                status="TIMEOUT",
                http_status=504,
                latency_ms=latency_ms,
                error_detail=f"Ping timed out after 45s: {err_str}",
            )
            return False, f"Request timed out after 45s ({err_str})"
        else:
            p.record_failure(key_status, err_str)
            record_api_call_log(
                document_name="Ping Test",
                model=m,
                key_status=key_status,
                status="FAILED",
                http_status=500,
                latency_ms=latency_ms,
                error_detail=err_str,
            )
            return False, f"API Error: {err_str}"


# ---------------------------------------------------------------------------
# Main Extractor Class
# ---------------------------------------------------------------------------


class AIExtractor:
    """
    Manages prompt rendering, concurrency-safe shared rate limiting,
    multi-key NVIDIA NIM calls across 3 keys, 429 failover, and JSON parsing.
    """

    def __init__(
        self,
        config: Optional[AIConfig] = None,
        pool: Optional[NvidiaKeyPool] = None,
        default_model: Optional[str] = None,
    ) -> None:
        self.config = config or AIConfig()
        if pool:
            self.config.key_pool = pool
        if default_model:
            self.config.model = default_model
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
        return check_nvidia_available(self.config.key_pool, base_url=self.config.base_url)

    def extract(self, resume_text: str, filename: str = "") -> AIExtractionResult:
        """
        Extract candidate data using NVIDIA NIM with aggregate rate limiting and multi-key failover.
        Safe for concurrent invocation by multiple threads.
        """
        if not resume_text or not resume_text.strip():
            return AIExtractionResult(
                success=False,
                error="Empty resume text — skipping AI extraction.",
                model_used=self.config.model,
            )

        template = self._load_prompt()
        prompt = template.replace("{resume_text}", resume_text[:32000])

        start_time = time.monotonic()
        last_error = ""

        from openai import OpenAI

        for attempt in range(1, self.config.max_retries + 1):
            # 1. Acquire permit from shared rate limiter (max 40 RPM across all keys)
            limiter_timeout = max(90.0, float(self.config.timeout))
            permit_granted = self.config.rate_limiter.acquire(timeout=limiter_timeout)
            if not permit_granted:
                last_error = f"Rate limit wait timeout after {limiter_timeout:.0f}s (application exceeding 40 RPM budget)."
                logger.warning("[%s] %s", filename, last_error)
                time.sleep(self.config.retry_delay)
                continue

            # 2. Obtain key from pool
            key_status = self.config.key_pool.get_key_for_request()
            if not key_status:
                last_error = "No active NVIDIA keys available in pool (all cooling down)."
                time.sleep(self.config.retry_delay)
                continue

            try:
                client = OpenAI(
                    base_url=self.config.base_url,
                    api_key=key_status.key,
                    timeout=self.config.timeout,
                    max_retries=0,  # We manage retries and failover explicitly
                )

                system_msg = (
                    "You are a meticulous talent intelligence extraction AI. "
                    "Your objective is 100% extraction precision: never omit, truncate, or summarize "
                    "candidate contact details, work experience, responsibilities, education records, "
                    "projects, skills, or links. "
                    "Output must strictly adhere to the requested JSON schema without any markdown fences, thoughts, or commentary."
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
                    max_tokens=self.config.num_predict,
                )

                raw = completion.choices[0].message.content or ""
                duration = time.monotonic() - call_start

                parsed, parse_error = extract_json_from_response(raw)
                if parse_error:
                    self.config.key_pool.record_failure(key_status, parse_error)
                    record_api_call_log(
                        document_name=filename or "Resume Extraction",
                        model=self.config.model,
                        key_status=key_status,
                        status="PARSE_ERROR",
                        http_status=200,
                        latency_ms=duration * 1000,
                        error_detail=parse_error,
                    )
                    last_error = parse_error
                    continue

                # Successful extraction
                self.config.key_pool.record_success(key_status)
                record_api_call_log(
                    document_name=filename or "Resume Extraction",
                    model=self.config.model,
                    key_status=key_status,
                    status="SUCCESS",
                    http_status=200,
                    latency_ms=duration * 1000,
                )
                logger.info(
                    "[%s] NVIDIA NIM success on key %s (index %d) in %.2fs [Model: %s]",
                    filename,
                    key_status.masked_key,
                    key_status.index,
                    duration,
                    self.config.model,
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
                headers = getattr(exc, "response", None) and getattr(exc.response, "headers", None)
                elapsed_ms = (time.monotonic() - call_start) * 1000 if "call_start" in locals() else 0.0

                # HTTP 429 Rate Limit
                if "429" in err_str or "RateLimitError" in err_type:
                    wait_s = parse_retry_after(err_str, headers)
                    backoff = max(wait_s, 5.0 * (2 ** (attempt - 1)))
                    self.config.key_pool.record_rate_limit(key_status, backoff_seconds=backoff, account_wide=True)
                    record_api_call_log(
                        document_name=filename or "Resume Extraction",
                        model=self.config.model,
                        key_status=key_status,
                        status="RATE_LIMITED",
                        http_status=429,
                        latency_ms=elapsed_ms,
                        error_detail=f"Rate limit hit; rotating (cooldown {backoff:.1f}s)",
                    )
                    last_error = f"Rate limit on key {key_status.masked_key} (cooldown {backoff:.1f}s) — rotating"
                    logger.warning("[%s] %s", filename, last_error)
                    continue

                # HTTP 401 Auth Error
                if "401" in err_str or "AuthenticationError" in err_type:
                    key_status.is_active = False
                    self.config.key_pool.record_failure(key_status, "Invalid API Key")
                    record_api_call_log(
                        document_name=filename or "Resume Extraction",
                        model=self.config.model,
                        key_status=key_status,
                        status="AUTH_ERROR",
                        http_status=401,
                        latency_ms=elapsed_ms,
                        error_detail="Invalid API Key (HTTP 401)",
                    )
                    last_error = f"Invalid NVIDIA key {key_status.masked_key} disabled"
                    logger.error("[%s] %s", filename, last_error)
                    continue

                # Timeout handling (APITimeoutError, ReadTimeout, socket timeout)
                is_timeout = (
                    "timeout" in err_str.lower()
                    or "timed out" in err_str.lower()
                    or "APITimeoutError" in err_type
                    or "TimeoutException" in err_type
                    or "ReadTimeout" in err_type
                    or "Timeout" in err_type
                )
                if is_timeout:
                    self.config.key_pool.record_failure(key_status, f"Timeout after {self.config.timeout}s")
                    record_api_call_log(
                        document_name=filename or "Resume Extraction",
                        model=self.config.model,
                        key_status=key_status,
                        status="TIMEOUT",
                        http_status=504,
                        latency_ms=elapsed_ms,
                        error_detail=f"Request timed out after {self.config.timeout}s (attempt {attempt}/{self.config.max_retries})",
                    )
                    last_error = f"Request timed out after {self.config.timeout}s on key {key_status.masked_key}"
                    logger.warning(
                        "[%s] Timeout on key %s after %ds: %s (attempt %d/%d)",
                        filename,
                        key_status.masked_key,
                        self.config.timeout,
                        exc,
                        attempt,
                        self.config.max_retries,
                    )
                    time.sleep(self.config.retry_delay * attempt)
                    continue

                # Transient model error
                self.config.key_pool.record_failure(key_status, err_str)
                record_api_call_log(
                    document_name=filename or "Resume Extraction",
                    model=self.config.model,
                    key_status=key_status,
                    status="FAILED",
                    http_status=500,
                    latency_ms=elapsed_ms,
                    error_detail=err_str,
                )
                last_error = f"NVIDIA NIM error: {exc}"
                logger.warning("[%s] Transient error on key %s: %s", filename, key_status.masked_key, exc)
                time.sleep(self.config.retry_delay * attempt)

        return AIExtractionResult(
            success=False,
            error=f"Extraction failed after {self.config.max_retries} attempts: {last_error}",
            model_used=self.config.model,
            duration_s=time.monotonic() - start_time,
        )



