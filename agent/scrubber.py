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


# All rules folded into one pattern so each note is scanned once, not once per rule.
_COMBINED_CAUSE_RE = re.compile(
    "|".join(f"(?P<{tag}>{pattern.pattern})" for tag, pattern in ROOT_CAUSE_RULES), re.I
)
_RULE_ORDER = [tag for tag, _ in ROOT_CAUSE_RULES]


def extract_safe_tags(raw_note: str) -> list[str]:
    if not raw_note:
        return ["CAUSE_UNCLASSIFIED"]
    found = {m.lastgroup for m in _COMBINED_CAUSE_RE.finditer(raw_note)}
    tags = [tag for tag in _RULE_ORDER if tag in found]
    return tags if tags else ["CAUSE_UNCLASSIFIED"]


def _collect_values(obj: Any) -> tuple[set[str], set[str]]:
    """Walk the payload once. Returns (every distinct string: keys and string values,
    every distinct number large enough to hold a card or phone number, as text)."""
    strings: set[str] = set()
    big_numbers: set[str] = set()

    def visit(v: Any) -> None:
        if isinstance(v, str):
            strings.add(v)
        elif isinstance(v, bool) or v is None:
            pass
        elif isinstance(v, (int, float)):
            if abs(v) >= 1e9:
                big_numbers.add(json.dumps(v))
        elif isinstance(v, (dict, list, tuple)):
            stack.append(v)

    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                strings.add(str(k))
                visit(v)
        elif isinstance(cur, (list, tuple)):
            for v in cur:
                visit(v)
        else:
            visit(cur)
    return strings, big_numbers


def _find_real_name(text: str, names: set[str], min_len: int, max_len: int) -> str | None:
    """Return a known real name that appears inside text (case-insensitive), if any."""
    t = text.lower()
    n = len(t)
    for i in range(n - min_len + 1):
        for j in range(i + min_len, min(n, i + max_len) + 1):
            if t[i:j] in names:
                return t[i:j]
    return None


def enforce_outbound_gate(payload: dict[str, Any], known_real_names: set[str]) -> str:
    serialized = json.dumps(payload)

    # 1. Every token field must be a well-formed token.
    for section in ("companies", "tickets", "time_costs", "assets"):
        for record in payload.get(section, []):
            for token_field in ("company_token", "tech_token", "asset_token"):
                if token_field in record and record[token_field] is not None:
                    if not VALID_TOKEN_RE.match(record[token_field]):
                        raise PrivacyViolationError(
                            f"BLOCKED: Malformed or unmasked token in '{token_field}': {record[token_field]}"
                        )

    strings, big_numbers = _collect_values(payload)
    # A validated token is HMAC output: it cannot carry a name or PII, and skipping it
    # stops short names like "Abe" falsely matching hex digits inside a token.
    texts = [t for t in strings if not VALID_TOKEN_RE.match(t)]

    # 2. No known real name may appear in any text in the payload. Each distinct
    #    string is checked once against a set of names, so the cost grows with the
    #    payload, not payload x number of names.
    names = {n.strip().lower() for n in known_real_names if len(n.strip()) >= 3}
    if names:
        min_len = min(len(n) for n in names)
        max_len = max(len(n) for n in names)
        for text in texts:
            hit = _find_real_name(text, names, min_len, max_len)
            if hit:
                raise PrivacyViolationError(
                    f"BLOCKED: Real entity name '{hit}' detected in outbound payload!"
                )

    # 3. No PII-shaped values. Checked on every distinct text, plus any number
    #    big enough to be a card or phone number (smaller numbers cannot match).
    for value in [*texts, *big_numbers]:
        for rule_name, pattern in FORBIDDEN_PII_PATTERNS:
            match = pattern.search(value)
            if match:
                raise PrivacyViolationError(
                    f"BLOCKED: Forbidden PII pattern ({rule_name}) detected: '{match.group(0)}'"
                )

    return serialized
