from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable
import json
import os
import sys
import tempfile

import numpy as np


class AudioError(Exception):
    """A localizable error code suitable for display."""


class Cancelled(AudioError):
    def __init__(self):
        super().__init__('cancelled')


class Progress:
    def __init__(self, callback: Callable[[int, str], None] | None = None):
        self.event = Event()
        self.callback = callback or (lambda value, stage: None)

    def check(self):
        if self.event.is_set():
            raise Cancelled()

    def update(self, value: int, stage: str):
        self.check()
        self.callback(value, stage)


@dataclass
class Audio:
    samples: np.ndarray
    rate: int
    path: str

    @property
    def duration(self) -> float:
        return len(self.samples) / self.rate


def resource(name: str) -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / name


def data_dir() -> Path:
    path = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'KEYWAVE'
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
