from collections import Counter
from typing import Any


def compute_kpis(payload: dict[str, Any]) -> dict[str, Any]:
    companies = payload.get('companies', [])
    tickets = payload.get('tickets', [])
    time_costs = payload.get('time_costs', [])
    assets = payload.get('assets', [])

    hours_by_client: dict[str, float] = {}
    labor_by_client: dict[str, float] = {}
    for entry in time_costs:
        tok = entry.get('company_token')
        if not tok:
            continue
        hrs = float(entry.get('hours', 0.0))
        rate = float(entry.get('hourly_cost', 0.0))
        hours_by_client[tok] = hours_by_client.get(tok, 0.0) + hrs
        labor_by_client[tok] = labor_by_client.get(tok, 0.0) + (hrs * rate)

    client_profitability = []
    total_mrr = 0.0
    total_net_profit = 0.0

    for comp in companies:
        tok = comp['company_token']
        mrr = float(comp.get('mrr', 0.0))
        stack_cost = float(comp.get('stack_cost', 0.0))
        hours = round(hours_by_client.get(tok, 0.0), 2)
        labor_cost = round(labor_by_client.get(tok, 0.0), 2)
        net_profit = round(mrr - stack_cost - labor_cost, 2)
        margin_pct = round((net_profit / mrr) * 100, 2) if mrr > 0 else 0.0
        eff_hourly = round(mrr / hours, 2) if hours > 0 else None

        total_mrr += mrr
        total_net_profit += net_profit

        client_profitability.append({
            'company_token': tok,
            'mrr': round(mrr, 2),
            'stack_cost': round(stack_cost, 2),
            'labor_cost': labor_cost,
            'hours': hours,
            'net_profit': net_profit,
            'margin_pct': margin_pct,
            'effective_hourly_rate': eff_hourly,
        })

    tag_counts: Counter[str] = Counter()
    sla_met_count = 0
    for t in tickets:
        if t.get('sla_met'):
            sla_met_count += 1
        tags = t.get('root_cause_tags') or t.get('tags') or []
        for tag in tags:
            tag_counts[tag] += 1

    sla_adherence_pct = round((sla_met_count / len(tickets)) * 100, 1) if tickets else 100.0

    compliant_assets = sum(1 for a in assets if a.get('patch_compliant'))
    patch_compliance_pct = round((compliant_assets / len(assets)) * 100, 1) if assets else 100.0
    out_of_warranty_count = sum(1 for a in assets if int(a.get('warranty_days_left', 0)) < 0)

    return {
        'summary': {
            'total_mrr': round(total_mrr, 2),
            'total_net_profit': round(total_net_profit, 2),
            'sla_adherence_pct': sla_adherence_pct,
            'patch_compliance_pct': patch_compliance_pct,
            'out_of_warranty_count': out_of_warranty_count,
        },
        'client_profitability': client_profitability,
        'root_cause_breakdown': dict(tag_counts.most_common()),
    }
