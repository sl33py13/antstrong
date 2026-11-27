import csv
from pathlib import Path
from agent.ingest import process_drop_folder


def _write_csv(path: Path, headers: list[str], rows: list[list]):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def test_process_drop_folder_tokenises_and_scrubs_all_tables(tmp_path):
    drop_dir = tmp_path / "drop"
    drop_dir.mkdir()
    vault_dir = tmp_path / "vault"

    _write_csv(
        drop_dir / "companies.csv",
        ["company_id", "company_name", "mrr", "stack_cost"],
        [
            ["C01", "Harbour Legal Group", "5000.00", "1100.00"],
            ["C02", "Bayside Logistics", "2400.00", "600.00"],
        ],
    )
    _write_csv(
        drop_dir / "tickets.csv",
        ["ticket_id", "company_id", "company_name", "tech_id", "tech_name", "summary", "sla_met", "status"],
        [
            ["T100", "C01", "Harbour Legal Group", "U1", "Liam Vance", "VPN down at 192.168.1.10", "true", "closed"],
            ["T101", "C02", "Bayside Logistics", "U2", "Maya Lin", "Backup failed on NAS", "false", "open"],
        ],
    )
    _write_csv(
        drop_dir / "time_costs.csv",
        ["entry_id", "company_id", "company_name", "tech_id", "tech_name", "hours", "hourly_cost", "billable"],
        [
            ["E01", "C01", "Harbour Legal Group", "U1", "Liam Vance", "12.5", "65.00", "true"],
            ["E02", "C02", "Bayside Logistics", "U2", "Maya Lin", "22.0", "60.00", "false"],
        ],
    )
    _write_csv(
        drop_dir / "assets.csv",
        ["asset_id", "company_id", "company_name", "hostname", "os_supported", "patch_compliant", "warranty_days_left"],
        [
            ["A01", "C01", "Harbour Legal Group", "HLG-SRV-01", "true", "true", "420"],
            ["A02", "C02", "Bayside Logistics", "BAY-PC-14", "false", "false", "-15"],
        ],
    )

    payload = process_drop_folder(drop_dir=str(drop_dir), vault_dir=str(vault_dir))
    raw_dump = str(payload)

    for forbidden in ["Harbour Legal Group", "Bayside Logistics", "Liam Vance", "Maya Lin", "HLG-SRV-01", "BAY-PC-14", "192.168.1.10"]:
        assert forbidden not in raw_dump

    assert len(payload["companies"]) == 2
    assert len(payload["tickets"]) == 2
    assert len(payload["time_costs"]) == 2
    assert len(payload["assets"]) == 2
    assert payload["tickets"][0]["tags"] == ["CAUSE_NETWORK_WAN"]


def test_deterministic_tokens_across_repeated_ingestions(tmp_path):
    drop_dir = tmp_path / "drop"
    drop_dir.mkdir()
    vault_dir = tmp_path / "vault"

    _write_csv(
        drop_dir / "companies.csv",
        ["company_id", "company_name", "mrr", "stack_cost"],
        [["C01", "Harbour Legal Group", "5000", "1100"]],
    )

    first_run = process_drop_folder(drop_dir=str(drop_dir), vault_dir=str(vault_dir))
    second_run = process_drop_folder(drop_dir=str(drop_dir), vault_dir=str(vault_dir))

    assert first_run["companies"][0]["company_token"] == second_run["companies"][0]["company_token"]
