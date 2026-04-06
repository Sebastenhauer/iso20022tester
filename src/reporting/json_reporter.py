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
            "anzahl_testfälle": len(results),
            "anzahl_pass": sum(1 for r in results if r.overall_pass),
            "anzahl_fail": sum(1 for r in results if not r.overall_pass),
        },
        "testfälle": [],
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
        if r.pain002_result:
            p = r.pain002_result
            tc["pain002"] = {
                "pain002_msg_id": p.pain002_msg_id,
                "original_msg_id": p.original_msg_id,
                "gruppen_status": p.group_status,
                "zahlungs_status": p.payment_status,
                "transaktionen": [
                    {
                        "end_to_end_id": t.end_to_end_id,
                        "status": t.status,
                        "grund_code": t.reason_code,
                        "zusatzinfo": t.reason_additional,
                    }
                    for t in p.transaction_statuses
                ],
                "pain002_datei": p.pain002_file_path,
            }
        report["testfälle"].append(tc)

    report_path = f"{output_path}/testlauf_ergebnis.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    return report_path
