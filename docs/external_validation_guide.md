# Anleitung: Externe Validierung der generierten XML-Dateien

## Warum externe Validierung?

Unser Tool validiert jede generierte XML-Datei bereits intern (XSD + Business Rules). Eine **unabhängige Gegenprüfung** durch externe Services stellt sicher, dass unsere Implementierung korrekt ist und die Dateien auch von Banken akzeptiert werden.

---

## Option 1: SIX Validation Portal (⭐ Empfohlen)

Das offizielle Portal der Schweizer Finanzbranche. Kostenlos, unterstützt pain.001.001.09 / SPS 2025.

### Schritt-für-Schritt

1. **Registrieren** auf [validation.iso-payments.ch/SPS](https://validation.iso-payments.ch/sps/account/logon)
   - Geschäftliche E-Mail erforderlich (keine Gmail/GMX/Bluewin)
   - Registrierung → Bestätigungs-E-Mail → Login

2. **XML-Datei hochladen**
   - Login → "Neue Validierung"
   - Datei auswählen (z.B. `20260320_TC-SEPA-001_abc123.xml`)
   - Nachrichtentyp: `pain.001.001.09` (CH)
   - "Validieren" klicken

3. **Ergebnis prüfen**
   - Grün = Konform
   - Rot = Fehler mit genauer Beschreibung und Position
   - Report als HTML/Text herunterladen

### Empfohlene Teststrategie

Mindestens **1 Datei pro Zahlungstyp** validieren:

| Testfall | Zahlungstyp | Erwartetes Ergebnis |
|----------|------------|-------------------|
| TC-SEPA-001 | SEPA | Valide |
| TC-QR-001 | Domestic-QR | Valide |
| TC-IBAN-001 | Domestic-IBAN | Valide |
| TC-CBPR-001 | CBPR+ | Valide |
| TC-SEPA-002 | SEPA (NOK) | Valide (XSD-konform, Business-Rule-Verletzung intern) |

> **Hinweis:** Auch NOK-Testfälle müssen XSD-valide sein — die Regelverletzung betrifft nur Business Rules, nicht das Schema.

---

## Option 2: TreasuryHost (Schnell-Check)

Kostenlos, keine Registrierung, aber nur Web-Upload (keine API).

1. Öffne [treasuryhost.eu/solutions/painp](https://www.treasuryhost.eu/solutions/painp/)
2. XML-Datei hochladen
3. Ergebnis: Schema-Validierung + tabellarische Anzeige der Zahlungen

**Einschränkung:** Unterstützt pain.001.001.03 und .09, aber validiert nur gegen das generische ISO-Schema, nicht gegen SPS-spezifische Regeln.

---

## Option 3: Lokale Second-Opinion-Validierung

Für automatisierte Gegenprüfung im Entwicklungsprozess steht ein Script bereit:

```bash
poetry run python scripts/validate_external.py output/2026-03-21_*/
```

Dieses Script validiert alle XML-Dateien in einem Output-Verzeichnis mit der `xmlschema`-Library (unabhängig von unserer lxml-basierten Validierung) und erzeugt einen Report.

Details: siehe `scripts/validate_external.py`.
