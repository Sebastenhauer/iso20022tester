# Software Design Dokument: ISO 20022 pain.001 Test Generator

**Projekt:** ISO 20022 pain.001 XML Test Generator
**Version:** 2.1
**Datum:** 20. März 2026
**Status:** Finalisiertes Design
**Basis:** SDD v1.2, Anforderungsdokument v1.1, SPS 2025 Spezifikationen

---

## 1. Systemübersicht

Das System automatisiert die Erstellung von ISO 20022-konformen pain.001.001.09-Zahlungsdateien auf Basis von Excel-Testfalldefinitionen. Es stellt sicher, dass generierte Dateien sowohl schema-valide (XSD) als auch fachlich korrekt gemäß den Swiss Payment Standards (SPS 2025) sind.

**Scope Phase 1:** Excel-Input → XML-Generierung → Validierung → Output & Reporting
**Scope Phase 2 (geplant):** API-Integration, Response-Vergleich (nicht Teil dieses Dokuments)

---

## 2. Technologie-Stack

| Komponente | Technologie | Zweck |
|-----------|------------|-------|
| Sprache | Python 3.10+ | Laufzeitumgebung |
| Paketmanagement | Poetry | Deterministische Abhängigkeiten |
| Datenvalidierung | Pydantic v2 | Modelle mit `decimal.Decimal` für finanzielle Präzision |
| XML-Verarbeitung | lxml | XSD-Validierung, XML-Generierung, Namespace-Management |
| Excel-Schnittstelle | openpyxl | Lesen der Testfalldefinitionen |
| Testdaten | faker | Reproduzierbare Zufallsdaten mit globalem Seed |
| Word-Output | python-docx | Fachlicher Revisionsbericht |
| Konfiguration | PyYAML | `config.yaml` Handling |
| CLI | argparse | Kommandozeileninterface |
| Feiertagskalender | workalendar | TARGET2- und SIX-Bankarbeitstage |
| Caching | SQLite/JSON | Semantic Caching (Infrastruktur vorbereitet für KI-Mapping) |

### 2.1 Entscheidung: KI-Mapping in Phase 1

Das in SDD v1 spezifizierte Pydantic-AI-Mapping wird in Phase 1 **nicht** implementiert. Stattdessen wird ein **deterministisches Mapping** verwendet:

- `Weitere Testdaten` enthält Key=Value-Paare (z.B. `Cdtr.Nm=Müller AG`)
- Keys werden gegen eine statische Mapping-Tabelle (Key → XPath) aufgelöst
- Unbekannte Keys erzeugen eine Fehlermeldung

**Begründung:** Für Phase 1 sind die Input-Felder bekannt und endlich. Ein deterministischer Ansatz ist zuverlässiger, braucht keinen API-Key und ist vollständig reproduzierbar.

Die Caching-Infrastruktur (SQLite/JSON) wird trotzdem angelegt, damit eine spätere KI-Integration nahtlos möglich ist.

---

## 3. Architektur

### 3.1 Modul-Übersicht

```
┌─────────────────────────────────────────────────────────┐
│                        CLI (main.py)                    │
│              argparse: --input / --config               │
└──────────┬──────────────────────────────────┬───────────┘
           │                                  │
           ▼                                  ▼
┌─────────────────────┐           ┌──────────────────────┐
│   Input Handler     │           │   Config Loader      │
│   (Excel-Parser)    │           │   (config.yaml)      │
└──────────┬──────────┘           └──────────┬───────────┘
           │                                  │
           ▼                                  │
┌─────────────────────┐                       │
│   Mapping Engine    │◄──────────────────────┘
│   (deterministisch) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Data Factory      │
│   (faker + Seed)    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌──────────────────────┐
│   XML Generator     │────►│  Payment Type Modules │
│   (lxml, pain.001)  │     │  SEPA / Dom-QR /     │
└──────────┬──────────┘     │  Dom-IBAN / CBPR+    │
           │                └──────────────────────┘
           ▼
┌─────────────────────┐
│  Validation Engine  │
│  XSD + Bus. Rules   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Reporting Module   │
│  .docx / JSON /     │
│  JUnit-XML          │
└─────────────────────┘
```

### 3.2 Projektstruktur

```
iso20022tester/
├── pyproject.toml
├── config.yaml
├── schemas/
│   └── pain.001.001.09.ch.03.xsd
├── docs/
│   ├── SDD_v2.md
│   └── specs/
│       ├── business-rules-sps-2025-de.md
│       └── ig-credit-transfer-sps-2025-de.md
├── templates/
│   └── testfaelle_vorlage.xlsx          # Beispiel-Excel mit je 1 pos/neg TC pro Typ
├── src/
│   ├── __init__.py
│   ├── main.py                          # CLI Entry Point
│   ├── config.py                        # Config-Loader (YAML → Pydantic)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── testcase.py                  # Pydantic-Modelle: TestCase, Transaction
│   │   └── config.py                    # Pydantic-Modell: AppConfig
│   ├── input_handler/
│   │   ├── __init__.py
│   │   └── excel_parser.py              # Excel-Einlesen + Validierung
│   ├── mapping/
│   │   ├── __init__.py
│   │   ├── field_mapper.py              # Deterministisches Key→XPath Mapping
│   │   └── mapping_table.py             # Statische Mapping-Definitionen
│   ├── data_factory/
│   │   ├── __init__.py
│   │   ├── generator.py                 # Faker-basierte Datengenerierung
│   │   ├── iban.py                      # IBAN-Generierung (Mod-97)
│   │   └── reference.py                 # QRR/SCOR-Referenz-Generierung
│   ├── xml_generator/
│   │   ├── __init__.py
│   │   ├── pain001_builder.py           # XML-Aufbau (A/B/C-Level)
│   │   └── namespace.py                 # Namespace-Konstanten
│   ├── payment_types/
│   │   ├── __init__.py
│   │   ├── base.py                      # Abstrakte Basisklasse
│   │   ├── sepa.py                      # Typ S: SEPA Credit Transfer
│   │   ├── domestic_qr.py               # Typ D: QR-Zahlung (QR-IBAN)
│   │   ├── domestic_iban.py             # Typ D: Klassische IBAN-Zahlung
│   │   └── cbpr_plus.py                 # Typ X: Cross-Border
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── xsd_validator.py             # XSD-Schema-Validierung
│   │   └── business_rules.py            # Business-Rule-Engine
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── word_reporter.py             # .docx-Bericht
│   │   ├── json_reporter.py             # JSON-Ergebnis
│   │   └── junit_reporter.py            # JUnit-XML für CI/CD
│   └── cache/
│       ├── __init__.py
│       └── mapping_cache.py             # SQLite/JSON Cache (vorbereitet)
└── tests/
    ├── __init__.py
    ├── test_excel_parser.py
    ├── test_iban.py
    ├── test_reference.py
    ├── test_xml_generator.py
    ├── test_business_rules.py
    ├── test_payment_types.py
    └── test_e2e.py                      # E2E mit Beispiel-Excel
```

---

## 4. Datenmodellierung

### 4.1 Pydantic-Modelle

```python
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum

class PaymentType(str, Enum):
    SEPA = "SEPA"
    DOMESTIC_QR = "Domestic-QR"
    DOMESTIC_IBAN = "Domestic-IBAN"
    CBPR_PLUS = "CBPR+"

class ExpectedResult(str, Enum):
    OK = "OK"
    NOK = "NOK"

class DebtorInfo(BaseModel):
    """Debtor-Daten werden vollständig aus dem Excel eingelesen (Pflicht)."""
    name: str                            # Debtor-Name (Pflicht)
    iban: str                            # Debtor-IBAN (Pflicht)
    bic: Optional[str] = None           # Debtor-BIC (optional)
    street: Optional[str] = None        # Strasse
    building: Optional[str] = None      # Hausnummer
    postal_code: Optional[str] = None   # PLZ
    town: Optional[str] = None          # Ort
    country: str = "CH"                 # Land (Default: CH)

class TestCase(BaseModel):
    testcase_id: str
    titel: str
    ziel: str
    expected_result: ExpectedResult
    payment_type: PaymentType
    amount: Decimal = Field(..., decimal_places=2)
    currency: str
    debtor: DebtorInfo                   # Vollständig aus Excel, kein Default-Debtor
    overrides: Dict[str, str] = {}       # Parsed aus "Weitere Testdaten"
    violate_rule: Optional[str] = None   # Extrahiert aus ViolateRule=...
    tx_count: int = 1                    # Extrahiert aus TxCount=...
    expected_api_response: Optional[str] = None
    remarks: Optional[str] = None

class Transaction(BaseModel):
    end_to_end_id: str
    amount: Decimal = Field(..., decimal_places=2)
    currency: str
    creditor_name: str
    creditor_iban: str
    creditor_address: Optional[Dict[str, str]] = None
    charge_bearer: Optional[str] = None
    remittance_info: Optional[Dict[str, str]] = None
    overrides: Dict[str, str] = {}

class PaymentInstruction(BaseModel):
    msg_id: str
    pmt_inf_id: str
    pmt_mtd: str = "TRF"                # Immer "TRF" (kein CHK)
    cre_dt_tm: str
    reqd_exctn_dt: str
    debtor: DebtorInfo                   # Aus Excel übernommen
    service_level: Optional[str] = None
    local_instrument: Optional[str] = None
    category_purpose: Optional[str] = None
    charge_bearer: Optional[str] = None
    transactions: List[Transaction]

class AppConfig(BaseModel):
    output_path: str
    xsd_path: str = "schemas/pain.001.001.09.ch.03.xsd"
    seed: Optional[int] = None
    report_format: str = "docx"          # "docx" oder "txt"
```

### 4.2 Finanzielle Präzision

Alle Beträge werden als `decimal.Decimal` geführt. Kontrollsummen (`NbOfTxs`, `CtrlSum`) werden aus den Einzelbeträgen berechnet, nicht aus Floats.

---

## 5. Komponentendetails

### 5.1 Input Handler (excel_parser.py)

**Pflicht-Spalten** (Reihenfolge fix, gemäß FR-04):

| # | Spalte | Pflicht | Beschreibung |
|---|--------|---------|-------------|
| 1 | TestcaseID | Ja | Eindeutige ID; Zeilen ohne ID werden übersprungen |
| 2 | Titel | Ja | Kurzbeschreibung des Testfalls |
| 3 | Ziel | Ja | Testziel |
| 4 | Erwartetes Ergebnis | Ja | `OK` oder `NOK` |
| 5 | Zahlungstyp | Ja | `SEPA`, `Domestic-QR`, `Domestic-IBAN`, `CBPR+` |
| 6 | Betrag | Ja | Betrag als Dezimalzahl |
| 7 | Währung | Ja | ISO 4217 Währungscode |
| 8 | Debtor Infos | Ja | `Key=Value; Key=Value` Format. Pflicht-Keys: `IBAN`, `Name`. Optional: `BIC`, `Strasse`, `Hausnummer`, `PLZ`, `Ort`, `Land` |
| 9 | Weitere Testdaten | Nein | Key=Value-Paare für Overrides |
| 10 | Erwartete API-Antwort | Nein | Phase 2 |
| 11 | Ergebnis (OK/NOK) | Nein | Wird vom System befüllt |
| 12 | Bemerkungen | Nein | Freitext |

**Verhalten:**
- Spaltenvalidierung beim Start (FR-05): Fehler bei fehlenden Pflichtspalten → Abbruch
- Zeilen ohne TestcaseID → Überspringen (FR-03)
- Zeilen mit TestcaseID aber ungültigen Pflichtfeldern → Sammelfehler, Abbruch nach vollständiger Prüfung (FR-11)
- Spezialkeys aus `Weitere Testdaten` extrahieren: `ViolateRule`, `TxCount`

### 5.2 Mapping Engine (deterministisch)

Statische Mapping-Tabelle: Key → XPath im pain.001-Schema.

Beispiele:

| Key | XPath | Ebene |
|-----|-------|-------|
| `Cdtr.Nm` | `CdtTrfTxInf/Cdtr/Nm` | C |
| `Cdtr.PstlAdr.StrtNm` | `CdtTrfTxInf/Cdtr/PstlAdr/StrtNm` | C |
| `Cdtr.PstlAdr.TwnNm` | `CdtTrfTxInf/Cdtr/PstlAdr/TwnNm` | C |
| `Cdtr.PstlAdr.Ctry` | `CdtTrfTxInf/Cdtr/PstlAdr/Ctry` | C |
| `CdtrAcct.IBAN` | `CdtTrfTxInf/CdtrAcct/Id/IBAN` | C |
| `CdtrAgt.BICFI` | `CdtTrfTxInf/CdtrAgt/FinInstnId/BICFI` | C |
| `ChrgBr` | `ChrgBr` | B oder C |
| `SvcLvl.Cd` | `PmtTpInf/SvcLvl/Cd` | B |
| `LclInstrm.Cd` | `PmtTpInf/LclInstrm/Cd` | B |
| `CtgyPurp.Cd` | `PmtTpInf/CtgyPurp/Cd` | B |
| `RmtInf.Ustrd` | `CdtTrfTxInf/RmtInf/Ustrd` | C |
| `ReqdExctnDt` | `ReqdExctnDt/Dt` | B |

Unbekannte Keys → Fehlermeldung mit Hinweis auf gültige Keys.

### 5.3 Data Factory

**Seed-Mechanismus (FR-31):**
- Globaler Seed pro Testlauf (aus `config.yaml`)
- Beeinflusst: Namen, Adressen, IBANs, MsgId, PmtInfId, EndToEndId
- **Ausnahme:** `CreDtTm` spiegelt immer den tatsächlichen Generierungszeitpunkt

**IBAN-Generierung (FR-28):**
- Mod-97 prüfziffervalide IBANs
- Länderspezifisch: CH (21 Stellen), DE (22 Stellen), etc.
- QR-IBANs: IID im Bereich 30000–31999
- Reguläre CH-IBANs: IID außerhalb 30000–31999

**Referenz-Generierung:**
- **QRR:** 26 numerische Stellen + Mod-10-Prüfziffer (27 Stellen gesamt)
- **SCOR:** `RF` + 2-stellige Prüfziffer + max. 21 alphanumerische Zeichen (max. 25 gesamt)

**Bankarbeitstag-Berechnung (FR-26):**
- `ReqdExctnDt` = nächster Bankarbeitstag ab Generierungszeitpunkt
- SEPA: TARGET2-Kalender (via `workalendar.europe.EuropeanCentralBank`)
- Domestic-QR, Domestic-IBAN, CBPR+: Schweizer Bankfeiertage (via `workalendar.europe.Switzerland`)

**Zeichensatz-Validierung (SPS Latin-1 Subset):**
- Alle generierten und vom User eingegebenen Daten werden gegen den SPS-Zeichensatz validiert
- Erlaubt: `a-z A-Z 0-9 / - ? : ( ) . , ' + Leerzeichen`
- Sonderzeichen wie `ä ö ü` werden in faker-generierten Daten durch ASCII-Äquivalente ersetzt
- Fehlermeldung bei ungültigen Zeichen in User-Overrides

**Adressgenerierung:**
- Strukturierte Adressen: StrtNm, BldgNb, PstCd, TwnNm, Ctry
- Länderspezifisch via faker-Locales (`de_CH`, `de_DE`, etc.)

### 5.4 XML Generator (pain001_builder.py)

Baut die pain.001.001.09 XML-Struktur mit lxml unter striktem Namespace-Management.

**Namespace:**
```
urn:iso:std:iso:20022:tech:xsd:pain.001.001.09
```

**XML-Aufbau:**

```
Document
└── CstmrCdtTrfInitn
    ├── GrpHdr (A-Level, genau 1x)
    │   ├── MsgId
    │   ├── CreDtTm
    │   ├── NbOfTxs
    │   ├── CtrlSum
    │   └── InitgPty/Nm
    └── PmtInf (B-Level, 1..n)
        ├── PmtInfId
        ├── PmtMtd (= "TRF")
        ├── NbOfTxs
        ├── CtrlSum
        ├── PmtTpInf
        │   ├── SvcLvl/Cd
        │   └── LclInstrm/Cd (optional)
        ├── ReqdExctnDt/Dt
        ├── Dbtr/Nm + PstlAdr
        ├── DbtrAcct/Id/IBAN
        ├── DbtrAgt/FinInstnId/BICFI
        ├── ChrgBr (optional, wenn auf B-Level)
        └── CdtTrfTxInf (C-Level, 1..n)
            ├── PmtId
            │   ├── InstrId (optional)
            │   └── EndToEndId
            ├── Amt/InstdAmt (Ccy + Betrag)
            ├── CdtrAgt/FinInstnId (optional)
            ├── Cdtr/Nm + PstlAdr
            ├── CdtrAcct/Id/IBAN
            ├── ChrgBr (optional, wenn auf C-Level)
            └── RmtInf (optional)
                ├── Strd/CdtrRefInf (QRR/SCOR)
                └── Ustrd (Freitext)
```

**Regeln:**
- `PmtMtd` ist immer `TRF` (Transfer) — kein `CHK` (Bank Check) in Phase 1
- `ChrgBr` darf nur auf B-Level **oder** C-Level stehen, nicht auf beiden gleichzeitig
- `NbOfTxs` und `CtrlSum` werden auf A- und B-Level korrekt berechnet
- Bei `TxCount > 1` werden mehrere `CdtTrfTxInf` innerhalb eines `PmtInf` erzeugt

### 5.5 Payment Type Modules

Jeder Zahlungstyp implementiert eine gemeinsame Basisklasse mit folgenden Methoden:
- `get_defaults()` → Dict mit Typ-spezifischen Defaultwerten
- `validate(payment_instruction)` → Liste von Regelverletzungen
- `generate_creditor_account()` → Passender IBAN-Typ

#### Mapping SPS-Typen → Projekt-Zahlungstypen

| Projekt | SPS-Typ | Beschreibung |
|---------|---------|-------------|
| SEPA | Typ S | Euro-Zahlungen im SEPA-Raum |
| Domestic-QR | Typ D | Inlandszahlung mit QR-IBAN |
| Domestic-IBAN | Typ D | Inlandszahlung mit regulärer IBAN |
| CBPR+ | Typ X | Cross-Border / Fremdwährung |

#### Typ S — SEPA

| Feld | Regel |
|------|-------|
| Währung | EUR (zwingend) |
| SvcLvl/Cd | `SEPA` (zwingend) |
| ChrgBr | `SLEV` (zwingend, wenn angegeben) |
| Creditor-Name | Max. 70 Zeichen |
| Creditor-Konto | IBAN (zwingend) |
| Creditor-BIC | Optional |
| Betragsgrenzen | 0.01 – 999'999'999.99 |

#### Typ D — Domestic-QR

| Feld | Regel |
|------|-------|
| Währung | CHF oder EUR |
| Creditor-Konto | QR-IBAN (IID 30000–31999, zwingend) |
| Referenz | QRR (zwingend). SCOR ist **nicht** zulässig bei QR-IBAN |
| SvcLvl/Cd | Gemäß SPS (nicht `SEPA`) |
| Adresse | Strukturiert oder hybrid |
| Betragsgrenzen | 0.01 – 9'999'999'999.99 |

#### Typ D — Domestic-IBAN

| Feld | Regel |
|------|-------|
| Währung | CHF |
| Creditor-Konto | Reguläre CH-IBAN (nicht QR-IBAN) |
| Referenz | SCOR (optional), keine QRR erlaubt |
| SvcLvl/Cd | Gemäß SPS (nicht `SEPA`) |
| Betragsgrenzen | 0.01 – 9'999'999'999.99 |

#### Typ X — CBPR+

| Feld | Regel |
|------|-------|
| Währung | Vom User vorgegeben (kein Default, Pflicht) |
| Creditor-Konto | IBAN oder Kontonummer |
| Creditor-Agent | Pflicht-Input vom User (BIC via `CdtrAgt.BICFI` in Overrides). Fehlermeldung wenn nicht angegeben |
| PmtMtd | Immer `TRF` (kein CHK) |
| SvcLvl/Cd | Gemäß CBPR+-Regelwerk (nicht `SEPA`) |
| UltmtDbtr/UltmtCdtr | Strukturierte Adresse zwingend |

### 5.6 Validation Engine

Zweistufige Validierung:

**Stufe 1: XSD-Validierung**
- Validierung gegen `schemas/pain.001.001.09.ch.03.xsd`
- Schema-invalide Dateien werden **nicht** gespeichert (FR-81)
- Fehlermeldung enthält XSD-Fehlerbeschreibung + betroffenes Element (FR-82)

**Stufe 2: Business-Rule-Validierung**
- Läuft nur nach erfolgreicher XSD-Validierung (FR-83)
- Regeln als parametrisierbare Funktionen
- Jede Regel hat eine interne ID (z.B. `BR-SEPA-001`)

**Pass/Fail-Logik:**

| Erwartetes Ergebnis | Validierung | Bewertung |
|-------------------|------------|-----------|
| OK | Alle Prüfungen bestanden | **Pass** |
| NOK | Mind. 1 Business Rule verletzt | **Pass** |
| OK | Validierungsfehler | **Fail** |
| NOK | Alle Prüfungen bestanden | **Fail** |

**Negative Testing (FR-30):**
- `ViolateRule=<RuleID>` triggert gezielte Regelverletzung
- XSD-Validität bleibt erhalten (Schema darf nicht verletzt werden)
- Nur Business Rules werden verletzt

### 5.7 Business Rule Katalog

Die folgenden Business Rules werden aus den SPS-2025-Dokumenten abgeleitet und als Code-Module implementiert. Die IDs sind projektintern.

#### Header-Regeln (A-Level)

| Rule-ID | Beschreibung | Prüfung |
|---------|-------------|---------|
| BR-HDR-001 | MsgId Eindeutigkeit | MsgId muss pro Testlauf eindeutig sein |
| BR-HDR-002 | NbOfTxs Konsistenz | NbOfTxs im GrpHdr = Summe aller Transaktionen |
| BR-HDR-003 | CtrlSum Konsistenz | CtrlSum im GrpHdr = Summe aller Beträge |
| BR-HDR-004 | InitgPty vorhanden | InitgPty/Nm muss gesetzt sein |

#### Zahlungstyp-übergreifende Regeln (B/C-Level)

| Rule-ID | Beschreibung | Prüfung |
|---------|-------------|---------|
| BR-GEN-001 | NbOfTxs B-Level | NbOfTxs im PmtInf = Anzahl CdtTrfTxInf |
| BR-GEN-002 | CtrlSum B-Level | CtrlSum im PmtInf = Summe der Beträge im Block |
| BR-GEN-003 | ChrgBr Platzierung | ChrgBr nur auf B-Level ODER C-Level, nicht beide |
| BR-GEN-004 | UltmtDbtr Platzierung | UltmtDbtr nur auf B-Level ODER C-Level, nicht beide |
| BR-GEN-005 | ReqdExctnDt Bankarbeitstag | ReqdExctnDt muss ein Bankarbeitstag sein |
| BR-GEN-006 | Adresse: Name bei PstlAdr | Wenn PstlAdr vorhanden → Nm muss gesetzt sein |
| BR-GEN-007 | Adresse: TwnNm + Ctry | Wenn PstlAdr → TwnNm und Ctry zwingend |
| BR-GEN-008 | Adresse: AdrLine max 2 | Max. 2 AdrLine-Elemente, je max. 70 Zeichen |
| BR-GEN-009 | Referenzfeld-Zeichensatz | InstrId, EndToEndId, PmtInfId: kein "/" am Anfang/Ende, kein "//" |
| BR-GEN-010 | Betrag > 0 | InstdAmt muss > 0 sein |
| BR-GEN-011 | Gruppierungsregel | Alle Transaktionen in einem PmtInf müssen identische SvcLvl, LclInstrm, CtgyPurp haben |
| BR-GEN-012 | SPS-Zeichensatz | Alle Textfelder müssen dem SPS Latin-1 Subset entsprechen (`a-z A-Z 0-9 / - ? : ( ) . , ' +`) |

#### SEPA-Regeln (Typ S)

| Rule-ID | Beschreibung | Prüfung |
|---------|-------------|---------|
| BR-SEPA-001 | Währung EUR | Währung muss EUR sein |
| BR-SEPA-002 | SvcLvl = SEPA | SvcLvl/Cd muss "SEPA" sein |
| BR-SEPA-003 | ChrgBr = SLEV | Wenn ChrgBr angegeben, muss es "SLEV" sein |
| BR-SEPA-004 | Creditor-Name max 70 | Cdtr/Nm max. 70 Zeichen |
| BR-SEPA-005 | Creditor IBAN | CdtrAcct muss IBAN enthalten |
| BR-SEPA-006 | Betragsgrenzen | 0.01 ≤ Betrag ≤ 999'999'999.99 |

#### Domestic-QR-Regeln (Typ D, QR-IBAN)

| Rule-ID | Beschreibung | Prüfung |
|---------|-------------|---------|
| BR-QR-001 | QR-IBAN Pflicht | CdtrAcct muss QR-IBAN sein (IID 30000–31999) |
| BR-QR-002 | QRR Pflicht | Bei QR-IBAN muss QR-Referenz (QRR) vorhanden sein |
| BR-QR-003 | Keine SCOR bei QR-IBAN | SCOR-Referenz ist bei QR-IBAN nicht zulässig |
| BR-QR-004 | Währung CHF/EUR | Währung muss CHF oder EUR sein |
| BR-QR-005 | SvcLvl ≠ SEPA | SvcLvl/Cd darf nicht "SEPA" sein |
| BR-QR-006 | QRR Format | QRR: 27 Stellen numerisch, letzte Stelle = Mod-10-Prüfziffer |

#### Domestic-IBAN-Regeln (Typ D, reguläre IBAN)

| Rule-ID | Beschreibung | Prüfung |
|---------|-------------|---------|
| BR-IBAN-001 | Reguläre CH-IBAN | CdtrAcct darf keine QR-IBAN sein |
| BR-IBAN-002 | Keine QRR | QR-Referenz ist bei regulärer IBAN nicht zulässig |
| BR-IBAN-003 | SCOR optional + valide | SCOR-Referenz optional. Wenn vorhanden: Format (RF + 2-stellige Mod-97-Prüfziffer + max. 21 Zeichen) und Prüfziffer werden validiert |
| BR-IBAN-004 | Währung CHF | Währung muss CHF sein |
| BR-IBAN-005 | SvcLvl ≠ SEPA | SvcLvl/Cd darf nicht "SEPA" sein |

#### CBPR+-Regeln (Typ X)

| Rule-ID | Beschreibung | Prüfung |
|---------|-------------|---------|
| BR-CBPR-001 | Währung vom User | Währung und Zielland müssen explizit angegeben sein |
| BR-CBPR-002 | SvcLvl ≠ SEPA | SvcLvl/Cd darf nicht "SEPA" sein |
| BR-CBPR-003 | UltmtDbtr strukturiert | UltmtDbtr muss strukturierte Adresse haben |
| BR-CBPR-004 | UltmtCdtr strukturiert | UltmtCdtr muss strukturierte Adresse haben |
| BR-CBPR-005 | Creditor-Agent Pflicht | Creditor-Agent (BIC) muss vom User in Overrides angegeben werden. Fehlermeldung wenn fehlend |

#### IBAN-Validierungsregeln

| Rule-ID | Beschreibung | Prüfung |
|---------|-------------|---------|
| BR-IBAN-V01 | Mod-97 Prüfziffer | IBAN-Prüfziffer muss Mod-97 bestehen |
| BR-IBAN-V02 | Längenprüfung | IBAN-Länge muss zum Ländercode passen |
| BR-IBAN-V03 | QR-IBAN Erkennung | IID 30000–31999 = QR-IBAN |
| BR-REF-V01 | SCOR Prüfziffer | SCOR-Referenz: RF + Mod-97-Prüfziffer wird validiert |
| BR-REF-V02 | QRR Prüfziffer | QRR: Mod-10 (rekursiv) Prüfziffer der letzten Stelle wird validiert |

### 5.8 Reporting Module

**Ausgabeordner:**
- Übergeordneter Pfad: aus `config.yaml`
- Pro Testlauf: Unterordner `YYYY-MM-DD_HHMMSS/`

**Dateinamen (XML):**
`[Timestamp]_[TestCaseID]_[UUID_Short].xml`

**Zusammenfassung (FR-94–FR-96):**

Format: `.docx` (bevorzugt), `.txt` als Fallback (konfigurierbar).

Inhalt:
- Testlauf-Datum/-Uhrzeit
- Input-Excel-Dateiname
- Anzahl Testfälle gesamt / Pass / Fail
- Pro Testfall: TestcaseID, Titel, Zahlungstyp, XSD-Status, Business-Rule-Status (mit Rule-IDs), Pass/Fail, Bemerkungen

**JSON-Report:**
Strukturierte Ausgabe derselben Daten für maschinelle Weiterverarbeitung.

**JUnit-XML:**
Für CI/CD-Integration (z.B. Azure DevOps). Ein `<testcase>` pro TestcaseID.

### 5.9 Caching (vorbereitet)

SQLite-Datenbank oder JSON-Datei unter `.cache/mapping_cache.db`.

Schema:
```
input_key TEXT PRIMARY KEY,
xpath TEXT,
created_at TIMESTAMP,
source TEXT  -- "static" oder "ai"
```

In Phase 1 werden nur statische Mappings verwendet (`source = "static"`). Die Infrastruktur erlaubt spätere Ergänzung durch KI-generierte Mappings.

---

## 6. Konfiguration (config.yaml)

```yaml
# Ausgabepfad für generierte XML-Dateien und Reports
output_path: "./output"

# Pfad zum XSD-Schema (relativ zum Projektroot)
xsd_path: "schemas/pain.001.001.09.ch.03.xsd"

# Seed für reproduzierbare Zufallsdaten (optional, null = zufällig)
seed: null

# Report-Format: "docx" oder "txt"
report_format: "docx"
```

---

## 7. CLI-Interface

```bash
python src/main.py --input testfaelle.xlsx --config config.yaml
```

| Argument | Pflicht | Beschreibung |
|----------|---------|-------------|
| `--input` | Ja | Pfad zur Excel-Datei mit Testfällen |
| `--config` | Ja | Pfad zur config.yaml |
| `--seed` | Nein | Übersteuert den Seed aus config.yaml |
| `--verbose` | Nein | Ausführliche Konsolenausgabe |

Fehlermeldungen werden auf Deutsch ausgegeben (NF-10).

---

## 8. Negative Testing — Ablauf

1. Excel-Zeile hat `Erwartetes Ergebnis = NOK` und `ViolateRule=BR-SEPA-001`
2. System identifiziert die Regel `BR-SEPA-001` (Währung muss EUR sein)
3. Data Factory / XML Generator setzt bewusst eine andere Währung (z.B. CHF)
4. XSD-Validierung → Pass (Währung ist ein gültiger ISO-Code)
5. Business-Rule-Validierung → Fail bei BR-SEPA-001
6. Da erwartet = NOK und Rule verletzt → **Testfall = Pass**
7. XML wird gespeichert, Regelverletzung wird im Report dokumentiert

---

## 9. Beispiel-Excel Template

Das Template (`templates/testfaelle_vorlage.xlsx`) enthält mindestens 8 Testfälle:

| TestcaseID | Zahlungstyp | Erw. Ergebnis | Beschreibung |
|-----------|------------|--------------|-------------|
| TC-SEPA-001 | SEPA | OK | Positive SEPA-Zahlung |
| TC-SEPA-002 | SEPA | NOK | Negative SEPA (ViolateRule=BR-SEPA-001) |
| TC-QR-001 | Domestic-QR | OK | Positive QR-Zahlung |
| TC-QR-002 | Domestic-QR | NOK | Negative QR (ViolateRule=BR-QR-002) |
| TC-IBAN-001 | Domestic-IBAN | OK | Positive IBAN-Zahlung |
| TC-IBAN-002 | Domestic-IBAN | NOK | Negative IBAN (ViolateRule=BR-IBAN-004) |
| TC-CBPR-001 | CBPR+ | OK | Positive Cross-Border-Zahlung |
| TC-CBPR-002 | CBPR+ | NOK | Negative CBPR+ (ViolateRule=BR-CBPR-001) |

---

## 10. Geklärte Design-Entscheidungen (v2)

| Thema | Entscheidung |
|-------|-------------|
| Debtor-Daten | Werden vollständig aus dem Excel eingelesen (kein Default-Debtor in config.yaml) |
| Creditor-Agent CBPR+ | Muss vom User im Excel angegeben werden. Fehlermeldung wenn fehlend |
| SCOR-Validierung | Prüfziffer (RF + Mod-97) wird vollständig validiert |
| Feiertagskalender | `workalendar` (TARGET2 + Switzerland) |
| Zeichensatz | SPS Latin-1 Subset wird validiert, faker-Daten werden bereinigt |
| PmtMtd | Immer `TRF`, kein `CHK` in Phase 1 |
| KI-Mapping | Deterministisch in Phase 1, Caching-Infrastruktur vorbereitet |
| CLI | argparse |
| Dateinamen | `[Timestamp]_[TestCaseID]_[UUID_Short].xml` |

## 11. Offene Punkte

| OP-ID | Thema | Status |
|-------|-------|--------|
| OP-02 | Individuelle C-Level-Overrides bei TxCount>1 | Offen (Phase 1, Schritt 2) |
| OP-03 | Docker-Containerisierung | Offen (nicht in Phase 1) |
| OP-04 | Phase 2 API-Spezifikation | Offen (nach Phase-1-Abnahme) |
