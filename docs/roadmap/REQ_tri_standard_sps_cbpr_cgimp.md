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
| BR-CGI-RGRP-01 | RgltryRptg: Wenn Details vorhanden, Type (Tp) Pflicht | Handbook Slide 17 | Error |
| BR-CGI-RGRP-02 | RgltryRptg: Authority darf nur 1x pro DbtCdtRptgInd vorkommen | Handbook Slide 16 | Error |
| BR-CGI-RGRP-03 | RgltryRptg: Max 10 Occurrences pro Transaktion | Handbook Slide 13 | Error |
| BR-CGI-RGRP-04 | RgltryRptg: Code max 10 Zeichen | Handbook Slide 17 | Error |
| BR-CGI-TAX-01 | Tax: Wenn CtgyPurp=WHLD, Tax-Element erwartet | Handbook Slide 42 | Warning |
| BR-CGI-TAX-02 | Tax: Creditor und Debtor TaxId Pflicht wenn Tax vorhanden | Handbook Slide 44 | Error |
| BR-CGI-TAX-03 | Tax: Method Pflicht wenn Tax vorhanden (REWHT, EWHT, WHTX etc.) | Handbook Slide 44 | Error |
| BR-CGI-TAX-04 | Tax: Record muss mindestens Type und TaxAmount enthalten | Handbook Slide 44 | Error |
| BR-CGI-TAX-05 | Tax: TaxableBaseAmount und TotalTaxAmount muessen gleiche Waehrung haben | Handbook Slide 44 | Error |

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

### FR-CGI-06: Tax Component

Element `<Tax>` auf C-Level fuer WHT-Szenarien (Withholding Tax). Wird aktiviert bei CtgyPurp=WHLD.

```xml
<Tax>
  <Cdtr><TaxId>12345</TaxId></Cdtr>            <!-- Creditor Tax ID -->
  <Dbtr><TaxId>98765</TaxId></Dbtr>            <!-- Debtor Tax ID -->
  <Mtd>REWHT</Mtd>                              <!-- Method: REWHT, EWHT, WHTX, etc. -->
  <Rcrd>
    <Tp>3</Tp>                                   <!-- 1=Withhold at source, 3=Deducted at source -->
    <Ctgy>002</Ctgy>                             <!-- Category: 001=Salary, 002=Commission, etc. -->
    <TaxAmt>
      <TaxblBaseAmt Ccy="THB">13000.00</TaxblBaseAmt>  <!-- Taxable base -->
      <TtlAmt Ccy="THB">390.00</TtlAmt>               <!-- Tax amount -->
    </TaxAmt>
  </Rcrd>
</Tax>
```

Optionale Erweiterungen pro Record:
- `<CertId>` — WHT Document/Certificate Number
- `<FrmsCd>` — Form Number (z.B. 2306, 2307 fuer Philippines)
- `<Dtls><Prd><FrToDt>` — Steuerperiode (von/bis Datum)
- `<TaxTp>` — Organisationstyp (ORG = Organisation)

**Steuerung via Excel:**
- CtgyPurp=WHLD im "Weitere Testdaten" aktiviert Tax
- Overrides: `Tax.Cdtr.TaxId=12345; Tax.Dbtr.TaxId=98765; Tax.Mtd=REWHT; Tax.Rcrd.Tp=3; Tax.Rcrd.Ctgy=002; Tax.Rcrd.TaxblBaseAmt=13000; Tax.Rcrd.TtlAmt=390`

### FR-CGI-07: Testfaelle

Folgende CGI-MP-Testfaelle im Excel erstellen:

### 4.7.1 Basis-Testfaelle (OK + NOK)

| TestcaseID | Beschreibung | Besonderheit | OK/NOK |
|-----------|-------------|-------------|--------|
| TC-CGI-001 | CGI-MP Standard EUR Wire | Basis-Zahlung, strukturierte Adresse, SHAR | OK |
| TC-CGI-002 | CGI-MP USD Wire mit UETR | UETR optional aber gesetzt | OK |
| TC-CGI-003 | CGI-MP mit Category Purpose SALA | Gehaltszahlung | OK |
| TC-CGI-009 | CGI-MP mit CdtrRefInf SCOR | ISO 11649 Structured Creditor Reference | OK |
| TC-CGI-010 | CGI-MP Multi-Tx (3 Transaktionen) | Batch-Zahlung, verschiedene Creditors | OK |
| TC-CGI-011 | CGI-MP mit Hybrid-Adresse | StrtNm + TwnNm + Ctry + 1 AdrLine | OK |
| TC-CGI-012 | CGI-MP Vollstaendig alle Optionen | Purpose, CtgyPurp, RgltryRptg, UETR, Strd Remittance | OK |
| TC-CGI-NOK-01 | CGI-MP Adresse ohne Country | BR-CGI-ADDR-01 | NOK |
| TC-CGI-NOK-02 | CGI-MP Structured + Unstructured gleichzeitig | BR-CGI-RMT-01 | NOK |

### 4.7.2 Regulatory Reporting Testfaelle (10 OK + 10 NOK)

**Positive (OK):**

| TestcaseID | Beschreibung | RgltryRptg Details |
|-----------|-------------|-------------------|
| TC-CGI-RR-OK-01 | Frankreich → Nicht-SEPA: Wirtschaftscode | Ind=DEBT, Tp=PURP, Cd=E01 (Goods, Banque de France) |
| TC-CGI-RR-OK-02 | Frankreich → Nicht-SEPA: DECL-Code | Ind=DEBT, Tp=DECL, Cd=S0001 |
| TC-CGI-RR-OK-03 | Deutschland → China: Zahlungszweck | Ind=CRED, Tp=PURP, Cd=COCADR (Current Account incl. dividend) |
| TC-CGI-RR-OK-04 | Indonesien → USA: Citizenship + Creditor + Purpose | Ind=DEBT, 3x Dtls: CIST/1, CRST/2, PURP/50 |
| TC-CGI-RR-OK-05 | Schweiz → Brasilien: Zahlungszweck mit Authority | Ind=DEBT, Tp=PURP, Cd=12345, Authority Name+Country |
| TC-CGI-RR-OK-06 | UK → Indien: Minimal (nur Ind + Tp + Cd) | Ind=CRED, Tp=PURP, Cd=P0801 |
| TC-CGI-RR-OK-07 | USA → Taiwan: Purpose of Funds | Ind=CRED, Tp=PUFD, Cd=FX (Foreign Exchange) |
| TC-CGI-RR-OK-08 | DE → Suedafrika: DEBT mit Information-Text | Ind=DEBT, Tp=PURP, Cd=TRADE, Inf=Export goods machinery |
| TC-CGI-RR-OK-09 | CH → Saudi-Arabien: CRED + Amount | Ind=CRED, Tp=PURP, Cd=OIL01, Amount=50000 SAR |
| TC-CGI-RR-OK-10 | Multi-RgltryRptg: DEBT + CRED gleichzeitig | 2x RgltryRptg: 1x Ind=DEBT Tp=PURP, 1x Ind=CRED Tp=PURP |

**Negative (NOK):**

| TestcaseID | Beschreibung | Verletzte Rule |
|-----------|-------------|---------------|
| TC-CGI-RR-NOK-01 | RgltryRptg ohne DbtCdtRptgInd | BR-CGI-PURP-02 (Indicator Pflicht) |
| TC-CGI-RR-NOK-02 | RgltryRptg Details ohne Type (Tp) | BR-CGI-RGRP-01 (Type Pflicht wenn Details) |
| TC-CGI-RR-NOK-03 | RgltryRptg Code > 10 Zeichen | BR-CGI-RGRP-04 (Code max 10 Zeichen) |
| TC-CGI-RR-NOK-04 | RgltryRptg Authority 2x bei gleichem Indicator | BR-CGI-RGRP-02 (Authority max 1x pro Ind) |
| TC-CGI-RR-NOK-05 | RgltryRptg > 10 Occurrences | BR-CGI-RGRP-03 (Max 10 pro Tx) |
| TC-CGI-RR-NOK-06 | Regulatory Purpose unter `<Purp>` statt `<RgltryRptg>` | BR-CGI-PURP-01 (Purp nicht fuer Regulatory) |
| TC-CGI-RR-NOK-07 | RgltryRptg mit Ind=BOTH (nicht unterstuetzt) | BR-CGI-PURP-02 (nur DEBT/CRED gueltig) |
| TC-CGI-RR-NOK-08 | RgltryRptg Details leer (nur Tp, kein Cd und kein Inf) | BR-CGI-RGRP-01 (min. Cd oder Inf erwartet) |
| TC-CGI-RR-NOK-09 | RgltryRptg mit leerem Cd-Tag `<Cd></Cd>` | BR-CGI-CHAR-01 (leere Tags verboten) |
| TC-CGI-RR-NOK-10 | RgltryRptg mit ungueltigem Indicator-Wert | BR-CGI-PURP-02 (Wert nicht DEBT/CRED/BOTH) |

### 4.7.3 Tax Information Testfaelle (10 OK + 10 NOK)

**Positive (OK):**

| TestcaseID | Beschreibung | Tax Details |
|-----------|-------------|------------|
| TC-CGI-TAX-OK-01 | Thailand WHT Commission (Form 2306) | CtgyPurp=WHLD, Method=REWHT, Tp=3, Ctgy=002, THB 390 auf 13000 (3%) |
| TC-CGI-TAX-OK-02 | Thailand WHT Payroll (Form 2306) | CtgyPurp=WHLD, Method=EWHT, Tp=1, Ctgy=001, THB 390 auf 13000 (3%) |
| TC-CGI-TAX-OK-03 | Philippines WHT Fee (Form 2306) | CtgyPurp=WHLD, Method=3, Tp=WHTX, Ctgy=WC340, PHP 2500 auf 50000 (5%) |
| TC-CGI-TAX-OK-04 | Philippines WHT Fee (Form 2307 quarterly) | CtgyPurp=WHLD, FrmsCd=2307, Period Q1 2024, PHP 2500 |
| TC-CGI-TAX-OK-05 | Einfache WHT mit nur Cdtr/Dbtr TaxId + Method | CtgyPurp=WHLD, CdtrTaxId=12345, DbtrTaxId=98765, Method=REWHT, 1 Record |
| TC-CGI-TAX-OK-06 | WHT mit TaxType ORG (Organisation) | CtgyPurp=WHLD, CdtrTaxTp=ORG, DbtrTaxTp=ORG |
| TC-CGI-TAX-OK-07 | WHT mit CertId und FrmsCd | CertId=WHT-DOC-001, FrmsCd=2306 |
| TC-CGI-TAX-OK-08 | WHT mit Period (FrDt/ToDt) | Record.Dtls.Prd: 2024-01-01 bis 2024-12-31 |
| TC-CGI-TAX-OK-09 | WHT USD Zahlung (nicht THB/PHP) | CtgyPurp=WHLD, USD, TaxblBaseAmt USD 100000, TtlAmt USD 5000 (5%) |
| TC-CGI-TAX-OK-10 | WHT mit mehreren Records (2 Steuerarten) | 2x Record: 1x Commission (002) + 1x Salary (001) in einer Zahlung |

**Negative (NOK):**

| TestcaseID | Beschreibung | Verletzte Rule |
|-----------|-------------|---------------|
| TC-CGI-TAX-NOK-01 | CtgyPurp=WHLD aber kein Tax-Element | BR-CGI-TAX-01 (Tax erwartet bei WHLD) |
| TC-CGI-TAX-NOK-02 | Tax ohne Creditor TaxId | BR-CGI-TAX-02 (CdtrTaxId Pflicht) |
| TC-CGI-TAX-NOK-03 | Tax ohne Debtor TaxId | BR-CGI-TAX-02 (DbtrTaxId Pflicht) |
| TC-CGI-TAX-NOK-04 | Tax ohne Method | BR-CGI-TAX-03 (Method Pflicht) |
| TC-CGI-TAX-NOK-05 | Tax Record ohne Type (Tp) | BR-CGI-TAX-04 (Record.Tp Pflicht) |
| TC-CGI-TAX-NOK-06 | Tax Record ohne TaxAmount | BR-CGI-TAX-04 (Record.TaxAmt Pflicht) |
| TC-CGI-TAX-NOK-07 | TaxableBaseAmount CHF aber TotalTaxAmount USD | BR-CGI-TAX-05 (Waehrung muss gleich sein) |
| TC-CGI-TAX-NOK-08 | Tax-Element ohne CtgyPurp=WHLD | BR-CGI-TAX-01 (WHLD erwartet wenn Tax) |
| TC-CGI-TAX-NOK-09 | Tax mit leerem TaxId-Tag `<TaxId></TaxId>` | BR-CGI-CHAR-01 (leere Tags verboten) |
| TC-CGI-TAX-NOK-10 | Tax Record TotalTaxAmount > TaxableBaseAmount | BR-CGI-TAX-05 (Steuer > Basis unplausibel) |

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
