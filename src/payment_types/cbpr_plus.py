"""CBPR+ Cross-Border Zahlung (Typ X)."""

from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.data_factory.iban import validate_iban
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult
from src.payment_types.base import PaymentTypeHandler
from src.validation.rule_catalog import check_rule as _check


class CbprPlusHandler(PaymentTypeHandler):
    @property
    def payment_type(self) -> PaymentType:
        return PaymentType.CBPR_PLUS

    def get_service_level(self) -> Optional[str]:
        return None

    def validate(
        self, testcase: TestCase, transactions: List[Transaction]
    ) -> List[ValidationResult]:
        results = []

        # BR-CBPR-002: SvcLvl ≠ SEPA
        svc_lvl = testcase.overrides.get("SvcLvl.Cd", "")
        results.append(_check(
            "BR-CBPR-002", svc_lvl != "SEPA",
            "SvcLvl ist 'SEPA'" if svc_lvl == "SEPA" else None,
        ))

        for tx in transactions:
            # BR-CBPR-001: Währung muss angegeben sein (prüfe tatsächliche Transaktionsdaten)
            results.append(_check(
                "BR-CBPR-001", bool(tx.currency),
                "Keine Währung angegeben" if not tx.currency else None,
            ))

            # BR-CBPR-005: Creditor-Agent Pflicht
            has_bic = bool(tx.creditor_bic)
            results.append(_check(
                "BR-CBPR-005", has_bic,
                (
                    "Creditor-Agent (BIC) fehlt. Bitte 'CdtrAgt.BICFI=<BIC>' "
                    "in 'Weitere Testdaten' angeben."
                ) if not has_bic else None,
            ))

        return results

    def generate_transactions(
        self, testcase: TestCase, factory: DataFactory
    ) -> List[Transaction]:
        transactions = []
        tx_inputs = testcase.transaction_inputs or [None]

        for tx_input in tx_inputs:
            creditor_iban = (
                (tx_input.creditor_iban if tx_input else None)
                or testcase.overrides.get("CdtrAcct.IBAN")
                or factory.generate_creditor_iban(PaymentType.CBPR_PLUS)
            )
            creditor_name = (
                (tx_input.creditor_name if tx_input else None)
                or testcase.overrides.get("Cdtr.Nm")
                or factory.generate_creditor_name()
            )
            creditor_bic = (
                (tx_input.creditor_bic if tx_input else None)
                or testcase.overrides.get("CdtrAgt.BICFI")
            )
            amount = (
                (tx_input.amount if tx_input else None)
                or testcase.amount
                or factory.generate_amount(PaymentType.CBPR_PLUS)
            )
            currency = (
                (tx_input.currency if tx_input else None)
                or testcase.currency
                or factory.generate_currency(PaymentType.CBPR_PLUS)
            )

            country = creditor_iban[:2] if len(creditor_iban) >= 2 else "GB"
            address = factory.generate_creditor_address(country)

            tx = Transaction(
                end_to_end_id=factory.generate_end_to_end_id(),
                amount=amount,
                currency=currency,
                creditor_name=creditor_name,
                creditor_iban=creditor_iban,
                creditor_address=address,
                creditor_bic=creditor_bic,
                overrides=testcase.overrides,
            )
            transactions.append(tx)
        return transactions
