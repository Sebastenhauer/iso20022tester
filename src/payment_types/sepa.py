"""SEPA Credit Transfer (Typ S)."""

from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.data_factory.iban import validate_iban
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult
from src.payment_types.base import PaymentTypeHandler

SEPA_MAX_AMOUNT = Decimal("999999999.99")
SEPA_MIN_AMOUNT = Decimal("0.01")


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

        # BR-SEPA-001: Währung EUR (prüfe tatsächliche Transaktionswährung)
        for tx in transactions:
            results.append(ValidationResult(
                rule_id="BR-SEPA-001",
                rule_description="Währung muss EUR sein",
                passed=tx.currency == "EUR",
                details=f"Währung ist '{tx.currency}'" if tx.currency != "EUR" else None,
            ))

        # BR-SEPA-006: Betragsgrenzen
        for tx in transactions:
            results.append(ValidationResult(
                rule_id="BR-SEPA-006",
                rule_description="Betrag muss zwischen 0.01 und 999'999'999.99 liegen",
                passed=SEPA_MIN_AMOUNT <= tx.amount <= SEPA_MAX_AMOUNT,
                details=f"Betrag ist {tx.amount}" if not (SEPA_MIN_AMOUNT <= tx.amount <= SEPA_MAX_AMOUNT) else None,
            ))

        for tx in transactions:
            # BR-SEPA-004: Creditor-Name max 70
            results.append(ValidationResult(
                rule_id="BR-SEPA-004",
                rule_description="Creditor-Name max. 70 Zeichen",
                passed=len(tx.creditor_name) <= 70,
                details=f"Name hat {len(tx.creditor_name)} Zeichen" if len(tx.creditor_name) > 70 else None,
            ))

            # BR-SEPA-005: Creditor IBAN
            results.append(ValidationResult(
                rule_id="BR-SEPA-005",
                rule_description="Creditor muss eine gültige IBAN haben",
                passed=validate_iban(tx.creditor_iban),
                details=f"IBAN '{tx.creditor_iban}' ist ungültig" if not validate_iban(tx.creditor_iban) else None,
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
