"""End-to-End Tests: Excel rein → XML + Report raus.

Testet die gesamte Pipeline ohne Dateisystem-Nebeneffekte wo moeglich.
"""

import os
import tempfile
from decimal import Decimal

import pytest
from openpyxl import Workbook

from src.config import load_config
from src.main import run
from src.models.config import AppConfig


V2_HEADERS = [
    "TestcaseID", "Titel", "Ziel", "Erwartetes Ergebnis", "Zahlungstyp",
    "Betrag", "Waehrung", "Debtor Name", "Debtor IBAN", "Debtor BIC",
    "Creditor Name", "Creditor IBAN", "Creditor BIC", "Verwendungszweck",
    "ViolateRule", "Weitere Testdaten", "Erwartete API-Antwort", "Bemerkungen",
]


def _create_excel(rows, tmpdir):
    """Erstellt eine Excel-Datei im temp-Verzeichnis."""
    wb = Workbook()
    ws = wb.active
    ws.append(V2_HEADERS)
    for row in rows:
        ws.append(row)
    path = os.path.join(tmpdir, "test.xlsx")
    wb.save(path)
    return path


def _config(tmpdir):
    return AppConfig(
        output_path=tmpdir,
        xsd_path="schemas/pain.001/pain.001.001.09.ch.03.xsd",
        seed=42,
        report_format="txt",
    )


def _sepa_row(tc_id="TC-001", expected="OK", violate=None):
    return [
        tc_id, "SEPA Test", "Positive Zahlung", expected, "SEPA",
        1500.00, "EUR", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
        None, None, None, None,
        violate, None, None, None,
    ]


def _qr_row(tc_id="TC-002", expected="OK", violate=None):
    return [
        tc_id, "QR Test", "QR Zahlung", expected, "Domestic-QR",
        500.00, "CHF", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
        None, None, None, None,
        violate, None, None, None,
    ]


def _iban_row(tc_id="TC-003", expected="OK", violate=None):
    return [
        tc_id, "IBAN Test", "Domestic Zahlung", expected, "Domestic-IBAN",
        800.00, "CHF", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
        None, None, None, None,
        violate, None, None, None,
    ]


def _cbpr_row(tc_id="TC-004", expected="OK", violate=None, bic="BNPAFRPP"):
    overrides = f"CdtrAgt.BICFI={bic}" if bic else ""
    return [
        tc_id, "CBPR+ Test", "Cross-Border", expected, "CBPR+",
        10000.00, "USD", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
        None, None, None, None,
        violate, overrides, None, None,
    ]


# --- SIC5 Instant Helpers ---

V2_HEADERS_INSTANT = V2_HEADERS + ["Instant"]


def _create_excel_instant(rows, tmpdir):
    """Erstellt eine Excel-Datei mit Instant-Spalte."""
    wb = Workbook()
    ws = wb.active
    ws.append(V2_HEADERS_INSTANT)
    for row in rows:
        ws.append(row)
    path = os.path.join(tmpdir, "test.xlsx")
    wb.save(path)
    return path


def _instant_row(tc_id="TC-INST", expected="OK", violate=None):
    return [
        tc_id, "SIC5 Instant", "Instant Zahlung CHF", expected, "Domestic-IBAN",
        250.00, "CHF", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
        None, None, None, None,
        violate, None, None, None,
        True,  # Instant
    ]


# =========================================================================
# Positive Testfaelle (OK → Pass)
# =========================================================================

class TestPositiveE2E:
    def test_sepa_ok(self, tmp_path):
        excel = _create_excel([_sepa_row()], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert len(results) == 1
        assert results[0].overall_pass is True
        assert results[0].xsd_valid is True

    def test_qr_ok(self, tmp_path):
        excel = _create_excel([_qr_row()], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert len(results) == 1
        assert results[0].overall_pass is True

    def test_iban_ok(self, tmp_path):
        excel = _create_excel([_iban_row()], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert len(results) == 1
        assert results[0].overall_pass is True

    def test_cbpr_ok(self, tmp_path):
        excel = _create_excel([_cbpr_row()], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert len(results) == 1
        assert results[0].overall_pass is True

    def test_all_types_together(self, tmp_path):
        rows = [_sepa_row("TC-S"), _qr_row("TC-Q"), _iban_row("TC-I"), _cbpr_row("TC-C")]
        excel = _create_excel(rows, str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert len(results) == 4
        assert all(r.overall_pass for r in results)


# =========================================================================
# Negative Testfaelle (NOK + ViolateRule → Pass)
# =========================================================================

class TestNegativeE2E:
    def test_sepa_nok_wrong_currency(self, tmp_path):
        excel = _create_excel([_sepa_row("TC-N1", "NOK", "BR-SEPA-001")], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        failed_ids = {r.rule_id for r in results[0].business_rule_results if not r.passed}
        assert "BR-SEPA-001" in failed_ids

    def test_qr_nok_no_reference(self, tmp_path):
        excel = _create_excel([_qr_row("TC-N2", "NOK", "BR-QR-002")], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True

    def test_iban_nok_wrong_currency(self, tmp_path):
        excel = _create_excel([_iban_row("TC-N3", "NOK", "BR-IBAN-004")], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True

    def test_cbpr_nok_no_agent(self, tmp_path):
        excel = _create_excel(
            [_cbpr_row("TC-N4", "NOK", "BR-CBPR-005", bic="BNPAFRPP")],
            str(tmp_path),
        )
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True

    def test_dom_nok_charge_bearer_set(self, tmp_path):
        """BR-DOM-001: Domestic mit ChrgBr=SHAR via ViolateRule."""
        excel = _create_excel(
            [_iban_row("TC-N5", "NOK", "BR-DOM-001")],
            str(tmp_path),
        )
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        failed_ids = {r.rule_id for r in results[0].business_rule_results if not r.passed}
        assert "BR-DOM-001" in failed_ids


# =========================================================================
# Charge Bearer Aliasse (OUR/BEN/SHA)
# =========================================================================

class TestChargeBearerAliasE2E:
    def test_cbpr_our_resolves_to_debt(self, tmp_path):
        """ChrgBr=OUR wird zu DEBT aufgeloest (CBPR+ OK)."""
        row = [
            "TC-CB1", "CBPR+ OUR", "OUR Test", "OK", "CBPR+",
            5000.00, "USD", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None, "CdtrAgt.BICFI=BNPAFRPP; ChrgBr=OUR", None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True

    def test_cbpr_ben_resolves_to_cred(self, tmp_path):
        """ChrgBr=BEN wird zu CRED aufgeloest (CBPR+ OK)."""
        row = [
            "TC-CB2", "CBPR+ BEN", "BEN Test", "OK", "CBPR+",
            5000.00, "USD", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None, "CdtrAgt.BICFI=BNPAFRPP; ChrgBr=BEN", None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True

    def test_cbpr_sha_resolves_to_shar(self, tmp_path):
        """ChrgBr=SHA wird zu SHAR aufgeloest (CBPR+ OK)."""
        row = [
            "TC-CB3", "CBPR+ SHA", "SHA Test", "OK", "CBPR+",
            5000.00, "USD", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None, "CdtrAgt.BICFI=BNPAFRPP; ChrgBr=SHA", None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True

    def test_cbpr_debt_direct(self, tmp_path):
        """ChrgBr=DEBT direkt (CBPR+ OK)."""
        row = [
            "TC-CB4", "CBPR+ DEBT", "DEBT Test", "OK", "CBPR+",
            5000.00, "USD", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None, "CdtrAgt.BICFI=BNPAFRPP; ChrgBr=DEBT", None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True


# =========================================================================
# Multi-Transaktion
# =========================================================================

class TestMultiTransactionE2E:
    def test_two_transactions(self, tmp_path):
        row1 = [
            "TC-MT", "Multi", "Ziel", "OK", "SEPA",
            100, "EUR", "Test AG", "CH9300762011623852957", None,
            "Creditor1", None, None, None,
            None, None, None, None,
        ]
        row2 = [
            None, None, None, None, None,
            200, "EUR", None, None, None,
            "Creditor2", None, None, None,
            None, None, None, None,
        ]
        excel = _create_excel([row1, row2], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert len(results) == 1
        assert results[0].overall_pass is True


# =========================================================================
# Output-Dateien
# =========================================================================

class TestOutputFiles:
    def test_xml_created(self, tmp_path):
        excel = _create_excel([_sepa_row()], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].xml_file_path is not None
        assert os.path.exists(results[0].xml_file_path)
        assert results[0].xml_file_path.endswith(".xml")

    def test_reports_created(self, tmp_path):
        excel = _create_excel([_sepa_row()], str(tmp_path))
        run(excel, _config(str(tmp_path)), seed_override=42)
        # Finde den Testlauf-Unterordner
        subdirs = [d for d in os.listdir(str(tmp_path)) if os.path.isdir(os.path.join(str(tmp_path), d))]
        assert len(subdirs) == 1
        run_dir = os.path.join(str(tmp_path), subdirs[0])
        files = os.listdir(run_dir)
        assert any(f.endswith(".json") for f in files), f"No JSON report in {files}"
        assert any(f.endswith(".xml") and "testlauf" in f for f in files), f"No JUnit XML in {files}"
        assert any(f.endswith(".txt") for f in files), f"No TXT report in {files}"


# =========================================================================
# Seed-Reproduzierbarkeit
# =========================================================================

class TestReproducibility:
    def test_same_seed_same_results(self, tmp_path):
        excel = _create_excel([_sepa_row()], str(tmp_path))
        r1 = run(excel, _config(str(tmp_path / "run1")), seed_override=42)
        r2 = run(excel, _config(str(tmp_path / "run2")), seed_override=42)
        # Gleicher Seed → gleiche Creditor-Daten
        br1 = {r.rule_id: r.passed for r in r1[0].business_rule_results}
        br2 = {r.rule_id: r.passed for r in r2[0].business_rule_results}
        assert br1 == br2


# =========================================================================
# SIC5 Instant E2E
# =========================================================================

class TestSic5InstantE2E:
    def test_instant_ok(self, tmp_path):
        """SIC5 Instant Zahlung: CHF + CH-IBAN + Instant=True → OK."""
        excel = _create_excel_instant([_instant_row()], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert len(results) == 1
        assert results[0].overall_pass is True
        assert results[0].xsd_valid is True

    def test_instant_nok_wrong_currency_violation(self, tmp_path):
        """SIC5 Instant: Violation BR-SIC5-001 (Währung EUR statt CHF) → NOK."""
        excel = _create_excel_instant(
            [_instant_row("TC-INST-N1", "NOK", "BR-SIC5-001")],
            str(tmp_path),
        )
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        failed_ids = {r.rule_id for r in results[0].business_rule_results if not r.passed}
        assert "BR-SIC5-001" in failed_ids

    def test_instant_nok_wrong_iban_violation(self, tmp_path):
        """SIC5 Instant: Violation BR-SIC5-002 (DE-IBAN statt CH) → NOK."""
        excel = _create_excel_instant(
            [_instant_row("TC-INST-N2", "NOK", "BR-SIC5-002")],
            str(tmp_path),
        )
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        failed_ids = {r.rule_id for r in results[0].business_rule_results if not r.passed}
        assert "BR-SIC5-002" in failed_ids

    def test_non_instant_iban_still_works(self, tmp_path):
        """Domestic-IBAN ohne Instant bleibt unverändert."""
        row = [
            "TC-NI", "Non-Instant", "Nicht-Instant", "OK", "Domestic-IBAN",
            100.00, "CHF", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None, None, None, None,
            False,  # Instant=False
        ]
        excel = _create_excel_instant([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True


# =========================================================================
# Category Purpose (CtgyPurp) E2E
# =========================================================================

class TestCategoryPurposeE2E:
    def test_sepa_with_category_purpose(self, tmp_path):
        """SEPA mit CtgyPurp.Cd=SALA via Overrides → OK."""
        row = [
            "TC-CP1", "SEPA CtgyPurp", "Category Purpose Test", "OK", "SEPA",
            1500.00, "EUR", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None, "CtgyPurp.Cd=SALA", None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True

    def test_iban_with_category_purpose(self, tmp_path):
        """Domestic-IBAN mit CtgyPurp.Cd=SUPP → OK."""
        row = [
            "TC-CP2", "IBAN CtgyPurp", "Category Purpose Test", "OK", "Domestic-IBAN",
            800.00, "CHF", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None, "CtgyPurp.Cd=SUPP", None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True

    def test_cbpr_with_category_purpose(self, tmp_path):
        """CBPR+ mit CtgyPurp.Cd=SECU → OK."""
        row = [
            "TC-CP3", "CBPR+ CtgyPurp", "Category Purpose Test", "OK", "CBPR+",
            10000.00, "USD", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None, "CdtrAgt.BICFI=BNPAFRPP; CtgyPurp.Cd=SECU", None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True


# =========================================================================
# Ultimate Debtor / Ultimate Creditor E2E
# =========================================================================

class TestUltimatePartiesE2E:
    def test_qr_with_ultimate_debtor(self, tmp_path):
        """QR-Zahlung mit UltmtDbtr (B-Level) via Overrides → OK."""
        row = [
            "TC-UD1", "QR UltmtDbtr", "QR mit Auftraggeber", "OK", "Domestic-QR",
            4500.00, "CHF", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None,
            "UltmtDbtr.Nm=Treuhand Meier GmbH; UltmtDbtr.PstlAdr.TwnNm=Zuerich; UltmtDbtr.PstlAdr.Ctry=CH",
            None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        assert results[0].xsd_valid is True

    def test_sepa_with_ultimate_creditor(self, tmp_path):
        """SEPA mit UltmtCdtr (C-Level) via Overrides → OK."""
        row = [
            "TC-UC1", "SEPA UltmtCdtr", "SEPA mit Endbeguenstigter", "OK", "SEPA",
            8000.00, "EUR", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None,
            "UltmtCdtr.Nm=Endbeguenstigter Verein; UltmtCdtr.PstlAdr.TwnNm=Berlin; UltmtCdtr.PstlAdr.Ctry=DE",
            None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        assert results[0].xsd_valid is True

    def test_sepa_with_both_ultimate_parties(self, tmp_path):
        """SEPA mit UltmtDbtr (B-Level) + UltmtCdtr (C-Level) → OK."""
        row = [
            "TC-UB1", "SEPA Beide Ultimate", "Beide Ultimate Parties", "OK", "SEPA",
            12500.00, "EUR", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None,
            "UltmtDbtr.Nm=Treuhand AG; UltmtDbtr.PstlAdr.Ctry=CH; UltmtCdtr.Nm=Stiftung Alpha; UltmtCdtr.PstlAdr.Ctry=AT",
            None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        assert results[0].xsd_valid is True

    def test_iban_with_ultimate_debtor_name_only(self, tmp_path):
        """Domestic-IBAN mit UltmtDbtr nur Name (Minimal) → OK."""
        row = [
            "TC-UD2", "IBAN UltmtDbtr minimal", "UltmtDbtr nur Name", "OK", "Domestic-IBAN",
            3000.00, "CHF", "Test AG", "CH9300762011623852957", "CRESCHZZ80A",
            None, None, None, None,
            None,
            "UltmtDbtr.Nm=Einfacher Auftraggeber",
            None, None,
        ]
        excel = _create_excel([row], str(tmp_path))
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        assert results[0].xsd_valid is True


# =========================================================================
# Violation Chaining E2E
# =========================================================================

class TestViolationChainingE2E:
    """E2E-Tests fuer kommaseparierte ViolateRule-Ketten."""

    def test_sepa_chained_currency_and_charge_bearer(self, tmp_path):
        """SEPA mit zwei Violations: Waehrung + ChrgBr."""
        excel = _create_excel(
            [_sepa_row("TC-CH1", "NOK", "BR-SEPA-001,BR-SEPA-003")],
            str(tmp_path),
        )
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        failed_ids = {r.rule_id for r in results[0].business_rule_results if not r.passed}
        assert "BR-SEPA-001" in failed_ids
        assert "BR-SEPA-003" in failed_ids

    def test_sepa_chained_three_violations(self, tmp_path):
        """SEPA mit drei Violations: Waehrung + ChrgBr + Name."""
        excel = _create_excel(
            [_sepa_row("TC-CH2", "NOK", "BR-SEPA-001,BR-SEPA-003,BR-SEPA-004")],
            str(tmp_path),
        )
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        failed_ids = {r.rule_id for r in results[0].business_rule_results if not r.passed}
        assert {"BR-SEPA-001", "BR-SEPA-003", "BR-SEPA-004"}.issubset(failed_ids)

    def test_conflict_produces_error_result(self, tmp_path):
        """Konfligierende Violations erzeugen einen Fehler-Testfall."""
        excel = _create_excel(
            [_sepa_row("TC-CH3", "NOK", "BR-SEPA-001,BR-QR-004")],
            str(tmp_path),
        )
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        # Konflikt fuehrt zu Fehler-Ergebnis (overall_pass=False)
        assert results[0].overall_pass is False

    def test_domestic_chained_ref_and_charge_bearer(self, tmp_path):
        """Domestic-QR mit Referenz entfernen + ChrgBr aendern."""
        excel = _create_excel(
            [_qr_row("TC-CH4", "NOK", "BR-QR-002,BR-DOM-001")],
            str(tmp_path),
        )
        results = run(excel, _config(str(tmp_path)), seed_override=42)
        assert results[0].overall_pass is True
        failed_ids = {r.rule_id for r in results[0].business_rule_results if not r.passed}
        assert "BR-QR-002" in failed_ids
        assert "BR-DOM-001" in failed_ids
