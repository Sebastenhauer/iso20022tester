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

3. ``sps_violates_cgi_proprietary_orgid.xml``
   A clean SPS pain.001 where the Debtor's identification uses
   ``OrgId/Othr/SchmeNm/Prtry`` (free-form proprietary scheme name)
   instead of the conditional ``OrgId/Othr/SchmeNm/Cd`` (ISO external
   code list). SPS XSD permits both forms via an XSD ``<choice>``,
   and the SPS IG has no rule restricting the choice. CGI-MP
   ``BR-CGI-ORG-01`` explicitly forbids the ``Prtry`` form: "Cd is
   to be used when SchmeNm is given, which at the same time means
   SchmeNm/Prtry is not possible to be given". The XML therefore
   passes SPS but violates CGI-MP best practice.

   Real-world example: the Swiss UID number ``CHE-xxx.xxx.xxx`` is
   commonly identified with a proprietary scheme tag because no
   official ``ExternalOrganisationIdentification1Code`` value
   covers it.

   Earlier iterations of this demo file used:
   - Empty ``<PmtTpInf/>`` + ``<RmtInf/>`` tags -- forbidden by SPS
     IG Kapitel 3.4 ("Verwendung leerer Elemente nicht zulaessig"),
     so no SPS-vs-CGI delta on the empty-tag axis exists.
   - An unstructured ``UltmtDbtr/PstlAdr`` (only ``AdrLine`` +
     ``Ctry``) -- rejected by SPS CH21 ("TwnNm muss verwendet
     werden"). SPS only permits structured or hybrid addresses,
     both with ``TwnNm`` + ``Ctry`` as mandatory.
   The proprietary-OrgId path produces a clean delta that survives
   external SPS validation.

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


def patch_inject_proprietary_orgid(tree: etree._ElementTree) -> None:
    """Inject a Debtor identification using the proprietary scheme form
    ``OrgId/Othr/SchmeNm/Prtry`` (instead of the conditional ``Cd``).

    Why this demonstrates a SPS-vs-CGI delta:

    - **SPS 2025**: the SPS XSD inherits the standard ISO 20022
      ``PartyIdentification135`` complex type, which uses an XSD
      ``<choice>`` between ``Cd`` and ``Prtry`` inside ``SchmeNm``.
      Both alternatives are schema-valid. The SPS IG does not
      restrict the choice (no SPS-specific rule against ``Prtry``).
      Real-world example: the Swiss UID number (``CHE-xxx.xxx.xxx``)
      is commonly identified with a proprietary scheme tag because
      no official ISO ``ExternalOrganisationIdentification1Code``
      value covers it.

    - **CGI-MP**: the rule ``BR-CGI-ORG-01`` (CGI-MP Handbook
      ``SchmeNm in OrgId``) explicitly states that ``Cd`` must be
      used when ``SchmeNm`` is given, and that ``Prtry`` is not
      allowed. The intent is to anchor identifications in the ISO
      external code list rather than in free-form proprietary names.

    The injected XML therefore:
    - passes the SPS XSD pattern facets (Latin-1 chars only)
    - passes the SPS IG (no SPS-specific rule against Prtry)
    - violates CGI-MP best practice (BR-CGI-ORG-01)

    The previous iteration of this demo used an unstructured
    ``UltmtDbtr/PstlAdr/AdrLine``, but the SPS validator (GEFEG.FX)
    rejected it via SPS rule **CH21** ("Das Element <TwnNm> muss
    verwendet werden") -- SPS only permits structured or hybrid
    addresses, where ``TwnNm`` + ``Ctry`` are mandatory in both
    forms. There is no purely unstructured (AdrLine-only) variant
    in SPS, contrary to my earlier reading of IG Kapitel 3.11.
    """
    dbtr = tree.find(".//p:PmtInf/p:Dbtr", NS)
    if dbtr is None:
        return

    # If Dbtr already has an Id element, skip (we don't want to merge
    # with an existing identification)
    if dbtr.find("p:Id", NS) is not None:
        return

    # Build the Id/OrgId/Othr/Id + SchmeNm/Prtry chain. This is the
    # standard real-world pattern for the Swiss UID number when
    # identified via a proprietary scheme name.
    id_el = etree.SubElement(dbtr, f"{{{PAIN001_NS}}}Id")
    org_id = etree.SubElement(id_el, f"{{{PAIN001_NS}}}OrgId")
    othr = etree.SubElement(org_id, f"{{{PAIN001_NS}}}Othr")
    id_value = etree.SubElement(othr, f"{{{PAIN001_NS}}}Id")
    id_value.text = "CHE-112.334.566"
    schme_nm = etree.SubElement(othr, f"{{{PAIN001_NS}}}SchmeNm")
    prtry = etree.SubElement(schme_nm, f"{{{PAIN001_NS}}}Prtry")
    prtry.text = "CH-UID-NUMMER"


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

    # === Demo 3: SPS XML with proprietary OrgId scheme name ===
    sps_src = find_xml(run_dir, "TC-S-001")
    print(f"\nSource SPS XML: {sps_src}")

    tree_orgid = parse_xml(sps_src)
    patch_inject_proprietary_orgid(tree_orgid)
    orgid_path = OUT_DIR / "sps_violates_cgi_proprietary_orgid.xml"
    serialize(tree_orgid, orgid_path)

    valid, errors = validate_against_sps_xsd(orgid_path)
    print(f"\n[3] SPS-konform, CGI-MP BR-CGI-ORG-01 violation  {orgid_path}")
    print(f"     SPS-XSD: {'PASS (expected)' if valid else 'FAIL'}")
    for e in errors[:3]:
        print(f"        {e}")

    print("\nDone. See examples/violations/ for the three demo files.")


if __name__ == "__main__":
    main()
