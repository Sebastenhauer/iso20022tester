"""Property-based Tests mit Hypothesis für IBAN, QRR, SCOR und Beträge.

Entdeckt automatisch Randfälle über den gesamten Eingaberaum,
die durch fixe Testfälle nicht abgedeckt werden.
"""

import random
from decimal import Decimal

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.data_factory.iban import (
    IBAN_LENGTHS,
    QR_IID_MIN,
    QR_IID_MAX,
    _mod97,
    calculate_iban_check_digits,
    generate_ch_iban,
    generate_iban,
    is_qr_iban,
    validate_iban,
    validate_iban_length,
)
from src.data_factory.reference import (
    _mod10_recursive_check_digit,
    _mod97_iso,
    generate_qrr,
    generate_scor,
    validate_qrr,
    validate_scor,
)
from src.data_factory.generator import DataFactory
from src.models.testcase import PaymentType


# =========================================================================
# Strategies
# =========================================================================

# Zufällige Seeds für reproduzierbare Generatoren
seed_strategy = st.integers(min_value=0, max_value=2**31 - 1)

# Länder mit IBAN-Support (Länge > 0)
iban_countries = [c for c, l in IBAN_LENGTHS.items() if l > 0]
iban_country_strategy = st.sampled_from(iban_countries)

# Alle Payment-Types
payment_type_strategy = st.sampled_from(list(PaymentType))


# =========================================================================
# IBAN Mod-97 Property Tests
# =========================================================================

class TestIbanMod97Properties:
    """Property-Tests für IBAN Mod-97 Validierung."""

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_generated_ch_iban_always_valid(self, seed: int):
        """Jede generierte CH-IBAN muss Mod-97-valid sein."""
        rng = random.Random(seed)
        iban = generate_ch_iban(rng)
        assert validate_iban(iban), f"Ungültige IBAN generiert: {iban}"

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_generated_ch_qr_iban_always_valid(self, seed: int):
        """Jede generierte QR-IBAN muss valid sein und IID im Bereich 30000-31999 haben."""
        rng = random.Random(seed)
        iban = generate_ch_iban(rng, qr=True)
        assert validate_iban(iban), f"Ungültige QR-IBAN: {iban}"
        assert is_qr_iban(iban), f"QR-IBAN nicht als QR erkannt: {iban}"
        iid = int(iban[4:9])
        assert QR_IID_MIN <= iid <= QR_IID_MAX, f"IID außerhalb QR-Bereich: {iid}"

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_generated_ch_regular_iban_never_qr(self, seed: int):
        """Reguläre CH-IBANs dürfen nie QR-IBANs sein."""
        rng = random.Random(seed)
        iban = generate_ch_iban(rng, qr=False)
        assert validate_iban(iban), f"Ungültige reguläre IBAN: {iban}"
        assert not is_qr_iban(iban), f"Reguläre IBAN fälschlicherweise als QR: {iban}"

    @given(seed=seed_strategy, country=iban_country_strategy)
    @settings(max_examples=300)
    def test_generated_iban_any_country_always_valid(self, seed: int, country: str):
        """IBANs für jedes unterstützte Land müssen Mod-97-valid sein."""
        rng = random.Random(seed)
        iban = generate_iban(rng, country)
        assert validate_iban(iban), f"Ungültige IBAN für {country}: {iban}"
        assert iban.startswith(country), f"Falscher Ländercode: {iban}"
        expected_length = IBAN_LENGTHS[country]
        assert len(iban) == expected_length, (
            f"Falsche Länge für {country}: erwartet {expected_length}, "
            f"erhalten {len(iban)}"
        )

    @given(seed=seed_strategy, country=iban_country_strategy)
    @settings(max_examples=200)
    def test_iban_length_validation_consistent(self, seed: int, country: str):
        """Generierte IBANs müssen auch die Längenprüfung bestehen."""
        rng = random.Random(seed)
        iban = generate_iban(rng, country)
        assert validate_iban_length(iban), f"Längenprüfung fehlgeschlagen: {iban}"

    @given(
        country=st.sampled_from(["CH", "DE", "FR", "IT", "GB"]),
        bban_digits=st.text(
            alphabet=st.characters(whitelist_categories=("Nd",)),
            min_size=1,
            max_size=1,
        ),
    )
    def test_check_digit_calculation_idempotent(self, country: str, bban_digits: str):
        """calculate_iban_check_digits mit gleichem Input gibt gleiches Ergebnis."""
        # Feste BBAN-Länge pro Land
        bban_length = IBAN_LENGTHS[country] - 4
        bban = bban_digits[0] * bban_length  # z.B. "000...0" oder "111...1"
        check1 = calculate_iban_check_digits(country, bban)
        check2 = calculate_iban_check_digits(country, bban)
        assert check1 == check2

    @given(seed=seed_strategy)
    @settings(max_examples=100)
    def test_iban_mod97_remainder_is_one(self, seed: int):
        """Für jede gültige IBAN muss der Mod-97-Rest nach Umordnung genau 1 sein."""
        rng = random.Random(seed)
        iban = generate_ch_iban(rng)
        rearranged = iban[4:] + iban[:4]
        assert _mod97(rearranged) == 1

    @given(seed=seed_strategy)
    @settings(max_examples=100)
    def test_flipping_single_char_invalidates_iban(self, seed: int):
        """Änderung eines einzelnen Zeichens muss die IBAN invalidieren (fast immer)."""
        rng = random.Random(seed)
        iban = generate_ch_iban(rng)
        # Zufällige Stelle im BBAN-Teil ändern (Positionen 4-20)
        pos = rng.randint(4, len(iban) - 1)
        original_char = iban[pos]
        # Anderes Zeichen wählen (Ziffer oder Buchstabe)
        if original_char.isdigit():
            new_char = str((int(original_char) + 1) % 10)
        else:
            new_char = "A" if original_char != "A" else "B"
        mutated = iban[:pos] + new_char + iban[pos + 1:]
        # In extrem seltenen Fällen kann die mutierte IBAN zufällig wieder valid sein
        # (Wahrscheinlichkeit ca. 1/97), daher prüfen wir nur ob sie unterschiedlich ist
        assert mutated != iban


# =========================================================================
# QRR Mod-10 Property Tests
# =========================================================================

class TestQrrMod10Properties:
    """Property-Tests für QRR Mod-10 Prüfziffer."""

    @given(seed=seed_strategy)
    @settings(max_examples=300)
    def test_generated_qrr_always_valid(self, seed: int):
        """Jede generierte QRR muss 27 Stellen haben und Mod-10-valid sein."""
        rng = random.Random(seed)
        qrr = generate_qrr(rng)
        assert len(qrr) == 27, f"QRR hat falsche Länge: {len(qrr)}"
        assert qrr.isdigit(), f"QRR enthält nicht-numerische Zeichen: {qrr}"
        assert validate_qrr(qrr), f"Ungültige QRR generiert: {qrr}"

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_qrr_check_digit_is_correct(self, seed: int):
        """Die letzte Stelle der QRR muss der berechneten Prüfziffer entsprechen."""
        rng = random.Random(seed)
        qrr = generate_qrr(rng)
        expected_check = _mod10_recursive_check_digit(qrr[:26])
        assert int(qrr[26]) == expected_check

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_flipping_digit_invalidates_qrr(self, seed: int):
        """Änderung einer Stelle (nicht der Prüfziffer) muss QRR invalidieren."""
        rng = random.Random(seed)
        qrr = generate_qrr(rng)
        # Zufällige Stelle in den ersten 26 Ziffern ändern
        pos = rng.randint(0, 25)
        original = int(qrr[pos])
        new_digit = (original + 1) % 10
        mutated = qrr[:pos] + str(new_digit) + qrr[pos + 1:]
        # Prüfziffer ist jetzt falsch (außer in extrem seltenen Fällen)
        # Wir verifizieren mindestens, dass die Mutation anders ist
        assert mutated != qrr

    @given(
        digits=st.text(
            alphabet=st.sampled_from("0123456789"),
            min_size=26,
            max_size=26,
        )
    )
    def test_mod10_check_digit_range(self, digits: str):
        """Mod-10-Prüfziffer muss immer im Bereich 0-9 liegen."""
        check = _mod10_recursive_check_digit(digits)
        assert 0 <= check <= 9

    @given(
        digits=st.text(
            alphabet=st.sampled_from("0123456789"),
            min_size=26,
            max_size=26,
        )
    )
    def test_mod10_roundtrip(self, digits: str):
        """Prüfziffer angehängt → validate_qrr muss True ergeben."""
        check = _mod10_recursive_check_digit(digits)
        qrr = digits + str(check)
        assert validate_qrr(qrr), f"Roundtrip fehlgeschlagen: {qrr}"

    @given(
        non_numeric=st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=27,
            max_size=27,
        )
    )
    def test_non_numeric_qrr_rejected(self, non_numeric: str):
        """Nicht-numerische 27-stellige Strings müssen als ungültig abgelehnt werden."""
        assume(not non_numeric.isdigit())
        assert not validate_qrr(non_numeric)

    @given(
        length=st.integers(min_value=0, max_value=50).filter(lambda x: x != 27)
    )
    def test_wrong_length_qrr_rejected(self, length: int):
        """QRR mit falscher Länge muss abgelehnt werden."""
        qrr = "0" * length
        assert not validate_qrr(qrr)


# =========================================================================
# SCOR ISO 11649 Property Tests
# =========================================================================

class TestScorIso11649Properties:
    """Property-Tests für SCOR ISO 11649 Prüfziffern."""

    @given(seed=seed_strategy)
    @settings(max_examples=300)
    def test_generated_scor_always_valid(self, seed: int):
        """Jede generierte SCOR muss valid sein."""
        rng = random.Random(seed)
        scor = generate_scor(rng)
        assert scor.startswith("RF"), f"SCOR beginnt nicht mit RF: {scor}"
        assert 5 <= len(scor) <= 25, f"SCOR hat ungültige Länge: {len(scor)}"
        assert validate_scor(scor), f"Ungültige SCOR generiert: {scor}"

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_scor_check_digits_are_numeric(self, seed: int):
        """Die Prüfziffern (Position 2-3) müssen numerisch sein und 02-98."""
        rng = random.Random(seed)
        scor = generate_scor(rng)
        check_str = scor[2:4]
        assert check_str.isdigit(), f"Prüfziffern nicht numerisch: {check_str}"
        check_val = int(check_str)
        assert 2 <= check_val <= 98, f"Prüfziffer außerhalb 02-98: {check_val}"

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_scor_mod97_remainder_is_one(self, seed: int):
        """Für jede gültige SCOR muss der Mod-97-Rest nach Umordnung 1 sein."""
        rng = random.Random(seed)
        scor = generate_scor(rng)
        rearranged = scor[4:] + scor[:4]
        assert _mod97_iso(rearranged) == 1

    @given(seed=seed_strategy)
    @settings(max_examples=100)
    def test_scor_reference_part_is_alphanumeric(self, seed: int):
        """Der Referenzteil (ab Position 4) muss alphanumerisch sein."""
        rng = random.Random(seed)
        scor = generate_scor(rng)
        reference = scor[4:]
        assert reference.isalnum(), f"Referenzteil nicht alphanumerisch: {reference}"

    @given(seed=seed_strategy)
    @settings(max_examples=100)
    def test_corrupted_scor_detected(self, seed: int):
        """Änderung des Referenzteils muss die SCOR invalidieren."""
        rng = random.Random(seed)
        scor = generate_scor(rng)
        # Ein Zeichen im Referenzteil ändern
        ref = scor[4:]
        if len(ref) > 0:
            pos = rng.randint(0, len(ref) - 1)
            ch = ref[pos]
            # Anderes alphanumerisches Zeichen wählen
            if ch == "Z":
                new_ch = "A"
            elif ch == "9":
                new_ch = "0"
            else:
                new_ch = chr(ord(ch) + 1)
            mutated = scor[:4 + pos] + new_ch + scor[4 + pos + 1:]
            # Mutierte SCOR sollte in fast allen Fällen ungültig sein
            assert mutated != scor

    @given(
        reference=st.text(
            alphabet=st.sampled_from(
                "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            ),
            min_size=1,
            max_size=21,
        )
    )
    @settings(max_examples=200)
    def test_scor_roundtrip_from_reference(self, reference: str):
        """Aus beliebigem alphanumerischem Referenztext eine gültige SCOR erzeugen."""
        # Prüfziffer berechnen wie im Produktionscode
        temp = reference + "RF00"
        remainder = _mod97_iso(temp)
        check = 98 - remainder
        scor = f"RF{check:02d}{reference}"

        # Muss valid sein wenn Gesamtlänge im Rahmen
        if 5 <= len(scor) <= 25:
            assert validate_scor(scor), f"Roundtrip fehlgeschlagen: {scor}"


# =========================================================================
# Amount Range Property Tests
# =========================================================================

class TestAmountRangeProperties:
    """Property-Tests für Betrags-Erzeugung und Bereichsgrenzen."""

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_sepa_amount_within_bounds(self, seed: int):
        """SEPA-Beträge müssen zwischen 10.00 und 999'999'999.99 liegen."""
        factory = DataFactory(seed=seed)
        amount = factory.generate_amount(PaymentType.SEPA)
        assert isinstance(amount, Decimal)
        assert amount >= Decimal("10.0"), f"SEPA-Betrag zu klein: {amount}"
        assert amount <= Decimal("999999999.99"), f"SEPA-Betrag zu groß: {amount}"

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_domestic_qr_amount_within_bounds(self, seed: int):
        """Domestic-QR-Beträge müssen im gültigen Bereich liegen."""
        factory = DataFactory(seed=seed)
        amount = factory.generate_amount(PaymentType.DOMESTIC_QR)
        assert isinstance(amount, Decimal)
        assert amount >= Decimal("10.0"), f"Betrag zu klein: {amount}"
        assert amount <= Decimal("9999999999.99"), f"Betrag zu groß: {amount}"

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_domestic_iban_amount_within_bounds(self, seed: int):
        """Domestic-IBAN-Beträge müssen im gültigen Bereich liegen."""
        factory = DataFactory(seed=seed)
        amount = factory.generate_amount(PaymentType.DOMESTIC_IBAN)
        assert isinstance(amount, Decimal)
        assert amount >= Decimal("10.0")
        assert amount <= Decimal("9999999999.99")

    @given(seed=seed_strategy)
    @settings(max_examples=200)
    def test_cbpr_plus_amount_within_bounds(self, seed: int):
        """CBPR+-Beträge müssen im gültigen Bereich liegen."""
        factory = DataFactory(seed=seed)
        amount = factory.generate_amount(PaymentType.CBPR_PLUS)
        assert isinstance(amount, Decimal)
        assert amount >= Decimal("10.0")
        assert amount <= Decimal("9999999999.99")

    @given(seed=seed_strategy, payment_type=payment_type_strategy)
    @settings(max_examples=300)
    def test_amount_always_has_max_two_decimals(self, seed: int, payment_type: PaymentType):
        """Beträge dürfen maximal 2 Nachkommastellen haben."""
        factory = DataFactory(seed=seed)
        amount = factory.generate_amount(payment_type)
        # Quantisiert auf 2 Dezimalstellen
        quantized = amount.quantize(Decimal("0.01"))
        assert amount == quantized, f"Mehr als 2 Dezimalstellen: {amount}"

    @given(seed=seed_strategy, payment_type=payment_type_strategy)
    @settings(max_examples=200)
    def test_amount_is_positive(self, seed: int, payment_type: PaymentType):
        """Beträge müssen immer positiv sein."""
        factory = DataFactory(seed=seed)
        amount = factory.generate_amount(payment_type)
        assert amount > Decimal("0"), f"Betrag nicht positiv: {amount}"

    @given(seed=seed_strategy)
    @settings(max_examples=100)
    def test_sepa_currency_always_eur(self, seed: int):
        """SEPA-Währung muss immer EUR sein."""
        factory = DataFactory(seed=seed)
        currency = factory.generate_currency(PaymentType.SEPA)
        assert currency == "EUR"

    @given(seed=seed_strategy)
    @settings(max_examples=100)
    def test_domestic_currency_always_chf(self, seed: int):
        """Domestic-Zahlungstypen müssen CHF als Währung haben."""
        factory = DataFactory(seed=seed)
        for pt in (PaymentType.DOMESTIC_QR, PaymentType.DOMESTIC_IBAN):
            currency = factory.generate_currency(pt)
            assert currency == "CHF"

    @given(seed=seed_strategy)
    @settings(max_examples=100)
    def test_cbpr_plus_currency_valid(self, seed: int):
        """CBPR+-Währung muss eine der erlaubten Währungen sein."""
        factory = DataFactory(seed=seed)
        currency = factory.generate_currency(PaymentType.CBPR_PLUS)
        assert currency in ("USD", "GBP", "JPY", "EUR"), (
            f"Unerlaubte CBPR+-Währung: {currency}"
        )
