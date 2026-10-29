"""
tests/test_nvidia_pool.py
=========================
Unit and concurrency tests for NvidiaKeyPool, NvidiaRateLimiter, and failover mechanics.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.ai_extractor import (
    DEFAULT_NVIDIA_MODEL,
    AIConfig,
    AIExtractor,
    NvidiaKeyPool,
    NvidiaKeyStatus,
    NvidiaRateLimiter,
    extract_json_from_response,
    parse_retry_after,
)


def test_key_status_masking():
    status = NvidiaKeyStatus(key="nvapi-1234567890abcdef", index=0)
    assert "nvapi-12" in status.masked_key
    assert "cdef" in status.masked_key
    assert "34567890ab" not in status.masked_key

    short = NvidiaKeyStatus(key="nvapi-123", index=1)
    assert short.masked_key == "nvapi-***"


def test_three_keys_initialization():
    keys = [
        "nvapi-key111111111111111111111111",
        "nvapi-key222222222222222222222222",
        "nvapi-key333333333333333333333333",
    ]
    pool = NvidiaKeyPool(keys)
    assert pool.total_count == 3
    assert pool.active_count == 3
    assert pool.keys[0].index == 0
    assert pool.keys[1].index == 1
    assert pool.keys[2].index == 2


def test_round_robin_distribution():
    keys = ["nvapi-k1", "nvapi-k2", "nvapi-k3"]
    pool = NvidiaKeyPool(keys)

    # Acquire and release in sequence
    k1 = pool.get_key_for_request()
    pool.release_key(k1)
    k2 = pool.get_key_for_request()
    pool.release_key(k2)
    k3 = pool.get_key_for_request()
    pool.release_key(k3)
    k4 = pool.get_key_for_request()
    pool.release_key(k4)

    assert k1.key == "nvapi-k1"
    assert k2.key == "nvapi-k2"
    assert k3.key == "nvapi-k3"
    assert k4.key == "nvapi-k1"  # Wrapped around cleanly


def test_concurrent_least_in_flight_balancing():
    keys = ["nvapi-k1", "nvapi-k2", "nvapi-k3"]
    pool = NvidiaKeyPool(keys)

    # Simulate 3 concurrent workers acquiring keys at the same time without releasing yet
    w1 = pool.get_key_for_request()
    w2 = pool.get_key_for_request()
    w3 = pool.get_key_for_request()

    # All three distinct keys must be used concurrently
    acquired_keys = {w1.key, w2.key, w3.key}
    assert acquired_keys == {"nvapi-k1", "nvapi-k2", "nvapi-k3"}
    assert w1.in_flight_calls == 1
    assert w2.in_flight_calls == 1
    assert w3.in_flight_calls == 1

    # Cleanup
    pool.release_key(w1)
    pool.release_key(w2)
    pool.release_key(w3)


def test_rate_limit_failover_and_cooldown():
    keys = ["nvapi-k1", "nvapi-k2", "nvapi-k3"]
    pool = NvidiaKeyPool(keys)

    k1 = pool.get_key_for_request()
    assert k1.key == "nvapi-k1"

    # Mark key 1 rate limited for 10 seconds
    pool.record_rate_limit(k1, backoff_seconds=10.0, account_wide=False)
    assert pool.active_count == 2
    assert not k1.is_available

    # Next request must bypass rate-limited key 1 and use key 2
    k2 = pool.get_key_for_request()
    assert k2.key == "nvapi-k2"
    pool.release_key(k2)


def test_rate_limiter_strict_limit_enforcement():
    # Test rate limiter with 5 requests max per minute
    limiter = NvidiaRateLimiter(max_requests_per_minute=5)
    limiter.reset()

    # Acquire 5 permits immediately
    for _ in range(5):
        assert limiter.acquire(timeout=0.1) is True

    # 6th permit must be blocked because 5 RPM is reached
    assert limiter.acquire(timeout=0.05) is False
    assert limiter.current_load_last_minute == 5


def test_rate_limiter_concurrency_under_load():
    """Ensure multi-threaded acquisitions never exceed rate limit."""
    limiter = NvidiaRateLimiter(max_requests_per_minute=10)
    limiter.reset()

    granted = []
    lock = threading.Lock()

    def worker():
        if limiter.acquire(timeout=0.05):
            with lock:
                granted.append(time.time())

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker) for _ in range(25)]
        for f in futures:
            f.result()

    # Exactly 10 requests must be granted under the 10-request capacity
    assert len(granted) == 10
    assert limiter.current_load_last_minute == 10


def test_retry_after_parser():
    assert parse_retry_after("Rate limit exceeded. Please retry after 12 seconds.") == 12.0
    assert parse_retry_after("Too many requests, try again in 4.5 seconds") == 4.5
    assert parse_retry_after("Error occurred", headers={"retry-after": "18"}) == 18.0
    assert parse_retry_after("Generic error with no delay") == 15.0


def test_json_extractor_handles_think_tags_and_fences():
    raw_with_think = (
        "<think>Analyzing resume text for candidate info...</think>\n"
        "```json\n"
        '{"full_name": "Alice Chen", "email": "alice@example.com"}\n'
        "```"
    )
    parsed, err = extract_json_from_response(raw_with_think)
    assert err == ""
    assert parsed["full_name"] == "Alice Chen"
    assert parsed["email"] == "alice@example.com"


def test_pool_empty_and_reload():
    pool = NvidiaKeyPool([])
    assert pool.total_count == 0
    assert pool.get_key_for_request() is None


def test_api_call_logging():
    from src.ai_extractor import (
        clear_api_call_logs,
        get_api_call_logs,
        record_api_call_log,
    )

    clear_api_call_logs()
    assert len(get_api_call_logs()) == 0

    key_stat = NvidiaKeyStatus(key="nvapi-test1234567890abcdef", index=0)
    record_api_call_log(
        document_name="candidate_resume.pdf",
        model="meta/llama-3.3-70b-instruct",
        key_status=key_stat,
        status="SUCCESS",
        http_status=200,
        latency_ms=1250.0,
    )

    logs = get_api_call_logs()
    assert len(logs) == 1
    assert logs[0].document_name == "candidate_resume.pdf"
    assert logs[0].status == "SUCCESS"
    assert logs[0].http_status == 200
    assert "Key #1" in logs[0].key_masked
    assert logs[0].latency_ms == 1250.0

    # Rate limited log entry
    record_api_call_log(
        document_name="second_resume.pdf",
        model="meta/llama-3.3-70b-instruct",
        key_status=key_stat,
        status="RATE_LIMITED",
        http_status=429,
        latency_ms=300.0,
        error_detail="HTTP 429 rate limit hit",
    )

    logs = get_api_call_logs()
    assert len(logs) == 2
    assert logs[0].status == "RATE_LIMITED"
    assert logs[0].http_status == 429
    assert "429 rate limit" in logs[0].error_detail

    clear_api_call_logs()
    assert len(get_api_call_logs()) == 0


def test_reload_all_three_keys_from_env(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY_1", "nvapi-key11111111111111111111")
    monkeypatch.setenv("NVIDIA_API_KEY_2", "nvapi-key22222222222222222222")
    monkeypatch.setenv("NVIDIA_API_KEY_3", "nvapi-key33333333333333333333")

    pool = NvidiaKeyPool()
    pool.reload_from_env()
    assert pool.total_count == 3
    assert pool.active_count == 3
    assert pool.keys[0].key == "nvapi-key11111111111111111111"
    assert pool.keys[1].key == "nvapi-key22222222222222222222"
    assert pool.keys[2].key == "nvapi-key33333333333333333333"


def test_ai_config_timeout_defaults_and_env(monkeypatch):
    from src.ai_extractor import AIConfig

    # Default timeout is 180s to prevent premature 500/504 timeouts on large models
    monkeypatch.delenv("NVIDIA_API_TIMEOUT", raising=False)
    monkeypatch.delenv("REQUEST_TIMEOUT", raising=False)
    cfg_default = AIConfig()
    assert cfg_default.timeout == 180

    # Respects NVIDIA_API_TIMEOUT
    monkeypatch.setenv("NVIDIA_API_TIMEOUT", "240")
    cfg_env = AIConfig()
    assert cfg_env.timeout == 240

    # Respects explicit argument
    cfg_explicit = AIConfig(timeout=300)
    assert cfg_explicit.timeout == 300


def test_api_call_logging_timeout():
    from src.ai_extractor import (
        clear_api_call_logs,
        get_api_call_logs,
        record_api_call_log,
        NvidiaKeyStatus,
    )

    clear_api_call_logs()
    key_stat = NvidiaKeyStatus(key="nvapi-test1234567890abcdef", index=0)
    record_api_call_log(
        document_name="large_resume.pdf",
        model="meta/llama-3.3-70b-instruct",
        key_status=key_stat,
        status="TIMEOUT",
        http_status=504,
        latency_ms=180120.0,
        error_detail="Request timed out after 180s",
    )

    logs = get_api_call_logs()
    assert len(logs) == 1
    assert logs[0].status == "TIMEOUT"
    assert logs[0].http_status == 504
    assert "Request timed out after 180s" in logs[0].error_detail
    clear_api_call_logs()

