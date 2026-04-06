# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ISO 20022 Payment Test Generator. Supports **two message families** in parallel:

1. **pain.001.001.09** (Customer Credit Transfer Initiation) — C2B messages targeted at Swiss Payment Standards 2025 (SPS), with additional profiles for CGI-MP and CBPR+.
2. **pacs.008.001.08** (FI-to-FI Customer Credit Transfer) — Interbank messages for CBPR+ (SR2026). Allows testing inflow scenarios as well as outflow.

All user-facing text (error messages, documentation, Excel columns) is in German.

**Status:** pain.001 feature-complete for SPS/CGI-MP/CBPR+. pacs.008 V1 implemented for CBPR+ flavor; TARGET2/SEPA/SIC flavors prepared in the data model but not yet active.

## Build & Run Commands

```bash
poetry install                                                    # install dependencies
poetry run pytest                                                 # run all tests (800+)
poetry run pytest tests/test_pacs008_builders.py                  # run a single file

# pain.001 run
poetry run python -m src.main \
    --input templates/testfaelle_comprehensive.xlsx \
    --config config.yaml

# pacs.008 run (auto-detected from excel header; --message forces)
poetry run python -m src.main \
    --input templates/testfaelle_pacs008_comprehensive.xlsx \
    --config config.yaml

# pacs.008 with external FINaplo validation
poetry run python -m src.main \
    --input templates/testfaelle_pacs008_comprehensive.xlsx \
    --config config.yaml \
    --finaplo
```

CLI flags:
- `--message pain.001|pacs.008` — force message type (default: auto-detect from Excel header)
- `--finaplo` — enable external FINaplo API validation for pacs.008 (requires `finaplo/api-key-*.txt`)

## Architecture

Two parallel pipelines sharing common infrastructure:

```
                Excel Input
                     |
                Auto-Detect (header-based)
                /          \
       pain.001            pacs.008
           |                  |
   PaymentTestPipeline   Pacs008TestPipeline
   (src/pipeline.py)     (src/pacs008_pipeline.py)
           |                  |
   Data Factory + pain001     Pacs008 Builders (CBPR+)
   Builders (SPS/CGI/CBPR+)   + BAH envelope
           |                  |
         XSD Validation (per-message schema)
           |                  |
         Business Rules Catalog (rule_catalog.py)
           |                  |
         (optional) FINaplo External Validation  ---- pacs.008 only
           |                  |
         Reports (JSON + DOCX/TXT)
                     |
         output/<ts>/{pain.001|pacs.008}/
```

### Modules (src/)

**Shared infrastructure:**
- `input_handler/excel_parser.py` — parses both excel formats; `detect_message_type()` picks the right parser
- `data_factory/` — IBAN (Mod-97), QRR (Mod-10), SCOR (ISO 11649), faker-based names/addresses, BIC directory
- `validation/rule_catalog.py` — unified rule catalog across all standards
- `validation/xsd_validator.py` — generic XSD validator
- `finaplo/client.py` — REST wrapper for FINaplo external validation (Bearer auth, per-flavor endpoint dispatch)
- `models/config.py` — AppConfig (Pydantic)

**pain.001-specific:**
- `pipeline.py` — PaymentTestPipeline
- `models/testcase.py` — TestCase, PaymentInstruction, Transaction (pain.001 shape)
- `xml_generator/builders.py`, `pain001_builder.py`, `bah_builder.py` — pain.001 XML construction
- `payment_types/` — SEPA, Domestic-QR, Domestic-IBAN, CBPR+ handlers
- `validation/business_rules.py` — pain.001 business rules (BR-SEPA-*, BR-QR-*, BR-IBAN-*, BR-CBPR-*, BR-CGI-*, BR-CH21-*, BR-GEN-*, BR-HDR-*, BR-ADDR-*, BR-CCY-*, BR-SIC5-*, BR-SCT-INST-*, BR-REM-*, BR-ULTMT-*)

**pacs.008-specific:**
- `pacs008_pipeline.py` — Pacs008TestPipeline
- `models/pacs008.py` — Pacs008TestCase, Pacs008Instruction, Pacs008Transaction, AgentInfo, PartyInfo, AccountInfo, ChargesInfo, PostalAddress, Pacs008BusinessMessage (BAH+Document envelope), Pacs008Flavor enum
- `xml_generator/pacs008/` — Subpackage with namespaces.py, builders.py, message_builder.py
- `payment_types/pacs008/defaults.py` — default values (SttlmMtd=INDA, ChrgBr=SHAR, T+1 settlement date, single default IntrmyAgt for CBPR+)
- `validation/pacs008_rules.py` — BR-CBPR-PACS-001..015 validator
- `validation/pacs008_violations.py` — Violations registry for negative testing

## Message-Type Auto-Detection

`detect_message_type(header)` in `src/input_handler/excel_parser.py` selects the pipeline:

- **pain.001 marker:** `Zahlungstyp` column (enum values SEPA/Domestic-QR/Domestic-IBAN/CBPR+ are pain.001-exclusive)
- **pacs.008 markers:** at least 2 of `InstgAgt BIC`, `InstdAgt BIC`, `IntrBkSttlmDt`, `IntrBkSttlmAmt`, `SttlmMtd`, `BAH From BIC`
- Ambiguous headers (both present) → ValueError, user must pass `--message` explicitly

## Key Domain Rules

### pain.001 / SPS 2025

- **QR-IBANs** have IID range 30000–31999; they require QR-Reference only (not SCOR)
- **QRR** is encoded as `Prtry` (not `Cd`) in the XML — XSD only allows SCOR as `Cd`
- **Regular IBANs** use SCOR (optional) or no reference (never QR-Reference)
- **SEPA:** EUR only, ChrgBr must be SLEV, Creditor name max 70 chars
- **CBPR+ pain.001:** Creditor-Agent BIC must be provided by user in overrides; BAH wrapping with MsgDefIdr=pain.001.001.09
- **Debtor data** comes entirely from Excel (structured debtor address via 5 columns: `Debtor Strasse/Hausnummer/PLZ/Ort/Land`)
- **PmtMtd** is always TRF (no CHK)
- **Negative test cases** use `ViolateRule=<RuleID>` — violations modify transaction data, not testcase data
- **Business rules** validate against actual transaction data (post-violation), not testcase input
- **Business-day calculation** via `workalendar`: TARGET2 (SEPA), Switzerland (Domestic/CBPR+)
- **SPS charset** is ASCII-only: `^[a-zA-Z0-9 /\-?:().,'+]*$` — no umlauts or accents in text fields (SPS is stricter than the XSD Latin-1 subset)
- **SPS CH21** compliance for `OrgId`: LEI must be wrapped as `Othr/Id` + `SchmeNm/Cd=LEI`, not as the bare `<LEI>` element
- **SPS CH21** for RgltryRptg: `Dtls/Cd` requires `Dtls/Ctry` (builder auto-derives from `Authrty.Ctry` as defensive fallback)
- **Multi-transaction** testcases use continuation rows (empty TestcaseID column = additional transaction for previous TC)
- **Overrides** via "Weitere Testdaten" as `Key=Value; Key=Value` in dot-notation (`RgltryRptg.Dtls.Cd=BOP`, `UltmtDbtr.Nm=...`, `TaxRmt.Cdtr.TaxId=...`, `Dbtr.Id.OrgId.LEI=...`, `Cdtr.PstlAdr.StrtNm=...`)

### pacs.008 / CBPR+ SR2026

- **InstrId** is mandatory on `PmtId` in CBPR+ (min=1, maxLength=16); builder auto-uses `INSTR<hex8>` if caller doesn't set one
- **UETR** must be UUIDv4 format (enforced by BR-CBPR-PACS-015)
- **CreDtTm** requires timezone offset (e.g. `+00:00`) — CBPR+ restricted DateTime pattern
- **CBPR+ allows exactly one CdtTrfTxInf per message** (maxOccurs=1); batching is not supported in CBPR+
- **CBPR+ GroupHeader93** does NOT contain `CtrlSum` or `InstgAgt`/`InstdAgt` (those are C-level only). The builder injects instruction-level InstgAgt/InstdAgt into the transaction via transient attrs
- **SttlmMtd in CBPR+** is enumerated `{INDA, INGA, COVE}` — **CLRG is NOT allowed in CBPR+**; V1 rejects COVE as out-of-scope (no pacs.009 generator yet)
- **ClrSysId is mandatory inside ClrSysMmbId** (XSD min=1); builder defaults to code `USABA` if caller doesn't set a clearing system code
- **BAH envelope** wraps `<Document>` inside `<BusinessMessage>` with `<AppHdr>` sibling: MsgDefIdr=`pacs.008.001.08`, BizSvc=`swift.cbprplus.02`
- **Currency-aware amount formatting**: zero-decimal currencies (JPY, KRW, ISK, VND, BIF, CLP, DJF, GNF, KMF, PYG, RWF, UGX, UYI, VUV, XAF, XOF, XPF) emit amounts without decimal places; three-decimal currencies (BHD, IQD, JOD, KWD, LYD, OMR, TND) use 3 decimals; all others use 2
- **Charges-Info**: no default values — `ChrgsInf` is only emitted if the caller explicitly provides entries
- **Default values** (applied by `src/payment_types/pacs008/defaults.py` when user doesn't set):
  - `SttlmMtd=INDA`
  - `ChrgBr=SHAR`
  - `IntrBkSttlmDt = T+1` business day (TARGET2 for EUR, Switzerland otherwise)
  - For CBPR+ flavor: single default `IntrmyAgt1 = CHASUS33XXX` if all three intermediary slots are empty

## FINaplo External Validation

Optional external validation against [FINaplo](https://finaplo-apis.paymentcomponents.com). Credentials are read from the gitignored `finaplo/` directory at the repo root:

- `finaplo/api-key-*.txt` — Bearer token (trial or paid subscription)
- `finaplo/base-url-*.txt` — Base URL (LIVE: `https://finaplo-apis.paymentcomponents.com`, SANDBOX: `.../sandbox`)
- Env vars `FINAPLO_API_KEY` and `FINAPLO_BASE_URL` override the files

Per-flavor endpoint dispatch:
- **CBPR+** → `POST /cbpr/validate` (active in V1)
- **TARGET2** → `POST /target2/validate` (prepared, not yet exercised)
- **SEPA** → `POST /sepa/{scheme}/validate` (prepared)

The pipeline skips FINaplo calls for negative testcases (saves quota) and gracefully handles trial quota exhaustion (`subscription.expired` HTTP 412 → `FinaploQuotaExceeded` → remaining testcases run with `finaplo_valid=None` and don't fail).

See `docs/roadmap/2026-04-06_pacs008_finaplo_auto_repair_log.md` for the WP-12 auto-repair session log.

## Key Files

### Core docs
- `docs/SDD_v2.md` — Software Design Document v2.1 (pain.001 architecture, data models, business rule catalog)
- `pain001_generator_anforderungen.md` — requirements specification (FR-01 to FR-105)
- `docs/xml_validation_services.md` — landscape of external validation services
- `docs/roadmap/2026-04-06_pacs008_implementation_plan.md` — pacs.008 V1 plan (13 WPs, all completed)
- `docs/roadmap/2026-04-06_pacs008_finaplo_auto_repair_log.md` — WP-12 auto-repair session log
- `docs/roadmap/2026-04-06_pain001_pacs008_chain_analysis.md` — deep-dive TODO for future chain derivation
- `docs/roadmap/2026-04-06_correspondent_lookup_map.md` — deep-dive TODO for correspondent bank routing

### Schemas
- `schemas/pain.001/pain.001.001.09.ch.03.xsd` — official SPS 2025 schema (SIX Group)
- `schemas/pain.001/head.001.001.02.xsd` — BAH for CBPR+ pain.001
- `schemas/pacs.008/CBPRPlus_SR2026_..._pacs_008_001_08_...iso15enriched.xsd` — CBPR+ SR2026 pacs.008 schema
- `schemas/pacs.008/bah_CBPRPlus_SR2026_..._pacs_008_001_08_...iso15enriched.xsd` — BAH for CBPR+ pacs.008

### Specs
- `docs/specs/pain.001/` — SPS 2025 business rules and credit transfer implementation guidelines (~10k lines)
- `docs/specs/pacs.008/cbpr+nonpublic/` — CBPR+ SR2026 pacs.008 usage guideline + handbook (gitignored)
- `docs/specs/cbpr+nonpublic/`, `docs/specs/cgi_nonpublic/` — other proprietary IGs (gitignored)

### Templates
- `templates/testfaelle_comprehensive.xlsx` — pain.001 comprehensive (137 testcases)
- `templates/testfaelle_vorlage.xlsx` — pain.001 quick smoke template
- `templates/testfaelle_pacs008_comprehensive.xlsx` — pacs.008 comprehensive (50 testcases)
- `templates/testfaelle_pacs008_minimal.xlsx` — pacs.008 quick smoke (3 rows)

### Runtime
- `config.yaml` — runtime configuration (output path, XSD path, seed, report format)
- `finaplo/` (gitignored) — FINaplo API credentials and swagger
