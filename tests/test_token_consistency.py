from agent.ingest import process_drop_folder
from agent.vault import LocalKeyVault


def _write(path, text):
    path.write_text(text, encoding="utf-8")


def test_same_client_gets_one_token_across_files(tmp_path):
    drop = tmp_path / "drop"
    drop.mkdir()
    _write(drop / "companies.csv", "company_id,company_name,mrr,stack_cost\nC02,Bayside Logistics Pty Ltd,2400,680\n")
    _write(drop / "assets.csv", "asset_id,company_id,company_name,hostname,os_supported,patch_compliant,warranty_days_left\nA03,C02,Bayside Logistics,BAY-PC-14,false,false,-42\n")
    _write(drop / "tickets.csv", "ticket_id,company_id,company_name,tech_id,tech_name,summary,sla_met,status\nT1,C02,Bayside,U02,Maya Lin,VPN down,false,open\n")

    payload = process_drop_folder(str(drop), str(tmp_path / "vault"))
    tokens = {payload["companies"][0]["company_token"], payload["assets"][0]["company_token"], payload["tickets"][0]["company_token"]}
    assert len(tokens) == 1


def test_every_spelling_is_blocked_by_gate_and_vault_persists(tmp_path):
    drop = tmp_path / "drop"
    drop.mkdir()
    _write(drop / "companies.csv", "company_id,company_name,mrr,stack_cost\nC02,Bayside Logistics Pty Ltd,2400,680\n")
    _write(drop / "assets.csv", "asset_id,company_id,company_name,hostname,os_supported,patch_compliant,warranty_days_left\nA03,C02,Bayside Trading,BAY-PC-14,false,false,-42\n")
    process_drop_folder(str(drop), str(tmp_path / "vault"))

    reopened = LocalKeyVault(str(tmp_path / "vault"))
    assert "Bayside Logistics Pty Ltd" in reopened.get_rehydration_map().values()
    assert {"Bayside Logistics Pty Ltd", "Bayside Trading"} <= reopened.get_all_real_names()
