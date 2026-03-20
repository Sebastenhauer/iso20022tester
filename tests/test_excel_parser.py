"""Tests für den Excel-Parser."""

import os
import tempfile

from openpyxl import Workbook

from src.input_handler.excel_parser import parse_excel


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
    headers = [
        "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis", "Zahlungstyp",
        "Betrag", "Währung", "Debtor Infos", "Weitere Testdaten",
        "Erwartete API-Antwort", "Ergebnis (OK/NOK)", "Bemerkungen",
    ]
    data = [
        "TC-001", "Test", "Ziel", "OK", "SEPA", 100.00, "EUR",
        "Name=Test AG; IBAN=CH9300762011623852957", "", "", "", "",
    ]
    path = _create_test_excel([headers, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert len(testcases) == 1
    assert testcases[0].testcase_id == "TC-001"
    assert testcases[0].debtor.name == "Test AG"
    os.unlink(path)


def test_parse_missing_columns():
    headers = ["TestcaseID", "Titel"]
    path = _create_test_excel([headers])
    testcases, errors = parse_excel(path)
    assert len(errors) > 0
    assert "Fehlende Pflichtspalten" in errors[0]
    os.unlink(path)


def test_parse_skip_empty_testcase_id():
    headers = [
        "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis", "Zahlungstyp",
        "Betrag", "Währung", "Debtor Infos", "Weitere Testdaten",
        "Erwartete API-Antwort", "Ergebnis (OK/NOK)", "Bemerkungen",
    ]
    data1 = [
        "", "Test", "Ziel", "OK", "SEPA", 100, "EUR",
        "Name=Test; IBAN=CH9300762011623852957", "", "", "", "",
    ]
    data2 = [
        "TC-002", "Test2", "Ziel2", "OK", "SEPA", 200, "EUR",
        "Name=Test2; IBAN=CH9300762011623852957", "", "", "", "",
    ]
    path = _create_test_excel([headers, data1, data2])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert len(testcases) == 1
    assert testcases[0].testcase_id == "TC-002"
    os.unlink(path)


def test_parse_invalid_payment_type():
    headers = [
        "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis", "Zahlungstyp",
        "Betrag", "Währung", "Debtor Infos", "Weitere Testdaten",
        "Erwartete API-Antwort", "Ergebnis (OK/NOK)", "Bemerkungen",
    ]
    data = [
        "TC-001", "Test", "Ziel", "OK", "INVALID", 100, "EUR",
        "Name=Test; IBAN=CH9300762011623852957", "", "", "", "",
    ]
    path = _create_test_excel([headers, data])
    testcases, errors = parse_excel(path)
    assert len(errors) > 0
    assert "Zahlungstyp" in errors[0]
    os.unlink(path)


def test_parse_violate_rule_extraction():
    headers = [
        "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis", "Zahlungstyp",
        "Betrag", "Währung", "Debtor Infos", "Weitere Testdaten",
        "Erwartete API-Antwort", "Ergebnis (OK/NOK)", "Bemerkungen",
    ]
    data = [
        "TC-001", "Test", "Ziel", "NOK", "SEPA", 100, "EUR",
        "Name=Test; IBAN=CH9300762011623852957",
        "ViolateRule=BR-SEPA-001; ChrgBr=SLEV",
        "", "", "",
    ]
    path = _create_test_excel([headers, data])
    testcases, errors = parse_excel(path)
    assert len(errors) == 0
    assert testcases[0].violate_rule == "BR-SEPA-001"
    assert "ViolateRule" not in testcases[0].overrides
    assert testcases[0].overrides.get("ChrgBr") == "SLEV"
    os.unlink(path)
