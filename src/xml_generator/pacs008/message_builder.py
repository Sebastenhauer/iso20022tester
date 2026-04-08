"""High-Level pacs.008 Message Assembly.

Baut aus einer Pacs008BusinessMessage eine komplette
<BusinessMessage><AppHdr/><Document/></BusinessMessage>-XML-Struktur.

Die eigentliche Envelope-Form fuer CBPR+ ist ein Wrapper-Element,
das sowohl den BAH (head.001.001.02) als auch das Document
(pacs.008.001.08) als Geschwister enthaelt. Der externe XML-Validator-Service unter `/cbpr/validate`
akzeptiert diese Form direkt als plain-text XML-String.
"""

from datetime import datetime, timezone
from typing import Optional

from lxml import etree

from src.models.pacs008 import (
    Pacs008BusinessMessage,
    Pacs008Instruction,
)
from src.xml_generator.pacs008.builders import (
    build_cdt_trf_tx_inf,
    build_group_header,
)
from src.xml_generator.pacs008.namespaces import (
    DEFAULT_BIZ_SVC,
    DEFAULT_MSG_DEF_IDR,
    HEAD_NS,
    PACS008_NS,
)


# ---------------------------------------------------------------------------
# BAH (AppHdr, head.001.001.02)
# ---------------------------------------------------------------------------

def _hel(parent, tag: str, text: Optional[str] = None) -> etree._Element:
    elem = etree.SubElement(parent, f"{{{HEAD_NS}}}{tag}")
    if text is not None:
        elem.text = str(text)
    return elem


def build_bah(
    from_bic: str,
    to_bic: str,
    biz_msg_idr: str,
    cre_dt: Optional[str] = None,
    msg_def_idr: str = DEFAULT_MSG_DEF_IDR,
    biz_svc: str = DEFAULT_BIZ_SVC,
) -> etree._Element:
    """Baut ein BusinessApplicationHeaderV02 (AppHdr) fuer pacs.008.

    Reihenfolge nach head.001.001.02 XSD:
    CharSet?, Fr, To, BizMsgIdr, MsgDefIdr, BizSvc?, MktPrctc?, CreDt, ...

    V1 setzt Fr, To, BizMsgIdr, MsgDefIdr, BizSvc, CreDt.
    """
    if cre_dt is None:
        cre_dt = datetime.now(timezone.utc).astimezone().isoformat()

    nsmap = {None: HEAD_NS}
    app_hdr = etree.Element(f"{{{HEAD_NS}}}AppHdr", nsmap=nsmap)

    fr = _hel(app_hdr, "Fr")
    fi_id = _hel(fr, "FIId")
    fin_instn_id = _hel(fi_id, "FinInstnId")
    _hel(fin_instn_id, "BICFI", from_bic)

    to = _hel(app_hdr, "To")
    fi_id2 = _hel(to, "FIId")
    fin_instn_id2 = _hel(fi_id2, "FinInstnId")
    _hel(fin_instn_id2, "BICFI", to_bic)

    _hel(app_hdr, "BizMsgIdr", biz_msg_idr)
    _hel(app_hdr, "MsgDefIdr", msg_def_idr)
    _hel(app_hdr, "BizSvc", biz_svc)
    _hel(app_hdr, "CreDt", cre_dt)

    return app_hdr


# ---------------------------------------------------------------------------
# Document (pacs.008.001.08)
# ---------------------------------------------------------------------------

def build_document(instruction: Pacs008Instruction) -> etree._Element:
    """Baut das pacs.008 <Document>-Element mit <FIToFICstmrCdtTrf>.

    Wichtig: die CBPR+ `FIToFICstmrCdtTrf` hat genau eine CdtTrfTxInf.
    Falls die Instruction mehrere Transactions enthaelt, wird nur die
    erste gebaut (V1-Limit). Multi-Tx-Support ist Zukunftsthema.

    Die Funktion injiziert zwei instruction-level Felder in die
    Transaction-Objekte, damit der C-Level-Builder sie sieht:
    - ``_settlement_date_iso`` (IntrBkSttlmDt auf C-Level)
    - ``_instructing_agent`` / ``_instructed_agent`` (InstgAgt/InstdAgt auf C-Level)
    """
    nsmap = {None: PACS008_NS}
    document = etree.Element(f"{{{PACS008_NS}}}Document", nsmap=nsmap)
    fi_to_fi = etree.SubElement(
        document, f"{{{PACS008_NS}}}FIToFICstmrCdtTrf"
    )

    build_group_header(fi_to_fi, instruction)

    for tx in instruction.transactions:
        # Inject instruction-level context into transaction via transient
        # attributes (ohne das Modell zu muten, nutzen wir object.__setattr__).
        object.__setattr__(tx, "_settlement_date_iso", instruction.interbank_settlement_date)
        object.__setattr__(tx, "_instructing_agent", instruction.instructing_agent)
        object.__setattr__(tx, "_instructed_agent", instruction.instructed_agent)
        build_cdt_trf_tx_inf(fi_to_fi, tx)

    return document


# ---------------------------------------------------------------------------
# Business Message Envelope (BAH + Document)
# ---------------------------------------------------------------------------

def build_business_message(bm: Pacs008BusinessMessage) -> etree._Element:
    """Baut einen vollstaendigen BusinessMessage-Wrapper mit AppHdr + Document.

    Ergebnis:
    ```xml
    <BusinessMessage>
        <AppHdr xmlns="urn:iso:std:iso:20022:tech:xsd:head.001.001.02">
            ...
        </AppHdr>
        <Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
            ...
        </Document>
    </BusinessMessage>
    ```

    Der BusinessMessage-Wrapper ist selbst NICHT in einem Namespace; AppHdr
    und Document haben jeweils ihre eigenen Default-Namespaces. Diese Form
    ist das, was der externe XML-Validator-Service unter `/cbpr/validate` als Plain-Text-Body erwartet.
    """
    document = build_document(bm.instruction)
    bah = build_bah(
        from_bic=bm.bah_from_bic,
        to_bic=bm.bah_to_bic,
        biz_msg_idr=bm.bah_biz_msg_idr,
        cre_dt=bm.bah_cre_dt,
        msg_def_idr=bm.bah_msg_def_idr,
        biz_svc=bm.bah_biz_svc,
    )

    wrapper = etree.Element("BusinessMessage")
    wrapper.append(bah)
    wrapper.append(document)
    return wrapper


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def serialize(root: etree._Element, pretty: bool = True) -> bytes:
    """Serialisiert ein Element zu UTF-8 XML mit XML-Declaration."""
    return etree.tostring(
        root,
        pretty_print=pretty,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def serialize_document_only(instruction: Pacs008Instruction, pretty: bool = True) -> bytes:
    """Serialisiert nur das <Document>-Element (ohne BAH).

    Nuetzlich fuer XSD-Only-Validierung (pacs.008 XSD erwartet Document
    als Root, nicht BusinessMessage).
    """
    doc = build_document(instruction)
    return etree.tostring(
        doc,
        pretty_print=pretty,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )
