import random
import string

# BBAN-Formate nach SWIFT IBAN Registry (ISO 13616).
# Jeder Eintrag: (IBAN-Gesamtlänge, BBAN-Format-String).
# Format-Notation: Zahl + Typ-Buchstabe, wobei:
#   n = numerisch (0-9)
#   a = alphabetisch (A-Z)
#   c = alphanumerisch (A-Z, 0-9)
# Beispiel: "8n10n" = 8 numerische + 10 numerische Zeichen
IBAN_FORMATS = {
    # =========================================================================
    # Europa — SEPA-Kernländer
    # =========================================================================
    "CH": (21, "5n12c"),           # Schweiz
    "LI": (21, "5n12c"),           # Liechtenstein
    "DE": (22, "8n10n"),           # Deutschland
    "AT": (20, "5n11n"),           # Österreich
    "FR": (27, "5n5n11c2n"),       # Frankreich
    "IT": (27, "1a5n5n12c"),       # Italien
    "ES": (24, "4n4n1n1n10n"),     # Spanien
    "NL": (18, "4a10n"),           # Niederlande
    "BE": (16, "3n7n2n"),          # Belgien
    "LU": (20, "3n13c"),           # Luxemburg
    "GB": (22, "4a6n8n"),          # Grossbritannien
    "IE": (22, "4a6n8n"),          # Irland
    "PT": (25, "4n4n11n2n"),       # Portugal
    "FI": (18, "6n7n1n"),          # Finnland
    "SE": (24, "3n16n1n"),         # Schweden
    "DK": (18, "4n9n1n"),          # Dänemark
    "NO": (15, "4n6n1n"),          # Norwegen
    "PL": (28, "8n16n"),           # Polen
    "CZ": (24, "4n6n10n"),         # Tschechien
    "SK": (24, "4n6n10n"),         # Slowakei
    "HU": (28, "3n4n1n15n1n"),     # Ungarn
    "HR": (21, "7n10n"),           # Kroatien
    "BG": (22, "4a4n2n8c"),        # Bulgarien
    "RO": (24, "4a16c"),           # Rumänien
    "CY": (28, "3n5n16c"),         # Zypern
    "MT": (31, "4a5n18c"),         # Malta
    "LV": (21, "4a13c"),           # Lettland
    "LT": (20, "5n11n"),           # Litauen
    "EE": (20, "2n2n11n1n"),       # Estland
    "SI": (19, "5n8n2n"),          # Slowenien
    "GR": (27, "3n4n16c"),         # Griechenland
    "IS": (26, "4n2n6n10n"),       # Island

    # =========================================================================
    # Europa — weitere SEPA-Teilnehmer / EWR
    # =========================================================================
    "AD": (24, "4n4n12c"),         # Andorra
    "MC": (27, "5n5n11c2n"),       # Monaco (FR-Format)
    "SM": (27, "1a5n5n12c"),       # San Marino (IT-Format)
    "VA": (22, "3n15n"),           # Vatikan
    "GI": (23, "4a15c"),           # Gibraltar
    "FO": (18, "4n9n1n"),          # Färöer (DK-Format)
    "GL": (18, "4n9n1n"),          # Grönland (DK-Format)

    # =========================================================================
    # Europa — Nicht-EU/SEPA
    # =========================================================================
    "AL": (28, "8n16c"),           # Albanien
    "RS": (22, "3n13n2n"),         # Serbien
    "BA": (20, "3n3n8n2n"),        # Bosnien
    "ME": (22, "3n13n2n"),         # Montenegro
    "MK": (19, "3n10c2n"),         # Nordmazedonien
    # "XK" (Kosovo) bewusst entfernt: XK ist ein SWIFT-User-assigned
    # Laendercode, aber nicht in ISO 3166-1 alpha-2 enthalten. Strikte
    # Validatoren (z.B. Swiss SPS Validator, GEFEG.FX) lehnen es ab
    # ("BE09: Kein gueltiger Laender-Code gemaess ISO 3166"). Wenn ein
    # Anwender XK explizit braucht, muss er die IBAN manuell im Excel
    # angeben.
    "MD": (24, "2c18c"),           # Moldawien
    "UA": (29, "6n19n"),           # Ukraine
    "BY": (28, "4c4n16c"),         # Belarus

    # =========================================================================
    # Naher Osten
    # =========================================================================
    "SA": (24, "2n18c"),           # Saudi-Arabien
    "AE": (23, "3n16n"),           # VAE
    "QA": (29, "4a21c"),           # Katar
    "BH": (22, "4a14c"),           # Bahrain
    "KW": (30, "4a22c"),           # Kuwait
    "IL": (23, "3n3n13n"),         # Israel
    "TR": (26, "5n1n16c"),         # Türkei
    "JO": (30, "4a4n18c"),         # Jordanien
    "LB": (28, "4n20c"),           # Libanon
    "PS": (29, "4a21c"),           # Palästina
    "IQ": (23, "4a3n12n"),         # Irak
    "OM": (23, "3n16c"),           # Oman
    "YE": (30, "4a4n18n"),         # Jemen

    # =========================================================================
    # Afrika
    # =========================================================================
    "TN": (24, "2n3n13n2n"),       # Tunesien
    "MU": (30, "4a2n2n12n3n3a"),   # Mauritius (endet auf Währungscode)
    "MR": (27, "5n5n11n2n"),       # Mauretanien
    "SC": (31, "4a2n2n16n3a"),     # Seychellen (endet auf Währungscode)
    "ST": (25, "4n4n11n2n"),       # São Tomé und Príncipe
    "EG": (29, "4n4n17n"),         # Ägypten
    "LY": (25, "3n3n15n"),         # Libyen
    "SD": (18, "2n12n"),           # Sudan
    "BI": (27, "5n5n11n2n"),       # Burundi
    "DJ": (27, "5n5n11n2n"),       # Dschibuti
    "SO": (23, "4n3n12n"),         # Somalia

    # =========================================================================
    # Westafrika / Zentralafrika (Experimentelle IBAN-Länder)
    # =========================================================================
    "AO": (25, "21n"),             # Angola
    "BF": (28, "2c22n"),           # Burkina Faso
    "BJ": (28, "2c22n"),           # Benin
    "CF": (27, "23n"),             # Zentralafrika
    "CG": (27, "23n"),             # Kongo
    "CI": (28, "2c22n"),           # Elfenbeinküste
    "CM": (27, "23n"),             # Kamerun
    "CV": (25, "21n"),             # Kap Verde
    "DZ": (26, "22n"),             # Algerien (experimentell)
    "GA": (27, "23n"),             # Gabun
    "GQ": (27, "23n"),             # Äquatorialguinea
    "GW": (25, "2c19n"),           # Guinea-Bissau
    "KM": (27, "23n"),             # Komoren
    "MA": (28, "24n"),             # Marokko
    "MG": (27, "23n"),             # Madagaskar
    "ML": (28, "2c22n"),           # Mali
    "MZ": (25, "21n"),             # Mosambik
    "NE": (28, "2c22n"),           # Niger
    "SN": (28, "2c22n"),           # Senegal
    "TD": (27, "23n"),             # Tschad
    "TG": (28, "2c22n"),           # Togo

    # =========================================================================
    # Amerika
    # =========================================================================
    "BR": (29, "8n5n10n1a1c"),     # Brasilien (Kontotyp + Inhaber)
    "CR": (22, "4n14n"),           # Costa Rica
    "DO": (28, "4c20n"),           # Dominikanische Republik
    "GT": (28, "4c20n"),           # Guatemala
    "SV": (28, "4a20n"),           # El Salvador
    "LC": (32, "4a24c"),           # St. Lucia
    "VG": (24, "4a16n"),           # Brit. Jungferninseln
    "NI": (28, "4a20n"),           # Nicaragua
    "HN": (28, "4a20n"),           # Honduras
    "FK": (18, "2a12n"),           # Falklandinseln

    # =========================================================================
    # Asien / Kaukasus / Zentralasien
    # =========================================================================
    "PK": (24, "4a16c"),           # Pakistan
    "KZ": (20, "3n13c"),           # Kasachstan
    "GE": (22, "2a16n"),           # Georgien
    "AZ": (28, "4a20c"),           # Aserbaidschan
    "TL": (23, "3n14n2n"),         # Timor-Leste
    "MN": (20, "4n12n"),           # Mongolei
    "RU": (33, "9n5n15c"),         # Russland
    "IR": (26, "22n"),             # Iran (experimentell)

    # =========================================================================
    # Überseegebiete (Frankreich — nutzen FR-Format, gleiche Länge 27)
    # =========================================================================
    "GF": (27, "5n5n11c2n"),       # Französisch-Guayana
    "GP": (27, "5n5n11c2n"),       # Guadeloupe
    "MQ": (27, "5n5n11c2n"),       # Martinique
    "RE": (27, "5n5n11c2n"),       # Réunion
    "YT": (27, "5n5n11c2n"),       # Mayotte
    "PF": (27, "5n5n11c2n"),       # Franz. Polynesien
    "NC": (27, "5n5n11c2n"),       # Neukaledonien
    "WF": (27, "5n5n11c2n"),       # Wallis und Futuna
    "PM": (27, "5n5n11c2n"),       # Saint-Pierre und Miquelon
    "BL": (27, "5n5n11c2n"),       # Saint-Barthélemy
    "MF": (27, "5n5n11c2n"),       # Saint-Martin
    "TF": (27, "5n5n11c2n"),       # Französische Süd-Territorien

    # =========================================================================
    # Länder ohne IBAN (Kontonummer-basiert für CBPR+)
    # =========================================================================
    "US": (0, ""),
    "JP": (0, ""),
    "CN": (0, ""),
    "AU": (0, ""),
    "CA": (0, ""),
    "IN": (0, ""),
    "SG": (0, ""),
    "HK": (0, ""),
    "KR": (0, ""),
    "TH": (0, ""),
    "MX": (0, ""),
    "ZA": (0, ""),
    "NG": (0, ""),
}

# Abgeleitetes Dict für Abwärtskompatibilität: Ländercode → IBAN-Länge
IBAN_LENGTHS = {code: length for code, (length, _) in IBAN_FORMATS.items()}

# QR-IBAN IID-Bereich
QR_IID_MIN = 30000
QR_IID_MAX = 31999


def _parse_bban_format(fmt: str) -> list:
    """Parst einen BBAN-Format-String in eine Liste von (Anzahl, Typ)-Tupeln.

    Beispiel: "8n10n" → [(8, 'n'), (10, 'n')]
              "4a6n8c" → [(4, 'a'), (6, 'n'), (8, 'c')]
    """
    segments = []
    i = 0
    while i < len(fmt):
        num_str = ""
        while i < len(fmt) and fmt[i].isdigit():
            num_str += fmt[i]
            i += 1
        if i < len(fmt) and fmt[i] in ("n", "a", "c"):
            segments.append((int(num_str), fmt[i]))
            i += 1
        else:
            break
    return segments


def _generate_bban_segment(rng: random.Random, count: int, seg_type: str) -> str:
    """Generiert einen BBAN-Segment-String gemäß Typ.

    n = numerisch (0-9)
    a = alphabetisch (A-Z)
    c = alphanumerisch (A-Z, 0-9)
    """
    if seg_type == "n":
        return "".join([str(rng.randint(0, 9)) for _ in range(count)])
    elif seg_type == "a":
        return "".join([rng.choice(string.ascii_uppercase) for _ in range(count)])
    else:  # "c" — alphanumerisch
        chars = string.ascii_uppercase + string.digits
        return "".join([rng.choice(chars) for _ in range(count)])


def _validate_bban_segment(segment: str, seg_type: str) -> bool:
    """Prüft ob ein BBAN-Segment dem erwarteten Typ entspricht."""
    if seg_type == "n":
        return segment.isdigit()
    elif seg_type == "a":
        return segment.isalpha() and segment.isupper()
    else:  # "c"
        return all(ch.isdigit() or (ch.isalpha() and ch.isupper()) for ch in segment)


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


def validate_bban_format(iban: str) -> bool:
    """Prüft ob der BBAN-Teil einer IBAN dem Landesformat entspricht.

    Validiert sowohl die Länge als auch das Zeichenformat (n/a/c)
    jeder BBAN-Position gemäß SWIFT IBAN Registry.
    """
    iban_clean = iban.replace(" ", "").upper()
    if len(iban_clean) < 4:
        return False
    country = iban_clean[:2]
    fmt_entry = IBAN_FORMATS.get(country)
    if not fmt_entry:
        return False
    expected_length, bban_fmt = fmt_entry
    if expected_length == 0 or not bban_fmt:
        return False
    if len(iban_clean) != expected_length:
        return False

    bban = iban_clean[4:]
    segments = _parse_bban_format(bban_fmt)

    pos = 0
    for count, seg_type in segments:
        if pos + count > len(bban):
            return False
        segment = bban[pos:pos + count]
        if not _validate_bban_segment(segment, seg_type):
            return False
        pos += count

    return pos == len(bban)


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

    # BBAN: 5-stellige IID + 12-stellige Kontonummer (CH: 12c = alphanumerisch)
    account = _generate_bban_segment(rng, 12, "c")
    bban = f"{iid:05d}{account}"

    check = calculate_iban_check_digits("CH", bban)
    return f"CH{check}{bban}"


def generate_iban(rng: random.Random, country_code: str = "DE") -> str:
    """Generiert eine prüfziffervalide IBAN für ein gegebenes Land.

    Erzeugt BBANs, die dem Landesformat entsprechen (numerisch, alpha
    oder alphanumerisch an den richtigen Positionen).
    """
    country = country_code.upper()
    fmt_entry = IBAN_FORMATS.get(country)
    if not fmt_entry:
        raise ValueError(f"IBAN-Generierung für Land '{country}' nicht unterstützt.")
    length, bban_fmt = fmt_entry
    if length == 0:
        raise ValueError(f"IBAN-Generierung für Land '{country}' nicht unterstützt.")

    segments = _parse_bban_format(bban_fmt)
    bban = "".join(
        _generate_bban_segment(rng, count, seg_type)
        for count, seg_type in segments
    )

    check = calculate_iban_check_digits(country, bban)
    return f"{country}{check}{bban}"


# Kontonummer-Formate für Länder ohne IBAN (CBPR+)
# Tupel: (Prefix/Routing-Format, Kontonummer-Länge)
NON_IBAN_ACCOUNT_FORMATS = {
    "US": {"routing_length": 9, "account_length": 12, "label": "ABA/Account"},
    "AU": {"routing_length": 6, "account_length": 10, "label": "BSB/Account"},
    "CA": {"routing_length": 9, "account_length": 12, "label": "Transit/Account"},
    "JP": {"routing_length": 7, "account_length": 8, "label": "Bank/Branch/Account"},
    "CN": {"routing_length": 0, "account_length": 19, "label": "Account"},
    "IN": {"routing_length": 11, "account_length": 14, "label": "IFSC/Account"},
    "SG": {"routing_length": 4, "account_length": 12, "label": "Bank/Account"},
    "HK": {"routing_length": 3, "account_length": 12, "label": "Bank/Account"},
    "KR": {"routing_length": 3, "account_length": 13, "label": "Bank/Account"},
    "TH": {"routing_length": 0, "account_length": 10, "label": "Account"},
    "MX": {"routing_length": 0, "account_length": 18, "label": "CLABE"},
    "ZA": {"routing_length": 6, "account_length": 11, "label": "Branch/Account"},
    "NG": {"routing_length": 3, "account_length": 10, "label": "Bank/Account"},
}


def generate_non_iban_account(rng: random.Random, country_code: str) -> str:
    """Generiert eine realistische Kontonummer für Länder ohne IBAN.

    Gibt nur den Account-Identifier zurück (ohne Routing-Prefix).
    """
    country = country_code.upper()
    fmt = NON_IBAN_ACCOUNT_FORMATS.get(country)
    if not fmt:
        # Fallback: generische 12-stellige Kontonummer
        return "".join([str(rng.randint(0, 9)) for _ in range(12)])

    length = fmt["account_length"]
    return "".join([str(rng.randint(0, 9)) for _ in range(length)])


def is_non_iban_country(country_code: str) -> bool:
    """Prüft ob ein Land keine IBAN verwendet."""
    return IBAN_LENGTHS.get(country_code.upper(), 0) == 0 and country_code.upper() in IBAN_LENGTHS


# Häufig verwendete SEPA-Länder
SEPA_COUNTRIES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE", "CH", "LI", "NO",
    "IS", "GB",
]
