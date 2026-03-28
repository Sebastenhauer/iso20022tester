# Requirements: Tri-Standard Support (SPS + CBPR+ + CGI-MP)

**Version:** 2.0
**Datum:** 28. Maerz 2026
**Status:** Entwurf
**Basis:** Bestehende Dual-Standard-Implementierung (SPS + CBPR+), CGI-MP WG1 User Handbook pain.001.001.09 Nov 2025

---

## 1. Hintergrund

### 1.1 Aktuelle Situation

Das System unterstuetzt zwei Standards fuer pain.001.001.09:
- **SPS 2025** (Swiss Payment Standards): Customer-to-Bank fuer Schweizer Zahlungen
- **CBPR+ SR2026** (SWIFT): Bank-to-Bank Relay-Szenario

Beide sind ueber die Excel-Spalte "Standard" pro Testfall waehlbar. Die XML-Generierung, XSD-Validierung und Business Rules sind standard-abhaengig via Strategy Pattern implementiert.

### 1.2 Problem

CBPR+ ist ein Bank-to-Bank-Standard. Fuer den primaeren Use Case **Corporate-to-Bank (C2B)** im internationalen Zahlungsverkehr fehlt der passende globale Standard. **CGI-MP** fuellt diese Luecke:

- CGI-MP ist der globale C2B-Standard (pain.001 von Corporate an Bank)
- CGI-MP nutzt das **Standard-ISO-XSD** (kein eigenes restriktives Schema)
- CGI-MP definiert Business Rules als Usage-Guideline-Schicht
- CGI-MP ist die Basis fuer CBPR+ Relay (CBPR+ ist eine Restriction von CGI-MP)

### 1.3 Ziel

Drei Standards pro Testfall: `sps2025`, `cbpr+2026`, `cgi-mp` (neu). End-to-End: Excel-Auswahl → XML-Generierung → XSD-Validierung → Business Rules → Reporting.

---

## 2. Standards im Vergleich

| Aspekt | SPS 2025 | CGI-MP | CBPR+ SR2026 |
|--------|----------|--------|-------------|
| **Scope** | C2B Schweiz | C2B global | B2B Relay |
| **XSD** | `pain.001.001.09.ch.03` | Standard ISO pain.001.001.09 | CBPR+ Restriction |
| **Eigenes XSD?** | Ja (im Repo) | **Nein** (SPS XSD genuegt) | Ja (proprietaer) |
| **Multi-Tx** | 1..n PmtInf, 1..n Tx | 1..n PmtInf, 1..n Tx | Genau 1/1 |
| **UETR** | Optional | Optional (empfohlen) | Pflicht |
| **ChrgBr** | DEBT/CRED/SHAR/SLEV | DEBT/CRED/SHAR/SLEV | DEBT/CRED/SHAR |
| **CtrlSum** | Ja (GrpHdr + PmtInf) | Ja (GrpHdr + PmtInf) | Entfaellt |
| **CreDtTm** | ISO 8601 lokal | ISO 8601 lokal | Pflicht UTC-Offset |
| **Zeichensatz** | SPS Latin-1 Subset | UTF-8 (voll) | FIN-X Restricted |
| **Adressen (ab Nov 2026)** | Strukturiert Pflicht | Strukturiert oder Hybrid | Strukturiert oder Hybrid |
| **Regulatory Reporting** | — | Ja (laenderspezifisch) | Wie CGI-MP |
| **Extended Structured Remittance** | CdtrRefInf (SCOR, QRR) | Voll (RfrdDocInf, RfrdDocAmt, CdtrRefInf, TaxRmt) | Wie CGI-MP |
| **Tax Component** | — | Ja (WHT Thailand/Philippines) | — |
| **Leere Tags** | Erlaubt (XSD-konform) | Verboten (Best Practice) | Verboten |

---

## 3. Betroffene Module und Aenderungen

### 3.1 Datenmodell (`src/models/testcase.py`)

Standard Enum erweitern:
```python
class Standard(str, Enum):
    SPS_2025 = "sps2025"
    CBPR_PLUS_2026 = "cbpr+2026"
    CGI_MP = "cgi-mp"
```

### 3.2 Excel-Parser (`src/input_handler/excel_parser.py`)

Standard-Spalte akzeptiert `cgi-mp` als neuen Wert. Keine strukturelle Aenderung — nur Validierung erweitern.

### 3.3 Strategy Pattern (`src/xml_generator/standard_strategy.py`)

Neue `CgiMpStrategy` Klasse:

```python
class CgiMpStrategy(StandardStrategy):
    """CGI-MP (Common Global Implementation — Market Practice).

    XML-Struktur identisch mit SPS (GrpHdr, PmtInf, CdtTrfTxInf).
    Unterschiede nur auf Business-Rule-Ebene und optionalen Elementen.
    """
    def grp_hdr_nb_of_txs(self, all_txs): return str(len(all_txs))
    def grp_hdr_ctrl_sum(self, all_txs): return str(sum(tx.amount for tx in all_txs))
    def pmt_inf_nb_of_txs(self, txs): return str(len(txs))
    def pmt_inf_ctrl_sum(self, txs): return str(sum(tx.amount for tx in txs))
```

Die Grundstruktur ist identisch mit SPS. Unterschiede liegen in:
- Optionale Elemente: RgltryRptg, erweiterte Structured Remittance, Tax
- Zeichensatz: UTF-8 statt SPS Latin-1 (permissiver, nicht restriktiver)
- UETR: optional, wird generiert wenn CBPR+-Zahlungstyp

### 3.4 XSD-Validierung (`src/validation/xsd_validator.py`)

CGI-MP verwendet das **SPS XSD** fuer die Validierung. Das SPS `.ch.03` XSD ist eine Swiss Restriction des ISO-Basis-Schemas — CGI-MP-konforme XMLs, die im Schweizer Kontext generiert werden, sind SPS XSD-kompatibel.

```python
def validate(self, xml_doc, standard):
    if standard == Standard.CBPR_PLUS_2026:
        schema = self.cbpr_schema
    else:
        # SPS und CGI-MP verwenden beide das SPS XSD
        schema = self.sps_schema
```

### 3.5 Business Rules (`src/validation/rule_catalog.py`)

Neue CGI-MP-spezifische Rules. Jede Rule traegt ein `standards` Attribut.

---

## 4. Functional Requirements

### FR-CGI-01: Standard-Auswahl

Neuer Wert `cgi-mp` in der Excel-Spalte "Standard". Default bleibt `sps2025`.

### FR-CGI-02: CGI-MP Strategy

Neue `CgiMpStrategy` in `standard_strategy.py`, registriert in `_STRATEGIES`. XML-Grundstruktur identisch mit SPS. Kein eigenes XSD noetig.

### FR-CGI-03: CGI-MP Business Rules

| Rule-ID | Beschreibung | Quelle | Severity |
|---------|-------------|--------|----------|
| BR-CGI-ADDR-01 | Adresse: Country Pflicht, TownName empfohlen (Pflicht ab Nov 2025 fuer int./urgent) | Handbook Slide 11 | Error |
| BR-CGI-ADDR-02 | Unstructured Adresse verboten fuer UltmtDbtr, UltmtCdtr, InitgPty | Handbook Slide 8 | Error |
| BR-CGI-ADDR-03 | Hybrid Adresse: max 2 AdrLine, keine Duplikation mit strukturierten Feldern | Handbook Slide 9 | Error |
| BR-CGI-RMT-01 | Structured und Unstructured Remittance gegenseitig exklusiv | Handbook Slide 24 | Error |
| BR-CGI-RMT-02 | Structured Remittance max 9000 Zeichen (exkl. Tags) | Handbook Slide 24 | Error |
| BR-CGI-RMT-03 | RfrdDocInf: Wenn Number vorhanden, Type Pflicht | Handbook Slide 26 | Error |
| BR-CGI-RMT-04 | RfrdDocInf: Issuer nicht verwenden (Best Practice) | Handbook Slide 26 | Warning |
| BR-CGI-RMT-05 | AdditionalRemittanceInformation: max 1 Occurrence (Best Practice) | Handbook Slide 38 | Warning |
| BR-CGI-PURP-01 | Regulatory purpose unter RgltryRptg, NICHT unter Purp | Handbook Slide 13 | Error |
| BR-CGI-PURP-02 | Wenn RgltryRptg verwendet, DbtCdtRptgInd (DEBT/CRED) Pflicht | Handbook Slide 15 | Error |
| BR-CGI-CHAR-01 | Leere XML-Tags (ohne Wert oder nur Blanks) verboten | Handbook Slide 4 | Error |

### FR-CGI-04: Regulatory Reporting XML-Builder

Neues XML-Element `<RgltryRptg>` auf C-Level (CdtTrfTxInf) generieren:

```xml
<RgltryRptg>
  <DbtCdtRptgInd>DEBT</DbtCdtRptgInd>    <!-- oder CRED -->
  <Dtls>
    <Tp>PURP</Tp>                          <!-- PURP, CRST, CIST, PUFD -->
    <Cd>E01</Cd>                           <!-- max 10 Zeichen -->
  </Dtls>
</RgltryRptg>
```

**Steuerung via Excel:**
- Neue optionale Spalte `Regulatory Reporting` oder via Overrides: `RgltryRptg.Ind=DEBT; RgltryRptg.Tp=PURP; RgltryRptg.Cd=E01`
- Mapping-Table (`mapping_table.py`) erweitern mit RgltryRptg-Keys

### FR-CGI-05: Structured Remittance Information erweitern

Ueber die bestehende CdtrRefInf (SCOR, QRR, USTRD) hinaus:

**RfrdDocInf** (Referred Document Information):
```xml
<Strd>
  <RfrdDocInf>
    <Tp><CdOrPrtry><Cd>CINV</Cd></CdOrPrtry></Tp>
    <Nb>INV-2026-001</Nb>
    <RltdDt>2026-03-15</RltdDt>
  </RfrdDocInf>
  <RfrdDocAmt>
    <DuePyblAmt Ccy="EUR">10000.00</DuePyblAmt>
    <RmtdAmt Ccy="EUR">10000.00</RmtdAmt>
  </RfrdDocAmt>
</Strd>
```

**Steuerung via Excel:**
- Overrides: `RmtInf.Strd.RfrdDocInf.Tp=CINV; RmtInf.Strd.RfrdDocInf.Nb=INV-2026-001; RmtInf.Strd.RfrdDocAmt.DuePyblAmt=10000.00`

### FR-CGI-06: Tax Component (Optional, Phase 2)

Element `<Tax>` auf C-Level fuer WHT-Szenarien. Wird aktiviert bei CtgyPurp=WHLD. Komplexe Struktur (Creditor/Debtor TaxId, Method, Record mit TaxAmount). Empfehlung: Erst implementieren wenn konkreter Use Case vorliegt.

### FR-CGI-07: Testfaelle

Folgende CGI-MP-Testfaelle im Excel erstellen:

**Positive (OK):**

| TestcaseID | Beschreibung | Besonderheit |
|-----------|-------------|-------------|
| TC-CGI-001 | CGI-MP Standard EUR Wire | Basis-Zahlung, strukturierte Adresse, SHAR |
| TC-CGI-002 | CGI-MP USD Wire mit UETR | UETR optional aber gesetzt |
| TC-CGI-003 | CGI-MP mit Category Purpose SALA | Gehaltszahlung |
| TC-CGI-004 | CGI-MP mit Regulatory Reporting (Frankreich) | RgltryRptg: DEBT, PURP, E01 |
| TC-CGI-005 | CGI-MP mit Regulatory Reporting (China) | RgltryRptg: CRED, PURP, COCADR |
| TC-CGI-006 | CGI-MP mit Structured Remittance (Invoice) | RfrdDocInf CINV + RfrdDocAmt |
| TC-CGI-007 | CGI-MP mit Structured Remittance (Invoice + Discount) | CINV + DscntApldAmt |
| TC-CGI-008 | CGI-MP mit Structured Remittance (Credit Note) | CREN + CdtNoteAmt |
| TC-CGI-009 | CGI-MP mit CdtrRefInf SCOR | ISO 11649 Structured Creditor Reference |
| TC-CGI-010 | CGI-MP Multi-Tx (3 Transaktionen) | Batch-Zahlung, verschiedene Creditors |
| TC-CGI-011 | CGI-MP mit Hybrid-Adresse | StrtNm + TwnNm + Ctry + 1 AdrLine |
| TC-CGI-012 | CGI-MP Vollstaendig alle Optionen | Purpose, CtgyPurp, RgltryRptg, UETR, Structured Remittance |

**Negative (NOK):**

| TestcaseID | Beschreibung | Verletzte Rule |
|-----------|-------------|---------------|
| TC-CGI-NOK-01 | CGI-MP Adresse ohne Country | BR-CGI-ADDR-01 |
| TC-CGI-NOK-02 | CGI-MP Structured + Unstructured Remittance gleichzeitig | BR-CGI-RMT-01 |

---

## 5. Implementierungsreihenfolge

| Schritt | Beschreibung | Aufwand |
|---------|-------------|---------|
| 1 | `Standard.CGI_MP` Enum + Excel-Parser Validierung | Klein |
| 2 | `CgiMpStrategy` Klasse (delegiert an SPS-Logik) | Klein |
| 3 | CGI-MP Business Rules im Katalog registrieren (BR-CGI-*) | Mittel |
| 4 | Regulatory Reporting Builder + Mapping-Keys | Mittel |
| 5 | Structured Remittance erweitern (RfrdDocInf, RfrdDocAmt) | Mittel |
| 6 | CGI-MP Testfaelle im Excel + XML generieren | Mittel |
| 7 | XSD-Validierung + Business Rule Tests | Klein |
| 8 | End-to-End-Test + Reporting | Klein |

Geschaetzter Gesamtaufwand: Schritte 1-3 sind minimal (CGI-MP nutzt gleiche XML-Struktur wie SPS). Schritte 4-5 erfordern neue XML-Builder-Funktionen.

---

## 6. Nicht in Scope

- CGI-MP Relay Payments (Forwarding Agent Logik) — eigener Use Case
- Market Survey / End-to-End Use Cases (Handbook Slides 58-78) — nur informativ
- Appendix B laenderspezifische Regeln (40+ Laender) — als Referenzdoku
- Garnishment Remittance (US-spezifisch, seltener Use Case)
- Tax Component Detail-Implementierung (Thailand/Philippines WHT Forms) — Phase 2
- CGI-MP pain.002 (Payment Status Report)
- BAH (Business Application Header) — nicht fuer C2B-pain.001 erforderlich

---

## 7. Abgrenzung der drei Standards

```
                    Corporate-to-Bank                    Bank-to-Bank
                    ─────────────────                    ────────────

  Schweiz:          SPS 2025                             (SIC/euroSIC)

  Global:           CGI-MP                               CBPR+ SR2026
                    - Alles erlaubt                      - Single Tx
                    - Structured Remittance              - Kein CtrlSum
                    - Regulatory Reporting               - UETR Pflicht
                    - Tax Component                      - FIN-X Charset
                    - UTF-8 Charset                      - BAH Pflicht
```

Unser Tool deckt die **C2B-Seite** ab: SPS fuer Schweizer Zahlungen, CGI-MP fuer internationale Zahlungen. CBPR+ bleibt fuer den Relay-Test verfuegbar.
