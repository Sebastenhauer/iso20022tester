"""Generates two demonstration XMLs that illustrate the diffs between
the SPS 2025 and CGI-MP November 2025 implementation guides.

Outputs (in ``examples/violations/``):

1. ``cgi_mp_argentina_baseline.xml``
   A clean, baseline CGI-MP pain.001 with EUR payment to an Argentine
   creditor. Contains full Regulatory Reporting (DEBT/SNB/BOP) and Tax
   Remittance Information. Passes both the SPS XSD and the CGI-MP
   best-practice rules.

2. ``cgi_mp_violates_sps_xsd.xml``
   The same baseline, but the Cdtr/Nm has been mutated to include the
   Unicode character "★" (U+2605, BLACK STAR). This is valid UTF-8 and
   permitted under CGI-MP (which allows the full UTF-8 charset), but it
   violates the SPS pain.001.001.09.ch.03 XSD pattern facet, which
   restricts text fields to Basic-Latin + Latin-1 Supplement +
   Latin-Extended-A (plus 5 special chars).

3. ``sps_violates_cgi_unstructured_address.xml``
   A clean SPS pain.001 with an UltmtDbtr inserted whose PstlAdr uses
   only ``AdrLine`` (unstructured) entries plus the mandatory Country.
   SPS allows unstructured addresses for any party (IG Kapitel 3.11,
   gueltig bis November 2026); CGI-MP explicitly forbids unstructured
   addresses for UltmtDbtr / UltmtCdtr / InitgPty (BR-CGI-ADDR-02 /
   CGI-MP Handbook Slide 8: "Not allowed for Ultimate Debtor, Ultimate
   Creditor, Initiating Party"). The XML therefore passes both SPS
   XSD and SPS IG, but violates CGI-MP best practice.

   An earlier iteration of this demo file used empty ``<PmtTpInf/>``
   and ``<RmtInf/>`` tags, which initially seemed valid against the
   SPS XSD. External SPS validation showed that SPS Kapitel 3.4
   explicitly forbids empty elements, so there is no SPS-allows-but-
   CGI-doesn't delta on the empty-tag axis. The unstructured-address
   path produces a clean delta instead.

The script uses the post-generation lxml-mutation approach because
the in-pipeline ``Cdtr.PstlAdr.*`` override propagation has a V1
limitation: handler-generated addresses are not overwritten by C-level
overrides. The mutations here patch that gap for the demo.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from lxml import etree

PAIN001_NS = "urn:iso:std:iso:20022:tech:xsd:pain.001.001.09"
NS = {"p": PAIN001_NS}
SPS_XSD_PATH = "schemas/pain.001/pain.001.001.09.ch.03.xsd"

OUT_DIR = Path("examples/violations")
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def latest_run_dir() -> Path:
    """Returns the most recent output/<timestamp> directory."""
    output = Path("output")
    if not output.is_dir():
        sys.exit("No output/ directory present. Run the pipeline first.")
    runs = sorted(p for p in output.iterdir() if p.is_dir())
    if not runs:
        sys.exit("No output runs available.")
    return runs[-1]


def find_xml(run_dir: Path, tc_id_substring: str) -> Path:
    """Find the most recent XML file matching a TC-ID substring."""
    matches = sorted(run_dir.glob(f"*{tc_id_substring}*.xml"))
    if not matches:
        sys.exit(f"No XML found in {run_dir} for {tc_id_substring}")
    return matches[-1]


def parse_xml(path: Path) -> etree._ElementTree:
    return etree.parse(str(path))


def serialize(tree_or_root, path: Path) -> None:
    if hasattr(tree_or_root, "write"):
        tree_or_root.write(
            str(path),
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )
    else:
        path.write_bytes(etree.tostring(
            tree_or_root,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        ))


def validate_against_sps_xsd(path: Path) -> tuple[bool, list[str]]:
    schema = etree.XMLSchema(etree.parse(SPS_XSD_PATH))
    doc = etree.parse(str(path))
    if schema.validate(doc):
        return True, []
    errors = [f"line {e.line}: {e.message}" for e in schema.error_log]
    return False, errors


# ---------------------------------------------------------------------------
# Patch functions
# ---------------------------------------------------------------------------

def patch_argentina_baseline(tree: etree._ElementTree) -> None:
    """Replace the random faker creditor address with a real Buenos Aires
    address, so the demo file makes geographical sense."""
    cdtr_addr = tree.find(".//p:CdtTrfTxInf/p:Cdtr/p:PstlAdr", NS)
    if cdtr_addr is None:
        return
    new_fields = {
        "StrtNm": "Avenida Corrientes",
        "BldgNb": "1234",
        "PstCd": "C1043AAZ",
        "TwnNm": "Buenos Aires",
        "Ctry": "AR",
    }
    for tag, value in new_fields.items():
        el = cdtr_addr.find(f"p:{tag}", NS)
        if el is not None:
            el.text = value


def patch_inject_star_in_cdtr_name(tree: etree._ElementTree) -> None:
    """Insert the ★ char (U+2605) into the Creditor Name. This char is
    valid UTF-8 (CGI-MP allows it) but violates the SPS XSD Latin pattern
    facet which only permits Basic-Latin + Latin-1 + Latin-Extended-A."""
    cdtr_nm = tree.find(".//p:CdtTrfTxInf/p:Cdtr/p:Nm", NS)
    if cdtr_nm is None:
        return
    original = cdtr_nm.text or ""
    cdtr_nm.text = "Compania Argentina \u2605 Comercio S.A."  # ★
    return original, cdtr_nm.text


def patch_inject_unstructured_ultmtdbtr(tree: etree._ElementTree) -> None:
    """Inject an UltmtDbtr with an unstructured AdrLine address into
    the first CdtTrfTxInf.

    Why this demonstrates a SPS-vs-CGI delta:

    - **SPS 2025** has no rule against unstructured addresses for
      UltmtDbtr. The PstlAdr/AdrLine sub-element is XSD-valid in
      pain.001.001.09 and the SPS IG explicitly permits unstructured
      addresses (Variante "unstrukturiert" / "hybrid", IG Kapitel
      3.11) until November 2026 for parties in general.
    - **CGI-MP** explicitly forbids unstructured addresses for
      UltmtDbtr, UltmtCdtr, and InitgPty (BR-CGI-ADDR-02 in our
      catalog; CGI-MP Handbook Slide 8: "Not allowed for Ultimate
      Debtor, Ultimate Creditor, Initiating Party"). Only structured
      or hybrid forms are accepted, never AdrLine-only.

    The injected UltmtDbtr therefore:
    - passes the SPS XSD pattern facets (only Latin-1 chars used)
    - passes the SPS IG (no rule violation)
    - violates CGI-MP best practice (BR-CGI-ADDR-02)

    XSD position: UltmtDbtr in CdtTrfTxInf must come AFTER ChqInstr
    and BEFORE IntrmyAgt1/CdtrAgt/Cdtr (per pain.001.001.09 schema).

    Earlier iterations of this script tried injecting empty <RmtInf/>
    or <PmtTpInf/> tags, but those are forbidden by both standards:
    SPS IG Kapitel 3.4 explicitly prohibits empty elements, so there
    is no SPS-allows-but-CGI-doesn't delta on the empty-tag axis.
    The unstructured-UltmtDbtr-address path produces a clean delta
    instead.
    """
    cdt_tx = tree.find(".//p:CdtTrfTxInf", NS)
    if cdt_tx is None:
        return

    # Build the UltmtDbtr element with name + AdrLine-only address
    ultmt_dbtr = etree.Element(f"{{{PAIN001_NS}}}UltmtDbtr")
    nm = etree.SubElement(ultmt_dbtr, f"{{{PAIN001_NS}}}Nm")
    nm.text = "Mutterkonzern Holding AG"
    pstl_adr = etree.SubElement(ultmt_dbtr, f"{{{PAIN001_NS}}}PstlAdr")
    # Country first (required by both standards), then unstructured AdrLines
    ctry = etree.SubElement(pstl_adr, f"{{{PAIN001_NS}}}Ctry")
    ctry.text = "CH"
    adr1 = etree.SubElement(pstl_adr, f"{{{PAIN001_NS}}}AdrLine")
    adr1.text = "Bahnhofstrasse 100"
    adr2 = etree.SubElement(pstl_adr, f"{{{PAIN001_NS}}}AdrLine")
    adr2.text = "8001 Zurich, Switzerland"

    # Insert at the correct XSD position: after ChqInstr (or whatever is
    # the latest existing element from the pre-UltmtDbtr block), before
    # IntrmyAgt1/CdtrAgt/Cdtr/etc. We look for the first occurrence of
    # any "later" element and insert before it.
    pre_ultmt_tags = {
        "PmtId", "PmtTpInf", "Amt", "XchgRateInf", "ChrgBr", "ChqInstr",
    }
    insert_idx = None
    for idx, child in enumerate(list(cdt_tx)):
        local = child.tag.split("}")[-1]
        if local not in pre_ultmt_tags:
            insert_idx = idx
            break
    if insert_idx is None:
        cdt_tx.append(ultmt_dbtr)
    else:
        cdt_tx.insert(insert_idx, ultmt_dbtr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    run_dir = latest_run_dir()
    print(f"Using run directory: {run_dir}")

    # === Demo 1+2: CGI-MP Argentina baseline + SPS-violating star variant ===
    cgi_ar_src = find_xml(run_dir, "TC-DEMO-CGI-AR")
    print(f"Source CGI-AR XML: {cgi_ar_src}")

    # Baseline (with corrected address)
    tree_baseline = parse_xml(cgi_ar_src)
    patch_argentina_baseline(tree_baseline)
    baseline_path = OUT_DIR / "cgi_mp_argentina_baseline.xml"
    serialize(tree_baseline, baseline_path)

    valid, errors = validate_against_sps_xsd(baseline_path)
    print(f"\n[1] BASELINE  {baseline_path}")
    print(f"     SPS-XSD: {'PASS' if valid else 'FAIL'}")
    for e in errors[:3]:
        print(f"        {e}")

    # Star variant: parse the just-saved baseline and inject ★ into Cdtr/Nm
    tree_star = parse_xml(baseline_path)
    patch_inject_star_in_cdtr_name(tree_star)
    star_path = OUT_DIR / "cgi_mp_violates_sps_xsd.xml"
    serialize(tree_star, star_path)

    valid, errors = validate_against_sps_xsd(star_path)
    print(f"\n[2] CGI-konform, SPS-XSD violating  {star_path}")
    print(f"     SPS-XSD: {'PASS' if valid else 'FAIL (expected)'}")
    for e in errors[:3]:
        print(f"        {e}")

    # === Demo 3: SPS XML with unstructured UltmtDbtr address ===
    sps_src = find_xml(run_dir, "TC-S-001")
    print(f"\nSource SPS XML: {sps_src}")

    tree_unstr = parse_xml(sps_src)
    patch_inject_unstructured_ultmtdbtr(tree_unstr)
    unstr_path = OUT_DIR / "sps_violates_cgi_unstructured_address.xml"
    serialize(tree_unstr, unstr_path)

    valid, errors = validate_against_sps_xsd(unstr_path)
    print(f"\n[3] SPS-konform, CGI-MP BR-CGI-ADDR-02 violation  {unstr_path}")
    print(f"     SPS-XSD: {'PASS (expected)' if valid else 'FAIL'}")
    for e in errors[:3]:
        print(f"        {e}")

    print("\nDone. See examples/violations/ for the three demo files.")


if __name__ == "__main__":
    main()
