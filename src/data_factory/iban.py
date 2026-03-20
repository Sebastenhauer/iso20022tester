import random
import string

# IBAN-Längen nach Ländercode (Auswahl der häufigsten)
IBAN_LENGTHS = {
    "CH": 21,
    "LI": 21,
    "DE": 22,
    "AT": 20,
    "FR": 27,
    "IT": 27,
    "ES": 24,
    "NL": 18,
    "BE": 16,
    "LU": 20,
    "GB": 22,
    "IE": 22,
    "PT": 25,
    "FI": 18,
    "SE": 24,
    "DK": 18,
    "NO": 15,
    "PL": 28,
    "CZ": 24,
    "SK": 24,
    "HU": 28,
    "HR": 21,
    "BG": 22,
    "RO": 24,
    "CY": 28,
    "MT": 31,
    "LV": 21,
    "LT": 20,
    "EE": 20,
    "SI": 19,
    "GR": 27,
    "IS": 26,
    "US": 0,  # USA hat keine IBAN
}

# QR-IBAN IID-Bereich
QR_IID_MIN = 30000
QR_IID_MAX = 31999


def _mod97(iban_str: str) -> int:
    """Berechnet Mod-97 für eine IBAN-Zeichenkette."""
    numeric = ""
    for ch in iban_str:
        if ch.isdigit():
            numeric += ch
        else:
            numeric += str(ord(ch.upper()) - ord("A") + 10)
    return int(numeric) % 97


def calculate_iban_check_digits(country_code: str, bban: str) -> str:
    """Berechnet die IBAN-Prüfziffer (2 Stellen)."""
    temp = bban + country_code + "00"
    remainder = _mod97(temp)
    check = 98 - remainder
    return f"{check:02d}"


def validate_iban(iban: str) -> bool:
    """Prüft eine IBAN auf Mod-97-Validität."""
    iban_clean = iban.replace(" ", "").upper()
    if len(iban_clean) < 4:
        return False
    rearranged = iban_clean[4:] + iban_clean[:4]
    return _mod97(rearranged) == 1


def is_qr_iban(iban: str) -> bool:
    """Prüft ob eine IBAN eine QR-IBAN ist (IID 30000-31999)."""
    iban_clean = iban.replace(" ", "").upper()
    if not iban_clean.startswith("CH") and not iban_clean.startswith("LI"):
        return False
    if len(iban_clean) != 21:
        return False
    try:
        iid = int(iban_clean[4:9])
        return QR_IID_MIN <= iid <= QR_IID_MAX
    except ValueError:
        return False


def get_iban_length(country_code: str) -> int:
    """Gibt die erwartete IBAN-Länge für einen Ländercode zurück."""
    return IBAN_LENGTHS.get(country_code.upper(), 0)


def validate_iban_length(iban: str) -> bool:
    """Prüft ob die IBAN-Länge zum Ländercode passt."""
    iban_clean = iban.replace(" ", "").upper()
    if len(iban_clean) < 2:
        return False
    country = iban_clean[:2]
    expected = get_iban_length(country)
    if expected == 0:
        return False
    return len(iban_clean) == expected


def generate_ch_iban(rng: random.Random, qr: bool = False) -> str:
    """Generiert eine prüfziffervalide Schweizer IBAN.

    Args:
        rng: Random-Generator für Reproduzierbarkeit
        qr: True für QR-IBAN (IID 30000-31999), False für reguläre IBAN
    """
    if qr:
        iid = rng.randint(QR_IID_MIN, QR_IID_MAX)
    else:
        # IID außerhalb QR-Bereich: 0-29999 oder 32000-99999
        iid = rng.randint(0, 29999 + (99999 - 32000 + 1))
        if iid >= 30000:
            iid += (QR_IID_MAX - QR_IID_MIN + 1)

    # BBAN: 5-stellige IID + 12-stellige Kontonummer
    account = "".join([str(rng.randint(0, 9)) for _ in range(12)])
    bban = f"{iid:05d}{account}"

    check = calculate_iban_check_digits("CH", bban)
    return f"CH{check}{bban}"


def generate_iban(rng: random.Random, country_code: str = "DE") -> str:
    """Generiert eine prüfziffervalide IBAN für ein gegebenes Land."""
    country = country_code.upper()
    length = get_iban_length(country)
    if length == 0:
        raise ValueError(f"IBAN-Generierung für Land '{country}' nicht unterstützt.")

    bban_length = length - 4  # 2 Ländercode + 2 Prüfziffer
    bban = "".join([str(rng.randint(0, 9)) for _ in range(bban_length)])

    check = calculate_iban_check_digits(country, bban)
    return f"{country}{check}{bban}"


# Häufig verwendete SEPA-Länder
SEPA_COUNTRIES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE", "CH", "LI", "NO",
    "IS", "GB",
]
