import csv
import os
from typing import Any
from agent.vault import LocalKeyVault
from agent.scrubber import extract_safe_tags, enforce_outbound_gate


def _parse_bool(val: str) -> bool:
    return str(val).strip().lower() in ('true', '1', 'yes', 'y')


def _read_csv(path: str) -> list[dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, mode='r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def process_drop_folder(
    drop_dir: str = 'drop-folder',
    vault_dir: str = '.antstrong_vault',
) -> dict[str, Any]:
    vault = LocalKeyVault(vault_dir=vault_dir)

    companies_out = []
    for row in _read_csv(os.path.join(drop_dir, 'companies.csv')):
        c_tok = vault.tokenise('companies', row['company_id'], row['company_name'])
        companies_out.append({
            'company_token': c_tok,
            'mrr': float(row.get('mrr', 0.0)),
            'stack_cost': float(row.get('stack_cost', 0.0)),
        })

    tickets_out = []
    for row in _read_csv(os.path.join(drop_dir, 'tickets.csv')):
        c_tok = vault.tokenise('companies', row['company_id'], row.get('company_name', ''))
        t_tok = vault.tokenise('technicians', row['tech_id'], row.get('tech_name', ''))
        safe_tags = extract_safe_tags(row.get('summary', ''))
        tickets_out.append({
            'company_token': c_tok,
            'tech_token': t_tok,
            'tags': safe_tags,
            'root_cause_tags': safe_tags,
            'sla_met': _parse_bool(row.get('sla_met', 'false')),
            'status': row.get('status', 'open').strip().lower(),
        })

    time_costs_out = []
    for row in _read_csv(os.path.join(drop_dir, 'time_costs.csv')):
        c_tok = vault.tokenise('companies', row['company_id'], row.get('company_name', ''))
        t_tok = vault.tokenise('technicians', row['tech_id'], row.get('tech_name', ''))
        time_costs_out.append({
            'company_token': c_tok,
            'tech_token': t_tok,
            'hours': float(row.get('hours', 0.0)),
            'hourly_cost': float(row.get('hourly_cost', 0.0)),
            'billable': _parse_bool(row.get('billable', 'true')),
        })

    assets_out = []
    for row in _read_csv(os.path.join(drop_dir, 'assets.csv')):
        c_tok = vault.tokenise('companies', row['company_id'], row.get('company_name', ''))
        a_tok = vault.tokenise('assets', row['asset_id'], row.get('hostname', ''))
        assets_out.append({
            'company_token': c_tok,
            'asset_token': a_tok,
            'os_supported': _parse_bool(row.get('os_supported', 'true')),
            'patch_compliant': _parse_bool(row.get('patch_compliant', 'true')),
            'warranty_days_left': int(row.get('warranty_days_left', 0)),
        })

    payload = {
        'companies': companies_out,
        'tickets': tickets_out,
        'time_costs': time_costs_out,
        'assets': assets_out,
    }

    vault.save()
    known_real_names = vault.get_all_real_names()
    enforce_outbound_gate(payload, known_real_names)
    return payload
