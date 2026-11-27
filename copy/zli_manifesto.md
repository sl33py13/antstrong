# Zero-Leak Intelligence (ZLI) Specification v1.0

Zero-Leak Intelligence (ZLI) is a local-first analytics architecture requiring that all personally identifiable information (PII) and sensitive infrastructure identifiers be scrubbed and tokenised within the customer's local perimeter prior to analytical synthesis, guaranteeing zero raw data egress while preserving full auditability back to the source data.

## Core Requirements
1. Gate 1: Local Perimeter Ingestion
2. Gate 2: Local Vault Tokenisation (LocalKeyVault)
3. Gate 3: Evidence-Grounded Synthesis tied to the data (scope, record counts, trends, and contributing source records)
