import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["FLASHCARDS_HOME"] = tempfile.mkdtemp()

import cards as core  # noqa: E402


class ParseTableTests(unittest.TestCase):
    def test_markdown_table_from_gemini(self):
        text = """Here are your flashcards:

```markdown
| front | back | note |
|---|---|---|
| **любовь** | love | Моя любовь к тебе |
| звезда | star | Звезда по имени Солнце |
```
Let me know if you want more!"""
        cards = core.parse_table(text)
        self.assertEqual([(c.front, c.back) for c in cards], [("любовь", "love"), ("звезда", "star")])
        self.assertEqual(cards[1].note, "Звезда по имени Солнце")

    def test_tab_separated_copy_from_web(self):
        text = "front\tback\tnote\nŞarkı\tsong\tBu şarkı senin için\nığdır\tIğdır\t\nİstanbul'u\tIstanbul (acc.)\t"
        cards = core.parse_table(text)
        self.assertEqual(len(cards), 3)
        self.assertEqual(cards[0].front, "Şarkı")
        self.assertEqual(cards[0].note, "Bu şarkı senin için")
        self.assertEqual(cards[2].front, "İstanbul'u")

    def test_csv_semicolon_and_comma(self):
        self.assertEqual(core.parse_table("слово;перевод\nдом;house\nкот;cat")[1].front, "кот")
        cards = core.parse_table('gül,rose\n"göz, gözler",eye(s)')
        self.assertEqual(cards[1].front, "göz, gözler")

    def test_rows_without_back_are_skipped(self):
        self.assertEqual(len(core.parse_table("a\tb\nonly-front\n\t\nc\td")), 2)

    def test_header_not_detected_for_real_cards(self):
        self.assertEqual(core.parse_table("дом\thouse")[0].front, "дом")


class FileTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self):
        deck = [core.Card("ёлка", "fir tree", "line, with comma"), core.Card("çiçek", "flower")]
        path = core.save_deck("Песня / Şarkı", deck)
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertEqual(core.load_deck(path), deck)
        self.assertIn(path, core.list_decks())

    def test_utf16_file(self):
        p = Path(core.DATA_DIR) / "u16.txt"
        p.write_text("ağaç\ttree\n", encoding="utf-16")
        self.assertEqual(core.load_file(p)[0].front, "ağaç")

    def test_non_utf8_file_gives_clear_error(self):
        p = Path(core.DATA_DIR) / "cp1251.csv"
        p.write_bytes("дом;house\n".encode("cp1251"))
        with self.assertRaises(ValueError):
            core.load_file(p)

    def test_xlsx(self):
        p = Path(core.DATA_DIR) / "t.xlsx"
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("xl/sharedStrings.xml", f'<sst {ns}><si><t>front</t></si><si><t>back</t></si>'
                       f'<si><t>сердце</t></si><si><t>heart</t></si></sst>')
            z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData>'
                       '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                       '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c>'
                       '<c r="D2" t="inlineStr"><is><t>kalp</t></is></c></row>'
                       '</sheetData></worksheet>')
        cards = core.load_file(p)
        self.assertEqual(cards, [core.Card("сердце", "heart", "kalp")])


class PromptTests(unittest.TestCase):
    def test_prompt_contains_lyrics_and_languages(self):
        p = core.build_prompt("Gel gel\n", "Turkish", "German", 10)
        self.assertIn("Gel gel", p)
        self.assertIn("Turkish", p)
        self.assertIn("German", p)
        self.assertIn("| front | back | note |", p)

    def test_missing_key(self):
        with self.assertRaises(core.GeminiError):
            core.ask_gemini("hi", "")


if __name__ == "__main__":
    unittest.main()
