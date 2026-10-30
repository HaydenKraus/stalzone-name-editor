from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from categories import CATEGORY_ORDER, categorize  # noqa: E402
from detect import find_lang_files  # noqa: E402
from langfile import LangFile  # noqa: E402

GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\STALZONE")


class CategoryTests(unittest.TestCase):
    def test_item_types(self):
        cases = {
            "item.wpn.aksu.name": "Оружие",
            "item.arm.kyrtka.name": "Броня",
            "item.melee.knife.name": "Ближний бой",
            "item.exp.kustarnik.name": "Гранаты и взрывчатка",
            "item.amm.akumulator.name": "Патроны",
            "item.att.scope_hamr.name": "Обвесы",
            "item.wpn_mod.adv.name": "Модификации оружия",
            "item.art.medusa.name": "Артефакты",
            "item.med.aptechka.name": "Медикаменты",
            "item.food.tushonka.name": "Еда",
            "item.bag.big.name": "Рюкзаки и сумки",
            "item.quest.covenant.name": "Квестовые",
            "item.ny_toys.setA.name": "Событийные",
            "item.16519.name": "Квестовые",
        }
        for key, expected in cases.items():
            with self.subTest(key=key):
                self.assertEqual(categorize(key), expected)

    def test_interface_types(self):
        cases = {
            "general.options.boolean.foo": "Настройки",
            "stalker.hud.hint": "HUD и PDA",
            "pda.waypoint.we.foo": "HUD и PDA",
            "shop.tabs.weapons": "Магазин и экономика",
            "general.achievement.id.foo": "Достижения и гайды",
            "gui.pause.settings.title": "Настройки",
            "stalker.inv_view.grid": "Инвентарь и экипировка",
            "stalker.gui.inventory.title": "Интерфейс",
            "weapon.tooltip.weapon.foo": "Оружие",
            "quote.ziv.foo": "Цитаты и лор",
            "go.misc.foo": "Объекты мира",
            "checkpoints.dungeon.foo": "Локации и мир",
            "cnps.dialog.foo": "NPC и фракции",
            "quest_contract.foo.bar": "Задания и операции",
            "frontline.wave.foo": "PvP и режимы",
            "hideout.feature.foo": "Убежище",
            "clans.tournament.foo": "Кланы",
            "phonograph.vinyl.foo": "Пластинки",
            "key.binding.foo": "Управление",
        }
        for key, expected in cases.items():
            with self.subTest(key=key):
                pack = "gloomycore" if expected == "Интерфейс" else "stalker"
                self.assertEqual(categorize(key, pack), expected)

    def test_all_categories_are_ordered(self):
        for key in ("item.wpn.x.name", "gui.x.title", "unknown.key"):
            self.assertIn(categorize(key), CATEGORY_ORDER)


class LangFileTests(unittest.TestCase):
    def test_roundtrip_preserves_formatting(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            path = tmp_path / "ru.lang"
            path.write_bytes(
                b"# comment\r\n"
                b"item.wpn.aksu.name=AKSU\r\n"
                b"\r\n"
                b"item.wpn.aksu.description=A=B\r\n"
                b"gui.title=No newline"
            )

            lf = LangFile(path, "stalker")
            self.assertEqual(len(lf.entries), 3)
            self.assertFalse(lf.dirty)

            name = next(e for e in lf.entries if e.key == "item.wpn.aksu.name")
            lf.set_value(name, "AKSU Test")
            self.assertTrue(lf.dirty)

            backup = lf.save(tmp_path / "backups")
            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            self.assertFalse(lf.dirty)

            self.assertEqual(
                path.read_bytes(),
                b"# comment\r\n"
                b"item.wpn.aksu.name=AKSU Test\r\n"
                b"\r\n"
                b"item.wpn.aksu.description=A=B\r\n"
                b"gui.title=No newline",
            )

    def test_duplicate_keys_edit_only_selected_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ru.lang"
            path.write_text(
                "item.wpn.x.name=First\nitem.wpn.x.name=Second\n", encoding="utf-8"
            )
            lf = LangFile(path, "stalker")
            self.assertEqual(len(lf.entries), 2)
            lf.set_value(lf.entries[1], "Changed")
            lf.save(Path(tmp) / "backups")
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "item.wpn.x.name=First\nitem.wpn.x.name=Changed\n",
            )

    def test_create_backup_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ru.lang"
            path.write_text("item.wpn.x.name=X\n", encoding="utf-8")
            lf = LangFile(path, "stalker")
            backup = lf.create_backup(Path(tmp) / "backups")
            self.assertTrue(backup.is_file())
            self.assertEqual(backup.read_bytes(), path.read_bytes())
            second = lf.create_backup(Path(tmp) / "backups")
            self.assertNotEqual(backup, second)

    def test_copy_to_custom_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ru.lang"
            path.write_text("item.wpn.x.name=X\n", encoding="utf-8")
            lf = LangFile(path, "stalker")
            destination = Path(tmp) / "my backups" / "Моя копия.lang"
            backup = lf.copy_to(destination)
            self.assertEqual(backup, destination)
            self.assertEqual(destination.read_bytes(), path.read_bytes())

    def test_bom_and_crlf_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ru.lang"
            path.write_bytes(b"\xef\xbb\xbfitem.arm.x.name=\xd0\x91\xd1\x80\xd0\xbe\xd0\xbd\xd1\x8f\r\n")
            lf = LangFile(path, "stalker")
            lf.set_value(lf.entries[0], "Броня")
            lf.save(Path(tmp) / "backups")
            self.assertEqual(
                path.read_bytes(),
                b"\xef\xbb\xbfitem.arm.x.name=\xd0\x91\xd1\x80\xd0\xbe\xd0\xbd\xd1\x8f\r\n",
            )


class DetectTests(unittest.TestCase):
    def test_find_lang_files_in_fake_game(self):
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp)
            files = [
                game / "modassets/assets/stalker/lang/ru.lang",
                game / "modassets/assets/stalker/lang/en.lang",
                game / "modassets/assets/gloomycore/lang/ru.lang",
                game / "modassets/assets/_jurisdiction/korea/stalker/lang/ru.lang",
                game / "mods/mymod/lang/ru.lang",
            ]
            for path in files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("item.wpn.x.name=X\n", encoding="utf-8")

            sources = find_lang_files(game)
            self.assertEqual(len(sources), 5)
            self.assertEqual(sources[0].pack, "stalker")
            self.assertEqual(sources[0].lang, "ru")
            packs = {s.pack for s in sources}
            self.assertEqual(
                packs,
                {"stalker", "gloomycore", "_jurisdiction/korea/stalker", "mods/mymod"},
            )

    @unittest.skipUnless(GAME.is_dir(), "STALZONE не установлена")
    def test_real_game_files(self):
        sources = find_lang_files(GAME)
        self.assertGreaterEqual(len(sources), 10)
        ru = [s for s in sources if s.pack == "stalker" and s.lang == "ru"]
        self.assertEqual(len(ru), 1)
        lf = LangFile(ru[0].path, ru[0].pack)
        self.assertGreater(len(lf.entries), 20000)
        self.assertTrue(any(e.key == "item.wpn.aksu.name" for e in lf.entries))


if __name__ == "__main__":
    unittest.main()
