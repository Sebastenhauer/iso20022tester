"""XML-Generator: Baut pain.001.001.09 XML-Struktur mit lxml.

Unterstützt SPS 2025 und CBPR+ SR2026 mit standard-abhängiger Struktur.
"""

from datetime import datetime, timezone
from typing import List

from lxml import etree

from src.models.testcase import (
    Pain001Document,
    PaymentInstruction,
    Standard,
    Transaction,
)
from src.xml_generator.builders import (
    build_amount,
    build_creditor_elements,
    build_debtor_elements,
    build_initiating_party,
    build_payment_type_info,
    build_remittance_info,
    el,
)
from src.xml_generator.namespace import NSMAP, PAIN001_NS


def _build_transaction(parent: etree._Element, tx: Transaction) -> None:
    """Baut ein CdtTrfTxInf-Element (C-Level)."""
    cdt_trf = el(parent, "CdtTrfTxInf")

    # PmtId
    pmt_id = el(cdt_trf, "PmtId")
    el(pmt_id, "EndToEndId", tx.end_to_end_id)
    if tx.uetr:
        el(pmt_id, "UETR", tx.uetr)

    # Amt
    build_amount(cdt_trf, tx.amount, tx.currency)

    # Creditor: CdtrAgt + Cdtr + CdtrAcct
    build_creditor_elements(cdt_trf, tx)

    # RmtInf
    if tx.remittance_info:
        build_remittance_info(cdt_trf, tx.remittance_info)


def _build_pmt_inf(
    parent: etree._Element,
    instr: PaymentInstruction,
    standard: Standard = Standard.SPS_2025,
) -> None:
    """Baut einen PmtInf-Block (B-Level) mit allen Transaktionen (C-Level)."""
    pmt_inf = el(parent, "PmtInf")

    el(pmt_inf, "PmtInfId", instr.pmt_inf_id)
    el(pmt_inf, "PmtMtd", instr.pmt_mtd)

    # SPS: NbOfTxs + CtrlSum auf B-Level; CBPR+: entfaellt
    if standard == Standard.SPS_2025:
        nb_of_txs = str(len(instr.transactions))
        ctrl_sum = sum(tx.amount for tx in instr.transactions)
        el(pmt_inf, "NbOfTxs", nb_of_txs)
        el(pmt_inf, "CtrlSum", str(ctrl_sum))

    # PmtTpInf
    build_payment_type_info(
        pmt_inf,
        service_level=instr.service_level,
        local_instrument=instr.local_instrument,
        category_purpose=instr.category_purpose,
    )

    # ReqdExctnDt
    reqd_exctn_dt = el(pmt_inf, "ReqdExctnDt")
    el(reqd_exctn_dt, "Dt", instr.reqd_exctn_dt)

    # Debtor
    build_debtor_elements(pmt_inf, instr.debtor)

    # ChrgBr (B-Level)
    if instr.charge_bearer:
        el(pmt_inf, "ChrgBr", instr.charge_bearer)

    # C-Level: CdtTrfTxInf
    for tx in instr.transactions:
        _build_transaction(pmt_inf, tx)


def build_pain001_xml(
    instruction: PaymentInstruction,
    standard: Standard = Standard.SPS_2025,
) -> etree._Element:
    """Baut ein pain.001-Dokument mit einem PmtInf-Block (Einzel-Payment)."""
    cre_dt_tm = instruction.cre_dt_tm

    # CBPR+: CreDtTm muss UTC-Offset haben
    if standard == Standard.CBPR_PLUS_2026 and "+" not in cre_dt_tm and "Z" not in cre_dt_tm:
        cre_dt_tm = datetime.now(timezone.utc).astimezone().isoformat()

    # CBPR+: PmtInfId muss MsgId entsprechen (Rule R8)
    if standard == Standard.CBPR_PLUS_2026:
        instruction = instruction.model_copy(update={"pmt_inf_id": instruction.msg_id})

    doc = Pain001Document(
        msg_id=instruction.msg_id,
        cre_dt_tm=cre_dt_tm,
        initiating_party_name=instruction.debtor.name,
        payment_instructions=[instruction],
    )
    return build_pain001_document(doc, standard=standard)


def build_pain001_document(
    document: Pain001Document,
    standard: Standard = Standard.SPS_2025,
) -> etree._Element:
    """Baut ein komplettes pain.001.001.09 XML-Dokument.

    SPS 2025: 1..n PmtInf mit NbOfTxs/CtrlSum auf allen Levels.
    CBPR+ SR2026: Genau 1 PmtInf, kein CtrlSum auf GrpHdr/PmtInf Level,
                  NbOfTxs immer "1", PmtInfId = MsgId.
    """
    all_txs = [
        tx
        for instr in document.payment_instructions
        for tx in instr.transactions
    ]

    # Document root
    doc = etree.Element(f"{{{PAIN001_NS}}}Document", nsmap=NSMAP)
    cstmr = el(doc, "CstmrCdtTrfInitn")

    # === A-Level: GrpHdr ===
    grp_hdr = el(cstmr, "GrpHdr")
    el(grp_hdr, "MsgId", document.msg_id)
    el(grp_hdr, "CreDtTm", document.cre_dt_tm)

    if standard == Standard.CBPR_PLUS_2026:
        # CBPR+: NbOfTxs immer "1", kein CtrlSum
        el(grp_hdr, "NbOfTxs", "1")
    else:
        # SPS: Aggregiert ueber alle PmtInf
        el(grp_hdr, "NbOfTxs", str(len(all_txs)))
        el(grp_hdr, "CtrlSum", str(sum(tx.amount for tx in all_txs)))

    build_initiating_party(grp_hdr, document.initiating_party_name)

    # === B-Level: PmtInf (1..n für SPS, genau 1 für CBPR+) ===
    for instr in document.payment_instructions:
        _build_pmt_inf(cstmr, instr, standard=standard)

    return doc


def serialize_xml(doc: etree._Element, pretty_print: bool = True) -> bytes:
    """Serialisiert ein XML-Element zu Bytes."""
    return etree.tostring(
        doc,
        pretty_print=pretty_print,
        xml_declaration=True,
        encoding="UTF-8",
    )
