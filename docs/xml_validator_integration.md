# XML Validator integration Guide

**Provider:** [the XML Validator service provider external XML Validator service Financial Messaging APIs](<XML_VALIDATOR_BASE_URL>)
**Swagger (lokal gitignored):** `xml_validator/api-spec.json`
**Status in diesem Repo:** Aktiv fuer pacs.008 CBPR+; pain.001 und andere Flavors vorbereitet.

## Zweck

external XML Validator service wird als **externer Second-Opinion-Validator** fuer die pacs.008 Pipeline genutzt. Waehrend XSD und interne Business Rules die strukturellen und SPS/CBPR+-spezifischen Regeln abdecken, bringt external XML Validator service den SWIFT-Usage-Guideline-Check (und in vielen Faellen auch Business-Rule-Feedback) aus einer unabhaengigen Quelle.

Konkret fand der WP-12 Auto-Repair-Loop damit einen realen Bug, den die internen Validierungen nicht erkannt hatten (JPY-Decimal-Issue, siehe `docs/roadmap/2026-04-06_pacs008_external_validator_audit_log.md`).

## Account-Setup

1. Konto auf [<XML_VALIDATOR_PROVIDER_PORTAL>](<XML_VALIDATOR_PROVIDER_PORTAL>) anlegen. Es gibt einen kostenlosen 7-Tage-Trial mit limitierter Request-Anzahl (erfahrungsgemaess ~20 Calls total); fuer Produktiveinsatz ist ein bezahltes Abonnement noetig.
2. Im external XML Validator service-Dashboard den API-Key generieren.
3. Den Key im Repo ablegen (gitignored):
   ```
   xml_validator/api-key-<date>.txt    # Bearer-Token, eine Zeile
   xml_validator/base-url-<date>.txt   # z.B. <XML_VALIDATOR_BASE_URL>
   ```
4. Alternativ: Environment-Variablen `XML_VALIDATOR_API_KEY` und `XML_VALIDATOR_BASE_URL` (haben Vorrang vor den Dateien).

Der Ordner `xml_validator/` ist via `.gitignore` ausgeschlossen, damit Credentials nie versehentlich commited werden.

## Base-URLs

Swagger listet beide Environments:

| Environment | Base URL |
|---|---|
| LIVE | `<XML_VALIDATOR_BASE_URL>` |
| SANDBOX | `<XML_VALIDATOR_BASE_URL>/sandbox` |

Waehrend des Trial-Zeitraums nutzen beide dieselbe Quota.

## Endpoint-Dispatch pro Flavor

`src/xml_validator_service/client.py::endpoint_for_flavor(flavor, sepa_scheme="sct")` mappt:

| Pacs008Flavor | Endpoint | Status |
|---|---|---|
| `CBPR+` | `POST /cbpr/validate` | ✅ aktiv |
| `TARGET2` | `POST /target2/validate` | vorbereitet |
| `SEPA` | `POST /sepa/{scheme}/validate` | vorbereitet |
| `SIC` | — | NotImplementedError |

## Request-Format

```http
POST /cbpr/validate HTTP/1.1
Host: <configured base URL>
Authorization: Bearer <api-key>
Content-Type: text/plain
Accept: */*

<?xml version="1.0" encoding="UTF-8"?>
<BusinessMessage>
  <AppHdr xmlns="urn:iso:std:iso:20022:tech:xsd:head.001.001.02">...</AppHdr>
  <Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">...</Document>
</BusinessMessage>
```

Body ist plain-text mit dem kompletten BusinessMessage-Envelope (BAH + Document), genauso wie es unsere Pipeline ohnehin produziert.

## Response-Formate

| Status | Bedeutung | Handling |
|---|---|---|
| 200 | Message valid | `ExternalValidationResult(valid=True, errors=[])` |
| 400 | Validation-Fehler (typischerweise JSON-Array oder JSON-Object mit `errors`/`messages`/`violations`) | `ExternalValidationResult(valid=False, errors=[...])` |
| 401 | Unauthorized (Key falsch / abgelaufen) | `XmlValidatorAuthError` raised |
| 412 | `subscription.expired` (Trial-Quota aufgebraucht) | `XmlValidatorQuotaExceeded` raised → Pipeline skipt alle verbleibenden Calls |
| 500-599 | Server-Fehler | `XmlValidatorServerError` raised |
| Netzwerk | Connection/Timeout | `XmlValidatorError` raised |

### Beispiel 400-Response

```json
[
  {
    "severity": "FATAL",
    "errorCode": "D00007",
    "fieldPath": "/cdtTrfTxInf[0]/instdAmt",
    "description": "Invalid currency code or too many decimal digits.",
    "erroneousValue": {"value": 500000.0, "ccy": "JPY"},
    "line": 0,
    "column": 0
  }
]
```

Der Parser (`_parse_error_body`) versucht zuerst JSON zu parsen und extrahiert dann bekannte Key-Namen (`errors`, `messages`, `violations`, `detail`, `message`); Plain-Text-Responses werden zeilenweise in die Error-Liste uebersetzt.

## Pipeline-Integration

`Pacs008TestPipeline(config, use_external_validator=True)` aktiviert den external XML Validator service-Aufruf pro Testcase. Triggering via CLI:

```bash
poetry run python -m src.main \
    --input templates/testfaelle_pacs008_comprehensive.xlsx \
    --config config.yaml \
    --external-validate
```

Logik (pro Testcase):

1. **Skip fuer negative Testcases**: wenn `expected_result=NOK` und `violate_rule` gesetzt, wird external XML Validator service nicht aufgerufen (Quota-Sparmassnahme)
2. **Skip wenn Quota exhausted**: nach der ersten `XmlValidatorQuotaExceeded` setzt die Pipeline ein Flag und skippt alle verbleibenden Calls
3. **Normaler Call**: `client.validate(xml_bytes, flavor=tc.flavor)` → `ExternalValidationResult`
4. **Error-Handling**: Netzwerk/Auth/Server → `external_valid=False`, `external_errors=[...]`; Quota exhausted → `external_valid=None` (neutral, nicht Fail)

Das Ergebnis landet im JSON-Report pro Testcase:

```json
{
  "testcase_id": "TC-PCS-001",
  "external_valide": true,
  "external_fehler": []
}
```

Und als Run-Level-Counter:

```json
{
  "testlauf": {
    "external_validation_enabled": true,
    "external_validation_checked": 18,
    "external_valid": 17
  }
}
```

## Overall-Pass-Logik mit external XML Validator service

```
overall_ok = xsd_valid AND all_br_pass AND xml_validator_ok
xml_validator_ok = (external_valid is None OR external_valid is True)

wenn expected_result == NOK:
    overall_pass = not overall_ok
sonst:
    overall_pass = overall_ok
```

Das heisst: ein external XML Validator service-`valid=None` (skip/quota) zaehlt als neutral und blockiert keinen Pass. Nur ein echter `valid=False` markiert den Testcase als Fail.

## Trial-Quota

Der kostenlose Trial hat eine **harte Total-Quota** (erfahrungsgemaess ~20 Calls, nicht per-Tag oder per-Stunde resettend). Bei Erreichen der Quota liefert die API `HTTP 412` mit Body `subscription.expired`.

**Quota-Schonende Massnahmen in der Pipeline:**

- Negative Testcases werden uebersprungen (spart ~20 Calls bei `testfaelle_pacs008_comprehensive.xlsx`)
- Nach dem ersten `subscription.expired` laeuft die Pipeline weiter mit `external_valid=None` und macht keine weiteren Calls

**Wenn du eine groessere Test-Runde planst:** upgrade auf ein Paid-Tier oder verteile die Runs auf mehrere Trial-Accounts.

## Troubleshooting

| Symptom | Ursache | Loesung |
|---|---|---|
| `XmlValidatorConfigError: API-Key nicht gefunden` | Weder ENV noch Datei gesetzt | `xml_validator/api-key-*.txt` anlegen oder `XML_VALIDATOR_API_KEY` setzen |
| `XmlValidatorAuthError: 401 Unauthorized` | Key falsch/abgelaufen | Neuen Key im external XML Validator service-Dashboard generieren |
| `XmlValidatorQuotaExceeded: subscription.expired` | Trial-Quota leer | Auf Paid-Tier upgraden oder neues Konto |
| Alle Testcases `external_valide=None` im Report | `use_external_validator` nicht aktiviert oder Quota gleich beim ersten Call leer | `--external-validate` Flag setzen + Key pruefen |
| `Pipeline-Exception: ...` | anderer Fehler (Netzwerk/Encoding) | Stacktrace im Report-Feld `external_fehler` pruefen |

## Unit-Tests

- `tests/test_xml_validator_client.py`: 20 Tests fuer den Client (Auth, Error-Parsing, per-Flavor Dispatch, Quota-Handling)
- `tests/test_pacs008_pipeline.py::Testexternal XML Validator serviceIntegration`: 6 Integration-Tests fuer die Pipeline (mocked 200/400/401, Counter, Auto-Disable bei fehlenden Credentials)

Alle Client- und Integration-Tests nutzen `responses` fuer HTTP-Mocks; es sind keine echten Netzwerk-Calls in der CI.
