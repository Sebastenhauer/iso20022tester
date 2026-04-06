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


def test_parse_instant_flag_true():
    """Instant-Spalte wird als Boolean geparst."""
    headers_with_instant = V2_HEADERS + ["Instant"]
    data = [
        "TC-001", "Test", "Ziel", "OK", "Domestic-IBAN",
        100.00, "CHF", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
        None, None, None, None,
        None, None, None, None,
        True,
    ]
    path = _create_test_excel([headers_with_instant, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert testcases[0].instant is True
    os.unlink(path)


def test_parse_instant_flag_false():
    """Instant=False oder fehlend bleibt False."""
    headers_with_instant = V2_HEADERS + ["Instant"]
    data = [
        "TC-001", "Test", "Ziel", "OK", "Domestic-IBAN",
        100.00, "CHF", "Test AG", "CH9300762011623852957", None,
        None, None, None, None,
        None, None, None, None,
        False,
    ]
    path = _create_test_excel([headers_with_instant, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert testcases[0].instant is False
    os.unlink(path)


def test_parse_instant_missing_column():
    """Ohne Instant-Spalte ist instant=False."""
    data = [
        "TC-001", "Test", "Ziel", "OK", "Domestic-IBAN",
        100.00, "CHF", "Test AG", "CH9300762011623852957", None,
        None, None, None, None,
        None, None, None, None,
    ]
    path = _create_test_excel([V2_HEADERS, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert testcases[0].instant is False
    os.unlink(path)


def test_parse_duplicate_testcase_id():
    """Doppelte TestcaseIDs erzeugen einen Fehler."""
    row1 = [
        "TC-001", "Test1", "Ziel1", "OK", "SEPA",
        100, "EUR", "Test AG", "CH9300762011623852957", None,
        None, None, None, None, None, None, None, None,
    ]
    row2 = [
        "TC-001", "Test2", "Ziel2", "OK", "SEPA",
        200, "EUR", "Test AG", "CH9300762011623852957", None,
        None, None, None, None, None, None, None, None,
    ]
    path = _create_test_excel([V2_HEADERS, row1, row2])
    testcases, errors = parse_excel(path)
    assert len(errors) > 0
    assert "doppelt" in errors[0].lower()
    os.unlink(path)


def test_parse_sammelauftrag_true():
    """Sammelauftrag=True wird als batch_booking=True geparst."""
    headers = V2_HEADERS + ["Sammelauftrag"]
    data = [
        "TC-001", "Test", "Ziel", "OK", "Domestic-IBAN",
        100.00, "CHF", "Test AG", "CH9300762011623852957", None,
        None, None, None, None,
        None, None, None, None,
        True,
    ]
    path = _create_test_excel([headers, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert testcases[0].batch_booking is True
    os.unlink(path)


def test_parse_sammelauftrag_false():
    """Sammelauftrag=False wird als batch_booking=False geparst."""
    headers = V2_HEADERS + ["Sammelauftrag"]
    data = [
        "TC-001", "Test", "Ziel", "OK", "Domestic-IBAN",
        100.00, "CHF", "Test AG", "CH9300762011623852957", None,
        None, None, None, None,
        None, None, None, None,
        False,
    ]
    path = _create_test_excel([headers, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert testcases[0].batch_booking is False
    os.unlink(path)


def test_parse_sammelauftrag_missing_column():
    """Ohne Sammelauftrag-Spalte ist batch_booking=None."""
    data = [
        "TC-001", "Test", "Ziel", "OK", "Domestic-IBAN",
        100.00, "CHF", "Test AG", "CH9300762011623852957", None,
        None, None, None, None,
        None, None, None, None,
    ]
    path = _create_test_excel([V2_HEADERS, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert testcases[0].batch_booking is None
    os.unlink(path)


def test_parse_sammelauftrag_ja():
    """Sammelauftrag='Ja' wird als batch_booking=True geparst."""
    headers = V2_HEADERS + ["Sammelauftrag"]
    data = [
        "TC-001", "Test", "Ziel", "OK", "Domestic-IBAN",
        100.00, "CHF", "Test AG", "CH9300762011623852957", None,
        None, None, None, None,
        None, None, None, None,
        "Ja",
    ]
    path = _create_test_excel([headers, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert testcases[0].batch_booking is True
    os.unlink(path)
