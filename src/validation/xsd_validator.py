"""XSD-Schema-Validierung für pain.001.001.09 (SPS + CBPR+)."""

from typing import List, Optional, Tuple

from lxml import etree

from src.models.testcase import Standard


class XsdValidator:
    """Validiert XML-Dokumente gegen SPS- und/oder CBPR+-Schema."""

    def __init__(self, sps_xsd_path: str, cbpr_xsd_path: Optional[str] = None):
        self.sps_schema = self._load_schema(sps_xsd_path)
        self.cbpr_schema = self._load_schema(cbpr_xsd_path) if cbpr_xsd_path else None

    @staticmethod
    def _load_schema(xsd_path: str) -> etree.XMLSchema:
        with open(xsd_path, "rb") as f:
            schema_doc = etree.parse(f)
        return etree.XMLSchema(schema_doc)

    def validate(
        self, xml_doc: etree._Element, standard: Standard = Standard.SPS_2025
    ) -> Tuple[bool, List[str]]:
        """Validiert ein XML-Dokument gegen das zum Standard passende Schema.

        Returns:
            Tuple von (is_valid, error_messages).
        """
        if standard == Standard.CBPR_PLUS_2026:
            if self.cbpr_schema is None:
                raise RuntimeError(
                    "CBPR+ XSD nicht konfiguriert. Bitte 'cbpr_xsd_path' in "
                    "config.yaml setzen. Das XSD ist ueber SWIFT MyStandards "
                    "(kostenloser Login) verfügbar."
                )
            schema = self.cbpr_schema
        else:
            schema = self.sps_schema

        is_valid = schema.validate(xml_doc)
        errors = []
        if not is_valid:
            for error in schema.error_log:
                errors.append(f"Zeile {error.line}: {error.message}")
        return is_valid, errors
