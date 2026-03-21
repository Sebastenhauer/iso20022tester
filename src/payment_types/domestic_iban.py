"""Domestic IBAN-Zahlung (Typ D mit regulärer IBAN)."""

from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.data_factory.iban import is_qr_iban, validate_iban
from src.data_factory.reference import validate_scor
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult
from src.payment_types.base import PaymentTypeHandler
from src.validation.rule_catalog import get_rule

DOMESTIC_MAX_AMOUNT = Decimal("9999999999.99")
DOMESTIC_MIN_AMOUNT = Decimal("0.01")


def _check(rule_id: str, passed: bool, details: str = None) -> ValidationResult:
    rule = get_rule(rule_id)
    return ValidationResult(
        rule_id=rule.rule_id,
        rule_description=rule.description,
        passed=passed,
        details=details,
    )


class DomesticIbanHandler(PaymentTypeHandler):
    @property
    def payment_type(self) -> PaymentType:
        return PaymentType.DOMESTIC_IBAN

    def get_defaults(self) -> Dict[str, str]:
        return {}

    def get_service_level(self) -> Optional[str]:
        return None

    def validate(
        self, testcase: TestCase, transactions: List[Transaction]
    ) -> List[ValidationResult]:
        results = []

        for tx in transactions:
            # BR-IBAN-004: Währung CHF
            results.append(_check(
                "BR-IBAN-004", tx.currency == "CHF",
                f"Währung ist '{tx.currency}'" if tx.currency != "CHF" else None,
            ))

        # BR-IBAN-005: SvcLvl ≠ SEPA
        svc_lvl = testcase.overrides.get("SvcLvl.Cd", "")
        results.append(_check(
            "BR-IBAN-005", svc_lvl != "SEPA",
            "SvcLvl ist 'SEPA'" if svc_lvl == "SEPA" else None,
        ))

        for tx in transactions:
            # BR-IBAN-006: Domestic-IBAN muss CH oder LI sein
            iban_country = tx.creditor_iban[:2].upper() if len(tx.creditor_iban) >= 2 else ""
            results.append(_check(
                "BR-IBAN-006", iban_country in ("CH", "LI"),
                f"IBAN Länderkennzeichen '{iban_country}' ist nicht CH/LI" if iban_country not in ("CH", "LI") else None,
            ))

            # BR-IBAN-001: Reguläre CH-IBAN (nicht QR)
            results.append(_check(
                "BR-IBAN-001", not is_qr_iban(tx.creditor_iban),
                f"IBAN '{tx.creditor_iban}' ist eine QR-IBAN" if is_qr_iban(tx.creditor_iban) else None,
            ))

            # BR-IBAN-002: Keine QRR
            ref_info = tx.remittance_info or {}
            ref_type = ref_info.get("type", "")
            results.append(_check(
                "BR-IBAN-002", ref_type != "QRR",
                "QRR-Referenz bei regulärer IBAN gefunden" if ref_type == "QRR" else None,
            ))

            # BR-IBAN-003: SCOR validieren wenn vorhanden
            ref_value = ref_info.get("value", "")
            if ref_type == "SCOR":
                results.append(_check(
                    "BR-IBAN-003", validate_scor(ref_value),
                    f"SCOR '{ref_value}' ist ungültig" if not validate_scor(ref_value) else None,
                ))

        return results

    def generate_transactions(
        self, testcase: TestCase, factory: DataFactory
    ) -> List[Transaction]:
        transactions = []
        for i in range(testcase.tx_count):
            creditor_iban = testcase.overrides.get(
                "CdtrAcct.IBAN",
                factory.generate_creditor_iban(PaymentType.DOMESTIC_IBAN),
            )
            creditor_name = testcase.overrides.get(
                "Cdtr.Nm",
                factory.generate_creditor_name(),
            )
            address = factory.generate_creditor_address("CH")

            ref = factory.generate_reference(PaymentType.DOMESTIC_IBAN)

            tx = Transaction(
                end_to_end_id=factory.generate_end_to_end_id(),
                amount=testcase.amount,
                currency=testcase.currency,
                creditor_name=creditor_name,
                creditor_iban=creditor_iban,
                creditor_address=address,
                remittance_info=ref,
                overrides=testcase.overrides,
            )
            transactions.append(tx)
        return transactions
