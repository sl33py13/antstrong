"""antSTRONG offline licence verification (Ed25519 + Base64).

Every way of running antSTRONG, including the 14-day trial, needs a certificate
signed with the antSTRONG private key. The expiry lives inside the signed
payload, so deleting or editing local files cannot extend a trial.

Trial certificates are issued at download time (email capture on the website).
The one-time TRIAL-RESET certificate is the same thing with
trial_reset_used=true. The "2 windows maximum" rule is enforced by the issuer,
which keeps a ledger of who has been issued what. The client cannot enforce it.

Clock rollback (setting the PC date backwards) is caught two ways:
  1. now must not be earlier than the certificate's issued_at (minus a grace period).
  2. A local high-water mark of the latest time seen. Deleting that file only
     falls back to check 1, so it never gives more time than the signature allows.
"""

import base64
import hashlib
import json
import platform
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

PUBLIC_KEY_B64 = "REPLACE_WITH_YOUR_32_BYTE_ED25519_PUBLIC_KEY_B64="

HEADER = "-----BEGIN ANTSTRONG LICENSE-----"
FOOTER = "-----END ANTSTRONG LICENSE-----"
SUPPORTED_VERSIONS = {1}
CLOCK_GRACE_SECONDS = 24 * 60 * 60  # tolerate time zones and small clock drift


@dataclass
class LicenseStatus:
    valid: bool
    mode: str  # "licensed" | "trial" | "trial_reset" | "expired" | "unlicensed"
    tier: str
    licensee: str
    client_cap: int | None
    days_remaining: int
    reason: str = ""


def _invalid(reason: str, mode: str = "expired", tier: str = "None", licensee: str = "") -> LicenseStatus:
    return LicenseStatus(False, mode, tier, licensee, 0, 0, reason)


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def machine_fingerprint() -> str:
    """Stable, non-PII machine identifier (hashed). Used only when a certificate
    carries a machine_id, i.e. it was deliberately issued for one machine."""
    raw = ""
    try:
        if platform.system() == "Windows":
            import winreg  # type: ignore[import-not-found]

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                raw = winreg.QueryValueEx(key, "MachineGuid")[0]
        else:
            for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                if Path(p).exists():
                    raw = Path(p).read_text(encoding="utf-8").strip()
                    break
    except OSError:
        raw = ""
    if not raw:
        raw = platform.node()
    return hashlib.sha256(f"antstrong:{raw}".encode("utf-8")).hexdigest()[:32]


def verify_license_block(
    raw_text: str,
    now_ts: int | None = None,
    fingerprint: str | None = None,
) -> LicenseStatus:
    now = int(time.time()) if now_ts is None else now_ts
    lines = [
        line.strip()
        for line in raw_text.strip().splitlines()
        if line.strip() and line.strip() not in (HEADER, FOOTER)
    ]
    token = "".join(lines)

    if "." not in token:
        return _invalid("Malformed license block.")

    payload_b64, sig_b64 = token.split(".", 1)

    try:
        payload_bytes = _b64url_decode(payload_b64)
        sig_bytes = _b64url_decode(sig_b64)
        pub_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_B64))
        pub_key.verify(sig_bytes, payload_bytes)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (InvalidSignature, ValueError):
        return _invalid("Invalid cryptographic signature.")

    if not isinstance(payload, dict) or payload.get("v") not in SUPPORTED_VERSIONS:
        return _invalid("Unsupported license format.")

    tier = payload.get("tier", "Starter")
    licensee = payload.get("licensee", "Unknown")
    issued_at = int(payload.get("issued_at", 0))
    expires_at = int(payload.get("expires_at", 0))

    bound_to = payload.get("machine_id")
    if bound_to:
        actual = fingerprint if fingerprint is not None else machine_fingerprint()
        if bound_to != actual:
            return _invalid("License is registered to a different machine.", tier=tier, licensee=licensee)

    if now < issued_at - CLOCK_GRACE_SECONDS:
        return _invalid("System clock is earlier than the license issue date.", tier=tier, licensee=licensee)

    if now >= expires_at:
        return _invalid("License or trial window has expired.", tier=tier, licensee=licensee)

    days_left = max(1, -(-(expires_at - now) // 86400))  # round up: 13.2 days left shows 14
    if tier == "Trial":
        mode = "trial_reset" if payload.get("trial_reset_used") else "trial"
    else:
        mode = "licensed"

    return LicenseStatus(
        valid=True,
        mode=mode,
        tier=tier,
        licensee=licensee,
        client_cap=payload.get("client_cap"),
        days_remaining=days_left,
    )


class LicenseStore:
    """Persists the active certificate and the clock high-water mark locally.

    Files (inside the app data folder):
      license.txt  the pasted certificate block
      clock.json   {"last_seen_at": <unix ts>}
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.license_file = self.data_dir / "license.txt"
        self.clock_file = self.data_dir / "clock.json"

    def _last_seen(self) -> int:
        try:
            return int(json.loads(self.clock_file.read_text(encoding="utf-8"))["last_seen_at"])
        except (OSError, ValueError, KeyError, TypeError):
            return 0

    def _record_seen(self, now: int) -> None:
        if now > self._last_seen():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.clock_file.write_text(json.dumps({"last_seen_at": now}), encoding="utf-8")

    def status(self, now_ts: int | None = None, fingerprint: str | None = None) -> LicenseStatus:
        now = int(time.time()) if now_ts is None else now_ts
        if not self.license_file.exists():
            return _invalid(
                "No license installed. Paste your trial or license certificate in Settings -> License.",
                mode="unlicensed",
            )

        if now < self._last_seen() - CLOCK_GRACE_SECONDS:
            return _invalid("System clock has been moved backwards. Correct the date and restart.")

        status = verify_license_block(
            self.license_file.read_text(encoding="utf-8"), now_ts=now, fingerprint=fingerprint
        )
        self._record_seen(now)
        return status

    def install(self, raw_text: str, now_ts: int | None = None, fingerprint: str | None = None) -> LicenseStatus:
        """Validate a pasted certificate and save it only if it is valid."""
        now = int(time.time()) if now_ts is None else now_ts
        if now < self._last_seen() - CLOCK_GRACE_SECONDS:
            return _invalid("System clock has been moved backwards. Correct the date and restart.")

        status = verify_license_block(raw_text, now_ts=now, fingerprint=fingerprint)
        if status.valid:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.license_file.write_text(raw_text.strip() + "\n", encoding="utf-8")
            self._record_seen(now)
        return status
