# Vergleich: SPS 2025 (Typ X) vs. SWIFT CBPR+ SR2025

## Quellen

| Standard | Dokument | Version | Zugang |
|----------|----------|---------|--------|
| **CBPR+** | CBPRPlus-pain.001.001.09 Usage Guideline | SR2025 (Combined) | SWIFT MyStandards (Login erforderlich, Registration gratis) |
| **CBPR+** | CBPR+ Roadmap beyond November 2025 | — | [PDF](https://www.swift.com/sites/default/files/files/cbpr-phase-2-roadmap_detailed_final_v2.pdf) |
| **CBPR+** | Rulebook for Payment Initiation Relay | März 2023 | [PDF](https://www.swift.com/sites/default/files/files/swift_rulebook_for_payment_initiation_relay_17032023.pdf) |
| **SPS** | IG Credit Transfer SPS 2025 | v2.2 | SIX Group (lokal: `ig-credit-transfer-sps-2025-de.md`) |
| **SPS** | Business Rules SPS 2025 | v3.2 | SIX Group (lokal: `business-rules-sps-2025-de.md`) |

> **Hinweis:** Die offizielle CBPR+ Usage Guideline ist nur über [SWIFT MyStandards](https://www2.swift.com/mystandards/) mit kostenlosem Login verfügbar. Die Analyse basiert auf dem offiziellen Dokument "CBPRPlus-pain.001.001.09_CustomerCreditTransferInitiation — CBPRPlus SR2025 (Combined)" (244 Seiten, 13. Dezember 2024).

## Zusammenfassung

CBPR+ und SPS Typ X haben **erhebliche Unterschiede**. CBPR+ ist restriktiver in der Struktur (1 Transaktion pro Message) aber flexibler bei Währungen und Gebühren. SPS Typ X ist eine vereinfachte Adaption für den Schweizer Markt.

## Detailvergleich

### 1. Transaktionen pro Nachricht

| Aspekt | CBPR+ | SPS (Typ X) |
|--------|-------|-------------|
| **PmtInf pro Message** | Genau 1 | 1..n |
| **CdtTrfTxInf pro PmtInf** | Genau 1 | 1..n |
| **NbOfTxs** | Immer "1" | Summe aller Tx |
| **CtrlSum** | **Entfernt** | Vorhanden |
| **BatchBooking** | **Entfernt** | Optional |
| **Identisch?** | **Nein** — fundamentaler Unterschied |

**CBPR+-Quelle:** Usage Guideline p.111, 138, 145

**Konsequenz für unseren Code:** Unser Generator erstellt Multi-Payment XMLs (mehrere PmtInf) — diese sind **nicht CBPR+-konform**. Für echte CBPR+-Konformität müsste pro Transaktion eine separate XML erstellt werden.

### 2. UETR (Unique End-to-End Transaction Reference)

| Aspekt | CBPR+ | SPS (Typ X) |
|--------|-------|-------------|
| **UETR** | **Pflicht** (UUIDv4) | Optional |
| **Format** | `[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}` | — |
| **Identisch?** | **Nein** |

**CBPR+-Quelle:** Usage Guideline p.133

### 3. Gebührenregelung (ChrgBr)

| Aspekt | CBPR+ | SPS (Typ X) |
|--------|-------|-------------|
| **Erlaubte Werte** | DEBT, CRED, SHAR | DEBT, CRED, SHAR, SLEV |
| **SLEV** | **Explizit entfernt** | Erlaubt |
| **Position** | Bevorzugt auf Tx-Level | B-Level oder C-Level |
| **Identisch?** | **Nein** — CBPR+ verbietet SLEV |

**CBPR+-Quelle:** Usage Guideline p.203-204

### 4. Währung

| Aspekt | CBPR+ | SPS (Typ X) |
|--------|-------|-------------|
| **Erlaubte Währungen** | Alle ISO 4217 | V1: alle ausser CHF/EUR, V2: alle |
| **Dezimalstellen** | Gemäss ISO 4217 pro Währung (max 5) | Max 2 |
| **Betragsformat** | totalDigits=18, fractionDigits=5 | totalDigits undefiniert, fractionDigits=2 |
| **Identisch?** | **Nein** — CBPR+ erlaubt mehr Dezimalstellen |

**CBPR+-Quelle:** Usage Guideline p.196-197, Rule R8/R9

### 5. Zeichensatz

| Aspekt | CBPR+ | SPS |
|--------|-------|-----|
| **Referenzfelder** | FIN X: `a-zA-Z0-9 /-?:().,'+` (max 35) | SPS Reference Charset (identisch) |
| **Namensfelder** | FIN X Extended: + `!#$%&*=^_{}\|~";<>@[\]` (max 140) | SPS Latin-1 Subset (~350 Zeichen, max 140) |
| **Identisch?** | **Nein** — unterschiedliche Zeichensätze für Textfelder |

**CBPR+-Quelle:** Usage Guideline p.94 (CBPR_RestrictedFINXMax35Text, CBPR_RestrictedFINXMax140Text_Extended)

### 6. Namenslängen

| Aspekt | CBPR+ | SPS (Typ X) |
|--------|-------|-------------|
| **Debtor/Creditor Name** | Max 140 Zeichen | Max 140 Zeichen |
| **Identisch?** | Ja |

### 7. BIC-Anforderungen

| Aspekt | CBPR+ | SPS (Typ X) |
|--------|-------|-------------|
| **Debtor Agent** | BIC Pflicht | BIC Pflicht |
| **Creditor Agent** | BIC empfohlen | BIC Pflicht (per Override) |
| **Intermediary Agents** | Bis zu 3 (mit Kaskadenregeln R11-R12) | Nicht explizit unterstützt |
| **Identisch?** | Teilweise — CBPR+ hat Agent-Chain-Regeln |

**CBPR+-Quelle:** Usage Guideline p.54-55 (R11, R12, R14-R16)

### 8. Adressanforderungen

| Aspekt | CBPR+ | SPS |
|--------|-------|-----|
| **Formate** | Strukturiert, Hybrid, Unstrukturiert (Grace Period bis Nov 2026) | Strukturiert, Hybrid (ab Nov 2025), Unstrukturiert (bis Nov 2026) |
| **TwnNm + Ctry Pflicht** | Ja | Ja |
| **AddressLine max** | 7 Zeilen (je 70 Zeichen) | 2 Zeilen (je 70 Zeichen) |
| **Duplikationsverbot** | Strukturierte Daten dürfen nicht in AddressLine wiederholt werden | Identisch |
| **Identisch?** | Teilweise — CBPR+ erlaubt mehr AddressLines |

**CBPR+-Quelle:** Usage Guideline p.126-127, 150

### 9. Zahlungsmethode

| Aspekt | CBPR+ | SPS (Typ X) |
|--------|-------|-------------|
| **PmtMtd** | CHK oder TRF (TRA entfernt) | Nur TRF |
| **Identisch?** | **Nein** — CBPR+ erlaubt CHK |

### 10. Remittance Information

| Aspekt | CBPR+ | SPS (Typ X) |
|--------|-------|-------------|
| **Structured/Unstructured** | Gegenseitig exklusiv | Gegenseitig exklusiv |
| **Unstructured max** | 1 Occurrence, 140 Zeichen | 140 Zeichen |
| **Reference max** | 35 Zeichen | 25 Zeichen (SCOR) |
| **Codes** | SCOR, DISP, FXDR, PUOR, RADM, RPIN | SCOR |
| **Identisch?** | **Nein** — CBPR+ hat mehr Referenztyp-Codes |

### 11. Payment Type Information

| Aspekt | CBPR+ | SPS (Typ X) |
|--------|-------|-------------|
| **ServiceLevel** | Keine Einschränkung (nicht SEPA) | Nicht SEPA |
| **InstructionPriority** | HIGH, NORM erlaubt | Nicht verwendet |
| **CategoryPurpose** | Coded empfohlen | Optional |
| **R19** | PmtTpInf auf PmtInf und TxInf-Level gegenseitig exklusiv | Nicht erzwungen |
| **Identisch?** | Teilweise |

### 12. Entfernte Elemente in CBPR+ (nicht in SPS)

Diese Elemente existieren in ISO 20022 pain.001 und in SPS, sind aber in CBPR+ **explizit entfernt**:

| Element | CBPR+ Status |
|---------|-------------|
| GrpHdr/CtrlSum | Entfernt |
| PmtInf/BatchBooking | Entfernt |
| PmtInf/NbOfTxs | Entfernt |
| PmtInf/CtrlSum | Entfernt |
| ChrgBr=SLEV | Entfernt |
| PmtMtd=TRA | Entfernt |
| PostalAddress/AddressType | Entfernt |
| CdtTrfTxInf/SupplementaryData | Entfernt |

## Konsequenzen für unseren Code

| Aspekt | Aktueller Stand | Für CBPR+-Konformität nötig |
|--------|-----------------|---------------------------|
| Multi-Payment (GroupId) | Unterstützt | Muss für CBPR+ auf 1 Tx/Message beschränkt werden |
| UETR | Nicht implementiert | Pflichtfeld für CBPR+ |
| SLEV als ChrgBr | Erlaubt für Typ X | Muss für CBPR+ verboten werden |
| CtrlSum in PmtInf | Wird generiert | Muss für CBPR+ entfallen |
| NbOfTxs in PmtInf | Wird generiert | Muss für CBPR+ entfallen |
| Dezimalstellen | Max 2 | CBPR+ erlaubt bis 5 (währungsabhängig) |
