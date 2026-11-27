import base64
import json
import shutil
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

import agent.license_guard as lg
import agent.server as server

SAMPLE_DROP = Path(__file__).resolve().parent.parent / "drop-folder"


def _cert(key, tier="Trial", days=14):
    import time
    now = int(time.time())
    payload = {"v": 1, "licensee_id": "T-1", "licensee": "Test MSP", "tier": tier, "client_cap": None,
               "issued_at": now, "expires_at": now + days * 86400, "trial_reset_used": False}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    enc = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
    return f"{lg.HEADER}\n{enc(raw)}.{enc(key.sign(raw))}\n{lg.FOOTER}"


@pytest.fixture
def client(tmp_path, monkeypatch):
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(lg, "PUBLIC_KEY_B64", base64.b64encode(key.public_key().public_bytes_raw()).decode())
    drop = tmp_path / "drop"
    if SAMPLE_DROP.exists():
        shutil.copytree(SAMPLE_DROP, drop)
    else:
        drop.mkdir()
    monkeypatch.setattr(server, "DROP_DIR", str(drop))
    monkeypatch.setattr(server, "VAULT_DIR", str(tmp_path / "vault"))
    monkeypatch.setattr(server, "LICENSE_DIR", str(tmp_path / "vault"))
    return TestClient(server.app), key


def test_data_endpoints_locked_without_license(client):
    c, _ = client
    assert c.get("/api/dashboard-data").status_code == 402
    assert c.get("/api/cloud-payload").status_code == 402
    assert c.get("/api/license").json()["mode"] == "unlicensed"
    assert c.get("/").status_code == 200  # the page itself loads so the user can paste a certificate


def test_bad_certificate_rejected(client):
    c, _ = client
    r = c.post("/api/license", json={"certificate": "nonsense"})
    assert r.status_code == 400
    assert c.get("/api/dashboard-data").status_code == 402


def test_valid_trial_unlocks_dashboard(client):
    c, key = client
    r = c.post("/api/license", json={"certificate": _cert(key)})
    assert r.status_code == 200
    assert r.json()["mode"] == "trial"

    data = c.get("/api/dashboard-data")
    assert data.status_code == 200
    assert data.json()["license"]["days_remaining"] == 14
    assert c.get("/api/cloud-payload").status_code == 200


def test_server_binds_to_localhost_only():
    assert server.HOST == "127.0.0.1"
