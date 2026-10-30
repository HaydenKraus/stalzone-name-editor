"""Чтение и сохранение .lang-файлов STALZONE с сохранением форматирования."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from categories import categorize


@dataclass
class Entry:
    line_index: int
    key: str
    value: str
    original: str
    kind: str
    category: str


class LangFile:
    """Один файл локализации.

    Файл хранится построчно, поэтому при сохранении меняются только значения
    отредактированных строк: комментарии, пустые строки, порядок и переводы
    строк остаются как были.
    """

    def __init__(self, path: str | Path, pack: str = "") -> None:
        self.path = Path(path)
        self.pack = pack
        self.entries: list[Entry] = []
        self._prefixes: dict[int, str] = {}
        self._load()

    def _load(self) -> None:
        raw = self.path.read_bytes()
        self.has_bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        self.lines = text.splitlines(keepends=True)

        for index, line in enumerate(self.lines):
            body = line.rstrip("\r\n")
            if not body or body.lstrip().startswith("#"):
                continue
            key_part, sep, value = body.partition("=")
            if not sep:
                continue
            key = key_part.strip()
            if not key:
                continue
            self._prefixes[index] = body[: len(body) - len(value)]
            self.entries.append(
                Entry(
                    line_index=index,
                    key=key,
                    value=value,
                    original=value,
                    kind=key.rsplit(".", 1)[-1] if "." in key else "",
                    category=categorize(key, self.pack),
                )
            )

    @property
    def lang(self) -> str:
        return self.path.stem

    @property
    def dirty(self) -> bool:
        return any(entry.value != entry.original for entry in self.entries)

    def get(self, entry: Entry) -> str:
        return entry.value

    def set_value(self, entry: Entry, value: str) -> None:
        if "\n" in value or "\r" in value:
            raise ValueError("Название не должно содержать перевод строки")
        if value == entry.value:
            return
        ending = self.lines[entry.line_index][
            len(self.lines[entry.line_index].rstrip("\r\n")) :
        ]
        self.lines[entry.line_index] = self._prefixes[entry.line_index] + value + ending
        entry.value = value

    def revert(self, entry: Entry) -> None:
        self.set_value(entry, entry.original)

    def reset_all(self) -> None:
        for entry in self.entries:
            self.set_value(entry, entry.original)

    def copy_to(self, destination: str | Path) -> Path:
        """Скопировать файл по указанному пути, создав папки при необходимости."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.path, destination)
        return destination

    def create_backup(self, backup_dir: str | Path) -> Path:
        """Скопировать текущий файл в папку резервных копий."""
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{self.pack.replace('/', '_')}_{self.lang}_{stamp}"
        backup = backup_dir / f"{base}.lang"
        counter = 1
        while backup.exists():
            backup = backup_dir / f"{base}-{counter}.lang"
            counter += 1
        return self.copy_to(backup)

    def save(self, backup_dir: str | Path) -> Path | None:
        """Сохранить изменения. Вернуть путь резервной копии или None."""
        if not self.dirty:
            return None

        backup = self.create_backup(backup_dir)

        text = "".join(self.lines)
        data = text.encode("utf-8")
        if self.has_bom:
            data = b"\xef\xbb\xbf" + data

        temp = self.path.with_name(self.path.name + ".tmp")
        temp.write_bytes(data)
        temp.replace(self.path)

        for entry in self.entries:
            entry.original = entry.value
        return backup
