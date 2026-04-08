"""End-to-end Tests fuer die pacs.008 Pipeline."""

import json
import os
from decimal import Decimal

import pytest

from src.models.config import AppConfig
from src.models.pacs008 import (
    Pacs008Flavor,
    Pacs008TestCase,
    PostalAddress,
    SettlementMethod,
)
from src.models.testcase import ExpectedResult
from src.pacs008_pipeline import Pacs008TestPipeline


def _config(tmp_path):
    return AppConfig(
        output_path=str(tmp_path),
        xsd_path="schemas/pain.001/pain.001.001.09.ch.03.xsd",
        seed=42,
        report_format="txt",
    )


def _minimal_testcase(**overrides):
    defaults = dict(
        testcase_id="TC-PACS-E2E-001",
        titel="Minimal E2E",
        ziel="Full Pipeline Smoke",
        expected_result=ExpectedResult.OK,
        flavor=Pacs008Flavor.CBPR_PLUS,
        bah_from_bic="UBSWCHZH80A",
        bah_to_bic="DEUTDEFFXXX",
        instructing_agent_bic="UBSWCHZH80A",
        instructed_agent_bic="DEUTDEFFXXX",
        debtor_name="Muster AG",
        debtor_address=PostalAddress(
            street_name="Bahnhofstrasse", building_number="42",
            postal_code="8001", town_name="Zurich", country="CH",
        ),
        debtor_iban="CH5604835012345678009",
        debtor_agent_bic="UBSWCHZH80A",
        creditor_name="Empfaenger GmbH",
        creditor_address=PostalAddress(
            street_name="Unter den Linden", building_number="7",
            postal_code="10117", town_name="Berlin", country="DE",
        ),
        creditor_iban="DE89370400440532013000",
        creditor_agent_bic="DEUTDEFFXXX",
        amount=Decimal("1000.00"),
        currency="EUR",
    )
    defaults.update(overrides)
    return Pacs008TestCase(**defaults)


class TestPipelineEndToEnd:
    def test_single_pass(self, tmp_path):
        tc = _minimal_testcase()
        pipeline = Pacs008TestPipeline(_config(tmp_path))
        results = pipeline.process([tc], str(tmp_path))
        assert len(results) == 1
        r = results[0]
        assert r.overall_pass, (
            f"Expected pass; xsd={r.xsd_valid}, "
            f"errors={r.xsd_errors}, "
            f"br_fails={[br.rule_id for br in r.business_rule_results if not br.passed]}"
        )
        # XML file exists
        assert r.xml_file_path is not None
        assert os.path.exists(r.xml_file_path)
        # File is in pacs.008 subfolder
        assert "pacs.008" in r.xml_file_path
        # Content is a valid BusinessMessage
        content = open(r.xml_file_path).read()
        assert "<BusinessMessage>" in content
        assert "<AppHdr" in content
        assert "<Document" in content
        assert "pacs.008.001.08" in content

    def test_violation_nok_becomes_pass(self, tmp_path):
        """NOK expected + violated rule = overall_pass."""
        tc = _minimal_testcase(
            testcase_id="TC-PACS-E2E-VIOL",
            expected_result=ExpectedResult.NOK,
            violate_rule="BR-CBPR-PACS-001",  # clears UETR
        )
        pipeline = Pacs008TestPipeline(_config(tmp_path))
        results = pipeline.process([tc], str(tmp_path))
        r = results[0]
        # Violation applied -> BR-CBPR-PACS-001 should fail
        fails = [br.rule_id for br in r.business_rule_results if not br.passed]
        assert "BR-CBPR-PACS-001" in fails
        # Expected NOK and it did fail -> overall_pass True
        assert r.overall_pass

    def test_report_generated(self, tmp_path):
        tc = _minimal_testcase()
        pipeline = Pacs008TestPipeline(_config(tmp_path))
        results = pipeline.process([tc], str(tmp_path))
        paths = pipeline.generate_reports(results, "dummy.xlsx", str(tmp_path))
        assert "json" in paths
        assert os.path.exists(paths["json"])
        with open(paths["json"]) as f:
            report = json.load(f)
        assert report["testlauf"]["message_type"] == "pacs.008"
        assert report["testlauf"]["total"] == 1
        assert report["testlauf"]["pass"] == 1

    def test_output_separation_from_pain001(self, tmp_path):
        """pacs.008 Files landen in pacs.008/ Subfolder."""
        tc = _minimal_testcase()
        pipeline = Pacs008TestPipeline(_config(tmp_path))
        results = pipeline.process([tc], str(tmp_path))
        pacs_dir = os.path.join(str(tmp_path), "pacs.008")
        assert os.path.isdir(pacs_dir)
        xml_files = [f for f in os.listdir(pacs_dir) if f.endswith(".xml")]
        assert len(xml_files) == 1

    def test_missing_agent_fails_rules(self, tmp_path):
        """TestCase ohne InstgAgt/InstdAgt sollte Business Rules scheitern."""
        tc = _minimal_testcase(
            testcase_id="TC-PACS-NO-AGT",
            instructing_agent_bic=None,
            debtor_agent_bic=None,  # fallback chain to instg
            instructed_agent_bic=None,
            creditor_agent_bic=None,
        )
        pipeline = Pacs008TestPipeline(_config(tmp_path))
        results = pipeline.process([tc], str(tmp_path))
        r = results[0]
        # Ohne Agenten faellt XSD oder Business Rules
        assert not r.overall_pass or not r.xsd_valid


# ---------------------------------------------------------------------------
# External XML Validator Integration (WP-11)
# ---------------------------------------------------------------------------

class TestExternalValidatorIntegration:
    def test_disabled_by_default(self, tmp_path):
        tc = _minimal_testcase()
        pipeline = Pacs008TestPipeline(_config(tmp_path))
        assert pipeline.use_external_validator is False
        results = pipeline.process([tc], str(tmp_path))
        assert results[0].external_valid is None
        assert results[0].external_errors == []

    def test_enabled_with_mock_success(self, tmp_path, monkeypatch):
        import responses
        monkeypatch.setenv("XML_VALIDATOR_API_KEY", "test-key")
        monkeypatch.setenv("XML_VALIDATOR_BASE_URL", "https://api.test")
        tc = _minimal_testcase(testcase_id="TC-EXTVAL-OK")
        with responses.RequestsMock() as rm:
            rm.add(
                responses.POST,
                "https://api.test/cbpr/validate",
                body="Message is valid",
                status=200,
            )
            pipeline = Pacs008TestPipeline(
                _config(tmp_path), use_external_validator=True
            )
            assert pipeline.use_external_validator is True
            results = pipeline.process([tc], str(tmp_path))
        r = results[0]
        assert r.external_valid is True
        assert r.external_errors == []
        assert r.overall_pass

    def test_enabled_with_mock_400(self, tmp_path, monkeypatch):
        import responses
        monkeypatch.setenv("XML_VALIDATOR_API_KEY", "test-key")
        monkeypatch.setenv("XML_VALIDATOR_BASE_URL", "https://api.test")
        tc = _minimal_testcase(testcase_id="TC-EXTVAL-400")
        with responses.RequestsMock() as rm:
            rm.add(
                responses.POST,
                "https://api.test/cbpr/validate",
                body='{"errors": ["BAH issue"]}',
                status=400,
            )
            pipeline = Pacs008TestPipeline(
                _config(tmp_path), use_external_validator=True
            )
            results = pipeline.process([tc], str(tmp_path))
        r = results[0]
        assert r.external_valid is False
        assert r.external_errors == ["BAH issue"]
        assert not r.overall_pass  # external failure propagates

    def test_401_captured_in_report(self, tmp_path, monkeypatch):
        import responses
        monkeypatch.setenv("XML_VALIDATOR_API_KEY", "bogus")
        monkeypatch.setenv("XML_VALIDATOR_BASE_URL", "https://api.test")
        tc = _minimal_testcase(testcase_id="TC-EXTVAL-401")
        with responses.RequestsMock() as rm:
            rm.add(
                responses.POST,
                "https://api.test/cbpr/validate",
                body="Unauthorized",
                status=401,
            )
            pipeline = Pacs008TestPipeline(
                _config(tmp_path), use_external_validator=True
            )
            results = pipeline.process([tc], str(tmp_path))
        r = results[0]
        assert r.external_valid is False
        assert any(
            "401" in err or "Unauthorized" in err for err in r.external_errors
        )

    def test_report_counters(self, tmp_path, monkeypatch):
        import responses
        monkeypatch.setenv("XML_VALIDATOR_API_KEY", "test-key")
        monkeypatch.setenv("XML_VALIDATOR_BASE_URL", "https://api.test")
        tc = _minimal_testcase()
        with responses.RequestsMock() as rm:
            rm.add(
                responses.POST,
                "https://api.test/cbpr/validate",
                body="Message is valid",
                status=200,
            )
            pipeline = Pacs008TestPipeline(
                _config(tmp_path), use_external_validator=True
            )
            results = pipeline.process([tc], str(tmp_path))
            paths = pipeline.generate_reports(results, "dummy.xlsx", str(tmp_path))

        import json
        with open(paths["json"]) as f:
            report = json.load(f)
        assert report["testlauf"]["external_validation_enabled"] is True
        assert report["testlauf"]["external_validation_checked"] == 1
        assert report["testlauf"]["external_validation_passed"] == 1

    def test_disabled_via_missing_credentials(self, tmp_path, monkeypatch):
        """When no key is available, the external validator auto-disables."""
        monkeypatch.delenv("XML_VALIDATOR_API_KEY", raising=False)
        monkeypatch.delenv("XML_VALIDATOR_BASE_URL", raising=False)
        monkeypatch.setenv("XML_VALIDATOR_DIR", str(tmp_path / "nonexistent"))
        pipeline = Pacs008TestPipeline(
            _config(tmp_path), use_external_validator=True
        )
        assert pipeline.use_external_validator is False  # auto-disabled
