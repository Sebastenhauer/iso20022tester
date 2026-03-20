"""SEPA Credit Transfer (Typ S)."""

from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.data_factory.iban import validate_iban
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult
from src.payment_types.base import PaymentTypeHandler
from src.validation.rule_catalog import get_rule

SEPA_MAX_AMOUNT = Decimal("999999999.99")
SEPA_MIN_AMOUNT = Decimal("0.01")


def _check(rule_id: str, passed: bool, details: str = None) -> ValidationResult:
    rule = get_rule(rule_id)
    return ValidationResult(
        rule_id=rule.rule_id,
        rule_description=rule.description,
        passed=passed,
        details=details,
    )


class SepaHandler(PaymentTypeHandler):
    @property
    def payment_type(self) -> PaymentType:
        return PaymentType.SEPA

    def get_defaults(self) -> Dict[str, str]:
        return {
            "SvcLvl.Cd": "SEPA",
            "ChrgBr": "SLEV",
        }

    def get_service_level(self) -> Optional[str]:
        return "SEPA"

    def get_charge_bearer(self) -> Optional[str]:
        return "SLEV"

    def validate(
        self, testcase: TestCase, transactions: List[Transaction]
    ) -> List[ValidationResult]:
        results = []

        for tx in transactions:
            # BR-SEPA-001: Währung EUR
            results.append(_check(
                "BR-SEPA-001", tx.currency == "EUR",
                f"Währung ist '{tx.currency}'" if tx.currency != "EUR" else None,
            ))

            # BR-SEPA-006: Betragsgrenzen
            in_range = SEPA_MIN_AMOUNT <= tx.amount <= SEPA_MAX_AMOUNT
            results.append(_check(
                "BR-SEPA-006", in_range,
                f"Betrag ist {tx.amount}" if not in_range else None,
            ))

            # BR-SEPA-004: Creditor-Name max 70
            results.append(_check(
                "BR-SEPA-004", len(tx.creditor_name) <= 70,
                f"Name hat {len(tx.creditor_name)} Zeichen" if len(tx.creditor_name) > 70 else None,
            ))

            # BR-SEPA-005: Creditor IBAN
            results.append(_check(
                "BR-SEPA-005", validate_iban(tx.creditor_iban),
                f"IBAN '{tx.creditor_iban}' ist ungültig" if not validate_iban(tx.creditor_iban) else None,
            ))

        return results

    def generate_transactions(
        self, testcase: TestCase, factory: DataFactory
    ) -> List[Transaction]:
        transactions = []
        for i in range(testcase.tx_count):
            creditor_iban = testcase.overrides.get(
                "CdtrAcct.IBAN",
                factory.generate_creditor_iban(PaymentType.SEPA),
            )
            creditor_name = testcase.overrides.get(
                "Cdtr.Nm",
                factory.generate_creditor_name(),
            )
            # SEPA: Name max 70 Zeichen
            if len(creditor_name) > 70:
                creditor_name = creditor_name[:70]

            address = factory.generate_creditor_address(
                creditor_iban[:2] if len(creditor_iban) >= 2 else "DE"
            )

            tx = Transaction(
                end_to_end_id=factory.generate_end_to_end_id(),
                amount=testcase.amount,
                currency=testcase.currency,
                creditor_name=creditor_name,
                creditor_iban=creditor_iban,
                creditor_address=address,
                creditor_bic=testcase.overrides.get("CdtrAgt.BICFI"),
                charge_bearer="SLEV",
                overrides=testcase.overrides,
            )
            transactions.append(tx)
        return transactions
