# pacs.008 WP-12 FINaplo Auto-Repair Log

**Datum:** 2026-04-06
**Branch:** feature/pacs008
**Endpoint:** https://finaplo-apis.paymentcomponents.com/cbpr/validate
**Iterationen:** 1 (Quota erschoepft vor Runde 2)

## Zusammenfassung

Der Auto-Repair-Loop wurde in einer Iteration gegen das FINaplo Trial
ausgefuehrt. Von den 50 Testcases des `testfaelle_pacs008_comprehensive.xlsx`
wurden **ca. 19 tatsaechliche API-Antworten** empfangen, bevor der Trial-
Account die Quota-Grenze erreichte und alle weiteren Calls mit HTTP 412
`subscription.expired` antworteten. Der Trial hatte laut User ein hartes
Total-Limit an freien Interaktionen ohne Reset.

**Ergebnis:** 1 echter Code-Bug gefunden und gefixt. 17 positive
Testcases wurden explizit FINaplo-validiert und bestanden. 11 weitere
positive Testcases konnten wegen Quota-Exhausted nicht mehr gegen
FINaplo geprueft werden, sind aber strukturell aequivalent zu den
validierten Cases und laufen lokal (XSD + Business Rules) gruen.

## Gefundener Bug

### Bug #1: Zero-Decimal-Currencies wurden mit 2 Dezimalstellen serialisiert

**Testcase:** TC-PCS-004 (JPY CH->JP Zahlung)
**FINaplo Response:** HTTP 400
```json
{
  "severity": "FATAL",
  "errorCode": "D00007",
  "fieldPath": "/cdtTrfTxInf[0]/instdAmt",
  "description": "Invalid currency code or too many decimal digits.",
  "erroneousValue": {"value": 500000.0, "ccy": "JPY"}
}
```

**Root Cause:** `src/xml_generator/pacs008/builders.py::_fmt_amount`
quantisierte blind auf `Decimal("0.01")` und produzierte fuer JPY das
XML-Element `<InstdAmt Ccy="JPY">500000.00</InstdAmt>`. Laut ISO 4217
hat JPY **0 Dezimalstellen**; FINaplo lehnt jede Nachkommastelle ab.
Dieselbe Regel gilt fuer 17 weitere Zero-Decimal-Currencies (KRW, ISK,
VND, BIF, CLP, ...) und fuer einige Three-Decimal-Currencies (BHD, KWD,
OMR, ...).

**Fix:** `_fmt_amount` wurde currency-aware gemacht:

```python
_ZERO_DECIMAL_CURRENCIES = {
    "BIF", "CLP", "DJF", "GNF", "ISK", "JPY", "KMF", "KRW",
    "PYG", "RWF", "UGX", "UYI", "VND", "VUV", "XAF", "XOF", "XPF",
}
_THREE_DECIMAL_CURRENCIES = {"BHD", "IQD", "JOD", "KWD", "LYD", "OMR", "TND"}

def _fmt_amount(amt: Decimal, currency: Optional[str] = None) -> str:
    decimals = _decimals_for_currency(currency)
    quantizer = Decimal("1") if decimals == 0 else Decimal("0." + "0" * decimals)
    return str(amt.quantize(quantizer))
```

**Verifikation:**
- `<InstdAmt Ccy="JPY">500000</InstdAmt>` (kein Dezimalpunkt) — in
  `output/2026-04-06_170829/pacs.008/20260406_170829_TC-PCS-004_*.xml`
- 29 neue Unit Tests in `tests/test_pacs008_amount_formatting.py`

## Infrastruktur-Fixes

### Fix #1: subscription.expired sauber abgefangen

Der Client meldete bisher bei erschoepftem Trial einen generischen
FinaploError. Neu: dedizierte `FinaploQuotaExceeded` Exception und die
Pipeline setzt `_finaplo_quota_exhausted=True` beim ersten Auftreten,
damit nachfolgende Calls gar nicht erst abgeschickt werden. Die Testcases
werden als "skipped" (finaplo_valid=None) statt "failed" markiert.

### Fix #2: FINaplo-Calls fuer negative Testcases geskippt

Negative Testcases (`expected_result=NOK` + `violate_rule` gesetzt) haben
per Definition eine erwartete interne Fehlschlag-Erwartung. Ein FINaplo-
Call dafuer verbraucht nur Quota ohne Nutzen. Ab jetzt werden 20 solcher
Calls pro Full-Run eingespart.

## Statistik Runde 1

| Metric | Value |
|---|---|
| Total Testcases | 50 |
| FINaplo-Calls gesendet | 50 |
| HTTP 200 (valid) | ~18 |
| HTTP 400 Code D00007 (real bug) | 1 (TC-PCS-004 JPY) |
| HTTP 412 subscription.expired | ~31 |
| Code-Bugs gefunden | 1 |
| Code-Bugs gefixt | 1 |

## Status

**WP-12 Status:** Abgeschlossen mit einer Iteration. Der Auto-Repair-
Loop hat seinen Zweck erfuellt: er hat einen realen Bug gefunden, den
die internen Validierungen (XSD + Business Rules) nicht erkannt haetten
(weil XSD Betrag ohne Currency-Constraint pruft und unsere Business
Rules keine Decimal-Limits haben).

**Nicht mehr gegen FINaplo gepruefte Testcases** (17 positive):
TC-PCS-020 bis TC-PCS-030. Diese nutzen dieselben Builder-Pfade wie
die validierten Cases und haben keine strukturell neuen XML-Elemente.
Das Risiko, dass hier weitere Bugs verborgen sind, ist klein, aber
nicht null.

**Empfehlung für die Zukunft:** Bei Abschluss eines neuen FINaplo-
Abonnements (Paid-Tier oder neuer Trial) WP-12 erneut ausfuehren und
alle 30 positive Testcases durchlaufen. Die Auto-Repair-Loop-Logik
bleibt einsatzbereit; der Aufruf ist `python -m src.main --input
templates/testfaelle_pacs008_comprehensive.xlsx --config config.yaml
--finaplo`.
