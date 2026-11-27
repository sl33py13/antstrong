import pytest
from agent.vault import LocalKeyVault
from agent.scrubber import extract_safe_tags, enforce_outbound_gate, PrivacyViolationError


def test_tokenisation_and_clean_payload_passes(tmp_path):
    vault = LocalKeyVault(vault_dir=str(tmp_path))
    c_tok = vault.tokenise("companies", "101", "Acme Dental Pty Ltd")
    t_tok = vault.tokenise("technicians", "7", "Sarah Connor")
    vault.save()

    assert c_tok.startswith("CL_")
    assert t_tok.startswith("TC_")
    assert "Acme" not in c_tok

    tags = extract_safe_tags("User locked out of M365 Outlook after password reset")
    assert "CAUSE_MFA_AUTH" in tags
    assert "CAUSE_EMAIL_M365" in tags

    safe_payload = {
        "companies": [{"company_token": c_tok, "mrr": 4500.00, "stack_cost": 920.00}],
        "tickets": [{"company_token": c_tok, "tech_token": t_tok, "tags": tags, "sla_met": True}],
    }

    known_names = set(vault.get_rehydration_map().values())
    approved_json = enforce_outbound_gate(safe_payload, known_names)
    assert "Acme Dental" not in approved_json
    assert "Sarah Connor" not in approved_json


def test_poison_pill_blocks_leaked_real_name(tmp_path):
    vault = LocalKeyVault(vault_dir=str(tmp_path))
    c_tok = vault.tokenise("companies", "101", "Acme Dental Pty Ltd")
    known_names = set(vault.get_rehydration_map().values())

    leaked_payload = {
        "companies": [{"company_token": c_tok, "notes": "Call Acme Dental Pty Ltd urgently"}]
    }

    with pytest.raises(PrivacyViolationError, match="Real entity name"):
        enforce_outbound_gate(leaked_payload, known_names)


def test_poison_pill_blocks_email_and_ip(tmp_path):
    vault = LocalKeyVault(vault_dir=str(tmp_path))
    c_tok = vault.tokenise("companies", "101", "Acme Dental Pty Ltd")
    known_names = set(vault.get_rehydration_map().values())

    for bad_value in ["john.doe@acmedental.com.au", "192.168.14.22", "+61 2 6123 4567"]:
        leaked_payload = {
            "tickets": [{"company_token": c_tok, "leaked_field": bad_value}]
        }
        with pytest.raises(PrivacyViolationError):
            enforce_outbound_gate(leaked_payload, known_names)


def test_raw_note_with_pii_produces_only_safe_tags():
    dirty_note = (
        "Client John Smith at Acme Dental (john@acme.com, 10.0.0.55) called about "
        "Outlook crashing and Windows Update reboot loop."
    )
    tags = extract_safe_tags(dirty_note)
    assert tags == ["CAUSE_EMAIL_M365", "CAUSE_PATCH_OS"]
    for tag in tags:
        assert tag.startswith("CAUSE_")
        assert "john" not in tag.lower()
        assert "acme" not in tag.lower()


def test_poison_pill_blocks_unmasked_or_malformed_token(tmp_path):
    vault = LocalKeyVault(vault_dir=str(tmp_path))
    known_names = set(vault.get_rehydration_map().values())

    bad_payload = {
        "tickets": [{"company_token": "ACME_101", "tech_token": "TC_1234567890", "sla_met": True}]
    }
    with pytest.raises(PrivacyViolationError, match="Malformed or unmasked token"):
        enforce_outbound_gate(bad_payload, known_names)
