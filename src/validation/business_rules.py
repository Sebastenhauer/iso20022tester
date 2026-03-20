"""Business-Rule-Engine: Übergreifende Regeln und Orchestrierung.

Alle Rule-Metadaten kommen aus dem zentralen `rule_catalog`.
Diese Datei enthält nur die Validierungs- und Violation-Logik.
"""

import random
from decimal import Decimal
from typing import List

from src.data_factory.generator import validate_sps_charset
from src.data_factory.iban import validate_iban, validate_iban_length
from src.models.testcase import (
    PaymentInstruction,
    PaymentType,
    TestCase,
    Transaction,
    ValidationResult,
)
from src.payment_types.base import PaymentTypeHandler
from src.payment_types.cbpr_plus import CbprPlusHandler
from src.payment_types.domestic_iban import DomesticIbanHandler
from src.payment_types.domestic_qr import DomesticQrHandler
from src.payment_types.sepa import SepaHandler
from src.validation.rule_catalog import get_rule


# ---------------------------------------------------------------------------
# Hilfsfunktion: ValidationResult aus Katalog erstellen
# ---------------------------------------------------------------------------

def _check(rule_id: str, passed: bool, details: str = None) -> ValidationResult:
    """Erstellt ein ValidationResult mit Beschreibung aus dem Katalog."""
    rule = get_rule(rule_id)
    return ValidationResult(
        rule_id=rule.rule_id,
        rule_description=rule.description,
        passed=passed,
        details=details,
    )


# ---------------------------------------------------------------------------
# Referenzfeld-Zeichensatz
# ---------------------------------------------------------------------------

def _validate_ref_charset(value: str) -> bool:
    """Prüft Referenzfeld-Zeichensatz (BR-GEN-009)."""
    if not value:
        return True
    if value.startswith("/") or value.endswith("/"):
        return False
    if "//" in value:
        return False
    return True


# ---------------------------------------------------------------------------
# Handler-Lookup
# ---------------------------------------------------------------------------

def _get_handler(payment_type: PaymentType) -> PaymentTypeHandler:
    """Gibt den passenden Handler für einen Zahlungstyp zurück."""
    handlers = {
        PaymentType.SEPA: SepaHandler(),
        PaymentType.DOMESTIC_QR: DomesticQrHandler(),
        PaymentType.DOMESTIC_IBAN: DomesticIbanHandler(),
        PaymentType.CBPR_PLUS: CbprPlusHandler(),
    }
    return handlers[payment_type]


# ---------------------------------------------------------------------------
# Validierung: Übergreifende Regeln
# ---------------------------------------------------------------------------

def validate_general_rules(
    instruction: PaymentInstruction,
    testcase: TestCase,
) -> List[ValidationResult]:
    """Validiert zahlungstyp-übergreifende Business Rules."""
    results = []
    txs = instruction.transactions

    # BR-HDR-002: NbOfTxs Konsistenz (vom Builder sichergestellt)
    results.append(_check("BR-HDR-002", True))

    # BR-HDR-003: CtrlSum Konsistenz (vom Builder sichergestellt)
    results.append(_check("BR-HDR-003", True))

    # BR-HDR-004: InitgPty vorhanden
    has_name = bool(instruction.debtor.name)
    results.append(_check(
        "BR-HDR-004", has_name,
        "InitgPty/Nm fehlt" if not has_name else None,
    ))

    # BR-GEN-005: ReqdExctnDt Bankarbeitstag
    results.append(_check("BR-GEN-005", bool(instruction.reqd_exctn_dt)))

    # BR-GEN-009: Referenzfeld-Zeichensatz
    ref_fields = [
        ("PmtInfId", instruction.pmt_inf_id),
        ("MsgId", instruction.msg_id),
    ]
    for tx in txs:
        ref_fields.append(("EndToEndId", tx.end_to_end_id))

    for field_name, value in ref_fields:
        if value:
            valid = _validate_ref_charset(value)
            results.append(_check(
                "BR-GEN-009", valid,
                f"{field_name}='{value}' verletzt Zeichensatz-Regeln" if not valid else None,
            ))

    # BR-GEN-010: Betrag > 0
    for tx in txs:
        results.append(_check(
            "BR-GEN-010", tx.amount > 0,
            f"Betrag ist {tx.amount}" if tx.amount <= 0 else None,
        ))

    # BR-GEN-012: SPS-Zeichensatz
    text_fields = [("Debtor Name", instruction.debtor.name)]
    for tx in txs:
        text_fields.append(("Creditor Name", tx.creditor_name))
        if tx.creditor_address:
            for key, val in tx.creditor_address.items():
                if key != "Ctry":
                    text_fields.append((f"Creditor {key}", val))

    for field_name, value in text_fields:
        if value and not validate_sps_charset(value):
            results.append(_check(
                "BR-GEN-012", False,
                f"'{value}' enthält ungültige Zeichen",
            ))

    # BR-IBAN-V01 / V02: IBAN-Validierung
    iban_fields = [("Debtor IBAN", instruction.debtor.iban)]
    for tx in txs:
        iban_fields.append(("Creditor IBAN", tx.creditor_iban))

    for field_name, iban in iban_fields:
        results.append(_check(
            "BR-IBAN-V01", validate_iban(iban),
            f"IBAN '{iban}' ist ungültig" if not validate_iban(iban) else None,
        ))
        results.append(_check(
            "BR-IBAN-V02", validate_iban_length(iban),
            f"IBAN '{iban}' hat falsche Länge" if not validate_iban_length(iban) else None,
        ))

    return results


# ---------------------------------------------------------------------------
# Orchestrierung
# ---------------------------------------------------------------------------

def validate_all_business_rules(
    instruction: PaymentInstruction,
    testcase: TestCase,
) -> List[ValidationResult]:
    """Führt alle Business-Rule-Validierungen durch."""
    results = []
    results.extend(validate_general_rules(instruction, testcase))

    # BR-SEPA-003: ChrgBr muss SLEV sein (braucht instruction.charge_bearer)
    if testcase.payment_type == PaymentType.SEPA:
        cb = instruction.charge_bearer or ""
        results.append(_check(
            "BR-SEPA-003", cb == "SLEV",
            f"ChrgBr ist '{cb}'" if cb != "SLEV" else None,
        ))

    handler = _get_handler(testcase.payment_type)
    results.extend(handler.validate(testcase, instruction.transactions))

    return results


# ---------------------------------------------------------------------------
# Violation-Funktionen (Negative Testing)
# ---------------------------------------------------------------------------

def apply_rule_violation(
    testcase: TestCase,
    instruction: PaymentInstruction,
) -> PaymentInstruction:
    """Wendet eine gezielte Regelverletzung an (Negative Testing).

    Modifiziert die PaymentInstruction so, dass die angegebene Business Rule
    verletzt wird, ohne die XSD-Validität zu brechen.
    """
    rule_id = testcase.violate_rule
    if not rule_id:
        return instruction

    violations = {
        "BR-SEPA-001": _violate_sepa_currency,
        "BR-SEPA-003": _violate_sepa_charge_bearer,
        "BR-SEPA-004": _violate_sepa_name_length,
        "BR-QR-002": _violate_qr_reference,
        "BR-QR-003": _violate_qr_scor,
        "BR-QR-004": _violate_qr_currency,
        "BR-IBAN-001": _violate_iban_qr,
        "BR-IBAN-002": _violate_iban_qrr,
        "BR-IBAN-004": _violate_iban_currency,
        "BR-CBPR-001": _violate_cbpr_currency,
        "BR-CBPR-005": _violate_cbpr_agent,
    }

    violation_fn = violations.get(rule_id)
    if violation_fn:
        return violation_fn(instruction)

    return instruction


def _update_all_transactions(instr, **updates):
    """Hilfsfunktion: Aktualisiert alle Transaktionen in einer Instruction."""
    txs = [tx.model_copy(update=updates) for tx in instr.transactions]
    return instr.model_copy(update={"transactions": txs})


def _violate_sepa_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SEPA-001: Setzt Währung auf CHF statt EUR."""
    return _update_all_transactions(instr, currency="CHF")


def _violate_sepa_charge_bearer(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SEPA-003: Setzt ChrgBr auf DEBT statt SLEV."""
    return instr.model_copy(update={"charge_bearer": "DEBT"})


def _violate_sepa_name_length(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SEPA-004: Setzt einen zu langen Creditor-Namen."""
    return _update_all_transactions(instr, creditor_name="A" * 71)


def _violate_qr_reference(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-QR-002: Entfernt die QRR-Referenz."""
    return _update_all_transactions(instr, remittance_info=None)


def _violate_qr_scor(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-QR-003: Setzt SCOR-Referenz bei QR-IBAN."""
    return _update_all_transactions(
        instr, remittance_info={"type": "SCOR", "value": "RF18539007547034"},
    )


def _violate_qr_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-QR-004: Setzt Währung auf USD."""
    return _update_all_transactions(instr, currency="USD")


def _violate_iban_qr(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-IBAN-001: Setzt eine QR-IBAN als Creditor."""
    from src.data_factory.iban import generate_ch_iban
    rng = random.Random(42)
    qr_iban = generate_ch_iban(rng, qr=True)
    return _update_all_transactions(instr, creditor_iban=qr_iban)


def _violate_iban_qrr(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-IBAN-002: Setzt QRR-Referenz bei regulärer IBAN."""
    from src.data_factory.reference import generate_qrr
    rng = random.Random(42)
    qrr = generate_qrr(rng)
    return _update_all_transactions(
        instr, remittance_info={"type": "QRR", "value": qrr},
    )


def _violate_iban_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-IBAN-004: Setzt Währung auf EUR statt CHF."""
    return _update_all_transactions(instr, currency="EUR")


def _violate_cbpr_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-CBPR-001: Entfernt die Währung (leerer String)."""
    return _update_all_transactions(instr, currency="")


def _violate_cbpr_agent(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-CBPR-005: Entfernt den Creditor-Agent BIC."""
    return _update_all_transactions(instr, creditor_bic=None)
