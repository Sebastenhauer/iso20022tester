"""Business-Rule-Validation fuer CBPR+ pacs.008.

Eigenstaendiger Validator parallel zu ``src/validation/business_rules.py``
(pain.001). Arbeitet mit ``Pacs008Instruction`` + ``Pacs008BusinessMessage``
statt ``PaymentInstruction`` + ``TestCase``.

Rule-IDs aus dem Katalog: BR-CBPR-PACS-001 .. 015.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import List, Optional

from src.models.pacs008 import (
    AgentInfo,
    Pacs008BusinessMessage,
    Pacs008Instruction,
    Pacs008Transaction,
    PartyInfo,
    SettlementMethod,
)
from src.models.pacs008 import BusinessRuleResultLite as RuleResult


_UUID4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_ISO_CCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# CBPR+ XSD erlaubt nur INDA, INGA, COVE. COVE ist in V1 out of scope
# (kein pacs.009 Generator), daher akzeptieren wir aktuell nur INDA + INGA.
_VALID_SETTLEMENT_METHODS = {"INDA", "INGA"}
_VALID_CHARGE_BEARER = {"DEBT", "CRED", "SHAR"}


def _r(rule_id: str, passed: bool, details: Optional[str]) -> RuleResult:
    """Kurz-Factory fuer RuleResult. Description wird aus dem Catalog geholt."""
    from src.validation.rule_catalog import get_rule

    try:
        rule = get_rule(rule_id)
        description = rule.description
    except (KeyError, ValueError):
        description = rule_id
    return RuleResult(
        rule_id=rule_id,
        rule_description=description,
        passed=passed,
        details=details,
    )


def _party_has_address(party: Optional[PartyInfo]) -> bool:
    if party is None:
        return False
    if not party.name:
        return False
    if party.postal_address is None or party.postal_address.is_empty():
        return False
    # Mindestens Ctry oder TwnNm oder StrtNm
    addr = party.postal_address
    return bool(addr.country or addr.town_name or addr.street_name)


def validate_pacs008(
    business_message: Pacs008BusinessMessage,
) -> List[RuleResult]:
    """Fuehrt alle CBPR+ pacs.008 Business Rules aus.

    Args:
        business_message: Die komplette Nachricht inkl. BAH und Instruction.

    Returns:
        Liste aller Rule-Ergebnisse (positiv und negativ).
    """
    results: List[RuleResult] = []
    instr = business_message.instruction

    # BAH Rules (BR-CBPR-PACS-007, 008)
    results.append(_r(
        "BR-CBPR-PACS-007",
        business_message.bah_msg_def_idr == "pacs.008.001.08",
        f"MsgDefIdr ist '{business_message.bah_msg_def_idr}' (muss 'pacs.008.001.08' sein)"
        if business_message.bah_msg_def_idr != "pacs.008.001.08" else None,
    ))
    results.append(_r(
        "BR-CBPR-PACS-008",
        business_message.bah_biz_svc == "swift.cbprplus.04",
        f"BizSvc ist '{business_message.bah_biz_svc}' (muss 'swift.cbprplus.04' sein)"
        if business_message.bah_biz_svc != "swift.cbprplus.04" else None,
    ))

    # BR-CBPR-PACS-013: NbOfTxs consistency
    actual_tx_count = len(instr.transactions)
    nb_ok = instr.number_of_transactions == actual_tx_count
    results.append(_r(
        "BR-CBPR-PACS-013",
        nb_ok,
        f"NbOfTxs={instr.number_of_transactions} aber {actual_tx_count} CdtTrfTxInf vorhanden"
        if not nb_ok else None,
    ))

    # BR-CBPR-PACS-014: CtrlSum consistency
    total = sum(
        (tx.interbank_settlement_amount or tx.instructed_amount) for tx in instr.transactions
    )
    total_q = Decimal(total).quantize(Decimal("0.01"))
    ctrl_q = instr.control_sum.quantize(Decimal("0.01"))
    ctrl_ok = total_q == ctrl_q
    results.append(_r(
        "BR-CBPR-PACS-014",
        ctrl_ok,
        f"CtrlSum={ctrl_q} aber Summe der IntrBkSttlmAmt={total_q}"
        if not ctrl_ok else None,
    ))

    # BR-CBPR-PACS-009: IntrBkSttlmDt Format + Banktag-Check
    date_str = instr.interbank_settlement_date or ""
    date_format_ok = bool(_ISO_DATE_PATTERN.match(date_str))
    date_is_weekday = False
    if date_format_ok:
        try:
            d = date.fromisoformat(date_str)
            date_is_weekday = d.weekday() < 5  # Mo-Fr
        except ValueError:
            date_format_ok = False
    results.append(_r(
        "BR-CBPR-PACS-009",
        date_format_ok and date_is_weekday,
        (
            f"IntrBkSttlmDt '{date_str}' hat falsches Format oder ist kein Werktag"
            if not (date_format_ok and date_is_weekday) else None
        ),
    ))

    # Per-Transaction Rules
    for tx in instr.transactions:
        _validate_transaction(tx, instr, results)

    return results


def _validate_transaction(
    tx: Pacs008Transaction,
    instr: Pacs008Instruction,
    results: List[RuleResult],
) -> None:
    """Laeuft alle Per-Tx-Rules fuer eine einzelne CdtTrfTxInf."""

    # BR-CBPR-PACS-001: UETR Pflicht
    has_uetr = bool(tx.uetr)
    results.append(_r(
        "BR-CBPR-PACS-001",
        has_uetr,
        "UETR fehlt auf PmtId" if not has_uetr else None,
    ))

    # BR-CBPR-PACS-015: UETR Format UUIDv4
    if has_uetr:
        uetr_ok = bool(_UUID4_PATTERN.match(tx.uetr))
        results.append(_r(
            "BR-CBPR-PACS-015",
            uetr_ok,
            f"UETR '{tx.uetr}' ist kein gueltiges UUIDv4" if not uetr_ok else None,
        ))

    # BR-CBPR-PACS-002: InstgAgt identifiziert
    instg_ok = instr.instructing_agent.has_identification
    results.append(_r(
        "BR-CBPR-PACS-002",
        instg_ok,
        "InstgAgt ohne BICFI oder ClrSysMmbId" if not instg_ok else None,
    ))

    # BR-CBPR-PACS-003: InstdAgt identifiziert
    instd_ok = instr.instructed_agent.has_identification
    results.append(_r(
        "BR-CBPR-PACS-003",
        instd_ok,
        "InstdAgt ohne BICFI oder ClrSysMmbId" if not instd_ok else None,
    ))

    # BR-CBPR-PACS-004: SttlmMtd gueltig
    mtd = instr.settlement_method.value if isinstance(instr.settlement_method, SettlementMethod) else str(instr.settlement_method)
    sttlm_ok = mtd in _VALID_SETTLEMENT_METHODS
    results.append(_r(
        "BR-CBPR-PACS-004",
        sttlm_ok,
        f"SttlmMtd '{mtd}' ist nicht erlaubt in V1 (INDA/INGA/CLRG)"
        if not sttlm_ok else None,
    ))

    # BR-CBPR-PACS-005: Creditor-Adresse strukturiert
    cdtr_addr_ok = _party_has_address(tx.creditor)
    results.append(_r(
        "BR-CBPR-PACS-005",
        cdtr_addr_ok,
        "Creditor: Nm oder PstlAdr/Ctry fehlt" if not cdtr_addr_ok else None,
    ))

    # BR-CBPR-PACS-006: Debtor-Adresse strukturiert
    dbtr_addr_ok = _party_has_address(tx.debtor)
    results.append(_r(
        "BR-CBPR-PACS-006",
        dbtr_addr_ok,
        "Debtor: Nm oder PstlAdr/Ctry fehlt" if not dbtr_addr_ok else None,
    ))

    # BR-CBPR-PACS-010: ChrgBr gueltig
    cb = tx.charge_bearer or ""
    cb_ok = cb in _VALID_CHARGE_BEARER
    results.append(_r(
        "BR-CBPR-PACS-010",
        cb_ok,
        f"ChrgBr '{cb}' ist nicht DEBT/CRED/SHAR" if not cb_ok else None,
    ))

    # BR-CBPR-PACS-011: Waehrung ISO 4217
    ccy = tx.instructed_currency or ""
    ccy_ok = bool(_ISO_CCY_PATTERN.match(ccy))
    results.append(_r(
        "BR-CBPR-PACS-011",
        ccy_ok,
        f"Waehrung '{ccy}' ist kein gueltiger ISO 4217 Code" if not ccy_ok else None,
    ))

    # BR-CBPR-PACS-012: ChrgsInf Konsistenz (wenn vorhanden, Agt Pflicht)
    for i, ci in enumerate(tx.charges_info):
        ok = ci.agent.has_identification
        results.append(_r(
            "BR-CBPR-PACS-012",
            ok,
            f"ChrgsInf[{i}] Agt ohne BICFI oder ClrSysMmbId" if not ok else None,
        ))
