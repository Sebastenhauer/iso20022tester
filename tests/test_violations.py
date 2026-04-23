"""Tests fuer Violation-Funktionen (Negative Testing).

Jede violatable Rule wird getestet:
1. Violation anwenden
2. Pruefen dass die betroffene Rule danach fehlschlaegt
3. Pruefen dass das XML trotzdem XSD-valide bleibt
"""

from decimal import Decimal

import pytest

from src.data_factory.generator import DataFactory
from src.data_factory.iban import is_qr_iban
from src.models.testcase import (
    DebtorInfo,
    ExpectedResult,
    PaymentInstruction,
    PaymentType,
    TestCase,
    Transaction,
)
from src.payment_types import get_handler
from src.validation.business_rules import (
    apply_rule_violation,
    check_violation_conflicts,
    parse_violate_rules,
    validate_all_business_rules,
)
from src.xml_generator.pain001_builder import build_pain001_xml
from src.validation.xsd_validator import XsdValidator


DEBTOR = DebtorInfo(name="Test AG", iban="CH9300762011623852957", bic="CRESCHZZ80A")
FACTORY = DataFactory(seed=99)


def _make_tc(payment_type, currency, violate_rule, overrides=None):
    return TestCase(
        testcase_id="TC-VIO",
        titel="Violation Test",
        ziel="Test",
        expected_result=ExpectedResult.NOK,
        payment_type=payment_type,
        amount=Decimal("100.00"),
        currency=currency,
        debtor=DEBTOR,
        violate_rule=violate_rule,
        overrides=overrides or {},
    )


def _make_instr(tc, factory=None):
    factory = factory or DataFactory(seed=99)
    handler = get_handler(tc.payment_type)
    txs = handler.generate_transactions(tc, factory)
    return PaymentInstruction(
        msg_id=factory.generate_msg_id(),
        pmt_inf_id=factory.generate_pmt_inf_id(),
        cre_dt_tm="2026-03-28T10:00:00",
        reqd_exctn_dt="2026-03-30",
        debtor=tc.debtor,
        service_level=handler.get_service_level(),
        charge_bearer=handler.get_charge_bearer(),
        transactions=txs,
    )


@pytest.fixture
def xsd_validator():
    return XsdValidator("schemas/pain.001/pain.001.001.09.ch.03.xsd")


# =========================================================================
# SEPA Violations
# =========================================================================

class TestSepaViolations:
    def test_br_sepa_001_wrong_currency(self, xsd_validator):
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-SEPA-001")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        # Waehrung sollte nicht mehr EUR sein
        assert violated.transactions[0].currency != "EUR"
        # Rule muss fehlschlagen
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-SEPA-001" in failed_ids
        # XML muss trotzdem XSD-valide sein
        xml = build_pain001_xml(violated)
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"

    def test_br_sepa_003_wrong_charge_bearer(self, xsd_validator):
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-SEPA-003")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.charge_bearer != "SLEV"
        xml = build_pain001_xml(violated)
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"

    def test_br_sepa_004_name_too_long(self, xsd_validator):
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-SEPA-004")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert len(violated.transactions[0].creditor_name) > 70
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-SEPA-004" in failed_ids


# =========================================================================
# QR Violations
# =========================================================================

class TestQrViolations:
    def test_br_qr_002_no_reference(self, xsd_validator):
        tc = _make_tc(PaymentType.DOMESTIC_QR, "CHF", "BR-QR-002")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].remittance_info is None
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-QR-002" in failed_ids
        xml = build_pain001_xml(violated)
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"

    def test_br_qr_003_scor_at_qr_iban(self, xsd_validator):
        tc = _make_tc(PaymentType.DOMESTIC_QR, "CHF", "BR-QR-003")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].remittance_info["type"] == "SCOR"
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-QR-003" in failed_ids

    def test_br_qr_004_wrong_currency(self, xsd_validator):
        tc = _make_tc(PaymentType.DOMESTIC_QR, "CHF", "BR-QR-004")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].currency not in ("CHF", "EUR")


# =========================================================================
# IBAN Violations
# =========================================================================

class TestIbanViolations:
    def test_br_iban_001_qr_iban(self, xsd_validator):
        tc = _make_tc(PaymentType.DOMESTIC_IBAN, "CHF", "BR-IBAN-001")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert is_qr_iban(violated.transactions[0].creditor_iban)
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-IBAN-001" in failed_ids

    def test_br_iban_002_qrr_at_regular_iban(self, xsd_validator):
        tc = _make_tc(PaymentType.DOMESTIC_IBAN, "CHF", "BR-IBAN-002")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].remittance_info["type"] == "QRR"

# =========================================================================
# Domestic Violations
# =========================================================================

class TestDomesticViolations:
    def test_br_dom_001_charge_bearer_set(self, xsd_validator):
        """BR-DOM-001: ChrgBr bei Domestic-IBAN wird auf SHAR gesetzt."""
        tc = _make_tc(PaymentType.DOMESTIC_IBAN, "CHF", "BR-DOM-001")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.charge_bearer == "SHAR"
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-DOM-001" in failed_ids
        # XML muss trotzdem XSD-valide sein
        xml = build_pain001_xml(violated)
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"

    def test_br_dom_001_qr_charge_bearer_set(self, xsd_validator):
        """BR-DOM-001: ChrgBr bei Domestic-QR wird auf SHAR gesetzt."""
        tc = _make_tc(PaymentType.DOMESTIC_QR, "CHF", "BR-DOM-001")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.charge_bearer == "SHAR"
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-DOM-001" in failed_ids


# =========================================================================
# CBPR+ Violations
# =========================================================================

class TestCbprViolations:
    def test_br_cbpr_001_empty_currency(self, xsd_validator):
        tc = _make_tc(PaymentType.CBPR_PLUS, "USD", "BR-CBPR-001",
                      overrides={"CdtrAgt.BICFI": "BNPAFRPP"})
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].currency == ""

    def test_br_cbpr_005_no_agent(self, xsd_validator):
        tc = _make_tc(PaymentType.CBPR_PLUS, "USD", "BR-CBPR-005",
                      overrides={"CdtrAgt.BICFI": "BNPAFRPP"})
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].creditor_bic is None
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-CBPR-005" in failed_ids

    def test_br_cbpr_003_empty_charge_bearer(self, xsd_validator):
        tc = _make_tc(PaymentType.CBPR_PLUS, "USD", "BR-CBPR-003",
                      overrides={"CdtrAgt.BICFI": "BNPAFRPP"})
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.charge_bearer == ""


# =========================================================================
# Unbekannte Rule
# =========================================================================

class TestSic5Violations:
    def test_br_sic5_001_wrong_currency(self, xsd_validator):
        """BR-SIC5-001: Setzt Währung auf EUR statt CHF."""
        tc = _make_tc(PaymentType.DOMESTIC_IBAN, "CHF", "BR-SIC5-001")
        tc = tc.model_copy(update={"instant": True})
        instr = _make_instr(tc)
        instr = instr.model_copy(update={"service_level": "INST", "local_instrument": "INST"})
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].currency == "EUR"
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-SIC5-001" in failed_ids
        xml = build_pain001_xml(violated)
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"

    def test_br_sic5_002_wrong_iban(self, xsd_validator):
        """BR-SIC5-002: Setzt DE-IBAN statt CH-IBAN."""
        tc = _make_tc(PaymentType.DOMESTIC_IBAN, "CHF", "BR-SIC5-002")
        tc = tc.model_copy(update={"instant": True})
        instr = _make_instr(tc)
        instr = instr.model_copy(update={"service_level": "INST", "local_instrument": "INST"})
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].creditor_iban.startswith("DE")
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-SIC5-002" in failed_ids


class TestSctInstViolations:
    def test_br_sct_inst_001_wrong_currency(self, xsd_validator):
        """BR-SCT-INST-001: Setzt Waehrung auf CHF statt EUR bei SCT Inst."""
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-SCT-INST-001")
        tc = tc.model_copy(update={"instant": True})
        instr = _make_instr(tc)
        instr = instr.model_copy(update={"service_level": "INST", "local_instrument": "INST"})
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].currency == "CHF"
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-SCT-INST-001" in failed_ids
        xml = build_pain001_xml(violated)
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"

class TestUnknownViolation:
    def test_unknown_rule_returns_unchanged(self):
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-UNKNOWN-999")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        # Instruction sollte unveraendert sein
        assert violated.transactions[0].currency == instr.transactions[0].currency


# =========================================================================
# Violation Chaining (kommaseparierte Rule-IDs)
# =========================================================================

class TestParseViolateRules:
    def test_single_rule(self):
        assert parse_violate_rules("BR-SEPA-001") == ["BR-SEPA-001"]

    def test_two_rules(self):
        assert parse_violate_rules("BR-SEPA-001,BR-SEPA-003") == ["BR-SEPA-001", "BR-SEPA-003"]

    def test_whitespace_handling(self):
        assert parse_violate_rules("BR-SEPA-001 , BR-SEPA-003") == ["BR-SEPA-001", "BR-SEPA-003"]

    def test_trailing_comma(self):
        assert parse_violate_rules("BR-SEPA-001,") == ["BR-SEPA-001"]

    def test_empty_string(self):
        assert parse_violate_rules("") == []


class TestConflictDetection:
    def test_no_conflict_different_fields(self):
        errors = check_violation_conflicts(["BR-SEPA-001", "BR-SEPA-003"])
        assert errors == []

    def test_conflict_same_field_currency(self):
        errors = check_violation_conflicts(["BR-SEPA-001", "BR-QR-004"])
        assert len(errors) == 1
        assert "currency" in errors[0]

    def test_conflict_same_field_charge_bearer(self):
        errors = check_violation_conflicts(["BR-SEPA-003", "BR-DOM-001"])
        assert len(errors) == 1
        assert "charge_bearer" in errors[0]

    def test_conflict_same_field_remittance(self):
        errors = check_violation_conflicts(["BR-QR-002", "BR-QR-003"])
        assert len(errors) == 1
        assert "remittance_info" in errors[0]

    def test_unknown_rules_no_conflict(self):
        errors = check_violation_conflicts(["BR-UNKNOWN-001", "BR-UNKNOWN-002"])
        assert errors == []

    def test_three_rules_two_conflicts(self):
        errors = check_violation_conflicts(["BR-SEPA-001", "BR-QR-004", "BR-SIC5-001"])
        assert len(errors) == 1
        assert "currency" in errors[0]


class TestViolationChaining:
    def test_sepa_currency_and_charge_bearer(self, xsd_validator):
        """Zwei unabhaengige Violations gleichzeitig anwenden."""
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-SEPA-001,BR-SEPA-003")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        # Beide Violations muessen angewendet sein
        assert violated.transactions[0].currency != "EUR"
        assert violated.charge_bearer != "SLEV"
        # Beide Rules muessen fehlschlagen
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-SEPA-001" in failed_ids
        assert "BR-SEPA-003" in failed_ids
        # XSD muss valide bleiben
        xml = build_pain001_xml(violated)
        valid, errors = xsd_validator.validate(xml)
        assert valid, f"XSD errors: {errors}"

    def test_sepa_currency_and_name_length(self, xsd_validator):
        """Currency + Name-Length Violations gleichzeitig."""
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-SEPA-001,BR-SEPA-004")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].currency != "EUR"
        assert len(violated.transactions[0].creditor_name) > 70
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-SEPA-001" in failed_ids
        assert "BR-SEPA-004" in failed_ids

    def test_three_violations(self, xsd_validator):
        """Drei unabhaengige Violations gleichzeitig."""
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-SEPA-001,BR-SEPA-003,BR-SEPA-004")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].currency != "EUR"
        assert violated.charge_bearer != "SLEV"
        assert len(violated.transactions[0].creditor_name) > 70
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert {"BR-SEPA-001", "BR-SEPA-003", "BR-SEPA-004"}.issubset(failed_ids)

    def test_conflict_raises_error(self):
        """Konfligierende Violations muessen ValueError ausloesen."""
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-SEPA-001,BR-QR-004")
        instr = _make_instr(tc)
        with pytest.raises(ValueError, match="Konflikt"):
            apply_rule_violation(tc, instr)

    def test_chain_with_unknown_rule(self, xsd_validator):
        """Unbekannte Rules in der Kette werden uebersprungen."""
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-SEPA-001,BR-UNKNOWN-999")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].currency != "EUR"

    def test_chain_whitespace_handling(self, xsd_validator):
        """Leerzeichen um Komma werden korrekt behandelt."""
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-SEPA-001 , BR-SEPA-003")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].currency != "EUR"
        assert violated.charge_bearer != "SLEV"

    def test_domestic_qr_reference_and_charge_bearer(self, xsd_validator):
        """Domestic-QR: Referenz entfernen + ChrgBr aendern."""
        tc = _make_tc(PaymentType.DOMESTIC_QR, "CHF", "BR-QR-002,BR-DOM-001")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].remittance_info is None
        assert violated.charge_bearer == "SHAR"
        results = validate_all_business_rules(violated, tc)
        failed_ids = {r.rule_id for r in results if not r.passed}
        assert "BR-QR-002" in failed_ids
        assert "BR-DOM-001" in failed_ids
