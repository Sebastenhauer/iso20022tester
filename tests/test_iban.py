"""Tests für IBAN-Generierung und -Validierung."""

import random

import pytest

from src.data_factory.iban import (
    IBAN_FORMATS,
    IBAN_LENGTHS,
    generate_ch_iban,
    generate_iban,
    is_qr_iban,
    validate_bban_format,
    validate_iban,
    validate_iban_length,
)


def test_generate_ch_iban_valid():
    rng = random.Random(42)
    iban = generate_ch_iban(rng)
    assert validate_iban(iban)
    assert iban.startswith("CH")
    assert len(iban) == 21


def test_generate_ch_qr_iban():
    rng = random.Random(42)
    iban = generate_ch_iban(rng, qr=True)
    assert validate_iban(iban)
    assert is_qr_iban(iban)
    iid = int(iban[4:9])
    assert 30000 <= iid <= 31999


def test_generate_ch_regular_iban_not_qr():
    rng = random.Random(42)
    for _ in range(20):
        iban = generate_ch_iban(rng, qr=False)
        assert validate_iban(iban)
        assert not is_qr_iban(iban)


def test_generate_de_iban():
    rng = random.Random(42)
    iban = generate_iban(rng, "DE")
    assert validate_iban(iban)
    assert iban.startswith("DE")
    assert len(iban) == 22


def test_validate_iban_known_valid():
    # Bekannte gültige IBANs
    assert validate_iban("CH9300762011623852957")
    assert validate_iban("DE89370400440532013000")


def test_validate_iban_invalid():
    assert not validate_iban("CH9300762011623852999")
    assert not validate_iban("XX")
    assert not validate_iban("")


def test_validate_iban_length():
    assert validate_iban_length("CH9300762011623852957")
    assert validate_iban_length("DE89370400440532013000")
    assert not validate_iban_length("CH93007620116238529")  # zu kurz
    assert not validate_iban_length("US123456789")  # USA hat keine IBAN


def test_is_qr_iban():
    assert is_qr_iban("CH4431999123000889012")  # IID 31999
    assert not is_qr_iban("CH9300762011623852957")  # IID 00762
    assert not is_qr_iban("DE89370400440532013000")  # kein CH


def test_reproducibility():
    iban1 = generate_ch_iban(random.Random(42))
    iban2 = generate_ch_iban(random.Random(42))
    assert iban1 == iban2


# =========================================================================
# IBAN_LENGTHS Abwärtskompatibilität
# =========================================================================

def test_iban_lengths_derived_from_formats():
    """IBAN_LENGTHS muss aus IBAN_FORMATS abgeleitet werden."""
    for code, length in IBAN_LENGTHS.items():
        fmt_length, _ = IBAN_FORMATS[code]
        assert length == fmt_length, f"{code}: IBAN_LENGTHS={length} != IBAN_FORMATS={fmt_length}"


def test_iban_country_count():
    """Mindestens 80 Länder mit IBAN-Support (Länge > 0)."""
    iban_countries = [c for c, l in IBAN_LENGTHS.items() if l > 0]
    assert len(iban_countries) >= 80, f"Nur {len(iban_countries)} IBAN-Länder"


# =========================================================================
# BBAN-Format-Validierung
# =========================================================================

def test_validate_bban_format_known_ibans():
    """Bekannte gültige IBANs müssen die BBAN-Formatprüfung bestehen."""
    known_valid = [
        "DE75512108001245126199",
        "FR7630006000011234567890189",
        "IT60X0542811101000000123456",
        "NL02ABNA0123456789",
        "GB33BUKB20201555555555",
        "BG19STSA93000123456789",
        "BR1500000000000010932840814P2",
        "MU43BOMM0101123456789101000MUR",
        "SC74MCBL01031234567890123456USD",
        "PK36SCBL0000001123456702",
        "RO66BACX0000001234567890",
        "GE60NB0000000123456789",
        "AZ77VTBA00000000001234567890",
    ]
    for iban in known_valid:
        assert validate_bban_format(iban), f"BBAN-Format ungültig für: {iban}"


def test_validate_bban_format_rejects_wrong_format():
    """IBANs mit falschem BBAN-Format müssen abgelehnt werden."""
    # NL erwartet 4a+10n — rein numerischer BBAN ist ungültig
    assert not validate_bban_format("NL020000012345678900")
    # DE erwartet 18n — Buchstaben im BBAN sind ungültig
    assert not validate_bban_format("DE75ABCDEFGH12345678")


def test_validate_bban_format_edge_cases():
    """Randfälle für BBAN-Formatprüfung."""
    assert not validate_bban_format("")
    assert not validate_bban_format("XX")
    assert not validate_bban_format("US12345678901234")  # Non-IBAN-Land


# =========================================================================
# Generierung neuer Länder (Formatkonformität)
# =========================================================================

# Alle IBAN-Länder als Parametrierung
_iban_countries = sorted(c for c, (l, _) in IBAN_FORMATS.items() if l > 0)


@pytest.mark.parametrize("country", _iban_countries)
def test_generate_iban_all_countries(country):
    """Generierte IBANs für jedes Land: Mod-97, Länge und BBAN-Format korrekt."""
    rng = random.Random(42)
    iban = generate_iban(rng, country)
    expected_length = IBAN_LENGTHS[country]

    assert iban.startswith(country), f"Falscher Ländercode: {iban}"
    assert len(iban) == expected_length, (
        f"{country}: Länge {len(iban)} statt {expected_length}"
    )
    assert validate_iban(iban), f"{country}: Mod-97 ungültig für {iban}"
    assert validate_bban_format(iban), f"{country}: BBAN-Format ungültig für {iban}"


# Spezifische Tests für Länder mit gemischten Formaten
class TestMixedFormatCountries:
    """Tests für Länder mit Alpha/Alphanumerischen BBAN-Segmenten."""

    def test_br_iban_has_alpha_positions(self):
        """Brasilien: Position 24 muss Alpha sein, Position 25 alphanumerisch."""
        rng = random.Random(42)
        for _ in range(10):
            iban = generate_iban(rng, "BR")
            assert len(iban) == 29
            # BBAN Positionen (0-basiert im BBAN = ab Index 4 in IBAN):
            # 8n + 5n + 10n + 1a + 1c
            bban = iban[4:]
            assert bban[:23].isdigit(), f"BR: numerischer Teil nicht numerisch: {bban}"
            assert bban[23].isalpha(), f"BR: Position 23 nicht Alpha: {bban[23]}"
            assert bban[24].isalnum(), f"BR: Position 24 nicht alphanumerisch: {bban[24]}"

    def test_mu_iban_ends_with_currency(self):
        """Mauritius: letzte 3 Zeichen müssen Alpha sein (Währungscode)."""
        rng = random.Random(42)
        for _ in range(10):
            iban = generate_iban(rng, "MU")
            assert len(iban) == 30
            currency_part = iban[-3:]
            assert currency_part.isalpha(), (
                f"MU: Währungs-Suffix nicht Alpha: {currency_part}"
            )

    def test_sc_iban_ends_with_currency(self):
        """Seychellen: letzte 3 Zeichen müssen Alpha sein (Währungscode)."""
        rng = random.Random(42)
        for _ in range(10):
            iban = generate_iban(rng, "SC")
            assert len(iban) == 31
            currency_part = iban[-3:]
            assert currency_part.isalpha(), (
                f"SC: Währungs-Suffix nicht Alpha: {currency_part}"
            )

    def test_it_iban_starts_with_cin_letter(self):
        """Italien: erste BBAN-Position muss Alpha sein (CIN)."""
        rng = random.Random(42)
        for _ in range(10):
            iban = generate_iban(rng, "IT")
            assert len(iban) == 27
            cin = iban[4]
            assert cin.isalpha(), f"IT: CIN nicht Alpha: {cin}"

    def test_nl_iban_starts_with_bank_code(self):
        """Niederlande: erste 4 BBAN-Zeichen müssen Alpha sein (Bankcode)."""
        rng = random.Random(42)
        for _ in range(10):
            iban = generate_iban(rng, "NL")
            assert len(iban) == 18
            bank = iban[4:8]
            assert bank.isalpha(), f"NL: Bankcode nicht Alpha: {bank}"

    def test_gb_iban_starts_with_sort_code(self):
        """GB: erste 4 BBAN-Zeichen müssen Alpha sein (Bankcode)."""
        rng = random.Random(42)
        for _ in range(10):
            iban = generate_iban(rng, "GB")
            assert len(iban) == 22
            bank = iban[4:8]
            assert bank.isalpha(), f"GB: Bankcode nicht Alpha: {bank}"

    def test_ge_iban_starts_with_alpha(self):
        """Georgien: erste 2 BBAN-Zeichen müssen Alpha sein."""
        rng = random.Random(42)
        for _ in range(10):
            iban = generate_iban(rng, "GE")
            assert len(iban) == 22
            bank = iban[4:6]
            assert bank.isalpha(), f"GE: Bankcode nicht Alpha: {bank}"


# =========================================================================
# Non-IBAN Account Generation
# =========================================================================

def test_generate_non_iban_account_us():
    from src.data_factory.iban import generate_non_iban_account
    rng = random.Random(42)
    acct = generate_non_iban_account(rng, "US")
    assert len(acct) == 12  # US account length
    assert acct.isdigit()


def test_generate_non_iban_account_au():
    from src.data_factory.iban import generate_non_iban_account
    rng = random.Random(42)
    acct = generate_non_iban_account(rng, "AU")
    assert len(acct) == 10  # AU (BSB) account length
    assert acct.isdigit()


def test_generate_non_iban_account_unknown_country():
    from src.data_factory.iban import generate_non_iban_account
    rng = random.Random(42)
    acct = generate_non_iban_account(rng, "XX")
    assert len(acct) == 12  # Fallback: 12 Stellen
    assert acct.isdigit()


def test_is_non_iban_country():
    from src.data_factory.iban import is_non_iban_country
    assert is_non_iban_country("US")
    assert is_non_iban_country("JP")
    assert is_non_iban_country("AU")
    assert not is_non_iban_country("CH")
    assert not is_non_iban_country("DE")
    assert not is_non_iban_country("XX")  # nicht in IBAN_LENGTHS
