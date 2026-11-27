import argparse
import base64
import json
import time
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HEADER = "-----BEGIN ANTSTRONG LICENSE-----"
FOOTER = "-----END ANTSTRONG LICENSE-----"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_keypair(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()

    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    (out_dir / "antstrong_ed25519_private.pem").write_bytes(priv_bytes)
    print("Public key (Base64 for PUBLIC_KEY_B64):")
    print(base64.b64encode(pub_raw).decode("ascii"))
    print(f"Private key saved to: {out_dir / 'antstrong_ed25519_private.pem'}")


def sign_certificate(
    private_key_path: Path,
    licensee_id: str,
    licensee: str,
    tier: str,
    client_cap: int | None,
    days_valid: int,
    trial_reset_used: bool,
    machine_id: str | None = None,
) -> str:
    priv = serialization.load_pem_private_key(private_key_path.read_bytes(), password=None)
    now = int(time.time())
    payload = {
        "v": 1,
        "licensee_id": licensee_id,
        "licensee": licensee,
        "tier": tier,
        "client_cap": client_cap,
        "issued_at": now,
        "expires_at": now + (days_valid * 86400),
        "trial_reset_used": trial_reset_used,
    }
    if machine_id:
        payload["machine_id"] = machine_id
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig_bytes = priv.sign(payload_bytes)
    token = f"{_b64url_encode(payload_bytes)}.{_b64url_encode(sig_bytes)}"
    wrapped = "\n".join(token[i : i + 76] for i in range(0, len(token), 76))
    return f"{HEADER}\n{wrapped}\n{FOOTER}"


def main() -> None:
    parser = argparse.ArgumentParser(description="antSTRONG Ed25519 License Tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("keygen")
    gen.add_argument("--out", type=Path, default=Path("./keys"))

    sign = sub.add_parser("sign")
    sign.add_argument("--key", type=Path, required=True)
    sign.add_argument("--id", required=True)
    sign.add_argument("--licensee", required=True)
    sign.add_argument("--tier", required=True)
    sign.add_argument("--cap", type=int, default=None)
    sign.add_argument("--days", type=int, default=365)
    sign.add_argument("--reset-used", action="store_true")
    sign.add_argument("--machine-id", default=None, help="Optional: bind to one machine's fingerprint")

    trial = sub.add_parser("trial", help="Issue a 14-day Trial certificate")
    trial.add_argument("--key", type=Path, required=True)
    trial.add_argument("--id", required=True)
    trial.add_argument("--licensee", required=True)
    trial.add_argument("--reset", action="store_true", help="One-time TRIAL-RESET (check the ledger first)")

    args = parser.parse_args()
    if args.cmd == "keygen":
        generate_keypair(args.out)
    elif args.cmd == "sign":
        print(
            sign_certificate(
                private_key_path=args.key,
                licensee_id=args.id,
                licensee=args.licensee,
                tier=args.tier,
                client_cap=args.cap,
                days_valid=args.days,
                trial_reset_used=args.reset_used,
                machine_id=args.machine_id,
            )
        )
    elif args.cmd == "trial":
        print(
            sign_certificate(
                private_key_path=args.key,
                licensee_id=args.id,
                licensee=args.licensee,
                tier="Trial",
                client_cap=None,
                days_valid=14,
                trial_reset_used=args.reset,
            )
        )


if __name__ == "__main__":
    main()
