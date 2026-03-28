"""CBPR+ Cross-Border Zahlung (Typ X)."""

from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult
from src.payment_types.base import PaymentTypeHandler
from src.validation.rule_catalog import check_rule as _check


class CbprPlusHandler(PaymentTypeHandler):
    @property
    def payment_type(self) -> PaymentType:
        return PaymentType.CBPR_PLUS

    def get_charge_bearer(self) -> Optional[str]:
        return "SHAR"

    def get_default_currency(self, factory: DataFactory) -> str:
        return factory.generate_currency(PaymentType.CBPR_PLUS)

    def get_address_country(self, creditor_iban: str) -> str:
        return creditor_iban[:2] if len(creditor_iban) >= 2 else "GB"

    def should_generate_uetr(self) -> bool:
        return True

    def generate_remittance(self, factory: DataFactory) -> Optional[Dict[str, str]]:
        return None  # CBPR+: keine automatische Referenz

    def validate(
        self, testcase: TestCase, transactions: List[Transaction]
    ) -> List[ValidationResult]:
        results = []

        svc_lvl = testcase.overrides.get("SvcLvl.Cd", "")
        results.append(_check(
            "BR-CBPR-002", svc_lvl != "SEPA",
            "SvcLvl ist 'SEPA'" if svc_lvl == "SEPA" else None,
        ))

        for tx in transactions:
            results.append(_check(
                "BR-CBPR-001", bool(tx.currency),
                "Keine Waehrung angegeben" if not tx.currency else None,
            ))

            results.append(_check(
                "BR-CBPR-005", bool(tx.creditor_bic),
                (
                    "Creditor-Agent (BIC) fehlt. Bitte 'CdtrAgt.BICFI=<BIC>' "
                    "in 'Weitere Testdaten' angeben."
                ) if not tx.creditor_bic else None,
            ))

            results.append(_check(
                "BR-CBPR-006", bool(tx.uetr),
                "UETR fehlt (UUIDv4 ist Pflicht fuer CBPR+)" if not tx.uetr else None,
            ))

        return results
