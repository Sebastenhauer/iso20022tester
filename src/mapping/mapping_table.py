"""Statische Mapping-Tabelle: Excel-Key → XPath im pain.001-Schema."""

# Ebene: "B" = PmtInf, "C" = CdtTrfTxInf
FIELD_MAPPINGS = {
    # C-Level: Creditor
    "Cdtr.Nm": {"xpath": "Cdtr/Nm", "level": "C"},
    "Cdtr.PstlAdr.StrtNm": {"xpath": "Cdtr/PstlAdr/StrtNm", "level": "C"},
    "Cdtr.PstlAdr.BldgNb": {"xpath": "Cdtr/PstlAdr/BldgNb", "level": "C"},
    "Cdtr.PstlAdr.PstCd": {"xpath": "Cdtr/PstlAdr/PstCd", "level": "C"},
    "Cdtr.PstlAdr.TwnNm": {"xpath": "Cdtr/PstlAdr/TwnNm", "level": "C"},
    "Cdtr.PstlAdr.Ctry": {"xpath": "Cdtr/PstlAdr/Ctry", "level": "C"},
    "Cdtr.PstlAdr.AdrLine": {"xpath": "Cdtr/PstlAdr/AdrLine", "level": "C"},

    # C-Level: Creditor Account
    "CdtrAcct.IBAN": {"xpath": "CdtrAcct/Id/IBAN", "level": "C"},

    # C-Level: Creditor Agent
    "CdtrAgt.BICFI": {"xpath": "CdtrAgt/FinInstnId/BICFI", "level": "C"},
    "CdtrAgt.ClrSysMmbId": {"xpath": "CdtrAgt/FinInstnId/ClrSysMmbId/MmbId", "level": "C"},

    # C-Level: Amount
    "Amt.InstdAmt": {"xpath": "Amt/InstdAmt", "level": "C"},
    "Amt.InstdAmt.Ccy": {"xpath": "Amt/InstdAmt@Ccy", "level": "C"},

    # C-Level: Remittance Information
    "RmtInf.Ustrd": {"xpath": "RmtInf/Ustrd", "level": "C"},
    "RmtInf.Strd.CdtrRefInf.Ref": {"xpath": "RmtInf/Strd/CdtrRefInf/Ref", "level": "C"},
    "RmtInf.Strd.CdtrRefInf.Tp.CdOrPrtry.Cd": {
        "xpath": "RmtInf/Strd/CdtrRefInf/Tp/CdOrPrtry/Cd", "level": "C",
    },

    # C-Level: Ultimate Creditor
    "UltmtCdtr.Nm": {"xpath": "UltmtCdtr/Nm", "level": "C"},
    "UltmtCdtr.PstlAdr.StrtNm": {"xpath": "UltmtCdtr/PstlAdr/StrtNm", "level": "C"},
    "UltmtCdtr.PstlAdr.TwnNm": {"xpath": "UltmtCdtr/PstlAdr/TwnNm", "level": "C"},
    "UltmtCdtr.PstlAdr.Ctry": {"xpath": "UltmtCdtr/PstlAdr/Ctry", "level": "C"},

    # C-Level: Payment ID
    "PmtId.InstrId": {"xpath": "PmtId/InstrId", "level": "C"},
    "PmtId.EndToEndId": {"xpath": "PmtId/EndToEndId", "level": "C"},

    # B-Level: Payment Type Information
    "SvcLvl.Cd": {"xpath": "PmtTpInf/SvcLvl/Cd", "level": "B"},
    "LclInstrm.Cd": {"xpath": "PmtTpInf/LclInstrm/Cd", "level": "B"},
    "CtgyPurp.Cd": {"xpath": "PmtTpInf/CtgyPurp/Cd", "level": "B"},

    # B-Level: Charge Bearer
    "ChrgBr": {"xpath": "ChrgBr", "level": "B"},

    # B-Level: Requested Execution Date
    "ReqdExctnDt": {"xpath": "ReqdExctnDt/Dt", "level": "B"},

    # B-Level: Debtor (Override)
    "Dbtr.Nm": {"xpath": "Dbtr/Nm", "level": "B"},
    "DbtrAcct.IBAN": {"xpath": "DbtrAcct/Id/IBAN", "level": "B"},
    "DbtrAgt.BICFI": {"xpath": "DbtrAgt/FinInstnId/BICFI", "level": "B"},

    # B-Level: Ultimate Debtor
    "UltmtDbtr.Nm": {"xpath": "UltmtDbtr/Nm", "level": "B"},
    "UltmtDbtr.PstlAdr.StrtNm": {"xpath": "UltmtDbtr/PstlAdr/StrtNm", "level": "B"},
    "UltmtDbtr.PstlAdr.TwnNm": {"xpath": "UltmtDbtr/PstlAdr/TwnNm", "level": "B"},
    "UltmtDbtr.PstlAdr.Ctry": {"xpath": "UltmtDbtr/PstlAdr/Ctry", "level": "B"},

    # B-Level: Batch Booking
    "BtchBookg": {"xpath": "BtchBookg", "level": "B"},
}

# Spezial-Keys, die nicht gemappt, sondern separat verarbeitet werden
SPECIAL_KEYS = {"ViolateRule", "TxCount", "GroupId"}


def get_valid_keys() -> list[str]:
    """Gibt alle gültigen Mapping-Keys zurück."""
    return sorted(list(FIELD_MAPPINGS.keys()) + sorted(SPECIAL_KEYS))
