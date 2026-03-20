"""XML-Generator: Baut pain.001.001.09 XML-Struktur mit lxml.

Nutzt die wiederverwendbaren Builder aus `builders.py` für
Adressen, Parteien, Beträge und Referenzen.
"""

from lxml import etree

from src.models.testcase import PaymentInstruction, Transaction
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


def build_pain001_xml(payment_instruction: PaymentInstruction) -> etree._Element:
    """Baut ein komplettes pain.001.001.09 XML-Dokument.

    Args:
        payment_instruction: Die Zahlungsinstruktion mit allen Daten.

    Returns:
        lxml Element-Tree des Dokuments.
    """
    # Document root
    doc = etree.Element(f"{{{PAIN001_NS}}}Document", nsmap=NSMAP)
    cstmr = el(doc, "CstmrCdtTrfInitn")

    # === A-Level: GrpHdr ===
    grp_hdr = el(cstmr, "GrpHdr")
    el(grp_hdr, "MsgId", payment_instruction.msg_id)
    el(grp_hdr, "CreDtTm", payment_instruction.cre_dt_tm)
    nb_of_txs = str(len(payment_instruction.transactions))
    el(grp_hdr, "NbOfTxs", nb_of_txs)
    ctrl_sum = sum(tx.amount for tx in payment_instruction.transactions)
    el(grp_hdr, "CtrlSum", str(ctrl_sum))
    build_initiating_party(grp_hdr, payment_instruction.debtor.name)

    # === B-Level: PmtInf ===
    pmt_inf = el(cstmr, "PmtInf")
    el(pmt_inf, "PmtInfId", payment_instruction.pmt_inf_id)
    el(pmt_inf, "PmtMtd", payment_instruction.pmt_mtd)
    el(pmt_inf, "NbOfTxs", nb_of_txs)
    el(pmt_inf, "CtrlSum", str(ctrl_sum))

    # PmtTpInf
    build_payment_type_info(
        pmt_inf,
        service_level=payment_instruction.service_level,
        local_instrument=payment_instruction.local_instrument,
        category_purpose=payment_instruction.category_purpose,
    )

    # ReqdExctnDt
    reqd_exctn_dt = el(pmt_inf, "ReqdExctnDt")
    el(reqd_exctn_dt, "Dt", payment_instruction.reqd_exctn_dt)

    # Debtor
    build_debtor_elements(pmt_inf, payment_instruction.debtor)

    # ChrgBr (B-Level)
    if payment_instruction.charge_bearer:
        el(pmt_inf, "ChrgBr", payment_instruction.charge_bearer)

    # === C-Level: CdtTrfTxInf ===
    for tx in payment_instruction.transactions:
        _build_transaction(pmt_inf, tx)

    return doc


def serialize_xml(doc: etree._Element, pretty_print: bool = True) -> bytes:
    """Serialisiert ein XML-Element zu Bytes."""
    return etree.tostring(
        doc,
        pretty_print=pretty_print,
        xml_declaration=True,
        encoding="UTF-8",
    )
