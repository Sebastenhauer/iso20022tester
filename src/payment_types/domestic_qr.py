"""Domestic QR-Zahlung (Typ D mit QR-IBAN)."""

from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.data_factory.iban import is_qr_iban
from src.data_factory.reference import validate_qrr
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult
from src.payment_types.base import PaymentTypeHandler
from src.validation.rule_catalog import check_rule as _check


class DomesticQrHandler(PaymentTypeHandler):
    @property
    def payment_type(self) -> PaymentType:
        return PaymentType.DOMESTIC_QR

    def get_default_currency(self, factory: DataFactory) -> str:
        return "CHF"

    def build_remittance_from_input(self, ustrd: Optional[str]) -> Optional[Dict[str, str]]:
        # QR-Zahlungen: User-Input als USTRD ignorieren, immer QRR generieren
        return None

    def validate(
        self, testcase: TestCase, transactions: List[Transaction]
    ) -> List[ValidationResult]:
        results = []

        for tx in transactions:
            results.append(_check(
                "BR-QR-004", tx.currency in ("CHF", "EUR"),
                f"Waehrung ist '{tx.currency}'" if tx.currency not in ("CHF", "EUR") else None,
            ))

        svc_lvl = testcase.overrides.get("SvcLvl.Cd", "")
        results.append(_check(
            "BR-QR-005", svc_lvl != "SEPA",
            "SvcLvl ist 'SEPA'" if svc_lvl == "SEPA" else None,
        ))

        for tx in transactions:
            results.append(_check(
                "BR-QR-001", is_qr_iban(tx.creditor_iban),
                f"IBAN '{tx.creditor_iban}' ist keine QR-IBAN" if not is_qr_iban(tx.creditor_iban) else None,
            ))

            iban_country = tx.creditor_iban[:2].upper() if len(tx.creditor_iban) >= 2 else ""
            results.append(_check(
                "BR-QR-007", iban_country in ("CH", "LI"),
                f"QR-IBAN Laenderkennzeichen '{iban_country}' ist nicht CH/LI" if iban_country not in ("CH", "LI") else None,
            ))

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
                    f"QRR '{ref_value}' ist ungueltig" if not validate_qrr(ref_value) else None,
                ))

            results.append(_check(
                "BR-QR-003", ref_type != "SCOR",
                "SCOR-Referenz bei QR-IBAN gefunden" if ref_type == "SCOR" else None,
            ))

        return results
