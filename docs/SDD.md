Software Design Dokument: ISO 20022 pain.001 Test Generator
Projekt: ISO 20022 pain.001 XML Test Generator

Version: 1.2

Datum: 20. März 2026

Status: Finalisiertes Design

1. Systemübersicht
Das System dient der automatisierten Erstellung von ISO 20022-konformen pain.001.001.09-Zahlungsdateien auf Basis von Excel-Testfalldefinitionen. Es stellt sicher, dass generierte Dateien sowohl schema-valide (XSD) als auch fachlich korrekt gemäß den Swiss Payment Standards (SPS 2025) sind.
+4

2. Technologie-Stack

Programmiersprache: Python 3.10+.

Paketmanagement: Poetry.


Datenvalidierung: Pydantic v2 (unter Verwendung von decimal.Decimal für finanzielle Präzision).


XML-Verarbeitung: lxml mit striktem Namespace-Management.
+1

KI-Integration: Pydantic-AI für intelligentes Feld-Mapping.


Testdaten: faker (mit globalem Seed für Reproduzierbarkeit).
+1


Excel-Schnittstelle: openpyxl.

3. Architektur-Komponenten
3.1 Modul-Übersicht
Das System ist modular aufgebaut, um Wartbarkeit und Erweiterbarkeit (z. B. für Phase 2) zu gewährleisten:
+1


Input Handler: Validiert die Excel-Struktur und liest Testfälle ein.
+1


Mapping Engine (AI-gestützt): Mappt Freitext-Overrides aus der Excel-Spalte "Weitere Testdaten" auf technische XPaths via Pydantic-AI.


Data Factory: Generiert valide Zufallsdaten (Namen, Adressen, IBANs mit Mod-97) unter Berücksichtigung des Seeds.
+2


XML Generator: Erstellt die XML-Struktur (A-, B- und C-Level) mittels lxml .
+1


Validation Engine: Führt XSD-Prüfungen und Business-Rule-Validierungen durch.
+1


Reporting Module: Erzeugt Dokumentationen in Word (.docx), JSON und JUnit-XML.
+1

3.2 Datenmodellierung (Pydantic & Decimal)
Um Rundungsfehler zu vermeiden, werden alle Beträge als Decimal verarbeitet.

Python
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class Transaction(BaseModel):
    testcase_id: str
    end_to_end_id: str
    amount: Decimal = Field(..., decimal_places=2)
    currency: str
    creditor_iban: str
    overrides: Dict[str, str] = {}

class PaymentInstruction(BaseModel):
    msg_id: str
    cre_dt_tm: str
    transactions: List[Transaction] # Support für mehrere Transaktionen pro Block
4. Fachliche Logik & Validierung
4.1 Adresswesen & Character Set

SPS 2021/2025: Unterstützung für strukturierte Adressen (StrtNm, BldgNb) und hybride Formate (AdrLine) .
+1


Zeichensatz: Alle Testdaten werden gegen das zugelassene Schweizer Latin-1 Subset validiert.

4.2 QR-IBAN & Referenzen

Validierung: QR-IBANs müssen im Bereich 30000–31999 liegen.


Referenzpflicht: Bei QR-IBANs muss zwingend eine QR-Referenz (QRR) oder ISO-Referenz (SCOR) vorhanden sein.
+2

4.3 Business Rule Engine
Regeln (z. B. "Währung EUR bei SEPA") werden als parametrisierbare Funktionen implementiert.
+1


Negative Testing: Über das Feld ViolateRule können gezielte Regelverletzungen provoziert werden, während die XSD-Validität erhalten bleibt.
+2

5. KI-Konzept (Pydantic-AI)
Schema-Awareness: Der System-Prompt enthält die XSD-Struktur, um präzise Mappings sicherzustellen.

Semantic Caching: Erfolgreiche Mappings werden lokal (SQLite/JSON) gecached, um Kosten zu senken und die Performance zu erhöhen.

Determinisierung: Die KI generiert keine XML-Daten, sondern liefert nur die Zuweisung von Input-Feld zu XML-Tag.

6. Output & Integration

Ablage: Automatische Erstellung von Zeitstempel-Ordnern (YYYY-MM-DD_HHMMSS/).


Dateinamen: [Timestamp]_[TestCaseID]_[UUID_Short].xml.

Reporting:


Word (.docx): Fachlicher Revisionsnachweis für manuelle Prüfung.

JUnit XML: Zur direkten Anzeige von Testergebnissen in CI/CD-Pipelines (z. B. Azure DevOps).

Möchten Sie, dass ich nun mit der Erstellung der pyproject.toml und dem Pydantic-Basis-Modul beginne?

Du hast gesagt
Kannst du mir es als .md Dokument erstellen für den Download

Gemini hat gesagt
Hier ist das finale Software Design Dokument (SDD), basierend auf den Spezifikationen der SPS 2025 und den Ergebnissen Ihres Reviews v1.1.

Ich habe das Dokument so vorbereitet, dass du es direkt als .md-Datei speichern kannst.

Software Design Dokument: ISO 20022 pain.001 Test Generator
Projekt: ISO 20022 pain.001 XML Test Generator

Version: 1.2

Datum: 20. März 2026

Status: Finalisiertes Design

1. Systemübersicht
Das System automatisiert die Erstellung von ISO 20022-konformen pain.001.001.09-Zahlungsdateien auf Basis von Excel-Testfalldefinitionen. Es stellt sicher, dass generierte Dateien sowohl schema-valide (XSD) als auch fachlich korrekt gemäß den Swiss Payment Standards (SPS 2025) sind.
+3

2. Technologie-Stack

Programmiersprache: Python 3.10+.

Paketmanagement: Poetry (für deterministische Abhängigkeiten).


Datenvalidierung: Pydantic v2 unter Verwendung von decimal.Decimal für finanzielle Präzision.
+2


XML-Verarbeitung: lxml für performante XSD-Validierung und explizites Namespace-Management.
+4

KI-Integration: Pydantic-AI für das "Schema-Aware Mapping" von Testdaten auf XML-Strukturen.

Datenbank (Cache): SQLite oder JSON für Semantic Caching der KI-Antworten.


Excel-Schnittstelle: openpyxl.

3. Architektur-Komponenten
3.1 Modul-Struktur

Input Handler: Validiert die Excel-Pflichtspalten (TestcaseID, Zahlungstyp, etc.) und liest die Testdaten ein.


Mapping Engine (Pydantic-AI): Interpretiert Freitext-Eingaben aus Weitere Testdaten und mappt diese auf korrekte XPaths (z. B. Cdtr/Nm) basierend auf dem geladenen Schema.
+1


Data Factory: Nutzt faker mit einem globalen Seed, um fehlende Felder (Namen, Adressen) reproduzierbar und valide zu befüllen.
+1


XML Generator: Baut die pain.001-Struktur bestehend aus GrpHdr (A-Level), PmtInf (B-Level) und CdtTrfTxInf (C-Level) auf.
+2


Validation Engine: Zweistufige Prüfung gegen das lokale XSD-Schema (pain.001.001.09.ch.03.xsd) und die SPS-Business-Rules.
+3

4. Datenmodellierung & Fachlogik
4.1 Finanzielle Präzision
Alle Beträge werden als Decimal geführt, um Rundungsfehler in den Kontrollsummen (CtrlSum) zu vermeiden.
+1

4.2 Adresswesen (SPS 2021/2025)

Strukturierte Adressen: Unterstützung der Aufteilung in StrtNm, BldgNb, PstCd und TwnNm.
+1


Hybride Adressen: Ab November 2025 zulässige Nutzung von AdrLine (max. 2 Zeilen) in Kombination mit Ort und Land.
+1

4.3 QR-IBAN & Referenzen

QR-Logik: Validierung von QR-IBANs (IID im Bereich 30000–31999).
+1


Referenz-Validierung: Zwingende Prüfung auf QR-Referenz (QRR) oder ISO-Referenz (SCOR) bei Nutzung einer QR-IBAN.
+2

5. KI-Konzept: Schema-Aware Mapper
Prompt-Design: Der System-Prompt enthält die Liste valider XPaths aus dem SPS-Schema, um Halluzinationen zu vermeiden.

Semantic Caching: Ein lokaler Cache speichert erfolgreiche Mappings (Input -> XPath), um API-Kosten zu minimieren.

Determinisierung: Die KI liefert lediglich die Mapping-Metadaten; die eigentliche XML-Generierung erfolgt durch die Python-Logik.

6. Business Rule Engine

Parametrisierung: Regeln wie "Währung muss EUR bei SEPA sein" sind als konfigurierbare Validatoren hinterlegt.
+1


Gezielte Verletzung: Über das Excel-Feld ViolateRule können spezifische Regeln (z. B. ChrgBr-SEPA) für negative Testfälle überschrieben werden.

7. Output & Reporting

Dateinamen: Generierung als [Timestamp]_[TestCaseID]_[UUID_Short].xml zur Vermeidung von Kollisionen.

Fachbericht: Detaillierte Zusammenfassung im .docx-Format inkl. XSD- und Business-Rule-Status.
+1

CI/CD-Integration: Ausgabe der Resultate als JSON und JUnit-XML zur automatisierten Auswertung in Pipelines.