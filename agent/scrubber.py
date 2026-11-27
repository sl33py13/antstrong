import re
import json
from typing import Any


class PrivacyViolationError(Exception):
    pass


ROOT_CAUSE_RULES: list[tuple[str, re.Pattern]] = [
    ("CAUSE_MFA_AUTH", re.compile(r"\b(mfa|2fa|authenticator|password reset|locked out|sso|login)\b", re.I)),
    ("CAUSE_NETWORK_WAN", re.compile(r"\b(packet loss|latency|wan|isp|vpn|dns|dhcp|firewall|offline)\b", re.I)),
    ("CAUSE_EMAIL_M365", re.compile(r"\b(outlook|exchange|m365|365|mailbox|spam|phishing|teams)\b", re.I)),
    ("CAUSE_BACKUP_STORAGE", re.compile(r"\b(backup|veeam|datto|shadowprotect|nas|disk full|raid)\b", re.I)),
    ("CAUSE_HARDWARE_ENDPOINT", re.compile(r"\b(bsod|blue screen|battery|ups|printer|dock|laptop|overheating)\b", re.I)),
    ("CAUSE_PATCH_OS", re.compile(r"\b(windows update|patch|reboot|kb\d+|cve|vulnerability)\b", re.I)),
]

FORBIDDEN_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL_ADDRESS", re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")),
    ("IPV4_ADDRESS", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("PHONE_NUMBER", re.compile(r"(?:\+\d{1,3}[-.\s]?)?\(?\d{1,4}\)?[-.\s]\d{3,4}[-.\s]\d{3,4}")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
]

VALID_TOKEN_RE = re.compile(r"^(CL|TC|AS)_[0-9a-f]{10}$")


def extract_safe_tags(raw_note: str) -> list[str]:
    if not raw_note:
        return ["CAUSE_UNCLASSIFIED"]
    tags = [tag for tag, pattern in ROOT_CAUSE_RULES if pattern.search(raw_note)]
    return tags if tags else ["CAUSE_UNCLASSIFIED"]


def enforce_outbound_gate(payload: dict[str, Any], known_real_names: set[str]) -> str:
    serialized = json.dumps(payload)

    lowered_payload = serialized.lower()
    for real_name in known_real_names:
        cleaned = real_name.strip().lower()
        if len(cleaned) >= 3 and cleaned in lowered_payload:
            raise PrivacyViolationError(
                f"BLOCKED: Real entity name '{real_name}' detected in outbound payload!"
            )

    for rule_name, pattern in FORBIDDEN_PII_PATTERNS:
        match = pattern.search(serialized)
        if match:
            raise PrivacyViolationError(
                f"BLOCKED: Forbidden PII pattern ({rule_name}) detected: '{match.group(0)}'"
            )

    for section in ("companies", "tickets", "time_costs", "assets"):
        for record in payload.get(section, []):
            for token_field in ("company_token", "tech_token", "asset_token"):
                if token_field in record and record[token_field] is not None:
                    if not VALID_TOKEN_RE.match(record[token_field]):
                        raise PrivacyViolationError(
                            f"BLOCKED: Malformed or unmasked token in '{token_field}': {record[token_field]}"
                        )

    return serialized