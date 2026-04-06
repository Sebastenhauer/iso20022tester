# ISO 20022 Payment Test Generator

Automatisierte Erstellung von ISO 20022-konformen Zahlungsnachrichten auf Basis von Excel-Testfalldefinitionen. Unterstuetzt zwei Message-Familien parallel:

- **pain.001.001.09** (Customer Credit Transfer Initiation) — C2B-Messages fuer **Swiss Payment Standards (SPS) 2025**, **CGI-MP** und **SWIFT CBPR+ SR2026**
- **pacs.008.001.08** (FI-to-FI Customer Credit Transfer) — Interbank-Messages fuer **CBPR+ SR2026**, ermoeglicht **Inflow-Testing** (eingehende Zahlungen simulieren) und **Outflow-Testing** (ausgehende Zahlungen generieren). TARGET2/SEPA/SIC-Flavors sind im Datenmodell vorbereitet fuer V2.

Die CLI erkennt den Message-Type automatisch anhand des Excel-Headers; beide Pipelines laufen mit derselben `src.main`-Entry.

## Quick Start

```bash
poetry install

# pain.001 run
poetry run python -m src.main \
    --input templates/testfaelle_comprehensive.xlsx \
    --config config.yaml

# pacs.008 run (Message-Type wird automatisch erkannt)
poetry run python -m src.main \
    --input templates/testfaelle_pacs008_comprehensive.xlsx \
    --config config.yaml

# pacs.008 mit externer FINaplo Validation (benoetigt API-Key)
poetry run python -m src.main \
    --input templates/testfaelle_pacs008_comprehensive.xlsx \
    --config config.yaml \
    --finaplo
```

Output landet in `output/<timestamp>/pain.001/` bzw. `output/<timestamp>/pacs.008/` (getrennt pro Message-Type) und enthaelt die generierten XML-Files plus Reports (`testlauf_ergebnis.json` + `Testlauf_Zusammenfassung.docx`).

---

## pain.001 Test Generator

### Drei Standards -- Drei Use Cases

| | **SPS 2025** | **CGI-MP** | **CBPR+ SR2026** |
|-|-------------|-----------|-----------------|
| **Use Case** | Schweizer Corporate sendet Zahlung an CH-Bank | Multinationaler Corporate sendet Zahlung an Hausbank weltweit | Bank leitet Zahlung an Korrespondenzbank weiter |
| **Scope** | Customer-to-Bank (Schweiz) | Customer-to-Bank (global) | Bank-to-Bank (Relay) |
| **Schema** | `pain.001.001.09.ch.03` (im Repo) | Standard ISO pain.001.001.09 (SPS XSD kompatibel) | CBPR+ Restriction (proprietaer, MyStandards) |
| **Excel-Wert** | `sps2025` (Default) | `cgi-mp` | `cbpr+2026` |

> **Typischer Einsatz:** Ein Schweizer Corporate nutzt **SPS** fuer Domestic/SEPA und **CGI-MP** fuer internationale Zahlungen. **CBPR+** ist relevant fuer Banken, die pain.001 im Relay-Szenario weiterleiten.

### Strukturelle Unterschiede

| Element | SPS 2025 | CGI-MP | CBPR+ SR2026 |
|---------|----------|--------|-------------|
| GrpHdr/NbOfTxs | Summe aller Tx | Summe aller Tx | Immer "1" |
| GrpHdr/CtrlSum | Summe aller Betraege | Summe aller Betraege | **Entfaellt** |
| PmtInf/NbOfTxs | Anzahl Tx im Block | Anzahl Tx im Block | **Entfaellt** |
| PmtInf/CtrlSum | Summe im Block | Summe im Block | **Entfaellt** |
| PmtInfId | Generiert (eindeutig) | Kann = MsgId oder verschieden | **= MsgId** (Rule R8) |
| UETR | Optional | Optional (empfohlen) | **Pflicht** (UUIDv4) |
| CreDtTm | ISO 8601 lokal | ISO 8601 lokal | **Pflicht UTC-Offset** |
| ChrgBr | DEBT/CRED/SHAR/SLEV | DEBT/CRED/SHAR/SLEV | DEBT/CRED/SHAR (**kein SLEV**) |
| Transaktionen/Msg | 1..n PmtInf, 1..n Tx | 1..n PmtInf, 1..n Tx | **Genau 1 PmtInf, 1 Tx** |
| Zeichensatz | SPS Latin-1 Subset | UTF-8 (voll) | FIN-X Restricted |
| Leere Tags | Erlaubt | **Verboten** | Verboten |
| Regulatory Reporting | -- | Unterstuetzt | Wie CGI-MP |
| Structured Remittance | CdtrRefInf (SCOR, QRR) | Voll (RfrdDocInf, TaxRmt) | Wie CGI-MP |

Detaillierte Vergleiche: `docs/specs/vergleich-sps-epc-sepa-2025.md`, `docs/specs/vergleich-sps-cbprplus-2025.md`

## Features

- **Tri-Standard-Validierung** -- pro Testfall waehlbar: `sps2025` (Default), `cgi-mp` oder `cbpr+2026`, mit standard-spezifischer XML-Generierung und XSD-Validierung via Strategy Pattern
- **Excel-basierte Testfalldefinition** -- ein Testfall pro Zeile, zusaetzliche Transaktionen als Folgezeilen ohne TestcaseID
- **4 Zahlungstypen** -- SEPA, Domestic-QR, Domestic-IBAN, CBPR+ mit typ-spezifischen Regeln und automatischer Erkennung
- **55+ Business Rules** -- zentraler Rule-Katalog in 12 Kategorien inkl. SPS, CGI-MP und CBPR+-spezifische Regeln
- **CGI-MP C2B-Konformitaet** -- globaler Corporate-to-Bank Standard mit Address-, Remittance-, Purpose- und Tax-Rules
- **CBPR+ Relay-Konformitaet** -- UETR Pflicht, SLEV verboten, kein CtrlSum, PmtInfId=MsgId, UTC-Offset, FIN-X Charset
- **Multi-Payment** -- mehrere Testfaelle in einer XML via `GroupId` (SPS und CGI-MP; CBPR+ nur Single-Tx)
- **Negative Testing** -- violatable Rules fuer gezielte Regelverletzungen via `ViolateRule=<RuleID>`
- **Reproduzierbare Testdaten** -- Seed-basierte Generierung von IBANs (Mod-97), QR-Referenzen (Mod-10), SCOR (ISO 11649)
- **Minimale Pflichtfelder** -- nur TestcaseID, Titel, Ziel, Erwartetes Ergebnis und Debtor-IBAN
- **Second-Opinion + Round-Trip-Validierung** -- `xmlschema`-Gegenpruefung und XML-Roundtrip-Konsistenzcheck
- **50+ Laender IBAN-Generierung** -- Europa, Naher Osten, Asien, Amerika, Afrika
- **Reporting** -- Word (.docx), JSON und JUnit-XML Reports pro Testlauf
- **122 Testfaelle** -- 104 SPS + 10 CGI-MP + 8 CBPR+, alle XSD-validiert

---

## Ablauf & Architektur

### Pipeline

```mermaid
flowchart TD
    A[CLI-Start] --> B[Config laden]
    B --> C[Excel parsen & validieren]
    C --> D{Testfaelle vorhanden?}
    D -- Nein --> E[Abbruch mit Fehler]
    D -- Ja --> F[Gruppierung nach GroupId]
    F --> G[Naechster Testfall / Gruppe]
    G --> H["Standard bestimmen\n(sps2025 / cgi-mp / cbpr+2026)"]
    H --> I["Strategy Pattern:\nXML-Struktur waehlen"]
    I --> J[Mapping + Data Factory]
    J --> K[XML generieren]
    K --> L["XSD-Validierung\n(SPS oder CBPR+ Schema)"]
    L --> M[Business Rules pruefen]
    M --> N[Pass/Fail-Bewertung]
    N --> O{Weitere Testfaelle?}
    O -- Ja --> G
    O -- Nein --> P[Reporting: Word + JSON + JUnit-XML]
```

### Validierungs- und Pass/Fail-Logik

```mermaid
flowchart TD
    A[XML generiert] --> B[Stufe 1: XSD-Validierung]
    B --> C{XSD valide?}
    C -- Nein --> D["Bug im Generator → RuntimeError"]
    C -- Ja --> E[Stufe 2: Business Rules]
    E --> F{Rule-Violations?}
    F -- Nein --> G[Keine Fehler]
    F -- Ja --> H[Violations gesammelt]

    G & H --> I[Pass/Fail-Matrix]

    I --> J["OK + keine Fehler → Pass"]
    I --> K["OK + Fehler gefunden → Fail"]
    I --> L["NOK + Fehler gefunden → Pass"]
    I --> M["NOK + keine Fehler → Fail"]
```

> XSD-Fehler werden als Bug im Generator behandelt und werfen einen `RuntimeError`. Generierte XMLs **muessen** immer schema-valide sein -- auch bei negativen Testfaellen.

### pain.001 XML-Struktur (A/B/C-Level)

```mermaid
flowchart TD
    Doc["Document\n(xmlns:pain.001.001.09)"] --> Root["CstmrCdtTrfInitn"]
    Root --> GrpHdr["A-Level: GrpHdr\n─────────────\nMsgId, CreDtTm\nNbOfTxs, CtrlSum\n(SPS+CGI-MP: aggregiert)\n(CBPR+: NbOfTxs=1, kein CtrlSum)\nInitgPty"]
    Root --> PmtInf1["B-Level: PmtInf\n─────────────\nPmtInfId, PmtMtd=TRF\nPmtTpInf (SvcLvl, CtgyPurp)\nReqdExctnDt\nDbtr + DbtrAcct + DbtrAgt\nChrgBr"]
    PmtInf1 --> Tx1["C-Level: CdtTrfTxInf\n─────────────\nEndToEndId + UETR\nInstdAmt (Ccy)\nCdtrAgt / Cdtr / CdtrAcct\nRmtInf (QRR/SCOR/Ustrd)"]
    PmtInf1 --> Tx2["C-Level: CdtTrfTxInf\n─────────────\n(weitere Tx, SPS+CGI-MP)"]
    Root --> PmtInf2["B-Level: PmtInf\n─────────────\n(weitere PmtInf bei\nGroupId, SPS+CGI-MP)"]
    PmtInf2 --> Tx3["C-Level: CdtTrfTxInf"]

    style Doc fill:#e1f0ff,stroke:#4a90d9
    style Root fill:#e1f0ff,stroke:#4a90d9
    style GrpHdr fill:#d4edda,stroke:#28a745
    style PmtInf1 fill:#fff3cd,stroke:#ffc107
    style PmtInf2 fill:#fff3cd,stroke:#ffc107
    style Tx1 fill:#f8d7da,stroke:#dc3545
    style Tx2 fill:#f8d7da,stroke:#dc3545
    style Tx3 fill:#f8d7da,stroke:#dc3545
```

---

## Voraussetzungen

- Python 3.10+
- [Poetry](https://python-poetry.org/) (Paketmanagement)
- **Fuer CBPR+:** SWIFT CBPR+ XSD von [MyStandards](https://www2.swift.com/mystandards/) (kostenloser Login, proprietaer, nicht im Repo)
- **Fuer CGI-MP:** Kein zusaetzliches XSD noetig (SPS XSD wird verwendet)

## Installation

```bash
git clone https://github.com/Sebastenhauer/iso20022tester.git
cd iso20022tester
poetry install
```

### CBPR+ XSD einrichten (optional)

1. Auf [SWIFT MyStandards](https://www2.swift.com/mystandards/) einloggen (kostenlose Registration)
2. CBPR+ Collection oeffnen, pain.001.001.09 Usage Guideline XSD herunterladen
3. Ablegen unter `docs/specs/cbpr+nonpublic/` (wird per `.gitignore` nicht gepusht)
4. Pfad in `config.yaml` eintragen:
   ```yaml
   cbpr_xsd_path: "docs/specs/cbpr+nonpublic/<dateiname>.xsd"
   ```

## Verwendung

```bash
# XML generieren
poetry run python -m src.main --input <excel-datei> --config config.yaml [--seed 42] [--verbose]

# Round-Trip-Validierung
poetry run python -m src.main roundtrip <xml-dateien-oder-verzeichnis> --config config.yaml [--verbose]
```

**Beispiele:**

```bash
# 122 Testfaelle generieren (SPS + CGI-MP + CBPR+ gemischt)
poetry run python -m src.main --input templates/testfaelle_comprehensive.xlsx --config config.yaml --verbose
```

### Konfiguration (`config.yaml`)

```yaml
output_path: "./output"
xsd_path: "schemas/pain.001.001.09.ch.03.xsd"       # SPS XSD (im Repo, auch fuer CGI-MP)
cbpr_xsd_path: "docs/specs/cbpr+nonpublic/(...).xsd" # CBPR+ XSD (optional, proprietaer)
seed: null
report_format: "docx"
```

---

## Excel-Format (v2)

Jede Zeile mit `TestcaseID` startet einen neuen Testfall. Folgezeilen ohne TestcaseID = zusaetzliche Transaktionen.

### Spalten

| Spalte | Pflicht | Beschreibung |
|--------|---------|-------------|
| TestcaseID | Ja | Eindeutige ID |
| Titel | Ja | Kurzbeschreibung |
| Ziel | Ja | Testziel |
| Erwartetes Ergebnis | Ja | `OK` oder `NOK` |
| Zahlungstyp | Nein | `SEPA`, `Domestic-QR`, `Domestic-IBAN`, `CBPR+` (auto wenn leer) |
| Betrag | Nein | Dezimalzahl (wird generiert wenn leer) |
| Waehrung | Nein | ISO 4217 (wird abgeleitet wenn leer) |
| Debtor IBAN | Ja | IBAN des Auftraggebers |
| Debtor Name | Nein | Name (wird generiert wenn leer) |
| Debtor BIC | Nein | BIC des Auftraggebers |
| Creditor Name | Nein | Name (wird generiert wenn leer) |
| Creditor IBAN | Nein | IBAN (wird passend generiert) |
| Creditor BIC | Nein | BIC des Beguenstigten |
| Verwendungszweck | Nein | Freitext-Zahlungsreferenz |
| ViolateRule | Nein | Rule-ID fuer Regelverstoss (z.B. `BR-SEPA-001`) |
| Weitere Testdaten | Nein | Key=Value Overrides (z.B. `ChrgBr=DEBT; CtgyPurp.Cd=SALA`) |
| **Standard** | Nein | **`sps2025`** (Default), **`cgi-mp`** oder **`cbpr+2026`** |
| Bemerkungen | Nein | Freitext |

---

## Zahlungstypen

| Typ | SPS-Typ | Waehrung | Besonderheiten |
|-----|---------|---------|----------------|
| **SEPA** | S | EUR | SvcLvl=SEPA, ChrgBr=SLEV, Name max. 70 Zeichen |
| **Domestic-QR** | D | CHF/EUR | QR-IBAN (IID 30000-31999), QRR-Referenz zwingend |
| **Domestic-IBAN** | D | CHF | Regulaere CH-IBAN, SCOR optional, keine QRR |
| **CBPR+** | X | vom User | Creditor-Agent BIC Pflicht, UETR bei cbpr+2026 |

---

## Business Rules

**55+ Business Rules** in 12 Kategorien:

| Kategorie | Anzahl | Beschreibung |
|-----------|--------|-------------|
| **HDR** | 3 | Header: MsgId, NbOfTxs, CtrlSum |
| **GEN** | 8 | Uebergreifend: Betrag, Zeichensatz, BIC, Country-Code |
| **ADDR** | 3 | Adressen: Strukturiert Pflicht, TwnNm+Ctry |
| **REM** | 1 | Remittance: USTRD max 140 Zeichen |
| **CCY** | 1 | Waehrung: ISO 4217 Format |
| **SEPA** | 5 | SEPA: EUR, SLEV, Name max. 70 |
| **QR** | 7 | QR: QR-IBAN, QRR, keine SCOR |
| **IBAN** | 6 | Domestic-IBAN: CH/LI, keine QRR |
| **CBPR** | 5 | CBPR+: SLEV verboten, UETR Pflicht, Agent-Pflicht |
| **CGI** | 13 | CGI-MP: Adress-Rules, Remittance exklusiv, Reg. Reporting, Tax, leere Tags |
| **IBAN-V** | 2 | IBAN: Mod-97, Laengenvalidierung |
| **REF-V** | 1 | Referenz: SCOR ISO 11649 |

---

## Output

Pro Testlauf: `output/YYYY-MM-DD_HHMMSS/` mit XML-Dateien, Word-Report, JSON und JUnit-XML.

Vorab generierte Beispiele: `examples/` (122 XML-Dateien: 104 SPS + 10 CGI-MP + 8 CBPR+)

---

## Tests & Validierung

```bash
poetry run pytest                                    # 114 Unit Tests
poetry run python scripts/validate_external.py examples/  # Second-Opinion
```

### Externe Validierung

| Dienst | Fuer | URL |
|--------|------|-----|
| **SIX Validation Portal** | SPS 2025 | [validation.iso-payments.ch](https://validation.iso-payments.ch/sps/account/logon) |
| **SWIFT MyStandards** | CBPR+ SR2026 | [mystandards.swift.com](https://www2.swift.com/mystandards/) |
| **TreasuryHost** | pain.001 allgemein | [treasuryhost.eu](https://www.treasuryhost.eu/solutions/painp/) |

---

## Projektstruktur

```
iso20022tester/
├── config.yaml                          # Konfiguration (SPS + CBPR+ XSD Pfade)
├── schemas/
│   └── pain.001.001.09.ch.03.xsd       # SPS XSD (SIX Group, auch fuer CGI-MP)
├── docs/
│   ├── SDD_v2.md                        # Software Design Dokument
│   ├── roadmap/
│   │   └── REQ_tri_standard_sps_cbpr_cgimp.md  # Requirements Tri-Standard
│   ├── archive/                         # Archivierte Dokumente
│   └── specs/
│       ├── vergleich-sps-epc-sepa-2025.md
│       ├── vergleich-sps-cbprplus-2025.md
│       ├── cbpr+nonpublic/              # CBPR+ XSD (proprietaer, .gitignore)
│       └── cgi_nonpublic/               # CGI-MP Handbook (proprietaer, .gitignore)
├── templates/
│   └── testfaelle_comprehensive.xlsx    # 122 Testfaelle (SPS + CGI-MP + CBPR+)
├── examples/                            # 122 vorab generierte XML-Dateien
├── src/
│   ├── main.py / pipeline.py            # CLI + Pipeline
│   ├── models/testcase.py               # Standard Enum (sps2025/cgi-mp/cbpr+2026)
│   ├── xml_generator/
│   │   ├── pain001_builder.py           # XML-Aufbau
│   │   ├── builders.py                  # Wiederverwendbare Bausteine
│   │   └── standard_strategy.py         # Strategy Pattern (SPS/CGI-MP/CBPR+)
│   ├── payment_types/                   # SEPA, Domestic-QR/IBAN, CBPR+
│   ├── validation/
│   │   ├── xsd_validator.py             # Dual-XSD (SPS + CBPR+)
│   │   ├── rule_catalog.py              # 55+ Rules in 12 Kategorien
│   │   └── business_rules.py            # Validierungs- & Violation-Logik
│   └── reporting/                       # Word, JSON, JUnit
├── tests/                               # 114 Unit Tests
└── scripts/validate_external.py         # Second-Opinion-Validator
```

---

## Dokumentation

| Dokument | Beschreibung |
|----------|-------------|
| `docs/SDD_v2.md` | Software Design Dokument -- Architektur, Datenmodelle |
| `docs/roadmap/REQ_tri_standard_sps_cbpr_cgimp.md` | Requirements Tri-Standard (SPS + CGI-MP + CBPR+) |
| `docs/specs/vergleich-sps-epc-sepa-2025.md` | SPS vs. EPC SEPA Vergleich |
| `docs/specs/vergleich-sps-cbprplus-2025.md` | SPS vs. CBPR+ Vergleich |

---

## pacs.008 Test Generator (FI-to-FI Interbank)

Der pacs.008-Generator erzeugt **Financial Institution to Financial Institution Credit Transfer** Nachrichten fuer den **CBPR+ SR2026** Flavor. Hauptnutzen ist das Testen von **Inflows** (eingehende pacs.008 gegen die eigenen Systeme) und **Outflows** (ausgehende pacs.008 an Partner-FIs).

### Inflow vs Outflow

Das Excel kennt keinen dedizierten Richtungs-Flag. Die Richtung ergibt sich implizit aus den Agenten-BICs:

- **Outflow testen:** `InstgAgt BIC = eigener FI`, `InstdAgt BIC = Partner-FI`
- **Inflow testen:** `InstgAgt BIC = Partner-FI`, `InstdAgt BIC = eigener FI`

Das erzeugte XML (BAH + Document in einem BusinessMessage-Envelope) kann dann in die eigene Inbound-Pipeline eingespeist oder an den Partner-FI geschickt werden.

### Excel Template

`templates/testfaelle_pacs008_comprehensive.xlsx` enthaelt 50 Testcases (30 positive + 20 negative), die folgende Szenarien abdecken:

| Gruppe | Cases | Coverage |
|---|---|---|
| A — Basis-Positiv | TC-PCS-001..010 | 10 Waehrungen/Korridore (EUR, USD, GBP, JPY, CHF, CNY, SGD, AUD, CAD, HKD) |
| B — Intermediary Agents | TC-PCS-011..015 | 1-Hop, 2-Hop, 3-Hop Chains; Fedwire ClrSysMmbId statt BIC |
| C — Ultimate Parties + LEI | TC-PCS-016..020 | UltmtDbtr, UltmtCdtr, Dbtr/Cdtr LEI, Intercompany-Chain |
| D — Purpose / Charges | TC-PCS-021..025 | PurposeCode, CategoryPurpose (SALA, SUPP, TRAD), ChrgBr (DEBT, CRED, SHAR) |
| E — Clearing / Settlement | TC-PCS-026..030 | CdtrAgt via Fedwire ABA, SttlmMtd INGA, T+2 Settlement, High-value |
| F — Negative Tests | TC-PCS-N01..N20 | ViolateRule pro Regel, gestreut ueber mehrere Korridore |

Neue Cases koennen mit dem Generator-Script `scripts/generate_pacs008_testcases.py` deterministisch erzeugt werden.

### Excel-Spalten (Auszug)

```
TestcaseID, Titel, Ziel, Erwartetes Ergebnis, Flavor,
BAH From BIC, BAH To BIC,
InstgAgt BIC, InstdAgt BIC,
Debtor Name, Debtor {Strasse,Hausnummer,PLZ,Ort,Land}, Debtor IBAN, DbtrAgt BIC, DbtrAgt ClrSysMmbId,
IntrmyAgt1 BIC, IntrmyAgt1 ClrSysMmbId, IntrmyAgt2 BIC, IntrmyAgt3 BIC,
Creditor Name, Creditor {Strasse,Hausnummer,PLZ,Ort,Land}, Creditor IBAN, Creditor Kontonummer, Creditor Kontoschema, CdtrAgt BIC, CdtrAgt ClrSysMmbId,
IntrBkSttlmAmt, Waehrung, IntrBkSttlmDt, SttlmMtd,
ChrgBr, UETR,
PurposeCode, CategoryPurpose, Verwendungszweck,
ViolateRule, Weitere Testdaten, Bemerkungen
```

`Weitere Testdaten` akzeptiert Dot-Notation-Overrides wie `IntrmyAgt1.FinInstnId.BICFI=CHASUS33XXX` oder `UltmtDbtr.Nm=Muster Holding AG`.

### BusinessMessage-Envelope

Jedes generierte pacs.008-File enthaelt BAH + Document in einem einzigen XML-Wrapper (der Form, die auch SWIFT MyStandards + FINaplo erwarten):

```xml
<BusinessMessage>
  <AppHdr xmlns="urn:iso:std:iso:20022:tech:xsd:head.001.001.02">
    <Fr>...</Fr>
    <To>...</To>
    <BizMsgIdr>MSG...</BizMsgIdr>
    <MsgDefIdr>pacs.008.001.08</MsgDefIdr>
    <BizSvc>swift.cbprplus.02</BizSvc>
    <CreDt>2026-04-06T14:30:00+00:00</CreDt>
  </AppHdr>
  <Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
    <FIToFICstmrCdtTrf>
      <GrpHdr>...</GrpHdr>
      <CdtTrfTxInf>...</CdtTrfTxInf>
    </FIToFICstmrCdtTrf>
  </Document>
</BusinessMessage>
```

### Business Rules BR-CBPR-PACS-\*

15 Business Rules spezifisch fuer CBPR+ pacs.008 (Kategorie `CBPR-PACS` im Rule-Katalog):

| ID | Beschreibung |
|---|---|
| BR-CBPR-PACS-001 | UETR (ISO 17442) ist Pflicht auf PmtId |
| BR-CBPR-PACS-002 | InstgAgt muss identifiziert sein (BICFI oder ClrSysMmbId) |
| BR-CBPR-PACS-003 | InstdAgt muss identifiziert sein |
| BR-CBPR-PACS-004 | SttlmMtd muss INDA oder INGA sein (COVE out of scope, CLRG nicht in CBPR+) |
| BR-CBPR-PACS-005 | Creditor-Adresse muss strukturiert sein |
| BR-CBPR-PACS-006 | Debtor-Adresse muss strukturiert sein |
| BR-CBPR-PACS-007 | BAH MsgDefIdr muss 'pacs.008.001.08' sein |
| BR-CBPR-PACS-008 | BAH BizSvc muss 'swift.cbprplus.02' sein |
| BR-CBPR-PACS-009 | IntrBkSttlmDt muss ein Banktag sein |
| BR-CBPR-PACS-010 | ChrgBr muss DEBT/CRED/SHAR sein |
| BR-CBPR-PACS-011 | Waehrung muss ISO 4217 sein |
| BR-CBPR-PACS-012 | ChrgsInf: jeder Eintrag braucht Agt |
| BR-CBPR-PACS-013 | NbOfTxs muss der Anzahl CdtTrfTxInf entsprechen |
| BR-CBPR-PACS-014 | CtrlSum muss Summe der IntrBkSttlmAmt sein |
| BR-CBPR-PACS-015 | UETR muss UUIDv4-Format haben |

### FINaplo External Validation

Optionale externe Validation gegen die [FINaplo Financial Messaging API](https://finaplo-apis.paymentcomponents.com) von Payment Components.

**Setup:**

1. Account auf [finaplo.paymentcomponents.com](https://finaplo.paymentcomponents.com) erstellen (7-Tage-Trial oder Paid-Tier)
2. API-Key in den gitignored Ordner `finaplo/` im Repo-Root legen:
   - `finaplo/api-key-<datum>.txt` — Bearer-Token (eine Zeile)
   - `finaplo/base-url-<datum>.txt` — Base-URL (`https://finaplo-apis.paymentcomponents.com` fuer LIVE)
   - Alternativ: Environment-Variablen `FINAPLO_API_KEY` und `FINAPLO_BASE_URL`
3. Run mit `--finaplo` Flag:
   ```bash
   poetry run python -m src.main \
       --input templates/testfaelle_pacs008_comprehensive.xlsx \
       --config config.yaml \
       --finaplo
   ```

Die Pipeline ruft pro positivem Testcase den Endpoint `/cbpr/validate` auf und integriert das Ergebnis als dritte Validation-Spalte im Report (XSD + Business Rules + FINaplo). Negative Testcases werden geskippt, um Quota zu sparen.

Bei erschoepfter Quota (HTTP 412 `subscription.expired`) wechselt die Pipeline in den Skip-Mode: alle verbleibenden Testcases laufen mit `finaplo_valid=None` weiter, der Run bricht nicht ab.

**Per-Flavor-Endpoint-Dispatch** (R1 aus dem Planning):

| Flavor | Endpoint |
|---|---|
| CBPR+ | `POST /cbpr/validate` ✅ aktiv |
| TARGET2 | `POST /target2/validate` (vorbereitet, V2) |
| SEPA | `POST /sepa/{scheme}/validate` (vorbereitet, V2) |

### Weiterfuehrende Dokumentation

- `docs/roadmap/2026-04-06_pacs008_implementation_plan.md` — V1-Implementation-Plan mit 13 Work Packages
- `docs/roadmap/2026-04-06_pacs008_finaplo_auto_repair_log.md` — WP-12 Auto-Repair-Session-Log
- `docs/roadmap/2026-04-06_pain001_pacs008_chain_analysis.md` — Deep-Dive fuer pain.001→pacs.008 Chain-Derivation (V2 Idee)
- `docs/roadmap/2026-04-06_correspondent_lookup_map.md` — Deep-Dive fuer statische Correspondent-Bank-Map (V2 Idee)

---

## Lizenz

Proprietaer. SPS XSD: Copyright SIX Group. CBPR+ XSD: Copyright SWIFT (nicht im Repo). CGI-MP Handbook: Copyright SWIFT (nicht im Repo).
