# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ISO 20022 pain.001 Test Generator — generates ISO 20022-compliant pain.001.001.09 payment XML files from Excel test case definitions. Targets Swiss Payment Standards (SPS) 2025. All user-facing text (error messages, documentation, Excel columns) is in German.

**Status**: Phase 1 implemented and functional. Phase 2 (API integration) planned.

## Build & Run Commands

```bash
poetry install                        # install dependencies
poetry run pytest                     # run all tests
poetry run pytest tests/test_iban.py  # run single test file
poetry run python -m src.main --input templates/testfaelle_vorlage.xlsx --config config.yaml --verbose
```

## Architecture

Pipeline: Excel Input → Mapping → Data Generation → XML Build → Validation → Reporting.

Six modules in `src/`:
1. **input_handler/** — parses/validates Excel test case files (openpyxl)
2. **mapping/** — deterministic Key→XPath mapping for overrides (AI mapping deferred to Phase 2, cache infra prepared in `cache/`)
3. **data_factory/** — generates IBANs (Mod-97), QRR (Mod-10), SCOR (ISO 11649), names/addresses via faker with global seed
4. **xml_generator/** — builds pain.001 A/B/C-level structure via lxml with strict namespace management
5. **validation/** — two-stage: XSD schema validation + business rule checks (30+ rules)
6. **reporting/** — Word (.docx), JSON, JUnit-XML outputs

Payment-type-specific logic in `payment_types/`: SEPA (`sepa.py`), Domestic-QR (`domestic_qr.py`), Domestic-IBAN (`domestic_iban.py`), CBPR+ (`cbpr_plus.py`) — all inherit from `base.py`.

## Key Domain Rules

- QR-IBANs have IID range 30000–31999; they require QR-Reference only (not SCOR)
- QRR is encoded as `Prtry` (not `Cd`) in the XML — XSD only allows SCOR as `Cd`
- Regular IBANs use SCOR (optional) or no reference (never QR-Reference)
- SEPA: EUR only, ChrgBr must be SLEV, Creditor name max 70 chars
- CBPR+: Creditor-Agent BIC must be provided by user in overrides
- Debtor data comes entirely from Excel (no default debtor in config)
- PmtMtd is always TRF (no CHK in Phase 1)
- Negative test cases use `ViolateRule=<RuleID>` — violations modify transaction data, not testcase data
- Business rules validate against actual transaction data (post-violation), not testcase input
- `workalendar` for business day calculation: TARGET2 (SEPA), Switzerland (Domestic/CBPR+)
- All text fields validated against SPS Latin-1 charset subset

## Key Files

- `docs/SDD_v2.md` — Software Design Document v2.1 (architecture, data models, full business rule catalog)
- `pain001_generator_anforderungen.md` — requirements specification (FR-01 to FR-105)
- `docs/specs/` — SPS 2025 business rules and credit transfer implementation guidelines (~10k lines)
- `schemas/pain.001.001.09.ch.03.xsd` — official XSD schema (SIX Group)
- `templates/testfaelle_vorlage.xlsx` — example Excel with 10 test cases
- `config.yaml` — runtime configuration (output path, XSD path, seed, report format)
