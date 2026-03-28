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
        xsd_path="schemas/pain.001.001.09.ch.03.xsd",
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
