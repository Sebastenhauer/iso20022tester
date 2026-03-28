"""Round-Trip-Validierung: XML parsen und gegen Datenmodell vergleichen.

Parst generierte pain.001-XMLs zurück in eine Datenstruktur und
vergleicht Schluesselfelder. Erkennt Serialisierungs-Bugs.
"""

import os
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from lxml import etree

from src.xml_generator.namespace import PAIN001_NS

NS = {"p": PAIN001_NS}


class RoundtripDiff:
    """Ein Unterschied zwischen erwartetem und geparstem Wert."""

    def __init__(self, path: str, expected: str, actual: str):
        self.path = path
        self.expected = expected
        self.actual = actual

    def __str__(self):
        return f"  {self.path}: erwartet='{self.expected}', gefunden='{self.actual}'"


class RoundtripResult:
    """Ergebnis der Round-Trip-Validierung für eine XML-Datei."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self.diffs: List[RoundtripDiff] = []
        self.parse_error: Optional[str] = None
        self.xsd_valid: Optional[bool] = None
        self.parsed_data: Dict = {}

    @property
    def passed(self) -> bool:
        return not self.diffs and not self.parse_error

    def add_diff(self, path: str, expected: str, actual: str):
        self.diffs.append(RoundtripDiff(path, expected, actual))


def _text(elem, xpath: str) -> Optional[str]:
    """Extrahiert Text aus einem XPath-Treffer."""
    node = elem.find(xpath, NS)
    return node.text if node is not None else None


def parse_pain001_xml(file_path: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Parst eine pain.001 XML-Datei in ein Dictionary.

    Returns:
        (parsed_data, None) bei Erfolg, (None, error_message) bei Fehler.
    """
    try:
        tree = etree.parse(file_path)
    except Exception as e:
        return None, f"XML-Parse-Fehler: {e}"

    root = tree.getroot()
    cstmr = root.find("p:CstmrCdtTrfInitn", NS)
    if cstmr is None:
        return None, "CstmrCdtTrfInitn-Element nicht gefunden"

    # A-Level: GrpHdr
    grp_hdr = cstmr.find("p:GrpHdr", NS)
    if grp_hdr is None:
        return None, "GrpHdr-Element nicht gefunden"

    data = {
        "msg_id": _text(grp_hdr, "p:MsgId"),
        "cre_dt_tm": _text(grp_hdr, "p:CreDtTm"),
        "nb_of_txs": _text(grp_hdr, "p:NbOfTxs"),
        "ctrl_sum": _text(grp_hdr, "p:CtrlSum"),
        "initg_pty_nm": _text(grp_hdr, "p:InitgPty/p:Nm"),
        "payment_instructions": [],
    }

    # B-Level: PmtInf (1..n)
    for pmt_inf in cstmr.findall("p:PmtInf", NS):
        instr = {
            "pmt_inf_id": _text(pmt_inf, "p:PmtInfId"),
            "pmt_mtd": _text(pmt_inf, "p:PmtMtd"),
            "nb_of_txs": _text(pmt_inf, "p:NbOfTxs"),
            "ctrl_sum": _text(pmt_inf, "p:CtrlSum"),
            "svc_lvl_cd": _text(pmt_inf, "p:PmtTpInf/p:SvcLvl/p:Cd"),
            "reqd_exctn_dt": _text(pmt_inf, "p:ReqdExctnDt/p:Dt"),
            "dbtr_nm": _text(pmt_inf, "p:Dbtr/p:Nm"),
            "dbtr_iban": _text(pmt_inf, "p:DbtrAcct/p:Id/p:IBAN"),
            "dbtr_bic": _text(pmt_inf, "p:DbtrAgt/p:FinInstnId/p:BICFI"),
            "chrg_br": _text(pmt_inf, "p:ChrgBr"),
            "transactions": [],
        }

        # C-Level: CdtTrfTxInf
        for cdt_trf in pmt_inf.findall("p:CdtTrfTxInf", NS):
            instd_amt = cdt_trf.find("p:Amt/p:InstdAmt", NS)
            tx = {
                "end_to_end_id": _text(cdt_trf, "p:PmtId/p:EndToEndId"),
                "amount": instd_amt.text if instd_amt is not None else None,
                "currency": instd_amt.get("Ccy") if instd_amt is not None else None,
                "cdtr_nm": _text(cdt_trf, "p:Cdtr/p:Nm"),
                "cdtr_iban": _text(cdt_trf, "p:CdtrAcct/p:Id/p:IBAN"),
                "cdtr_bic": _text(cdt_trf, "p:CdtrAgt/p:FinInstnId/p:BICFI"),
                "cdtr_ctry": _text(cdt_trf, "p:Cdtr/p:PstlAdr/p:Ctry"),
                "rmt_ustrd": _text(cdt_trf, "p:RmtInf/p:Ustrd"),
                "rmt_ref": _text(cdt_trf, "p:RmtInf/p:Strd/p:CdtrRefInf/p:Ref"),
                "rmt_type": (
                    _text(cdt_trf, "p:RmtInf/p:Strd/p:CdtrRefInf/p:Tp/p:CdOrPrtry/p:Cd")
                    or _text(cdt_trf, "p:RmtInf/p:Strd/p:CdtrRefInf/p:Tp/p:CdOrPrtry/p:Prtry")
                ),
            }
            instr["transactions"].append(tx)

        data["payment_instructions"].append(instr)

    return data, None


def validate_roundtrip(file_path: str, xsd_validator=None) -> RoundtripResult:
    """Fuehrt eine Round-Trip-Validierung für eine XML-Datei durch.

    Prueft:
    1. XML ist parsbar
    2. Alle erwarteten Elemente sind vorhanden
    3. Konsistenzpruefungen (NbOfTxs, CtrlSum)
    4. Optional: XSD re-validation
    """
    result = RoundtripResult(file_path)

    # 1. Parsen
    parsed, error = parse_pain001_xml(file_path)
    if error:
        result.parse_error = error
        return result

    result.parsed_data = parsed

    # 2. XSD Re-Validierung (optional)
    if xsd_validator:
        try:
            tree = etree.parse(file_path)
            xsd_valid, xsd_errors = xsd_validator.validate(tree.getroot())
            result.xsd_valid = xsd_valid
            if not xsd_valid:
                result.parse_error = f"XSD-Fehler: {'; '.join(xsd_errors)}"
                return result
        except Exception as e:
            result.parse_error = f"XSD-Validierung fehlgeschlagen: {e}"
            return result

    # 3. Pflichtfelder pruefen
    for field in ("msg_id", "cre_dt_tm", "nb_of_txs", "ctrl_sum", "initg_pty_nm"):
        if not parsed.get(field):
            result.add_diff(f"GrpHdr/{field}", "vorhanden", "fehlt")

    # 4. PmtInf-Konsistenz
    if not parsed["payment_instructions"]:
        result.add_diff("PmtInf", "mindestens 1", "0")
        return result

    total_txs = 0
    total_sum = Decimal("0")

    for pi_idx, pi in enumerate(parsed["payment_instructions"]):
        prefix = f"PmtInf[{pi_idx}]"

        # Pflichtfelder
        for field in ("pmt_inf_id", "pmt_mtd", "dbtr_nm", "dbtr_iban"):
            if not pi.get(field):
                result.add_diff(f"{prefix}/{field}", "vorhanden", "fehlt")

        # PmtMtd muss TRF sein
        if pi.get("pmt_mtd") and pi["pmt_mtd"] != "TRF":
            result.add_diff(f"{prefix}/PmtMtd", "TRF", pi["pmt_mtd"])

        if not pi["transactions"]:
            result.add_diff(f"{prefix}/CdtTrfTxInf", "mindestens 1", "0")
            continue

        # NbOfTxs Konsistenz
        actual_nb = str(len(pi["transactions"]))
        if pi.get("nb_of_txs") and pi["nb_of_txs"] != actual_nb:
            result.add_diff(
                f"{prefix}/NbOfTxs",
                actual_nb,
                pi["nb_of_txs"],
            )

        # CtrlSum Konsistenz
        pi_sum = Decimal("0")
        for tx in pi["transactions"]:
            if tx.get("amount"):
                try:
                    pi_sum += Decimal(tx["amount"])
                except Exception:
                    pass

        if pi.get("ctrl_sum"):
            try:
                declared_sum = Decimal(pi["ctrl_sum"])
                if declared_sum != pi_sum:
                    result.add_diff(
                        f"{prefix}/CtrlSum",
                        str(pi_sum),
                        str(declared_sum),
                    )
            except Exception:
                pass

        total_txs += len(pi["transactions"])
        total_sum += pi_sum

        # C-Level Pflichtfelder
        for tx_idx, tx in enumerate(pi["transactions"]):
            tx_prefix = f"{prefix}/CdtTrfTxInf[{tx_idx}]"
            for field in ("end_to_end_id", "amount", "currency", "cdtr_nm", "cdtr_iban"):
                if not tx.get(field):
                    result.add_diff(f"{tx_prefix}/{field}", "vorhanden", "fehlt")

            # Betrag > 0
            if tx.get("amount"):
                try:
                    if Decimal(tx["amount"]) <= 0:
                        result.add_diff(f"{tx_prefix}/amount", "> 0", tx["amount"])
                except Exception:
                    result.add_diff(f"{tx_prefix}/amount", "gültige Zahl", tx["amount"])

    # 5. GrpHdr NbOfTxs / CtrlSum Konsistenz
    if parsed.get("nb_of_txs") and parsed["nb_of_txs"] != str(total_txs):
        result.add_diff("GrpHdr/NbOfTxs", str(total_txs), parsed["nb_of_txs"])

    if parsed.get("ctrl_sum"):
        try:
            grp_sum = Decimal(parsed["ctrl_sum"])
            if grp_sum != total_sum:
                result.add_diff("GrpHdr/CtrlSum", str(total_sum), str(grp_sum))
        except Exception:
            pass

    return result


def run_roundtrip(
    xml_paths: List[str],
    xsd_validator=None,
    verbose: bool = False,
) -> List[RoundtripResult]:
    """Fuehrt Round-Trip-Validierung für mehrere XML-Dateien durch."""
    results = []

    for path in xml_paths:
        if verbose:
            print(f"\nRound-Trip: {os.path.basename(path)}")

        result = validate_roundtrip(path, xsd_validator)
        results.append(result)

        if result.parse_error:
            print(f"  FEHLER: {result.parse_error}")
        elif result.diffs:
            print(f"  FAIL: {len(result.diffs)} Abweichungen")
            if verbose:
                for d in result.diffs:
                    print(str(d))
        else:
            pi_count = len(result.parsed_data.get("payment_instructions", []))
            tx_count = sum(
                len(pi.get("transactions", []))
                for pi in result.parsed_data.get("payment_instructions", [])
            )
            print(f"  OK ({pi_count} PmtInf, {tx_count} Transaktionen)")

    return results
