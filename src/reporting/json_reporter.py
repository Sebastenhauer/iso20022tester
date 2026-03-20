"""JSON-Report-Generator."""

import json
from datetime import datetime
from typing import List

from src.models.testcase import TestCaseResult


def generate_json_report(
    results: List[TestCaseResult],
    excel_file: str,
    output_path: str,
) -> str:
    """Erstellt einen JSON-Report und speichert ihn."""
    report = {
        "testlauf": {
            "datum": datetime.now().isoformat(),
            "input_datei": excel_file,
            "anzahl_testfaelle": len(results),
            "anzahl_pass": sum(1 for r in results if r.overall_pass),
            "anzahl_fail": sum(1 for r in results if not r.overall_pass),
        },
        "testfaelle": [],
    }

    for r in results:
        tc = {
            "testcase_id": r.testcase_id,
            "titel": r.titel,
            "zahlungstyp": r.payment_type.value,
            "erwartetes_ergebnis": r.expected_result.value,
            "xsd_valide": r.xsd_valid,
            "xsd_fehler": r.xsd_errors,
            "business_rules": [
                {
                    "rule_id": br.rule_id,
                    "beschreibung": br.rule_description,
                    "bestanden": br.passed,
                    "details": br.details,
                }
                for br in r.business_rule_results
            ],
            "ergebnis": "Pass" if r.overall_pass else "Fail",
            "xml_datei": r.xml_file_path,
            "bemerkungen": r.remarks,
        }
        report["testfaelle"].append(tc)

    report_path = f"{output_path}/testlauf_ergebnis.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report_path
