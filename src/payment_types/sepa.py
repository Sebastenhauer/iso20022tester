"""SEPA Credit Transfer (Typ S)."""

from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.data_factory.iban import validate_iban
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult
from src.payment_types.base import PaymentTypeHandler
from src.validation.rule_catalog import check_rule as _check

SEPA_MAX_AMOUNT = Decimal("999999999.99")
SEPA_MIN_AMOUNT = Decimal("0.01")


class SepaHandler(PaymentTypeHandler):
    @property
    def payment_type(self) -> PaymentType:
        return PaymentType.SEPA

    def get_service_level(self) -> Optional[str]:
        return "SEPA"

    def get_charge_bearer(self) -> Optional[str]:
        return "SLEV"

    def get_default_currency(self, factory: DataFactory) -> str:
        return "EUR"

    def get_address_country(self, creditor_iban: str) -> str:
        return creditor_iban[:2] if len(creditor_iban) >= 2 else "DE"

    def get_max_creditor_name_length(self) -> Optional[int]:
        return 70

    def generate_remittance(self, factory: DataFactory) -> Optional[Dict[str, str]]:
        return None  # SEPA: keine automatische Referenz

    def validate(
        self, testcase: TestCase, transactions: List[Transaction]
    ) -> List[ValidationResult]:
        results = []

        for tx in transactions:
            results.append(_check(
                "BR-SEPA-001", tx.currency == "EUR",
                f"Währung ist '{tx.currency}'" if tx.currency != "EUR" else None,
            ))

            in_range = SEPA_MIN_AMOUNT <= tx.amount <= SEPA_MAX_AMOUNT
            results.append(_check(
                "BR-SEPA-006", in_range,
                f"Betrag ist {tx.amount}" if not in_range else None,
            ))

            results.append(_check(
                "BR-SEPA-004", len(tx.creditor_name) <= 70,
                f"Name hat {len(tx.creditor_name)} Zeichen" if len(tx.creditor_name) > 70 else None,
            ))

            results.append(_check(
                "BR-SEPA-005", validate_iban(tx.creditor_iban),
                f"IBAN '{tx.creditor_iban}' ist ungültig" if not validate_iban(tx.creditor_iban) else None,
            ))

        return results
