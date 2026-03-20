"""Domestic QR-Zahlung (Typ D mit QR-IBAN)."""

from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.data_factory.iban import is_qr_iban, validate_iban
from src.data_factory.reference import validate_qrr
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult
from src.payment_types.base import PaymentTypeHandler

DOMESTIC_MAX_AMOUNT = Decimal("9999999999.99")
DOMESTIC_MIN_AMOUNT = Decimal("0.01")


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

        # BR-QR-004: Währung CHF/EUR (prüfe tatsächliche Transaktionswährung)
        for tx in transactions:
            results.append(ValidationResult(
                rule_id="BR-QR-004",
                rule_description="Währung muss CHF oder EUR sein",
                passed=tx.currency in ("CHF", "EUR"),
                details=f"Währung ist '{tx.currency}'" if tx.currency not in ("CHF", "EUR") else None,
            ))

        # BR-QR-005: SvcLvl ≠ SEPA
        svc_lvl = testcase.overrides.get("SvcLvl.Cd", "")
        results.append(ValidationResult(
            rule_id="BR-QR-005",
            rule_description="SvcLvl darf nicht 'SEPA' sein",
            passed=svc_lvl != "SEPA",
            details="SvcLvl ist 'SEPA'" if svc_lvl == "SEPA" else None,
        ))

        for tx in transactions:
            # BR-QR-001: QR-IBAN Pflicht
            results.append(ValidationResult(
                rule_id="BR-QR-001",
                rule_description="Creditor muss eine QR-IBAN haben (IID 30000-31999)",
                passed=is_qr_iban(tx.creditor_iban),
                details=f"IBAN '{tx.creditor_iban}' ist keine QR-IBAN" if not is_qr_iban(tx.creditor_iban) else None,
            ))

            # BR-QR-002 & BR-QR-006: QRR Pflicht und Format
            ref_info = tx.remittance_info or {}
            ref_type = ref_info.get("type", "")
            ref_value = ref_info.get("value", "")

            results.append(ValidationResult(
                rule_id="BR-QR-002",
                rule_description="Bei QR-IBAN muss eine QR-Referenz (QRR) vorhanden sein",
                passed=ref_type == "QRR" and len(ref_value) > 0,
                details="Keine QRR-Referenz vorhanden" if ref_type != "QRR" else None,
            ))

            if ref_type == "QRR":
                results.append(ValidationResult(
                    rule_id="BR-QR-006",
                    rule_description="QRR: 27 Stellen numerisch, Mod-10-Prüfziffer",
                    passed=validate_qrr(ref_value),
                    details=f"QRR '{ref_value}' ist ungültig" if not validate_qrr(ref_value) else None,
                ))

            # BR-QR-003: Keine SCOR bei QR-IBAN
            results.append(ValidationResult(
                rule_id="BR-QR-003",
                rule_description="SCOR-Referenz ist bei QR-IBAN nicht zulässig",
                passed=ref_type != "SCOR",
                details="SCOR-Referenz bei QR-IBAN gefunden" if ref_type == "SCOR" else None,
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
