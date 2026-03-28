"""Strategy-Pattern für standard-abhängige XML-Generierung.

Jeder Standard (SPS 2025, CBPR+ SR2026, zukünftig EPC SEPA) definiert
eigene Regeln für GrpHdr, PmtInf und Instruction-Vorbereitung.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from src.models.testcase import PaymentInstruction, Standard, Transaction


class StandardStrategy(ABC):
    """Definiert standard-abhängiges Verhalten für die XML-Generierung."""

    @abstractmethod
    def grp_hdr_nb_of_txs(self, all_txs: List[Transaction]) -> str:
        """NbOfTxs im GrpHdr."""
        ...

    @abstractmethod
    def grp_hdr_ctrl_sum(self, all_txs: List[Transaction]) -> Optional[str]:
        """CtrlSum im GrpHdr. None = Element weglassen."""
        ...

    @abstractmethod
    def pmt_inf_nb_of_txs(self, txs: List[Transaction]) -> Optional[str]:
        """NbOfTxs im PmtInf. None = Element weglassen."""
        ...

    @abstractmethod
    def pmt_inf_ctrl_sum(self, txs: List[Transaction]) -> Optional[str]:
        """CtrlSum im PmtInf. None = Element weglassen."""
        ...

    def prepare_cre_dt_tm(self, cre_dt_tm: str) -> str:
        """Bereitet CreDtTm vor (z.B. UTC-Offset für CBPR+)."""
        return cre_dt_tm

    def prepare_pmt_inf_id(self, pmt_inf_id: str, msg_id: str) -> str:
        """Bereitet PmtInfId vor (z.B. = MsgId für CBPR+)."""
        return pmt_inf_id


class Sps2025Strategy(StandardStrategy):
    """Swiss Payment Standards 2025.

    - NbOfTxs: Summe aller Transaktionen
    - CtrlSum: Summe aller Beträge (auf GrpHdr und PmtInf)
    - CreDtTm: lokale Zeit OK
    - PmtInfId: unabhängig von MsgId
    """

    def grp_hdr_nb_of_txs(self, all_txs: List[Transaction]) -> str:
        return str(len(all_txs))

    def grp_hdr_ctrl_sum(self, all_txs: List[Transaction]) -> Optional[str]:
        return str(sum(tx.amount for tx in all_txs))

    def pmt_inf_nb_of_txs(self, txs: List[Transaction]) -> Optional[str]:
        return str(len(txs))

    def pmt_inf_ctrl_sum(self, txs: List[Transaction]) -> Optional[str]:
        return str(sum(tx.amount for tx in txs))


class CbprPlus2026Strategy(StandardStrategy):
    """CBPR+ SR2026 (Cross-Border Payments and Reporting Plus).

    - NbOfTxs: immer "1" auf GrpHdr
    - CtrlSum: nicht auf GrpHdr oder PmtInf
    - CreDtTm: muss UTC-Offset enthalten
    - PmtInfId: muss MsgId entsprechen (Rule R8)
    """

    def grp_hdr_nb_of_txs(self, all_txs: List[Transaction]) -> str:
        return "1"

    def grp_hdr_ctrl_sum(self, all_txs: List[Transaction]) -> Optional[str]:
        return None

    def pmt_inf_nb_of_txs(self, txs: List[Transaction]) -> Optional[str]:
        return None

    def pmt_inf_ctrl_sum(self, txs: List[Transaction]) -> Optional[str]:
        return None

    def prepare_cre_dt_tm(self, cre_dt_tm: str) -> str:
        if "+" not in cre_dt_tm and "Z" not in cre_dt_tm:
            return datetime.now(timezone.utc).astimezone().isoformat()
        return cre_dt_tm

    def prepare_pmt_inf_id(self, pmt_inf_id: str, msg_id: str) -> str:
        return msg_id


class CgiMpStrategy(StandardStrategy):
    """CGI-MP (Common Global Implementation — Market Practice).

    Corporate-to-Bank global standard. XML-Struktur identisch mit SPS:
    - NbOfTxs: Summe aller Transaktionen
    - CtrlSum: Summe aller Betraege (GrpHdr + PmtInf)
    - CreDtTm: lokale Zeit OK (UTF-8, kein FIN-X)
    - PmtInfId: unabhaengig von MsgId
    - UETR: optional (empfohlen)
    - ChrgBr: DEBT/CRED/SHAR/SLEV alle erlaubt

    Unterschiede zu SPS liegen auf Business-Rule-Ebene:
    - Leere Tags verboten (BR-CGI-CHAR-01)
    - Structured/Unstructured Remittance exklusiv (BR-CGI-RMT-01)
    - Regulatory Reporting unterstuetzt (BR-CGI-PURP-01/02)
    - Adress-Regeln fuer UltmtDbtr/UltmtCdtr (BR-CGI-ADDR-02)
    """

    def grp_hdr_nb_of_txs(self, all_txs: List[Transaction]) -> str:
        return str(len(all_txs))

    def grp_hdr_ctrl_sum(self, all_txs: List[Transaction]) -> Optional[str]:
        return str(sum(tx.amount for tx in all_txs))

    def pmt_inf_nb_of_txs(self, txs: List[Transaction]) -> Optional[str]:
        return str(len(txs))

    def pmt_inf_ctrl_sum(self, txs: List[Transaction]) -> Optional[str]:
        return str(sum(tx.amount for tx in txs))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_STRATEGIES = {
    Standard.SPS_2025: Sps2025Strategy,
    Standard.CBPR_PLUS_2026: CbprPlus2026Strategy,
    Standard.CGI_MP: CgiMpStrategy,
}


def get_strategy(standard: Standard) -> StandardStrategy:
    """Gibt die passende Strategy für einen Standard zurück."""
    cls = _STRATEGIES.get(standard)
    if cls is None:
        raise ValueError(f"Kein Strategy für Standard '{standard.value}' definiert.")
    return cls()
