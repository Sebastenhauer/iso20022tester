import random
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional

from faker import Faker

from src.data_factory.iban import generate_ch_iban, generate_iban, SEPA_COUNTRIES
from src.data_factory.reference import generate_qrr, generate_scor
from src.models.testcase import PaymentType

# SPS-Zeichensatz (Latin-1 Subset)
SPS_CHARSET_PATTERN = re.compile(r"^[a-zA-Z0-9 /\-?:().,'+]*$")

# Zeichen-Ersetzungstabelle für Umlaute etc.
_CHAR_REPLACEMENTS = {
    "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    "ß": "ss", "é": "e", "è": "e", "ê": "e", "à": "a", "â": "a",
    "ù": "u", "û": "u", "î": "i", "ï": "i", "ô": "o", "ç": "c",
    "ñ": "n", "á": "a", "í": "i", "ó": "o", "ú": "u",
}


def sanitize_sps_charset(text: str) -> str:
    """Ersetzt ungültige Zeichen durch SPS-konforme Äquivalente."""
    result = []
    for ch in text:
        if ch in _CHAR_REPLACEMENTS:
            result.append(_CHAR_REPLACEMENTS[ch])
        elif SPS_CHARSET_PATTERN.match(ch):
            result.append(ch)
        else:
            # Unbekanntes Zeichen entfernen
            pass
    return "".join(result)


def validate_sps_charset(text: str) -> bool:
    """Prüft ob ein Text dem SPS-Zeichensatz entspricht."""
    return bool(SPS_CHARSET_PATTERN.match(text))


class DataFactory:
    """Generiert valide Testdaten basierend auf faker und einem globalen Seed."""

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.faker = Faker("de_CH")
        if seed is not None:
            Faker.seed(seed)

    def generate_msg_id(self) -> str:
        """Generiert eine eindeutige MsgId."""
        short_uuid = uuid.UUID(int=self.rng.getrandbits(128)).hex[:12]
        return f"MSG-{short_uuid}"

    def generate_pmt_inf_id(self) -> str:
        """Generiert eine eindeutige PmtInfId."""
        short_uuid = uuid.UUID(int=self.rng.getrandbits(128)).hex[:12]
        return f"PMT-{short_uuid}"

    def generate_end_to_end_id(self) -> str:
        """Generiert eine eindeutige EndToEndId."""
        short_uuid = uuid.UUID(int=self.rng.getrandbits(128)).hex[:12]
        return f"E2E-{short_uuid}"

    def generate_creditor_name(self) -> str:
        """Generiert einen Creditor-Namen."""
        name = self.faker.company()
        return sanitize_sps_charset(name)

    def generate_creditor_address(self, country: str = "CH") -> Dict[str, str]:
        """Generiert eine strukturierte Creditor-Adresse."""
        if country == "CH":
            fake = Faker("de_CH")
        elif country == "DE":
            fake = Faker("de_DE")
        elif country == "FR":
            fake = Faker("fr_FR")
        else:
            fake = Faker("en_US")
        if self.seed is not None:
            Faker.seed(self.seed + hash(country) % 10000)

        return {
            "StrtNm": sanitize_sps_charset(fake.street_name()),
            "BldgNb": str(self.rng.randint(1, 200)),
            "PstCd": fake.postcode(),
            "TwnNm": sanitize_sps_charset(fake.city()),
            "Ctry": country,
        }

    def generate_creditor_iban(self, payment_type: PaymentType) -> str:
        """Generiert eine passende Creditor-IBAN je nach Zahlungstyp."""
        if payment_type == PaymentType.DOMESTIC_QR:
            return generate_ch_iban(self.rng, qr=True)
        elif payment_type == PaymentType.DOMESTIC_IBAN:
            return generate_ch_iban(self.rng, qr=False)
        elif payment_type == PaymentType.SEPA:
            country = self.rng.choice([c for c in SEPA_COUNTRIES if c != "CH"])
            return generate_iban(self.rng, country)
        elif payment_type == PaymentType.CBPR_PLUS:
            return generate_iban(self.rng, "GB")
        return generate_ch_iban(self.rng, qr=False)

    def generate_reference(self, payment_type: PaymentType) -> Optional[Dict[str, str]]:
        """Generiert eine Zahlungsreferenz je nach Zahlungstyp."""
        if payment_type == PaymentType.DOMESTIC_QR:
            return {"type": "QRR", "value": generate_qrr(self.rng)}
        elif payment_type == PaymentType.DOMESTIC_IBAN:
            # SCOR ist optional bei Domestic-IBAN
            if self.rng.random() > 0.5:
                return {"type": "SCOR", "value": generate_scor(self.rng)}
            return None
        return None

    def generate_amount(self, payment_type: PaymentType, currency: str) -> Decimal:
        """Generiert einen gültigen Betrag je nach Zahlungstyp."""
        if payment_type == PaymentType.SEPA:
            max_amount = Decimal("999999999.99")
        else:
            max_amount = Decimal("9999999999.99")

        # Realistischer Bereich
        amount = Decimal(str(round(self.rng.uniform(10.0, 50000.0), 2)))
        return min(amount, max_amount)

    def generate_uuid_short(self) -> str:
        """Generiert eine kurze UUID für Dateinamen."""
        return uuid.UUID(int=self.rng.getrandbits(128)).hex[:8]

    def get_next_business_day(self, payment_type: PaymentType) -> date:
        """Berechnet den nächsten Bankarbeitstag."""
        try:
            if payment_type == PaymentType.SEPA:
                from workalendar.europe import EuropeanCentralBank
                cal = EuropeanCentralBank()
            else:
                from workalendar.europe import Switzerland
                cal = Switzerland()

            current = date.today()
            return cal.add_working_days(current, 1)
        except ImportError:
            # Fallback: nächster Werktag ohne Feiertagsprüfung
            from datetime import timedelta
            current = date.today() + timedelta(days=1)
            while current.weekday() >= 5:
                current += timedelta(days=1)
            return current
