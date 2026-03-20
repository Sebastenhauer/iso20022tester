"""Domestic IBAN-Zahlung (Typ D mit regulärer IBAN)."""

from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.data_factory.iban import is_qr_iban, validate_iban
from src.data_factory.reference import validate_scor
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult
from src.payment_types.base import PaymentTypeHandler

DOMESTIC_MAX_AMOUNT = Decimal("9999999999.99")
DOMESTIC_MIN_AMOUNT = Decimal("0.01")


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

        # BR-IBAN-004: Währung CHF (prüfe tatsächliche Transaktionswährung)
        for tx in transactions:
            results.append(ValidationResult(
                rule_id="BR-IBAN-004",
                rule_description="Währung muss CHF sein",
                passed=tx.currency == "CHF",
                details=f"Währung ist '{tx.currency}'" if tx.currency != "CHF" else None,
            ))

        # BR-IBAN-005: SvcLvl ≠ SEPA
        svc_lvl = testcase.overrides.get("SvcLvl.Cd", "")
        results.append(ValidationResult(
            rule_id="BR-IBAN-005",
            rule_description="SvcLvl darf nicht 'SEPA' sein",
            passed=svc_lvl != "SEPA",
            details="SvcLvl ist 'SEPA'" if svc_lvl == "SEPA" else None,
        ))

        for tx in transactions:
            # BR-IBAN-001: Reguläre CH-IBAN (nicht QR)
            results.append(ValidationResult(
                rule_id="BR-IBAN-001",
                rule_description="Creditor darf keine QR-IBAN haben",
                passed=not is_qr_iban(tx.creditor_iban),
                details=f"IBAN '{tx.creditor_iban}' ist eine QR-IBAN" if is_qr_iban(tx.creditor_iban) else None,
            ))

            # BR-IBAN-002: Keine QRR
            ref_info = tx.remittance_info or {}
            ref_type = ref_info.get("type", "")
            results.append(ValidationResult(
                rule_id="BR-IBAN-002",
                rule_description="QR-Referenz ist bei regulärer IBAN nicht zulässig",
                passed=ref_type != "QRR",
                details="QRR-Referenz bei regulärer IBAN gefunden" if ref_type == "QRR" else None,
            ))

            # BR-IBAN-003: SCOR validieren wenn vorhanden
            ref_value = ref_info.get("value", "")
            if ref_type == "SCOR":
                results.append(ValidationResult(
                    rule_id="BR-IBAN-003",
                    rule_description="SCOR-Referenz muss formal valide sein (RF + Mod-97)",
                    passed=validate_scor(ref_value),
                    details=f"SCOR '{ref_value}' ist ungültig" if not validate_scor(ref_value) else None,
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
