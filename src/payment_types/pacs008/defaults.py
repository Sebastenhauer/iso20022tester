"""Zentralisierte Default-Werte fuer pacs.008 (CBPR+ Flavor in V1).

Alle Felder, die der User nicht explizit im Excel setzt, bekommen
hier ihren Default. User-Overrides (Spalten + "Weitere Testdaten")
haben immer Vorrang.

Entscheidungen aus der Planungsphase:
- SttlmMtd Default: INDA (Instructed Agent settles). Neben COVE der
  gaengigste Modus in CBPR+; COVE ist in V1 out of scope.
- ChrgBr Default: SHAR (geteilte Kosten). Der User kann DEBT/CRED
  einfach per Excel-Spalte ueberschreiben.
- IntrBkSttlmDt Default: T+1 Banktag (TARGET2-Kalender fuer
  EUR-Zahlungen, CH-Kalender sonst).
- InstgAgt/InstdAgt Default: KEIN Default. Wenn der User nichts
  mitgibt, bleiben diese None und die Validierung (WP-06) meldet
  BR-CBPR-PACS-002/003 als Fehler. Begruendung: diese BICs sind
  zahlungs-spezifisch und koennen nicht sinnvoll pauschal gesetzt
  werden (User-Entscheid #9 in der Planungssession).
- ChrgsInf Default: LEER. Keine automatisch generierten ChrgsInf-
  Eintraege (User-Entscheid #8). Wenn der User einen einzelnen
  ChrgsInf-Eintrag via Dot-Notation oder Zukunfts-Spalten erstellen
  will, bleibt das explizit.
- Intermediary-Agent Default: GENAU EINER, aus `DEFAULT_INTERMEDIARY_1`,
  wenn User keinen explizit setzt (User-Entscheid #6).
  Die konkrete BIC ist bewusst ein Platzhalter ohne Live-Routing-
  Bedeutung und sollte fuer realistische Testcases ueberschrieben
  werden.
- BAH Defaults: MsgDefIdr=pacs.008.001.08, BizSvc=swift.cbprplus.02
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

# ---------------------------------------------------------------------------
# Settlement
# ---------------------------------------------------------------------------

DEFAULT_SETTLEMENT_METHOD = "INDA"
DEFAULT_SETTLEMENT_DATE_OFFSET_DAYS = 1  # T+1

# Currencies for which we use TARGET2 calendar (vs Switzerland)
TARGET2_CURRENCIES = {"EUR"}

# ---------------------------------------------------------------------------
# Charges
# ---------------------------------------------------------------------------

DEFAULT_CHARGE_BEARER = "SHAR"
# Kein Default fuer ChrgsInf-Liste. Wenn der User nichts mitgibt,
# bleibt die Liste leer und BR-CBPR-PACS-012 prueft, ob das konsistent
# mit ChrgBr=SHAR ist (SHAR ohne ChrgsInf ist erlaubt, DEBT/CRED ohne
# ChrgsInf typischerweise auch).

# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

# Keine globalen Defaults fuer InstgAgt / InstdAgt / DbtrAgt / CdtrAgt.
# Diese muessen pro Testcase aus dem Excel kommen.

# Ein (1) Intermediary Agent wird gesetzt, wenn der User keinen
# explizit angibt. Der Platzhalter ist ein echtes Major-Bank-BIC,
# darf aber zur Laufzeit vom User ueberschrieben werden.
DEFAULT_INTERMEDIARY_1_BIC = "CHASUS33XXX"  # JPMorgan Chase, NY (USD-Korrespondent)

# ---------------------------------------------------------------------------
# BAH (head.001.001.02)
# ---------------------------------------------------------------------------

BAH_MSG_DEF_IDR = "pacs.008.001.08"
BAH_BIZ_SVC = "swift.cbprplus.02"


# ---------------------------------------------------------------------------
# Settlement Date Resolver
# ---------------------------------------------------------------------------

def resolve_settlement_date(
    currency: str,
    base: Optional[date] = None,
    offset_days: int = DEFAULT_SETTLEMENT_DATE_OFFSET_DAYS,
) -> date:
    """Bestimmt `IntrBkSttlmDt` unter Beruecksichtigung von Banktagen.

    Args:
        currency: ISO 4217 Currency Code (EUR -> TARGET2, sonst CH)
        base: Start-Datum (default: heute)
        offset_days: Anzahl Bankarbeitstage ab `base` (default: +1)

    Returns:
        Ein ``date``-Objekt, das ``offset_days`` Banktage nach ``base`` liegt.
        Bei ImportError wird per Fallback nur auf Werktage (Mo-Fr)
        geprueft.
    """
    if base is None:
        base = date.today()

    try:
        if currency in TARGET2_CURRENCIES:
            from workalendar.europe import EuropeanCentralBank
            cal = EuropeanCentralBank()
        else:
            from workalendar.europe import Switzerland
            cal = Switzerland()
        return cal.add_working_days(base, offset_days)
    except ImportError:
        # Fallback: naiver Mo-Fr-Check
        current = base + timedelta(days=1)
        remaining = offset_days - 1
        while current.weekday() >= 5 or remaining > 0:
            current += timedelta(days=1)
            if current.weekday() < 5:
                remaining -= 1
                if remaining < 0:
                    break
        return current


def resolve_settlement_date_str(
    currency: str,
    base: Optional[date] = None,
    offset_days: int = DEFAULT_SETTLEMENT_DATE_OFFSET_DAYS,
) -> str:
    """Wie ``resolve_settlement_date`` aber gibt ISO-8601 String zurueck."""
    return resolve_settlement_date(currency, base, offset_days).isoformat()


# ---------------------------------------------------------------------------
# Apply-Defaults Helper
# ---------------------------------------------------------------------------

def apply_defaults_to_testcase(tc) -> None:
    """Wendet Defaults auf ein Pacs008TestCase-Objekt IN PLACE an.

    Nur Felder, die `None` sind, werden gefuellt. Felder, die der User
    explizit im Excel gesetzt hat, bleiben unberuehrt.

    Args:
        tc: ein Pacs008TestCase-Objekt

    Mutiert:
        - ``charge_bearer`` -> ``SHAR`` wenn None
        - ``settlement_method`` bleibt (ist im Modell schon auf INDA default)
        - ``interbank_settlement_date`` -> T+1 Banktag wenn None
        - ``intermediary_agent_1_bic`` -> DEFAULT_INTERMEDIARY_1_BIC
          wenn alle Intermediary-Felder None sind UND flavor=CBPR+
    """
    from src.models.pacs008 import Pacs008Flavor

    if tc.charge_bearer is None:
        tc.charge_bearer = DEFAULT_CHARGE_BEARER

    if tc.interbank_settlement_date is None:
        currency = tc.currency or "EUR"
        tc.interbank_settlement_date = resolve_settlement_date_str(currency)

    # Intermediary nur setzen, wenn (a) CBPR+ und (b) keiner der drei
    # Intermediary-Slots vom User befuellt wurde.
    if tc.flavor == Pacs008Flavor.CBPR_PLUS:
        none_intermediary = (
            tc.intermediary_agent_1_bic is None
            and tc.intermediary_agent_1_clr_sys_mmb_id is None
            and tc.intermediary_agent_2_bic is None
            and tc.intermediary_agent_3_bic is None
        )
        if none_intermediary:
            tc.intermediary_agent_1_bic = DEFAULT_INTERMEDIARY_1_BIC
