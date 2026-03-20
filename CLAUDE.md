# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ISO 20022 pain.001 Test Generator — generates ISO 20022-compliant pain.001.001.09 payment XML files from Excel test case definitions. Targets Swiss Payment Standards (SPS) 2025. All user-facing text (error messages, documentation, Excel columns) is in German.

**Status**: Design and specifications complete; implementation not yet started.

## Technology Stack (per SDD)

- Python 3.10+, managed with **Poetry**
- **Pydantic v2** with `decimal.Decimal` for all financial amounts
- **lxml** for XML generation and XSD validation (strict namespace management)
- **Pydantic-AI** for schema-aware free-text field mapping
- **openpyxl** for Excel input, **faker** for test data (seed-based reproducibility)
- **python-docx** for Word reports, plus JSON and JUnit-XML output

## Build & Run Commands

No build infrastructure exists yet. When created, it should use:
```bash
poetry install          # install dependencies
poetry run pytest       # run tests
poetry run python src/main.py  # run the generator
```

## Architecture

The system follows a pipeline: Excel Input → Mapping → Data Generation → XML Build → Validation → Reporting.

Six modules (defined in `docs/SDD.md`):
1. **Input Handler** — parses/validates Excel test case files
2. **Mapping Engine** — AI-powered mapping of free-text overrides to XML XPaths
3. **Data Factory** — generates random valid data (IBANs, names, etc.) via faker with global seed
4. **XML Generator** — builds pain.001 A/B/C-level structure via lxml
5. **Validation Engine** — two-stage: XSD schema validation + business rule checks
6. **Reporting Module** — Word (.docx), JSON, JUnit-XML outputs

Payment-type-specific logic is separated into modules: SEPA, Domestic-QR, Domestic-IBAN, CBPR+.

## Key Domain Rules

- QR-IBANs have IID range 30000–31999; they require QR-Reference (not SCOR/NON)
- Regular IBANs use SCOR or NON reference types (never QR-Reference)
- Negative test cases use `ViolateRule=<RuleName>` in the Excel override field
- `TxCount=<n>` in overrides generates multiple transactions per file
- Output file naming: `[Timestamp]_[TestCaseID]_[UUID_Short].xml`

## Key Files

- `docs/SDD.md` — Software Design Document (architecture decisions, data models)
- `pain001_generator_anforderungen.md` — full requirements specification (FR-01 to FR-105)
- `docs/specs/` — SPS 2025 business rules and credit transfer implementation guidelines
- `schemas/pain.001.001.09.ch.03.xsd` — official XSD schema for validation
