"""Offline BIC-Verzeichnis-Validierung gegen SWIFT BIC Directory.

Lädt ein lokales BIC-Verzeichnis (CSV oder JSON) und prüft ob ein BIC
existiert und aktiv ist.

Konfigurierbar über config.yaml mit `bic_directory_path`.
Wenn kein Pfad konfiguriert ist, wird die Validierung übersprungen.
"""

import csv
import json
import os
from dataclasses import dataclass, field
from typing import Dict, Optional, Set


@dataclass(frozen=True)
class BICEntry:
    """Ein Eintrag aus dem SWIFT BIC Directory."""

    bic8: str  # 8-stelliger BIC (Institution Code)
    institution_name: str = ""
    country_code: str = ""
    is_active: bool = True


class BICDirectory:
    """Offline BIC-Verzeichnis für Validierung.

    Unterstützte Formate:
    - CSV: Spalten BIC8 (oder BIC), InstitutionName, CountryCode, Status
    - JSON: Liste von Objekten mit denselben Feldern

    Der BIC wird immer auf 8 Stellen normalisiert (11-stellige BICs
    werden auf die ersten 8 Zeichen gekürzt, da die letzten 3 Zeichen
    den Branch-Code darstellen).
    """

    def __init__(self):
        self._entries: Dict[str, BICEntry] = {}

    @staticmethod
    def normalize_bic(bic: str) -> str:
        """Normalisiert einen BIC auf 8 Stellen (uppercase)."""
        bic = bic.strip().upper()
        if len(bic) == 11:
            return bic[:8]
        return bic

    def load(self, file_path: str) -> int:
        """Lädt das BIC-Verzeichnis aus einer Datei.

        Args:
            file_path: Pfad zur CSV- oder JSON-Datei.

        Returns:
            Anzahl geladener Einträge.

        Raises:
            FileNotFoundError: Datei nicht gefunden.
            ValueError: Unbekanntes Dateiformat oder ungültige Daten.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"BIC-Verzeichnis nicht gefunden: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            return self._load_csv(file_path)
        elif ext == ".json":
            return self._load_json(file_path)
        else:
            raise ValueError(
                f"Unbekanntes Format für BIC-Verzeichnis: '{ext}' "
                f"(erwartet: .csv oder .json)"
            )

    def _load_csv(self, file_path: str) -> int:
        """Lädt BIC-Einträge aus einer CSV-Datei."""
        count = 0
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=self._detect_delimiter(file_path))
            headers = {h.strip().upper(): h for h in (reader.fieldnames or [])}

            bic_col = self._find_column(headers, ("BIC8", "BIC", "BICFI", "BIC_CODE"))
            name_col = self._find_column(headers, ("INSTITUTION_NAME", "INSTITUTIONNAME", "NAME", "INSTITUTION"))
            country_col = self._find_column(headers, ("COUNTRY_CODE", "COUNTRYCODE", "COUNTRY", "CTRY"))
            status_col = self._find_column(headers, ("STATUS", "IS_ACTIVE", "ACTIVE", "RECORD_STATUS"))

            if not bic_col:
                raise ValueError(
                    f"BIC-Spalte nicht gefunden in CSV. "
                    f"Verfügbare Spalten: {list(reader.fieldnames or [])}"
                )

            for row in reader:
                bic_raw = row.get(bic_col, "").strip().upper()
                if not bic_raw:
                    continue

                bic8 = self.normalize_bic(bic_raw)
                if len(bic8) != 8:
                    continue

                name = row.get(name_col, "").strip() if name_col else ""
                country = row.get(country_col, "").strip().upper() if country_col else ""

                is_active = True
                if status_col:
                    status_val = row.get(status_col, "").strip().upper()
                    is_active = status_val not in ("INACTIVE", "FALSE", "0", "N", "NO", "DELETED")

                self._entries[bic8] = BICEntry(
                    bic8=bic8,
                    institution_name=name,
                    country_code=country,
                    is_active=is_active,
                )
                count += 1

        return count

    def _load_json(self, file_path: str) -> int:
        """Lädt BIC-Einträge aus einer JSON-Datei."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("JSON BIC-Verzeichnis muss eine Liste von Objekten sein")

        count = 0
        for item in data:
            if not isinstance(item, dict):
                continue

            bic_raw = (
                item.get("bic8") or item.get("bic") or item.get("BIC8")
                or item.get("BIC") or item.get("BICFI") or ""
            ).strip().upper()

            if not bic_raw:
                continue

            bic8 = self.normalize_bic(bic_raw)
            if len(bic8) != 8:
                continue

            name = str(
                item.get("institution_name") or item.get("InstitutionName")
                or item.get("name") or ""
            ).strip()

            country = str(
                item.get("country_code") or item.get("CountryCode")
                or item.get("country") or ""
            ).strip().upper()

            is_active = True
            status_keys = ("status", "is_active", "Status")
            status_val = None
            for sk in status_keys:
                if sk in item:
                    status_val = item[sk]
                    break
            if status_val is not None:
                if isinstance(status_val, bool):
                    is_active = status_val
                elif isinstance(status_val, str):
                    is_active = status_val.strip().upper() not in (
                        "INACTIVE", "FALSE", "0", "N", "NO", "DELETED"
                    )

            self._entries[bic8] = BICEntry(
                bic8=bic8,
                institution_name=name,
                country_code=country,
                is_active=is_active,
            )
            count += 1

        return count

    def lookup(self, bic: str) -> Optional[BICEntry]:
        """Sucht einen BIC im Verzeichnis.

        Args:
            bic: 8- oder 11-stelliger BIC.

        Returns:
            BICEntry wenn gefunden, sonst None.
        """
        bic8 = self.normalize_bic(bic)
        return self._entries.get(bic8)

    def exists(self, bic: str) -> bool:
        """Prüft ob ein BIC im Verzeichnis existiert."""
        return self.lookup(bic) is not None

    def is_active(self, bic: str) -> bool:
        """Prüft ob ein BIC existiert und aktiv ist."""
        entry = self.lookup(bic)
        return entry is not None and entry.is_active

    def validate_bic(self, bic: str) -> tuple[bool, Optional[str]]:
        """Validiert einen BIC gegen das Verzeichnis.

        Returns:
            Tuple (valid, error_message).
            valid=True wenn BIC existiert und aktiv ist.
            error_message enthält Details bei Fehlern.
        """
        entry = self.lookup(bic)
        if entry is None:
            return False, f"BIC '{bic}' nicht im SWIFT BIC Directory gefunden"
        if not entry.is_active:
            return False, f"BIC '{bic}' ist im SWIFT BIC Directory als inaktiv markiert"
        return True, None

    @property
    def size(self) -> int:
        """Anzahl Einträge im Verzeichnis."""
        return len(self._entries)

    @staticmethod
    def _detect_delimiter(file_path: str) -> str:
        """Erkennt den CSV-Delimiter (Komma oder Semikolon)."""
        with open(file_path, "r", encoding="utf-8-sig") as f:
            first_line = f.readline()
        if ";" in first_line and "," not in first_line:
            return ";"
        if "\t" in first_line and "," not in first_line:
            return "\t"
        return ","

    @staticmethod
    def _find_column(headers: Dict[str, str], candidates: tuple) -> Optional[str]:
        """Findet eine Spalte anhand möglicher Namen."""
        for candidate in candidates:
            if candidate in headers:
                return headers[candidate]
        return None


# ---------------------------------------------------------------------------
# Singleton / Factory
# ---------------------------------------------------------------------------

_directory_instance: Optional[BICDirectory] = None


def load_bic_directory(file_path: str) -> BICDirectory:
    """Lädt das BIC-Verzeichnis und gibt eine BICDirectory-Instanz zurück.

    Wird als Singleton verwaltet — bei erneutem Aufruf mit gleichem Pfad
    wird die bestehende Instanz zurückgegeben.
    """
    global _directory_instance
    if _directory_instance is not None:
        return _directory_instance

    directory = BICDirectory()
    count = directory.load(file_path)
    _directory_instance = directory
    return directory


def get_bic_directory() -> Optional[BICDirectory]:
    """Gibt die aktuelle BICDirectory-Instanz zurück (oder None)."""
    return _directory_instance


def reset_bic_directory():
    """Setzt die Singleton-Instanz zurück (für Tests)."""
    global _directory_instance
    _directory_instance = None
