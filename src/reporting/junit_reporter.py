"""JUnit-XML-Report-Generator für CI/CD-Integration."""

from typing import List
from xml.etree import ElementTree as ET

from src.models.testcase import TestCaseResult


def generate_junit_report(
    results: List[TestCaseResult],
    output_path: str,
) -> str:
    """Erstellt einen JUnit-XML-Report."""
    testsuite = ET.Element("testsuite")
    testsuite.set("name", "pain001-testgenerator")
    testsuite.set("tests", str(len(results)))
    testsuite.set("failures", str(sum(1 for r in results if not r.overall_pass)))

    for r in results:
        testcase = ET.SubElement(testsuite, "testcase")
        testcase.set("name", f"{r.testcase_id}: {r.titel}")
        testcase.set("classname", r.payment_type.value)

        if not r.overall_pass:
            failure = ET.SubElement(testcase, "failure")
            failure.set("type", "AssertionError")

            messages = []
            if r.xsd_errors:
                messages.append("XSD-Fehler: " + "; ".join(r.xsd_errors))

            failed_rules = [
                br for br in r.business_rule_results if not br.passed
            ]
            for br in failed_rules:
                msg = f"{br.rule_id}: {br.rule_description}"
                if br.details:
                    msg += f" ({br.details})"
                messages.append(msg)

            failure.text = "\n".join(messages)

    report_path = f"{output_path}/testlauf_ergebnis.xml"
    tree = ET.ElementTree(testsuite)
    ET.indent(tree, space="  ")
    tree.write(report_path, encoding="unicode", xml_declaration=True)

    return report_path
