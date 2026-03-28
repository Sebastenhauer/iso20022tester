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
    return XsdValidator("schemas/pain.001.001.09.ch.03.xsd")


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

    def test_br_iban_004_wrong_currency(self, xsd_validator):
        tc = _make_tc(PaymentType.DOMESTIC_IBAN, "CHF", "BR-IBAN-004")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        assert violated.transactions[0].currency != "CHF"


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

class TestUnknownViolation:
    def test_unknown_rule_returns_unchanged(self):
        tc = _make_tc(PaymentType.SEPA, "EUR", "BR-UNKNOWN-999")
        instr = _make_instr(tc)
        violated = apply_rule_violation(tc, instr)
        # Instruction sollte unveraendert sein
        assert violated.transactions[0].currency == instr.transactions[0].currency
