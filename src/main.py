"""CLI Entry Point: pain.001 Test Generator."""

import argparse
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.config import load_config
from src.data_factory.generator import DataFactory
from src.input_handler.excel_parser import parse_excel
from src.mapping.field_mapper import validate_and_map_overrides
from src.models.config import AppConfig
from src.models.testcase import (
    ExpectedResult,
    Pain001Document,
    PaymentInstruction,
    PaymentType,
    TestCase,
    TestCaseResult,
)
from src.payment_types import get_handler
from src.reporting.json_reporter import generate_json_report
from src.reporting.junit_reporter import generate_junit_report
from src.reporting.word_reporter import generate_word_report, generate_txt_report
from src.validation.business_rules import (
    apply_rule_violation,
    validate_all_business_rules,
)
from src.validation.xsd_validator import XsdValidator
from src.xml_generator.pain001_builder import (
    build_pain001_document,
    build_pain001_xml,
    serialize_xml,
)




def _apply_defaults(testcase: TestCase, factory: DataFactory) -> TestCase:
    """Wendet Defaults an fuer optionale Felder die leer sind."""
    updates = {}

    if testcase.payment_type is None:
        updates["payment_type"] = PaymentType.DOMESTIC_IBAN

    payment_type = updates.get("payment_type", testcase.payment_type)

    if testcase.debtor.name is None:
        debtor = testcase.debtor.model_copy(update={"name": factory.generate_debtor_name()})
        updates["debtor"] = debtor

    if testcase.currency is None:
        updates["currency"] = factory.generate_currency(payment_type)

    if testcase.amount is None:
        updates["amount"] = factory.generate_amount(payment_type)

    if updates:
        testcase = testcase.model_copy(update=updates)

    return testcase


def _build_instruction(
    testcase: TestCase,
    factory: DataFactory,
) -> Tuple[Optional[PaymentInstruction], Optional[TestCaseResult]]:
    """Baut eine PaymentInstruction aus einem Testfall.

    Returns:
        (instruction, None) bei Erfolg, (None, error_result) bei Fehler.
    """
    # 0. Defaults anwenden
    testcase = _apply_defaults(testcase, factory)

    # 1. Overrides validieren
    mapped, special, mapping_errors = validate_and_map_overrides(testcase.overrides)
    if mapping_errors:
        error_msgs = [e.message for e in mapping_errors]
        return None, TestCaseResult(
            testcase_id=testcase.testcase_id,
            titel=testcase.titel,
            payment_type=testcase.payment_type,
            expected_result=testcase.expected_result,
            xsd_valid=False,
            xsd_errors=error_msgs,
            overall_pass=False,
            remarks="Mapping-Fehler: " + "; ".join(error_msgs),
        )

    # 2. Handler und Transaktionen generieren
    handler = get_handler(testcase.payment_type)
    transactions = handler.generate_transactions(testcase, factory)

    # 2a. Per-Transaktions C-Level-Overrides anwenden (F-13)
    tx_inputs = testcase.transaction_inputs or []
    for i, tx in enumerate(transactions):
        if i < len(tx_inputs) and tx_inputs[i].overrides:
            tx_mapped, _, tx_errors = validate_and_map_overrides(tx_inputs[i].overrides)
            if tx_errors:
                error_msgs = [e.message for e in tx_errors]
                return None, TestCaseResult(
                    testcase_id=testcase.testcase_id,
                    titel=testcase.titel,
                    payment_type=testcase.payment_type,
                    expected_result=testcase.expected_result,
                    xsd_valid=False,
                    xsd_errors=error_msgs,
                    overall_pass=False,
                    remarks=f"Mapping-Fehler in Transaktion {i+1}: " + "; ".join(error_msgs),
                )
            updates = {}
            for key, info in tx_mapped.items():
                if info["level"] == "C":
                    if key == "Cdtr.Nm":
                        updates["creditor_name"] = info["value"]
                    elif key == "CdtrAcct.IBAN":
                        updates["creditor_iban"] = info["value"]
                    elif key == "CdtrAgt.BICFI":
                        updates["creditor_bic"] = info["value"]
                    elif key == "RmtInf.Ustrd":
                        updates["remittance_info"] = {"type": "USTRD", "value": info["value"]}
                    elif key.startswith("Cdtr.PstlAdr."):
                        addr_key = key.split(".")[-1]
                        addr = dict(tx.creditor_address or {})
                        addr[addr_key] = info["value"]
                        updates["creditor_address"] = addr
            if updates:
                transactions[i] = tx.model_copy(update=updates)

    # 3. PaymentInstruction zusammenbauen
    instruction = PaymentInstruction(
        msg_id=factory.generate_msg_id(),
        pmt_inf_id=factory.generate_pmt_inf_id(),
        cre_dt_tm=datetime.now().isoformat(),
        reqd_exctn_dt=factory.get_next_business_day(testcase.payment_type).isoformat(),
        debtor=testcase.debtor,
        service_level=handler.get_service_level(),
        charge_bearer=handler.get_charge_bearer(),
        transactions=transactions,
    )

    # 4. Overrides anwenden (B-Level)
    for key, mapping_info in mapped.items():
        value = mapping_info["value"]
        if mapping_info["level"] == "B":
            if key == "ChrgBr":
                instruction = instruction.model_copy(update={"charge_bearer": value})
            elif key == "SvcLvl.Cd":
                instruction = instruction.model_copy(update={"service_level": value})
            elif key == "LclInstrm.Cd":
                instruction = instruction.model_copy(update={"local_instrument": value})
            elif key == "CtgyPurp.Cd":
                instruction = instruction.model_copy(update={"category_purpose": value})
            elif key == "ReqdExctnDt":
                instruction = instruction.model_copy(update={"reqd_exctn_dt": value})

    # 5. Negative Testing: Gezielte Regelverletzung
    if testcase.violate_rule:
        instruction = apply_rule_violation(testcase, instruction)

    return instruction, None


def _process_single_testcase(
    testcase: TestCase,
    factory: DataFactory,
    xsd_validator: XsdValidator,
    output_dir: str,
    verbose: bool = False,
) -> TestCaseResult:
    """Verarbeitet einen einzelnen Testfall (1 Testfall -> 1 XML)."""
    instruction, error_result = _build_instruction(testcase, factory)
    if error_result:
        return error_result

    # XML generieren (Einzel-Payment)
    xml_doc = build_pain001_xml(instruction)

    # XSD-Validierung
    xsd_valid, xsd_errors = xsd_validator.validate(xml_doc)
    if not xsd_valid:
        error_detail = "\n".join(f"  - {err}" for err in xsd_errors)
        raise RuntimeError(
            f"XSD-Validierung fehlgeschlagen für {testcase.testcase_id} "
            f"({testcase.payment_type.value}). "
            f"Dies deutet auf einen Bug im XML-Generator hin.\n"
            f"XSD-Fehler:\n{error_detail}"
        )

    # XML speichern
    xml_file_path = _save_xml(xml_doc, testcase.testcase_id, factory, output_dir)
    if verbose:
        print(f"  XML gespeichert: {xml_file_path}")

    # Business-Rule-Validierung + Pass/Fail
    return _evaluate_testcase(testcase, instruction, xml_file_path)


def _process_group(
    testcases: List[TestCase],
    factory: DataFactory,
    xsd_validator: XsdValidator,
    output_dir: str,
    verbose: bool = False,
) -> List[TestCaseResult]:
    """Verarbeitet eine Gruppe von Testfällen (N Testfälle → 1 XML mit N PmtInf)."""
    instructions: List[Tuple[TestCase, PaymentInstruction]] = []
    results: List[TestCaseResult] = []

    # Instruktionen bauen
    for tc in testcases:
        instruction, error_result = _build_instruction(tc, factory)
        if error_result:
            results.append(error_result)
        else:
            instructions.append((tc, instruction))

    if not instructions:
        return results

    # Pain001Document zusammenbauen (Multi-Payment)
    group_id = testcases[0].group_id
    all_instructions = [instr for _, instr in instructions]
    first_instr = all_instructions[0]

    document = Pain001Document(
        msg_id=first_instr.msg_id,
        cre_dt_tm=first_instr.cre_dt_tm,
        initiating_party_name=first_instr.debtor.name,
        payment_instructions=all_instructions,
    )

    # XML generieren (Multi-Payment)
    xml_doc = build_pain001_document(document)

    # XSD-Validierung
    xsd_valid, xsd_errors = xsd_validator.validate(xml_doc)
    if not xsd_valid:
        tc_ids = ", ".join(tc.testcase_id for tc, _ in instructions)
        error_detail = "\n".join(f"  - {err}" for err in xsd_errors)
        raise RuntimeError(
            f"XSD-Validierung fehlgeschlagen für Gruppe '{group_id}' "
            f"(Testfälle: {tc_ids}). "
            f"Dies deutet auf einen Bug im XML-Generator hin.\n"
            f"XSD-Fehler:\n{error_detail}"
        )

    # XML speichern (Dateiname enthält GroupId)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uuid_short = factory.generate_uuid_short()
    filename = f"{timestamp}_Group-{group_id}_{uuid_short}.xml"
    xml_file_path = os.path.join(output_dir, filename)
    xml_bytes = serialize_xml(xml_doc)
    with open(xml_file_path, "wb") as f:
        f.write(xml_bytes)

    if verbose:
        print(f"  XML gespeichert (Multi-Payment, {len(instructions)} PmtInf): {xml_file_path}")

    # Business-Rule-Validierung pro Testfall
    for tc, instr in instructions:
        result = _evaluate_testcase(tc, instr, xml_file_path)
        results.append(result)

    return results


def _evaluate_testcase(
    testcase: TestCase,
    instruction: PaymentInstruction,
    xml_file_path: str,
) -> TestCaseResult:
    """Business-Rule-Validierung und Pass/Fail-Bewertung für einen Testfall."""
    business_rule_results = validate_all_business_rules(instruction, testcase)
    all_rules_passed = all(br.passed for br in business_rule_results)

    if testcase.expected_result == ExpectedResult.OK:
        overall_pass = all_rules_passed
    else:  # NOK
        overall_pass = not all_rules_passed

    return TestCaseResult(
        testcase_id=testcase.testcase_id,
        titel=testcase.titel,
        payment_type=testcase.payment_type,
        expected_result=testcase.expected_result,
        xsd_valid=True,
        xsd_errors=[],
        business_rule_results=business_rule_results,
        overall_pass=overall_pass,
        xml_file_path=xml_file_path,
        remarks=testcase.remarks,
    )


def _save_xml(
    xml_doc, testcase_id: str, factory: DataFactory, output_dir: str
) -> str:
    """Speichert ein XML-Dokument und gibt den Dateipfad zurück."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    uuid_short = factory.generate_uuid_short()
    filename = f"{timestamp}_{testcase_id}_{uuid_short}.xml"
    xml_file_path = os.path.join(output_dir, filename)
    xml_bytes = serialize_xml(xml_doc)
    with open(xml_file_path, "wb") as f:
        f.write(xml_bytes)
    return xml_file_path


def _group_testcases(testcases: List[TestCase]) -> List[List[TestCase]]:
    """Gruppiert Testfälle nach GroupId. Ohne GroupId → Einzelgruppe."""
    groups: Dict[Optional[str], List[TestCase]] = {}
    for tc in testcases:
        key = tc.group_id  # None für Einzel-Testfälle
        if key not in groups:
            groups[key] = []
        groups[key].append(tc)
    return list(groups.values())


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

    # 2. Factory initialisieren
    seed = seed_override if seed_override is not None else config.seed
    factory = DataFactory(seed=seed)

    # 3. XSD-Validator laden
    try:
        xsd_validator = XsdValidator(config.xsd_path)
    except Exception as e:
        print(f"Fehler beim Laden des XSD-Schemas '{config.xsd_path}': {e}")
        sys.exit(1)

    # 4. Output-Verzeichnis erstellen
    run_dir = os.path.join(
        config.output_path,
        datetime.now().strftime("%Y-%m-%d_%H%M%S"),
    )
    os.makedirs(run_dir, exist_ok=True)
    print(f"Output-Verzeichnis: {run_dir}")

    # 5. Testfälle verarbeiten (einzeln oder gruppiert)
    results = []
    groups = _group_testcases(testcases)

    for group in groups:
        is_multi = group[0].group_id is not None and len(group) > 1

        if is_multi:
            group_id = group[0].group_id
            if verbose:
                tc_ids = ", ".join(tc.testcase_id for tc in group)
                print(f"\nVerarbeite Gruppe '{group_id}': {tc_ids}")

            group_results = _process_group(
                group, factory, xsd_validator, run_dir, verbose
            )
            for result in group_results:
                results.append(result)
                status = "Pass" if result.overall_pass else "Fail"
                print(f"  {result.testcase_id}: {status}")
        else:
            # Einzel-Testfälle (auch einzelne mit GroupId)
            for tc in group:
                if verbose:
                    pt_label = tc.payment_type.value if tc.payment_type else "auto"
                    print(f"\nVerarbeite: {tc.testcase_id} ({pt_label})")
                result = _process_single_testcase(
                    tc, factory, xsd_validator, run_dir, verbose
                )
                results.append(result)
                status = "Pass" if result.overall_pass else "Fail"
                print(f"  {tc.testcase_id}: {status}")

    # 6. Reports generieren
    print(f"\nErstelle Reports...")

    # JSON immer
    json_path = generate_json_report(results, input_file, run_dir)
    print(f"  JSON: {json_path}")

    # JUnit immer
    junit_path = generate_junit_report(results, run_dir)
    print(f"  JUnit: {junit_path}")

    # Word oder Text
    if config.report_format == "docx":
        try:
            word_path = generate_word_report(results, input_file, run_dir)
            print(f"  Word: {word_path}")
        except Exception as e:
            print(f"  Word-Report fehlgeschlagen ({e}), erstelle Text-Fallback...")
            txt_path = generate_txt_report(results, input_file, run_dir)
            print(f"  Text: {txt_path}")
    else:
        txt_path = generate_txt_report(results, input_file, run_dir)
        print(f"  Text: {txt_path}")

    # 7. Zusammenfassung
    pass_count = sum(1 for r in results if r.overall_pass)
    fail_count = len(results) - pass_count
    print(f"\n{'=' * 50}")
    print(f"Ergebnis: {pass_count} Pass, {fail_count} Fail von {len(results)} Testfällen")
    print(f"{'=' * 50}")

    return results


def run_roundtrip_mode(xml_paths: List[str], config: AppConfig, verbose: bool = False):
    """Round-Trip-Modus: Parst XMLs zurueck und prueft Konsistenz."""
    from src.validation.roundtrip import run_roundtrip

    xsd_validator = None
    try:
        xsd_validator = XsdValidator(config.xsd_path)
    except Exception as e:
        print(f"Warnung: XSD-Schema konnte nicht geladen werden: {e}")

    print(f"Round-Trip-Validierung fuer {len(xml_paths)} XML-Datei(en)...")
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

    # Default-Modus: generate
    gen_parser = subparsers.add_parser("generate", help="XML-Dateien generieren (Standard)")
    gen_parser.add_argument("--input", required=True, help="Pfad zur Excel-Datei mit Testfaellen")
    gen_parser.add_argument("--config", required=True, help="Pfad zur config.yaml")
    gen_parser.add_argument("--seed", type=int, default=None, help="Uebersteuert den Seed")
    gen_parser.add_argument("--verbose", action="store_true", help="Ausfuehrliche Ausgabe")

    # Round-Trip-Modus
    rt_parser = subparsers.add_parser("roundtrip", help="Round-Trip-Validierung fuer XML-Dateien")
    rt_parser.add_argument("xml_files", nargs="+", help="XML-Dateien oder Verzeichnis")
    rt_parser.add_argument("--config", required=True, help="Pfad zur config.yaml")
    rt_parser.add_argument("--verbose", action="store_true", help="Ausfuehrliche Ausgabe")

    # Abwaertskompatibilitaet: --input ohne Subcommand = generate
    parser.add_argument("--input", help="Pfad zur Excel-Datei (Abwaertskompatibilitaet)")
    parser.add_argument("--config", help="Pfad zur config.yaml")
    parser.add_argument("--seed", type=int, default=None, help="Seed")
    parser.add_argument("--verbose", action="store_true", help="Verbose")

    args = parser.parse_args()

    if args.command == "roundtrip":
        config = load_config(args.config)
        # Verzeichnisse zu einzelnen XML-Dateien auflösen
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
