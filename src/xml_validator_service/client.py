"""External XML Validator Service Client.

Thin REST wrapper for an external ISO 20022 validation service. The
specific provider/URL is configurable; this module makes no assumption
about which third-party API is used.

Authentication: HTTP Bearer token.

Credentials are loaded from (in priority order):
1. Environment variables ``XML_VALIDATOR_API_KEY`` and ``XML_VALIDATOR_BASE_URL``
2. Files in the gitignored ``xml_validator/`` folder at repo root:
   - ``api-key*.txt`` containing the bearer token (single line)
   - ``base-url*.txt`` containing the base URL

Endpoint dispatch by ``Pacs008Flavor``:
- ``CBPR+``   -> POST ``/cbpr/validate``
- ``TARGET2`` -> POST ``/target2/validate`` (future)
- ``SEPA``    -> POST ``/sepa/{sepaScheme}/validate`` (future)

Response handling:
- ``200 OK``: plain-text body, parsed as ``valid=True``
- ``400/4xx``: validation errors (JSON list, JSON dict with common
  keys, or plain text); parsed into ``ExternalValidationResult.errors``
- ``401``: ``XmlValidatorAuthError``
- ``500-5xx``: ``XmlValidatorServerError``
- Specific 4xx with body ``"subscription.expired"``: signals trial
  quota exhaustion as ``XmlValidatorQuotaExceeded`` so the pipeline
  can stop further calls in the same run
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import requests

from src.models.pacs008 import Pacs008Flavor


# No hardcoded default base URL: the user must configure their service
# endpoint via env var or the gitignored credentials folder.

ENV_DIR = "XML_VALIDATOR_DIR"
ENV_KEY = "XML_VALIDATOR_API_KEY"
ENV_BASE_URL = "XML_VALIDATOR_BASE_URL"

# Folders searched for credentials.
DEFAULT_CREDENTIAL_DIRS = ("xml_validator",)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class XmlValidatorError(Exception):
    """Base exception for the external XML validator client."""


class XmlValidatorAuthError(XmlValidatorError):
    """HTTP 401 Unauthorized."""


class XmlValidatorServerError(XmlValidatorError):
    """HTTP 5xx server error."""


class XmlValidatorConfigError(XmlValidatorError):
    """Credentials or configuration missing."""


class XmlValidatorQuotaExceeded(XmlValidatorError):
    """Service quota exhausted (e.g. trial limit)."""


# ---------------------------------------------------------------------------
# Validation Result
# ---------------------------------------------------------------------------

@dataclass
class ExternalValidationResult:
    """Result of an external XML validation call."""

    valid: bool
    status_code: int
    raw_response: str
    errors: List[str] = field(default_factory=list)
    flavor: Optional[str] = None
    endpoint: Optional[str] = None


# ---------------------------------------------------------------------------
# Credential Loader
# ---------------------------------------------------------------------------

def _read_text_file(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError):
        return None


def load_credentials(credential_dir: Optional[str] = None) -> tuple:
    """Loads API key and base URL.

    Priority:
    1. ENV variables ``XML_VALIDATOR_API_KEY`` + ``XML_VALIDATOR_BASE_URL``
    2. Files in the explicit ``credential_dir`` (or ``XML_VALIDATOR_DIR``)
    3. Files in the default credential dir ``xml_validator/`` (gitignored)

    Returns:
        (api_key, base_url) -- both required.

    Raises:
        XmlValidatorConfigError when key or base URL cannot be found.
    """
    api_key = os.environ.get(ENV_KEY)
    base_url = os.environ.get(ENV_BASE_URL)

    search_dirs: List[Path] = []
    if credential_dir:
        search_dirs.append(Path(credential_dir))
    elif env_dir := os.environ.get(ENV_DIR):
        search_dirs.append(Path(env_dir))
    else:
        for candidate in DEFAULT_CREDENTIAL_DIRS:
            search_dirs.append(Path(candidate))

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        if not api_key:
            for f in sorted(search_dir.glob("api-key*.txt")):
                api_key = _read_text_file(f)
                if api_key:
                    break
        if not base_url:
            for f in sorted(search_dir.glob("base-url*.txt")):
                base_url = _read_text_file(f)
                if base_url:
                    break
        if api_key and base_url:
            break

    if not api_key:
        raise XmlValidatorConfigError(
            f"XML Validator API key not found. Set the env variable "
            f"{ENV_KEY} or place 'api-key*.txt' in one of "
            f"{', '.join(DEFAULT_CREDENTIAL_DIRS)}/ at the repo root."
        )
    if not base_url:
        raise XmlValidatorConfigError(
            f"XML Validator base URL not found. Set the env variable "
            f"{ENV_BASE_URL} or place 'base-url*.txt' in one of "
            f"{', '.join(DEFAULT_CREDENTIAL_DIRS)}/ at the repo root."
        )

    return api_key, base_url.rstrip("/")


# ---------------------------------------------------------------------------
# Endpoint Dispatch
# ---------------------------------------------------------------------------

def endpoint_for_flavor(flavor: Pacs008Flavor, sepa_scheme: str = "sct") -> str:
    """Returns the validation endpoint path for a pacs.008 flavor.

    V1 implements only CBPR+; the other flavors are prepared and raise
    NotImplementedError when called.
    """
    if flavor == Pacs008Flavor.CBPR_PLUS:
        return "/cbpr/validate"
    if flavor == Pacs008Flavor.TARGET2:
        return "/target2/validate"
    if flavor == Pacs008Flavor.SEPA:
        return f"/sepa/{sepa_scheme}/validate"
    raise NotImplementedError(
        f"XML Validator endpoint for flavor {flavor} is not defined."
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class XmlValidatorClient:
    """REST client for the external XML validator service."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        credential_dir: Optional[str] = None,
        timeout: float = 30.0,
    ):
        if api_key is None or base_url is None:
            key_from_file, url_from_file = load_credentials(credential_dir)
            self.api_key = api_key or key_from_file
            self.base_url = (base_url or url_from_file).rstrip("/")
        else:
            self.api_key = api_key
            self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def validate(
        self,
        xml: bytes,
        flavor: Pacs008Flavor = Pacs008Flavor.CBPR_PLUS,
    ) -> ExternalValidationResult:
        """Sends an XML message to the external validator.

        Args:
            xml: complete XML message bytes (BAH + Document for CBPR+)
            flavor: determines the API endpoint

        Returns:
            ExternalValidationResult with valid flag, status, and any errors

        Raises:
            XmlValidatorAuthError on 401
            XmlValidatorServerError on 5xx
            XmlValidatorQuotaExceeded on 'subscription.expired' bodies
            XmlValidatorError on network failure
        """
        endpoint = endpoint_for_flavor(flavor)
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "text/plain",
            "Accept": "*/*",
        }
        body = xml.decode("utf-8") if isinstance(xml, bytes) else xml

        try:
            response = requests.post(
                url, data=body, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as e:
            raise XmlValidatorError(
                f"Network error during XML validator call: {e}"
            ) from e

        return self._parse_response(response, flavor, endpoint)

    def _parse_response(
        self,
        response: requests.Response,
        flavor: Pacs008Flavor,
        endpoint: str,
    ) -> ExternalValidationResult:
        """Interprets the HTTP response and builds an ExternalValidationResult."""
        raw = response.text or ""

        if response.status_code == 401:
            raise XmlValidatorAuthError(
                f"XML Validator 401 Unauthorized. Body: {raw[:200]}"
            )
        if 500 <= response.status_code < 600:
            raise XmlValidatorServerError(
                f"XML Validator {response.status_code} server error. "
                f"Body: {raw[:200]}"
            )

        if response.status_code == 200:
            valid = "valid" in raw.lower() or response.status_code == 200
            return ExternalValidationResult(
                valid=valid,
                status_code=200,
                raw_response=raw,
                errors=[],
                flavor=flavor.value,
                endpoint=endpoint,
            )

        # Trial / subscription quota exhausted is signalled with body
        # 'subscription.expired' on a 4xx response. We treat this
        # separately from validation errors so the pipeline can stop
        # further calls in the same run.
        if "subscription.expired" in (raw or "").lower():
            raise XmlValidatorQuotaExceeded(
                "XML Validator service quota exhausted (subscription.expired). "
                "Skipping remaining calls in this run."
            )

        # 4xx => validation errors
        errors = _parse_error_body(raw)
        return ExternalValidationResult(
            valid=False,
            status_code=response.status_code,
            raw_response=raw,
            errors=errors,
            flavor=flavor.value,
            endpoint=endpoint,
        )


def _parse_error_body(body: str) -> List[str]:
    """Parses a 4xx response body into a list of error messages.

    Tries JSON first (list, or dict with common error-key names), then
    falls back to splitting the plain-text body line-by-line.
    """
    import json
    body = (body or "").strip()
    if not body:
        return []
    try:
        parsed = json.loads(body)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
        if isinstance(parsed, dict):
            for key in ("errors", "messages", "violations", "detail", "message"):
                if key in parsed:
                    val = parsed[key]
                    if isinstance(val, list):
                        return [str(x) for x in val]
                    return [str(val)]
            return [json.dumps(parsed)]
    except (json.JSONDecodeError, TypeError):
        pass
    return [line for line in body.splitlines() if line.strip()]
