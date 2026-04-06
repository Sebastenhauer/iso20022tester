"""Tests fuer parse_pacs008_excel()."""

from decimal import Decimal

import openpyxl
import pytest

from src.input_handler.excel_parser import parse_pacs008_excel
from src.models.pacs008 import Pacs008Flavor, SettlementMethod
from src.models.testcase import ExpectedResult


def _build_excel(path, header, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)


MIN_HEADER = [
    "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis",
    "InstgAgt BIC", "InstdAgt BIC",
    "Debtor Name", "Debtor IBAN", "DbtrAgt BIC",
    "Creditor Name", "Creditor IBAN", "CdtrAgt BIC",
    "IntrBkSttlmAmt", "Währung", "IntrBkSttlmDt", "SttlmMtd",
]

MIN_ROW = [
    "TC-A", "Title A", "Goal A", "OK",
    "UBSWCHZH80A", "DEUTDEFFXXX",
    "Muster AG", "CH5604835012345678009", "UBSWCHZH80A",
    "Empfaenger GmbH", "DE89370400440532013000", "DEUTDEFFXXX",
    "1000", "EUR", "2026-04-08", "INDA",
]


def test_parse_stub_template():
    """Das ausgelieferte Stub-Template parsed ohne Fehler."""
    tcs, errs = parse_pacs008_excel("templates/testfaelle_pacs008_minimal.xlsx")
    assert errs == []
    assert len(tcs) == 3
    assert tcs[0].testcase_id == "TC-PACS-001"
    assert tcs[0].flavor == Pacs008Flavor.CBPR_PLUS
    assert tcs[0].settlement_method == SettlementMethod.INDA
    assert tcs[0].amount == Decimal("1000")
    assert tcs[0].currency == "EUR"
    assert tcs[0].debtor_iban == "CH5604835012345678009"
    assert tcs[0].creditor_agent_bic == "DEUTDEFFXXX"
    assert tcs[0].debtor_address is not None
    assert tcs[0].debtor_address.town_name == "Zurich"


def test_intermediary_agent(tmp_path):
    path = tmp_path / "imy.xlsx"
    header = MIN_HEADER + ["IntrmyAgt1 BIC", "ChrgBr"]
    row = MIN_ROW + ["CHASUS33XXX", "SHAR"]
    _build_excel(str(path), header, [row])
    tcs, errs = parse_pacs008_excel(str(path))
    assert errs == []
    assert tcs[0].intermediary_agent_1_bic == "CHASUS33XXX"
    assert tcs[0].charge_bearer == "SHAR"


def test_clr_sys_mmb_id(tmp_path):
    path = tmp_path / "clr.xlsx"
    header = MIN_HEADER + ["CdtrAgt ClrSysMmbId"]
    row = MIN_ROW[:-5] + ["Empfaenger Inc", None, None, None, "EUR",
                          "2026-04-08", "INDA", "021000021"]
    # This row structure is a bit tangled -- rebuild cleanly
    header = [
        "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis",
        "Debtor Name", "Debtor IBAN", "DbtrAgt BIC",
        "Creditor Name", "Creditor IBAN", "CdtrAgt BIC", "CdtrAgt ClrSysMmbId",
        "IntrBkSttlmAmt", "Währung", "IntrBkSttlmDt", "SttlmMtd",
    ]
    row = [
        "TC-CLR", "Title", "Goal", "OK",
        "Muster AG", "CH5604835012345678009", "UBSWCHZH80A",
        "NY Corp", None, None, "021000021",
        "500", "USD", "2026-04-08", "INDA",
    ]
    _build_excel(str(path), header, [row])
    tcs, errs = parse_pacs008_excel(str(path))
    assert errs == []
    assert tcs[0].creditor_agent_clr_sys_mmb_id == "021000021"
    assert tcs[0].creditor_agent_bic is None


def test_overrides_dot_notation(tmp_path):
    path = tmp_path / "ov.xlsx"
    header = MIN_HEADER + ["Weitere Testdaten"]
    row = MIN_ROW + ["IntrmyAgt1.FinInstnId.BICFI=CHASUS33XXX; ChrgsInf[0].Amt=12.50"]
    _build_excel(str(path), header, [row])
    tcs, errs = parse_pacs008_excel(str(path))
    assert errs == []
    assert tcs[0].overrides["IntrmyAgt1.FinInstnId.BICFI"] == "CHASUS33XXX"
    assert tcs[0].overrides["ChrgsInf[0].Amt"] == "12.50"


def test_violate_rule_column(tmp_path):
    path = tmp_path / "viol.xlsx"
    header = MIN_HEADER + ["ViolateRule"]
    row = MIN_ROW + ["BR-CBPR-PACS-001"]
    _build_excel(str(path), header, [row])
    tcs, errs = parse_pacs008_excel(str(path))
    assert errs == []
    assert tcs[0].violate_rule == "BR-CBPR-PACS-001"


def test_missing_required_column_errors(tmp_path):
    path = tmp_path / "bad.xlsx"
    header = ["TestcaseID", "Titel"]  # missing Ziel, Erwartetes Ergebnis
    row = ["TC-X", "Title"]
    _build_excel(str(path), header, [row])
    tcs, errs = parse_pacs008_excel(str(path))
    assert tcs == []
    assert any("Fehlende Pflichtspalten" in e for e in errs)


def test_invalid_expected_result(tmp_path):
    path = tmp_path / "bad.xlsx"
    _build_excel(str(path), MIN_HEADER, [["TC-X", "T", "Z", "XXX"] + MIN_ROW[4:]])
    tcs, errs = parse_pacs008_excel(str(path))
    assert tcs == []
    assert any("OK/NOK" in e for e in errs)


def test_duplicate_testcase_id(tmp_path):
    path = tmp_path / "dup.xlsx"
    _build_excel(str(path), MIN_HEADER, [MIN_ROW, MIN_ROW])
    tcs, errs = parse_pacs008_excel(str(path))
    assert tcs == []
    assert any("doppelt vorhanden" in e for e in errs)


def test_invalid_flavor_errors(tmp_path):
    path = tmp_path / "flav.xlsx"
    header = MIN_HEADER + ["Flavor"]
    row = MIN_ROW + ["Banana"]
    _build_excel(str(path), header, [row])
    tcs, errs = parse_pacs008_excel(str(path))
    assert tcs == []
    assert any("Ungueltiger Flavor" in e for e in errs)


def test_invalid_sttlm_mtd_errors(tmp_path):
    path = tmp_path / "stm.xlsx"
    row = list(MIN_ROW)
    row[15] = "XXXX"  # SttlmMtd col
    _build_excel(str(path), MIN_HEADER, [row])
    tcs, errs = parse_pacs008_excel(str(path))
    assert tcs == []
    assert any("Ungueltige SttlmMtd" in e for e in errs)


def test_empty_rows_ignored(tmp_path):
    path = tmp_path / "empty.xlsx"
    _build_excel(str(path), MIN_HEADER, [MIN_ROW, [None] * len(MIN_HEADER)])
    tcs, errs = parse_pacs008_excel(str(path))
    assert errs == []
    assert len(tcs) == 1  # empty row skipped


def test_expected_result_nok(tmp_path):
    path = tmp_path / "nok.xlsx"
    row = list(MIN_ROW)
    row[3] = "NOK"
    _build_excel(str(path), MIN_HEADER, [row])
    tcs, errs = parse_pacs008_excel(str(path))
    assert errs == []
    assert tcs[0].expected_result == ExpectedResult.NOK
