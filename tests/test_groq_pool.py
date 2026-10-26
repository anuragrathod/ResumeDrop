"""Unit tests for GroqKeyPool multi-key rotation and rate-limit handling."""
import time
from src.ai_extractor import GroqKeyPool, GroqKeyStatus


def test_key_pool_initialization():
    keys = ["gsk_key11111111", "gsk_key22222222", "gsk_key33333333"]
    pool = GroqKeyPool(keys)
    assert pool.total_count == 3
    assert pool.active_count == 3


def test_key_pool_round_robin():
    keys = ["gsk_key1", "gsk_key2", "gsk_key3"]
    pool = GroqKeyPool(keys)

    k1 = pool.get_key_for_request()
    k2 = pool.get_key_for_request()
    k3 = pool.get_key_for_request()
    k4 = pool.get_key_for_request()

    assert k1.key == "gsk_key1"
    assert k2.key == "gsk_key2"
    assert k3.key == "gsk_key3"
    assert k4.key == "gsk_key1"  # wrapped around


def test_key_pool_rate_limit_failover():
    keys = ["gsk_key1", "gsk_key2"]
    pool = GroqKeyPool(keys)

    k1 = pool.get_key_for_request()
    assert k1.key == "gsk_key1"

    # Mark key 1 rate limited
    pool.record_rate_limit(k1, backoff_seconds=10.0)
    assert pool.active_count == 1

    # Next request must bypass rate-limited key 1 and use key 2
    next_k = pool.get_key_for_request()
    assert next_k.key == "gsk_key2"
