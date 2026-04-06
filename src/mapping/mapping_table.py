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
    "CdtrAcct.Othr.Id": {"xpath": "CdtrAcct/Id/Othr/Id", "level": "C"},
    "CdtrAcct.Othr.SchmeNm": {"xpath": "CdtrAcct/Id/Othr/SchmeNm/Prtry", "level": "C"},

    # C-Level: Creditor Identification (OrgId)
    "Cdtr.Id.OrgId.LEI": {"xpath": "Cdtr/Id/OrgId/LEI", "level": "C"},

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

    # C-Level: Ultimate Debtor (C-Level, pro Transaktion)
    "CdtTrfTxInf.UltmtDbtr.Nm": {"xpath": "UltmtDbtr/Nm", "level": "C"},
    "CdtTrfTxInf.UltmtDbtr.PstlAdr.StrtNm": {"xpath": "UltmtDbtr/PstlAdr/StrtNm", "level": "C"},
    "CdtTrfTxInf.UltmtDbtr.PstlAdr.TwnNm": {"xpath": "UltmtDbtr/PstlAdr/TwnNm", "level": "C"},
    "CdtTrfTxInf.UltmtDbtr.PstlAdr.Ctry": {"xpath": "UltmtDbtr/PstlAdr/Ctry", "level": "C"},

    # C-Level: Ultimate Creditor
    "UltmtCdtr.Nm": {"xpath": "UltmtCdtr/Nm", "level": "C"},
    "UltmtCdtr.PstlAdr.StrtNm": {"xpath": "UltmtCdtr/PstlAdr/StrtNm", "level": "C"},
    "UltmtCdtr.PstlAdr.TwnNm": {"xpath": "UltmtCdtr/PstlAdr/TwnNm", "level": "C"},
    "UltmtCdtr.PstlAdr.Ctry": {"xpath": "UltmtCdtr/PstlAdr/Ctry", "level": "C"},

    # C-Level: Purpose
    "Purp.Cd": {"xpath": "Purp/Cd", "level": "C"},

    # C-Level: Regulatory Reporting
    "RgltryRptg.DbtCdtRptgInd": {"xpath": "RgltryRptg/DbtCdtRptgInd", "level": "C"},
    "RgltryRptg.Authrty.Nm": {"xpath": "RgltryRptg/Authrty/Nm", "level": "C"},
    "RgltryRptg.Authrty.Ctry": {"xpath": "RgltryRptg/Authrty/Ctry", "level": "C"},
    "RgltryRptg.Dtls.Tp": {"xpath": "RgltryRptg/Dtls/Tp", "level": "C"},
    "RgltryRptg.Dtls.Cd": {"xpath": "RgltryRptg/Dtls/Cd", "level": "C"},
    "RgltryRptg.Dtls.Inf": {"xpath": "RgltryRptg/Dtls/Inf", "level": "C"},

    # C-Level: Tax Remittance (RmtInf/Strd/TaxRmt)
    "TaxRmt.Cdtr.TaxId": {"xpath": "RmtInf/Strd/TaxRmt/Cdtr/TaxId", "level": "C"},
    "TaxRmt.Cdtr.RegnId": {"xpath": "RmtInf/Strd/TaxRmt/Cdtr/RegnId", "level": "C"},
    "TaxRmt.Cdtr.TaxTp": {"xpath": "RmtInf/Strd/TaxRmt/Cdtr/TaxTp", "level": "C"},
    "TaxRmt.Dbtr.TaxId": {"xpath": "RmtInf/Strd/TaxRmt/Dbtr/TaxId", "level": "C"},
    "TaxRmt.Dbtr.RegnId": {"xpath": "RmtInf/Strd/TaxRmt/Dbtr/RegnId", "level": "C"},
    "TaxRmt.Dbtr.TaxTp": {"xpath": "RmtInf/Strd/TaxRmt/Dbtr/TaxTp", "level": "C"},
    "TaxRmt.AdmstnZone": {"xpath": "RmtInf/Strd/TaxRmt/AdmstnZone", "level": "C"},
    "TaxRmt.RefNb": {"xpath": "RmtInf/Strd/TaxRmt/RefNb", "level": "C"},
    "TaxRmt.Mtd": {"xpath": "RmtInf/Strd/TaxRmt/Mtd", "level": "C"},
    "TaxRmt.TtlTaxAmt": {"xpath": "RmtInf/Strd/TaxRmt/TtlTaxAmt", "level": "C"},
    "TaxRmt.TtlTaxAmt.Ccy": {"xpath": "RmtInf/Strd/TaxRmt/TtlTaxAmt@Ccy", "level": "C"},
    "TaxRmt.Dt": {"xpath": "RmtInf/Strd/TaxRmt/Dt", "level": "C"},

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
    "Dbtr.Id.OrgId.LEI": {"xpath": "Dbtr/Id/OrgId/LEI", "level": "B"},
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
SPECIAL_KEYS = {"ViolateRule", "GroupId"}


def _build_tag_to_keys_lookup() -> dict[str, list[str]]:
    """Baut einen Reverse-Lookup: XML-Blatt-Tag → Liste von FIELD_MAPPINGS-Keys.

    Extrahiert den letzten Tag-Namen aus dem XPath jedes Mappings.
    Beispiel: xpath="Cdtr/PstlAdr/StrtNm" → Blatt-Tag "StrtNm"

    Tags die auf genau einen Key abbilden sind eindeutig auflösbar.
    Tags die auf mehrere Keys abbilden sind mehrdeutig.
    """
    lookup: dict[str, list[str]] = {}
    for key, mapping in FIELD_MAPPINGS.items():
        xpath = mapping["xpath"]
        # Attribut-Syntax (z.B. "Amt/InstdAmt@Ccy") → ignorieren
        if "@" in xpath:
            continue
        leaf_tag = xpath.rsplit("/", 1)[-1]
        lookup.setdefault(leaf_tag, []).append(key)
    return lookup


# Reverse-Lookup: XML-Tag-Name → Liste von zugehörigen FIELD_MAPPINGS-Keys
TAG_TO_KEYS = _build_tag_to_keys_lookup()


def get_valid_keys() -> list[str]:
    """Gibt alle gültigen Mapping-Keys zurück."""
    return sorted(list(FIELD_MAPPINGS.keys()) + sorted(SPECIAL_KEYS))
