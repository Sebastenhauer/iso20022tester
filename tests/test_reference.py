"""Tests für QRR- und SCOR-Referenz-Generierung und -Validierung."""

import random

from src.data_factory.reference import (
    generate_qrr,
    generate_scor,
    validate_qrr,
    validate_scor,
)


def test_generate_qrr_valid():
    rng = random.Random(42)
    qrr = generate_qrr(rng)
    assert len(qrr) == 27
    assert qrr.isdigit()
    assert validate_qrr(qrr)


def test_validate_qrr_invalid_length():
    assert not validate_qrr("12345")
    assert not validate_qrr("1234567890123456789012345678")  # 28 Stellen


def test_validate_qrr_invalid_check():
    rng = random.Random(42)
    qrr = generate_qrr(rng)
    # Letzte Stelle ändern
    bad_qrr = qrr[:26] + str((int(qrr[26]) + 1) % 10)
    assert not validate_qrr(bad_qrr)


def test_generate_scor_valid():
    rng = random.Random(42)
    scor = generate_scor(rng)
    assert scor.startswith("RF")
    assert 5 <= len(scor) <= 25
    assert validate_scor(scor)


def test_validate_scor_invalid():
    assert not validate_scor("XX12345")
    assert not validate_scor("RF")
    assert not validate_scor("")


def test_validate_scor_bad_checksum():
    rng = random.Random(42)
    scor = generate_scor(rng)
    # Prüfziffer ändern
    bad_scor = "RF00" + scor[4:]
    assert not validate_scor(bad_scor)


def test_reproducibility():
    qrr1 = generate_qrr(random.Random(42))
    qrr2 = generate_qrr(random.Random(42))
    assert qrr1 == qrr2
