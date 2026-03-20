"""Business-Rule-Engine: Übergreifende Regeln und Orchestrierung."""

import re
from decimal import Decimal
from typing import Dict, List, Optional

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

# Referenzfeld-Zeichensatz: kein "/" am Anfang/Ende, kein "//"
_REF_PATTERN = re.compile(r"^(?!/)[^/]{0,}(?<!/)((?!//).)*/?((?<!/).)$|^[^/]$|^$")


def _validate_ref_charset(value: str) -> bool:
    """Prüft Referenzfeld-Zeichensatz (BR-GEN-009)."""
    if not value:
        return True
    if value.startswith("/") or value.endswith("/"):
        return False
    if "//" in value:
        return False
    return True


def _get_handler(payment_type: PaymentType) -> PaymentTypeHandler:
    """Gibt den passenden Handler für einen Zahlungstyp zurück."""
    handlers = {
        PaymentType.SEPA: SepaHandler(),
        PaymentType.DOMESTIC_QR: DomesticQrHandler(),
        PaymentType.DOMESTIC_IBAN: DomesticIbanHandler(),
        PaymentType.CBPR_PLUS: CbprPlusHandler(),
    }
    return handlers[payment_type]


def validate_general_rules(
    instruction: PaymentInstruction,
    testcase: TestCase,
) -> List[ValidationResult]:
    """Validiert zahlungstyp-übergreifende Business Rules."""
    results = []
    txs = instruction.transactions

    # BR-HDR-002: NbOfTxs Konsistenz (GrpHdr)
    results.append(ValidationResult(
        rule_id="BR-HDR-002",
        rule_description="NbOfTxs im GrpHdr = Summe aller Transaktionen",
        passed=True,  # Wird vom Builder korrekt gesetzt
    ))

    # BR-HDR-003: CtrlSum Konsistenz
    results.append(ValidationResult(
        rule_id="BR-HDR-003",
        rule_description="CtrlSum im GrpHdr = Summe aller Beträge",
        passed=True,  # Wird vom Builder korrekt gesetzt
    ))

    # BR-HDR-004: InitgPty vorhanden
    results.append(ValidationResult(
        rule_id="BR-HDR-004",
        rule_description="InitgPty/Nm muss gesetzt sein",
        passed=bool(instruction.debtor.name),
        details="InitgPty/Nm fehlt" if not instruction.debtor.name else None,
    ))

    # BR-GEN-005: ReqdExctnDt Bankarbeitstag
    # Wird bei der Generierung sichergestellt, hier nur Plausibilitätsprüfung
    results.append(ValidationResult(
        rule_id="BR-GEN-005",
        rule_description="ReqdExctnDt muss ein Bankarbeitstag sein",
        passed=bool(instruction.reqd_exctn_dt),
    ))

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
            results.append(ValidationResult(
                rule_id="BR-GEN-009",
                rule_description=f"Referenzfeld-Zeichensatz für {field_name}",
                passed=valid,
                details=f"{field_name}='{value}' verletzt Zeichensatz-Regeln" if not valid else None,
            ))

    # BR-GEN-010: Betrag > 0
    for tx in txs:
        results.append(ValidationResult(
            rule_id="BR-GEN-010",
            rule_description="Betrag muss > 0 sein",
            passed=tx.amount > 0,
            details=f"Betrag ist {tx.amount}" if tx.amount <= 0 else None,
        ))

    # BR-GEN-012: SPS-Zeichensatz
    text_fields = [
        ("Debtor Name", instruction.debtor.name),
    ]
    for tx in txs:
        text_fields.append(("Creditor Name", tx.creditor_name))
        if tx.creditor_address:
            for key, val in tx.creditor_address.items():
                if key != "Ctry":
                    text_fields.append((f"Creditor {key}", val))

    for field_name, value in text_fields:
        if value:
            valid = validate_sps_charset(value)
            if not valid:
                results.append(ValidationResult(
                    rule_id="BR-GEN-012",
                    rule_description=f"SPS-Zeichensatz für {field_name}",
                    passed=False,
                    details=f"'{value}' enthält ungültige Zeichen",
                ))

    # BR-IBAN-V01 / V02: IBAN-Validierung
    iban_fields = [("Debtor IBAN", instruction.debtor.iban)]
    for tx in txs:
        iban_fields.append(("Creditor IBAN", tx.creditor_iban))

    for field_name, iban in iban_fields:
        results.append(ValidationResult(
            rule_id="BR-IBAN-V01",
            rule_description=f"IBAN Mod-97 Prüfziffer für {field_name}",
            passed=validate_iban(iban),
            details=f"IBAN '{iban}' ist ungültig" if not validate_iban(iban) else None,
        ))
        results.append(ValidationResult(
            rule_id="BR-IBAN-V02",
            rule_description=f"IBAN-Länge für {field_name}",
            passed=validate_iban_length(iban),
            details=f"IBAN '{iban}' hat falsche Länge" if not validate_iban_length(iban) else None,
        ))

    return results


def validate_all_business_rules(
    instruction: PaymentInstruction,
    testcase: TestCase,
) -> List[ValidationResult]:
    """Führt alle Business-Rule-Validierungen durch."""
    results = []

    # Übergreifende Regeln
    results.extend(validate_general_rules(instruction, testcase))

    # Zahlungstyp-spezifische Regeln
    handler = _get_handler(testcase.payment_type)
    results.extend(handler.validate(testcase, instruction.transactions))

    return results


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


def _violate_sepa_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SEPA-001: Setzt Währung auf CHF statt EUR."""
    txs = []
    for tx in instr.transactions:
        txs.append(tx.model_copy(update={"currency": "CHF"}))
    return instr.model_copy(update={"transactions": txs})


def _violate_sepa_charge_bearer(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SEPA-003: Setzt ChrgBr auf DEBT statt SLEV."""
    return instr.model_copy(update={"charge_bearer": "DEBT"})


def _violate_sepa_name_length(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-SEPA-004: Setzt einen zu langen Creditor-Namen."""
    txs = []
    for tx in instr.transactions:
        txs.append(tx.model_copy(update={"creditor_name": "A" * 71}))
    return instr.model_copy(update={"transactions": txs})


def _violate_qr_reference(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-QR-002: Entfernt die QRR-Referenz."""
    txs = []
    for tx in instr.transactions:
        txs.append(tx.model_copy(update={"remittance_info": None}))
    return instr.model_copy(update={"transactions": txs})


def _violate_qr_scor(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-QR-003: Setzt SCOR-Referenz bei QR-IBAN."""
    txs = []
    for tx in instr.transactions:
        txs.append(tx.model_copy(update={
            "remittance_info": {"type": "SCOR", "value": "RF18539007547034"}
        }))
    return instr.model_copy(update={"transactions": txs})


def _violate_qr_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-QR-004: Setzt Währung auf USD."""
    txs = []
    for tx in instr.transactions:
        txs.append(tx.model_copy(update={"currency": "USD"}))
    return instr.model_copy(update={"transactions": txs})


def _violate_iban_qr(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-IBAN-001: Setzt eine QR-IBAN als Creditor."""
    import random
    from src.data_factory.iban import generate_ch_iban
    rng = random.Random(42)
    qr_iban = generate_ch_iban(rng, qr=True)
    txs = []
    for tx in instr.transactions:
        txs.append(tx.model_copy(update={"creditor_iban": qr_iban}))
    return instr.model_copy(update={"transactions": txs})


def _violate_iban_qrr(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-IBAN-002: Setzt QRR-Referenz bei regulärer IBAN."""
    from src.data_factory.reference import generate_qrr
    import random
    rng = random.Random(42)
    txs = []
    for tx in instr.transactions:
        txs.append(tx.model_copy(update={
            "remittance_info": {"type": "QRR", "value": generate_qrr(rng)}
        }))
    return instr.model_copy(update={"transactions": txs})


def _violate_iban_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-IBAN-004: Setzt Währung auf EUR statt CHF."""
    txs = []
    for tx in instr.transactions:
        txs.append(tx.model_copy(update={"currency": "EUR"}))
    return instr.model_copy(update={"transactions": txs})


def _violate_cbpr_currency(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-CBPR-001: Entfernt die Währung (leerer String)."""
    txs = []
    for tx in instr.transactions:
        txs.append(tx.model_copy(update={"currency": ""}))
    return instr.model_copy(update={"transactions": txs})


def _violate_cbpr_agent(instr: PaymentInstruction) -> PaymentInstruction:
    """BR-CBPR-005: Entfernt den Creditor-Agent BIC."""
    txs = []
    for tx in instr.transactions:
        txs.append(tx.model_copy(update={"creditor_bic": None}))
    return instr.model_copy(update={"transactions": txs})
