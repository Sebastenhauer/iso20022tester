"""FINaplo API Client (Payment Components).

Thin REST Wrapper um die FINaplo Financial Messaging APIs.

Authentifizierung: Bearer-Token aus der gitignored ``finaplo/``
Ordner-Struktur am Repo-Root:
- ``finaplo/api-key-<date>.txt`` enthaelt den Token
- ``finaplo/base-url-<date>.txt`` enthaelt die Base-URL (LIVE oder Sandbox)

Endpoint-Dispatch je Pacs008-Flavor:
- ``CBPR+``   -> POST ``/cbpr/validate``
- ``TARGET2`` -> POST ``/target2/validate`` (future)
- ``SEPA``    -> POST ``/sepa/{sepaScheme}/validate`` (future)

Response-Formate (laut Swagger):
- ``200 OK``: Plain-Text ``"Message is valid"`` (oder aehnlich)
- ``400``: Detaillierte Fehler (JSON oder Text)
- ``401``: Auth-Fehler
- ``500``: Server-Fehler
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import requests

from src.models.pacs008 import Pacs008Flavor


DEFAULT_LIVE_BASE_URL = "https://finaplo-apis.paymentcomponents.com"
DEFAULT_SANDBOX_BASE_URL = "https://finaplo-apis.paymentcomponents.com/sandbox"

FINAPLO_DIR_ENV = "FINAPLO_DIR"
FINAPLO_KEY_ENV = "FINAPLO_API_KEY"
FINAPLO_BASE_URL_ENV = "FINAPLO_BASE_URL"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class FinaploError(Exception):
    """Basis-Exception fuer FINaplo Client."""


class FinaploAuthError(FinaploError):
    """401 Unauthorized."""


class FinaploServerError(FinaploError):
    """5xx Server-Fehler."""


class FinaploConfigError(FinaploError):
    """Credentials oder Config fehlen."""


# ---------------------------------------------------------------------------
# Validation Result
# ---------------------------------------------------------------------------

@dataclass
class FinaploResult:
    """Ergebnis einer FINaplo Validation."""

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


def load_credentials(finaplo_dir: Optional[str] = None) -> tuple:
    """Liest API-Key und Base-URL aus dem ``finaplo/`` Ordner.

    Priorities:
    1. ENV-Variablen ``FINAPLO_API_KEY`` + ``FINAPLO_BASE_URL``
    2. Dateien im uebergebenen ``finaplo_dir`` (oder ``FINAPLO_DIR``)
       oder Default ``finaplo/`` am CWD
       - ``api-key*.txt``
       - ``base-url*.txt``
    3. Fallback ``DEFAULT_LIVE_BASE_URL`` als Base-URL (Key bleibt Pflicht)

    Returns:
        (api_key, base_url)

    Raises:
        FinaploConfigError wenn kein Key gefunden wird.
    """
    api_key = os.environ.get(FINAPLO_KEY_ENV)
    base_url = os.environ.get(FINAPLO_BASE_URL_ENV)

    search_dir = Path(finaplo_dir or os.environ.get(FINAPLO_DIR_ENV, "finaplo"))
    if search_dir.is_dir():
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

    if not api_key:
        raise FinaploConfigError(
            f"FINaplo API-Key nicht gefunden. Erwartet wird entweder "
            f"die ENV-Variable {FINAPLO_KEY_ENV} oder eine Datei "
            f"'api-key*.txt' im Ordner {search_dir}."
        )

    base_url = base_url or DEFAULT_LIVE_BASE_URL
    base_url = base_url.rstrip("/")

    return api_key, base_url


# ---------------------------------------------------------------------------
# Endpoint Dispatch
# ---------------------------------------------------------------------------

def endpoint_for_flavor(flavor: Pacs008Flavor, sepa_scheme: str = "sct") -> str:
    """Liefert den relativen Pfad fuer Validation je Flavor.

    V1 implementiert nur CBPR+; die anderen Flavors sind vorbereitet
    und werfen bei Aufruf (noch) einen NotImplementedError.
    """
    if flavor == Pacs008Flavor.CBPR_PLUS:
        return "/cbpr/validate"
    if flavor == Pacs008Flavor.TARGET2:
        return "/target2/validate"
    if flavor == Pacs008Flavor.SEPA:
        return f"/sepa/{sepa_scheme}/validate"
    raise NotImplementedError(f"FINaplo endpoint fuer Flavor {flavor} nicht definiert.")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class FinaploClient:
    """REST Client fuer FINaplo Validation APIs."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        finaplo_dir: Optional[str] = None,
        timeout: float = 30.0,
    ):
        if api_key is None or base_url is None:
            key_from_file, url_from_file = load_credentials(finaplo_dir)
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
    ) -> FinaploResult:
        """Sendet eine XML-Nachricht an den FINaplo Validator.

        Args:
            xml: Die komplette XML-Nachricht als Bytes (BAH + Document).
            flavor: Bestimmt den API-Endpoint.

        Returns:
            FinaploResult mit valid-Flag, Status und parsierten Errors.

        Raises:
            FinaploAuthError bei 401
            FinaploServerError bei 5xx
            FinaploError bei Netzwerk-Fehlern
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
            raise FinaploError(f"Netzwerk-Fehler beim FINaplo-Call: {e}") from e

        return self._parse_response(response, flavor, endpoint)

    def _parse_response(
        self,
        response: requests.Response,
        flavor: Pacs008Flavor,
        endpoint: str,
    ) -> FinaploResult:
        """Interpretiert die HTTP-Response und baut ein FinaploResult."""
        raw = response.text or ""

        if response.status_code == 401:
            raise FinaploAuthError(
                f"FINaplo 401 Unauthorized. Body: {raw[:200]}"
            )
        if 500 <= response.status_code < 600:
            raise FinaploServerError(
                f"FINaplo {response.status_code} Server-Fehler. Body: {raw[:200]}"
            )

        if response.status_code == 200:
            valid = "valid" in raw.lower() or response.status_code == 200
            return FinaploResult(
                valid=valid,
                status_code=200,
                raw_response=raw,
                errors=[],
                flavor=flavor.value,
                endpoint=endpoint,
            )

        # 400-499 => Validation-Fehler
        errors = _parse_error_body(raw)
        return FinaploResult(
            valid=False,
            status_code=response.status_code,
            raw_response=raw,
            errors=errors,
            flavor=flavor.value,
            endpoint=endpoint,
        )


def _parse_error_body(body: str) -> List[str]:
    """Parst ein 400-Response-Body zu einer Liste von Fehlermeldungen.

    FINaplo liefert unterschiedliche Formate (Plain-Text oder JSON). Wir
    versuchen zuerst JSON, dann splitten wir nach Zeilen.
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
            # Heuristik: haeufige Key-Namen
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
