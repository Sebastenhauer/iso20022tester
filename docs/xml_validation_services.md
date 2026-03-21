# Validierungsmöglichkeiten für pain.001 XML-Dateien

**Datum:** 21. März 2026
**Zweck:** Übersicht über Services und Tools zur externen Validierung der generierten pain.001.001.09 XML-Dateien

---

> **Hinweis:** Dieses Dokument dient als Entscheidungsgrundlage für die Auswahl externer Validierungsdienste.
> Unser Tool führt bereits intern eine zweistufige Validierung durch (XSD-Schema + 30+ Business Rules).
> Die hier aufgeführten Services ermöglichen eine **unabhängige Gegenprüfung** durch Dritte — insbesondere
> durch das offizielle SIX Validation Portal — um sicherzustellen, dass die generierten XML-Dateien
> auch ausserhalb unserer eigenen Implementierung als konform erkannt werden.

---

## Zusammenfassung

Unsere generierten XML-Dateien werden bereits intern gegen das XSD-Schema und 30+ Business Rules validiert. Für eine **unabhängige, externe Validierung** gibt es mehrere Optionen — von kostenlosen Online-Tools bis hin zu professionellen Enterprise-Plattformen. Die wichtigste Erkenntnis: **das offizielle SIX Validation Portal ist kostenlos und sollte die primäre Validierungsquelle sein.**

---

## 1. Offizielle Plattformen

### 1.1 SIX Validation Portal (⭐ Empfehlung #1)

| Eigenschaft | Details |
|------------|---------|
| **URL** | [validation.iso-payments.ch/SPS](https://validation.iso-payments.ch/sps/account/logon) |
| **Anbieter** | SIX Interbank Clearing AG |
| **Preis** | **Kostenlos** |
| **Registrierung** | Ja, mit geschäftlicher E-Mail (keine Freemail-Adressen wie Gmail/GMX) |
| **Format** | pain.001.001.09 (SPS 2025) ✅ |
| **Validierung** | XSD + SPS Implementation Guidelines |
| **Output** | Testbericht als Text und HTML (Download möglich) |

**Was wird geprüft:**
- XSD-Schema-Validität
- Konformität mit den Swiss Payment Standards Implementation Guidelines
- Strukturelle Korrektheit der Nachricht

**Was wird NICHT geprüft:**
- Veränderbare Parameter oder Werte aus externen Code-Listen
- Gültige Partei-Identifikationen
- Währungscodes oder ISO 20022 External Code Sets

**Vorteile:**
- Offizielle Referenz-Validierung der Schweizer Finanzbranche
- Kostenlos für Software-Anbieter und Finanzinstitute
- Unterstützt die aktuelle SPS 2025 Version
- Upload via Web-Interface

**Nachteile:**
- Keine API-Integration (nur manueller Upload)
- Geschäftliche E-Mail für Registrierung erforderlich
- Kein automatisierter Batch-Betrieb möglich

**Bewertung:** ★★★★★ — Die offizielle Referenz. Jede generierte Datei sollte mindestens einmal hierüber validiert werden.

---

### 1.2 SIX QR-Rechnung Validation Portal

| Eigenschaft | Details |
|------------|---------|
| **URL** | [validation.iso-payments.ch/qrrechnung](https://validation.iso-payments.ch/qrrechnung/account/logon) |
| **Preis** | **Kostenlos** |
| **Scope** | QR-Rechnung spezifisch (nicht direkt pain.001) |

Relevant nur für die Validierung von QR-Referenzen und QR-IBANs als Ergänzung.

---

## 2. Kommerzielle Plattformen

### 2.1 XMLdation Validator

| Eigenschaft | Details |
|------------|---------|
| **URL** | [xmldation.com/en/solutions/components/validator](https://www.xmldation.com/en/solutions/components/validator) |
| **Anbieter** | XMLdation Ltd. (Finnland) |
| **Preis** | **Auf Anfrage** (Enterprise-Lizenz, Demo verfügbar) |
| **Format** | ISO 20022 (inkl. pain.001.001.09) ✅ |
| **API** | Ja, REST-API für automatisierte Validierung |
| **Support** | Support@XMLdation.com |

**Was wird geprüft:**
- XSD-Schema-Validität
- Bankspezifische und Service-spezifische Regeln
- Hunderte von Format-Varianten
- Detaillierte Fehlerberichte mit exakter Fehlerposition

**Vorteile:**
- Marktführer für ISO 20022 Validierung
- API-Integration möglich (automatisierbar)
- Bankspezifische Regelwerke konfigurierbar
- Detaillierte, verständliche Fehlerberichte

**Nachteile:**
- Preis nur auf Anfrage (typisch Enterprise-Preissegment)
- Overkill für Einzelvalidierung
- Keine kostenlose Testversion öffentlich verfügbar

**Bewertung:** ★★★★☆ — Professionellste Lösung, aber erst relevant wenn automatisierte Validierung im CI/CD gebraucht wird.

---

### 2.2 Truugo ISO 20022 Validator

| Eigenschaft | Details |
|------------|---------|
| **URL** | [truugo.com/iso20022_validator](https://www.truugo.com/iso20022_validator/) |
| **Preis** | **Freemium** (kostenlose Testcredits bei Registrierung) |
| **Format** | pain.001.001.03 (Basic-Profil) — pain.001.001.09 unklar |
| **API** | Ja (kostenpflichtig) |

**Was wird geprüft:**
- XSD-Schema-Validität (Basic-Profil)
- Konfigurierbare Constraints (Pflichtfelder, Code-Listen, Längen, Integritätsregeln)

**Vorteile:**
- Kostenlose Testcredits
- API für Automatisierung
- No-Code UI für eigene Validierungsprofile

**Nachteile:**
- Basic-Profil nur Schema-Validierung
- pain.001.001.09 Support nicht bestätigt
- Kostenpflichtig für regelmässige Nutzung

**Bewertung:** ★★★☆☆ — Interessant für Custom-Validierungsprofile, aber SPS-2025-Support unsicher.

---

### 2.3 20022Labs

| Eigenschaft | Details |
|------------|---------|
| **URL** | [20022labs.com/message-validation-tools](https://20022labs.com/message-validation-tools/) |
| **Preis** | **Auf Anfrage** |
| **Format** | ISO 20022 (Fokus auf MT→MX Migration) |
| **Sandbox** | [20022labs.com/sandbox](https://20022labs.com/sandbox/) |

**Was wird geprüft:**
- ISO 20022 XML-Struktur
- MT→ISO 20022 Transformation

**Bewertung:** ★★☆☆☆ — Fokus auf SWIFT-Migration, weniger auf SPS-spezifische Validierung.

---

## 3. Kostenlose Online-Tools

### 3.1 TreasuryHost PAIN.001 Validator

| Eigenschaft | Details |
|------------|---------|
| **URL** | [treasuryhost.eu/solutions/painp](https://www.treasuryhost.eu/solutions/painp/) |
| **Preis** | **Kostenlos** (Web), API kostenpflichtig |
| **Format** | pain.001 (SEPA) |
| **Registrierung** | Nein |

**Was wird geprüft:**
- SEPA ISO 20022 Schema-Validierung
- Tabellarische Anzeige aller Zahlungen

**Vorteile:**
- Sofort nutzbar, keine Registrierung
- Übersichtliche Darstellung der Zahlungen
- API für Automatisierung verfügbar

**Nachteile:**
- Fokus auf SEPA (pain.001.001.03), nicht SPS 2025
- Keine Business-Rule-Validierung
- Daten werden an externen Server gesendet

**Bewertung:** ★★★☆☆ — Gut für schnelle SEPA-Prüfung, nicht für SPS-spezifische Validierung.

---

### 3.2 Mobilefish.com SEPA XML Validator

| Eigenschaft | Details |
|------------|---------|
| **URL** | [mobilefish.com/services/sepa_xml_validation](https://www.mobilefish.com/services/sepa_xml_validation/sepa_xml_validation.php) |
| **Preis** | **Kostenlos** |
| **Format** | SEPA pain.001.001.03 |
| **Registrierung** | Nein |

**Vorteile:**
- Sofort nutzbar
- Einfache Bedienung

**Nachteile:**
- Nur pain.001.001.03 (nicht .09)
- Nur SEPA, keine SPS-Regeln
- Daten werden hochgeladen

**Bewertung:** ★★☆☆☆ — Nur für schnelle SEPA-Checks älterer Versionen.

---

### 3.3 SEPAViewer (Kibervarnost)

| Eigenschaft | Details |
|------------|---------|
| **URL** | [kibervarnost.si/sepaviewer](https://kibervarnost.si/sepaviewer/) |
| **Preis** | **Kostenlos** |
| **Format** | pain.001.001.03 |
| **Datenschutz** | Client-side (Daten bleiben im Browser) |

**Was wird geboten:**
- XML-Viewer mit Bearbeitungsfunktion
- IBAN-Validierung
- CSV-Export
- Kein Server-Upload (alles im Browser)

**Vorteile:**
- Datenschutzfreundlich (kein Upload)
- Bearbeitung direkt im Browser
- IBAN-Validierung eingebaut

**Nachteile:**
- Nur pain.001.001.03
- Kein SPS-2025-Support
- Viewer, kein vollständiger Validator

**Bewertung:** ★★★☆☆ — Bester kostenloser Viewer für Datenschutz-bewusste Nutzung.

---

## 4. Bank-spezifische Tools

### 4.1 Danske Bank File Validation Tool

| Eigenschaft | Details |
|------------|---------|
| **URL** | [danskeci.com/.../file-validation-tool](https://danskeci.com/ci/transaction-banking/instructions/integration-services/file-validation-tool) |
| **Preis** | **Kostenlos** (für Danske-Bank-Kunden) |
| **Format** | pain.001.001.03 |
| **Datenaufbewahrung** | 24 Stunden, dann gelöscht |

**Einschränkungen:**
- Nur pain.001.001.03
- Copyright-geschützt, nur für Bank-Kunden
- Testkonten erforderlich für Payment-Details

**Bewertung:** ★★☆☆☆ — Nur relevant für Danske-Bank-Kunden.

---

### 4.2 SEB Developer Portal

| Eigenschaft | Details |
|------------|---------|
| **URL** | [developer.baltics.sebgroup.com/tools/non-api-tools](https://developer.baltics.sebgroup.com/tools/non-api-tools) |
| **Preis** | **Kostenlos** |
| **Scope** | SEB-spezifische Formate |

**Bewertung:** ★★☆☆☆ — Nur relevant für SEB-Kunden.

---

## 5. Lokale / Eigene Validierung

### 5.1 Eigene XSD-Validierung (bereits implementiert ✅)

Unser Tool validiert bereits jede generierte XML-Datei gegen `pain.001.001.09.ch.03.xsd`. Dies deckt die Schema-Ebene vollständig ab.

### 5.2 Python `xmlschema` Library

| Eigenschaft | Details |
|------------|---------|
| **URL** | [pypi.org/project/xmlschema](https://pypi.org/project/xmlschema/) |
| **Preis** | **Kostenlos** (Open Source) |
| **Vorteil** | Strengere XSD-Validierung als lxml in manchen Fällen |

Alternative zu lxml für XSD-Validierung. Kann als Second-Opinion-Validator eingesetzt werden.

### 5.3 Pain001 Python Library

| Eigenschaft | Details |
|------------|---------|
| **URL** | [github.com/sebastienrousseau/pain001](https://github.com/sebastienrousseau/pain001) |
| **Preis** | **Kostenlos** (Open Source, MIT) |
| **Format** | pain.001.001.03 bis .11 |

Generiert und validiert pain.001-Dateien. Könnte als Referenz-Implementierung zum Vergleich dienen, ist aber primär ein Generator, kein Validator.

---

## 6. Empfehlung: Validierungsstrategie

### Sofort umsetzen (Phase 1)

| Schritt | Tool | Aufwand | Kosten |
|---------|------|---------|--------|
| **1. Interne Validierung** | Eigene XSD + Business Rules | ✅ Bereits implementiert | Kostenlos |
| **2. SIX Validation Portal** | validation.iso-payments.ch | Registrierung + manueller Upload | Kostenlos |
| **3. TreasuryHost** | treasuryhost.eu | Kein Aufwand, sofort nutzbar | Kostenlos |

### Empfohlener Workflow

```
1. XML generieren (unser Tool)
        │
        ▼
2. Interne Validierung (XSD + Business Rules)
        │ ✅ Pass
        ▼
3. Stichproben-Validierung auf SIX Portal
   (mindestens 1x pro Zahlungstyp)
        │ ✅ Pass
        ▼
4. Optional: TreasuryHost für schnelle SEPA-Checks
        │
        ▼
5. Ergebnis dokumentieren
```

### Später (Phase 2 / CI/CD)

Wenn automatisierte Validierung im CI/CD-Pipeline gebraucht wird:

1. **XMLdation API** evaluieren (Demo anfordern: [xmldation.com/en/demo](https://www.xmldation.com/en/demo/))
2. **TreasuryHost API** als günstigere Alternative prüfen
3. **Second-Opinion-Validator** mit `xmlschema` Library als lokale Ergänzung

### Nicht empfohlen

- Mobilefish.com, Danske Bank, SEB → zu alt (nur .03), zu bank-spezifisch
- 20022Labs → Fokus auf MT→MX Migration, nicht SPS

---

## Quellen

- [SIX Group — Tools & Validation Portals](https://www.six-group.com/en/products-services/banking-services/payment-standardization/expertise/tools.html)
- [SIX Validation Portal Login](https://validation.iso-payments.ch/sps/account/logon)
- [SIX Download Center](https://www.six-group.com/en/products-services/banking-services/payment-standardization/downloads-faq/download-center.html)
- [XMLdation Validator](https://www.xmldation.com/en/solutions/components/validator)
- [XMLdation pain.001 Wiki](https://knowledge.xmldation.com/iso_20022/pain.001)
- [Truugo ISO 20022 Validator](https://www.truugo.com/iso20022_validator/)
- [20022Labs Message Validation Tools](https://20022labs.com/message-validation-tools/)
- [TreasuryHost PAIN.001 Validator](https://www.treasuryhost.eu/solutions/painp/)
- [Mobilefish SEPA Validator](https://www.mobilefish.com/services/sepa_xml_validation/sepa_xml_validation.php)
- [SEPAViewer (Kibervarnost)](https://kibervarnost.si/sepaviewer/)
- [Danske Bank File Validation Tool](https://danskeci.com/ci/transaction-banking/instructions/integration-services/file-validation-tool)
- [Pain001 Python Library](https://github.com/sebastienrousseau/pain001)
- [lxml Validation Documentation](https://lxml.de/validation.html)
