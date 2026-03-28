# Requirements: Tri-Standard Support (SPS + CBPR+ + CGI-MP)

**Version:** 1.0
**Datum:** 28. Maerz 2026
**Status:** Entwurf
**Basis:** Bestehende Dual-Standard-Implementierung (SPS + CBPR+), CGI-MP WG1 User Handbook pain.001 V09 Nov 2025

---

## 1. Hintergrund

### 1.1 Aktuelle Situation

Das System unterstuetzt zwei Standards fuer pain.001.001.09:
- **SPS 2025** (Swiss Payment Standards): Customer-to-Bank fuer Schweizer Zahlungen (Domestic, SEPA, CBPR+)
- **CBPR+ SR2026** (SWIFT): Bank-to-Bank Relay-Szenario

### 1.2 Problem

CBPR+ ist ein Bank-to-Bank-Standard. Fuer den primaeren Use Case **Corporate-to-Bank (C2B)** im internationalen Zahlungsverkehr fehlt der passende globale Standard:

- **CGI-MP** (Common Global Implementation — Market Practice) ist der globale C2B-Standard
- CGI-MP nutzt das **gleiche Standard-ISO-XSD** (kein eigenes restriktives Schema wie CBPR+)
- CGI-MP definiert Business Rules als **Usage-Guideline-Schicht** ueber dem ISO-Schema
- CGI-MP ist die Basis fuer CBPR+ Relay pain.001 (CBPR+ ist eine Restriction von CGI-MP)

### 1.3 Ziel

Drei Standards pro Testfall waehlbar: `sps2025`, `cbpr+2026`, `cgi-mp` (neu).

---

## 2. Standards im Vergleich

| Aspekt | SPS 2025 | CGI-MP | CBPR+ SR2026 |
|--------|----------|--------|-------------|
| **Scope** | C2B Schweiz | C2B global | B2B Relay |
| **XSD** | `pain.001.001.09.ch.03` (Swiss Restriction) | Standard ISO `pain.001.001.09` | CBPR+ Restriction (42 restriktive Typen) |
| **Eigenes XSD noetig?** | Ja (im Repo) | **Nein** (Standard ISO XSD genuegt) | Ja (proprietaer) |
| **Multi-Tx/PmtInf** | 1..n / 1..n | 1..n / 1..n (bilateral: mehr moeglich) | Genau 1 / 1 |
| **UETR** | Optional | **Optional** (empfohlen) | Pflicht |
| **ChrgBr** | DEBT/CRED/SHAR/SLEV | DEBT/CRED/SHAR/SLEV | DEBT/CRED/SHAR (kein SLEV) |
| **CtrlSum GrpHdr** | Ja | Ja | Entfaellt |
| **NbOfTxs/CtrlSum PmtInf** | Ja | Ja | Entfaellt |
| **PmtInfId** | Generiert (eindeutig) | Kann = MsgId oder verschieden | = MsgId |
| **CreDtTm** | ISO 8601 | ISO 8601 | Pflicht UTC-Offset |
| **Zeichensatz** | SPS Latin-1 Subset | **UTF-8 voll** (Clearing kann einschraenken) | FIN-X Restricted |
| **Adressen** | Strukturiert Pflicht (ab Nov 2026) | Strukturiert oder Hybrid (Unstrukturiert ab Nov 2026 verboten) | Strukturiert/Hybrid (Unstrukturiert ab Nov 2026 verboten) |
| **BAH** | Nicht erforderlich | Nicht erforderlich (Client-Channel-unabhaengig) | Pflicht |
| **Regulatory Reporting** | Nicht unterstuetzt | **Voll unterstuetzt** (laenderspezifisch) | Wie CGI-MP |
| **Structured Remittance** | CdtrRefInf (SCOR, QRR) | **Voll** (RfrdDocInf, RfrdDocAmt, CdtrRefInf, TaxRmt, GarnishRmt) | Wie CGI-MP |
| **Tax Component** | Nicht unterstuetzt | **Unterstuetzt** (WHT Thailand, Philippines etc.) | — |

---

## 3. Functional Requirements

### FR-CGI-01: Standard-Auswahl CGI-MP
Der Benutzer kann im Excel `cgi-mp` als Standard angeben. Ohne Angabe gilt weiterhin `sps2025`.

### FR-CGI-02: Standard Enum erweitern
```python
class Standard(str, Enum):
    SPS_2025 = "sps2025"
    CBPR_PLUS_2026 = "cbpr+2026"
    CGI_MP = "cgi-mp"          # NEU
```

### FR-CGI-03: XSD-Validierung CGI-MP
CGI-MP verwendet das **Standard ISO 20022 pain.001.001.09 XSD** (kein eigenes restriktives Schema). Fuer die Validierung wird entweder:
- Das SPS XSD (`.ch.03`) verwendet (ist eine Obermenge), oder
- Ein Standard ISO pain.001.001.09 XSD beschafft und konfiguriert

**Empfehlung:** Das SPS XSD ist kompatibel, da es eine Swiss Restriction des ISO-Schemas ist. CGI-MP-konforme XMLs die auch SPS-konform sind, passieren das SPS XSD.

### FR-CGI-04: XML-Generierung CGI-MP
Die XML-Struktur fuer CGI-MP ist **identisch mit SPS** bezueglich der Grundstruktur (GrpHdr, PmtInf, CdtTrfTxInf). Unterschiede:
- UETR optional (nicht erzwungen wie bei CBPR+)
- Keine SLEV-Einschraenkung bei ChrgBr
- UTF-8 Zeichensatz (keine Einschraenkung wie FIN-X)
- Structured Remittance Information voll unterstuetzt

### FR-CGI-05: CGI-MP Business Rules
Neue Business Rules aus dem CGI-MP User Handbook:

| Rule-ID | Beschreibung | Quelle |
|---------|-------------|--------|
| BR-CGI-ADDR-01 | Structured/Hybrid Adresse: Country Pflicht, TownName empfohlen | Handbook Slide 11 |
| BR-CGI-ADDR-02 | Unstructured Adresse nicht fuer UltmtDbtr, UltmtCdtr, InitgPty | Handbook Slide 8 |
| BR-CGI-ADDR-03 | Hybrid max 2 AdrLine; keine Duplikation mit strukturierten Feldern | Handbook Slide 9 |
| BR-CGI-RMT-01 | Structured/Unstructured Remittance gegenseitig exklusiv | Handbook Slide 24 |
| BR-CGI-RMT-02 | Structured Remittance max 9000 Zeichen (exkl. Tag-Namen) | Handbook Slide 24 |
| BR-CGI-RMT-03 | RfrdDocInf: Wenn Number vorhanden, Type Pflicht | Handbook Slide 26 |
| BR-CGI-RMT-04 | Issuer nicht verwenden (Best Practice) | Handbook Slide 26 |
| BR-CGI-RMT-05 | AdditionalRemittanceInformation: max 1 Occurrence (Best Practice) | Handbook Slide 38 |
| BR-CGI-PURP-01 | Regulatory purpose unter RgltryRptg, NICHT unter Purp | Handbook Slide 13 |
| BR-CGI-PURP-02 | Wenn RgltryRptg verwendet, DbtCdtRptgInd Pflicht | Handbook Slide 15 |
| BR-CGI-CHAR-01 | Leere XML-Tags duerfen nicht geliefert werden | Handbook Slide 4 |
| BR-CGI-RELAY-01 | Relay: Forwarding Agent BICFI Pflicht | Handbook Slide 53 |

### FR-CGI-06: Regulatory Reporting Support
Neues XML-Element `<RgltryRptg>` auf C-Level unterstuetzen:
- DbtCdtRptgInd (DEBT/CRED)
- Authority (Name, Country)
- Details (Type, Date, Country/Code, Amount, Information)

Laenderspezifische Codes aus Appendix B (Excel) referenzieren.

### FR-CGI-07: Structured Remittance Information erweitern
Ueber die bestehende CdtrRefInf (SCOR, QRR) hinaus:
- RfrdDocInf (Type, Number, RelatedDate)
- RfrdDocAmt (DuePayableAmount, RemittedAmount, DiscountAppliedAmount)
- TaxRemittance (fuer Steuer-Reconciliation)
- GarnishmentRemittance (fuer US Garnishment)
- AdditionalRemittanceInformation (max 3x 140 Zeichen)

### FR-CGI-08: Tax Component Support
Neues XML-Element `<Tax>` auf C-Level:
- Creditor/Debtor Tax IDs
- Method (REWHT, EWHT, WHTX)
- Record (Type, Category, TaxAmount)
- Wird aktiviert bei CtgyPurp=WHLD

### FR-CGI-09: Testfaelle
Mindestens folgende CGI-MP-Testfaelle im Excel:
- CGI-MP Standard-Zahlung (ACH, Wire)
- CGI-MP mit Regulatory Reporting (Frankreich, China, Indonesien)
- CGI-MP mit Structured Remittance (Invoice, Credit Note, Multi-Invoice)
- CGI-MP mit Tax/WHT (Thailand-Szenario)
- CGI-MP Relay Payment (mit Forwarding Agent)

---

## 4. Nicht in Scope (Phase 1)

- Appendix B laenderspezifische Regeln (40+ Laender) — nur als Referenz
- Garnishment Remittance (US-spezifisch, rare use case)
- Tax Component Detail-Implementierung (Thailand/Philippines Forms)
- CGI-MP pain.002 (Payment Status Report)
- Market Survey End-to-End Use Cases (Slide 58)

---

## 5. Implementierungsreihenfolge

| Schritt | Beschreibung | Abhaengigkeit |
|---------|-------------|---------------|
| 1 | `Standard.CGI_MP` Enum + Excel-Parser | Keine |
| 2 | CGI-MP Strategy (XML identisch mit SPS, UTF-8 Charset) | Schritt 1 |
| 3 | CGI-MP Business Rules im Katalog | Schritt 1 |
| 4 | Regulatory Reporting XML-Builder | Schritt 2 |
| 5 | Structured Remittance erweitern (RfrdDocInf, RfrdDocAmt) | Schritt 2 |
| 6 | Tax Component XML-Builder | Schritt 2 |
| 7 | CGI-MP Testfaelle im Excel | Schritte 3-6 |
| 8 | End-to-End-Test | Schritt 7 |

---

## 6. Abgrenzung zu CBPR+

CGI-MP und CBPR+ sind **komplementaer**, nicht konkurrierend:

```
Corporate  --[CGI-MP pain.001]--> Forwarding Agent --[CBPR+ pain.001]--> Debtor Agent --[pacs.008]--> Creditor Agent
```

- **CGI-MP** = Was der Corporate sendet (reich, alle Optionen, multi-tx)
- **CBPR+** = Was die Bank weiterleitet (restriktiv, single-tx, BAH)
- Der Forwarding Agent transformiert: CGI-MP → CBPR+ (Elemente entfernen, MsgId aendern, BAH hinzufuegen, UETR generieren falls fehlend)

Unser Tool deckt beide Seiten ab: CGI-MP fuer den Corporate-Test, CBPR+ fuer den Relay-Test.
