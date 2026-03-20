"""Tests für Business Rules."""

from decimal import Decimal

from src.models.testcase import (
    DebtorInfo,
    ExpectedResult,
    PaymentInstruction,
    PaymentType,
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


def test_domestic_iban_wrong_currency():
    tc = _make_testcase(
        currency="EUR",
        payment_type=PaymentType.DOMESTIC_IBAN,
    )
    tx = Transaction(
        end_to_end_id="E2E-test",
        amount=Decimal("100.00"),
        currency="EUR",
        creditor_name="Creditor AG",
        creditor_iban="CH9300762011623852957",
    )
    instr = _make_instruction(tc, [tx])
    instr = instr.model_copy(update={"service_level": None})
    results = validate_all_business_rules(instr, tc)
    failed_ids = [r.rule_id for r in results if not r.passed]
    assert "BR-IBAN-004" in failed_ids


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
