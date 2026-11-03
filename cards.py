"""Flashcard data handling: parsing tables, storing decks, talking to Gemini.

Everything here is plain Python (no third-party packages) so the app runs on
any computer that has Python 3 installed.
"""

import csv
import io
import json
import os
import re
import unicodedata
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

DATA_DIR = Path(os.environ.get("FLASHCARDS_HOME", Path.home() / "Flashcards"))
DECKS_DIR = DATA_DIR / "decks"
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "song_language": "Russian",
    "target_language": "English",
    "max_cards": 30,
}

HEADER_WORDS = {
    "front", "back", "note", "notes", "word", "words", "phrase", "translation",
    "meaning", "example", "context", "line", "lyric", "lyrics", "question",
    "answer", "original", "term", "definition",
    "frontword", "wordtype", "type", "frontnote", "backnote",
    "vorderseite", "rückseite", "wort", "übersetzung", "bedeutung", "beispiel",
    "notiz", "zeile", "wortart",
    "слово", "перевод", "пример", "kelime", "çeviri", "anlam", "örnek",
}

COLUMNS = ["frontword", "wordtype", "frontnote", "back", "backnote"]

# Header names that can be mapped to a column. Old decks use front/back/note.
COLUMN_ALIASES = {
    "frontword": "frontword", "front": "frontword", "word": "frontword",
    "wordtype": "wordtype", "type": "wordtype", "wortart": "wordtype",
    "frontnote": "frontnote",
    "back": "back", "translation": "back",
    "backnote": "backnote", "note": "backnote", "notes": "backnote",
}


@dataclass
class Card:
    frontword: str
    wordtype: str = ""
    frontnote: str = ""
    back: str = ""
    backnote: str = ""

    def values(self):
        return [getattr(self, col) for col in COLUMNS]


# ---------------------------------------------------------------------------
# Parsing tables (CSV, TSV, Markdown tables, Excel files)
# ---------------------------------------------------------------------------

_MD_SEPARATOR = re.compile(r"^[\s|:\-]+$")


def _clean(cell):
    cell = cell.strip()
    # Gemini sometimes puts words in **bold** or `code` inside tables.
    cell = re.sub(r"^\*\*(.*)\*\*$", r"\1", cell)
    cell = re.sub(r"^`(.*)`$", r"\1", cell)
    return cell.replace("<br>", " ").strip()


def _split_rows(text):
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("```")]
    if not lines:
        return []

    pipe_lines = [ln for ln in lines if ln.strip().startswith("|")]
    if len(pipe_lines) >= max(1, len(lines) // 2):
        rows = []
        for ln in pipe_lines:
            if _MD_SEPARATOR.match(ln):
                continue
            ln = ln.strip()
            if ln.startswith("|"):
                ln = ln[1:]
            if ln.endswith("|"):
                ln = ln[:-1]
            rows.append(ln.split("|"))
        return rows

    body = "\n".join(lines)
    if "\t" in body:
        delimiter = "\t"
    else:
        try:
            delimiter = csv.Sniffer().sniff(body[:4000], delimiters=",;").delimiter
        except csv.Error:
            delimiter = ","
    return list(csv.reader(io.StringIO(body), delimiter=delimiter))


def _header_key(cell):
    return re.sub(r"[\s_\-]", "", cell.strip().lower().strip("*"))


def _is_header(row):
    words = [_header_key(c) for c in row[:2]]
    return bool(words) and all(w in HEADER_WORDS for w in words if w)


def _header_mapping(header):
    """Map column names to positions, or None if the header isn't fully understood."""
    mapping = {}
    for i, cell in enumerate(header):
        key = _header_key(cell)
        if not key:
            continue
        col = COLUMN_ALIASES.get(key)
        if col is None or col in mapping:
            return None
        mapping[col] = i
    if "frontword" not in mapping or "back" not in mapping:
        return None
    return mapping


def rows_to_cards(rows):
    rows = [[_clean(c) for c in row] for row in rows]
    rows = [r for r in rows if any(r)]
    mapping = None
    if rows and _is_header(rows[0]):
        mapping = _header_mapping(rows[0])
        rows = rows[1:]
    if mapping is None:
        if max((len(r) for r in rows), default=0) <= 3:
            # Old format without word type: front, back, note.
            mapping = {"frontword": 0, "back": 1, "backnote": 2}
        else:
            mapping = {col: i for i, col in enumerate(COLUMNS)}
    cards = []
    for r in rows:
        fields = {col: r[i] if i < len(r) else "" for col, i in mapping.items()}
        if not fields["frontword"] or not fields["back"]:
            continue
        cards.append(Card(**fields))
    return cards


def parse_table(text):
    """Turn pasted/loaded table text into cards.

    Accepts tab-separated text (what you get when copying a table from Gemini,
    Google Sheets or Excel), CSV with , or ; and Markdown tables. The columns
    are frontword, wordtype, frontnote, back, backnote. Tables with only two
    or three columns are read the old way: front, back, note.
    """
    return rows_to_cards(_split_rows(text))


def _word_key(word):
    # NFC so that "й" typed as one character and as и + combining breve count as the same word.
    return unicodedata.normalize("NFC", word.strip())


def merge_cards(existing, new):
    """Add new cards to a deck, skipping any whose frontword is already there.

    Only an identical frontword counts as a duplicate, so a phrase or sentence
    that merely contains a known word is still added. Returns (added, skipped).
    """
    seen = {_word_key(c.frontword) for c in existing}
    added, skipped = [], []
    for c in new:
        key = _word_key(c.frontword)
        if key in seen:
            skipped.append(c)
        else:
            seen.add(key)
            added.append(c)
    return added, skipped


def cards_to_tsv(cards):
    lines = ["\t".join(COLUMNS)]
    for c in cards:
        lines.append("\t".join(x.replace("\t", " ").replace("\n", " ") for x in c.values()))
    return "\n".join(lines)


def read_text_file(path):
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError(
            "This file is not saved as UTF-8, so Cyrillic/Turkish letters can't be read reliably.\n"
            "Please save it as 'CSV UTF-8' (Excel) or download it as CSV from Google Sheets."
        ) from None


def _xlsx_rows(path):
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        sheets = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))
        if not sheets:
            return []
        root = ElementTree.fromstring(z.read(sheets[0]))

    rows = []
    for row in root.iter(f"{{{ns['m']}}}row"):
        values = {}
        for c in row.findall("m:c", ns):
            col = 0
            for ch in re.match(r"[A-Z]+", c.get("r", "A")).group():
                col = col * 26 + ord(ch) - 64
            kind = c.get("t")
            if kind == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(f"{{{ns['m']}}}t"))
            else:
                v = c.find("m:v", ns)
                text = v.text if v is not None and v.text else ""
                if kind == "s" and text:
                    text = shared[int(text)]
            values[col - 1] = text
        if values:
            rows.append([values.get(i, "") for i in range(max(values) + 1)])
    return rows


def load_file(path):
    """Read cards from a .csv/.tsv/.txt/.md or .xlsx file."""
    if str(path).lower().endswith(".xlsx"):
        return rows_to_cards(_xlsx_rows(path))
    return parse_table(read_text_file(path))


# ---------------------------------------------------------------------------
# Decks on disk: one UTF-8 CSV file per deck in ~/Flashcards/decks
# ---------------------------------------------------------------------------

def safe_name(name):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip(" .")
    return name or "Deck"


def list_decks():
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(DECKS_DIR.glob("*.csv"), key=lambda p: p.stem.lower())


def deck_path(name):
    return DECKS_DIR / f"{safe_name(name)}.csv"


def save_deck(name, cards):
    DECKS_DIR.mkdir(parents=True, exist_ok=True)
    path = deck_path(name)
    # utf-8-sig adds a BOM so Excel opens Cyrillic/Turkish text correctly.
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for c in cards:
            w.writerow(c.values())
    return path


def load_deck(path):
    return load_file(path)


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    if os.environ.get("GEMINI_API_KEY") and not cfg["gemini_api_key"]:
        cfg["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
    return cfg


def save_config(cfg):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# AI prompt + Gemini API
# ---------------------------------------------------------------------------

def build_prompt(lyrics, song_language, target_language, max_cards=30):
    song_language = song_language.strip() or "the song's language"
    target_language = target_language.strip() or "English"
    return f"""You are helping me learn {song_language} vocabulary from song lyrics.
Create up to {max_cards} flashcards from the song text below.

Rules:
- One card per useful word or short phrase, in the order they appear in the song. Skip names and duplicates.
- Column "frontword": the word or phrase in {song_language}, spelled exactly as in the original script \
(keep Cyrillic letters and Turkish letters like ç ğ ı İ ö ş ü). If the song uses an inflected form, \
write the dictionary form first and the song's form in brackets.
- Column "wordtype": the word type in {target_language}, e.g. noun, verb, adjective, phrase.
- Column "frontnote": the short lyric line where it appears, in {song_language}.
- Column "back": the {target_language} translation.
- Column "backnote": the {target_language} translation of that lyric line.
- Answer with ONLY a Markdown table with exactly the header \
| frontword | wordtype | frontnote | back | backnote | and nothing else.

Song text:
\"\"\"
{lyrics.strip()}
\"\"\"
"""


class GeminiError(Exception):
    pass


def ask_gemini(prompt, api_key, model="gemini-2.5-flash", timeout=120):
    if not api_key:
        raise GeminiError("No Gemini API key set. Add one in Settings.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8", "x-goog-api-key": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            pass
        raise GeminiError(f"Gemini returned an error ({e.code}):\n{detail}") from None
    except urllib.error.URLError as e:
        raise GeminiError(f"Could not reach Gemini: {e.reason}") from None

    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise GeminiError(f"Gemini sent no answer:\n{json.dumps(data, ensure_ascii=False)[:500]}") from None
    return "".join(p.get("text", "") for p in parts)
