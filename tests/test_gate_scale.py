import time

import pytest

from agent.scrubber import PrivacyViolationError, enforce_outbound_gate


def _payload(n):
    return {
        "companies": [{"company_token": f"CL_{i:010x}", "mrr": 1000.0} for i in range(n)],
        "tickets": [{"company_token": f"CL_{i:010x}", "tags": ["CAUSE_EMAIL_M365"], "status": "open"} for i in range(n)],
    }


def test_gate_is_fast_with_many_names():
    names = {f"Client Number {i} Pty Ltd" for i in range(50_000)} | {f"HOST-{i:06d}" for i in range(50_000)}
    t = time.perf_counter()
    enforce_outbound_gate(_payload(50_000), names)
    assert time.perf_counter() - t < 5


def test_gate_still_blocks_name_hidden_in_a_text_field():
    p = _payload(10)
    p["tickets"][3]["status"] = "escalated by harbour legal group"
    with pytest.raises(PrivacyViolationError):
        enforce_outbound_gate(p, {"Harbour Legal Group"})


def test_gate_blocks_name_used_as_a_key():
    p = _payload(2)
    p["notes"] = {"Bayside Logistics": 1}
    with pytest.raises(PrivacyViolationError):
        enforce_outbound_gate(p, {"Bayside Logistics"})


def test_short_hex_like_name_does_not_falsely_match_token():
    p = {"companies": [{"company_token": "CL_00abe00000", "mrr": 1.0}]}
    enforce_outbound_gate(p, {"Abe"})


def test_malformed_token_still_blocked():
    with pytest.raises(PrivacyViolationError):
        enforce_outbound_gate({"companies": [{"company_token": "Harbour Legal"}]}, set())


def test_card_number_smuggled_into_numeric_field_blocked():
    p = {"companies": [{"company_token": "CL_0000000001", "mrr": 4111111111111111}]}
    with pytest.raises(PrivacyViolationError):
        enforce_outbound_gate(p, set())


def test_email_and_ip_in_text_blocked():
    for bad in ("contact bob@example.com", "router 203.0.113.45"):
        with pytest.raises(PrivacyViolationError):
            enforce_outbound_gate({"tickets": [{"status": bad}]}, set())
