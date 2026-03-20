"""Tests für IBAN-Generierung und -Validierung."""

import random

from src.data_factory.iban import (
    generate_ch_iban,
    generate_iban,
    is_qr_iban,
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
