"""Tests für Business Rules."""

from decimal import Decimal

import pytest

from src.mapping.field_mapper import (
    CHARGE_BEARER_ALIASES,
    _normalize_charge_bearer,
    validate_and_map_overrides,
)
from src.models.testcase import (
    DebtorInfo,
    ExpectedResult,
    PaymentInstruction,
    PaymentType,
    Standard,
    TestCase,
    Transaction,
)
from src.validation.business_rules import validate_all_business_rules


def _make_testcase(**kwargs):
    defaults = {
        "testcase_id": "TC-TEST",
        "titel": "Test",
        "ziel": "Test",
        "expected_result": ExpectedResult.OK,
        "payment_type": PaymentType.SEPA,
        "amount": Decimal("100.00"),
        "currency": "EUR",
        "debtor": DebtorInfo(name="Test AG", iban="CH9300762011623852957"),
        "overrides": {},
    }
    defaults.update(kwargs)
    return TestCase(**defaults)


def _make_instruction(testcase, transactions):
    return PaymentInstruction(
        msg_id="MSG-test123",
        pmt_inf_id="PMT-test123",
        cre_dt_tm="2026-03-20T10:00:00",
        reqd_exctn_dt="2026-03-23",
        debtor=testcase.debtor,
        service_level="SEPA" if testcase.payment_type == PaymentType.SEPA else None,
        charge_bearer="SLEV" if testcase.payment_type == PaymentType.SEPA else None,
        transactions=transactions,
    )


def test_sepa_valid():
    tc = _make_testcase(currency="EUR", payment_type=PaymentType.SEPA)
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Berliner Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    failed = [r for r in results if not r.passed]
    assert len(failed) == 0, f"Failed rules: {[r.rule_id for r in failed]}"


def test_sepa_wrong_currency():
    tc = _make_testcase(currency="CHF", payment_type=PaymentType.SEPA)
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-SEPA-001" in failed_ids


def test_domestic_iban_no_charge_bearer_ok():
    """BR-DOM-001: Domestic-IBAN ohne ChrgBr ist OK."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_IBAN,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zürich", "Ctry": "CH"},
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None, "charge_bearer": None})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-DOM-001" not in failed_ids


def test_domestic_iban_with_charge_bearer_fails():
    """BR-DOM-001: Domestic-IBAN mit ChrgBr schlaegt fehl."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_IBAN,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zürich", "Ctry": "CH"},
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None, "charge_bearer": "SHAR"})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-DOM-001" in failed_ids


def test_domestic_qr_with_charge_bearer_fails():
    """BR-DOM-001: Domestic-QR mit ChrgBr schlaegt fehl."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_QR,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH4431999123000889012",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zürich", "Ctry": "CH"},
        remittance_info={"type": "QRR", "value": "000000000000000000000000000"},
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None, "charge_bearer": "DEBT"})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-DOM-001" in failed_ids


def test_cbpr_charge_bearer_debt_ok():
    """BR-CBPR-003: CBPR+ mit ChrgBr=DEBT ist OK."""
    tc = _make_testcase(
        currency="USD",
        payment_type=PaymentType.CBPR_PLUS,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="USD",
        creditor_name="Creditor Ltd",
        creditor_iban="GB29NWBK60161331926819",
        creditor_bic="BARCGB22XXX",
        creditor_address={"StrtNm": "Str.", "PstCd": "SW1A 1AA", "TwnNm": "London", "Ctry": "GB"},
        uetr="550e8400-e29b-41d4-a716-446655440000",
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None, "charge_bearer": "DEBT"})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-CBPR-003" not in failed_ids


def test_cbpr_charge_bearer_cred_ok():
    """BR-CBPR-003: CBPR+ mit ChrgBr=CRED ist OK."""
    tc = _make_testcase(
        currency="USD",
        payment_type=PaymentType.CBPR_PLUS,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="USD",
        creditor_name="Creditor Ltd",
        creditor_iban="GB29NWBK60161331926819",
        creditor_bic="BARCGB22XXX",
        creditor_address={"StrtNm": "Str.", "PstCd": "SW1A 1AA", "TwnNm": "London", "Ctry": "GB"},
        uetr="550e8400-e29b-41d4-a716-446655440000",
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None, "charge_bearer": "CRED"})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-CBPR-003" not in failed_ids


def test_cbpr_charge_bearer_slev_fails():
    """BR-CBPR-003: CBPR+ mit ChrgBr=SLEV schlaegt fehl."""
    tc = _make_testcase(
        currency="USD",
        payment_type=PaymentType.CBPR_PLUS,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="USD",
        creditor_name="Creditor Ltd",
        creditor_iban="GB29NWBK60161331926819",
        creditor_bic="BARCGB22XXX",
        creditor_address={"StrtNm": "Str.", "PstCd": "SW1A 1AA", "TwnNm": "London", "Ctry": "GB"},
        uetr="550e8400-e29b-41d4-a716-446655440000",
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None, "charge_bearer": "SLEV"})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-CBPR-003" in failed_ids


def test_cbpr_missing_agent():
    tc = _make_testcase(
        currency="USD",
        payment_type=PaymentType.CBPR_PLUS,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="USD",
        creditor_name="Creditor Ltd",
        creditor_iban="GB29NWBK60161331926819",
        creditor_bic=None,
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-CBPR-005" in failed_ids


# =========================================================================
# ChrgBr Alias-Normalisierung
# =========================================================================

class TestChargeBearerAliases:
    @pytest.mark.parametrize("alias,expected", [
        ("OUR", "DEBT"),
        ("BEN", "CRED"),
        ("SHA", "SHAR"),
        ("our", "DEBT"),  # Case-insensitive
        ("Our", "DEBT"),
    ])
    def test_alias_normalization(self, alias, expected):
        assert _normalize_charge_bearer(alias) == expected

    @pytest.mark.parametrize("raw_value", ["DEBT", "CRED", "SHAR", "SLEV"])
    def test_iso_values_unchanged(self, raw_value):
        assert _normalize_charge_bearer(raw_value) == raw_value

    def test_unknown_value_unchanged(self):
        assert _normalize_charge_bearer("UNKNOWN") == "UNKNOWN"

    def test_override_mapping_normalizes_chrgbr(self):
        """ChrgBr=OUR in overrides wird zu DEBT normalisiert."""
        mapped, _, errors = validate_and_map_overrides({"ChrgBr": "OUR"})
        assert len(errors) == 0
        assert mapped["ChrgBr"]["value"] == "DEBT"

    def test_override_mapping_keeps_iso_value(self):
        """ChrgBr=SHAR in overrides bleibt SHAR."""
        mapped, _, errors = validate_and_map_overrides({"ChrgBr": "SHAR"})
        assert len(errors) == 0
        assert mapped["ChrgBr"]["value"] == "SHAR"

    def test_non_chrgbr_not_normalized(self):
        """Andere Override-Keys werden nicht normalisiert."""
        mapped, _, errors = validate_and_map_overrides({"SvcLvl.Cd": "SEPA"})
        assert len(errors) == 0
        assert mapped["SvcLvl.Cd"]["value"] == "SEPA"


class TestLeiMapping:
    def test_creditor_lei_mapping(self):
        """Cdtr.Id.OrgId.LEI wird korrekt gemappt."""
        mapped, _, errors = validate_and_map_overrides({"Cdtr.Id.OrgId.LEI": "5493001KJTIIGC8Y1R12"})
        assert len(errors) == 0
        assert mapped["Cdtr.Id.OrgId.LEI"]["xpath"] == "Cdtr/Id/OrgId/LEI"
        assert mapped["Cdtr.Id.OrgId.LEI"]["level"] == "C"
        assert mapped["Cdtr.Id.OrgId.LEI"]["value"] == "5493001KJTIIGC8Y1R12"

    def test_debtor_lei_mapping(self):
        """Dbtr.Id.OrgId.LEI wird korrekt gemappt."""
        mapped, _, errors = validate_and_map_overrides({"Dbtr.Id.OrgId.LEI": "5493001KJTIIGC8Y1R12"})
        assert len(errors) == 0
        assert mapped["Dbtr.Id.OrgId.LEI"]["xpath"] == "Dbtr/Id/OrgId/LEI"
        assert mapped["Dbtr.Id.OrgId.LEI"]["level"] == "B"


# =========================================================================
# XML-Tag Auto-Resolution (Weitere Testdaten)
# =========================================================================

class TestXmlTagAutoResolution:
    """Tests für automatische Auflösung von XML-Tag-Namen zu FIELD_MAPPINGS-Keys."""

    def test_unique_tag_resolved(self):
        """Eindeutiger XML-Tag (InstdAmt) wird automatisch aufgelöst."""
        mapped, _, errors = validate_and_map_overrides({"InstdAmt": "500.00"})
        assert len(errors) == 0
        assert "Amt.InstdAmt" in mapped
        assert mapped["Amt.InstdAmt"]["value"] == "500.00"
        assert mapped["Amt.InstdAmt"]["xpath"] == "Amt/InstdAmt"

    def test_unique_tag_ustrd(self):
        """Eindeutiger XML-Tag (Ustrd) wird zu RmtInf.Ustrd aufgelöst."""
        mapped, _, errors = validate_and_map_overrides({"Ustrd": "Test-Zahlung"})
        assert len(errors) == 0
        assert "RmtInf.Ustrd" in mapped
        assert mapped["RmtInf.Ustrd"]["value"] == "Test-Zahlung"

    def test_unique_tag_endtoendid(self):
        """Eindeutiger XML-Tag (EndToEndId) wird aufgelöst."""
        mapped, _, errors = validate_and_map_overrides({"EndToEndId": "E2E-001"})
        assert len(errors) == 0
        assert "PmtId.EndToEndId" in mapped

    def test_unique_tag_ref(self):
        """Eindeutiger XML-Tag (Ref) wird zu RmtInf.Strd.CdtrRefInf.Ref aufgelöst."""
        mapped, _, errors = validate_and_map_overrides({"Ref": "RF18000000000539007547034"})
        assert len(errors) == 0
        assert "RmtInf.Strd.CdtrRefInf.Ref" in mapped

    def test_ambiguous_tag_dt_skipped_with_warning(self):
        """Mehrdeutiger XML-Tag (Dt) wird übersprungen mit Warnung (ReqdExctnDt vs TaxRmt.Dt)."""
        mapped, _, errors = validate_and_map_overrides({"Dt": "2025-01-15"})
        assert len(mapped) == 0
        assert len(errors) == 1
        assert errors[0].is_warning

    def test_ambiguous_tag_nm_skipped_with_warning(self):
        """Mehrdeutiger XML-Tag (Nm) wird übersprungen mit Warnung."""
        mapped, _, errors = validate_and_map_overrides({"Nm": "Test AG"})
        assert "Nm" not in mapped
        # Kein FIELD_MAPPINGS-Key sollte gemappt worden sein
        assert len(mapped) == 0
        assert len(errors) == 1
        assert errors[0].is_warning is True
        assert "mehrdeutig" in errors[0].message
        assert "Nm" in errors[0].message

    def test_ambiguous_tag_iban_skipped_with_warning(self):
        """Mehrdeutiger XML-Tag (IBAN) wird übersprungen."""
        mapped, _, errors = validate_and_map_overrides({"IBAN": "CH9300762011623852957"})
        assert len(mapped) == 0
        assert len(errors) == 1
        assert errors[0].is_warning is True
        assert "CdtrAcct.IBAN" in errors[0].message
        assert "DbtrAcct.IBAN" in errors[0].message

    def test_ambiguous_tag_cd_skipped_with_warning(self):
        """Mehrdeutiger XML-Tag (Cd) wird übersprungen."""
        mapped, _, errors = validate_and_map_overrides({"Cd": "SEPA"})
        assert len(mapped) == 0
        assert len(errors) == 1
        assert errors[0].is_warning is True

    def test_ambiguous_tag_bicfi_skipped_with_warning(self):
        """Mehrdeutiger XML-Tag (BICFI) wird übersprungen."""
        mapped, _, errors = validate_and_map_overrides({"BICFI": "CRESCHZZ80A"})
        assert len(mapped) == 0
        assert len(errors) == 1
        assert errors[0].is_warning is True

    def test_direct_key_takes_precedence(self):
        """Wenn ein Key direkt in FIELD_MAPPINGS existiert, wird er direkt verwendet."""
        mapped, _, errors = validate_and_map_overrides({"ChrgBr": "OUR"})
        assert len(errors) == 0
        # ChrgBr ist sowohl direkter Key als auch eindeutiger Tag
        assert "ChrgBr" in mapped
        assert mapped["ChrgBr"]["value"] == "DEBT"  # normalisiert

    def test_mixed_direct_and_tag_keys(self):
        """Mischung aus direkten Keys und XML-Tag-Namen."""
        mapped, _, errors = validate_and_map_overrides({
            "Cdtr.Nm": "Direkt GmbH",
            "InstdAmt": "250.00",
        })
        assert len(errors) == 0
        assert "Cdtr.Nm" in mapped
        assert "Amt.InstdAmt" in mapped

    def test_mixed_with_ambiguous_and_unknown(self):
        """Mix: direkt + eindeutig + mehrdeutig + unbekannt."""
        mapped, _, errors = validate_and_map_overrides({
            "ChrgBr": "SHAR",       # direkt
            "InstdAmt": "100.00",   # eindeutiger Tag
            "Nm": "Ambig",          # mehrdeutig
            "FooBar": "xyz",        # unbekannt
        })
        assert len(mapped) == 2  # ChrgBr + InstdAmt
        assert "ChrgBr" in mapped
        assert "Amt.InstdAmt" in mapped

        warnings = [e for e in errors if e.is_warning]
        hard_errors = [e for e in errors if not e.is_warning]
        assert len(warnings) == 1  # Nm
        assert len(hard_errors) == 1  # FooBar
        assert warnings[0].key == "Nm"
        assert hard_errors[0].key == "FooBar"

    def test_unknown_tag_still_errors(self):
        """Komplett unbekannter Key erzeugt weiterhin einen harten Fehler."""
        mapped, _, errors = validate_and_map_overrides({"Nonsense": "value"})
        assert len(mapped) == 0
        assert len(errors) == 1
        assert errors[0].is_warning is False
        assert "Unbekannter Override-Key" in errors[0].message

    def test_special_keys_still_work(self):
        """SPECIAL_KEYS funktionieren weiterhin."""
        mapped, special, errors = validate_and_map_overrides({
            "ViolateRule": "BR-SEPA-001",
            "InstdAmt": "99.99",
        })
        assert len(errors) == 0
        assert special["ViolateRule"] == "BR-SEPA-001"
        assert "Amt.InstdAmt" in mapped

    def test_unique_tag_mmbid(self):
        """MmbId (ClearingSystemMemberId) wird eindeutig aufgelöst."""
        mapped, _, errors = validate_and_map_overrides({"MmbId": "09000"})
        assert len(errors) == 0
        assert "CdtrAgt.ClrSysMmbId" in mapped
        assert mapped["CdtrAgt.ClrSysMmbId"]["xpath"] == "CdtrAgt/FinInstnId/ClrSysMmbId/MmbId"


# =========================================================================
# SIC5 Instant Rules
# =========================================================================

def test_sic5_instant_valid():
    """SIC5 Instant mit CHF und CH-IBAN: alle Regeln bestanden."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_IBAN,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"},
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={
        "service_level": "INST",
        "local_instrument": "INST",
        "charge_bearer": None,
    })
    results = validate_all_business_rules(instr, tc)
    failed = [r for r in results if not r.passed]
    assert len(failed) == 0, f"Failed rules: {[r.rule_id for r in failed]}"


def test_sic5_instant_wrong_currency():
    """BR-SIC5-001: Instant mit EUR schlaegt fehl."""
    tc = _make_testcase(
        currency="EUR",
        payment_type=PaymentType.DOMESTIC_IBAN,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"},
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={
        "service_level": "INST",
        "local_instrument": "INST",
        "charge_bearer": None,
    })
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-SIC5-001" in failed_ids


def test_sic5_instant_non_ch_iban():
    """BR-SIC5-002: Instant mit DE-IBAN schlaegt fehl."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_IBAN,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={
        "service_level": "INST",
        "local_instrument": "INST",
        "charge_bearer": None,
    })
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-SIC5-002" in failed_ids


def test_sic5_instant_missing_service_level():
    """BR-SIC5-003: Instant ohne SvcLvl=INST schlaegt fehl."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_IBAN,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"},
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={
        "service_level": None,
        "local_instrument": "INST",
        "charge_bearer": None,
    })
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-SIC5-003" in failed_ids


def test_sic5_instant_missing_local_instrument():
    """BR-SIC5-004: Instant ohne LclInstrm=INST schlaegt fehl."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_IBAN,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"},
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={
        "service_level": "INST",
        "local_instrument": None,
        "charge_bearer": None,
    })
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-SIC5-004" in failed_ids


# =========================================================================
# Purpose Code Rules
# =========================================================================

def test_purpose_code_valid():
    """BR-PURP-001: Gültiger Purpose Code (4 Grossbuchstaben) besteht."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_IBAN,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zürich", "Ctry": "CH"},
        purpose_code="SALA",
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None, "charge_bearer": None})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-PURP-001" not in failed_ids


def test_purpose_code_invalid():
    """BR-PURP-001: Ungültiger Purpose Code (Kleinbuchstaben) schlägt fehl."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_IBAN,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zürich", "Ctry": "CH"},
        purpose_code="sala",
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None, "charge_bearer": None})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-PURP-001" in failed_ids


def test_purpose_code_none_no_rule_check():
    """BR-PURP-001 wird nicht geprüft wenn kein Purpose Code gesetzt."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_IBAN,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zürich", "Ctry": "CH"},
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None, "charge_bearer": None})
    results = validate_all_business_rules(instr, tc)
    purp_results = [r for r in results if r.rule_id == "BR-PURP-001"]
    assert len(purp_results) == 0


def test_non_instant_no_sic5_rules():
    """Non-Instant Domestic-IBAN: SIC5-Regeln werden nicht geprueft."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.DOMESTIC_IBAN,
        instant=False,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "PstCd": "8001", "TwnNm": "Zuerich", "Ctry": "CH"},
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None, "charge_bearer": None})
    results = validate_all_business_rules(instr, tc)
    sic5_results = [r for r in results if r.rule_id.startswith("BR-SIC5")]
    assert len(sic5_results) == 0


# =========================================================================
# LEI (Legal Entity Identifier) Validierung
# =========================================================================

def test_lei_valid_creditor():
    """BR-GEN-013: Gültiger Creditor-LEI passiert die Validierung."""
    tc = _make_testcase(currency="EUR", payment_type=PaymentType.SEPA)
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
        creditor_lei="5493001KJTIIGC8Y1R12",
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    lei_results = [r for r in results if r.rule_id == "BR-GEN-013"]
    assert all(r.passed for r in lei_results), f"LEI validation failed: {lei_results}"


def test_lei_invalid_format():
    """BR-GEN-013: Ungültiger LEI wird erkannt."""
    tc = _make_testcase(currency="EUR", payment_type=PaymentType.SEPA)
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
        creditor_lei="INVALID_LEI",
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    lei_results = [r for r in results if r.rule_id == "BR-GEN-013"]
    assert any(not r.passed for r in lei_results)


def test_lei_valid_debtor():
    """BR-GEN-013: Gültiger Debtor-LEI passiert die Validierung."""
    debtor = DebtorInfo(
        name="Test AG", iban="CH9300762011623852957", lei="5493001KJTIIGC8Y1R12",
    )
    tc = _make_testcase(currency="EUR", payment_type=PaymentType.SEPA, debtor=debtor)
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    lei_results = [r for r in results if r.rule_id == "BR-GEN-013"]
    assert all(r.passed for r in lei_results)


def test_lei_invalid_debtor():
    """BR-GEN-013: Ungültiger Debtor-LEI wird erkannt (zu kurz)."""
    debtor = DebtorInfo(
        name="Test AG", iban="CH9300762011623852957", lei="TOOSHORT",
    )
    tc = _make_testcase(currency="EUR", payment_type=PaymentType.SEPA, debtor=debtor)
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    lei_results = [r for r in results if r.rule_id == "BR-GEN-013"]
    assert any(not r.passed for r in lei_results)


def test_lei_no_lei_no_validation():
    """BR-GEN-013: Ohne LEI gibt es keine LEI-Validierung."""
    tc = _make_testcase(currency="EUR", payment_type=PaymentType.SEPA)
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    lei_results = [r for r in results if r.rule_id == "BR-GEN-013"]
    assert len(lei_results) == 0


# =========================================================================
# SCT Inst (SEPA Instant) Rules
# =========================================================================

def _make_sct_inst_instruction(tc, transactions):
    """Erstellt eine PaymentInstruction fuer SCT Inst (SEPA Instant)."""
    return PaymentInstruction(
        msg_id="MSG-test123",
        pmt_inf_id="PMT-test123",
        cre_dt_tm="2026-03-20T10:00:00",
        reqd_exctn_dt="2026-03-23",
        debtor=tc.debtor,
        service_level="INST",
        local_instrument="INST",
        charge_bearer="SLEV",
        transactions=transactions,
    )


def test_sct_inst_valid():
    """SCT Inst mit EUR, SLEV, INST und Betrag unter 100k: alle Regeln bestanden."""
    tc = _make_testcase(
        currency="EUR",
        payment_type=PaymentType.SEPA,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("500.00"),
        currency="EUR",
        creditor_name="Creditor GmbH",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Berliner Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_sct_inst_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    failed = [r for r in results if not r.passed]
    assert len(failed) == 0, f"Failed rules: {[r.rule_id for r in failed]}"


def test_sct_inst_wrong_currency():
    """BR-SCT-INST-001: SCT Inst mit CHF statt EUR schlaegt fehl."""
    tc = _make_testcase(
        currency="CHF",
        payment_type=PaymentType.SEPA,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor GmbH",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_sct_inst_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-SCT-INST-001" in failed_ids


def test_sct_inst_missing_service_level():
    """BR-SCT-INST-003: SCT Inst ohne SvcLvl=INST schlaegt fehl."""
    tc = _make_testcase(
        currency="EUR",
        payment_type=PaymentType.SEPA,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor GmbH",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_sct_inst_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": "SEPA"})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-SCT-INST-003" in failed_ids


def test_sct_inst_missing_local_instrument():
    """BR-SCT-INST-004: SCT Inst ohne LclInstrm=INST schlaegt fehl."""
    tc = _make_testcase(
        currency="EUR",
        payment_type=PaymentType.SEPA,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor GmbH",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_sct_inst_instruction(tc, [tx])
    instr = instr.model_copy(update={"local_instrument": None})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-SCT-INST-004" in failed_ids


def test_sct_inst_wrong_charge_bearer():
    """BR-SCT-INST-005: SCT Inst mit ChrgBr=DEBT statt SLEV schlaegt fehl."""
    tc = _make_testcase(
        currency="EUR",
        payment_type=PaymentType.SEPA,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor GmbH",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_sct_inst_instruction(tc, [tx])
    instr = instr.model_copy(update={"charge_bearer": "DEBT"})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-SCT-INST-005" in failed_ids


def test_non_instant_sepa_no_sct_inst_rules():
    """Non-Instant SEPA: SCT-Inst-Regeln werden nicht geprueft."""
    tc = _make_testcase(
        currency="EUR",
        payment_type=PaymentType.SEPA,
        instant=False,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor GmbH",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    sct_inst_results = [r for r in results if r.rule_id.startswith("BR-SCT-INST")]
    assert len(sct_inst_results) == 0


def test_sepa_instant_no_sic5_rules():
    """SEPA Instant: SIC5-Regeln werden NICHT geprueft (nur SCT-Inst)."""
    tc = _make_testcase(
        currency="EUR",
        payment_type=PaymentType.SEPA,
        instant=True,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor GmbH",
        creditor_iban="DE89370400440532013000",
        creditor_address={"StrtNm": "Str.", "PstCd": "10115", "TwnNm": "Berlin", "Ctry": "DE"},
    )
    instr = _make_sct_inst_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    sic5_results = [r for r in results if r.rule_id.startswith("BR-SIC5")]
    assert len(sic5_results) == 0


# =========================================================================
# CGI-MP Structured Address Enforcement (BR-CGI-ADDR-03)
# =========================================================================


def _make_cgi_mp_testcase(**kwargs):
    """Erstellt einen CGI-MP Testfall mit Standard-Defaults."""
    defaults = {
        "testcase_id": "TC-CGI-TEST",
        "titel": "CGI-MP Test",
        "ziel": "Test",
        "expected_result": ExpectedResult.OK,
        "payment_type": PaymentType.SEPA,
        "amount": Decimal("100.00"),
        "currency": "EUR",
        "debtor": DebtorInfo(
            name="Test AG",
            iban="CH9300762011623852957",
            street="Bahnhofstrasse",
            postal_code="8001",
            town="Zuerich",
            country="CH",
        ),
        "standard": Standard.CGI_MP,
        "overrides": {},
    }
    defaults.update(kwargs)
    return TestCase(**defaults)


def test_cgi_mp_structured_address_ok():
    """BR-CGI-ADDR-03: CGI-MP mit vollstaendiger strukturierter Adresse besteht."""
    tc = _make_cgi_mp_testcase()
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={
            "StrtNm": "Berliner Str.",
            "BldgNb": "42",
            "PstCd": "10115",
            "TwnNm": "Berlin",
            "Ctry": "DE",
        },
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-CGI-ADDR-03" not in failed_ids


def test_cgi_mp_adrline_fails():
    """BR-CGI-ADDR-03: CGI-MP mit AdrLine anstatt strukturierter Adresse schlaegt fehl."""
    tc = _make_cgi_mp_testcase()
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={
            "AdrLine": "Berliner Str. 42|10115 Berlin",
            "Ctry": "DE",
        },
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-CGI-ADDR-03" in failed_ids


def test_cgi_mp_missing_structured_fields_fails():
    """BR-CGI-ADDR-03: CGI-MP mit fehlenden Pflichtfeldern schlaegt fehl."""
    tc = _make_cgi_mp_testcase()
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={
            "StrtNm": "Berliner Str.",
            "Ctry": "DE",
            # PstCd und TwnNm fehlen
        },
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-CGI-ADDR-03" in failed_ids


def test_cgi_mp_no_address_fails():
    """BR-CGI-ADDR-03: CGI-MP ohne Creditor-Adresse schlaegt fehl."""
    tc = _make_cgi_mp_testcase()
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address=None,
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-CGI-ADDR-03" in failed_ids


def test_non_cgi_mp_no_addr03_check():
    """BR-CGI-ADDR-03 wird bei Non-CGI-MP-Standards nicht geprueft."""
    tc = _make_testcase(
        currency="EUR",
        payment_type=PaymentType.SEPA,
    )
    # SPS standard (default) — AdrLine should be allowed
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={
            "AdrLine": "Berliner Str. 42|10115 Berlin",
            "Ctry": "DE",
        },
    )
    instr = _make_instruction(tc, [tx])
    results = validate_all_business_rules(instr, tc)
    cgi_results = [r for r in results if r.rule_id == "BR-CGI-ADDR-03"]
    assert len(cgi_results) == 0


def test_cgi_mp_violation_br_cgi_addr_03():
    """BR-CGI-ADDR-03 Violation: strukturierte Adresse wird durch AdrLine ersetzt."""
    from src.validation.business_rules import apply_rule_violation

    tc = _make_cgi_mp_testcase(violate_rule="BR-CGI-ADDR-03")
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="DE89370400440532013000",
        creditor_address={
            "StrtNm": "Berliner Str.",
            "BldgNb": "42",
            "PstCd": "10115",
            "TwnNm": "Berlin",
            "Ctry": "DE",
        },
    )
    instr = _make_instruction(tc, [tx])
    violated = apply_rule_violation(tc, instr)
    # Adresse muss jetzt AdrLine haben und keine strukturierten Felder
    addr = violated.transactions[0].creditor_address
    assert "AdrLine" in addr
    assert "StrtNm" not in addr

    # Validierung muss BR-CGI-ADDR-03 als fehlgeschlagen melden
    results = validate_all_business_rules(violated, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-CGI-ADDR-03" in failed_ids


# =========================================================================
# Tax Remittance Validation (BR-CGI-TAX-*)
# =========================================================================

class TestCgiMpTaxValidation:
    """Tests für CGI-MP Tax Remittance Business Rules."""

    def _make_cgi_tx(self, tax_remittance=None, **kwargs):
        defaults = dict(
            end_to_end_id="E2E-tax",
            amount=Decimal("5000.00"),
            currency="CHF",
            creditor_name="Steuerverwaltung",
            creditor_iban="CH9300762011623852957",
            creditor_address={
                "StrtNm": "Steuerstr.",
                "BldgNb": "1",
                "PstCd": "8001",
                "TwnNm": "Zuerich",
                "Ctry": "CH",
            },
            tax_remittance=tax_remittance,
        )
        defaults.update(kwargs)
        return Transaction(**defaults)

    def test_cgi_tax_01_whld_without_tax(self):
        """BR-CGI-TAX-01: CtgyPurp=WHLD erfordert TaxRmt."""
        tc = _make_testcase(
            payment_type=PaymentType.DOMESTIC_IBAN,
            standard=Standard.CGI_MP,
            currency="CHF",
        )
        tx = self._make_cgi_tx(tax_remittance=None)
        instr = PaymentInstruction(
            msg_id="MSG-tax",
            pmt_inf_id="PMT-tax",
            cre_dt_tm="2026-03-28T10:00:00",
            reqd_exctn_dt="2026-03-30",
            debtor=tc.debtor,
            category_purpose="WHLD",
            transactions=[tx],
        )
        results = validate_all_business_rules(instr, tc)
        failed = [r for r in results if r.rule_id == "BR-CGI-TAX-01"]
        assert len(failed) == 1
        assert not failed[0].passed

    def test_cgi_tax_01_whld_with_tax_passes(self):
        """BR-CGI-TAX-01: CtgyPurp=WHLD mit TaxRmt ist OK."""
        tc = _make_testcase(
            payment_type=PaymentType.DOMESTIC_IBAN,
            standard=Standard.CGI_MP,
            currency="CHF",
        )
        tx = self._make_cgi_tx(tax_remittance={
            "Cdtr.TaxId": "TAX-001",
            "Dbtr.TaxId": "PAYER-001",
            "Mtd": "NORM",
        })
        instr = PaymentInstruction(
            msg_id="MSG-tax",
            pmt_inf_id="PMT-tax",
            cre_dt_tm="2026-03-28T10:00:00",
            reqd_exctn_dt="2026-03-30",
            debtor=tc.debtor,
            category_purpose="WHLD",
            transactions=[tx],
        )
        results = validate_all_business_rules(instr, tc)
        tax_01 = [r for r in results if r.rule_id == "BR-CGI-TAX-01"]
        assert len(tax_01) == 1
        assert tax_01[0].passed

    def test_cgi_tax_02_missing_tax_ids(self):
        """BR-CGI-TAX-02: Cdtr.TaxId und Dbtr.TaxId sind Pflicht."""
        tc = _make_testcase(
            payment_type=PaymentType.DOMESTIC_IBAN,
            standard=Standard.CGI_MP,
            currency="CHF",
        )
        # Nur RefNb, keine TaxIds
        tx = self._make_cgi_tx(tax_remittance={
            "RefNb": "TAX-REF-001",
            "Mtd": "NORM",
        })
        instr = PaymentInstruction(
            msg_id="MSG-tax",
            pmt_inf_id="PMT-tax",
            cre_dt_tm="2026-03-28T10:00:00",
            reqd_exctn_dt="2026-03-30",
            debtor=tc.debtor,
            transactions=[tx],
        )
        results = validate_all_business_rules(instr, tc)
        tax_02 = [r for r in results if r.rule_id == "BR-CGI-TAX-02"]
        assert len(tax_02) == 1
        assert not tax_02[0].passed
        assert "Cdtr.TaxId" in tax_02[0].details
        assert "Dbtr.TaxId" in tax_02[0].details

    def test_cgi_tax_02_with_tax_ids_passes(self):
        """BR-CGI-TAX-02: Beide TaxIds vorhanden ist OK."""
        tc = _make_testcase(
            payment_type=PaymentType.DOMESTIC_IBAN,
            standard=Standard.CGI_MP,
            currency="CHF",
        )
        tx = self._make_cgi_tx(tax_remittance={
            "Cdtr.TaxId": "AUTH-001",
            "Dbtr.TaxId": "PAYER-001",
            "Mtd": "NORM",
        })
        instr = PaymentInstruction(
            msg_id="MSG-tax",
            pmt_inf_id="PMT-tax",
            cre_dt_tm="2026-03-28T10:00:00",
            reqd_exctn_dt="2026-03-30",
            debtor=tc.debtor,
            transactions=[tx],
        )
        results = validate_all_business_rules(instr, tc)
        tax_02 = [r for r in results if r.rule_id == "BR-CGI-TAX-02"]
        assert len(tax_02) == 1
        assert tax_02[0].passed

    def test_cgi_tax_03_missing_method(self):
        """BR-CGI-TAX-03: Mtd ist Pflicht wenn Tax vorhanden."""
        tc = _make_testcase(
            payment_type=PaymentType.DOMESTIC_IBAN,
            standard=Standard.CGI_MP,
            currency="CHF",
        )
        # Tax ohne Mtd
        tx = self._make_cgi_tx(tax_remittance={
            "Cdtr.TaxId": "AUTH-001",
            "Dbtr.TaxId": "PAYER-001",
        })
        instr = PaymentInstruction(
            msg_id="MSG-tax",
            pmt_inf_id="PMT-tax",
            cre_dt_tm="2026-03-28T10:00:00",
            reqd_exctn_dt="2026-03-30",
            debtor=tc.debtor,
            transactions=[tx],
        )
        results = validate_all_business_rules(instr, tc)
        tax_03 = [r for r in results if r.rule_id == "BR-CGI-TAX-03"]
        assert len(tax_03) == 1
        assert not tax_03[0].passed

    def test_cgi_tax_03_with_method_passes(self):
        """BR-CGI-TAX-03: Mtd vorhanden ist OK."""
        tc = _make_testcase(
            payment_type=PaymentType.DOMESTIC_IBAN,
            standard=Standard.CGI_MP,
            currency="CHF",
        )
        tx = self._make_cgi_tx(tax_remittance={
            "Cdtr.TaxId": "AUTH-001",
            "Dbtr.TaxId": "PAYER-001",
            "Mtd": "NORM",
        })
        instr = PaymentInstruction(
            msg_id="MSG-tax",
            pmt_inf_id="PMT-tax",
            cre_dt_tm="2026-03-28T10:00:00",
            reqd_exctn_dt="2026-03-30",
            debtor=tc.debtor,
            transactions=[tx],
        )
        results = validate_all_business_rules(instr, tc)
        tax_03 = [r for r in results if r.rule_id == "BR-CGI-TAX-03"]
        assert len(tax_03) == 1
        assert tax_03[0].passed

    def test_no_tax_validation_for_sps(self):
        """Tax-Validierung nur für CGI-MP, nicht SPS."""
        tc = _make_testcase(
            payment_type=PaymentType.DOMESTIC_IBAN,
            standard=Standard.SPS_2025,
            currency="CHF",
        )
        tx = self._make_cgi_tx(tax_remittance={
            "RefNb": "TAX-REF-001",
            # Kein Cdtr.TaxId/Dbtr.TaxId — bei SPS kein Fehler
        })
        instr = PaymentInstruction(
            msg_id="MSG-tax",
            pmt_inf_id="PMT-tax",
            cre_dt_tm="2026-03-28T10:00:00",
            reqd_exctn_dt="2026-03-30",
            debtor=tc.debtor,
            transactions=[tx],
        )
        results = validate_all_business_rules(instr, tc)
        tax_rules = [r for r in results if r.rule_id.startswith("BR-CGI-TAX")]
        assert len(tax_rules) == 0


# =========================================================================
# Batch Booking (BtchBookg) Validation
# =========================================================================

def test_batch_booking_true_single_tx_fails():
    """BR-BTCH-001: BtchBookg=true bei nur einer Transaktion muss fehlschlagen."""
    tc = _make_testcase(payment_type=PaymentType.DOMESTIC_IBAN, currency="CHF")
    tx = Transaction(
        end_to_end_id="E2E-btch",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "TwnNm": "Bern", "Ctry": "CH"},
    )
    instr = PaymentInstruction(
        msg_id="MSG-btch",
        pmt_inf_id="PMT-btch",
        cre_dt_tm="2026-03-28T10:00:00",
        reqd_exctn_dt="2026-03-30",
        debtor=tc.debtor,
        batch_booking=True,
        transactions=[tx],
    )
    results = validate_all_business_rules(instr, tc)
    btch_rules = [r for r in results if r.rule_id == "BR-BTCH-001"]
    assert len(btch_rules) == 1
    assert not btch_rules[0].passed


def test_batch_booking_true_multi_tx_passes():
    """BR-BTCH-001: BtchBookg=true bei mehreren Transaktionen ist OK."""
    tc = _make_testcase(payment_type=PaymentType.DOMESTIC_IBAN, currency="CHF")
    tx1 = Transaction(
        end_to_end_id="E2E-btch1",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "TwnNm": "Bern", "Ctry": "CH"},
    )
    tx2 = Transaction(
        end_to_end_id="E2E-btch2",
        amount=Decimal("200.00"),
        currency="CHF",
        creditor_name="Creditor2 AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "TwnNm": "Bern", "Ctry": "CH"},
    )
    instr = PaymentInstruction(
        msg_id="MSG-btch",
        pmt_inf_id="PMT-btch",
        cre_dt_tm="2026-03-28T10:00:00",
        reqd_exctn_dt="2026-03-30",
        debtor=tc.debtor,
        batch_booking=True,
        transactions=[tx1, tx2],
    )
    results = validate_all_business_rules(instr, tc)
    btch_rules = [r for r in results if r.rule_id == "BR-BTCH-001"]
    assert len(btch_rules) == 1
    assert btch_rules[0].passed


def test_batch_booking_false_no_rule_check():
    """BR-BTCH-001: BtchBookg=false erzeugt keine Rule-Prüfung."""
    tc = _make_testcase(payment_type=PaymentType.DOMESTIC_IBAN, currency="CHF")
    tx = Transaction(
        end_to_end_id="E2E-btch",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "TwnNm": "Bern", "Ctry": "CH"},
    )
    instr = PaymentInstruction(
        msg_id="MSG-btch",
        pmt_inf_id="PMT-btch",
        cre_dt_tm="2026-03-28T10:00:00",
        reqd_exctn_dt="2026-03-30",
        debtor=tc.debtor,
        batch_booking=False,
        transactions=[tx],
    )
    results = validate_all_business_rules(instr, tc)
    btch_rules = [r for r in results if r.rule_id == "BR-BTCH-001"]
    assert len(btch_rules) == 0


def test_batch_booking_none_no_rule_check():
    """BR-BTCH-001: BtchBookg=None erzeugt keine Rule-Prüfung."""
    tc = _make_testcase(payment_type=PaymentType.DOMESTIC_IBAN, currency="CHF")
    tx = Transaction(
        end_to_end_id="E2E-btch",
        amount=Decimal("100.00"),
        currency="CHF",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
        creditor_address={"StrtNm": "Str.", "TwnNm": "Bern", "Ctry": "CH"},
    )
    instr = PaymentInstruction(
        msg_id="MSG-btch",
        pmt_inf_id="PMT-btch",
        cre_dt_tm="2026-03-28T10:00:00",
        reqd_exctn_dt="2026-03-30",
        debtor=tc.debtor,
        batch_booking=None,
        transactions=[tx],
    )
    results = validate_all_business_rules(instr, tc)
    btch_rules = [r for r in results if r.rule_id == "BR-BTCH-001"]
    assert len(btch_rules) == 0
