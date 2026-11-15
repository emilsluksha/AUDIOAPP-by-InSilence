from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from .core import atomic_json, data_dir, resource


class History:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / 'history.json'
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            self.entries = value if isinstance(value, list) else []
        except (OSError, ValueError):
            self.entries = []

    def add(self, path: str, result: dict):
        compact = {key: value for key, value in result.items() if key not in ('spectrogram', 'spectrum', 'frequency')}
        self.entries.insert(0, {'id': uuid.uuid4().hex, 'file': path, 'date': datetime.now(timezone.utc).isoformat(), 'result': compact})
        self.entries = self.entries[:200]
        self.save()

    def remove(self, identifier: str):
        self.entries = [entry for entry in self.entries if entry['id'] != identifier]
        self.save()

    def clear(self):
        self.entries = []
        self.save()

    def save(self):
        atomic_json(self.path, self.entries)


class Translator:
    def __init__(self, language='en'):
        self.language = language
        self.catalogs = {name: json.loads(resource(f'localization/{name}.json').read_text(encoding='utf-8')) for name in ('en', 'ru')}

    def __call__(self, key: str) -> str:
        return self.catalogs[self.language].get(key, key)
