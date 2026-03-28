"""Tests fuer Payment-Type-Handler: Transaktionsgenerierung und Validierung."""

from decimal import Decimal

import pytest

from src.data_factory.generator import DataFactory
from src.data_factory.iban import is_qr_iban, validate_iban
from src.data_factory.reference import validate_qrr, validate_scor
from src.models.testcase import (
    DebtorInfo,
    ExpectedResult,
    PaymentType,
    TestCase,
    Transaction,
    TransactionInput,
)
from src.payment_types import get_handler
from src.payment_types.sepa import SepaHandler
from src.payment_types.domestic_qr import DomesticQrHandler
from src.payment_types.domestic_iban import DomesticIbanHandler
from src.payment_types.cbpr_plus import CbprPlusHandler


DEBTOR = DebtorInfo(name="Test AG", iban="CH9300762011623852957", bic="CRESCHZZ80A")
FACTORY = DataFactory(seed=42)


def _tc(payment_type, currency=None, amount=None, overrides=None, tx_inputs=None):
    return TestCase(
        testcase_id="TC-TEST",
        titel="Test",
        ziel="Test",
        expected_result=ExpectedResult.OK,
        payment_type=payment_type,
        amount=amount or Decimal("100.00"),
        currency=currency,
        debtor=DEBTOR,
        overrides=overrides or {},
        transaction_inputs=tx_inputs or [],
    )


# =========================================================================
# SEPA Handler
# =========================================================================

class TestSepaHandler:
    def test_generates_transactions(self):
        handler = SepaHandler()
        tc = _tc(PaymentType.SEPA, currency="EUR")
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        assert len(txs) == 1
        tx = txs[0]
        assert tx.currency == "EUR"
        assert tx.amount == Decimal("100.00")
        assert validate_iban(tx.creditor_iban)
        assert len(tx.creditor_name) > 0
        assert tx.charge_bearer == "SLEV"

    def test_creditor_name_max_70(self):
        handler = SepaHandler()
        tc = _tc(PaymentType.SEPA, currency="EUR",
                 overrides={"Cdtr.Nm": "A" * 100})
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        assert len(txs[0].creditor_name) <= 70

    def test_override_creditor_iban(self):
        handler = SepaHandler()
        tc = _tc(PaymentType.SEPA, currency="EUR",
                 overrides={"CdtrAcct.IBAN": "DE89370400440532013000"})
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        assert txs[0].creditor_iban == "DE89370400440532013000"

    def test_override_creditor_bic(self):
        handler = SepaHandler()
        tc = _tc(PaymentType.SEPA, currency="EUR",
                 overrides={"CdtrAgt.BICFI": "COBADEFFXXX"})
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        assert txs[0].creditor_bic == "COBADEFFXXX"

    def test_validate_ok(self):
        handler = SepaHandler()
        tc = _tc(PaymentType.SEPA, currency="EUR")
        tx = Transaction(
            end_to_end_id="E2E-1", amount=Decimal("100.00"), currency="EUR",
            creditor_name="Test", creditor_iban="DE89370400440532013000",
            creditor_address={"StrtNm": "Str", "TwnNm": "Berlin", "Ctry": "DE"},
        )
        results = handler.validate(tc, [tx])
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0

    def test_validate_wrong_currency(self):
        handler = SepaHandler()
        tc = _tc(PaymentType.SEPA, currency="CHF")
        tx = Transaction(
            end_to_end_id="E2E-1", amount=Decimal("100.00"), currency="CHF",
            creditor_name="Test", creditor_iban="DE89370400440532013000",
        )
        results = handler.validate(tc, [tx])
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-SEPA-001" in failed_ids

    def test_validate_name_too_long(self):
        handler = SepaHandler()
        tc = _tc(PaymentType.SEPA, currency="EUR")
        tx = Transaction(
            end_to_end_id="E2E-1", amount=Decimal("100.00"), currency="EUR",
            creditor_name="A" * 71, creditor_iban="DE89370400440532013000",
        )
        results = handler.validate(tc, [tx])
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-SEPA-004" in failed_ids

    def test_service_level_and_charge_bearer(self):
        handler = SepaHandler()
        assert handler.get_service_level() == "SEPA"
        assert handler.get_charge_bearer() == "SLEV"

    def test_multi_transaction_via_tx_inputs(self):
        handler = SepaHandler()
        tx_inputs = [
            TransactionInput(amount=Decimal("50.00"), currency="EUR", creditor_name="A"),
            TransactionInput(amount=Decimal("75.00"), currency="EUR", creditor_name="B"),
        ]
        tc = _tc(PaymentType.SEPA, currency="EUR", tx_inputs=tx_inputs)
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        assert len(txs) == 2
        assert txs[0].amount == Decimal("50.00")
        assert txs[1].amount == Decimal("75.00")


# =========================================================================
# Domestic-QR Handler
# =========================================================================

class TestDomesticQrHandler:
    def test_generates_qr_iban(self):
        handler = DomesticQrHandler()
        tc = _tc(PaymentType.DOMESTIC_QR, currency="CHF")
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        assert len(txs) == 1
        assert is_qr_iban(txs[0].creditor_iban)

    def test_generates_qrr_reference(self):
        handler = DomesticQrHandler()
        tc = _tc(PaymentType.DOMESTIC_QR, currency="CHF")
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        ref = txs[0].remittance_info
        assert ref is not None
        assert ref["type"] == "QRR"
        assert validate_qrr(ref["value"])

    def test_validate_ok(self):
        handler = DomesticQrHandler()
        tc = _tc(PaymentType.DOMESTIC_QR, currency="CHF")
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        results = handler.validate(tc, txs)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0

    def test_validate_wrong_currency(self):
        handler = DomesticQrHandler()
        tc = _tc(PaymentType.DOMESTIC_QR, currency="USD")
        tx = Transaction(
            end_to_end_id="E2E-1", amount=Decimal("100.00"), currency="USD",
            creditor_name="Test", creditor_iban="CH4431999123000889012",
            remittance_info={"type": "QRR", "value": "000000000000000000000000000"},
        )
        results = handler.validate(tc, [tx])
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-QR-004" in failed_ids

    def test_validate_non_qr_iban(self):
        handler = DomesticQrHandler()
        tc = _tc(PaymentType.DOMESTIC_QR, currency="CHF")
        tx = Transaction(
            end_to_end_id="E2E-1", amount=Decimal("100.00"), currency="CHF",
            creditor_name="Test", creditor_iban="CH9300762011623852957",
            remittance_info={"type": "QRR", "value": "000000000000000000000000000"},
        )
        results = handler.validate(tc, [tx])
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-QR-001" in failed_ids

    def test_validate_missing_qrr(self):
        handler = DomesticQrHandler()
        tc = _tc(PaymentType.DOMESTIC_QR, currency="CHF")
        tx = Transaction(
            end_to_end_id="E2E-1", amount=Decimal("100.00"), currency="CHF",
            creditor_name="Test", creditor_iban="CH4431999123000889012",
        )
        results = handler.validate(tc, [tx])
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-QR-002" in failed_ids


# =========================================================================
# Domestic-IBAN Handler
# =========================================================================

class TestDomesticIbanHandler:
    def test_generates_regular_iban(self):
        handler = DomesticIbanHandler()
        tc = _tc(PaymentType.DOMESTIC_IBAN, currency="CHF")
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        assert len(txs) == 1
        assert validate_iban(txs[0].creditor_iban)
        assert not is_qr_iban(txs[0].creditor_iban)

    def test_validate_ok(self):
        handler = DomesticIbanHandler()
        tc = _tc(PaymentType.DOMESTIC_IBAN, currency="CHF")
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        results = handler.validate(tc, txs)
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0

    def test_validate_wrong_currency(self):
        handler = DomesticIbanHandler()
        tc = _tc(PaymentType.DOMESTIC_IBAN, currency="EUR")
        tx = Transaction(
            end_to_end_id="E2E-1", amount=Decimal("100.00"), currency="EUR",
            creditor_name="Test", creditor_iban="CH9300762011623852957",
        )
        results = handler.validate(tc, [tx])
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-IBAN-004" in failed_ids

    def test_validate_qr_iban_rejected(self):
        handler = DomesticIbanHandler()
        tc = _tc(PaymentType.DOMESTIC_IBAN, currency="CHF")
        tx = Transaction(
            end_to_end_id="E2E-1", amount=Decimal("100.00"), currency="CHF",
            creditor_name="Test", creditor_iban="CH4431999123000889012",
        )
        results = handler.validate(tc, [tx])
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-IBAN-001" in failed_ids

    def test_service_level(self):
        handler = DomesticIbanHandler()
        assert handler.get_service_level() is None


# =========================================================================
# CBPR+ Handler
# =========================================================================

class TestCbprPlusHandler:
    def test_generates_transactions_with_bic(self):
        handler = CbprPlusHandler()
        tc = _tc(PaymentType.CBPR_PLUS, currency="USD",
                 overrides={"CdtrAgt.BICFI": "BNPAFRPP"})
        txs = handler.generate_transactions(tc, DataFactory(seed=1))
        assert len(txs) == 1
        assert txs[0].creditor_bic == "BNPAFRPP"
        assert txs[0].uetr is not None  # CBPR+ braucht UETR

    def test_validate_missing_bic(self):
        handler = CbprPlusHandler()
        tc = _tc(PaymentType.CBPR_PLUS, currency="USD")
        tx = Transaction(
            end_to_end_id="E2E-1", amount=Decimal("100.00"), currency="USD",
            creditor_name="Test", creditor_iban="GB29NWBK60161331926819",
            uetr="550e8400-e29b-41d4-a716-446655440000",
        )
        results = handler.validate(tc, [tx])
        failed_ids = [r.rule_id for r in results if not r.passed]
        assert "BR-CBPR-005" in failed_ids

    def test_validate_ok_with_bic(self):
        handler = CbprPlusHandler()
        tc = _tc(PaymentType.CBPR_PLUS, currency="USD")
        tx = Transaction(
            end_to_end_id="E2E-1", amount=Decimal("100.00"), currency="USD",
            creditor_name="Test", creditor_iban="GB29NWBK60161331926819",
            creditor_bic="BARCGB22XXX",
            uetr="550e8400-e29b-41d4-a716-446655440000",
        )
        results = handler.validate(tc, [tx])
        failed = [r for r in results if not r.passed]
        assert len(failed) == 0

    def test_charge_bearer_default(self):
        handler = CbprPlusHandler()
        assert handler.get_charge_bearer() == "SHAR"


# =========================================================================
# Registry
# =========================================================================

class TestHandlerRegistry:
    def test_get_handler_all_types(self):
        for pt in PaymentType:
            handler = get_handler(pt)
            assert handler.payment_type == pt
