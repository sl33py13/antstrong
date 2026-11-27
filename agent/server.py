import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from agent.ingest import process_drop_folder
from agent.license_guard import LicenseStatus, LicenseStore
from agent.analytics import compute_kpis
from agent.vault import LocalKeyVault
from agent.scrubber import PrivacyViolationError

DROP_DIR = os.environ.get("ANTSTRONG_DROP_DIR", "drop-folder")
VAULT_DIR = os.environ.get("ANTSTRONG_VAULT_DIR", ".antstrong_vault")
LICENSE_DIR = os.environ.get("ANTSTRONG_LICENSE_DIR", VAULT_DIR)
HOST = "127.0.0.1"  # local-only by design: the dashboard shows real client names
PORT = int(os.environ.get("ANTSTRONG_PORT", "8765"))

app = FastAPI(title="antSTRONG Local Agent & Dashboard", version="0.1.0")


class LicenseInstallRequest(BaseModel):
    certificate: str


def _license_store() -> LicenseStore:
    return LicenseStore(Path(LICENSE_DIR))


def _require_license() -> LicenseStatus:
    status = _license_store().status()
    if not status.valid:
        raise HTTPException(status_code=402, detail={"license": asdict(status)})
    return status


@app.get("/api/license")
def get_license():
    return asdict(_license_store().status())


@app.post("/api/license")
def install_license(req: LicenseInstallRequest):
    status = _license_store().install(req.certificate)
    if not status.valid:
        raise HTTPException(status_code=400, detail={"license": asdict(status)})
    return asdict(status)


def _run_pipeline():
    payload = process_drop_folder(drop_dir=DROP_DIR, vault_dir=VAULT_DIR)
    kpis = compute_kpis(payload)
    vault = LocalKeyVault(vault_dir=VAULT_DIR)
    rehydration_map = vault.get_rehydration_map()
    return payload, kpis, rehydration_map


@app.get("/api/cloud-payload")
def get_cloud_payload():
    """Returns strictly the zero-PII tokenized payload that goes to the cloud."""
    _require_license()
    try:
        payload, _, _ = _run_pipeline()
        return JSONResponse(content=payload)
    except PrivacyViolationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@app.get("/api/dashboard-data")
def get_dashboard_data():
    """Returns KPI analytics + local-only rehydration map (never sent to cloud)."""
    license_status = _require_license()
    try:
        payload, kpis, rehydration_map = _run_pipeline()
        return JSONResponse(content={
            "license": asdict(license_status),
            "kpis": kpis,
            "rehydration_map": rehydration_map,
            "outbound_payload_preview": payload,
        })
    except PrivacyViolationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@app.get("/", response_class=HTMLResponse)
def dashboard_ui():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>antSTRONG — Local-First MSP Intelligence</title>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --green: #22c55e;
      --red: #ef4444;
      --amber: #f59e0b;
    }
    * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { margin: 0; background: var(--bg); color: var(--text); padding: 24px; }
    .container { max-width: 1180px; margin: 0 auto; }
    header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 16px; border-bottom: 1px solid var(--border); padding-bottom: 18px; margin-bottom: 24px; }
    .brand h1 { margin: 0; font-size: 1.5rem; letter-spacing: -0.02em; }
    .brand span { color: var(--accent); }
    .brand p { margin: 4px 0 0; color: var(--muted); font-size: 0.9rem; }
    .controls { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
    .badge { white-space: nowrap; padding: 6px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; background: rgba(34,197,94,0.15); color: var(--green); border: 1px solid rgba(34,197,94,0.35); }
    .toggle-btn { background: var(--card); color: var(--text); border: 1px solid var(--accent); padding: 8px 14px; border-radius: 8px; cursor: pointer; font-weight: 600; font-size: 0.85rem; }
    .toggle-btn.cloud-mode { border-color: var(--amber); color: var(--amber); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }
    .card .label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .card .value { font-size: 1.7rem; font-weight: 700; margin-top: 8px; }
    .pos { color: var(--green); }
    .neg { color: var(--red); }
    .warn { color: var(--amber); }
    h2 { font-size: 1.1rem; margin: 0 0 12px; }
    table { width: 100%; border-collapse: collapse; background: var(--card); border-radius: 12px; overflow: hidden; border: 1px solid var(--border); margin-bottom: 24px; }
    th, td { text-align: left; padding: 12px 14px; border-bottom: 1px solid var(--border); font-size: 0.9rem; }
    th { color: var(--muted); font-weight: 600; background: rgba(15,23,42,0.5); }
    tr:last-child td { border-bottom: none; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem; }
    pre { background: #090d16; border: 1px solid var(--border); border-radius: 10px; padding: 16px; overflow-x: auto; font-size: 0.82rem; color: #cbd5e1; max-height: 320px; }
    .license-panel { background: var(--card); border: 1px solid var(--amber); border-radius: 12px; padding: 20px; margin-bottom: 24px; }
    .license-panel textarea { width: 100%; min-height: 140px; background: #090d16; color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 10px; font-family: ui-monospace, Menlo, monospace; font-size: 0.8rem; }
    .license-panel p { color: var(--muted); margin: 6px 0 12px; }
    .hidden { display: none; }
    .split { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    @media (max-width: 820px) { .split { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="brand">
        <h1>ant<span>STRONG</span></h1>
        <p>Zero-Exposure MSP Profitability, Compliance & Fleet Intelligence</p>
      </div>
      <div class="controls">
        <span class="badge" id="license-badge">LICENSE: CHECKING</span>
        <span class="badge" id="gate-status">PRIVACY GATE: PASSED (0 PII)</span>
        <button class="toggle-btn" onclick="showLicensePanel(true)">License</button>
        <button class="toggle-btn" id="view-toggle" onclick="toggleView()">View: Local Re-Hydrated (Real Names)</button>
        <button class="toggle-btn" onclick="loadDashboard()">Refresh CSVs</button>
      </div>
    </header>

    <div class="license-panel hidden" id="license-panel">
      <h2>License</h2>
      <p id="license-message">Paste your trial or license certificate below, including the BEGIN and END lines.</p>
      <textarea id="license-input" placeholder="-----BEGIN ANTSTRONG LICENSE-----"></textarea>
      <div style="margin-top:12px; display:flex; gap:12px;">
        <button class="toggle-btn" onclick="activateLicense()">Activate</button>
        <button class="toggle-btn" id="license-close" onclick="showLicensePanel(false)">Close</button>
      </div>
    </div>

    <div id="dashboard-body">
    <div class="grid" id="kpi-cards"></div>

    <h2>Agreement Profitability & Effective Hourly Rate</h2>
    <table>
      <thead>
        <tr>
          <th>Client</th>
          <th>MRR</th>
          <th>Stack Cost</th>
          <th>Labor Cost</th>
          <th>Hours</th>
          <th>Net Profit</th>
          <th>Margin %</th>
          <th>Eff. Hourly Rate</th>
        </tr>
      </thead>
      <tbody id="profit-table"></tbody>
    </table>

    <div class="split">
      <div class="card">
        <h2>Root-Cause Ticket Tags (Scrubbed In-RAM)</h2>
        <div id="tags-list"></div>
      </div>
      <div class="card">
        <h2>Exact Cloud Payload Inspector (What Leaves Your Network)</h2>
        <pre id="cloud-json">Loading...</pre>
      </div>
    </div>
    </div>
  </div>

  <script>
    let cloudOnlyMode = false;
    let cachedData = null;

    function esc(v) {
      return String(v).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }

    function showLicensePanel(show, message) {
      document.getElementById("license-panel").classList.toggle("hidden", !show);
      if (message) document.getElementById("license-message").textContent = message;
    }

    function setLicenseBadge(lic) {
      const b = document.getElementById("license-badge");
      if (lic && lic.valid) {
        const label = lic.mode === "licensed" ? lic.tier.toUpperCase() : "TRIAL";
        b.textContent = `${label}: ${lic.days_remaining} DAY(S) LEFT`;
        b.style.color = lic.days_remaining <= 3 ? "var(--amber)" : "var(--green)";
      } else {
        b.textContent = "NOT LICENSED";
        b.style.color = "var(--red)";
      }
    }

    async function activateLicense() {
      const certificate = document.getElementById("license-input").value;
      const res = await fetch("/api/license", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ certificate })
      });
      const data = await res.json();
      if (!res.ok) {
        showLicensePanel(true, "That certificate was not accepted: " + data.detail.license.reason);
        return;
      }
      document.getElementById("license-input").value = "";
      showLicensePanel(false);
      loadDashboard();
    }

    function fmtMoney(n) {
      const v = Number(n);
      return (v < 0 ? "-$" : "$") + Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function toggleView() {
      cloudOnlyMode = !cloudOnlyMode;
      const btn = document.getElementById("view-toggle");
      if (cloudOnlyMode) {
        btn.textContent = "View: Raw Cloud Mode (Tokenized Only)";
        btn.classList.add("cloud-mode");
      } else {
        btn.textContent = "View: Local Re-Hydrated (Real Names)";
        btn.classList.remove("cloud-mode");
      }
      render();
    }

    function resolveToken(token, map) {
      if (cloudOnlyMode) return token;
      return map[token] || token;
    }

    function render() {
      if (!cachedData) return;
      const { kpis, rehydration_map, outbound_payload_preview } = cachedData;
      const s = kpis.summary;

      document.getElementById("kpi-cards").innerHTML = `
        <div class="card"><div class="label">Total MRR</div><div class="value">${fmtMoney(s.total_mrr)}</div></div>
        <div class="card"><div class="label">Net Agreement Profit</div><div class="value ${s.total_net_profit >= 0 ? 'pos' : 'neg'}">${fmtMoney(s.total_net_profit)}</div></div>
        <div class="card"><div class="label">SLA Adherence</div><div class="value ${s.sla_adherence_pct >= 90 ? 'pos' : 'warn'}">${s.sla_adherence_pct}%</div></div>
        <div class="card"><div class="label">Patch Compliance</div><div class="value ${s.patch_compliance_pct >= 90 ? 'pos' : 'warn'}">${s.patch_compliance_pct}%</div></div>
        <div class="card"><div class="label">Out of Warranty Assets</div><div class="value ${s.out_of_warranty_count === 0 ? 'pos' : 'neg'}">${s.out_of_warranty_count}</div></div>
      `;

      document.getElementById("profit-table").innerHTML = kpis.client_profitability.map(c => {
        const displayName = resolveToken(c.company_token, rehydration_map);
        const profitClass = c.net_profit >= 0 ? "pos" : "neg";
        return `
          <tr>
            <td class="${cloudOnlyMode ? 'mono' : ''}"><strong>${esc(displayName)}</strong></td>
            <td>${fmtMoney(c.mrr)}</td>
            <td>${fmtMoney(c.stack_cost)}</td>
            <td>${fmtMoney(c.labor_cost)}</td>
            <td>${c.hours}h</td>
            <td class="${profitClass}"><strong>${fmtMoney(c.net_profit)}</strong></td>
            <td class="${profitClass}">${c.margin_pct}%</td>
            <td>${c.effective_hourly_rate !== null ? fmtMoney(c.effective_hourly_rate) + "/hr" : "—"}</td>
          </tr>
        `;
      }).join("");

      const tags = kpis.root_cause_breakdown || {};
      const tagEntries = Object.entries(tags);
      document.getElementById("tags-list").innerHTML = tagEntries.length
        ? tagEntries.map(([tag, count]) => `<p class="mono" style="margin:8px 0;"><strong>${tag}</strong>: ${count} ticket(s)</p>`).join("")
        : "<p style='color:var(--muted)'>No tickets ingested yet.</p>";

      document.getElementById("cloud-json").textContent = JSON.stringify(outbound_payload_preview, null, 2);
    }

    async function loadDashboard() {
      const res = await fetch("/api/dashboard-data");
      if (res.status === 402) {
        const err = await res.json();
        setLicenseBadge(err.detail.license);
        document.getElementById("dashboard-body").classList.add("hidden");
        showLicensePanel(true, err.detail.license.reason);
        return;
      }
      if (!res.ok) {
        const err = await res.json();
        document.getElementById("gate-status").textContent = "PRIVACY GATE BLOCKED!";
        document.getElementById("gate-status").style.color = "#ef4444";
        alert("Privacy Gate Blocked Payload: " + err.detail);
        return;
      }
      cachedData = await res.json();
      setLicenseBadge(cachedData.license);
      document.getElementById("dashboard-body").classList.remove("hidden");
      render();
    }

    loadDashboard();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn

    print(f"antSTRONG dashboard: http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
