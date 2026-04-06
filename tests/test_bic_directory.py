"""Tests für die BIC-Verzeichnis-Validierung (BR-BIC-001)."""

import json
import os
import tempfile

import pytest

from src.validation.bic_directory import (
    BICDirectory,
    BICEntry,
    load_bic_directory,
    get_bic_directory,
    reset_bic_directory,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Setzt die Singleton-Instanz vor und nach jedem Test zurück."""
    reset_bic_directory()
    yield
    reset_bic_directory()


# ---------------------------------------------------------------------------
# BICDirectory — Grundfunktionalität
# ---------------------------------------------------------------------------

class TestBICDirectoryBasics:
    def test_normalize_bic_8_chars(self):
        assert BICDirectory.normalize_bic("UBSWCHZH") == "UBSWCHZH"

    def test_normalize_bic_11_chars_to_8(self):
        assert BICDirectory.normalize_bic("UBSWCHZH80A") == "UBSWCHZH"

    def test_normalize_bic_lowercase(self):
        assert BICDirectory.normalize_bic("ubswchzh") == "UBSWCHZH"

    def test_normalize_bic_with_spaces(self):
        assert BICDirectory.normalize_bic("  UBSWCHZH  ") == "UBSWCHZH"

    def test_empty_directory_size(self):
        d = BICDirectory()
        assert d.size == 0

    def test_lookup_nonexistent(self):
        d = BICDirectory()
        assert d.lookup("UBSWCHZH") is None

    def test_exists_nonexistent(self):
        d = BICDirectory()
        assert d.exists("UBSWCHZH") is False


# ---------------------------------------------------------------------------
# CSV-Loading
# ---------------------------------------------------------------------------

class TestBICDirectoryCSV:
    def _write_csv(self, tmp_dir, filename, content):
        path = os.path.join(tmp_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_load_basic_csv(self, tmp_path):
        csv_content = "BIC8,InstitutionName,CountryCode,Status\n" \
                      "UBSWCHZH,UBS Switzerland AG,CH,ACTIVE\n" \
                      "ZKBKCHZZ,Zürcher Kantonalbank,CH,ACTIVE\n" \
                      "COBADEFF,Commerzbank AG,DE,ACTIVE\n"
        path = self._write_csv(str(tmp_path), "bic.csv", csv_content)

        d = BICDirectory()
        count = d.load(path)

        assert count == 3
        assert d.size == 3
        assert d.exists("UBSWCHZH")
        assert d.exists("ZKBKCHZZ")
        assert d.exists("COBADEFF")

    def test_load_csv_with_11_char_bics(self, tmp_path):
        csv_content = "BIC,InstitutionName,CountryCode\n" \
                      "UBSWCHZH80A,UBS Zurich,CH\n"
        path = self._write_csv(str(tmp_path), "bic.csv", csv_content)

        d = BICDirectory()
        d.load(path)

        assert d.exists("UBSWCHZH")
        assert d.exists("UBSWCHZH80A")  # 11-stelliger BIC wird normalisiert

    def test_load_csv_inactive_entries(self, tmp_path):
        csv_content = "BIC8,InstitutionName,CountryCode,Status\n" \
                      "UBSWCHZH,UBS Switzerland AG,CH,ACTIVE\n" \
                      "OLDBANKX,Old Bank,CH,INACTIVE\n"
        path = self._write_csv(str(tmp_path), "bic.csv", csv_content)

        d = BICDirectory()
        d.load(path)

        assert d.is_active("UBSWCHZH") is True
        assert d.exists("OLDBANKX") is True
        assert d.is_active("OLDBANKX") is False

    def test_load_csv_semicolon_delimiter(self, tmp_path):
        csv_content = "BIC8;InstitutionName;CountryCode\n" \
                      "UBSWCHZH;UBS Switzerland AG;CH\n"
        path = self._write_csv(str(tmp_path), "bic.csv", csv_content)

        d = BICDirectory()
        d.load(path)

        assert d.exists("UBSWCHZH")

    def test_load_csv_missing_bic_column_raises(self, tmp_path):
        csv_content = "Name,Country\n" \
                      "UBS,CH\n"
        path = self._write_csv(str(tmp_path), "bic.csv", csv_content)

        d = BICDirectory()
        with pytest.raises(ValueError, match="BIC-Spalte nicht gefunden"):
            d.load(path)

    def test_load_csv_skip_empty_bics(self, tmp_path):
        csv_content = "BIC8,InstitutionName\n" \
                      "UBSWCHZH,UBS\n" \
                      ",Empty\n" \
                      "ZKBKCHZZ,ZKB\n"
        path = self._write_csv(str(tmp_path), "bic.csv", csv_content)

        d = BICDirectory()
        count = d.load(path)

        assert count == 2


# ---------------------------------------------------------------------------
# JSON-Loading
# ---------------------------------------------------------------------------

class TestBICDirectoryJSON:
    def test_load_basic_json(self, tmp_path):
        data = [
            {"bic8": "UBSWCHZH", "institution_name": "UBS", "country_code": "CH"},
            {"bic8": "ZKBKCHZZ", "institution_name": "ZKB", "country_code": "CH"},
        ]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        d = BICDirectory()
        count = d.load(path)

        assert count == 2
        assert d.exists("UBSWCHZH")
        assert d.exists("ZKBKCHZZ")

    def test_load_json_with_status(self, tmp_path):
        data = [
            {"BIC": "UBSWCHZH", "status": "ACTIVE"},
            {"BIC": "OLDBANKX", "status": "INACTIVE"},
        ]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        d = BICDirectory()
        d.load(path)

        assert d.is_active("UBSWCHZH") is True
        assert d.is_active("OLDBANKX") is False

    def test_load_json_bool_status(self, tmp_path):
        data = [
            {"bic8": "UBSWCHZH", "is_active": True},
            {"bic8": "OLDBANKX", "is_active": False},
        ]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        d = BICDirectory()
        d.load(path)

        assert d.is_active("UBSWCHZH") is True
        assert d.is_active("OLDBANKX") is False

    def test_load_json_not_list_raises(self, tmp_path):
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump({"bic": "UBSWCHZH"}, f)

        d = BICDirectory()
        with pytest.raises(ValueError, match="Liste von Objekten"):
            d.load(path)


# ---------------------------------------------------------------------------
# validate_bic
# ---------------------------------------------------------------------------

class TestValidateBIC:
    def test_valid_bic(self, tmp_path):
        data = [{"bic8": "UBSWCHZH"}]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        d = BICDirectory()
        d.load(path)

        valid, error = d.validate_bic("UBSWCHZH")
        assert valid is True
        assert error is None

    def test_valid_bic_11_chars(self, tmp_path):
        data = [{"bic8": "UBSWCHZH"}]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        d = BICDirectory()
        d.load(path)

        valid, error = d.validate_bic("UBSWCHZH80A")
        assert valid is True

    def test_unknown_bic(self, tmp_path):
        data = [{"bic8": "UBSWCHZH"}]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        d = BICDirectory()
        d.load(path)

        valid, error = d.validate_bic("XXXXXXXZ")
        assert valid is False
        assert "nicht im SWIFT BIC Directory" in error

    def test_inactive_bic(self, tmp_path):
        data = [{"bic8": "OLDBANKX", "status": "INACTIVE"}]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        d = BICDirectory()
        d.load(path)

        valid, error = d.validate_bic("OLDBANKX")
        assert valid is False
        assert "inaktiv" in error


# ---------------------------------------------------------------------------
# File handling edge cases
# ---------------------------------------------------------------------------

class TestBICDirectoryFileHandling:
    def test_file_not_found(self):
        d = BICDirectory()
        with pytest.raises(FileNotFoundError, match="nicht gefunden"):
            d.load("/nonexistent/path/bic.csv")

    def test_unknown_extension(self, tmp_path):
        path = os.path.join(str(tmp_path), "bic.xml")
        with open(path, "w") as f:
            f.write("<bic/>")

        d = BICDirectory()
        with pytest.raises(ValueError, match="Unbekanntes Format"):
            d.load(path)

    def test_lookup_details(self, tmp_path):
        data = [{"bic8": "UBSWCHZH", "institution_name": "UBS", "country_code": "CH"}]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        d = BICDirectory()
        d.load(path)

        entry = d.lookup("UBSWCHZH")
        assert entry is not None
        assert entry.bic8 == "UBSWCHZH"
        assert entry.institution_name == "UBS"
        assert entry.country_code == "CH"
        assert entry.is_active is True


# ---------------------------------------------------------------------------
# Singleton / load_bic_directory
# ---------------------------------------------------------------------------

class TestBICDirectorySingleton:
    def test_get_bic_directory_before_load(self):
        assert get_bic_directory() is None

    def test_load_and_get(self, tmp_path):
        data = [{"bic8": "UBSWCHZH"}]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        d = load_bic_directory(path)
        assert d is not None
        assert d.size == 1
        assert get_bic_directory() is d

    def test_reset_clears_singleton(self, tmp_path):
        data = [{"bic8": "UBSWCHZH"}]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        load_bic_directory(path)
        assert get_bic_directory() is not None

        reset_bic_directory()
        assert get_bic_directory() is None


# ---------------------------------------------------------------------------
# Integration: BR-BIC-001 in business_rules
# ---------------------------------------------------------------------------

class TestBICBusinessRule:
    """Tests dass BR-BIC-001 korrekt in die Business Rules integriert ist."""

    def test_no_bic_directory_no_rule(self):
        """Ohne BIC-Verzeichnis wird BR-BIC-001 nicht geprüft."""
        from src.validation.business_rules import validate_general_rules
        from src.models.testcase import (
            DebtorInfo, PaymentInstruction, TestCase, Transaction,
            PaymentType, ExpectedResult,
        )
        from decimal import Decimal

        instruction = PaymentInstruction(
            msg_id="MSG001",
            pmt_inf_id="PMT001",
            cre_dt_tm="2026-04-06T10:00:00",
            reqd_exctn_dt="2026-04-07",
            debtor=DebtorInfo(
                name="Test AG", iban="CH9300762011623852957",
                bic="UBSWCHZH", country="CH",
            ),
            transactions=[
                Transaction(
                    end_to_end_id="E2E001",
                    amount=Decimal("100.00"),
                    currency="CHF",
                    creditor_name="Creditor AG",
                    creditor_iban="CH9300762011623852957",
                    creditor_bic="ZKBKCHZZ",
                    creditor_address={"StrtNm": "Hauptstrasse 1", "TwnNm": "Zürich", "Ctry": "CH"},
                ),
            ],
        )
        testcase = TestCase(
            testcase_id="TC001",
            titel="Test",
            ziel="Test",
            expected_result=ExpectedResult.OK,
            payment_type=PaymentType.DOMESTIC_IBAN,
            debtor=instruction.debtor,
        )

        results = validate_general_rules(instruction, testcase)
        bic_001 = [r for r in results if r.rule_id == "BR-BIC-001"]
        assert len(bic_001) == 0

    def test_bic_directory_validates(self, tmp_path):
        """Mit BIC-Verzeichnis wird BR-BIC-001 geprüft."""
        from src.validation.business_rules import validate_general_rules
        from src.models.testcase import (
            DebtorInfo, PaymentInstruction, TestCase, Transaction,
            PaymentType, ExpectedResult,
        )
        from decimal import Decimal

        # BIC-Verzeichnis mit UBSWCHZH laden
        data = [
            {"bic8": "UBSWCHZH", "institution_name": "UBS", "country_code": "CH"},
        ]
        path = os.path.join(str(tmp_path), "bic.json")
        with open(path, "w") as f:
            json.dump(data, f)

        load_bic_directory(path)

        instruction = PaymentInstruction(
            msg_id="MSG001",
            pmt_inf_id="PMT001",
            cre_dt_tm="2026-04-06T10:00:00",
            reqd_exctn_dt="2026-04-07",
            debtor=DebtorInfo(
                name="Test AG", iban="CH9300762011623852957",
                bic="UBSWCHZH", country="CH",
            ),
            transactions=[
                Transaction(
                    end_to_end_id="E2E001",
                    amount=Decimal("100.00"),
                    currency="CHF",
                    creditor_name="Creditor AG",
                    creditor_iban="CH9300762011623852957",
                    creditor_bic="ZKBKCHZZ",
                    creditor_address={"StrtNm": "Hauptstrasse 1", "TwnNm": "Zürich", "Ctry": "CH"},
                ),
            ],
        )
        testcase = TestCase(
            testcase_id="TC001",
            titel="Test",
            ziel="Test",
            expected_result=ExpectedResult.OK,
            payment_type=PaymentType.DOMESTIC_IBAN,
            debtor=instruction.debtor,
        )

        results = validate_general_rules(instruction, testcase)
        bic_001 = [r for r in results if r.rule_id == "BR-BIC-001"]

        # UBSWCHZH ist im Verzeichnis → pass
        # ZKBKCHZZ ist NICHT im Verzeichnis → fail
        assert len(bic_001) == 2
        ubsw_result = [r for r in bic_001 if "UBSWCHZH" in (r.details or "")
                       or (r.passed and "Debtor" not in (r.details or ""))]
        zkbk_result = [r for r in bic_001 if not r.passed]
        assert len(zkbk_result) == 1
        assert "ZKBKCHZZ" in zkbk_result[0].details
