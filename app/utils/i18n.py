from pathlib import Path
from typing import Any

import yaml


class MessageCatalog:
    """Small YAML-backed translation helper."""

    def __init__(self, messages_path: Path, default_language: str = "fa") -> None:
        self.default_language = default_language
        with messages_path.open(encoding="utf-8") as file:
            loaded = yaml.safe_load(file) or {}
        self._messages: dict[str, Any] = loaded

    @property
    def languages(self) -> list[str]:
        return sorted(self._messages.keys())

    def normalize_language(self, language_code: str | None) -> str:
        return self.default_language

    def t(self, language: str | None, key: str, **kwargs: object) -> str:
        normalized = self.normalize_language(language)
        value = self._resolve(normalized, key)
        if value is None and normalized != self.default_language:
            value = self._resolve(self.default_language, key)
        if value is None:
            return key
        if not isinstance(value, str):
            return str(value)
        return value.format(**kwargs)

    def _resolve(self, language: str, key: str) -> object | None:
        current: object = self._messages.get(language, {})
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current


def load_feature_flags(features_path: Path) -> dict[str, Any]:
    with features_path.open(encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}
    if not isinstance(loaded, dict):
        return {}
    return loaded
