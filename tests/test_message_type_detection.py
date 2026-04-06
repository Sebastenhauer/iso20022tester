"""Tests fuer Auto-Detection des Message-Typs (pain.001 vs pacs.008)."""

import pytest

from src.input_handler.excel_parser import (
    detect_message_type,
    detect_message_type_from_file,
)


def test_pain001_header_detected():
    header = [
        "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis",
        "Zahlungstyp", "Debtor Name", "Debtor IBAN", "Betrag", "Waehrung",
    ]
    assert detect_message_type(header) == "pain.001"


def test_pacs008_header_detected():
    header = [
        "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis", "Flavor",
        "BAH From BIC", "BAH To BIC",
        "InstgAgt BIC", "InstdAgt BIC",
        "IntrBkSttlmAmt", "IntrBkSttlmDt", "SttlmMtd",
    ]
    assert detect_message_type(header) == "pacs.008"


def test_ambiguous_header_raises():
    """Header mit Marker-Spalten beider Welten ist ambig."""
    header = [
        "TestcaseID", "Titel",
        "Zahlungstyp",  # pain.001
        "InstgAgt BIC", "InstdAgt BIC", "IntrBkSttlmDt",  # pacs.008
    ]
    with pytest.raises(ValueError, match="sowohl pain.001- als auch pacs.008"):
        detect_message_type(header)


def test_empty_or_unknown_header_raises():
    header = ["TestcaseID", "Titel", "SomeRandomColumn"]
    with pytest.raises(ValueError, match="konnte nicht erkannt"):
        detect_message_type(header)


def test_detect_from_stub_pacs008_file(tmp_path):
    """Integration: der Scaffold-Stub wird als pacs.008 erkannt."""
    import openpyxl
    path = tmp_path / "stub.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([
        "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis",
        "InstgAgt BIC", "InstdAgt BIC", "IntrBkSttlmDt", "SttlmMtd",
    ])
    ws.append([
        "TC-001", "Smoke", "Smoke", "OK",
        "UBSWCHZH80A", "DEUTDEFFXXX", "2026-04-08", "INDA",
    ])
    wb.save(path)
    assert detect_message_type_from_file(str(path)) == "pacs.008"


def test_detect_from_pain001_comprehensive_template():
    """Regression: bestehendes pain.001 Template wird weiterhin als pain.001 erkannt."""
    assert (
        detect_message_type_from_file("templates/testfaelle_comprehensive.xlsx")
        == "pain.001"
    )
