"""Prompt loader — filesystem + DB version fallback."""
from __future__ import annotations

from pathlib import Path

import structlog

log = structlog.get_logger()

_TEMPLATES_ROOT = Path(__file__).parent / "templates"

_LANG_SUFFIX = {
    "hi-IN": "hi",
    "en-IN": "en",
}


class PromptLoader:
    """
    Loads prompt templates from filesystem.
    Checks: templates/{version}/{key}_{lang}.txt
    Falls back to: templates/v1/{key}_{lang}.txt
    Language-agnostic templates (e.g. extractor_system.txt) have no suffix.
    """

    def __init__(self, db_session=None) -> None:
        self._db = db_session
        self._cache: dict[str, str] = {}

    def get(self, key: str, version: str, language: str = "hi-IN") -> str:
        lang_suffix = _LANG_SUFFIX.get(language, "hi")
        cache_key = f"{version}:{key}:{language}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Try versioned file with language suffix
        text = (
            self._load_file(_TEMPLATES_ROOT / version / f"{key}_{lang_suffix}.txt")
            or self._load_file(_TEMPLATES_ROOT / version / f"{key}.txt")
            or self._load_file(_TEMPLATES_ROOT / "v1" / f"{key}_{lang_suffix}.txt")
            or self._load_file(_TEMPLATES_ROOT / "v1" / f"{key}.txt")
        )

        if not text:
            log.warning("prompt_template_not_found", key=key, version=version, language=language)
            text = f"[Prompt {key} not found for version {version}]"

        self._cache[cache_key] = text
        return text

    def _load_file(self, path: Path) -> str | None:
        try:
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            log.warning("prompt_file_read_error", path=str(path), error=str(exc))
        return None

    def invalidate_cache(self) -> None:
        self._cache.clear()


# Module-level singleton
_loader = PromptLoader()


def get_prompt(key: str, version: str = "v1", language: str = "hi-IN") -> str:
    return _loader.get(key, version, language)
