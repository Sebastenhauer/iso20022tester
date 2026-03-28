"""Domestic IBAN-Zahlung (Typ D mit regulärer IBAN)."""

from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.data_factory.iban import is_qr_iban
from src.data_factory.reference import validate_scor
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult
from src.payment_types.base import PaymentTypeHandler
from src.validation.rule_catalog import check_rule as _check


class DomesticIbanHandler(PaymentTypeHandler):
    @property
    def payment_type(self) -> PaymentType:
        return PaymentType.DOMESTIC_IBAN

    def get_default_currency(self, factory: DataFactory) -> str:
        return "CHF"

    def validate(
        self, testcase: TestCase, transactions: List[Transaction]
    ) -> List[ValidationResult]:
        results = []

        for tx in transactions:
            results.append(_check(
                "BR-IBAN-004", tx.currency == "CHF",
                f"Währung ist '{tx.currency}'" if tx.currency != "CHF" else None,
            ))

        svc_lvl = testcase.overrides.get("SvcLvl.Cd", "")
        results.append(_check(
            "BR-IBAN-005", svc_lvl != "SEPA",
            "SvcLvl ist 'SEPA'" if svc_lvl == "SEPA" else None,
        ))

        for tx in transactions:
            iban_country = tx.creditor_iban[:2].upper() if len(tx.creditor_iban) >= 2 else ""
            results.append(_check(
                "BR-IBAN-006", iban_country in ("CH", "LI"),
                f"IBAN Länderkennzeichen '{iban_country}' ist nicht CH/LI" if iban_country not in ("CH", "LI") else None,
            ))

            results.append(_check(
                "BR-IBAN-001", not is_qr_iban(tx.creditor_iban),
                f"IBAN '{tx.creditor_iban}' ist eine QR-IBAN" if is_qr_iban(tx.creditor_iban) else None,
            ))

            ref_info = tx.remittance_info or {}
            ref_type = ref_info.get("type", "")
            results.append(_check(
                "BR-IBAN-002", ref_type != "QRR",
                "QRR-Referenz bei regulärer IBAN gefunden" if ref_type == "QRR" else None,
            ))

            ref_value = ref_info.get("value", "")
            if ref_type == "SCOR":
                results.append(_check(
                    "BR-IBAN-003", validate_scor(ref_value),
                    f"SCOR '{ref_value}' ist ungültig" if not validate_scor(ref_value) else None,
                ))

        return results
