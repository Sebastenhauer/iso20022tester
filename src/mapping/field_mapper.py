"""Deterministisches Key→XPath Mapping für Overrides aus 'Weitere Testdaten'."""

from typing import Dict, List, Tuple

from src.mapping.mapping_table import FIELD_MAPPINGS, SPECIAL_KEYS, get_valid_keys


class MappingError:
    def __init__(self, key: str, message: str):
        self.key = key
        self.message = message


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


def validate_and_map_overrides(
    overrides: Dict[str, str],
) -> Tuple[Dict[str, Dict], Dict[str, str], List[MappingError]]:
    """Validiert Override-Keys und gibt gemappte Felder zurück.

    Returns:
        Tuple von:
        - mapped_fields: Dict[key, {"xpath": ..., "level": ..., "value": ...}]
        - special_fields: Dict[key, value] für ViolateRule, TxCount etc.
        - errors: Liste von MappingErrors für ungültige Keys
    """
    mapped = {}
    special = {}
    errors = []

    for key, value in overrides.items():
        if key in SPECIAL_KEYS:
            special[key] = value
        elif key in FIELD_MAPPINGS:
            mapping = FIELD_MAPPINGS[key]
            mapped[key] = {
                "xpath": mapping["xpath"],
                "level": mapping["level"],
                "value": value,
            }
        else:
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
