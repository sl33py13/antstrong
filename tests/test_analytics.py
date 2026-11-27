from agent.analytics import compute_kpis


def test_compute_kpis_profitability_compliance_and_fleet():
    tokenized_payload = {
        "companies": [
            {"company_token": "CL_aaaaaaaaaa", "mrr": 5000.0, "stack_cost": 1000.0},
            {"company_token": "CL_bbbbbbbbbb", "mrr": 2000.0, "stack_cost": 800.0},
        ],
        "time_costs": [
            {"company_token": "CL_aaaaaaaaaa", "tech_token": "TC_1111111111", "hours": 10.0, "hourly_cost": 60.0, "billable": True},
            {"company_token": "CL_bbbbbbbbbb", "tech_token": "TC_1111111111", "hours": 25.0, "hourly_cost": 60.0, "billable": False},
        ],
        "tickets": [
            {"company_token": "CL_aaaaaaaaaa", "tech_token": "TC_1111111111", "tags": ["CAUSE_EMAIL_M365"], "sla_met": True, "status": "closed"},
            {"company_token": "CL_bbbbbbbbbb", "tech_token": "TC_1111111111", "tags": ["CAUSE_NETWORK_WAN"], "sla_met": False, "status": "open"},
        ],
        "assets": [
            {"company_token": "CL_aaaaaaaaaa", "asset_token": "AS_1111111111", "os_supported": True, "patch_compliant": True, "warranty_days_left": 300},
            {"company_token": "CL_bbbbbbbbbb", "asset_token": "AS_2222222222", "os_supported": False, "patch_compliant": False, "warranty_days_left": -10},
        ],
    }

    report = compute_kpis(tokenized_payload)

    assert report["summary"]["total_mrr"] == 7000.0
    assert report["summary"]["total_net_profit"] == 3100.0
    assert report["summary"]["sla_adherence_pct"] == 50.0
    assert report["summary"]["patch_compliance_pct"] == 50.0
    assert report["summary"]["out_of_warranty_count"] == 1

    clients = {c["company_token"]: c for c in report["client_profitability"]}
    assert clients["CL_aaaaaaaaaa"]["net_profit"] == 3400.0
    assert clients["CL_aaaaaaaaaa"]["margin_pct"] == 68.0
    assert clients["CL_aaaaaaaaaa"]["effective_hourly_rate"] == 500.0

    assert clients["CL_bbbbbbbbbb"]["net_profit"] == -300.0
    assert clients["CL_bbbbbbbbbb"]["margin_pct"] == -15.0
    assert clients["CL_bbbbbbbbbb"]["effective_hourly_rate"] == 80.0


def test_compute_kpis_handles_zero_hours_and_empty_tables():
    payload = {
        "companies": [{"company_token": "CL_aaaaaaaaaa", "mrr": 3000.0, "stack_cost": 500.0}],
        "time_costs": [],
        "tickets": [],
        "assets": [],
    }
    report = compute_kpis(payload)
    client = report["client_profitability"][0]

    assert client["net_profit"] == 2500.0
    assert client["effective_hourly_rate"] is None
    assert report["summary"]["sla_adherence_pct"] == 100.0
    assert report["summary"]["patch_compliance_pct"] == 100.0
