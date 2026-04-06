"""Tests fuer den FINaplo API Client (mit HTTP mocks)."""

import os
from pathlib import Path

import pytest
import responses

from src.finaplo.client import (
    DEFAULT_LIVE_BASE_URL,
    FINAPLO_BASE_URL_ENV,
    FINAPLO_DIR_ENV,
    FINAPLO_KEY_ENV,
    FinaploAuthError,
    FinaploClient,
    FinaploConfigError,
    FinaploError,
    FinaploResult,
    FinaploServerError,
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
        monkeypatch.setenv(FINAPLO_KEY_ENV, "env-key")
        monkeypatch.setenv(FINAPLO_BASE_URL_ENV, "https://env.example")
        monkeypatch.setenv(FINAPLO_DIR_ENV, "/nonexistent")
        key, url = load_credentials()
        assert key == "env-key"
        assert url == "https://env.example"

    def test_from_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv(FINAPLO_KEY_ENV, raising=False)
        monkeypatch.delenv(FINAPLO_BASE_URL_ENV, raising=False)
        (tmp_path / "api-key-test.txt").write_text("file-key\n")
        (tmp_path / "base-url-test.txt").write_text("https://file.example\n")
        key, url = load_credentials(str(tmp_path))
        assert key == "file-key"
        assert url == "https://file.example"

    def test_default_base_url_fallback(self, tmp_path, monkeypatch):
        monkeypatch.delenv(FINAPLO_KEY_ENV, raising=False)
        monkeypatch.delenv(FINAPLO_BASE_URL_ENV, raising=False)
        (tmp_path / "api-key-x.txt").write_text("k")
        key, url = load_credentials(str(tmp_path))
        assert url == DEFAULT_LIVE_BASE_URL

    def test_missing_key_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv(FINAPLO_KEY_ENV, raising=False)
        with pytest.raises(FinaploConfigError, match="API-Key"):
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
        assert endpoint_for_flavor(Pacs008Flavor.SEPA, sepa_scheme="inst") == "/sepa/inst/validate"

    def test_unknown_flavor_raises(self):
        with pytest.raises(NotImplementedError):
            endpoint_for_flavor(Pacs008Flavor.SIC)


# ---------------------------------------------------------------------------
# Client (with HTTP mocks)
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return FinaploClient(api_key="test-key", base_url="https://api.test")


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
        assert b"<BusinessMessage>" in call.request.body.encode() if isinstance(call.request.body, str) else b"<BusinessMessage>" in call.request.body


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
        with pytest.raises(FinaploAuthError):
            client.validate(SAMPLE_XML)

    @responses.activate
    def test_500_raises_server_error(self, client):
        responses.add(
            responses.POST,
            "https://api.test/cbpr/validate",
            body="Internal Server Error",
            status=500,
        )
        with pytest.raises(FinaploServerError):
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
