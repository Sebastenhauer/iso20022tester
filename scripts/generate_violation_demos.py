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

3. ``sps_violates_cgi_empty_tags.xml``
   A clean SPS pain.001 with empty ``<PmtTpInf/>`` and ``<RmtInf/>``
   elements injected into one CdtTrfTxInf. SPS XSD allows these because
   their sub-elements are all optional, so the empty containers pass
   validation. CGI-MP best-practice (`empty tags must not be used`)
   is violated.

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


def patch_inject_empty_tags(tree: etree._ElementTree) -> None:
    """Inject empty <RmtInf></RmtInf> into the first CdtTrfTxInf.

    Note on form:
    - The self-closing form ``<RmtInf/>`` is rejected by the GEFEG.FX SPS
      validator with ``Error: Empty element``, even though the SPS XSD
      itself accepts it (RemittanceInformation16 has all-optional
      sub-elements). The user-facing SPS validation tooling treats
      ``<X/>`` as a custom rule violation.
    - The open-close form ``<RmtInf></RmtInf>`` is accepted by SPS
      tooling (still empty content but presented in long form).
    - CGI-MP best practice ``BR-CGI-CHAR-01`` forbids both forms
      because the rule is "tag without value".

    Earlier versions of this script also injected an empty C-level
    ``<PmtTpInf/>``, which triggered SPS rule **CH07** ("PmtTpInf darf
    nicht gleichzeitig auf B- und C-Level verwendet werden") because
    the source TC-S-001 SEPA template already has a B-level PmtTpInf
    with SvcLvl=SEPA. CH07 is a structural exclusivity rule unrelated
    to the empty-tag demo, so the PmtTpInf injection has been removed.
    Only the RmtInf injection remains, in the SPS-tolerated open-close
    form.
    """
    cdt_tx = tree.find(".//p:CdtTrfTxInf", NS)
    if cdt_tx is None:
        return

    # Remove any existing RmtInf (e.g. from the SEPA testcase) so we
    # control the form precisely
    for existing_rmt in cdt_tx.findall("p:RmtInf", NS):
        cdt_tx.remove(existing_rmt)

    # Append open-close empty RmtInf (text="" forces lxml to render
    # <RmtInf></RmtInf> instead of the self-closing <RmtInf/>)
    rmt = etree.SubElement(cdt_tx, f"{{{PAIN001_NS}}}RmtInf")
    rmt.text = ""


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

    # === Demo 3: SPS XML with empty tags violating CGI-MP ===
    sps_src = find_xml(run_dir, "TC-S-001")
    print(f"\nSource SPS XML: {sps_src}")

    tree_empty = parse_xml(sps_src)
    patch_inject_empty_tags(tree_empty)
    empty_path = OUT_DIR / "sps_violates_cgi_empty_tags.xml"
    serialize(tree_empty, empty_path)

    valid, errors = validate_against_sps_xsd(empty_path)
    print(f"\n[3] SPS-konform, CGI-MP empty-tag violation  {empty_path}")
    print(f"     SPS-XSD: {'PASS (expected)' if valid else 'FAIL'}")
    for e in errors[:3]:
        print(f"        {e}")

    print("\nDone. See examples/violations/ for the three demo files.")


if __name__ == "__main__":
    main()
