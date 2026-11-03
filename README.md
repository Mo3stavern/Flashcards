# Flashcards

A very simple flashcards desktop app (Windows, macOS, Linux). You paste in a song text, an AI (Google Gemini or any other chatbot) turns it into a table of vocabulary, and the app turns that table into flashcards. Cyrillic and Turkish letters (ç ğ ı İ ö ş ü, ё, й …) work everywhere: in the text fields, in files, in deck names.

## Start the app

1. Install Python 3 from [python.org](https://www.python.org/downloads/). On Windows, tick "Add Python to PATH" during installation.
2. Run it from this folder:

```
python app.py
```

On Windows you can also double-click `app.py`. No other packages are needed.

Your decks are saved as normal UTF-8 CSV files in `Flashcards/decks` in your home folder. "Open decks folder" in the app takes you there. You can open the files in Excel, and any `.csv` file you drop into that folder shows up as a deck.

## Getting cards from Gemini

Click **New deck from song (AI)…**, paste the song text, pick the song language (for example Russian or Turkish) and the language you want translations in. Then choose one of these two options.

### Option A: Gemini website or any other AI (no setup)

1. Click **Copy prompt**. A ready-made prompt that includes your song text is now in your clipboard.
2. Paste it into [gemini.google.com](https://gemini.google.com), ChatGPT, Claude, or another chatbot.
3. Copy the table from the answer and paste it into the window the app opened. A live preview shows which cards were found.
4. Click **Save deck**.

### Option B: Gemini API (one click)

1. Get a free API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
2. Enter it in **Settings…** (or set the `GEMINI_API_KEY` environment variable).
3. Click **Create cards with Gemini API**. The cards come back in the preview window, where you check them and click **Save deck**.

You can change the model in Settings. The default is `gemini-2.5-flash`.

## Table format

You can also bring a table you made yourself: click **Import table file…** (`.csv`, `.tsv`, `.txt`, `.md`, `.xlsx`) or **Paste table…**.

| front  | back  | note                    |
|--------|-------|-------------------------|
| звезда | star  | Звезда по имени Солнце  |
| şarkı  | song  | Bu şarkı senin için     |

- Column 1 is the front of the card and column 2 is the back. Column 3 (optional) is shown under the answer, which works well for the line of the song the word came from.
- A header row like `front | back | note` is optional and gets skipped automatically.
- The app accepts tab-separated text (what you get when you copy a table out of Gemini, Google Sheets or Excel), CSV with `,` or `;`, Markdown tables, and Excel `.xlsx` files.
- Text files must be UTF-8 so that Cyrillic and Turkish come through correctly. In Excel, use "CSV UTF-8". In Google Sheets, use File, then Download, then CSV.

There is an example file in `examples/example_russian_turkish.csv`.

## Studying

Select a deck and click **Study** (or double-click the deck). Press `Space` to show the answer, then `1` (Again) or `2` (Got it). Cards you mark "Again" come back a few cards later until you know them all. Tick **Reverse** to see the translation first.

## Tests

```
python tests/test_cards.py
```
