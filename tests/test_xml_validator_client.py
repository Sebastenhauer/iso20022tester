"""Tests for the external XML Validator service client (with HTTP mocks)."""

import os
from pathlib import Path

import pytest
import responses

from src.xml_validator_service.client import (
    ENV_BASE_URL,
    ENV_DIR,
    ENV_KEY,
    ExternalValidationResult,
    XmlValidatorAuthError,
    XmlValidatorClient,
    XmlValidatorConfigError,
    XmlValidatorError,
    XmlValidatorServerError,
    _parse_error_body,
    endpoint_for_flavor,
    load_credentials,
)
from src.models.pacs008 import Pacs008Flavor


SAMPLE_XML = b"<?xml version=\"1.0\"?><BusinessMessage><AppHdr/><Document/></BusinessMessage>"


# ---------------------------------------------------------------------------
# Credential Loading
# ---------------------------------------------------------------------------

class TestLoadCredentials:
    def test_env_vars_priority(self, monkeypatch):
        monkeypatch.setenv(ENV_KEY, "env-key")
        monkeypatch.setenv(ENV_BASE_URL, "https://env.example")
        monkeypatch.setenv(ENV_DIR, "/nonexistent")
        key, url = load_credentials()
        assert key == "env-key"
        assert url == "https://env.example"

    def test_from_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv(ENV_KEY, raising=False)
        monkeypatch.delenv(ENV_BASE_URL, raising=False)
        (tmp_path / "api-key-test.txt").write_text("file-key\n")
        (tmp_path / "base-url-test.txt").write_text("https://file.example\n")
        key, url = load_credentials(str(tmp_path))
        assert key == "file-key"
        assert url == "https://file.example"

    def test_no_default_url_fallback(self, tmp_path, monkeypatch):
        """The client must NOT silently default to any hardcoded URL."""
        monkeypatch.delenv(ENV_KEY, raising=False)
        monkeypatch.delenv(ENV_BASE_URL, raising=False)
        (tmp_path / "api-key-x.txt").write_text("k")
        with pytest.raises(XmlValidatorConfigError, match="base URL"):
            load_credentials(str(tmp_path))

    def test_missing_key_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv(ENV_KEY, raising=False)
        monkeypatch.delenv(ENV_BASE_URL, raising=False)
        with pytest.raises(XmlValidatorConfigError, match="API key"):
            load_credentials(str(tmp_path))


# ---------------------------------------------------------------------------
# Endpoint Dispatch
# ---------------------------------------------------------------------------

class TestEndpointDispatch:
    def test_cbpr_plus(self):
        assert endpoint_for_flavor(Pacs008Flavor.CBPR_PLUS) == "/cbpr/validate"

    def test_target2(self):
        assert endpoint_for_flavor(Pacs008Flavor.TARGET2) == "/target2/validate"

    def test_sepa_default_scheme(self):
        assert endpoint_for_flavor(Pacs008Flavor.SEPA) == "/sepa/sct/validate"

    def test_sepa_custom_scheme(self):
        assert (
            endpoint_for_flavor(Pacs008Flavor.SEPA, sepa_scheme="inst")
            == "/sepa/inst/validate"
        )

    def test_unknown_flavor_raises(self):
        with pytest.raises(NotImplementedError):
            endpoint_for_flavor(Pacs008Flavor.SIC)


# ---------------------------------------------------------------------------
# Client (with HTTP mocks)
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return XmlValidatorClient(api_key="test-key", base_url="https://api.test")


class TestClientSuccessPath:
    @responses.activate
    def test_validate_200_valid(self, client):
        responses.add(
            responses.POST,
            "https://api.test/cbpr/validate",
            body="Message is valid",
            status=200,
        )
        result = client.validate(SAMPLE_XML, flavor=Pacs008Flavor.CBPR_PLUS)
        assert result.valid is True
        assert result.status_code == 200
        assert result.errors == []
        assert result.flavor == "CBPR+"
        assert result.endpoint == "/cbpr/validate"

    @responses.activate
    def test_request_headers(self, client):
        responses.add(
            responses.POST,
            "https://api.test/cbpr/validate",
            body="Message is valid",
            status=200,
        )
        client.validate(SAMPLE_XML)
        assert len(responses.calls) == 1
        call = responses.calls[0]
        assert call.request.headers["Authorization"] == "Bearer test-key"
        assert call.request.headers["Content-Type"] == "text/plain"
        body = call.request.body
        if isinstance(body, str):
            body = body.encode()
        assert b"<BusinessMessage>" in body


class TestClientErrorPaths:
    @responses.activate
    def test_400_with_plain_errors(self, client):
        responses.add(
            responses.POST,
            "https://api.test/cbpr/validate",
            body="Line 1 error\nLine 2 error",
            status=400,
        )
        result = client.validate(SAMPLE_XML)
        assert result.valid is False
        assert result.status_code == 400
        assert result.errors == ["Line 1 error", "Line 2 error"]

    @responses.activate
    def test_400_with_json_list(self, client):
        responses.add(
            responses.POST,
            "https://api.test/cbpr/validate",
            body='["err1", "err2"]',
            status=400,
            content_type="application/json",
        )
        result = client.validate(SAMPLE_XML)
        assert result.valid is False
        assert result.errors == ["err1", "err2"]

    @responses.activate
    def test_400_with_json_dict_errors_key(self, client):
        responses.add(
            responses.POST,
            "https://api.test/cbpr/validate",
            body='{"errors": ["a", "b"]}',
            status=400,
        )
        result = client.validate(SAMPLE_XML)
        assert result.errors == ["a", "b"]

    @responses.activate
    def test_401_raises_auth_error(self, client):
        responses.add(
            responses.POST,
            "https://api.test/cbpr/validate",
            body="Unauthorized",
            status=401,
        )
        with pytest.raises(XmlValidatorAuthError):
            client.validate(SAMPLE_XML)

    @responses.activate
    def test_500_raises_server_error(self, client):
        responses.add(
            responses.POST,
            "https://api.test/cbpr/validate",
            body="Internal Server Error",
            status=500,
        )
        with pytest.raises(XmlValidatorServerError):
            client.validate(SAMPLE_XML)


class TestParseErrorBody:
    def test_empty(self):
        assert _parse_error_body("") == []
        assert _parse_error_body(None) == []

    def test_plain_text(self):
        assert _parse_error_body("one\ntwo") == ["one", "two"]

    def test_json_list(self):
        assert _parse_error_body('["a","b"]') == ["a", "b"]

    def test_json_dict_message(self):
        assert _parse_error_body('{"message": "bad xml"}') == ["bad xml"]
