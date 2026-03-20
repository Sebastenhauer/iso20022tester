"""CLI Entry Point: pain.001 Test Generator."""

import argparse
import os
import sys
from collections import OrderedDict
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
from src.payment_types.cbpr_plus import CbprPlusHandler
from src.payment_types.domestic_iban import DomesticIbanHandler
from src.payment_types.domestic_qr import DomesticQrHandler
from src.payment_types.sepa import SepaHandler
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


def _get_handler(payment_type: PaymentType):
    handlers = {
        PaymentType.SEPA: SepaHandler(),
        PaymentType.DOMESTIC_QR: DomesticQrHandler(),
        PaymentType.DOMESTIC_IBAN: DomesticIbanHandler(),
        PaymentType.CBPR_PLUS: CbprPlusHandler(),
    }
    return handlers[payment_type]


def _build_instruction(
    testcase: TestCase,
    factory: DataFactory,
) -> Tuple[Optional[PaymentInstruction], Optional[TestCaseResult]]:
    """Baut eine PaymentInstruction aus einem Testfall.

    Returns:
        (instruction, None) bei Erfolg, (None, error_result) bei Fehler.
    """
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
    handler = _get_handler(testcase.payment_type)
    transactions = handler.generate_transactions(testcase, factory)

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
    """Verarbeitet einen einzelnen Testfall (1 Testfall → 1 XML)."""
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
    groups: OrderedDict[Optional[str], List[TestCase]] = OrderedDict()
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
                    print(f"\nVerarbeite: {tc.testcase_id} ({tc.payment_type.value})")
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


def main():
    parser = argparse.ArgumentParser(
        description="ISO 20022 pain.001 Test Generator",
    )
    parser.add_argument(
        "--input", required=True,
        help="Pfad zur Excel-Datei mit Testfällen",
    )
    parser.add_argument(
        "--config", required=True,
        help="Pfad zur config.yaml",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Übersteuert den Seed aus config.yaml",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Ausführliche Konsolenausgabe",
    )

    args = parser.parse_args()

    config = load_config(args.config)
    run(args.input, config, seed_override=args.seed, verbose=args.verbose)


if __name__ == "__main__":
    main()
