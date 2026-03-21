# Feature-Vorschlaege & Roadmap: iso20022tester

**Erstellt:** 2026-03-20
**Basis:** Analyse des bestehenden Repos + Recherche aehnlicher Open-Source-Projekte

---

## Bestandsaufnahme: Was kann das Repo bereits?

| Bereich | Status |
|---------|--------|
| Excel-basierte Testfalldefinition | Implementiert |
| pain.001.001.09 XML-Generierung (SPS 2025) | Implementiert |
| 4 Zahlungstypen: SEPA, Domestic-QR, Domestic-IBAN, CBPR+ | Implementiert |
| XSD-Validierung (lokal, pain.001.001.09.ch.03) | Implementiert |
| Business-Rule-Engine mit 30+ Regeln | Implementiert |
| Negative Testing via ViolateRule | Implementiert (11 Violations) |
| Multi-Payment (mehrere PmtInf pro Dokument) | Implementiert |
| IBAN-Generierung (Mod-97), QRR (Mod-10), SCOR (ISO 11649) | Implementiert |
| Reporting: Word (.docx), JSON, JUnit-XML | Implementiert |
| Seed-basierte Reproduzierbarkeit | Implementiert |
| Bankarbeitstag-Berechnung (TARGET2 / CH) | Implementiert |
| SPS-Zeichensatz-Validierung | Implementiert |
| Deterministisches Key->XPath Mapping | Implementiert |
| Caching-Infrastruktur (vorbereitet fuer KI-Mapping) | Infrastruktur vorhanden |
| API-Integration (Phase 2) | Geplant, nicht implementiert |

---

## Feature-Vorschlaege

### Prioritaet 1: Hoher Nutzen, nahe am bestehenden Code

#### F-01: API-Integration (Phase 2 laut Anforderungen)
**Quelle:** Eigene Anforderungen (FR-100 bis FR-105)
**Inspiration:** moov-io/iso20022 (HTTP API), Mbanq/iso20022 (Web-UI), iso20022.js (Developer-API)
**Beschreibung:**
- Versand generierter XML-Dateien an konfigurierbare Banking-API
- Authentifizierung: OAuth, mTLS, API-Key (konfigurierbar)
- pain.002 Response-Parsing und Vergleich mit erwarteter API-Antwort
- Erweiterung des Reporting um API-Ergebnisse
**Aufwand:** Hoch
**Nutzen:** Kernziel des Projekts — Schliesst den Test-Loop: Generierung -> Versand -> Validierung der Antwort
**Empfehlung:** Hoechste Prioritaet. Ohne API-Anbindung bleibt das Tool ein reiner Generator.

---

#### F-02: pain.002 Response-Parser
**Quelle:** FR-102, FR-103
**Inspiration:** pyiso20022 (Multi-Message-Type-Support), prowide-iso20022 (umfassendes Parsing)
**Beschreibung:**
- Parser fuer pain.002 (CustomerPaymentStatusReport)
- Extraktion von Status-Codes (ACCP, RJCT, etc.) und Reason-Codes
- Automatischer Abgleich: tatsaechlicher vs. erwarteter Status
- Auch als eigenstaendiges Validierungstool nutzbar
**Aufwand:** Mittel
**Nutzen:** Voraussetzung fuer sinnvolle API-Integration. Ohne pain.002-Verstaendnis kann die API-Antwort nicht interpretiert werden.
**Empfehlung:** Direkt mit F-01 zusammen umsetzen.

---

#### F-03: Erweiterung der Business-Rule-Abdeckung
**Quelle:** Eigener Rule-Katalog hat 30+ Regeln, SPS 2025 Spezifikation enthaelt deutlich mehr
**Inspiration:** boessu/SwissQRBill (detaillierte Validierung), Payment-Components/demo-iso20022
**Beschreibung:**
- Implementierung weiterer SPS-2025-Business-Rules aus den Spec-Dokumenten
- Insbesondere: Adressvalidierung (strukturiert vs. kombiniert), Laengenrestriktionen pro Feld, Currency-Land-Konsistenz
- Erweiterung der Violation-Funktionen fuer Negative Testing
- Ziel: Jede im SPS-Dokument definierte Regel hat ein Code-Gegenstueck
**Aufwand:** Mittel (inkrementell erweiterbar)
**Nutzen:** Hoehere Testabdeckung = hoehere Konfidenz in generierte XMLs
**Empfehlung:** Laufend erweitern, nicht als Big-Bang.

---

#### F-04: CSV-Input als alternatives Eingabeformat
**Quelle:** sebastienrousseau/pain001 (CSV + SQLite Support)
**Beschreibung:**
- CSV-Parser neben dem bestehenden Excel-Parser
- Gleiche Spaltenstruktur wie Excel, aber ohne openpyxl-Abhaengigkeit
- Nuetzlich fuer CI/CD-Pipelines und automatisierte Testlaeufe
- Einfacheres Versionieren von Testfaellen in Git (CSV ist Plaintext)
**Aufwand:** Gering (Excel-Parser-Logik ist abstrahierbar)
**Nutzen:** Deutlich bessere CI/CD-Integration. CSVs lassen sich diffbar versionieren.
**Empfehlung:** Quick Win mit hohem Nutzen fuer automatisierte Workflows.

---

### Prioritaet 2: Sinnvolle Ergaenzungen, mittelfristig

#### F-05: HTML-Report mit interaktiver Darstellung
**Quelle:** Eigene Idee, inspiriert durch die Vielfalt der Reporting-Formate
**Beschreibung:**
- HTML-Report als Ergaenzung zu Word/JSON/JUnit
- Interaktiv: Klappbare Testfall-Details, Syntax-Highlighting fuer XML
- Farbcodierung: Gruen (Pass), Rot (Fail), Gelb (Warnung)
- Eingebettetes XML-Preview mit Diff-Ansicht bei Violations
- Standalone-HTML (keine Abhaengigkeiten, einfach im Browser oeffnen)
**Aufwand:** Mittel
**Nutzen:** Bester Ueberblick fuer manuelle Reviews. Word ist umstaendlich, JSON ist nicht visuell.
**Empfehlung:** Gut fuer Stakeholder-Kommunikation und Testabnahmen.

---

#### F-06: Docker-Container und CI/CD-Pipeline
**Quelle:** NF-05 (Containerisierung als Option), OP-03 (offener Punkt)
**Inspiration:** moov-io/iso20022 (Docker + CI), aws-samples (Enterprise-ready)
**Beschreibung:**
- Dockerfile fuer reproduzierbare Ausfuehrung
- GitHub Actions Workflow: Lint, Test, Build, Report-Generierung
- Optional: Docker Compose fuer Setup mit API-Mock (Phase 2)
**Aufwand:** Gering bis Mittel
**Nutzen:** Professionalisierung, reproduzierbare Builds, CI/CD-faehig.
**Empfehlung:** Sinnvoll sobald das Tool produktiv eingesetzt wird.

---

#### F-07: KI-gestuetztes Mapping (Phase 2, Caching-Infra bereits vorhanden)
**Quelle:** SDD v2.1 §2.1 (KI-Mapping bewusst verschoben), Cache-Modul bereits angelegt
**Inspiration:** aws-samples/iso20022-message-generator (ML-Prototypen)
**Beschreibung:**
- Freitext-Keys aus "Weitere Testdaten" per LLM auf XPath mappen
- Semantic Caching (SQLite/JSON) ist bereits vorbereitet
- Fallback auf deterministisches Mapping bei unbekannten Keys
- Nutzung z.B. via Claude API oder lokales Modell
**Aufwand:** Mittel bis Hoch
**Nutzen:** Flexibleres, benutzerfreundlicheres Mapping ohne starre Key-Definitionen.
**Empfehlung:** Erst sinnvoll wenn viele verschiedene User mit unterschiedlichen Namenskonventionen arbeiten.

---

#### F-08: Multi-Version-Support (pain.001.001.03 bis .11)
**Quelle:** sebastienrousseau/pain001 (unterstuetzt alle 9 Versionen)
**Beschreibung:**
- Unterstuetzung mehrerer pain.001-Versionen neben .09
- Insbesondere pain.001.001.03 (weit verbreitet, aeltere Systeme)
- XSD-Schema pro Version, konfigurierbar
- Version als Parameter im Excel oder config.yaml
**Aufwand:** Hoch (XML-Struktur-Unterschiede pro Version)
**Nutzen:** Breitere Einsetzbarkeit, Kompatibilitaetstests mit aelteren Systemen.
**Empfehlung:** Nur bei konkretem Bedarf. SPS 2025 verlangt .09 — aeltere Versionen sind Nische.

---

#### F-09: Round-Trip-Validierung (XML -> Parse -> Vergleich)
**Quelle:** pyiso20022 (Parser-Funktionalitaet), prowide-iso20022 (Parse + Serialize)
**Beschreibung:**
- Generierte XML-Dateien zurueck einlesen und gegen das Datenmodell parsen
- Vergleich: Input-Daten vs. geparstes Ergebnis (Roundtrip-Check)
- Erkennt Serialisierungs-Bugs (z.B. Namespace-Probleme, fehlende Felder)
**Aufwand:** Mittel
**Nutzen:** Zusaetzliche Qualitaetssicherung des XML-Generators selbst.
**Empfehlung:** Guter Selbsttest, besonders bei Erweiterungen am Generator.

---

### Prioritaet 3: Nice-to-Have, langfristig

#### F-10: Web-UI fuer Testfall-Management
**Quelle:** Mbanq/iso20022 (Web-UI fuer Message-Generierung)
**Beschreibung:**
- Browser-basierte Oberflaeche statt Excel + CLI
- Formularbasierte Testfall-Erstellung mit Validierung
- Live-Vorschau der generierten XML
- Dashboard mit Testlauf-Historie und Trendanalyse
**Aufwand:** Sehr Hoch
**Nutzen:** Deutlich niedrigere Einstiegshuerde fuer nicht-technische Tester.
**Empfehlung:** Erst nach stabiler Phase-2-API. Uebergang von Tool zu Produkt.

---

#### F-11: QR-Bill-Generierung (PDF/SVG)
**Quelle:** claudep/swiss-qr-bill (~111 Stars), manuelbl/SwissQRBill (~176 Stars), schoero/SwissQRBill (~148 Stars)
**Beschreibung:**
- Aus Domestic-QR-Testfaellen automatisch Swiss QR-Bills als PDF/SVG erzeugen
- Nutzung der bereits vorhandenen QR-IBAN/QRR-Logik
- Integration via claudep/swiss-qr-bill (Python, MIT-Lizenz)
**Aufwand:** Gering (Library-Integration)
**Nutzen:** Visueller Output fuer QR-Zahlungstests. Nettes Add-on, aber nicht Kernfunktion.
**Empfehlung:** Quick Win fuer Demos, nicht kritisch fuer Kernfunktionalitaet.

---

#### F-12: Fuzzing / Property-Based Testing
**Quelle:** moov-io/iso20022 (Fuzzing fuer Produktionsreife)
**Beschreibung:**
- Automatische Generierung zufaelliger Testfaelle (ueber Seed hinaus)
- Hypothesis-basiertes Property-Testing fuer IBAN, QRR, SCOR
- Fuzz-Testing der XML-Generierung mit zufaelligen Overrides
- Ziel: Edge Cases finden, die manuelle Testfaelle nicht abdecken
**Aufwand:** Mittel
**Nutzen:** Findet Corner Cases, die kein manueller Tester findet.
**Empfehlung:** Gute Investition fuer langfristige Code-Qualitaet.

---

#### F-13: Individuelle C-Level-Overrides pro Transaktion
**Quelle:** Eigene Anforderungen (OP-02, teilweise offen)
**Beschreibung:**
- Bei TxCount>1: Unterschiedliche Creditor-Daten pro Transaktion
- Excel-Syntax z.B.: `Tx[1].Cdtr.Nm=Mueller; Tx[2].Cdtr.Nm=Schmid`
- Oder: Separate Zeilen im Excel pro Transaktion innerhalb einer Gruppe
**Aufwand:** Mittel (Excel-Parser + Mapping muss erweitert werden)
**Nutzen:** Realistischere Multi-Transaktions-Testfaelle.
**Empfehlung:** Sinnvoll wenn Multi-Payment-Tests haeufiger werden.

---

#### F-14: Testfall-Bibliothek / Vorlagen-Katalog
**Quelle:** Eigene Idee, inspiriert durch issettled/iso20022-issettled (Sample Messages)
**Beschreibung:**
- Vorgefertigte Testfall-Sets fuer gaengige Szenarien
- Z.B.: "SEPA Standard-Suite", "QR-Zahlung Komplett", "Negative Tests Alle Rules"
- Als Excel- oder CSV-Vorlagen im Repo
- Dokumentation: Was deckt jede Suite ab?
**Aufwand:** Gering (kein Code, nur Testdaten + Doku)
**Nutzen:** Schnellerer Einstieg fuer neue User, standardisierte Testabdeckung.
**Empfehlung:** Einfach und wertvoll. Kann sofort gestartet werden.

---

#### F-15: pain.008 Support (Direct Debit)
**Quelle:** viafintech/sps_king (pain.008 Support), python-sepaxml (Direct Debit)
**Beschreibung:**
- Erweiterung auf pain.008 (Lastschriften / Direct Debit)
- Neue Payment-Type-Handler, eigenes XSD
- Eigene Business Rules fuer Direct Debit
**Aufwand:** Hoch (neuer Message-Typ = neuer XML-Builder + Validierung)
**Nutzen:** Breitere Abdeckung des Schweizer Zahlungsverkehrs.
**Empfehlung:** Nur bei explizitem Bedarf. Scope-Erweiterung vom Kernziel.

---

## Priorisierte Uebersicht

| Prio | Feature | Aufwand | Nutzen | Empfehlung |
|------|---------|---------|--------|------------|
| 1 | F-01: API-Integration | Hoch | Sehr hoch | Naechster Meilenstein |
| 1 | F-02: pain.002 Parser | Mittel | Hoch | Zusammen mit F-01 |
| 1 | F-03: Mehr Business Rules | Mittel | Hoch | Laufend erweitern |
| 1 | F-04: CSV-Input | Gering | Hoch | Quick Win |
| 2 | F-05: HTML-Report | Mittel | Mittel | Fuer Stakeholder |
| 2 | F-06: Docker + CI/CD | Gering-Mittel | Mittel | Bei Produktiveinsatz |
| 2 | F-07: KI-Mapping | Mittel-Hoch | Mittel | Bei vielen Usern |
| 2 | F-08: Multi-Version-Support | Hoch | Gering-Mittel | Nur bei Bedarf |
| 2 | F-09: Round-Trip-Validierung | Mittel | Mittel | Selbsttest-Qualitaet |
| 3 | F-10: Web-UI | Sehr hoch | Hoch | Langfristig |
| 3 | F-11: QR-Bill PDF/SVG | Gering | Gering | Demo-Zwecke |
| 3 | F-12: Fuzzing | Mittel | Mittel | Langfristige Qualitaet |
| 3 | F-13: Individuelle C-Level-Overrides | Mittel | Mittel | Bei Multi-Payment-Bedarf |
| 3 | F-14: Testfall-Bibliothek | Gering | Mittel | Sofort startbar |
| 3 | F-15: pain.008 Direct Debit | Hoch | Gering | Nur bei Bedarf |

---

## Empfohlene Reihenfolge der Umsetzung

**Sofort / Quick Wins:**
1. F-04: CSV-Input (gering, hoher CI/CD-Nutzen)
2. F-14: Testfall-Bibliothek (kein Code noetig, verbessert Onboarding)

**Kurzfristig (Phase 2):**
3. F-01 + F-02: API-Integration + pain.002 Parser (Kernziel des Projekts)
4. F-03: Business Rules erweitern (laufend, parallel zu allem)

**Mittelfristig:**
5. F-06: Docker + CI/CD
6. F-05: HTML-Report
7. F-09: Round-Trip-Validierung

**Langfristig / Nach Bedarf:**
8. F-07, F-10, F-12, F-13, F-08, F-11, F-15
