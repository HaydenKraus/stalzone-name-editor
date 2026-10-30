"""Автоопределение установленной игры и файлов локализации."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - только Windows
    winreg = None  # type: ignore

PACK_LABELS = {
    "stalker": "Предметы и мир",
    "gloomycore": "Интерфейс",
}

_PRIORITY = {"stalker": 0, "gloomycore": 1}


@dataclass(frozen=True)
class LangSource:
    path: Path
    pack: str
    lang: str

    @property
    def pack_label(self) -> str:
        if self.pack in PACK_LABELS:
            return PACK_LABELS[self.pack]
        if self.pack.startswith("_jurisdiction/"):
            return "Юрисдикция · " + self.pack.split("/", 1)[1]
        if self.pack.startswith("mods"):
            return "Моды · " + self.pack
        return self.pack

    @property
    def label(self) -> str:
        return f"{self.pack_label} · {self.lang}"


def _steam_roots() -> list[Path]:
    roots: list[Path] = []
    if winreg is not None:
        for hive, key_name, value_name in (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        ):
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    value, _ = winreg.QueryValueEx(key, value_name)
                if value:
                    roots.append(Path(value))
            except OSError:
                pass
    for env in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env)
        if base:
            roots.append(Path(base) / "Steam")
    return roots


def _steam_libraries(steam_root: Path) -> list[Path]:
    libraries = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return libraries
    for match in re.finditer(r'"path"\s+"([^"]+)"', text):
        path = Path(match.group(1).replace("\\\\", "\\"))
        if path not in libraries:
            libraries.append(path)
    return libraries


def _uninstall_locations() -> list[Path]:
    if winreg is None:
        return []
    found: list[Path] = []
    keys = (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    )
    for key_name in keys:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_name) as root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        sub = winreg.EnumKey(root, index)
                        with winreg.OpenKey(root, sub) as item:
                            name, _ = winreg.QueryValueEx(item, "DisplayName")
                            if "STALZONE" not in str(name).upper():
                                continue
                            location, _ = winreg.QueryValueEx(item, "InstallLocation")
                            if location:
                                found.append(Path(location))
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def _looks_like_game(path: Path) -> bool:
    return (path / "modassets" / "assets").is_dir() or (path / "bin_ru").is_dir()


def find_game_dirs() -> list[Path]:
    """Найти каталоги игры: Steam, лаунчер EXBO, реестр, типовые пути."""
    candidates: list[Path] = []

    for steam_root in _steam_roots():
        for library in _steam_libraries(steam_root):
            candidates.append(library / "steamapps" / "common" / "STALZONE")

    candidates.extend(_uninstall_locations())

    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates.append(Path(base) / "STALZONE")
            candidates.append(Path(base) / "Programs" / "STALZONE")
            candidates.append(Path(base) / "EXBO" / "runtime" / "stalcraft")

    candidates.extend(
        [
            Path(r"C:\EXBO\runtime\stalcraft"),
            Path(r"C:\Games\STALZONE"),
            Path(r"D:\Games\STALZONE"),
            Path(r"D:\STALZONE"),
        ]
    )

    result: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen or not resolved.is_dir() or not _looks_like_game(resolved):
            continue
        seen.add(key)
        result.append(resolved)
    return result


def _pack_name(path: Path) -> str:
    parts = path.parts
    if "assets" in parts:
        index = len(parts) - 1 - list(reversed(parts)).index("assets")
        pack_parts = parts[index + 1 : -2]  # без .../lang/<lang>.lang
        if pack_parts:
            return "/".join(pack_parts)
    if "mods" in parts:
        index = parts.index("mods")
        return "/".join(parts[index:-2])
    return path.parent.parent.name


def find_lang_files(game_dir: str | Path) -> list[LangSource]:
    """Найти все .lang в modassets, патчах и папке mods."""
    game_dir = Path(game_dir)
    roots = [game_dir / "modassets"]
    roots.extend(sorted(game_dir.glob("bin_*/patchassets")))
    if (game_dir / "mods").is_dir():
        roots.append(game_dir / "mods")

    sources: list[LangSource] = []
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.lang"):
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if str(resolved).lower() in seen:
                continue
            seen.add(str(resolved).lower())
            sources.append(LangSource(resolved, _pack_name(resolved), resolved.stem))

    sources.sort(
        key=lambda s: (
            _PRIORITY.get(s.pack, 2),
            s.pack,
            0 if s.lang == "ru" else 1,
            s.lang,
        )
    )
    return sources
