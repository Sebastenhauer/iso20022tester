"""Violations Registry fuer Negative Testing von pacs.008.

Parallel zu ``src/validation/business_rules.py`` (Violations fuer
pain.001), aber mit eigenem Registry fuer die BR-CBPR-PACS-*-Rules.

Eine Violation-Funktion nimmt ein ``Pacs008BusinessMessage``-Objekt
entgegen und mutiert es so, dass die zugehoerige Rule genau einmal
fehlschlaegt. Die Pipeline ruft die passende Funktion vor dem
XML-Build auf, wenn ``testcase.violate_rule`` gesetzt ist.

Konflikt-Erkennung bei Chaining (mehrere ViolateRules gleichzeitig)
erfolgt via ``_PACS008_VIOLATION_FIELD_MAP``: Rules, die dasselbe
Feld mutieren, duerfen nicht in derselben Run-Chain kombiniert werden.
"""

from __future__ import annotations

from typing import Callable, Dict

from src.models.pacs008 import (
    AgentInfo,
    Pacs008BusinessMessage,
    SettlementMethod,
)


# ---------------------------------------------------------------------------
# Violation-Funktionen
# ---------------------------------------------------------------------------

def _violate_uetr_missing(bm: Pacs008BusinessMessage) -> Pacs008BusinessMessage:
    """BR-CBPR-PACS-001: UETR leeren.

    Nachtraeglich ein leeres UETR zu setzen ist tricky, weil das Pydantic-
    Modell ``uetr: str`` (required) verlangt. Wir umgehen das per
    object.__setattr__ und verlassen uns darauf, dass der Builder das
    in XML schreibt und der Validator es dann faengt.
    """
    for tx in bm.instruction.transactions:
        object.__setattr__(tx, "uetr", "")
    return bm


def _violate_uetr_invalid_format(bm: Pacs008BusinessMessage) -> Pacs008BusinessMessage:
    """BR-CBPR-PACS-015: UETR auf einen Non-UUIDv4-String setzen."""
    for tx in bm.instruction.transactions:
        object.__setattr__(tx, "uetr", "not-a-valid-uuid-string-01")
    return bm


def _violate_instg_agt_missing(bm: Pacs008BusinessMessage) -> Pacs008BusinessMessage:
    """BR-CBPR-PACS-002: InstgAgt ohne BICFI und ohne ClrSysMmbId."""
    bm.instruction.instructing_agent = AgentInfo(name="Nameless")
    return bm


def _violate_instd_agt_missing(bm: Pacs008BusinessMessage) -> Pacs008BusinessMessage:
    """BR-CBPR-PACS-003: InstdAgt ohne Identifikation."""
    bm.instruction.instructed_agent = AgentInfo(name="Nameless")
    return bm


def _violate_sttlm_mtd_cove(bm: Pacs008BusinessMessage) -> Pacs008BusinessMessage:
    """BR-CBPR-PACS-004: SttlmMtd auf COVE (out of scope V1) setzen."""
    bm.instruction.settlement_method = SettlementMethod.COVE
    return bm


def _violate_bah_msg_def_idr(bm: Pacs008BusinessMessage) -> Pacs008BusinessMessage:
    """BR-CBPR-PACS-007: BAH MsgDefIdr faelschen."""
    bm.bah_msg_def_idr = "pacs.008.001.09"  # wrong version
    return bm


def _violate_bah_biz_svc(bm: Pacs008BusinessMessage) -> Pacs008BusinessMessage:
    """BR-CBPR-PACS-008: BAH BizSvc faelschen."""
    bm.bah_biz_svc = "swift.wrong.01"
    return bm


def _violate_charge_bearer(bm: Pacs008BusinessMessage) -> Pacs008BusinessMessage:
    """BR-CBPR-PACS-010: ChrgBr auf invaliden Wert setzen."""
    for tx in bm.instruction.transactions:
        object.__setattr__(tx, "charge_bearer", "XXXX")
    return bm


def _violate_currency(bm: Pacs008BusinessMessage) -> Pacs008BusinessMessage:
    """BR-CBPR-PACS-011: Waehrung auf nicht-ISO-4217 setzen."""
    for tx in bm.instruction.transactions:
        object.__setattr__(tx, "instructed_currency", "X9X")
    return bm


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def get_pacs008_violations_registry() -> Dict[str, Callable[[Pacs008BusinessMessage], Pacs008BusinessMessage]]:
    """Liefert das Violations-Registry (Rule-ID -> Violation-Funktion)."""
    return {
        "BR-CBPR-PACS-001": _violate_uetr_missing,
        "BR-CBPR-PACS-002": _violate_instg_agt_missing,
        "BR-CBPR-PACS-003": _violate_instd_agt_missing,
        "BR-CBPR-PACS-004": _violate_sttlm_mtd_cove,
        "BR-CBPR-PACS-007": _violate_bah_msg_def_idr,
        "BR-CBPR-PACS-008": _violate_bah_biz_svc,
        "BR-CBPR-PACS-010": _violate_charge_bearer,
        "BR-CBPR-PACS-011": _violate_currency,
        "BR-CBPR-PACS-015": _violate_uetr_invalid_format,
        # Not violatable (structural / cross-field / schema-enforced):
        # - 005, 006 Adressen (Modell-Constraint + XSD)
        # - 009 Banktag (Logik ok, aber schon via Excel uebersteuerbar)
        # - 012 ChrgsInf (nur wenn vorhanden)
        # - 013, 014 NbOfTxs/CtrlSum (werden vom Builder deterministisch gesetzt)
    }


# Feld-Gruppen fuer Konflikt-Erkennung bei Violation-Chaining
_PACS008_VIOLATION_FIELD_MAP: Dict[str, str] = {
    "BR-CBPR-PACS-001": "uetr",
    "BR-CBPR-PACS-015": "uetr",
    "BR-CBPR-PACS-002": "instg_agt",
    "BR-CBPR-PACS-003": "instd_agt",
    "BR-CBPR-PACS-004": "sttlm_mtd",
    "BR-CBPR-PACS-007": "bah_msg_def_idr",
    "BR-CBPR-PACS-008": "bah_biz_svc",
    "BR-CBPR-PACS-010": "charge_bearer",
    "BR-CBPR-PACS-011": "currency",
}


def apply_pacs008_violation(
    bm: Pacs008BusinessMessage,
    rule_id: str,
) -> Pacs008BusinessMessage:
    """Wendet eine einzelne Violation auf eine BusinessMessage an.

    Raises:
        KeyError wenn rule_id nicht im Registry ist.
    """
    registry = get_pacs008_violations_registry()
    if rule_id not in registry:
        raise KeyError(
            f"Violation-Rule '{rule_id}' ist im pacs.008 Registry nicht vorhanden. "
            f"Verfuegbar: {', '.join(sorted(registry.keys()))}"
        )
    return registry[rule_id](bm)
