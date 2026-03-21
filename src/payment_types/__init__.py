"""Payment-Type-Handler und zentrales Registry."""

from src.models.testcase import PaymentType
from src.payment_types.base import PaymentTypeHandler
from src.payment_types.cbpr_plus import CbprPlusHandler
from src.payment_types.domestic_iban import DomesticIbanHandler
from src.payment_types.domestic_qr import DomesticQrHandler
from src.payment_types.sepa import SepaHandler


def get_handler(payment_type: PaymentType) -> PaymentTypeHandler:
    """Gibt den passenden Handler für einen Zahlungstyp zurück."""
    handlers = {
        PaymentType.SEPA: SepaHandler(),
        PaymentType.DOMESTIC_QR: DomesticQrHandler(),
        PaymentType.DOMESTIC_IBAN: DomesticIbanHandler(),
        PaymentType.CBPR_PLUS: CbprPlusHandler(),
    }
    return handlers[payment_type]
