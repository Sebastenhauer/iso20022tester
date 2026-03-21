"""Domestic QR-Zahlung (Typ D mit QR-IBAN)."""

from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.data_factory.iban import is_qr_iban, validate_iban
from src.data_factory.reference import validate_qrr
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


class DomesticQrHandler(PaymentTypeHandler):
    @property
    def payment_type(self) -> PaymentType:
        return PaymentType.DOMESTIC_QR

    def get_defaults(self) -> Dict[str, str]:
        return {}

    def get_service_level(self) -> Optional[str]:
        return None

    def validate(
        self, testcase: TestCase, transactions: List[Transaction]
    ) -> List[ValidationResult]:
        results = []

        for tx in transactions:
            # BR-QR-004: Währung CHF/EUR
            results.append(_check(
                "BR-QR-004", tx.currency in ("CHF", "EUR"),
                f"Währung ist '{tx.currency}'" if tx.currency not in ("CHF", "EUR") else None,
            ))

        # BR-QR-005: SvcLvl ≠ SEPA
        svc_lvl = testcase.overrides.get("SvcLvl.Cd", "")
        results.append(_check(
            "BR-QR-005", svc_lvl != "SEPA",
            "SvcLvl ist 'SEPA'" if svc_lvl == "SEPA" else None,
        ))

        for tx in transactions:
            # BR-QR-001: QR-IBAN Pflicht
            results.append(_check(
                "BR-QR-001", is_qr_iban(tx.creditor_iban),
                f"IBAN '{tx.creditor_iban}' ist keine QR-IBAN" if not is_qr_iban(tx.creditor_iban) else None,
            ))

            # BR-QR-007: QR-IBAN muss CH oder LI sein
            iban_country = tx.creditor_iban[:2].upper() if len(tx.creditor_iban) >= 2 else ""
            results.append(_check(
                "BR-QR-007", iban_country in ("CH", "LI"),
                f"QR-IBAN Länderkennzeichen '{iban_country}' ist nicht CH/LI" if iban_country not in ("CH", "LI") else None,
            ))

            # BR-QR-002 & BR-QR-006: QRR Pflicht und Format
            ref_info = tx.remittance_info or {}
            ref_type = ref_info.get("type", "")
            ref_value = ref_info.get("value", "")

            results.append(_check(
                "BR-QR-002", ref_type == "QRR" and len(ref_value) > 0,
                "Keine QRR-Referenz vorhanden" if ref_type != "QRR" else None,
            ))

            if ref_type == "QRR":
                results.append(_check(
                    "BR-QR-006", validate_qrr(ref_value),
                    f"QRR '{ref_value}' ist ungültig" if not validate_qrr(ref_value) else None,
                ))

            # BR-QR-003: Keine SCOR bei QR-IBAN
            results.append(_check(
                "BR-QR-003", ref_type != "SCOR",
                "SCOR-Referenz bei QR-IBAN gefunden" if ref_type == "SCOR" else None,
            ))

        return results

    def generate_transactions(
        self, testcase: TestCase, factory: DataFactory
    ) -> List[Transaction]:
        transactions = []
        for i in range(testcase.tx_count):
            creditor_iban = testcase.overrides.get(
                "CdtrAcct.IBAN",
                factory.generate_creditor_iban(PaymentType.DOMESTIC_QR),
            )
            creditor_name = testcase.overrides.get(
                "Cdtr.Nm",
                factory.generate_creditor_name(),
            )
            address = factory.generate_creditor_address("CH")

            # QRR-Referenz generieren
            ref = factory.generate_reference(PaymentType.DOMESTIC_QR)

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
