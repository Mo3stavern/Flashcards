# Flashcards

A very simple flashcards desktop app (Windows, macOS, Linux). You bring a vocabulary table (CSV, Excel, or pasted from a spreadsheet or AI chat) and the app turns it into flashcards. Cyrillic and Turkish letters (ç ğ ı İ ö ş ü, ё, й …) work everywhere: in the text fields, in files, in deck names.

## Start the app

1. Install Python 3 from [python.org](https://www.python.org/downloads/). On Windows, tick "Add Python to PATH" during installation.
2. Run it from this folder:

```
python app.py
```

On Windows you can also double-click `app.py`. No other packages are needed.

Your decks are saved as normal UTF-8 CSV files in `Flashcards/decks` in your home folder. "Open decks folder" in the app takes you there. You can open the files in Excel, and any `.csv` file you drop into that folder shows up as a deck.

## Making decks

Click **Import table file…** (`.csv`, `.tsv`, `.txt`, `.md`, `.xlsx`) or **Paste table…**, check the preview and click **Save deck**.

### Adding more cards to a deck

Select the deck, click **Edit deck…**, then **Add cards from file…** and pick a CSV or Excel table. Its cards are added to the end of the deck. Click **Save deck** to keep them.

Cards whose `frontword` is already in the deck are skipped, and the app tells you which ones. Only an identical `frontword` counts as a duplicate. A sentence or phrase that contains a word you already have is still added. Upper and lower case count as different, so `Şarkı` and `şarkı` are two separate words.

## Table format

| frontword | wordtype | frontnote              | back | backnote              |
|-----------|----------|------------------------|------|-----------------------|
| звезда    | noun     | Звезда по имени Солнце | star | A star called the Sun |
| şarkı     | noun     | Bu şarkı senin için    | song | This song is for you  |

- `frontword` is shown in bold black on the front of the card, with `wordtype` next to it in orange. `frontnote` is shown under them, which works well for the line of the song the word came from.
- `back` is the answer, and `backnote` is shown under it (for example, the translation of the song line).
- Only `frontword` and `back` are required. The other columns can be left empty.
- A header row like `frontword | wordtype | frontnote | back | backnote` is optional. If it is there, the columns can be in any order.
- Older tables with just `front | back | note` still work: column 1 becomes the front word, column 2 the back and column 3 the back note.
- The app accepts tab-separated text (what you get when you copy a table out of Gemini, Google Sheets or Excel), CSV with `,` or `;`, Markdown tables, and Excel `.xlsx` files.
- Text files must be UTF-8 so that Cyrillic and Turkish come through correctly. In Excel, use "CSV UTF-8". In Google Sheets, use File, then Download, then CSV.

There is an example file in `examples/example_russian_turkish.csv`.

## Studying

Select a deck and click **Study** (or double-click the deck). Press `Space` to show the answer, then `1` (Again) or `2` (Got it). Cards you mark "Again" come back a few cards later until you know them all. Tick **Reverse** to see the translation first.

## Tests

```
python tests/test_cards.py
```
