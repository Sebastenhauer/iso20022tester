"""Tests für den Excel-Parser (v2-Format)."""

import os
import tempfile

from openpyxl import Workbook

from src.input_handler.excel_parser import parse_excel


V2_HEADERS = [
    "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis", "Zahlungstyp",
    "Betrag", "Waehrung", "Debtor Name", "Debtor IBAN", "Debtor BIC",
    "Creditor Name", "Creditor IBAN", "Creditor BIC", "Verwendungszweck",
    "ViolateRule", "Weitere Testdaten", "Erwartete API-Antwort", "Bemerkungen",
]


def _create_test_excel(rows, filename="test.xlsx"):
    """Erstellt eine temporäre Excel-Datei mit den gegebenen Zeilen."""
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    path = os.path.join(tempfile.gettempdir(), filename)
    wb.save(path)
    return path


def test_parse_valid_excel():
    data = [
        "TC-001", "Test", "Ziel", "OK", "SEPA",
        100.00, "EUR", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
        None, None, None, None,
        None, None, None, None,
    ]
    path = _create_test_excel([V2_HEADERS, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert len(testcases) == 1
    assert testcases[0].testcase_id == "TC-001"
    assert testcases[0].debtor.iban == "CH9300762011623852957"
    os.unlink(path)


def test_parse_missing_columns():
    headers = ["TestcaseID", "Titel"]
    path = _create_test_excel([headers])
    testcases, errors = parse_excel(path)
    assert len(errors) > 0
    assert "Fehlende Pflichtspalten" in errors[0]
    os.unlink(path)


def test_parse_skip_empty_testcase_id():
    data1 = [
        "", "Test", "Ziel", "OK", "SEPA",
        100, "EUR", "Test", "CH9300762011623852957", None,
        None, None, None, None, None, None, None, None,
    ]
    data2 = [
        "TC-002", "Test2", "Ziel2", "OK", "SEPA",
        200, "EUR", "Test2", "CH9300762011623852957", None,
        None, None, None, None, None, None, None, None,
    ]
    path = _create_test_excel([V2_HEADERS, data1, data2])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    # Zeile ohne TestcaseID wird als zusätzliche Transaktion interpretiert,
    # aber es gibt keinen vorherigen Testfall → wird übersprungen
    # TC-002 ist der einzige Testfall
    assert len(testcases) == 1
    assert testcases[0].testcase_id == "TC-002"
    os.unlink(path)


def test_parse_invalid_payment_type():
    data = [
        "TC-001", "Test", "Ziel", "OK", "INVALID",
        100, "EUR", "Test", "CH9300762011623852957", None,
        None, None, None, None, None, None, None, None,
    ]
    path = _create_test_excel([V2_HEADERS, data])
    testcases, errors = parse_excel(path)
    assert len(errors) > 0
    assert "Zahlungstyp" in errors[0] or "Ungueltig" in errors[0]
    os.unlink(path)


def test_parse_violate_rule_extraction():
    data = [
        "TC-001", "Test", "Ziel", "NOK", "SEPA",
        100, "EUR", "Test", "CH9300762011623852957", None,
        None, None, None, None,
        "BR-SEPA-001", "ChrgBr=SLEV", None, None,
    ]
    path = _create_test_excel([V2_HEADERS, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert testcases[0].violate_rule == "BR-SEPA-001"
    assert testcases[0].overrides.get("ChrgBr") == "SLEV"
    os.unlink(path)


def test_parse_multiple_transactions():
    """Zeilen ohne TestcaseID sind zusätzliche Transaktionen."""
    row1 = [
        "TC-001", "Multi-Tx", "Ziel", "OK", "SEPA",
        100, "EUR", "Test AG", "CH9300762011623852957", None,
        "Creditor1", "DE89370400440532013000", None, None,
        None, None, None, None,
    ]
    row2 = [
        None, None, None, None, None,
        200, "EUR", None, None, None,
        "Creditor2", "FR7630006000011234567890189", None, None,
        None, None, None, None,
    ]
    path = _create_test_excel([V2_HEADERS, row1, row2])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert len(testcases) == 1
    assert testcases[0].tx_count == 2
    assert len(testcases[0].transaction_inputs) == 2
    os.unlink(path)
