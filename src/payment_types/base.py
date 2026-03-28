"""Abstrakte Basisklasse und TransactionBuilder fuer Zahlungstyp-Module."""

import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.models.testcase import (
    PaymentType,
    TestCase,
    Transaction,
    TransactionInput,
    ValidationResult,
)


class PaymentTypeHandler(ABC):
    """Basisklasse fuer zahlungstypspezifische Logik.

    Subklassen muessen payment_type und validate() implementieren.
    generate_transactions() nutzt den TransactionBuilder und kann
    ueberschrieben werden fuer typ-spezifische Anpassungen.
    """

    @property
    @abstractmethod
    def payment_type(self) -> PaymentType:
        ...

    @abstractmethod
    def validate(
        self, testcase: TestCase, transactions: List[Transaction]
    ) -> List[ValidationResult]:
        """Validiert zahlungstypspezifische Business Rules."""
        ...

    def get_service_level(self) -> Optional[str]:
        return None

    def get_charge_bearer(self) -> Optional[str]:
        return None

    def get_default_currency(self, factory: DataFactory) -> str:
        """Default-Waehrung fuer diesen Zahlungstyp."""
        return "CHF"

    def get_address_country(self, creditor_iban: str) -> str:
        """Land fuer die generierte Creditor-Adresse."""
        return "CH"

    def get_max_creditor_name_length(self) -> Optional[int]:
        """Max. Laenge des Creditor-Namens (None = kein Limit)."""
        return None

    def generate_remittance(self, factory: DataFactory) -> Optional[Dict[str, str]]:
        """Generiert typ-spezifische Zahlungsreferenz."""
        return factory.generate_reference(self.payment_type)

    def should_generate_uetr(self) -> bool:
        """Ob eine UETR (UUIDv4) generiert werden soll."""
        return False

    def build_remittance_from_input(self, ustrd: Optional[str]) -> Optional[Dict[str, str]]:
        """Baut Remittance-Info aus User-Input (Verwendungszweck)."""
        if ustrd:
            return {"type": "USTRD", "value": ustrd}
        return None

    def generate_transactions(
        self, testcase: TestCase, factory: DataFactory
    ) -> List[Transaction]:
        """Generiert Transaktionen. Nutzt den gemeinsamen TransactionBuilder."""
        builder = TransactionBuilder(factory, testcase, self)
        return builder.build_all()


class TransactionBuilder:
    """Baut Transaktionen mit einheitlicher Fallback-Logik.

    Vorrang: TransactionInput > TestCase.overrides > TestCase-Felder > Auto-Generierung
    """

    def __init__(self, factory: DataFactory, testcase: TestCase, handler: PaymentTypeHandler):
        self.factory = factory
        self.testcase = testcase
        self.handler = handler

    def build_all(self) -> List[Transaction]:
        tx_inputs = self.testcase.transaction_inputs or [None]
        return [self._build_one(tx_input) for tx_input in tx_inputs]

    def _build_one(self, tx_input: Optional[TransactionInput]) -> Transaction:
        creditor_iban = self._resolve_str(
            tx_input, "creditor_iban", "CdtrAcct.IBAN",
            lambda: self.factory.generate_creditor_iban(self.handler.payment_type),
        )
        creditor_name = self._resolve_str(
            tx_input, "creditor_name", "Cdtr.Nm",
            self.factory.generate_creditor_name,
        )
        max_len = self.handler.get_max_creditor_name_length()
        if max_len and len(creditor_name) > max_len:
            creditor_name = creditor_name[:max_len]

        creditor_bic = self._resolve_str(
            tx_input, "creditor_bic", "CdtrAgt.BICFI", lambda: None,
        )
        amount = self._resolve_amount(tx_input)
        currency = self._resolve_currency(tx_input)

        country = self.handler.get_address_country(creditor_iban)
        address = self.factory.generate_creditor_address(country)

        remittance = self._resolve_remittance(tx_input)

        return Transaction(
            end_to_end_id=self.factory.generate_end_to_end_id(),
            uetr=str(uuid.uuid4()) if self.handler.should_generate_uetr() else None,
            amount=amount,
            currency=currency,
            creditor_name=creditor_name,
            creditor_iban=creditor_iban,
            creditor_address=address,
            creditor_bic=creditor_bic,
            charge_bearer=self.handler.get_charge_bearer(),
            remittance_info=remittance,
            overrides=self.testcase.overrides,
        )

    def _resolve_str(
        self,
        tx_input: Optional[TransactionInput],
        field: str,
        override_key: str,
        generator,
    ) -> Optional[str]:
        """Resolve: tx_input.field > testcase.overrides[key] > generator()"""
        val = getattr(tx_input, field, None) if tx_input else None
        return val or self.testcase.overrides.get(override_key) or generator()

    def _resolve_amount(self, tx_input: Optional[TransactionInput]):
        return (
            (tx_input.amount if tx_input else None)
            or self.testcase.amount
            or self.factory.generate_amount(self.handler.payment_type)
        )

    def _resolve_currency(self, tx_input: Optional[TransactionInput]) -> str:
        return (
            (tx_input.currency if tx_input else None)
            or self.testcase.currency
            or self.handler.get_default_currency(self.factory)
        )

    def _resolve_remittance(self, tx_input: Optional[TransactionInput]) -> Optional[Dict[str, str]]:
        ustrd = tx_input.remittance_info if tx_input else None
        if ustrd:
            return self.handler.build_remittance_from_input(ustrd)
        return self.handler.generate_remittance(self.factory)
