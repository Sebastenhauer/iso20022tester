"""Abstrakte Basisklasse für Zahlungstyp-Module."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, List, Optional

from src.data_factory.generator import DataFactory
from src.models.testcase import PaymentType, TestCase, Transaction, ValidationResult


class PaymentTypeHandler(ABC):
    """Basisklasse für zahlungstypspezifische Logik."""

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

    @abstractmethod
    def generate_transactions(
        self, testcase: TestCase, factory: DataFactory
    ) -> List[Transaction]:
        """Generiert Transaktionen für diesen Zahlungstyp."""
        ...

    def get_service_level(self) -> Optional[str]:
        """Gibt den Service-Level-Code zurück."""
        return None

    def get_charge_bearer(self) -> Optional[str]:
        """Gibt den Default Charge Bearer zurück."""
        return None
