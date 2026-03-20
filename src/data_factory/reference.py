import random

# Mod-10 rekursiv Übertragstabelle (Schweizer Verfahren)
_MOD10_TABLE = [
    [0, 9, 4, 6, 8, 2, 7, 1, 3, 5],
    [9, 4, 6, 8, 2, 7, 1, 3, 5, 0],
    [4, 6, 8, 2, 7, 1, 3, 5, 0, 9],
    [6, 8, 2, 7, 1, 3, 5, 0, 9, 4],
    [8, 2, 7, 1, 3, 5, 0, 9, 4, 6],
    [2, 7, 1, 3, 5, 0, 9, 4, 6, 8],
    [7, 1, 3, 5, 0, 9, 4, 6, 8, 2],
    [1, 3, 5, 0, 9, 4, 6, 8, 2, 7],
    [3, 5, 0, 9, 4, 6, 8, 2, 7, 1],
    [5, 0, 9, 4, 6, 8, 2, 7, 1, 3],
]


def _mod10_recursive_check_digit(digits: str) -> int:
    """Berechnet die Mod-10-Prüfziffer (rekursives Verfahren)."""
    carry = 0
    for d in digits:
        carry = _MOD10_TABLE[carry][int(d)]
    return (10 - carry) % 10


def validate_qrr(qrr: str) -> bool:
    """Validiert eine QR-Referenz (27 Stellen numerisch, Mod-10 Prüfziffer)."""
    if len(qrr) != 27:
        return False
    if not qrr.isdigit():
        return False
    check = _mod10_recursive_check_digit(qrr[:26])
    return check == int(qrr[26])


def generate_qrr(rng: random.Random) -> str:
    """Generiert eine gültige QR-Referenz (27 Stellen)."""
    digits = "".join([str(rng.randint(0, 9)) for _ in range(26)])
    check = _mod10_recursive_check_digit(digits)
    return digits + str(check)


def _mod97_iso(value: str) -> int:
    """Berechnet Mod-97 für ISO 11649 (SCOR-Referenz)."""
    numeric = ""
    for ch in value:
        if ch.isdigit():
            numeric += ch
        else:
            numeric += str(ord(ch.upper()) - ord("A") + 10)
    return int(numeric) % 97


def validate_scor(scor: str) -> bool:
    """Validiert eine SCOR-Referenz (ISO 11649, RF + Prüfziffer + Referenz)."""
    scor_clean = scor.replace(" ", "").upper()
    if len(scor_clean) < 5 or len(scor_clean) > 25:
        return False
    if not scor_clean.startswith("RF"):
        return False
    if not scor_clean[2:4].isdigit():
        return False
    # Mod-97 Prüfung: Referenz + "RF" + Prüfziffer ans Ende
    rearranged = scor_clean[4:] + scor_clean[:4]
    return _mod97_iso(rearranged) == 1


def generate_scor(rng: random.Random) -> str:
    """Generiert eine gültige SCOR-Referenz (ISO 11649)."""
    # Referenzteil: 8-21 alphanumerische Zeichen
    ref_length = rng.randint(8, 21)
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    reference = "".join([rng.choice(chars) for _ in range(ref_length)])

    # Prüfziffer berechnen
    temp = reference + "RF00"
    remainder = _mod97_iso(temp)
    check = 98 - remainder

    return f"RF{check:02d}{reference}"
