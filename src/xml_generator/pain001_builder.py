"""XML-Generator: Baut pain.001.001.09 XML-Struktur mit lxml.

Unterstützt sowohl einzelne als auch mehrere PmtInf-Blöcke
(Multi-Payment) pro Dokument.
"""

from typing import List

from lxml import etree

from src.models.testcase import Pain001Document, PaymentInstruction, Transaction
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

    # Amt
    build_amount(cdt_trf, tx.amount, tx.currency)

    # Creditor: CdtrAgt + Cdtr + CdtrAcct
    build_creditor_elements(cdt_trf, tx)

    # RmtInf
    if tx.remittance_info:
        build_remittance_info(cdt_trf, tx.remittance_info)


def _build_pmt_inf(parent: etree._Element, instr: PaymentInstruction) -> None:
    """Baut einen PmtInf-Block (B-Level) mit allen Transaktionen (C-Level)."""
    pmt_inf = el(parent, "PmtInf")

    nb_of_txs = str(len(instr.transactions))
    ctrl_sum = sum(tx.amount for tx in instr.transactions)

    el(pmt_inf, "PmtInfId", instr.pmt_inf_id)
    el(pmt_inf, "PmtMtd", instr.pmt_mtd)
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


def build_pain001_xml(instruction: PaymentInstruction) -> etree._Element:
    """Baut ein pain.001-Dokument mit einem PmtInf-Block (Einzel-Payment).

    Convenience-Wrapper für Abwärtskompatibilität.
    """
    doc = Pain001Document(
        msg_id=instruction.msg_id,
        cre_dt_tm=instruction.cre_dt_tm,
        initiating_party_name=instruction.debtor.name,
        payment_instructions=[instruction],
    )
    return build_pain001_document(doc)


def build_pain001_document(document: Pain001Document) -> etree._Element:
    """Baut ein komplettes pain.001.001.09 XML-Dokument.

    Unterstützt 1..n PmtInf-Blöcke (Multi-Payment). GrpHdr aggregiert
    NbOfTxs und CtrlSum über alle PmtInf-Blöcke.

    Args:
        document: Das Dokument mit Message-Metadaten und PaymentInstructions.

    Returns:
        lxml Element-Tree des Dokuments.
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
    el(grp_hdr, "NbOfTxs", str(len(all_txs)))
    el(grp_hdr, "CtrlSum", str(sum(tx.amount for tx in all_txs)))
    build_initiating_party(grp_hdr, document.initiating_party_name)

    # === B-Level: PmtInf (1..n) ===
    for instr in document.payment_instructions:
        _build_pmt_inf(cstmr, instr)

    return doc


def serialize_xml(doc: etree._Element, pretty_print: bool = True) -> bytes:
    """Serialisiert ein XML-Element zu Bytes."""
    return etree.tostring(
        doc,
        pretty_print=pretty_print,
        xml_declaration=True,
        encoding="UTF-8",
    )
