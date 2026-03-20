"""XSD-Schema-Validierung für pain.001.001.09."""

from typing import List, Tuple

from lxml import etree


class XsdValidator:
    """Validiert XML-Dokumente gegen ein XSD-Schema."""

    def __init__(self, xsd_path: str):
        with open(xsd_path, "rb") as f:
            schema_doc = etree.parse(f)
        self.schema = etree.XMLSchema(schema_doc)

    def validate(self, xml_doc: etree._Element) -> Tuple[bool, List[str]]:
        """Validiert ein XML-Dokument gegen das Schema.

        Returns:
            Tuple von (is_valid, error_messages).
        """
        is_valid = self.schema.validate(xml_doc)
        errors = []
        if not is_valid:
            for error in self.schema.error_log:
                errors.append(
                    f"Zeile {error.line}: {error.message}"
                )
        return is_valid, errors
