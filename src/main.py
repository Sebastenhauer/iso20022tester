"""CLI Entry Point: pain.001 Test Generator."""

import argparse
import os
import sys
from datetime import datetime
from typing import List

from src.config import load_config
from src.input_handler.excel_parser import parse_excel
from src.models.config import AppConfig
from src.models.testcase import TestCaseResult
from src.pipeline import PaymentTestPipeline


def run(
    input_file: str,
    config: AppConfig,
    seed_override: int = None,
    verbose: bool = False,
) -> List[TestCaseResult]:
    """Hauptlogik: Liest Excel, generiert XMLs, validiert, erzeugt Reports."""

    # 1. Excel parsen
    print(f"Lese Testfälle aus: {input_file}")
    testcases, errors = parse_excel(input_file)
    if errors:
        print("Fehler beim Einlesen der Excel-Datei:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print(f"{len(testcases)} Testfälle eingelesen.")

    # 2. Pipeline initialisieren
    seed = seed_override if seed_override is not None else config.seed
    try:
        pipeline = PaymentTestPipeline(config, seed=seed)
    except Exception as e:
        print(f"Fehler beim Laden des XSD-Schemas: {e}")
        sys.exit(1)

    # 3. Output-Verzeichnis erstellen
    run_dir = os.path.join(
        config.output_path,
        datetime.now().strftime("%Y-%m-%d_%H%M%S"),
    )
    os.makedirs(run_dir, exist_ok=True)
    print(f"Output-Verzeichnis: {run_dir}")

    # 4. Testfälle verarbeiten
    results = pipeline.process(testcases, run_dir, verbose=verbose)

    for r in results:
        status = "Pass" if r.overall_pass else "Fail"
        print(f"  {r.testcase_id}: {status}")

    # 5. Reports generieren
    print(f"\nErstelle Reports...")
    paths = pipeline.generate_reports(results, input_file, run_dir)
    for fmt, path in paths.items():
        print(f"  {fmt.upper()}: {path}")

    # 6. Zusammenfassung
    pass_count = sum(1 for r in results if r.overall_pass)
    fail_count = len(results) - pass_count
    print(f"\n{'=' * 50}")
    print(f"Ergebnis: {pass_count} Pass, {fail_count} Fail von {len(results)} Testfällen")
    print(f"{'=' * 50}")

    return results


def run_parse_response(
    input_file: str,
    pain002_paths: List[str],
    config: AppConfig,
    seed_override: int = None,
    verbose: bool = False,
) -> List[TestCaseResult]:
    """Generiert pain.001, parst pain.002-Antworten und korreliert Ergebnisse."""

    # 1. Excel parsen und pain.001 generieren (wie run())
    print(f"Lese Testfälle aus: {input_file}")
    testcases, errors = parse_excel(input_file)
    if errors:
        print("Fehler beim Einlesen der Excel-Datei:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print(f"{len(testcases)} Testfälle eingelesen.")

    seed = seed_override if seed_override is not None else config.seed
    try:
        pipeline = PaymentTestPipeline(config, seed=seed)
    except Exception as e:
        print(f"Fehler beim Laden des XSD-Schemas: {e}")
        sys.exit(1)

    run_dir = os.path.join(
        config.output_path,
        datetime.now().strftime("%Y-%m-%d_%H%M%S"),
    )
    os.makedirs(run_dir, exist_ok=True)
    print(f"Output-Verzeichnis: {run_dir}")

    results = pipeline.process(testcases, run_dir, verbose=verbose)

    # 2. pain.002-Antworten parsen und korrelieren
    print(f"\nParse {len(pain002_paths)} pain.002-Datei(en)...")
    results, parse_errors = pipeline.process_responses(
        pain002_paths, results, verbose=verbose
    )

    if parse_errors:
        print("Fehler beim Parsen von pain.002-Dateien:")
        for e in parse_errors:
            print(f"  {e}")

    # 3. Ergebnisse ausgeben
    for r in results:
        status = "Pass" if r.overall_pass else "Fail"
        p002_info = ""
        if r.pain002_result:
            p002_sts = r.pain002_result.group_status or r.pain002_result.payment_status or "-"
            p002_info = f" [pain.002: {p002_sts}]"
        print(f"  {r.testcase_id}: {status}{p002_info}")

    # 4. Reports
    print(f"\nErstelle Reports...")
    paths = pipeline.generate_reports(results, input_file, run_dir)
    for fmt, path in paths.items():
        print(f"  {fmt.upper()}: {path}")

    # 5. Zusammenfassung
    pass_count = sum(1 for r in results if r.overall_pass)
    fail_count = len(results) - pass_count
    matched = sum(1 for r in results if r.pain002_result is not None)
    print(f"\n{'=' * 50}")
    print(f"Ergebnis: {pass_count} Pass, {fail_count} Fail von {len(results)} Testfällen")
    print(f"pain.002-Korrelation: {matched} von {len(results)} Testfällen zugeordnet")
    print(f"{'=' * 50}")

    return results


def run_roundtrip_mode(xml_paths: List[str], config: AppConfig, verbose: bool = False):
    """Round-Trip-Modus: Parst XMLs zurück und prueft Konsistenz."""
    from src.validation.roundtrip import run_roundtrip
    from src.validation.xsd_validator import XsdValidator

    xsd_validator = None
    try:
        xsd_validator = XsdValidator(config.xsd_path, cbpr_xsd_path=config.cbpr_xsd_path)
    except Exception as e:
        print(f"Warnung: XSD-Schema konnte nicht geladen werden: {e}")

    print(f"Round-Trip-Validierung für {len(xml_paths)} XML-Datei(en)...")
    results = run_roundtrip(xml_paths, xsd_validator, verbose)

    pass_count = sum(1 for r in results if r.passed)
    fail_count = len(results) - pass_count
    print(f"\n{'=' * 50}")
    print(f"Round-Trip: {pass_count} OK, {fail_count} Fehler von {len(results)} Dateien")
    print(f"{'=' * 50}")

    return 0 if fail_count == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="ISO 20022 pain.001 Test Generator",
    )

    subparsers = parser.add_subparsers(dest="command")

    gen_parser = subparsers.add_parser("generate", help="XML-Dateien generieren (Standard)")
    gen_parser.add_argument("--input", required=True, help="Pfad zur Excel-Datei")
    gen_parser.add_argument("--config", required=True, help="Pfad zur config.yaml")
    gen_parser.add_argument("--seed", type=int, default=None, help="Seed")
    gen_parser.add_argument("--verbose", action="store_true", help="Verbose")

    rt_parser = subparsers.add_parser("roundtrip", help="Round-Trip-Validierung")
    rt_parser.add_argument("xml_files", nargs="+", help="XML-Dateien oder Verzeichnis")
    rt_parser.add_argument("--config", required=True, help="Pfad zur config.yaml")
    rt_parser.add_argument("--verbose", action="store_true", help="Verbose")

    resp_parser = subparsers.add_parser(
        "parse-response", help="pain.002-Antworten parsen und mit Testfällen korrelieren"
    )
    resp_parser.add_argument("--input", required=True, help="Pfad zur Excel-Datei (pain.001 Testfälle)")
    resp_parser.add_argument("--responses", nargs="+", required=True, help="pain.002 XML-Dateien oder Verzeichnis")
    resp_parser.add_argument("--config", required=True, help="Pfad zur config.yaml")
    resp_parser.add_argument("--seed", type=int, default=None, help="Seed (muss mit Generierung übereinstimmen)")
    resp_parser.add_argument("--verbose", action="store_true", help="Verbose")

    # Abwärtskompatibilität: --input ohne Subcommand
    parser.add_argument("--input", help="Pfad zur Excel-Datei")
    parser.add_argument("--config", help="Pfad zur config.yaml")
    parser.add_argument("--seed", type=int, default=None, help="Seed")
    parser.add_argument("--verbose", action="store_true", help="Verbose")

    args = parser.parse_args()

    if args.command == "parse-response":
        config = load_config(args.config)
        pain002_files = []
        for path in args.responses:
            if os.path.isdir(path):
                for f in sorted(os.listdir(path)):
                    if f.endswith(".xml"):
                        pain002_files.append(os.path.join(path, f))
            else:
                pain002_files.append(path)
        run_parse_response(
            args.input, pain002_files, config,
            seed_override=args.seed, verbose=args.verbose,
        )

    elif args.command == "roundtrip":
        config = load_config(args.config)
        xml_files = []
        for path in args.xml_files:
            if os.path.isdir(path):
                for f in sorted(os.listdir(path)):
                    if f.endswith(".xml") and not f.startswith("testlauf"):
                        xml_files.append(os.path.join(path, f))
            else:
                xml_files.append(path)
        exit_code = run_roundtrip_mode(xml_files, config, verbose=args.verbose)
        sys.exit(exit_code)

    elif args.command == "generate" or args.input:
        input_file = getattr(args, "input", None)
        config_file = getattr(args, "config", None)
        if not input_file or not config_file:
            parser.error("--input und --config sind erforderlich")
        config = load_config(config_file)
        seed = getattr(args, "seed", None)
        verbose = getattr(args, "verbose", False)
        run(input_file, config, seed_override=seed, verbose=verbose)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
