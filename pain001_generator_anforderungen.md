# Anforderungsdokument: pain.001 Test Generator

**Projekt:** ISO 20022 pain.001 XML Test Generator
**Version:** 1.1
**Datum:** 2026-03-15
**Status:** Entwurf

---

## Inhaltsverzeichnis

1. [Projektübersicht](#1-projektübersicht)
2. [Systemkontext](#2-systemkontext)
3. [Funktionale Anforderungen](#3-funktionale-anforderungen)
   - 3.1 Input: Testfall-Definition
   - 3.2 XML-Generierung
   - 3.3 Validierung
   - 3.4 Output & Ablage
   - 3.5 Phase 2: API-Integration
4. [Nicht-funktionale Anforderungen](#4-nicht-funktionale-anforderungen)
5. [Offene Punkte](#5-offene-punkte)
6. [Glossar](#6-glossar)

---

## 1. Projektübersicht

### 1.1 Ziel

Das System ermöglicht das automatisierte Erstellen von ISO 20022 pain.001 XML-Zahlungsdateien auf Basis von manuell definierten Testfällen. Die generierten Dateien sollen sowohl schema- als auch fachlich valide sein und für das Testen von Banking-APIs eingesetzt werden.

### 1.2 Phasen

| Phase | Beschreibung | Status |
|-------|-------------|--------|
| Phase 1 | Testfall-Einlesen, XML-Generierung, Validierung, Ablage | In Planung |
| Phase 2 | Versand an Banking-API, Response-Vergleich, erweitertes Reporting | Geplant (noch nicht spezifiziert) |

### 1.3 Abgrenzung

- Das System erstellt ausschliesslich pain.001-Nachrichten (keine anderen ISO 20022 Message Types).
- Phase 2 (API-Anbindung) wird nach erfolgreicher Abnahme von Phase 1 spezifiziert.
- Das System ersetzt keine manuelle Fachprüfung, sondern unterstützt und beschleunigt diese.

---

## 2. Systemkontext

### 2.1 Akteure

| Akteur | Beschreibung |
|--------|-------------|
| Tester | Definiert Testfälle im Excel, startet das System, bewertet Ergebnisse |
| Banking-API | Empfänger der pain.001-Dateien (Phase 2, noch nicht spezifiziert) |

### 2.2 Externe Abhängigkeiten

| Abhängigkeit | Beschreibung |
|-------------|-------------|
| XSD-Schema | pain.001.001.09, Swiss Payment Standards (SPS), bezogen aus GitHub-Repo |
| Business Rules | SPS-Regeln als `.md`-Dateien im GitHub-Repo (`https://github.com/Sebastenhauer/iso20022tester`) |
| Excel-Input | Vom Tester gepflegte Testfall-Datei |

---

## 3. Funktionale Anforderungen

### 3.1 Input: Testfall-Definition (Excel)

| Req-ID | Priorität | Anforderung |
|--------|-----------|-------------|
| FR-01 | MUSS | Das System liest eine Excel-Datei (.xlsx) als Input. |
| FR-02 | MUSS | Jede Zeile (ab Zeile 2) repräsentiert genau einen Testfall. |
| FR-03 | MUSS | Zeilen ohne `TestcaseID` werden übersprungen (keine Fehlermeldung). |
| FR-04 | MUSS | Die Excel-Datei enthält folgende Pflicht-Spalten (Reihenfolge fix): `TestcaseID`, `Titel`, `Ziel`, `Erwartetes Ergebnis`, `Zahlungstyp`, `Betrag`, `Währung`, `Debtor Infos`, `Weitere Testdaten`, `Erwartete API-Antwort`, `Ergebnis (OK/NOK)`, `Bemerkungen` |
| FR-05 | MUSS | Das System validiert beim Start, ob alle Pflicht-Spalten vorhanden sind. Bei fehlenden Spalten wird ein Fehler ausgegeben und der Lauf abgebrochen. |
| FR-06 | MUSS | `Debtor Infos` enthält strukturierten Freitext im Format `Key=Value; Key=Value`, z.B. `IBAN=CH5604835012345678009; Name=Muster AG; Strasse=Bahnhofstrasse 1; PLZ=8001; Ort=Zürich`. Pflicht-Keys: `IBAN`, `Name`. Optional: `BIC`, `Strasse`, `Hausnummer`, `PLZ`, `Ort`, `Land` (Default: CH). Es gibt keinen Default-Debtor — alle Debtor-Daten werden vollständig aus dem Excel eingelesen. |
| FR-07 | MUSS | `Weitere Testdaten` enthält Key=Value-Paare als Freitext, z.B. `ChrgBr=OUR; Cdtr.Nm=Müller AG`. Diese Werte überschreiben Defaults und Zufallswerte. |
| FR-08 | MUSS | `Zahlungstyp` enthält einen der Werte: `SEPA`, `Domestic-QR`, `Domestic-IBAN`, `CBPR+`. |
| FR-09 | MUSS | `Erwartetes Ergebnis` enthält einen der Werte: `OK` oder `NOK`. |
| FR-10 | KANN | Das System gibt eine Warnung aus, wenn einzelne empfohlene Felder in `Weitere Testdaten` fehlen, aber nicht zwingend erforderlich sind. |
| FR-11 | MUSS | Testfälle mit `TestcaseID`, aber fehlenden oder ungültigen Pflichtfeldern (z.B. ungültiger `Zahlungstyp`, fehlendes `Betrag`) werden nicht übersprungen. Das System gibt eine verständliche Fehlermeldung pro betroffenem Testfall aus und fordert den User zur Korrektur auf. Der Lauf wird erst nach vollständiger Prüfung aller Zeilen abgebrochen (Sammelfehler). |
| FR-12 | MUSS | Der User spezifiziert im Excel, welche Business Rule bei einem negativen Testfall (`Erwartetes Ergebnis = NOK`) gezielt verletzt werden soll. Dies erfolgt via `Weitere Testdaten` mit dem Schlüssel `ViolateRule=<Regelbezeichnung>` (z.B. `ViolateRule=ChrgBr-SEPA`). Das System verwendet diesen Hinweis zur Steuerung der Generierung und zur Auswertung. |
| FR-13 | MUSS | Mehrere Transaktionen pro XML-Datei werden im Excel via `Weitere Testdaten` mit dem Schlüssel `TxCount=<n>` spezifiziert (z.B. `TxCount=3`). Alle Transaktionen teilen dieselben B-Level-Attribute; individuelle C-Level-Overrides sind nicht vorgesehen (Phase 1). |

---

### 3.2 XML-Generierung

#### 3.2.1 Allgemein

| Req-ID | Priorität | Anforderung |
|--------|-----------|-------------|
| FR-20 | MUSS | Das System generiert XML-Dateien gemäss pain.001.001.09 (Swiss Payment Standards, neueste Version). |
| FR-21 | MUSS | Jede XML-Datei enthält genau einen `GrpHdr`-Block und mindestens einen `PmtInf`-Block mit mindestens einer `CdtTrfTxInf`. |
| FR-22 | MUSS | `MsgId` wird automatisch generiert (eindeutig pro Testfall und Lauf). |
| FR-23 | MUSS | `PmtInfId` wird automatisch generiert. |
| FR-24 | MUSS | `EndToEndId` wird automatisch generiert (eindeutig pro Transaktion). |
| FR-25 | MUSS | `CreDtTm` wird auf den Zeitpunkt der Generierung gesetzt. |
| FR-26 | MUSS | `ReqdExctnDt` wird auf das nächste Bankarbeitstag-Datum gesetzt (Default), sofern nicht via `Weitere Testdaten` übersteuert. Der verwendete Feiertagskalender ist zahlungstyp-abhängig: TARGET2-Kalender für SEPA, SIX-Kalender (Schweizer Bankfeiertage) für Domestic-QR, Domestic-IBAN und CBPR+. |
| FR-27 | MUSS | Felder, die weder Pflichtfeld des Zahlungstyps noch durch den User vorgegeben sind, werden zufällig aber valide befüllt (z.B. Creditor-Name, Adresse). |
| FR-28 | MUSS | Zufällig generierte IBANs sind prüfziffervalide (Mod-97-Algorithmus). |
| FR-29 | MUSS | User-Overrides aus `Weitere Testdaten` überschreiben alle Defaults und Zufallswerte. |
| FR-30 | MUSS | Bei negativen Testfällen (`Erwartetes Ergebnis = NOK`) darf das Schema (XSD) nicht verletzt werden. Business Rules können gezielt verletzt werden. |
| FR-30a | MUSS | `PmtMtd` ist immer `TRF` (Transfer). Bank Checks (`CHK`) werden in Phase 1 nicht unterstützt. |
| FR-30b | MUSS | Alle Textfelder werden gegen den SPS-Zeichensatz (Latin-1 Subset: `a-z A-Z 0-9 / - ? : ( ) . , ' +`) validiert. Ungültige Zeichen in User-Eingaben erzeugen eine Fehlermeldung. |
| FR-31 | SOLL | Reproduzierbarkeit: Bei gleichem Excel-Input und gleichem Seed werden identische Zufallswerte generiert (konfigurierbar). Der Seed gilt global pro Testlauf und beeinflusst alle zufällig generierten Werte (Feldwerte wie Namen, Adressen, IBANs) sowie automatisch generierte IDs (`MsgId`, `PmtInfId`, `EndToEndId`). `CreDtTm` ist vom Seed ausgenommen und spiegelt immer den tatsächlichen Generierungszeitpunkt. |
| FR-32 | KANN | Mehrere Transaktionen pro Datei: Standard ist 1 Transaktion. Mehrere Transaktionen via `TxCount=<n>` in `Weitere Testdaten` möglich (Phase 1, zweiter Schritt, siehe FR-13). |

#### 3.2.2 Zahlungstyp-Regelwerke

**SEPA Credit Transfer**

| Req-ID | Priorität | Anforderung |
|--------|-----------|-------------|
| FR-40 | MUSS | Währung: EUR (Pflicht). |
| FR-41 | MUSS | `ChrgBr`: SHA (Pflicht, sofern nicht durch negativen TC übersteuert). |
| FR-42 | MUSS | Creditor IBAN: vorhanden und im SEPA-Raum (Pflicht). |
| FR-43 | MUSS | `SvcLvl/Cd`: SEPA. |
| FR-44 | SOLL | Creditor BIC: optional, wird zufällig befüllt falls nicht angegeben. |
| FR-45 | MUSS | `CtgyPurp`: nicht zwingend, aber valide falls angegeben. |

**Domestic CH — QR-Zahlung**

| Req-ID | Priorität | Anforderung |
|--------|-----------|-------------|
| FR-50 | MUSS | Creditor: QR-IBAN (Pflicht). |
| FR-51 | MUSS | Referenz: QRR (Pflicht bei QR-IBAN, wird zufällig generiert falls nicht angegeben). SCOR ist bei QR-IBAN **nicht** zulässig. SCOR kann optional bei regulärer IBAN mitgegeben werden. |
| FR-52 | MUSS | Währung: CHF oder EUR. |
| FR-53 | MUSS | `SvcLvl/Cd`: wird gemäss SPS-Vorgaben gesetzt. |
| FR-54 | MUSS | Creditor-Adresse: strukturiert oder unstrukturiert gemäss SPS. |

**Domestic CH — klassische IBAN-Zahlung**

| Req-ID | Priorität | Anforderung |
|--------|-----------|-------------|
| FR-60 | MUSS | Creditor: klassische CH-IBAN (nicht QR-IBAN). |
| FR-61 | MUSS | Keine strukturierte Zahlungsreferenz erforderlich. |
| FR-62 | MUSS | Währung: CHF. |

**CBPR+ (Cross-Border Payments and Reporting Plus)**

| Req-ID | Priorität | Anforderung |
|--------|-----------|-------------|
| FR-70 | MUSS | Zahlungstyp für alle Zahlungen ausserhalb SEPA-Raum und ausserhalb CHF-Inland. |
| FR-71 | MUSS | Währung und Zielland werden vom User vorgegeben (kein Default). |
| FR-72 | MUSS | Creditor-BIC oder Clearing-System-Identifikation: gemäss SPS/CBPR+-Vorgaben. Muss vom User im Excel via `Weitere Testdaten` angegeben werden (z.B. `CdtrAgt.BICFI=BNPAFRPP`). Das System gibt eine verständliche Fehlermeldung aus, wenn der Creditor-Agent bei CBPR+ fehlt. |
| FR-73 | MUSS | `SvcLvl` und `LclInstrm`: gemäss CBPR+-Regelwerk. |

---

### 3.3 Validierung

| Req-ID | Priorität | Anforderung |
|--------|-----------|-------------|
| FR-80 | MUSS | Jede generierte XML-Datei wird gegen das XSD (pain.001.001.09, SPS) validiert. |
| FR-81 | MUSS | Schema-invalide Dateien werden nicht gespeichert (Ausnahme: keine). |
| FR-82 | MUSS | Bei Schema-Validierungsfehler wird eine klare Fehlermeldung ausgegeben (XSD-Fehlerbeschreibung + betroffenes Element). |
| FR-83 | MUSS | Business-Rule-Validierung läuft nach erfolgreicher XSD-Validierung. |
| FR-84 | MUSS | Business Rules basieren auf den `.md`-Dateien aus dem GitHub-Repo (`https://github.com/Sebastenhauer/iso20022tester`). Die Dateien `business-rules-sps-2025-de.md` und `ig-credit-transfer-sps-2025-de.md` enthalten strukturierten Prosatext mit Tabellen, aber keine maschinenlesbaren Rule-IDs. Business Rules werden daher als Code-Module implementiert, die sich inhaltlich auf die Kapitel und Tabellen dieser Dokumente beziehen. Jede implementierte Regel erhält eine interne ID (z.B. `BR-SEPA-001`) zur Referenzierung im Report. |
| FR-84a | MUSS | Das XSD-Schema (`pain.001.001.09.ch.03.xsd`) wird lokal aus dem GitHub-Repo bezogen und im Projekt unter `schemas/` abgelegt. Der Pfad wird in `config.yaml` konfiguriert. Das Schema wird nicht zur Laufzeit vom Netz geladen. |
| FR-85 | MUSS | Pass/Fail-Logik: Erwartetes Ergebnis `OK` + alle Validierungen bestanden → **Pass**. |
| FR-86 | MUSS | Pass/Fail-Logik: Erwartetes Ergebnis `NOK` + mindestens eine Business Rule verletzt → **Pass**. |
| FR-87 | MUSS | Alle anderen Kombinationen → **Fail**, mit Angabe der abweichenden Validierungsergebnisse. |
| FR-88 | SOLL | Das System gibt an, welche spezifische Business Rule verletzt wurde (interne Rule-ID, z.B. `BR-SEPA-001`, mit Kurzbeschreibung im Report). |

---

### 3.4 Output & Ablage

| Req-ID | Priorität | Anforderung |
|--------|-----------|-------------|
| FR-90 | MUSS | Der User konfiguriert einen übergeordneten Output-Ordner (via `config.yaml`). |
| FR-91 | MUSS | Pro Testlauf wird automatisch ein Unterordner erstellt: `YYYY-MM-DD_HHMMSS/`. |
| FR-92 | MUSS | XML-Dateien werden gespeichert als: `{TestcaseID}_{Titel}.xml` (Sonderzeichen im Titel werden ersetzt). |
| FR-93 | MUSS | Auch Business-Rule-verletzende Dateien (negativer TC, schema-valide) werden gespeichert. |
| FR-94 | MUSS | Pro Testlauf wird eine Zusammenfassung erstellt (`Testlauf_Zusammenfassung.docx`, bevorzugtes Format; `.txt` als Fallback, konfigurierbar). |
| FR-95 | MUSS | Die Zusammenfassung enthält: Testlauf-Datum/-Uhrzeit, Input-Excel-Dateiname, Anzahl Testfälle gesamt, Anzahl Pass, Anzahl Fail. |
| FR-96 | MUSS | Die Zusammenfassung enthält pro Testfall: TestcaseID, Titel, Zahlungstyp, XSD-Status, Business-Rule-Status, Pass/Fail, Bemerkungen. |
| FR-97 | MUSS | Bei Fehlern (z.B. ungültiger Excel-Input) wird eine verständliche Fehlermeldung ausgegeben und der Lauf sauber beendet. |

---

### 3.5 Phase 2: API-Integration *(geplant)*

> **Hinweis:** Die nachfolgenden Anforderungen sind noch nicht vollständig spezifiziert. Details werden nach Abnahme von Phase 1 erarbeitet.

| Req-ID | Priorität | Anforderung |
|--------|-----------|-------------|
| FR-100 | MUSS | Das System sendet generierte XML-Dateien an eine konfigurierbare Banking-API. |
| FR-101 | MUSS | Authentifizierungsverfahren ist konfigurierbar (OAuth, mTLS, API-Key — tbd.). |
| FR-102 | MUSS | Die API-Antwort (pain.002 oder proprietäres Format — tbd.) wird ausgelesen. |
| FR-103 | MUSS | Die tatsächliche API-Antwort wird mit der in Excel definierten `Erwarteten API-Antwort` verglichen. |
| FR-104 | MUSS | Abweichungen zwischen tatsächlicher und erwarteter Antwort werden im Testlauf-Bericht dokumentiert. |
| FR-105 | SOLL | Die API-Antwort wird als Datei im Testlauf-Ordner gespeichert. |

---

## 4. Nicht-funktionale Anforderungen

| Req-ID | Kategorie | Priorität | Anforderung |
|--------|-----------|-----------|-------------|
| NF-01 | Technologie | MUSS | Implementierung in Python 3.10 oder höher. |
| NF-02 | Technologie | MUSS | Abhängigkeiten: `lxml` (XML/XSD), `openpyxl` (Excel), `faker` (Testdaten), `python-docx` (Word-Output), `PyYAML` (Konfiguration). |
| NF-03 | Technologie | MUSS | Konfiguration via `config.yaml` (Output-Pfad, XSD-Pfad, Seed [optional], Report-Format [`docx`/`txt`]). |
| NF-04 | Betrieb | MUSS | Lokale Ausführung auf Standard-Arbeitsrechner (Windows, macOS, Linux) ohne spezielle Infrastruktur. |
| NF-05 | Betrieb | SOLL | Containerisierung (Docker) als Option für spätere Laufumgebungen (noch zu entscheiden). |
| NF-06 | Wartbarkeit | MUSS | Zahlungstyp-Regelwerke sind als separate, konfigurierbare Module implementiert (erweiterbar für neue Typen). |
| NF-07 | Wartbarkeit | MUSS | Business Rules sind deklarativ definiert und unabhängig vom Generator-Code pflegbar. |
| NF-08 | Sicherheit | MUSS | Keine echten Produktivdaten (IBANs, Namen) werden im Code fest hinterlegt. |
| NF-09 | Usability | MUSS | Das System wird über die Kommandozeile gestartet: `python main.py --input testfaelle.xlsx --config config.yaml`. |
| NF-10 | Usability | MUSS | Fehlermeldungen sind auf Deutsch und fachlich verständlich. |
| NF-11 | Qualität | SOLL | Unit Tests für IBAN-Generator, Excel-Parser und Zahlungstyp-Regelwerke. |
| NF-12 | Qualität | SOLL | End-to-End-Test mit Beispiel-Excel (mindestens 1 TC pro Zahlungstyp, je positiv und negativ). |

---

## 5. Offene Punkte

| OP-ID | Thema | Beschreibung | Status | Fällig bis |
|-------|-------|-------------|--------|-----------|
| OP-01 | Excel-Struktur | ~~Entscheid: Werden `Zahlungstyp`, `Betrag` und `Währung` als eigene Pflicht-Spalten geführt?~~ **Entschieden: Ja, als dedizierte Pflicht-Spalten (FR-04).** | Geschlossen | — |
| OP-02 | Mehrere Transaktionen | Spezifikation für Testfälle mit mehreren `CdtTrfTxInf` pro Datei. Grundmechanismus via `TxCount=<n>` in `Weitere Testdaten` definiert (FR-13, FR-32). Individuelle C-Level-Konfiguration pro Transaktion ist Phase-1-Schritt-2 (noch nicht spezifiziert). | Teilweise offen | Offen |
| OP-03 | Laufumgebung | Entscheid: nur lokal oder auch containerisiert (Docker)? | Offen | Offen |
| OP-04 | Phase 2 API | Spezifikation der Banking-API: Endpunkt, Authentifizierung, Response-Format. | Offen | Nach Phase-1-Abnahme |
| OP-05 | Report-Format | ~~Entscheid: Zusammenfassung als `.txt` oder `.docx`?~~ **Entschieden: `.docx` bevorzugt, `.txt` als konfigurierbarer Fallback (FR-94).** | Geschlossen | — |
| OP-06 | Business Rule Engine | Die SPS-Dokumente enthalten keine maschinenlesbaren Rule-IDs. Business Rules werden als Code-Module mit internen IDs implementiert. **Entschieden:** Regeln werden direkt aus den SPS-Textdateien abgeleitet. Vollständiger Regelkatalog ist in SDD v2.1 §5.7 dokumentiert. | Geschlossen | — |

---

## 6. Glossar

| Begriff | Erklärung |
|---------|-----------|
| pain.001 | ISO 20022 Message Type: CustomerCreditTransferInitiation. Zahlungsauftrag vom Kunden an die Bank. |
| pain.002 | ISO 20022 Message Type: CustomerPaymentStatusReport. Statusantwort der Bank. |
| SPS | Swiss Payment Standards. Schweizer Implementierungsrichtlinien für ISO 20022, herausgegeben von SIX Group. |
| SEPA | Single Euro Payments Area. Einheitlicher Eurozahlungsverkehrsraum. |
| CBPR+ | Cross-Border Payments and Reporting Plus. ISO 20022-Standard für grenzüberschreitende Zahlungen ausserhalb SEPA. |
| QR-IBAN | Schweizer IBAN-Variante für QR-Rechnungen (Prefix 30–31). |
| QRR | QR-Referenz. 27-stellige numerische Referenz für QR-Rechnungen. |
| SCOR | Structured Creditor Reference (ISO 11649). Strukturierte Referenz für Rechnungen. |
| XSD | XML Schema Definition. Definiert die erlaubte Struktur einer XML-Datei. |
| Mod-97 | Prüfziffer-Algorithmus zur Validierung von IBANs. |
| GrpHdr | `GroupHeader`. Kopfzeile einer pain.001-Nachricht. |
| PmtInf | `PaymentInformation`. Zahlungsinformations-Block (1..n pro Nachricht). |
| CdtTrfTxInf | `CreditTransferTransactionInformation`. Einzeltransaktion (1..n pro PmtInf). |
| ChrgBr | `ChargeBearer`. Gibt an, wer die Überweisungsgebühren trägt (SHA, OUR, BEN). |
| EndToEndId | Eindeutige Referenz, die durch die gesamte Zahlungskette durchgereicht wird. |
| TC | Testfall (Testcase). |
| Pass / Fail | Bewertung eines Testfalls: Pass = Ergebnis entspricht Erwartung, Fail = Abweichung. |
