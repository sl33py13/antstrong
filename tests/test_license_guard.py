import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import agent.license_guard as lg

NOW = 1_800_000_000
DAY = 86400


@pytest.fixture
def priv(monkeypatch) -> Ed25519PrivateKey:
    key = Ed25519PrivateKey.generate()
    pub_raw = key.public_key().public_bytes_raw()
    monkeypatch.setattr(lg, "PUBLIC_KEY_B64", base64.b64encode(pub_raw).decode("ascii"))
    return key


def _encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _make_signed_block(
    priv: Ed25519PrivateKey,
    expires_at: int,
    tier: str = "Growth",
    trial_reset_used: bool = False,
    issued_at: int | None = None,
    **extra,
) -> str:
    payload = {
        "v": 1,
        "licensee_id": "LIC-001",
        "licensee": "Test MSP",
        "tier": tier,
        "client_cap": 50,
        "issued_at": issued_at if issued_at is not None else min(NOW, expires_at - DAY),
        "expires_at": expires_at,
        "trial_reset_used": trial_reset_used,
        **extra,
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = priv.sign(raw)
    return f"{lg.HEADER}\n{_encode(raw)}.{_encode(sig)}\n{lg.FOOTER}"


def _payload_and_sig(block: str) -> tuple[dict, str]:
    token = "".join(l for l in block.splitlines() if l not in (lg.HEADER, lg.FOOTER))
    p_b64, s_b64 = token.split(".", 1)
    return json.loads(lg._b64url_decode(p_b64)), s_b64


# --- signature and expiry -------------------------------------------------

def test_valid_and_expired_license(priv):
    status = lg.verify_license_block(_make_signed_block(priv, expires_at=NOW + 30 * DAY), now_ts=NOW)
    assert status.valid is True
    assert status.mode == "licensed"
    assert status.client_cap == 50
    assert status.days_remaining == 30

    exp = lg.verify_license_block(_make_signed_block(priv, expires_at=NOW - 10), now_ts=NOW)
    assert exp.valid is False
    assert exp.mode == "expired"


def test_tampered_license_rejected(priv):
    # The old test did block.replace("Growth", "Scale") on Base64 text, which
    # never matched, so nothing was tampered. Edit the decoded payload instead.
    block = _make_signed_block(priv, expires_at=NOW + 30 * DAY)
    payload, sig = _payload_and_sig(block)
    payload["tier"] = "Scale"
    payload["client_cap"] = None
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    tampered = f"{lg.HEADER}\n{_encode(raw)}.{sig}\n{lg.FOOTER}"
    assert lg.verify_license_block(tampered, now_ts=NOW).valid is False


def test_extended_expiry_rejected(priv):
    block = _make_signed_block(priv, expires_at=NOW + 2 * DAY, tier="Trial")
    payload, sig = _payload_and_sig(block)
    payload["expires_at"] = NOW + 3650 * DAY
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert lg.verify_license_block(f"{_encode(raw)}.{sig}", now_ts=NOW).valid is False


def test_wrong_signing_key_rejected(priv):
    other = Ed25519PrivateKey.generate()
    block = _make_signed_block(other, expires_at=NOW + 30 * DAY)
    assert lg.verify_license_block(block, now_ts=NOW).valid is False


@pytest.mark.parametrize("junk", ["", "hello", "abc.def", "!!!.???", f"{lg.HEADER}\n{lg.FOOTER}"])
def test_garbage_rejected(priv, junk):
    assert lg.verify_license_block(junk, now_ts=NOW).valid is False


def test_now_ts_zero_is_respected(priv):
    # Old code used `now_ts or time.time()`, so 0 silently became "now".
    block = _make_signed_block(priv, expires_at=100, issued_at=0)
    assert lg.verify_license_block(block, now_ts=0).valid is True


# --- trials ----------------------------------------------------------------

def test_signed_trial_and_trial_reset_modes(priv):
    trial = _make_signed_block(priv, expires_at=NOW + 14 * DAY, tier="Trial", issued_at=NOW)
    s = lg.verify_license_block(trial, now_ts=NOW)
    assert (s.valid, s.mode, s.days_remaining) == (True, "trial", 14)

    reset = _make_signed_block(priv, expires_at=NOW + 14 * DAY, tier="Trial", issued_at=NOW, trial_reset_used=True)
    assert lg.verify_license_block(reset, now_ts=NOW).mode == "trial_reset"


def test_paid_license_with_reset_flag_is_still_licensed(priv):
    block = _make_signed_block(priv, expires_at=NOW + 365 * DAY, tier="Growth", trial_reset_used=True)
    assert lg.verify_license_block(block, now_ts=NOW).mode == "licensed"


def test_no_certificate_means_unlicensed(tmp_path: Path, priv):
    s = lg.LicenseStore(tmp_path).status(now_ts=NOW)
    assert s.valid is False
    assert s.mode == "unlicensed"


def test_deleting_local_files_does_not_restart_trial(tmp_path: Path, priv):
    """The bug being fixed: trial start used to live in an unsigned local file."""
    store = lg.LicenseStore(tmp_path)
    cert = _make_signed_block(priv, expires_at=NOW + 14 * DAY, tier="Trial", issued_at=NOW)
    assert store.install(cert, now_ts=NOW).valid is True

    day_15 = NOW + 15 * DAY
    assert store.status(now_ts=day_15).valid is False

    # User deletes everything and reinstalls the same certificate.
    for f in tmp_path.iterdir():
        f.unlink()
    assert store.install(cert, now_ts=day_15).valid is False
    assert store.status(now_ts=day_15).mode == "unlicensed"


def test_invalid_certificate_is_not_saved(tmp_path: Path, priv):
    store = lg.LicenseStore(tmp_path)
    assert store.install("not a licence", now_ts=NOW).valid is False
    assert not store.license_file.exists()


# --- clock rollback --------------------------------------------------------

def test_clock_before_issue_date_rejected(priv):
    block = _make_signed_block(priv, expires_at=NOW + 14 * DAY, tier="Trial", issued_at=NOW)
    assert lg.verify_license_block(block, now_ts=NOW - 2 * DAY).valid is False
    # Small drift (time zones) is tolerated.
    assert lg.verify_license_block(block, now_ts=NOW - 3600).valid is True


def test_clock_rollback_detected_by_high_water_mark(tmp_path: Path, priv):
    store = lg.LicenseStore(tmp_path)
    cert = _make_signed_block(priv, expires_at=NOW + 14 * DAY, tier="Trial", issued_at=NOW)
    store.install(cert, now_ts=NOW)
    assert store.status(now_ts=NOW + 13 * DAY).valid is True

    rolled_back = store.status(now_ts=NOW + 5 * DAY)
    assert rolled_back.valid is False
    assert "backwards" in rolled_back.reason


# --- optional machine binding ----------------------------------------------

def test_machine_bound_license(priv):
    block = _make_signed_block(priv, expires_at=NOW + 365 * DAY, machine_id="abc123")
    assert lg.verify_license_block(block, now_ts=NOW, fingerprint="abc123").valid is True
    other = lg.verify_license_block(block, now_ts=NOW, fingerprint="zzz999")
    assert other.valid is False
    assert "different machine" in other.reason


def test_machine_fingerprint_is_stable_and_hashed():
    a, b = lg.machine_fingerprint(), lg.machine_fingerprint()
    assert a == b and len(a) == 32


# --- issuing tool round trip -----------------------------------------------

def test_generate_license_tool_round_trip(tmp_path: Path, monkeypatch, capsys):
    from tools import generate_license as gl

    gl.generate_keypair(tmp_path)
    pub_b64 = capsys.readouterr().out.splitlines()[1].strip()
    monkeypatch.setattr(lg, "PUBLIC_KEY_B64", pub_b64)

    key = tmp_path / "antstrong_ed25519_private.pem"
    trial = gl.sign_certificate(key, "TRIAL-001", "Acme MSP", "Trial", None, 14, False)
    s = lg.verify_license_block(trial)
    assert (s.valid, s.mode, s.days_remaining) == (True, "trial", 14)

    paid = gl.sign_certificate(key, "LIC-002", "Acme MSP", "Scale", None, 365, False)
    assert lg.verify_license_block(paid).mode == "licensed"
