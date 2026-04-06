"""Tests fuer Adress-Validierung und -Anreicherung."""

from decimal import Decimal

import pytest

from src.models.testcase import (
    DebtorInfo,
    ExpectedResult,
    PaymentInstruction,
    PaymentType,
    TestCase,
    Transaction,
)
from src.validation.address_validator import (
    COUNTRY_FORMATS,
    AddressValidationIssue,
    convert_unstructured_to_structured,
    enrich_address,
    validate_address,
)
from src.validation.business_rules import validate_all_business_rules


# =========================================================================
# Adress-Validierung (Modul-Level)
# =========================================================================

class TestValidateAddress:
    """Tests fuer validate_address()."""

    def test_valid_ch_address(self):
        addr = {"StrtNm": "Bahnhofstrasse", "BldgNb": "10", "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"}
        result = validate_address(addr)
        assert result.valid is True
        assert len(result.issues) == 0

    def test_valid_de_address(self):
        addr = {"StrtNm": "Berliner Str.", "BldgNb": "5", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"}
        result = validate_address(addr)
        assert result.valid is True

    def test_valid_gb_address(self):
        addr = {"StrtNm": "Baker Street", "BldgNb": "221B", "PstCd": "SW1A 1AA", "TwnNm": "London", "Ctry": "GB"}
        result = validate_address(addr)
        assert result.valid is True

    def test_valid_us_address(self):
        addr = {"StrtNm": "5th Avenue", "BldgNb": "350", "PstCd": "10001", "TwnNm": "New York", "Ctry": "US"}
        result = validate_address(addr)
        assert result.valid is True

    def test_missing_ctry(self):
        addr = {"StrtNm": "Str.", "TwnNm": "Stadt"}
        result = validate_address(addr)
        assert result.valid is False
        assert any(i.field == "Ctry" for i in result.issues)

    def test_missing_town(self):
        addr = {"StrtNm": "Str.", "PstCd": "8001", "Ctry": "CH"}
        result = validate_address(addr)
        assert result.valid is False
        assert any(i.field == "TwnNm" and i.issue_type == "missing" for i in result.issues)

    def test_missing_street(self):
        addr = {"PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"}
        result = validate_address(addr)
        assert result.valid is False
        assert any(i.field == "StrtNm" and i.issue_type == "missing" for i in result.issues)

    def test_invalid_ch_postal_code(self):
        addr = {"StrtNm": "Str.", "PstCd": "123", "TwnNm": "Zuerich", "Ctry": "CH"}
        result = validate_address(addr)
        assert result.valid is False
        assert any(i.field == "PstCd" and i.issue_type == "format" for i in result.issues)

    def test_invalid_de_postal_code(self):
        addr = {"StrtNm": "Str.", "PstCd": "1234", "TwnNm": "Berlin", "Ctry": "DE"}
        result = validate_address(addr)
        assert result.valid is False
        assert any(i.field == "PstCd" and i.issue_type == "format" for i in result.issues)

    def test_invalid_gb_postal_code(self):
        addr = {"StrtNm": "Str.", "PstCd": "12345", "TwnNm": "London", "Ctry": "GB"}
        result = validate_address(addr)
        assert result.valid is False
        assert any(i.field == "PstCd" and i.issue_type == "format" for i in result.issues)

    def test_missing_postal_code_ch(self):
        """CH hat PLZ-Pflicht."""
        addr = {"StrtNm": "Str.", "TwnNm": "Zuerich", "Ctry": "CH"}
        result = validate_address(addr)
        assert result.valid is False
        assert any(i.field == "PstCd" and i.issue_type == "missing" for i in result.issues)

    def test_missing_postal_code_hk_ok(self):
        """Hongkong hat keine PLZ-Pflicht."""
        addr = {"StrtNm": "Queen's Road", "TwnNm": "Hong Kong", "Ctry": "HK"}
        result = validate_address(addr)
        assert result.valid is True

    def test_missing_postal_code_ie_ok(self):
        """Irland: Eircode optional."""
        addr = {"StrtNm": "O'Connell Street", "TwnNm": "Dublin", "Ctry": "IE"}
        result = validate_address(addr)
        assert result.valid is True

    def test_field_length_too_long(self):
        addr = {"StrtNm": "A" * 71, "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"}
        result = validate_address(addr)
        assert result.valid is False
        assert any(i.field == "StrtNm" and i.issue_type == "length" for i in result.issues)

    def test_town_length_too_long(self):
        addr = {"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "A" * 36, "Ctry": "CH"}
        result = validate_address(addr)
        assert result.valid is False
        assert any(i.field == "TwnNm" and i.issue_type == "length" for i in result.issues)

    def test_unknown_country_generic_validation(self):
        """Unbekanntes Land: generische Validierung."""
        addr = {"StrtNm": "Str.", "PstCd": "12345", "TwnNm": "City", "Ctry": "XX"}
        result = validate_address(addr)
        assert result.valid is True
        assert result.country_code == "XX"

    def test_unknown_country_missing_town(self):
        addr = {"StrtNm": "Str.", "Ctry": "XX"}
        result = validate_address(addr)
        assert result.valid is False

    def test_debtor_role_in_messages(self):
        addr = {"StrtNm": "Str.", "PstCd": "123", "TwnNm": "Zuerich", "Ctry": "CH"}
        result = validate_address(addr, role="Debtor")
        assert any("Debtor" in i.message for i in result.issues)

    def test_suggestion_in_postal_code_error(self):
        addr = {"StrtNm": "Str.", "PstCd": "ABC", "TwnNm": "Zuerich", "Ctry": "CH"}
        result = validate_address(addr)
        pstcd_issues = [i for i in result.issues if i.field == "PstCd"]
        assert len(pstcd_issues) > 0
        assert pstcd_issues[0].suggestion is not None
        assert "8001" in pstcd_issues[0].suggestion


# =========================================================================
# PLZ-Formate: parametrisierte Tests
# =========================================================================

class TestPostalCodeFormats:
    """Parametrisierte Tests fuer PLZ-Formate verschiedener Laender."""

    @pytest.mark.parametrize("country,valid_plz", [
        ("CH", "8001"),
        ("CH", "1200"),
        ("DE", "10115"),
        ("DE", "80331"),
        ("AT", "1010"),
        ("FR", "75001"),
        ("IT", "00100"),
        ("NL", "1011 AB"),
        ("NL", "1011AB"),
        ("GB", "SW1A 1AA"),
        ("GB", "EC1A 1BB"),
        ("US", "10001"),
        ("US", "10001-1234"),
        ("CA", "K1A 0B1"),
        ("JP", "100-0001"),
        ("SE", "111 22"),
        ("PL", "00-001"),
        ("BR", "01001-000"),
        ("BR", "01001000"),
    ])
    def test_valid_postal_codes(self, country, valid_plz):
        addr = {"StrtNm": "Str.", "PstCd": valid_plz, "TwnNm": "City", "Ctry": country}
        result = validate_address(addr)
        plz_issues = [i for i in result.issues if i.field == "PstCd" and i.issue_type == "format"]
        assert len(plz_issues) == 0, f"{country} PLZ '{valid_plz}' should be valid: {plz_issues}"

    @pytest.mark.parametrize("country,invalid_plz", [
        ("CH", "123"),
        ("CH", "12345"),
        ("DE", "1234"),
        ("DE", "123456"),
        ("AT", "123"),
        ("FR", "1234"),
        ("IT", "1234"),
        ("GB", "12345"),
        ("US", "1234"),
        ("JP", "1234567"),
        ("PL", "12345"),
    ])
    def test_invalid_postal_codes(self, country, invalid_plz):
        addr = {"StrtNm": "Str.", "PstCd": invalid_plz, "TwnNm": "City", "Ctry": country}
        result = validate_address(addr)
        plz_issues = [i for i in result.issues if i.field == "PstCd" and i.issue_type == "format"]
        assert len(plz_issues) > 0, f"{country} PLZ '{invalid_plz}' should be invalid"


# =========================================================================
# Adress-Anreicherung
# =========================================================================

class TestEnrichAddress:
    """Tests fuer enrich_address()."""

    def test_gb_postcode_normalization(self):
        addr = {"StrtNm": "Baker St.", "PstCd": "SW1A1AA", "TwnNm": "London", "Ctry": "GB"}
        enriched, hints = enrich_address(addr)
        assert enriched["PstCd"] == "SW1A 1AA"
        assert len(hints) > 0

    def test_se_postcode_normalization(self):
        addr = {"StrtNm": "Str.", "PstCd": "11122", "TwnNm": "Stockholm", "Ctry": "SE"}
        enriched, hints = enrich_address(addr)
        assert enriched["PstCd"] == "111 22"

    def test_nl_postcode_normalization(self):
        addr = {"StrtNm": "Str.", "PstCd": "1011ab", "TwnNm": "Amsterdam", "Ctry": "NL"}
        enriched, hints = enrich_address(addr)
        assert enriched["PstCd"] == "1011 AB"

    def test_ca_postcode_normalization(self):
        addr = {"StrtNm": "Str.", "PstCd": "k1a0b1", "TwnNm": "Ottawa", "Ctry": "CA"}
        enriched, hints = enrich_address(addr)
        assert enriched["PstCd"] == "K1A 0B1"

    def test_lv_postcode_prefix(self):
        addr = {"StrtNm": "Str.", "PstCd": "1001", "TwnNm": "Riga", "Ctry": "LV"}
        enriched, hints = enrich_address(addr)
        assert enriched["PstCd"] == "LV-1001"

    def test_lt_postcode_prefix(self):
        addr = {"StrtNm": "Str.", "PstCd": "01001", "TwnNm": "Vilnius", "Ctry": "LT"}
        enriched, hints = enrich_address(addr)
        assert enriched["PstCd"] == "LT-01001"

    def test_already_correct_no_change(self):
        addr = {"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"}
        enriched, hints = enrich_address(addr)
        assert enriched["PstCd"] == "8001"
        assert len(hints) == 0

    def test_unknown_country_no_enrichment(self):
        addr = {"StrtNm": "Str.", "PstCd": "12345", "TwnNm": "City", "Ctry": "XX"}
        enriched, hints = enrich_address(addr)
        assert enriched["PstCd"] == "12345"
        assert len(hints) == 0


# =========================================================================
# Country-Format-Datenbank
# =========================================================================

class TestCountryFormats:
    """Tests fuer die Vollstaendigkeit der Laenderdatenbank."""

    def test_key_countries_present(self):
        """Alle wichtigen Zahlungsverkehrs-Laender sind vorhanden."""
        required = ["CH", "LI", "DE", "AT", "FR", "IT", "ES", "GB", "US", "JP"]
        for cc in required:
            assert cc in COUNTRY_FORMATS, f"Land {cc} fehlt in COUNTRY_FORMATS"

    def test_all_sepa_countries_reasonable(self):
        """SEPA-Kernlaender haben PLZ-Pflicht (ausser IE)."""
        sepa_core = ["CH", "DE", "AT", "FR", "IT", "ES", "NL", "BE", "LU"]
        for cc in sepa_core:
            fmt = COUNTRY_FORMATS[cc]
            assert fmt.requires_postal_code is True, f"{cc} sollte PLZ-Pflicht haben"

    def test_hk_no_postal_code_required(self):
        fmt = COUNTRY_FORMATS["HK"]
        assert fmt.requires_postal_code is False


# =========================================================================
# Integration: Business Rules mit Adress-Validierung
# =========================================================================

def _make_testcase(**kwargs):
    defaults = {
        "testcase_id": "TC-ADDR",
        "titel": "Address Test",
        "ziel": "Test",
        "expected_result": ExpectedResult.OK,
        "payment_type": PaymentType.DOMESTIC_IBAN,
        "amount": Decimal("100.00"),
        "currency": "CHF",
        "debtor": DebtorInfo(name="Test AG", iban="CH9300762011623852957"),
        "overrides": {},
    }
    defaults.update(kwargs)
    return TestCase(**defaults)


def _make_instruction(tc, transactions):
    return PaymentInstruction(
        msg_id="MSG-test123",
        pmt_inf_id="PMT-test123",
        cre_dt_tm="2026-03-20T10:00:00",
        reqd_exctn_dt="2026-03-23",
        debtor=tc.debtor,
        service_level=None,
        charge_bearer=None,
        transactions=transactions,
    )


class TestAddressBusinessRules:
    """Integration: BR-ADDR-010/011/012 in validate_all_business_rules."""

    def test_valid_address_no_addr_010_failure(self):
        """Gueltige CH-Adresse: keine BR-ADDR-010 Fehler."""
        tc = _make_testcase()
        tx = Transaction(
            end_to_end_id="E2E-test",
            amount=Decimal("100.00"),
            currency="CHF",
            creditor_name="Creditor AG",
            creditor_iban="CH9300762011623852957",
            creditor_address={"StrtNm": "Bahnhofstr.", "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"},
        )
        instr = _make_instruction(tc, [tx])
        results = validate_all_business_rules(instr, tc)
        addr_010 = [r for r in results if r.rule_id == "BR-ADDR-010"]
        assert all(r.passed for r in addr_010) or len(addr_010) == 0

    def test_invalid_postal_code_triggers_addr_010(self):
        """Ungueltige PLZ loest BR-ADDR-010 aus."""
        tc = _make_testcase()
        tx = Transaction(
            end_to_end_id="E2E-test",
            amount=Decimal("100.00"),
            currency="CHF",
            creditor_name="Creditor AG",
            creditor_iban="CH9300762011623852957",
            creditor_address={"StrtNm": "Str.", "PstCd": "123", "TwnNm": "Zuerich", "Ctry": "CH"},
        )
        instr = _make_instruction(tc, [tx])
        results = validate_all_business_rules(instr, tc)
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-ADDR-010" in failed_ids

    def test_too_long_street_triggers_addr_011(self):
        """Zu langer Strassenname loest BR-ADDR-011 aus."""
        tc = _make_testcase()
        tx = Transaction(
            end_to_end_id="E2E-test",
            amount=Decimal("100.00"),
            currency="CHF",
            creditor_name="Creditor AG",
            creditor_iban="CH9300762011623852957",
            creditor_address={"StrtNm": "A" * 71, "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"},
        )
        instr = _make_instruction(tc, [tx])
        results = validate_all_business_rules(instr, tc)
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-ADDR-011" in failed_ids

    def test_missing_postal_code_triggers_addr_012(self):
        """Fehlende PLZ bei CH loest BR-ADDR-012 aus."""
        tc = _make_testcase()
        tx = Transaction(
            end_to_end_id="E2E-test",
            amount=Decimal("100.00"),
            currency="CHF",
            creditor_name="Creditor AG",
            creditor_iban="CH9300762011623852957",
            creditor_address={"StrtNm": "Str.", "TwnNm": "Zuerich", "Ctry": "CH"},
        )
        instr = _make_instruction(tc, [tx])
        results = validate_all_business_rules(instr, tc)
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-ADDR-012" in failed_ids

    def test_debtor_invalid_postal_code_triggers_addr_010(self):
        """Debtor mit ungueltiger PLZ loest BR-ADDR-010 aus."""
        debtor = DebtorInfo(
            name="Test AG",
            iban="CH9300762011623852957",
            street="Teststr.",
            postal_code="123",
            town="Zuerich",
            country="CH",
        )
        tc = _make_testcase(debtor=debtor)
        tx = Transaction(
            end_to_end_id="E2E-test",
            amount=Decimal("100.00"),
            currency="CHF",
            creditor_name="Creditor AG",
            creditor_iban="CH9300762011623852957",
            creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"},
        )
        instr = _make_instruction(tc, [tx])
        results = validate_all_business_rules(instr, tc)
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-ADDR-010" in failed_ids

    def test_hk_address_without_postal_code_ok(self):
        """Hongkong-Adresse ohne PLZ: keine BR-ADDR-012 Fehler."""
        tc = _make_testcase(payment_type=PaymentType.CBPR_PLUS, currency="USD")
        tx = Transaction(
            end_to_end_id="E2E-test",
            amount=Decimal("100.00"),
            currency="USD",
            creditor_name="Creditor Ltd",
            creditor_iban="GB29NWBK60161331926819",
            creditor_bic="BARCGB22XXX",
            creditor_address={"StrtNm": "Queen's Road", "TwnNm": "Hong Kong", "Ctry": "HK"},
            uetr="550e8400-e29b-41d4-a716-446655440000",
        )
        instr = _make_instruction(tc, [tx])
        instr = instr.model_copy(update={"charge_bearer": "SHAR"})
        results = validate_all_business_rules(instr, tc)
        addr_012 = [r for r in results if r.rule_id == "BR-ADDR-012" and not r.passed]
        assert len(addr_012) == 0

    def test_german_error_messages(self):
        """Fehlermeldungen sind auf Deutsch."""
        tc = _make_testcase()
        tx = Transaction(
            end_to_end_id="E2E-test",
            amount=Decimal("100.00"),
            currency="CHF",
            creditor_name="Creditor AG",
            creditor_iban="CH9300762011623852957",
            creditor_address={"StrtNm": "Str.", "PstCd": "123", "TwnNm": "Zuerich", "Ctry": "CH"},
        )
        instr = _make_instruction(tc, [tx])
        results = validate_all_business_rules(instr, tc)
        addr_010 = [r for r in results if r.rule_id == "BR-ADDR-010" and not r.passed]
        assert len(addr_010) > 0
        # Fehlermeldung sollte deutsche Begriffe enthalten
        assert any("PLZ" in r.details or "Format" in r.details for r in addr_010)


# =========================================================================
# Auto-Konversion: Unstrukturiert → Strukturiert
# =========================================================================


class TestConvertUnstructuredToStructured:
    """Tests fuer die Auto-Konversion von AdrLine zu strukturierten Feldern."""

    def test_two_line_ch_address(self):
        """Schweizer 2-Zeilen-Adresse wird korrekt aufgespalten."""
        addr = {"AdrLine": "Bahnhofstrasse 42|8001 Zuerich", "Ctry": "CH"}
        result, success = convert_unstructured_to_structured(addr)
        assert success is True
        assert result["StrtNm"] == "Bahnhofstrasse"
        assert result["BldgNb"] == "42"
        assert result["PstCd"] == "8001"
        assert result["TwnNm"] == "Zuerich"
        assert result["Ctry"] == "CH"
        assert "AdrLine" not in result

    def test_two_line_de_address(self):
        """Deutsche 2-Zeilen-Adresse wird korrekt aufgespalten."""
        addr = {"AdrLine": "Berliner Str. 7|10115 Berlin", "Ctry": "DE"}
        result, success = convert_unstructured_to_structured(addr)
        assert success is True
        assert result["StrtNm"] == "Berliner Str."
        assert result["BldgNb"] == "7"
        assert result["PstCd"] == "10115"
        assert result["TwnNm"] == "Berlin"

    def test_no_adrline_no_conversion(self):
        """Ohne AdrLine findet keine Konversion statt."""
        addr = {"StrtNm": "Test", "Ctry": "CH"}
        result, success = convert_unstructured_to_structured(addr)
        assert success is False
        assert result == addr

    def test_preserves_existing_structured_fields(self):
        """Bereits vorhandene strukturierte Felder werden beibehalten."""
        addr = {
            "AdrLine": "New Street 5|3000 Bern",
            "Ctry": "CH",
            "TwnNm": "Existing Town",
        }
        result, success = convert_unstructured_to_structured(addr)
        assert success is True
        assert result["TwnNm"] == "Existing Town"  # Nicht ueberschrieben
        assert result["StrtNm"] == "New Street"

    def test_empty_adrline(self):
        """Leerer AdrLine wird nicht konvertiert."""
        addr = {"AdrLine": "", "Ctry": "CH"}
        result, success = convert_unstructured_to_structured(addr)
        assert success is False

    def test_street_without_building_number(self):
        """Strasse ohne Hausnummer wird als reiner StrtNm behandelt."""
        addr = {"AdrLine": "Rathaus|8001 Zuerich", "Ctry": "CH"}
        result, success = convert_unstructured_to_structured(addr)
        assert success is True
        assert result["StrtNm"] == "Rathaus"
        assert "BldgNb" not in result
