# Externe Validierungsservices für ISO 20022 Payment-XML

> **Hinweis:** Dieses Dokument liefert einen kuratierten Überblick über externe Tools zur unabhängigen Validierung von pain.001- und (perspektivisch) pacs.008-Nachrichten gegen die Implementation Guidelines **SPS 2025**, **CBPR+** und **CGI-MP**. Alle Angaben wurden am Recherchedatum (siehe Footer) direkt von den jeweiligen Websites gezogen; wo das nicht möglich war, ist dies explizit vermerkt.

## Zusammenfassung / Kurzübersicht

| # | Tool | Messages | Versionen | IGs | Preis | Nutzung | Bewertung |
|---|------|----------|-----------|-----|-------|---------|-----------|
| 1 | SIX Validation Portal | pain.001, pain.002, camt.05x | pain.001.001.09.ch.03, .03.ch.02 | **SPS 2025** | kostenlos (Registrierung) | Web-UI | 5/5 |
| 2 | SWIFT MyStandards Readiness Portal | pain.001, pacs.008, pacs.009, camt | alle aktuellen CBPR+-Versionen (pacs.008.001.08) | **CBPR+**, MI-spezifisch | Free Tier vorhanden; Readiness Portal via Bank | Web-UI | 5/5 (CBPR+) |
| 3 | XMLdation Validator | pain, pacs, camt | nicht öffentlich gelistet | SEPA, CGI-MP, nordische IGs, bankspezifisch | Freemium/B2B (keine Liste) | Web-UI + API | 3/5 |
| 4 | Truugo ISO 20022 Validator | pain.001, pain.002, camt.053, camt.054 | **nur V02/V03** der Basisschemas | generisch ISO 20022 | Free-Account limitiert; Essential 99 EUR/Mo | Web-UI + API | 1/5 (zu alt) |
| 5 | 20022Labs Sandbox | diverse | Sandbox im Aufbau, Fokus CA RTP | nicht spezifiziert | auf Website nicht angegeben | Web | 1/5 |
| 6 | TreasuryHost PAINP | pain.001 | pain.001.001.03 und **.09** | nur XSD (keine IG) | Free Demo + kostenpflichtige API | Web-UI + API | 3/5 |
| 7 | Mobilefish SEPA Validator | pain.001, pain.008 | **.02/.03** | XSD-only | kostenlos, ohne Registrierung | Web-UI | 1/5 (zu alt) |
| 8 | SEPAViewer (kibervarnost.si) | pain.001 | **.03 (SEPA)** | SEPA Viewer | kostenlos, lokal im Browser | Web-UI (Client) | 2/5 |
| 9 | Danske Bank File Validation | pain.001 | von Bank abhängig | Danske-IG | kostenlos (Kundenzugang) | Web-UI | n/a (bankspezifisch) |
| 10 | SEB Developer Portal Tools | pain.001 | nicht dokumentierbar (JS-SPA) | SEB-IG | kostenlos | Web-UI | n/a |
| 11 | FINaplo (Payment Components) | pain, pacs, camt | u.a. pain.001.001.09, pacs.008.001.08 | **CBPR+, SEPA, Fed, TARGET2** | Freemium + kostenpflichtig | Web-UI + REST-API + Java/.NET lib | 4/5 |
| 12 | Prowide ISO 20022 (OSS) | alle MX | generisch (XSD-basiert) | keine IG-Regeln | Open Source (Apache 2.0) | Java-Library | 3/5 (Baukasten) |
| 13 | pyiso20022 (OSS) | PAIN/PACS/CAMT/HEAD | generisch | keine | Open Source | Python-Library | 3/5 |

---

## 1. Offizielle Validatoren

### 1.1 SIX Validation Portal (Swiss Payment Standards)
- **URL:** https://validation.iso-payments.ch/sps/account/logon
- **Messages / Versionen:** pain.001.001.09.ch.03, pain.001.001.03.ch.02, pain.002, camt.05x (gemäss SPS-Katalog)
- **IGs:** Swiss Payment Standards 2025 (primäre Referenz für CH)
- **Preis:** kostenlos
- **Nutzung:** Web-UI nach Registrierung
- **Registrierung:** ja, Account notwendig (Business-Kontext; Gmail-Adressen werden akzeptiert, Profil muss gepflegt werden)
- **Datenschutz:** gemäss SIX-Nutzungsbedingungen (Details nur nach Login einsehbar)
- **Bewertung:** ★★★★★ — **Primärservice** für SPS-Validierung. Praktisch unverzichtbar als Goldstandard, weil Regeln 1:1 von SIX gepflegt werden.

### 1.2 SWIFT MyStandards / Readiness Portal (CBPR+)
- **URL:** https://www.swift.com/products/mystandards , https://www.swift.com/cbpr-self-attestation
- **Messages / Versionen:** alle CBPR+-relevanten Nachrichten, insb. **pacs.008.001.08**, pacs.009, pacs.004, camt.05x, camt.029, camt.056
- **IGs:** **CBPR+** Usage Guidelines, zahlreiche Market-Infrastructure-/Bank-spezifische Guidelines
- **Preis:** **Free Tier** für Individuen/Corporates mit gültigem swift.com-Account (kein SWIFT-Kunde nötig). Erweiterte Funktionen (Premium+/Lite) sowie bankspezifische Readiness-Portals meist über die jeweilige Bank zugänglich, Pricing nicht öffentlich.
- **Nutzung:** Web-UI; Nachrichten können per Drag&Drop gegen Usage Guideline getestet werden
- **Registrierung:** ja, swift.com-Account
- **Datenschutz:** Enterprise-grade (SWIFT), Uploads sind für User-Projekte persistent
- **Bewertung:** ★★★★★ für **CBPR+**. Einziger echter Goldstandard für Cross-Border-Validierung gegen die offiziellen CBPR+ Usage Guidelines.

---

## 2. Kommerzielle Services mit Free/Freemium

### 2.1 XMLdation
- **URL:** https://www.xmldation.com/
- **Messages / Versionen:** breite Abdeckung (pain, pacs, camt); konkrete öffentliche Liste auf der Startseite **nicht angegeben** — detaillierte Matrix nur nach Kontakt / in der Knowledgebase
- **IGs:** SEPA (EPC), nordische Banken, **CGI-MP** (historisch unterstützt), bankspezifische IGs; SPS 2025 nicht explizit beworben
- **Preis:** Payments-Testing-as-a-Service für Banken/PSOs; öffentliche Preisliste nicht vorhanden (Sales-Prozess). Früher existierte ein kostenloser Community-Validator — Status aktuell **auf der Website nicht angegeben**.
- **Nutzung:** Web-UI + REST-API (Simulatoren, Testprofile)
- **Registrierung:** ja, Businesskontakt
- **Bewertung:** ★★★☆☆ — Technisch stark, aber als Free-Second-Opinion kaum zugänglich. Relevant falls CGI-MP-Bankvarianten benötigt werden.

### 2.2 Truugo ISO 20022 Validator
- **URL:** https://www.truugo.com/iso20022_validator/ , https://www.truugo.com/pricing/
- **Messages / Versionen:** laut Toolseite nur **Credit Transfer Initiation V03, Payment Status Report V03, Account Statement V02, Debit/Credit Notification V02** — **kein** pain.001.001.09, **kein** pacs.008
- **IGs:** generische ISO 20022 XSD-Validierung
- **Preis:** Free-Account (stark limitiert); Essential 99 EUR/Monat, Advanced 259 EUR, Premium 499 EUR, Enterprise auf Anfrage; API-Lizenz 79–439 EUR/Monat
- **Nutzung:** Web-UI + API
- **Registrierung:** ja
- **Bewertung:** ★☆☆☆☆ — **Für unseren Use Case ungeeignet**, da ausschliesslich V02/V03 angeboten wird. Siehe Ausschlussliste.

### 2.3 20022Labs — Sandbox & Validation Tools
- **URL:** https://20022labs.com/message-validation-tools/ , https://20022labs.com/sandbox/
- **Messages / Versionen:** Tool-Seite ist eine *kuratierte Liste* fremder Tools (Trace Financial, Volante, XMLdation, NACHA, Unifits, Truugo) — **kein** eigener Validator. Sandbox derzeit im Aufbau (Fokus kanadische RTP).
- **IGs:** keine eigene
- **Preis / Registrierung:** auf Website nicht angegeben
- **Bewertung:** ★☆☆☆☆ — Als Verzeichnis hilfreich, nicht als Validator.

### 2.4 TreasuryHost PAINP
- **URL:** https://www.treasuryhost.eu/solutions/painp/
- **Messages / Versionen:** pain.001.001.03 **und pain.001.001.09**
- **IGs:** Validierung explizit nur gegen das **ISO 20022 XSD-Schema** — keine SPS/CBPR+/CGI-MP-Rules
- **Preis:** kostenlose Demo (Web-Upload, Excel-Konvertierung); API kostenpflichtig, Preise auf Anfrage
- **Nutzung:** Web-UI + REST-API
- **Registrierung:** für Demo nicht zwingend, API ja
- **Datenschutz:** auf Website nicht angegeben
- **Bewertung:** ★★★☆☆ — Gut als zweite XSD-Meinung für pain.001.001.09. Taugt **nicht** als IG-Validator.

### 2.5 FINaplo (Payment Components)
- **URL:** https://finaplo.paymentcomponents.com/ , https://www.paymentcomponents.com/
- **Messages / Versionen:** breite Abdeckung inkl. **pain.001.001.09**, **pacs.008.001.08**, camt-Familie
- **IGs:** **CBPR+**, SEPA, TARGET2, FedNow; Demo-Projekt auf GitHub (Payment-Components/demo-iso20022)
- **Preis:** Freemium-Online-Tool + kommerzielle Libraries (Java/.NET/REST). Preise auf Website nicht öffentlich gelistet.
- **Nutzung:** Web-UI + REST-API + Library
- **Registrierung:** ja für erweiterte Features
- **Bewertung:** ★★★★☆ — Einer der wenigen kommerziellen Tools mit expliziter CBPR+- und pacs.008-Unterstützung, die auch für Tests öffentlich zugänglich sind.

---

## 3. Kostenlose / Community-Tools

### 3.1 Mobilefish SEPA XML Validator
- **URL:** https://www.mobilefish.com/services/sepa_xml_validation/
- **Messages / Versionen:** pain.001.001.**02**, pain.001.001.**03**, pain.008.001.01/02 — **kein .09**
- **IGs:** reine XSD-Validierung
- **Preis:** kostenlos, keine Registrierung
- **Bewertung:** ★☆☆☆☆ — Für pain.001.001.09 und pacs.008 **ungeeignet**, historische SEPA-Variante.

### 3.2 SEPAViewer (kibervarnost.si)
- **URL:** https://kibervarnost.si/sepaviewer/
- **Messages / Versionen:** pain.001.001.03 (SEPA)
- **IGs:** nur SEPA-Viewer, keine Regelvalidierung
- **Preis:** kostenlos, anonym, lokal im Browser (keine Server-Uploads). Open Source (MIT, GitHub)
- **Datenschutz:** ausgezeichnet (alles client-seitig)
- **Bewertung:** ★★☆☆☆ — Gut für Inspektion, nicht für IG-Validierung.

### 3.3 Open-Source-Libraries (GitHub)
- **Prowide ISO 20022** (Java, Apache 2.0) — https://github.com/prowide/prowide-iso20022 — Parser/Model für alle MX-Messages inkl. pain.001 und pacs.008. Keine eingebauten IG-Regeln, aber perfekte Basis, um eigene Validierung programmatisch gegenzuprüfen.
- **pyiso20022** — https://github.com/phoughton/pyiso20022 — Python-Paket, PAIN/PACS/ADMI/COLR/CAMT/HEAD.
- **prog-nov/iso20022-messages-for-go** — https://github.com/prog-nov/iso20022-messages-for-go — enthält u.a. die XSDs für `pain.001.001.09`, `pacs.008.001.08`, `head.001.001.02` — nützlich als Referenz-Schema-Set.
- **Payment-Components/demo-iso20022** — https://github.com/Payment-Components/demo-iso20022 — Beispiel für die kommerzielle FINaplo-Library.
- **Bewertung (gesamt):** ★★★☆☆ — Keine IG-Regeln out-of-the-box, aber ideal als *unabhängige Parser-/XSD-Meinung* in CI.

---

## 4. Bank-spezifische Portale

### 4.1 Danske Bank File Validation Tool
- **URL:** über Danske Business Online
- **Nutzung:** nur für Danske-Kunden, validiert gegen deren IG
- **Bewertung:** n/a — nur bei Bankbeziehung nutzbar.

### 4.2 SEB Developer Portal (Baltics)
- **URL:** https://developer.baltics.sebgroup.com/tools/non-api-tools
- **Status:** Die Seite ist eine JavaScript-SPA, HTML-Fetch liefert nur CSS — Inhalte **konnten nicht zuverlässig verifiziert werden**. Historisch existiert ein XML-Validator für ISO 20022-Messages, den SEB für baltische Kunden bereitstellt.
- **Bewertung:** n/a für CH/CBPR+-Use Cases.

---

## 5. Empfehlungs-Matrix

| Message × IG | Primärer Validator | Sekundärer Check |
|---|---|---|
| pain.001.001.09 × **SPS 2025** | **SIX Validation Portal** | TreasuryHost PAINP (XSD-Zweitmeinung) + eigenes XSD aus `prog-nov/iso20022-messages-for-go` |
| pain.001.001.09 × **CGI-MP** | XMLdation (falls Zugang) | FINaplo |
| pain.001.001.09 × **SEPA/EPC** | SIX Validation Portal (deckt SEPA via SPS ab) | FINaplo, Mobilefish nur für .03-Altstände |
| pacs.008.001.08 × **CBPR+** | **SWIFT MyStandards Readiness Portal** | FINaplo (CBPR+-Profil), Prowide (Parser-Check) |
| pacs.008.001.08 × **CGI-MP** | XMLdation | FINaplo |
| Struktur-/XSD-Only (alle) | Lokaler lxml-XSD-Check im Projekt | Prowide / pyiso20022 in CI |

---

## 6. Ausschlussliste (für unseren Use Case nicht geeignet)

- **Truugo ISO 20022 Validator** — unterstützt laut eigener Tool-Seite nur **V02/V03** der relevanten Messages; kein pain.001.001.09, kein pacs.008. **Nicht verwenden**.
- **Mobilefish SEPA Validator** — nur pain.001.001.02/.03 und pain.008.001.01/.02. Kein .09, kein pacs.008.
- **SEPAViewer (kibervarnost.si)** — nur pain.001.001.03-Viewer, keine Regelvalidierung.
- **20022Labs Tool-Liste / Sandbox** — kein eigener Validator; Sandbox im Aufbau (Fokus Kanada-RTP).
- **Danske File Validation / SEB Tools** — bankspezifisch, nicht für externe Tests nutzbar.

---

## 7. Quellen

- SIX Validation Portal: https://validation.iso-payments.ch/sps/account/logon
- SIX Group SPS 2025: https://www.six-group.com/en/products-services/banking-services/payment-standardization/standards/iso-20022.html
- SWIFT MyStandards: https://www.swift.com/products/mystandards
- SWIFT CBPR+ Self-Attestation: https://www.swift.com/cbpr-self-attestation
- ECB Dokument zum Readiness Portal: https://www.ecb.europa.eu/paym/pdf/consultations/Readiness_Portal_for_message_testing.pdf
- XMLdation: https://www.xmldation.com/
- Truugo Validator: https://www.truugo.com/iso20022_validator/
- Truugo Pricing: https://www.truugo.com/pricing/
- 20022Labs Tools: https://20022labs.com/message-validation-tools/
- 20022Labs Sandbox: https://20022labs.com/sandbox/
- TreasuryHost PAINP: https://www.treasuryhost.eu/solutions/painp/
- Mobilefish: https://www.mobilefish.com/services/sepa_xml_validation/
- SEPAViewer: https://kibervarnost.si/sepaviewer/
- SEB Developer Portal: https://developer.baltics.sebgroup.com/tools/non-api-tools
- FINaplo (Payment Components): https://finaplo.paymentcomponents.com/
- Prowide ISO 20022 (GitHub): https://github.com/prowide/prowide-iso20022
- pyiso20022 (GitHub): https://github.com/phoughton/pyiso20022
- prog-nov/iso20022-messages-for-go: https://github.com/prog-nov/iso20022-messages-for-go
- Payment-Components/demo-iso20022: https://github.com/Payment-Components/demo-iso20022
- Clearstream CBPR+ pacs.008 Usage Guideline: https://www.clearstream.com/resource/blob/4151636/748b8c7bc59fe132742e3a15955d175d/pacs-008-2-data.pdf
- JPMorgan ISO 20022 CBPR+ Testing Guide (2025): https://www.jpmorgan.com/content/dam/jpmorgan/documents/payments/jpmorgan-iso20022-client-testing-guide.pdf

---

*Recherchedatum: 2026-04-06. Einige Detail-Seiten (SIX-Portal hinter Login, XMLdation-Produktmatrix, SEB Developer Portal JS-SPA, FINaplo SPA) waren per HTTP-Fetch nicht vollständig lesbar; dort basieren die Aussagen auf öffentlicher Produktkommunikation und Suchergebnissen zum Stichtag. Bitte vor Beschaffungsentscheidungen konkrete Angebote und aktuelle Preislisten direkt einholen.*
