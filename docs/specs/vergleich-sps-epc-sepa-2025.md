# Vergleich: SPS 2025 vs. EPC SEPA Credit Transfer 2025

## Quellen

| Standard | Dokument | Version | Datum | URL |
|----------|----------|---------|-------|-----|
| **EPC** | SCT Rulebook (EPC125-05) | 2025 v1.1 | 05.10.2025 | [PDF](https://www.europeanpaymentscouncil.eu/sites/default/files/kb/file/2025-09/EPC125-05%202025%20SCT%20Rulebook%20version%201.1.pdf) |
| **EPC** | SCT C2PSP Implementation Guidelines (EPC132-08) | 2025 v1.0 | 05.10.2025 | [PDF](https://www.europeanpaymentscouncil.eu/sites/default/files/kb/file/2024-11/EPC132-08%20SCT%20C2PSP%20IG%202025%20V1.0.pdf) |
| **EPC** | Character Set Best Practices (EPC217-08) | v1.1 | 18.12.2012 | [PDF](https://www.europeanpaymentscouncil.eu/sites/default/files/KB/files/EPC217-08%20Draft%20Best%20Practices%20SEPA%20Requirements%20for%20Character%20Set%20v1.1.pdf) |
| **SPS** | IG Credit Transfer SPS 2025 | v2.2 | 2025 | SIX Group (lokal: `ig-credit-transfer-sps-2025-de.md`) |
| **SPS** | Business Rules SPS 2025 | v3.2 | 2025 | SIX Group (lokal: `business-rules-sps-2025-de.md`) |

## Zusammenfassung

SPS und EPC sind für SEPA-Zahlungen (Typ S) weitgehend identisch. SPS ist eine **Obermenge** von EPC — es enthält alle EPC-Regeln für SEPA und ergänzt sie um die schweizspezifischen Zahlungsarten D (Inland) und X (CBPR+).

## Detailvergleich

### 1. Zeichensatz

| Aspekt | EPC (SEPA) | SPS |
|--------|-----------|-----|
| **Grundzeichensatz** | 73 Zeichen: `a-zA-Z0-9 /-?:().,'+` + Space | ~350+ Zeichen: Basic Latin + Latin-1 Supplement + Latin Extended-A + €ȘșȚț |
| **Referenzfelder** | Grundzeichensatz, kein `/` am Anfang/Ende, kein `//` | Identisch zu EPC |
| **SEPA-Weiterleitung** | — | Zeichen ausserhalb EPC-Grundzeichensatz werden konvertiert (z.B. ä→ae) gemäss Anhang C |
| **Identisch?** | Nein — SPS erlaubt deutlich mehr Zeichen, konvertiert aber bei SEPA-Weiterleitung |

**EPC-Quelle:** EPC217-08 §2, EPC132-08 §1.4

### 2. Betragsgrenzen

| Aspekt | EPC (SEPA) | SPS (Typ S) |
|--------|-----------|-------------|
| **Minimum** | 0.01 EUR | 0.01 EUR |
| **Maximum** | 999'999'999.99 EUR | 999'999'999.99 EUR |
| **Dezimalstellen** | Max 2 | Max 2 |
| **Währung** | Nur EUR | Nur EUR (für Typ S) |
| **Identisch?** | Ja |

**EPC-Quelle:** EPC125-05 §2.4, EPC132-08 Index 2.95

### 3. Gebührenregelung (ChrgBr)

| Aspekt | EPC (SEPA) | SPS (Typ S) |
|--------|-----------|-------------|
| **Erlaubter Wert** | Nur SLEV | Nur SLEV |
| **Pflicht/Optional** | Wenn gesetzt, muss SLEV sein | Wenn gesetzt, muss SLEV sein |
| **Identisch?** | Ja |

**EPC-Quelle:** EPC125-05 §4.2.4, EPC132-08 Index 2.75/2.98

### 4. Namenslängen

| Aspekt | EPC (SEPA) | SPS |
|--------|-----------|-----|
| **Debtor Name** | Max 70 Zeichen | Max 70 Zeichen (Typ S), max 140 (Typ D/X) |
| **Creditor Name** | Max 70 Zeichen | Max 70 Zeichen (Typ S), max 140 (Typ D/X) |
| **InitgPty Name** | Max 70 Zeichen | Max 70 Zeichen |
| **Identisch?** | Ja (für Typ S) — SPS erlaubt 140 für non-SEPA |

**EPC-Quelle:** EPC132-08 Index 2.22, 2.117, 1.7

### 5. IBAN-Anforderungen

| Aspekt | EPC (SEPA) | SPS |
|--------|-----------|-----|
| **Debtor** | IBAN Pflicht | IBAN Pflicht (alle Typen) |
| **Creditor** | Nur IBAN | IBAN oder QR-IBAN (Typ D), IBAN oder Konto (Typ X) |
| **Identisch?** | Ja (für Typ S) |

### 6. BIC-Anforderungen

| Aspekt | EPC (SEPA) | SPS (Typ S) |
|--------|-----------|-------------|
| **Creditor Agent BIC** | Optional (seit Feb 2016, IBAN-only) | Optional |
| **Debtor Agent BIC** | Pflicht | Pflicht |
| **Identisch?** | Ja |

**EPC-Quelle:** EPC125-05 AT-C002

### 7. Referenztypen (Remittance Information)

| Aspekt | EPC (SEPA) | SPS |
|--------|-----------|-----|
| **SCOR** | Ja (ISO 11649, max 25 Zeichen) | Ja |
| **Unstructured** | Ja (max 140 Zeichen) | Ja |
| **QRR** | Nein | Ja (nur Typ D mit QR-IBAN, als Prtry) |
| **Exklusivität** | Entweder Structured ODER Unstructured | Identisch |
| **Identisch?** | Ja (für Typ S) — QRR ist nur für Typ D |

**EPC-Quelle:** EPC132-08 Index 2.164

### 8. Service Level

| Aspekt | EPC (SEPA) | SPS (Typ S) |
|--------|-----------|-------------|
| **SvcLvl/Cd** | Muss "SEPA" sein | Muss "SEPA" sein |
| **SvcLvl/Prtry** | Nicht erlaubt | Nicht erlaubt |
| **Identisch?** | Ja |

**EPC-Quelle:** EPC132-08 Index 2.9

### 9. Adressanforderungen

| Aspekt | EPC (SEPA) | SPS |
|--------|-----------|-----|
| **Strukturiert** | Empfohlen | Empfohlen |
| **Hybrid** | Ab Okt 2025 unterstützt | Ab Nov 2025 unterstützt |
| **Unstrukturiert abschaffen** | Ab 15. Nov 2026 | Ab 20. Nov 2026 |
| **TwnNm + Ctry Pflicht** | Ja (bei strukturiert/hybrid) | Ja |
| **Identisch?** | Nahezu — Termine weichen um wenige Tage ab |

**EPC-Quelle:** EPC125-05 §2, EPC132-08 Index 2.23

### 10. Ausführungsdatum

| Aspekt | EPC (SEPA) | SPS (Typ S) |
|--------|-----------|-------------|
| **Kalender** | TARGET2 | TARGET2 |
| **Max Ausführungszeit** | D+1 Bankarbeitstag | D+1 Bankarbeitstag |
| **Identisch?** | Ja |

### 11. Zahlungsmethode

| Aspekt | EPC (SEPA) | SPS |
|--------|-----------|-----|
| **PmtMtd** | Nur TRF | TRF (Typ D/S/X), CHK (Typ C) |
| **Identisch?** | Ja (für Typ S) |

## Fazit: Regeln die nur in SPS existieren (nicht in EPC)

Diese Regeln sind SPS-spezifisch und haben keine EPC-Entsprechung:

| Rule-ID | Beschreibung | SPS-Typ |
|---------|-------------|---------|
| BR-QR-001..007 | QR-IBAN und QRR-Validierung | Typ D (Domestic QR) |
| BR-IBAN-001..006 | Domestic-IBAN-Regeln | Typ D (Domestic IBAN) |
| BR-CBPR-001..005 | CBPR+-Regeln | Typ X (Cross-Border) |
| BR-GEN-006 | Creditor-Name max 140 (non-SEPA) | Typ D/X |

## Fazit: Regeln die nur in EPC existieren (nicht in SPS)

Keine — SPS implementiert alle EPC-SEPA-Regeln vollständig.
