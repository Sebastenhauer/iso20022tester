# FINaplo Integration Guide

**Provider:** [Payment Components FINaplo Financial Messaging APIs](https://finaplo-apis.paymentcomponents.com)
**Swagger (lokal gitignored):** `finaplo/financial-messaging-apis-swagger.json`
**Status in diesem Repo:** Aktiv fuer pacs.008 CBPR+; pain.001 und andere Flavors vorbereitet.

## Zweck

FINaplo wird als **externer Second-Opinion-Validator** fuer die pacs.008 Pipeline genutzt. Waehrend XSD und interne Business Rules die strukturellen und SPS/CBPR+-spezifischen Regeln abdecken, bringt FINaplo den SWIFT-Usage-Guideline-Check (und in vielen Faellen auch Business-Rule-Feedback) aus einer unabhaengigen Quelle.

Konkret fand der WP-12 Auto-Repair-Loop damit einen realen Bug, den die internen Validierungen nicht erkannt hatten (JPY-Decimal-Issue, siehe `docs/roadmap/2026-04-06_pacs008_finaplo_auto_repair_log.md`).

## Account-Setup

1. Konto auf [https://finaplo.paymentcomponents.com](https://finaplo.paymentcomponents.com) anlegen. Es gibt einen kostenlosen 7-Tage-Trial mit limitierter Request-Anzahl (erfahrungsgemaess ~20 Calls total); fuer Produktiveinsatz ist ein bezahltes Abonnement noetig.
2. Im FINaplo-Dashboard den API-Key generieren.
3. Den Key im Repo ablegen (gitignored):
   ```
   finaplo/api-key-<datum>.txt    # Bearer-Token, eine Zeile
   finaplo/base-url-<datum>.txt   # z.B. https://finaplo-apis.paymentcomponents.com
   ```
4. Alternativ: Environment-Variablen `FINAPLO_API_KEY` und `FINAPLO_BASE_URL` (haben Vorrang vor den Dateien).

Der Ordner `finaplo/` ist via `.gitignore` ausgeschlossen, damit Credentials nie versehentlich commited werden.

## Base-URLs

Swagger listet beide Environments:

| Environment | Base URL |
|---|---|
| LIVE | `https://finaplo-apis.paymentcomponents.com` |
| SANDBOX | `https://finaplo-apis.paymentcomponents.com/sandbox` |

Waehrend des Trial-Zeitraums nutzen beide dieselbe Quota.

## Endpoint-Dispatch pro Flavor

`src/finaplo/client.py::endpoint_for_flavor(flavor, sepa_scheme="sct")` mappt:

| Pacs008Flavor | Endpoint | Status |
|---|---|---|
| `CBPR+` | `POST /cbpr/validate` | ✅ aktiv |
| `TARGET2` | `POST /target2/validate` | vorbereitet |
| `SEPA` | `POST /sepa/{scheme}/validate` | vorbereitet |
| `SIC` | — | NotImplementedError |

## Request-Format

```http
POST /cbpr/validate HTTP/1.1
Host: finaplo-apis.paymentcomponents.com
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
| 200 | Message valid | `FinaploResult(valid=True, errors=[])` |
| 400 | Validation-Fehler (typischerweise JSON-Array oder JSON-Object mit `errors`/`messages`/`violations`) | `FinaploResult(valid=False, errors=[...])` |
| 401 | Unauthorized (Key falsch / abgelaufen) | `FinaploAuthError` raised |
| 412 | `subscription.expired` (Trial-Quota aufgebraucht) | `FinaploQuotaExceeded` raised → Pipeline skipt alle verbleibenden Calls |
| 500-599 | Server-Fehler | `FinaploServerError` raised |
| Netzwerk | Connection/Timeout | `FinaploError` raised |

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

`Pacs008TestPipeline(config, use_finaplo=True)` aktiviert den FINaplo-Aufruf pro Testcase. Triggering via CLI:

```bash
poetry run python -m src.main \
    --input templates/testfaelle_pacs008_comprehensive.xlsx \
    --config config.yaml \
    --finaplo
```

Logik (pro Testcase):

1. **Skip fuer negative Testcases**: wenn `expected_result=NOK` und `violate_rule` gesetzt, wird FINaplo nicht aufgerufen (Quota-Sparmassnahme)
2. **Skip wenn Quota exhausted**: nach der ersten `FinaploQuotaExceeded` setzt die Pipeline ein Flag und skippt alle verbleibenden Calls
3. **Normaler Call**: `client.validate(xml_bytes, flavor=tc.flavor)` → `FinaploResult`
4. **Error-Handling**: Netzwerk/Auth/Server → `finaplo_valid=False`, `finaplo_errors=[...]`; Quota exhausted → `finaplo_valid=None` (neutral, nicht Fail)

Das Ergebnis landet im JSON-Report pro Testcase:

```json
{
  "testcase_id": "TC-PCS-001",
  "finaplo_valide": true,
  "finaplo_fehler": []
}
```

Und als Run-Level-Counter:

```json
{
  "testlauf": {
    "finaplo_enabled": true,
    "finaplo_checked": 18,
    "finaplo_valid": 17
  }
}
```

## Overall-Pass-Logik mit FINaplo

```
overall_ok = xsd_valid AND all_br_pass AND finaplo_ok
finaplo_ok = (finaplo_valid is None OR finaplo_valid is True)

wenn expected_result == NOK:
    overall_pass = not overall_ok
sonst:
    overall_pass = overall_ok
```

Das heisst: ein FINaplo-`valid=None` (skip/quota) zaehlt als neutral und blockiert keinen Pass. Nur ein echter `valid=False` markiert den Testcase als Fail.

## Trial-Quota

Der kostenlose Trial hat eine **harte Total-Quota** (erfahrungsgemaess ~20 Calls, nicht per-Tag oder per-Stunde resettend). Bei Erreichen der Quota liefert die API `HTTP 412` mit Body `subscription.expired`.

**Quota-Schonende Massnahmen in der Pipeline:**

- Negative Testcases werden uebersprungen (spart ~20 Calls bei `testfaelle_pacs008_comprehensive.xlsx`)
- Nach dem ersten `subscription.expired` laeuft die Pipeline weiter mit `finaplo_valid=None` und macht keine weiteren Calls

**Wenn du eine groessere Test-Runde planst:** upgrade auf ein Paid-Tier oder verteile die Runs auf mehrere Trial-Accounts.

## Troubleshooting

| Symptom | Ursache | Loesung |
|---|---|---|
| `FinaploConfigError: API-Key nicht gefunden` | Weder ENV noch Datei gesetzt | `finaplo/api-key-*.txt` anlegen oder `FINAPLO_API_KEY` setzen |
| `FinaploAuthError: 401 Unauthorized` | Key falsch/abgelaufen | Neuen Key im FINaplo-Dashboard generieren |
| `FinaploQuotaExceeded: subscription.expired` | Trial-Quota leer | Auf Paid-Tier upgraden oder neues Konto |
| Alle Testcases `finaplo_valide=None` im Report | `use_finaplo` nicht aktiviert oder Quota gleich beim ersten Call leer | `--finaplo` Flag setzen + Key pruefen |
| `Pipeline-Exception: ...` | anderer Fehler (Netzwerk/Encoding) | Stacktrace im Report-Feld `finaplo_fehler` pruefen |

## Unit-Tests

- `tests/test_finaplo_client.py`: 20 Tests fuer den Client (Auth, Error-Parsing, per-Flavor Dispatch, Quota-Handling)
- `tests/test_pacs008_pipeline.py::TestFinaploIntegration`: 6 Integration-Tests fuer die Pipeline (mocked 200/400/401, Counter, Auto-Disable bei fehlenden Credentials)

Alle Client- und Integration-Tests nutzen `responses` fuer HTTP-Mocks; es sind keine echten Netzwerk-Calls in der CI.
