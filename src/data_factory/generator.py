import random
import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional

from faker import Faker

from src.data_factory.iban import (
    generate_ch_iban,
    generate_iban,
    generate_non_iban_account,
    is_non_iban_country,
    IBAN_LENGTHS,
    SEPA_COUNTRIES,
)
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

    # Faker-Locale-Mapping für länderspezifische Adressdaten
    _FAKER_LOCALES = {
        "CH": "de_CH", "DE": "de_DE", "AT": "de_AT", "FR": "fr_FR",
        "IT": "it_IT", "ES": "es_ES", "PT": "pt_PT", "NL": "nl_NL",
        "BE": "nl_BE", "GB": "en_GB", "IE": "en_IE", "DK": "da_DK",
        "SE": "sv_SE", "NO": "no_NO", "FI": "fi_FI", "PL": "pl_PL",
        "CZ": "cs_CZ", "HU": "hu_HU", "RO": "ro_RO", "BG": "bg_BG",
        "HR": "hr_HR", "SI": "sl_SI", "EE": "et_EE", "LV": "lv_LV",
        "LT": "lt_LT", "GR": "el_GR", "TR": "tr_TR",
        "US": "en_US", "CA": "en_CA", "JP": "ja_JP", "AU": "en_AU",
        "NZ": "en_NZ", "BR": "pt_BR", "MX": "es_MX", "IN": "en_IN",
        "CN": "zh_CN", "SG": "en_US", "ZA": "en_US",
    }

    def generate_creditor_address(self, country: str = "CH") -> Dict[str, str]:
        """Generiert eine strukturierte Creditor-Adresse.

        Verwendet länderspezifische Faker-Locales und validiert die
        generierte PLZ gegen das Länderformat. Wendet Adress-Anreicherung an.
        """
        locale = self._FAKER_LOCALES.get(country, "en_US")
        try:
            fake = Faker(locale)
        except AttributeError:
            fake = Faker("en_US")
        if self.seed is not None:
            Faker.seed(self.seed + hash(country) % 10000)

        # Fallback-Faker (Latin-1 sicher) fuer Laender deren Locale
        # Strings produziert, die nach SPS-Charset-Sanitize leer werden.
        fake_fallback = Faker("en_US")

        def _safe(raw: str, gen_fallback, max_len: int = 70) -> str:
            """Sanitized + truncated; falls leer, Fallback aus en_US Faker."""
            val = sanitize_sps_charset(raw or "")
            if not val:
                val = sanitize_sps_charset(gen_fallback()) or "N/A"
            return val[:max_len]

        postcode = fake.postcode() or ""

        # PLZ gegen Länderformat validieren; bei Mismatch generische PLZ erzeugen
        from src.validation.address_validator import COUNTRY_FORMATS, enrich_address
        fmt = COUNTRY_FORMATS.get(country)
        if fmt and fmt.postal_code_regex:
            import re as _re
            if not _re.match(fmt.postal_code_regex, postcode):
                postcode = fmt.postal_code_example

        address = {
            "StrtNm": _safe(fake.street_name(), fake_fallback.street_name, 70),
            "BldgNb": str(self.rng.randint(1, 200)),
            "TwnNm": _safe(fake.city(), fake_fallback.city, 35),
            "Ctry": country,
        }
        # Nur setzen wenn nicht-leer: Laender wie HK/AE haben keine PLZ
        if postcode:
            address["PstCd"] = postcode

        address, _ = enrich_address(address)
        return address

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
            # CBPR+: Zufälliges Land mit IBAN-Support außerhalb SEPA
            # Länder ohne Postleitzahlensystem (HK, AE) ausschliessen,
            # da CBPR+/CGI-MP strukturierte Adresse inkl. PstCd verlangen.
            cbpr_iban_countries = [
                c for c, l in IBAN_LENGTHS.items()
                if l > 0
                and c not in SEPA_COUNTRIES
                and c not in ("CH", "LI", "HK", "AE")
            ]
            if cbpr_iban_countries:
                country = self.rng.choice(cbpr_iban_countries)
                return generate_iban(self.rng, country)
            return generate_iban(self.rng, "GB")
        return generate_ch_iban(self.rng, qr=False)

    def generate_creditor_account(
        self, payment_type: PaymentType
    ) -> Dict[str, Optional[str]]:
        """Generiert Creditor-Kontodaten: IBAN oder Non-IBAN je nach Zahlungstyp.

        Returns:
            Dict mit Keys: iban, account_id, account_scheme, country
        """
        if payment_type == PaymentType.CBPR_PLUS:
            # 30% Wahrscheinlichkeit für Non-IBAN-Land bei CBPR+
            non_iban_countries = [
                c for c, l in IBAN_LENGTHS.items() if l == 0
            ]
            use_non_iban = self.rng.random() < 0.3 and non_iban_countries

            if use_non_iban:
                country = self.rng.choice(non_iban_countries)
                account_id = generate_non_iban_account(self.rng, country)
                return {
                    "iban": None,
                    "account_id": account_id,
                    "account_scheme": "BBAN",
                    "country": country,
                }

        # Standard: IBAN generieren
        iban = self.generate_creditor_iban(payment_type)
        country = iban[:2] if len(iban) >= 2 else "CH"
        return {
            "iban": iban,
            "account_id": None,
            "account_scheme": None,
            "country": country,
        }

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

    def generate_debtor_name(self) -> str:
        """Generiert einen Debtor-Namen."""
        name = self.faker.company()
        return sanitize_sps_charset(name)

    def generate_currency(self, payment_type: PaymentType) -> str:
        """Gibt die Default-Währung für einen Zahlungstyp zurück."""
        if payment_type == PaymentType.SEPA:
            return "EUR"
        elif payment_type in (PaymentType.DOMESTIC_QR, PaymentType.DOMESTIC_IBAN):
            return "CHF"
        elif payment_type == PaymentType.CBPR_PLUS:
            return self.rng.choice(["USD", "GBP", "JPY", "EUR"])
        return "CHF"

    def generate_amount(self, payment_type: PaymentType, instant: bool = False) -> Decimal:
        """Generiert einen gültigen Betrag je nach Zahlungstyp."""
        if payment_type == PaymentType.SEPA:
            if instant:
                max_amount = Decimal("100000")
            else:
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
