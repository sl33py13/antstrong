# antSTRONG: project instructions for Claude

Read `CLAUDE_HANDOFF.md` first for the full brief (product, brand rules, pricing, licensing, landing page spec).

## Role
Claude acts as CTO/COO for Ben, who is the CEO. Mandate: build and commercialise antSTRONG, aiming at $5,000 AUD per fortnight in recurring revenue. Resolve issues independently and keep going. Escalate only for product scope, pricing, security or privacy guarantees, and external communications or live outreach.

## Hard rules
- Never use em dashes in any copy, docs, emails or UI text.
- Follow the terminology rules in `CLAUDE_HANDOFF.md` section 2.
- Real client names, emails, IPs and vault keys never leave the local machine. Anything outbound goes through `LocalKeyVault` and `enforce_outbound_gate`.
- Never commit `.antstrong_vault/`, `keys/` or any `.pem` file.
- Ben is not a developer. Do the file and repo setup yourself rather than giving him instructions.

## Decisions made
- **Trials:** a trial is a signed certificate (14 days, expiry inside the signature), not a local file. One shared free trial per company email domain. A second sign-up from the same domain receives the company's existing certificate with days remaining and is treated as a sales lead for a personal email offering the one-time TRIAL-RESET. Trial certificates are not machine-bound. The download page says: "One free trial per company. Share it with your team."
- **Trade marks (Ben lodging himself):** antSTRONG word mark in Classes 9 and 42 via IP Australia TM Headstart, in his own name. ZLI is optional, Class 42 only. "Zero-Leak Intelligence" in full is likely too descriptive to register.
- **Secondary employment:** Ben is an APS employee and should check his agency's outside employment policy and tell his manager before taking payment.

## Status (27 Nov 2026)
Pre-launch, no customers. Built: CSV ingestion, `LocalKeyVault`, scrubber and outbound gate, profit and SLA analytics, local dashboard (`agent/server.py`), offline Ed25519 licensing with tests (31 passing).

Fixed this session: one client getting different tokens across files; vault never saved after ingest; trial could be reset by deleting a local file.

Not built yet: landing page and sandbox; trial sign-up and download flow; finished emails and launch posts; Windows/Linux packaging; connectors for ConnectWise, Autotask, HaloPSA, Syncro (the landing copy mentions them, so do not publish that claim until it is true); the "3.84s" claim is not proven (see benchmark below).

## Next steps, in order
1. DONE: licence checks wired into `agent/server.py` (402 until a valid certificate), License panel, bound to 127.0.0.1:8765. Run with `python -m agent.server`.
2. DONE: keypair generated 27 Nov 2026. Public key embedded in `agent/license_guard.py`. Private key lives only on Ben's PC at `D:\GeminiSpace\antSTRONG\keys\` (gitignored) and must be backed up offline.
3. Benchmark: DONE 27 Nov 2026. 652,000 synthetic records (2,000 clients) took 8.2 to 8.7s end to end on a 2-core cloud machine, after fixing a privacy-gate slowdown (it was over 10 minutes: the gate searched the whole payload once per known name). Re-run on Ben's PC with `python -m tools.make_benchmark_data bench-data` then `python -m tools.benchmark bench-data` before publishing any speed figure. Until then the landing page says "hundreds of thousands of records in seconds".
3b. Demo: DONE 27 Nov 2026. `demo/index.html` is the real dashboard with the real engine's output for a fictional 8-client MSP (`demo/drop/`, made by `tools/make_demo_data.py`). Published privately as an artifact: https://claude.ai/artifact/S9a37QR8fzvf1W3xH8A3Fv (Ben shares it when ready).
3c. Next: landing page that embeds or links the demo, with only true claims.
4. Finish the email and launch copy.

## Working on this project
Run tests with `python -m pytest -q`. Project files live on Ben's PC at `D:\GeminiSpace\antSTRONG`; this repo is the shared copy.
