#!/usr/bin/env python3
"""Second-Opinion-Validator: Validiert generierte XML-Dateien mit xmlschema.

Verwendet die xmlschema-Library (unabhängig von lxml) als Gegenprüfung,
um sicherzustellen, dass unsere generierten Dateien auch von einer
alternativen XSD-Implementierung als valide erkannt werden.

Verwendung:
    poetry run python scripts/validate_external.py output/2026-03-21_*/
    poetry run python scripts/validate_external.py output/2026-03-21_*/ --report report.json
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime

try:
    import xmlschema
except ImportError:
    print("Fehler: 'xmlschema' ist nicht installiert.")
    print("Installation: poetry add xmlschema --group dev")
    sys.exit(1)


DEFAULT_XSD = "schemas/pain.001.001.09.ch.03.xsd"


def validate_file(schema: xmlschema.XMLSchema, xml_path: str) -> dict:
    """Validiert eine einzelne XML-Datei und gibt das Ergebnis zurück."""
    result = {
        "file": os.path.basename(xml_path),
        "path": xml_path,
        "valid": False,
        "errors": [],
    }

    try:
        schema.validate(xml_path)
        result["valid"] = True
    except xmlschema.XMLSchemaValidationError as e:
        result["errors"].append(str(e.reason) if e.reason else str(e))
    except Exception as e:
        result["errors"].append(f"Unerwarteter Fehler: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Second-Opinion XSD-Validierung mit xmlschema",
    )
    parser.add_argument(
        "directories",
        nargs="+",
        help="Output-Verzeichnisse mit XML-Dateien",
    )
    parser.add_argument(
        "--xsd",
        default=DEFAULT_XSD,
        help=f"Pfad zum XSD-Schema (Default: {DEFAULT_XSD})",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Pfad für JSON-Report (optional)",
    )

    args = parser.parse_args()

    # Schema laden
    if not os.path.exists(args.xsd):
        print(f"Fehler: XSD-Schema nicht gefunden: {args.xsd}")
        sys.exit(1)

    print(f"Lade Schema: {args.xsd}")
    try:
        schema = xmlschema.XMLSchema(args.xsd)
    except Exception as e:
        print(f"Fehler beim Laden des Schemas: {e}")
        sys.exit(1)

    # XML-Dateien finden
    xml_files = []
    for directory in args.directories:
        pattern = os.path.join(directory, "*.xml")
        found = glob.glob(pattern)
        # JUnit-Report ausschliessen
        found = [f for f in found if not f.endswith("testlauf_ergebnis.xml")]
        xml_files.extend(found)

    if not xml_files:
        print("Keine XML-Dateien gefunden.")
        sys.exit(1)

    xml_files.sort()
    print(f"\n{len(xml_files)} XML-Dateien gefunden.\n")
    print("=" * 60)

    # Validierung
    results = []
    valid_count = 0
    invalid_count = 0

    for xml_path in xml_files:
        result = validate_file(schema, xml_path)
        results.append(result)

        filename = result["file"]
        if result["valid"]:
            valid_count += 1
            print(f"  ✓ {filename}")
        else:
            invalid_count += 1
            print(f"  ✗ {filename}")
            for err in result["errors"]:
                print(f"    → {err}")

    # Zusammenfassung
    print("=" * 60)
    print(f"\nErgebnis: {valid_count} valide, {invalid_count} invalide "
          f"von {len(xml_files)} Dateien")

    if invalid_count == 0:
        print("\n✓ Alle Dateien bestehen die Second-Opinion-Validierung.")
    else:
        print(f"\n✗ {invalid_count} Datei(en) haben die Validierung nicht bestanden.")

    # JSON-Report
    if args.report:
        report = {
            "timestamp": datetime.now().isoformat(),
            "schema": args.xsd,
            "validator": f"xmlschema {xmlschema.__version__}",
            "total": len(xml_files),
            "valid": valid_count,
            "invalid": invalid_count,
            "results": results,
        }
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nReport gespeichert: {args.report}")

    sys.exit(0 if invalid_count == 0 else 1)


if __name__ == "__main__":
    main()
