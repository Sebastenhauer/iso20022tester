"""Business Application Header (BAH) Builder for CBPR+ pain.001.

Generates a head.001.001.02 AppHdr element that wraps a pain.001 Document.
Required by SWIFT MyStandards validator for CBPR+ messages.

The output is a combined XML with both AppHdr and Document as siblings
under a common wrapper element (``BusinessMessage``). Der Wrapper selbst
traegt keinen Namespace; AppHdr und Document deklarieren jeweils ihr
eigenes Default-Namespace. Das ist die Form, die SWIFTs CBPR+ Validator
(und MyStandards) erwartet.

Based on: IPPlus_head.001.001.02 Usage Guideline (pages 6-10)
"""

from datetime import datetime, timezone
from typing import Optional

from lxml import etree

HEAD_NS = "urn:iso:std:iso:20022:tech:xsd:head.001.001.02"
PAIN_NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"


def build_bah(
    from_bic: str,
    to_bic: str,
    msg_id: str,
    cre_dt: Optional[str] = None,
) -> etree._Element:
    """Baut ein BusinessApplicationHeaderV02 (AppHdr) Element.

    Args:
        from_bic: BIC des Senders (Debtor Agent oder Initiating Party)
        to_bic: BIC des Empfaengers (Debtor Agent bei Relay)
        msg_id: Business Message Identifier (= GrpHdr/MsgId, CBPR+ Rule R1)
        cre_dt: Creation DateTime mit UTC-Offset. Default: jetzt.

    Returns:
        lxml Element <AppHdr> im head.001.001.02 Namespace.
    """
    if cre_dt is None:
        cre_dt = datetime.now(timezone.utc).astimezone().isoformat()

    nsmap = {None: HEAD_NS}
    app_hdr = etree.Element(f"{{{HEAD_NS}}}AppHdr", nsmap=nsmap)

    # Fr (From) [1..1] — Sender BIC
    fr = _el(app_hdr, "Fr")
    fi_id = _el(fr, "FIId")
    fin_instn_id = _el(fi_id, "FinInstnId")
    _el(fin_instn_id, "BICFI", from_bic)

    # To [1..1] — Receiver BIC
    to = _el(app_hdr, "To")
    fi_id2 = _el(to, "FIId")
    fin_instn_id2 = _el(fi_id2, "FinInstnId")
    _el(fin_instn_id2, "BICFI", to_bic)

    # BizMsgIdr [1..1] — Must match GrpHdr/MsgId (Rule R1)
    _el(app_hdr, "BizMsgIdr", msg_id)

    # MsgDefIdr [1..1] — Message Definition Identifier
    _el(app_hdr, "MsgDefIdr", "pain.001.001.09")

    # CreDt [1..1] — Creation DateTime with UTC offset
    _el(app_hdr, "CreDt", cre_dt)

    return app_hdr


def wrap_with_bah(
    pain001_doc: etree._Element,
    from_bic: str,
    to_bic: str,
    msg_id: str,
    cre_dt: Optional[str] = None,
) -> etree._Element:
    """Wraps a pain.001 Document with a BAH in a BusinessMessage envelope.

    Ergebnis:
    ```xml
    <BusinessMessage>
        <AppHdr xmlns="urn:iso:std:iso:20022:tech:xsd:head.001.001.02">
            ...
        </AppHdr>
        <Document xmlns="urn:iso:std:iso:20022:tech:xsd:pain.001.001.09">
            ...
        </Document>
    </BusinessMessage>
    ```

    Der Wrapper selbst ist *nicht* in einem Namespace; AppHdr und Document
    deklarieren jeweils ihr eigenes Default-Namespace. Diese Form ist es,
    die SWIFTs CBPR+ Validator (und MyStandards) erwartet.

    Args:
        pain001_doc: The pain.001 Document element.
        from_bic: Sender BIC.
        to_bic: Receiver BIC (Debtor Agent).
        msg_id: Must match GrpHdr/MsgId.
        cre_dt: Creation DateTime with UTC offset.

    Returns:
        lxml Element containing AppHdr + Document.
    """
    # Build the BAH (carries its own default namespace via nsmap={None: HEAD_NS})
    bah = build_bah(from_bic, to_bic, msg_id, cre_dt)

    # Namespace-loser Wrapper: so behalten AppHdr und Document ihre eigenen
    # xmlns=-Deklarationen beim Serialisieren.
    wrapper = etree.Element("BusinessMessage")
    wrapper.append(bah)
    wrapper.append(pain001_doc)

    return wrapper


def _el(parent, tag, text=None):
    """Helper: creates sub-element in head.001 namespace."""
    elem = etree.SubElement(parent, f"{{{HEAD_NS}}}{tag}")
    if text is not None:
        elem.text = str(text)
    return elem
