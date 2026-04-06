"""XML-Generator: Baut pain.001.001.09 XML-Struktur mit lxml.

Unterstützt SPS 2025 und CBPR+ SR2026 via Strategy-Pattern.
Neue Standards (z.B. EPC SEPA) können durch Hinzufügen einer
StandardStrategy implementiert werden.
"""

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
    build_purpose,
    build_regulatory_reporting,
    build_remittance_info,
    build_tax_remittance,
    build_ultimate_creditor,
    build_ultimate_debtor,
    el,
)
from src.xml_generator.namespace import NSMAP, PAIN001_NS
from src.xml_generator.standard_strategy import StandardStrategy, get_strategy


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

    # UltmtDbtr (C-Level, optional — XSD: nach Amt, vor CdtrAgt)
    if tx.ultimate_debtor:
        build_ultimate_debtor(cdt_trf, tx.ultimate_debtor)

    # Creditor: CdtrAgt + Cdtr + CdtrAcct
    build_creditor_elements(cdt_trf, tx)

    # UltmtCdtr (C-Level, optional — XSD: nach CdtrAcct, vor Purp)
    if tx.ultimate_creditor:
        build_ultimate_creditor(cdt_trf, tx.ultimate_creditor)

    # Purp (C-Level, optional)
    build_purpose(cdt_trf, tx.purpose_code)

    # RgltryRptg (C-Level, optional)
    if tx.regulatory_reporting:
        build_regulatory_reporting(cdt_trf, tx.regulatory_reporting)

    # RmtInf (mit optionalem TaxRmt innerhalb Strd)
    if tx.remittance_info or tx.tax_remittance:
        rmt_inf = None
        if tx.remittance_info:
            rmt_inf = build_remittance_info(cdt_trf, tx.remittance_info)
        if tx.tax_remittance:
            if rmt_inf is None:
                rmt_inf = el(cdt_trf, "RmtInf")
            # TaxRmt lebt in Strd — finde oder erstelle Strd-Element
            strd = rmt_inf.find(f"{{{PAIN001_NS}}}Strd")
            if strd is None:
                strd = el(rmt_inf, "Strd")
            build_tax_remittance(strd, tx.tax_remittance)


def _build_pmt_inf(
    parent: etree._Element,
    instr: PaymentInstruction,
    strategy: StandardStrategy,
) -> None:
    """Baut einen PmtInf-Block (B-Level) mit allen Transaktionen (C-Level)."""
    pmt_inf = el(parent, "PmtInf")

    pmt_inf_id = strategy.prepare_pmt_inf_id(instr.pmt_inf_id, instr.msg_id)
    el(pmt_inf, "PmtInfId", pmt_inf_id)
    el(pmt_inf, "PmtMtd", instr.pmt_mtd)

    # BtchBookg (optional, XSD-Position: nach PmtMtd, vor NbOfTxs)
    if instr.batch_booking is not None:
        el(pmt_inf, "BtchBookg", str(instr.batch_booking).lower())

    nb = strategy.pmt_inf_nb_of_txs(instr.transactions)
    if nb is not None:
        el(pmt_inf, "NbOfTxs", nb)

    cs = strategy.pmt_inf_ctrl_sum(instr.transactions)
    if cs is not None:
        el(pmt_inf, "CtrlSum", cs)

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

    # UltmtDbtr (B-Level, optional — XSD: nach DbtrAgt, vor ChrgBr)
    if instr.ultimate_debtor:
        build_ultimate_debtor(pmt_inf, instr.ultimate_debtor)

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
    strategy = get_strategy(standard)
    cre_dt_tm = strategy.prepare_cre_dt_tm(instruction.cre_dt_tm)

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

    Standard-abhängiges Verhalten (NbOfTxs, CtrlSum, PmtInfId, CreDtTm)
    wird über die StandardStrategy gesteuert.
    """
    strategy = get_strategy(standard)

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
    el(grp_hdr, "NbOfTxs", strategy.grp_hdr_nb_of_txs(all_txs))

    ctrl_sum = strategy.grp_hdr_ctrl_sum(all_txs)
    if ctrl_sum is not None:
        el(grp_hdr, "CtrlSum", ctrl_sum)

    build_initiating_party(grp_hdr, document.initiating_party_name)

    # === B-Level: PmtInf (1..n) ===
    for instr in document.payment_instructions:
        _build_pmt_inf(cstmr, instr, strategy)

    return doc


def serialize_xml(doc: etree._Element, pretty_print: bool = True) -> bytes:
    """Serialisiert ein XML-Element zu Bytes."""
    return etree.tostring(
        doc,
        pretty_print=pretty_print,
        xml_declaration=True,
        encoding="UTF-8",
    )
