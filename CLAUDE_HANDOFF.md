# PROJECT HANDOFF: antSTRONG — Zero-Leak Intelligence (ZLI)

## 1. CORE OBJECTIVE & COMMERCIAL STAKES
- **Goal:** Build, ship, and commercialize **antSTRONG**, a local-first analytics and executive reporting engine for Managed Service Providers (MSPs).
- **Commercial Target / Mandate:** Generate **$5,000 AUD per fortnight** in recurring revenue (or risk losing primary income / being fired). Every product, marketing, pricing, and engineering decision must serve rapid commercial validation, high-trust enterprise conversion, and minimal operational overhead.
- **Target Buyer:** MSP owners, service delivery managers, and vCIOs who want margin intelligence and board-ready executive reports (QBRs, operational reviews) without uploading raw client PII or internal infrastructure data to third-party cloud BI vendors.

---

## 2. BRANDING, IP CLEARANCE & TERMINOLOGY RULES

### Brand Identity & IP Australia Status
- **Primary Brand Name:** `antSTRONG`
  - Cleared via web search and IP Australia TM Checker in Classes 9 & 42 (no competing MSP/analytics marks; only unrelated tools like ANTS Analytics and Angstrom).
  - Distinctive coined word mark suitable for primary formal trade mark registration.
- **Category Positioning / Tagline:** `Zero-Leak Intelligence (ZLI)`
  - Checked via IP Australia TM Checker in Classes 9 & 42 (`computer software design`).
  - Zero existing marks combine both "Zero" and "Intelligence"; `ZLI` returned only unrelated 3-letter combinations (`ZAI`, `X-LI`, `ELI`, `ZLX`, `ZII`).
  - Safe to use commercially as category positioning and tagline; always introduce on first mention as `Zero-Leak Intelligence (ZLI)`.

### Strict Copy & Style Rules (MANDATORY)
1. **NO EM DASHES (`—`):** Never use em dashes anywhere in copy, documentation, emails, or UI text. Use commas, colons, parentheses, or clean line breaks instead.
2. **Terminology Standardisation:**
   - Use **"PII"** naturally alongside concrete examples (client names, emails, phone numbers, internal IPs/hostnames) and do not define what "PII" stands for in a rookie textbook way.
   - Generalise **"PSA exports"** to **"operational data"** or **"operational datasets"** so copy remains valid when direct API connectors are added later.
   - Generalise **"QBRs"** to **"executive reports"** or **"client business reviews"**.
   - Avoid calling external APIs "fragile" (since `antSTRONG` will integrate APIs in future phases); instead highlight **"Zero Cloud Connectors Required"** for local drop-folder ingestion.
   - Use **"deterministic"** specifically to contrast against AI hallucinations (*"Deterministic math, zero AI hallucinations"*).
   - Use **"unique vault tokens"** (rather than repeating "deterministic") when describing `LocalKeyVault` PII replacement.
   - Ground all claims in **"the data"** / **"source records"** (aggregations, group rollups, trends, scope counts, and top contributing records), not just single-row citations.
   - Commercial tone: Use **"Thanks for choosing antSTRONG"** (never "backing", which sounds like crowdfunding).

---

## 3. TECHNICAL ARCHITECTURE & LOCAL ENVIRONMENT

### Development Environment
- **Workstation:** Windows PC (`D:\GeminiSpace\antSTRONG`)
- **Stack:** Python 3.15.2, Uvicorn backend (`agent.server`), `pytest`, `cryptography` (Ed25519), local CSV drop-folder ingestion, KPI/margin analytics, deterministic PII scrubbing/tokenisation (`LocalKeyVault` + `agent.scrubber`).
- **Delivery Format:** Local-first executable / Python package running strictly inside the customer's perimeter (Windows x64 and Linux x64). Zero raw data egress to vendor servers.

### Three Architectural Gates of Zero-Leak Intelligence (ZLI)
1. **Gate 1 — Local Perimeter Ingestion:**
   - Parses and normalises messy operational exports (non-standard dates, mixed currency symbols, missing headers, duplicate rows) locally inside customer hardware.
2. **Gate 2 — `LocalKeyVault` PII Scrubbing:**
   - Replaces client names, contact emails, phone numbers, and internal hostnames/IPs with unique encrypted vault tokens (`CLIENT_014`, `TECH_03`, `IP_009`) *prior* to analytical synthesis. Translation lookup keys stay strictly inside the customer's local vault.
3. **Gate 3 — Evidence-Grounded Executive Reports:**
   - Computes effective hourly rates, unbilled reactive ticket drag, flat-fee contract profitability, and SLA breach trends deterministically. Every headline claim carries verifiable scope metadata (time window, dataset slice, record count, and contributing source records).

### Future API Integration Strategy
- When direct PSA/RMM API connectors are added, split execution readouts into two separate timestamps so slow vendor APIs never make `antSTRONG` look slow:
  1. **Local API Fetch:** Network/rate-limit bound direct pull inside customer perimeter (e.g., `2.40s`).
  2. **ZLI Local Crunch:** Local PII tokenisation + deterministic rollup in milliseconds (e.g., `0.38s`).
- Highlight **Incremental Delta Sync** speed for repeat runs vs. **Initial Full Sync** (e.g., `185,000 records initial sync` vs. `1,420 updated records crunched in ~40ms`).
- Keep UI labels future-proof as **"Operational Data Source (Local Export / Direct API)"**.

---

## 4. COMMERCIAL MODEL, PRICING & OFFLINE LICENSING

### Pricing Tiers (Per MSP, Unlimited Technicians)
- **Starter (`$99/mo`):** Up to 15 managed clients · Full local ZLI engine · Unlimited executive reports
- **Growth (`$249/mo` · Most Popular):** Up to 50 managed clients · Multi-dataset rollups · Custom report branding
- **Scale (`$499/mo`):** Unlimited managed clients · Multi-site service delivery · Priority support & custom parsers

### Trial & Anti-Leakage Policy ("14-Day Trial / 2 Weeks or Bust")
- **Days 1–14:** Full-feature local trial unlocked on first run (no credit card, no cloud account).
- **After Day 14:** Hard lock into "License Required" mode (no permanent free tier, so solo operators with 1–2 clients cannot use it indefinitely for free).
- **One-Time Recovery Mechanism:** Buyers who genuinely missed their evaluation window can request a single, one-time **`TRIAL-RESET`** signed certificate granting one final 14-day window (`trial_reset_used: true`). Hard cap at 2 windows total.

### Ed25519 + Base64 Offline License System (Directory Opus Style)
- Included in `agent/license_guard.py`, `tools/generate_license.py`, and `tests/test_license_guard.py` inside this archive.

---

## 5. LANDING PAGE DESIGN, UX & INTERACTIVE SANDBOX SPEC
- **No sticky scroll-jacking:** Standard vertical scroll with an interactive clickable 3-step switcher (`1. Local Ingestion` | `2. LocalKeyVault Scrubbing` | `3. Executive Reports`).
- **Zero File Uploads on Homepage:** Intentionally block real file uploads on the web demo.
- **4-Tier Synthetic Dataset Selector with Dynamic Ant/Sisyphus Vector SVG:**
  1. **Light Load (`2,500 records · 650 KB`):** Stylized ant carrying a neat pebble overhead.
  2. **Medium & Messy (`45,000 records · 14 MB`):** Stylized ant rolling a rough boulder across flat ground.
  3. **Heavy Climb (`180,000 records · 85 MB`):** Stylized ant pushing a massive boulder up a steep Sisyphus incline.
  4. **Overhead Titan (`650,000+ records · 500 MB`):** Stylized ant hoisting a colossal boulder overhead (completing in `< 5 seconds`, e.g., `3.84s` in realtime).
- **Two-Stage Interactive Demo Flow:**
  - **Stage 1 (`Step 1: Run Guided Walkthrough`):** Slowed-down visual animation showing raw rows sliding through `LocalKeyVault`.
  - **Stage 2 (`Step 2: Run in Realtime`):** User-triggered button after Stage 1 completes, running at native speed with a live millisecond stopwatch and split timing readout (`Local Ingestion` vs. `ZLI Scrub & Crunch`).

---

## 6. COPY, EMAILS, LAUNCH POSTS & VIDEO STORYBOARD
Included as dedicated files inside this archive:
- `copy/landing_page_copy.md`
- `copy/zli_manifesto.md`
- `copy/transactional_emails.md`
- `copy/launch_and_outreach.md`
- `copy/promo_video_storyboard_30s.md`

---

## 7. IMMEDIATE NEXT ACTIONS FOR CLAUDE TO EXECUTE
1. Wire `agent/license_guard.py` into `agent.server` (FastAPI/Uvicorn startup validation and route checks, keeping `Settings -> License` accessible when expired).
2. Build the `Settings -> License` UI panel and POST endpoint to validate and persist pasted Base64 license certificates.
3. Run `tools/generate_license.py keygen`, embed the public key into `agent/license_guard.py`, and run `pytest tests/test_license_guard.py`.
4. Extract and finalise the landing page frontend + 4-tier Ant/Sisyphus sandbox into the marketing repo and wire up trial/download capture.
5. Execute Go-To-Market Sprint toward **$5,000 AUD / fortnight** (~10–20 MSPs on Growth/Scale): publish `/zli` and homepage, post to r/msp, MSPGeek, and LinkedIn, and run outbound outreach to MSP owners.
