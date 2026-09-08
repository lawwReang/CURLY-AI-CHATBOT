from __future__ import annotations

import json
import re
from pathlib import Path


class InfoRepository:
    """Conservative speech/STT alias normalizer.

    This repository contains terminology variants, not institutional facts.
    The canonical value is always resolved against the authoritative
    institutional knowledge in data.json.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.aliases: dict[str, str] = {}

        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            raw_aliases = data.get("aliases", {})
            if isinstance(raw_aliases, dict):
                self.aliases = {
                    str(alias).strip().lower(): str(canonical).strip()
                    for alias, canonical in raw_aliases.items()
                    if str(alias).strip() and str(canonical).strip()
                }

        self._ordered_aliases = sorted(
            self.aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

    @staticmethod
    def _normalize_spaces(text: str) -> str:
        return " ".join(text.strip().split())

    @staticmethod
    def _boundary_pattern(alias: str) -> re.Pattern[str]:
        escaped = re.escape(alias)
        return re.compile(
            rf"(?<![a-z0-9]){escaped}(?![a-z0-9])",
            re.IGNORECASE,
        )

    def normalize(self, text: str) -> tuple[str, list[dict[str, str]]]:
        """Return canonicalized text and the aliases that were applied.

        Matching is deliberately phrase-based and conservative. We do not
        ask an LLM to invent corrections and we do not write anything back
        to the repository automatically.
        """
        normalized = self._normalize_spaces(text)
        matches: list[dict[str, str]] = []

        for alias, canonical in self._ordered_aliases:
            pattern = self._boundary_pattern(alias)

            if pattern.search(normalized):
                normalized = pattern.sub(canonical, normalized)
                matches.append(
                    {
                        "heard": alias,
                        "canonical": canonical,
                    }
                )

        normalized = self._normalize_spaces(normalized)

        # De-duplicate mappings while preserving order.
        unique_matches: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for item in matches:
            key = (item["heard"], item["canonical"])
            if key not in seen:
                seen.add(key)
                unique_matches.append(item)

        return normalized, unique_matches

    @staticmethod
    def format_matches(matches: list[dict[str, str]]) -> str:
        if not matches:
            return ""

        return "\n".join(
            f'- "{item["heard"]}" → "{item["canonical"]}"'
            for item in matches
        )
