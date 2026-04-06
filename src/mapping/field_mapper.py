"""Deterministisches Key→XPath Mapping für Overrides aus 'Weitere Testdaten'."""

from typing import Dict, List, Optional, Tuple

from src.mapping.mapping_table import FIELD_MAPPINGS, SPECIAL_KEYS, TAG_TO_KEYS, get_valid_keys

# Benutzerfreundliche Aliasse fuer ChrgBr-Werte
CHARGE_BEARER_ALIASES = {
    "OUR": "DEBT",
    "BEN": "CRED",
    "SHA": "SHAR",
}


def _normalize_charge_bearer(value: str) -> str:
    """Normalisiert ChrgBr-Werte: OUR→DEBT, BEN→CRED, SHA→SHAR."""
    upper = value.upper()
    return CHARGE_BEARER_ALIASES.get(upper, value)


class MappingError:
    def __init__(self, key: str, message: str, is_warning: bool = False):
        self.key = key
        self.message = message
        self.is_warning = is_warning  # True = übersprungen (Warnung), False = harter Fehler


def parse_key_value_pairs(text: str) -> Dict[str, str]:
    """Parst 'Key=Value; Key=Value' Freitext in ein Dictionary."""
    result = {}
    if not text or not text.strip():
        return result

    pairs = text.split(";")
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        result[key.strip()] = value.strip()

    return result


def _resolve_xml_tag(tag: str) -> Tuple[str, Optional[str]]:
    """Versucht einen XML-Tag-Namen zu einem FIELD_MAPPINGS-Key aufzulösen.

    Returns:
        Tuple von (resolved_key oder None, warning_message oder None).
        - Eindeutig: (key, None)
        - Mehrdeutig: (None, Warnung)
        - Unbekannt: (None, None)
    """
    candidates = TAG_TO_KEYS.get(tag)
    if not candidates:
        return None, None
    if len(candidates) == 1:
        return candidates[0], None
    # Mehrdeutig: Tag erscheint an mehreren Stellen im Schema
    keys_list = ", ".join(sorted(candidates))
    warning = (
        f"XML-Tag '{tag}' ist mehrdeutig (erscheint an mehreren Stellen im Schema: "
        f"{keys_list}). Eintrag wird übersprungen. "
        f"Bitte den vollständigen Key verwenden, z.B. '{candidates[0]}'."
    )
    return None, warning


def validate_and_map_overrides(
    overrides: Dict[str, str],
) -> Tuple[Dict[str, Dict], Dict[str, str], List[MappingError]]:
    """Validiert Override-Keys und gibt gemappte Felder zurück.

    Unterstützt drei Arten von Keys:
    1. FIELD_MAPPINGS-Keys (z.B. "Cdtr.Nm") → direktes Mapping
    2. XML-Tag-Namen (z.B. "ChrgBr", "InstdAmt") → automatische Auflösung
       wenn der Tag eindeutig ist (nur an einer Stelle im Schema vorkommt)
    3. SPECIAL_KEYS (z.B. "ViolateRule") → separate Verarbeitung

    Bei mehrdeutigen XML-Tags (z.B. "Nm" → Cdtr.Nm, Dbtr.Nm, ...) wird der
    Eintrag übersprungen und eine Warnung erzeugt.

    Returns:
        Tuple von:
        - mapped_fields: Dict[key, {"xpath": ..., "level": ..., "value": ...}]
        - special_fields: Dict[key, value] für ViolateRule, TxCount etc.
        - errors: Liste von MappingErrors für ungültige Keys oder Warnungen
    """
    mapped = {}
    special = {}
    errors = []

    for key, value in overrides.items():
        if key in SPECIAL_KEYS:
            special[key] = value
        elif key in FIELD_MAPPINGS:
            mapping = FIELD_MAPPINGS[key]
            # ChrgBr: Benutzerfreundliche Aliasse normalisieren (OUR→DEBT etc.)
            resolved_value = _normalize_charge_bearer(value) if key == "ChrgBr" else value
            mapped[key] = {
                "xpath": mapping["xpath"],
                "level": mapping["level"],
                "value": resolved_value,
            }
        else:
            # Versuch: XML-Tag-Name automatisch auflösen
            resolved_key, warning = _resolve_xml_tag(key)
            if resolved_key:
                # Eindeutig aufgelöst
                mapping = FIELD_MAPPINGS[resolved_key]
                resolved_value = (
                    _normalize_charge_bearer(value)
                    if resolved_key == "ChrgBr"
                    else value
                )
                mapped[resolved_key] = {
                    "xpath": mapping["xpath"],
                    "level": mapping["level"],
                    "value": resolved_value,
                }
            elif warning:
                # Mehrdeutig → überspringen mit Warnung (kein harter Fehler)
                errors.append(MappingError(key=key, message=warning, is_warning=True))
            else:
                # Weder bekannter Key noch bekannter XML-Tag
                valid_keys = get_valid_keys()
                errors.append(
                    MappingError(
                        key=key,
                        message=(
                            f"Unbekannter Override-Key '{key}'. "
                            f"Gültige Keys: {', '.join(valid_keys)}"
                        ),
                    )
                )

    return mapped, special, errors
