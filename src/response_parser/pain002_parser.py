"""Parser für pain.002.001.10 (CustomerPaymentStatusReport).

Liest pain.002 XML-Dateien, extrahiert Transaktionsstatus (ACTC, RJCT, PDNG etc.)
und korreliert sie mit vorher generierten pain.001 Testfällen über MsgId/EndToEndId.
"""

from typing import Dict, List, Optional, Tuple

from lxml import etree

from src.models.testcase import (
    Pain002Result,
    TestCaseResult,
    TransactionStatusInfo,
)

# pain.002.001.10 Namespace
PAIN002_NS = "urn:iso:std:iso:20022:tech:xsd:pain.002.001.10"


def _find(parent: etree._Element, xpath: str) -> Optional[etree._Element]:
    """Sucht ein Element mit pain.002-Namespace."""
    result = parent.find(xpath, namespaces={"ns": PAIN002_NS})
    return result


def _findall(parent: etree._Element, xpath: str) -> List[etree._Element]:
    """Sucht alle Elemente mit pain.002-Namespace."""
    return parent.findall(xpath, namespaces={"ns": PAIN002_NS})


def _text(parent: etree._Element, xpath: str) -> Optional[str]:
    """Extrahiert Text aus einem Namespace-qualifizierten XPath."""
    elem = _find(parent, xpath)
    return elem.text if elem is not None else None


def parse_pain002(xml_path: str) -> Pain002Result:
    """Parst eine pain.002.001.10 XML-Datei.

    Extrahiert:
    - GrpHdr/MsgId: Message-ID der pain.002
    - OrgnlGrpInfAndSts: Original-MsgId und Gruppen-Status
    - OrgnlPmtInfAndSts: Per-Payment-Info und Per-Transaction Status

    Args:
        xml_path: Pfad zur pain.002 XML-Datei

    Returns:
        Pain002Result mit allen extrahierten Statusdaten

    Raises:
        ValueError: Bei ungültigem XML oder fehlendem Root-Element
    """
    tree = etree.parse(xml_path)
    root = tree.getroot()

    # Root kann <Document> sein oder direkt <CstmrPmtStsRpt>
    doc = root
    if root.tag == f"{{{PAIN002_NS}}}Document":
        doc = _find(root, "ns:CstmrPmtStsRpt")
    elif root.tag == f"{{{PAIN002_NS}}}CstmrPmtStsRpt":
        doc = root
    else:
        # Versuche ohne Namespace (z.B. bei fehlender NS-Deklaration)
        doc = root.find("CstmrPmtStsRpt")
        if doc is None:
            doc = root

    if doc is None:
        raise ValueError(f"Kein CstmrPmtStsRpt-Element in {xml_path}")

    # GrpHdr
    pain002_msg_id = _text(doc, "ns:GrpHdr/ns:MsgId") or ""

    # OrgnlGrpInfAndSts
    orig_grp = _find(doc, "ns:OrgnlGrpInfAndSts")
    original_msg_id = ""
    group_status = None
    if orig_grp is not None:
        original_msg_id = _text(orig_grp, "ns:OrgnlMsgId") or ""
        group_status = _text(orig_grp, "ns:GrpSts")

    # OrgnlPmtInfAndSts (kann 0..n vorkommen)
    pmt_inf_statuses = _findall(doc, "ns:OrgnlPmtInfAndSts")

    original_pmt_inf_id = None
    payment_status = None
    transaction_statuses: List[TransactionStatusInfo] = []

    for pmt_inf_sts in pmt_inf_statuses:
        if original_pmt_inf_id is None:
            original_pmt_inf_id = _text(pmt_inf_sts, "ns:OrgnlPmtInfId")
        if payment_status is None:
            payment_status = _text(pmt_inf_sts, "ns:PmtInfSts")

        # TxInfAndSts (kann 0..n vorkommen)
        tx_statuses = _findall(pmt_inf_sts, "ns:TxInfAndSts")
        for tx_sts in tx_statuses:
            e2e_id = _text(tx_sts, "ns:OrgnlEndToEndId") or ""
            tx_status = _text(tx_sts, "ns:TxSts") or ""

            # Reason: StsRsnInf/Rsn/Cd oder StsRsnInf/Rsn/Prtry
            reason_code = _text(tx_sts, "ns:StsRsnInf/ns:Rsn/ns:Cd")
            if reason_code is None:
                reason_code = _text(tx_sts, "ns:StsRsnInf/ns:Rsn/ns:Prtry")

            reason_additional = _text(
                tx_sts, "ns:StsRsnInf/ns:AddtlInf"
            )

            transaction_statuses.append(
                TransactionStatusInfo(
                    end_to_end_id=e2e_id,
                    status=tx_status,
                    reason_code=reason_code,
                    reason_additional=reason_additional,
                )
            )

    return Pain002Result(
        pain002_msg_id=pain002_msg_id,
        original_msg_id=original_msg_id,
        original_pmt_inf_id=original_pmt_inf_id,
        group_status=group_status,
        payment_status=payment_status,
        transaction_statuses=transaction_statuses,
        pain002_file_path=xml_path,
    )


def correlate_with_results(
    pain002_results: List[Pain002Result],
    testcase_results: List[TestCaseResult],
    instructions: Dict[str, "PaymentInstruction"],
) -> List[TestCaseResult]:
    """Korreliert pain.002 Ergebnisse mit Testfall-Ergebnissen.

    Matching-Strategie:
    1. OrgnlMsgId → instruction.msg_id (eindeutig pro Testfall)
    2. OrgnlEndToEndId → transaction.end_to_end_id (für Transaktions-Details)

    Args:
        pain002_results: Geparste pain.002 Ergebnisse
        testcase_results: Bestehende Testfall-Ergebnisse aus der Generierung
        instructions: Dict von testcase_id → PaymentInstruction
                      (für MsgId/E2E-ID Zuordnung)

    Returns:
        Aktualisierte TestCaseResult-Liste mit pain002_result-Feld
    """
    # Index: msg_id → testcase_id
    msg_id_to_tc: Dict[str, str] = {}
    for tc_id, instr in instructions.items():
        msg_id_to_tc[instr.msg_id] = tc_id

    # Index: end_to_end_id → testcase_id
    e2e_to_tc: Dict[str, str] = {}
    for tc_id, instr in instructions.items():
        for tx in instr.transactions:
            e2e_to_tc[tx.end_to_end_id] = tc_id

    # Index: testcase_id → result (für schnellen Zugriff)
    result_map: Dict[str, TestCaseResult] = {r.testcase_id: r for r in testcase_results}

    updated = []
    matched_tc_ids: set = set()

    for p002 in pain002_results:
        # Versuche Korrelation über OrgnlMsgId
        tc_id = msg_id_to_tc.get(p002.original_msg_id)

        # Fallback: Korrelation über EndToEndId der Transaktionen
        if tc_id is None and p002.transaction_statuses:
            for tx_sts in p002.transaction_statuses:
                tc_id = e2e_to_tc.get(tx_sts.end_to_end_id)
                if tc_id is not None:
                    break

        if tc_id is not None:
            matched_tc_ids.add(tc_id)
            if tc_id in result_map:
                result_map[tc_id] = result_map[tc_id].model_copy(
                    update={"pain002_result": p002}
                )

    return list(result_map.values())


def parse_pain002_files(xml_paths: List[str]) -> Tuple[List[Pain002Result], List[str]]:
    """Parst mehrere pain.002-Dateien.

    Args:
        xml_paths: Liste von Pfaden zu pain.002 XML-Dateien

    Returns:
        Tuple aus (erfolgreich geparste Ergebnisse, Fehlermeldungen)
    """
    results: List[Pain002Result] = []
    errors: List[str] = []

    for path in xml_paths:
        try:
            result = parse_pain002(path)
            results.append(result)
        except Exception as e:
            errors.append(f"{path}: {e}")

    return results, errors
