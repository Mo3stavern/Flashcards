"""Simple flashcards desktop app.

Run with:  python app.py
"""

import os
import random
import subprocess
import sys
import threading
import zipfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import cards as core

FONT = ("Segoe UI", 11) if sys.platform == "win32" else ("Helvetica", 12)
BIG = (FONT[0], 30, "bold")
MEDIUM = (FONT[0], 20)
SMALL = (FONT[0], 11, "italic")

SONG_LANGUAGES = ["Russian", "Turkish", "Ukrainian", "Bulgarian", "Serbian", "Kazakh", "Azerbaijani"]
TARGET_LANGUAGES = ["English", "German", "Turkish", "Russian"]


def open_folder(path):
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def text_widget(parent, height):
    frame = ttk.Frame(parent)
    txt = tk.Text(frame, height=height, wrap="word", font=FONT, undo=True)
    sb = ttk.Scrollbar(frame, command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    txt.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")
    return frame, txt


class TableDialog(tk.Toplevel):
    """Paste (or review) a table and save it as a deck, with a live preview."""

    def __init__(self, app, text="", name="", title="Paste table", editing=None):
        super().__init__(app.root)
        self.app = app
        self.editing = editing
        self.title(title)
        self.geometry("900x620")
        self.cards = []

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Deck name:").pack(side="left")
        self.name = tk.StringVar(value=name)
        ttk.Entry(top, textvariable=self.name, width=40, font=FONT).pack(side="left", padx=6)

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(side="bottom", fill="x")
        ttk.Button(bottom, text="Paste from clipboard", command=self._paste).pack(side="left")
        ttk.Button(bottom, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bottom, text="Save deck", command=self._save).pack(side="right", padx=6)

        ttk.Label(
            self, padding=(10, 0), wraplength=860,
            text="Paste the table from Gemini (or Excel / Google Sheets) below. "
                 "Column 1 = front, column 2 = back, column 3 = note (optional).",
        ).pack(anchor="w")

        frame, self.txt = text_widget(self, 10)
        frame.pack(fill="both", expand=True, padx=10, pady=6)
        self.txt.insert("1.0", text)
        self.txt.bind("<<Modified>>", self._on_change)

        self.count = ttk.Label(self, padding=(10, 0))
        self.count.pack(anchor="w")

        self.tree = ttk.Treeview(self, columns=("front", "back", "note"), show="headings", height=10)
        for col, w in (("front", 250), ("back", 250), ("note", 350)):
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=w)
        self.tree.pack(fill="both", expand=True, padx=10, pady=6)

        self._refresh()
        if not text:
            self.txt.focus_set()

    def _paste(self):
        try:
            clip = self.clipboard_get()
        except tk.TclError:
            return
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", clip)

    def _on_change(self, _event=None):
        if self.txt.edit_modified():
            self._refresh()
            self.txt.edit_modified(False)

    def _refresh(self):
        self.cards = core.parse_table(self.txt.get("1.0", "end"))
        self.tree.delete(*self.tree.get_children())
        for c in self.cards:
            self.tree.insert("", "end", values=(c.front, c.back, c.note))
        self.count.configure(text=f"{len(self.cards)} cards detected")

    def _save(self):
        name = self.name.get().strip()
        if not name:
            messagebox.showwarning("Deck name", "Please enter a deck name.", parent=self)
            return
        if not self.cards:
            messagebox.showwarning("No cards", "No cards found in the table.", parent=self)
            return
        path = core.deck_path(name)
        if path.exists() and path.stem != self.editing and not messagebox.askyesno(
            "Overwrite?", f"A deck called '{path.stem}' already exists. Replace it?", parent=self
        ):
            return
        core.save_deck(name, self.cards)
        if self.editing and self.editing != path.stem:
            core.deck_path(self.editing).unlink(missing_ok=True)
        self.app.refresh_decks(select=path.stem)
        self.destroy()


class SongDialog(tk.Toplevel):
    """Paste song lyrics and let Gemini (or any AI chat) turn them into a table."""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("New deck from a song")
        self.geometry("760x640")
        cfg = app.config

        form = ttk.Frame(self, padding=10)
        form.pack(fill="x")
        ttk.Label(form, text="Deck name:").grid(row=0, column=0, sticky="w")
        self.name = tk.StringVar()
        ttk.Entry(form, textvariable=self.name, width=40, font=FONT).grid(row=0, column=1, columnspan=3, sticky="w", pady=3)
        ttk.Label(form, text="Song language:").grid(row=1, column=0, sticky="w")
        self.song_lang = tk.StringVar(value=cfg["song_language"])
        ttk.Combobox(form, textvariable=self.song_lang, values=SONG_LANGUAGES, width=16).grid(row=1, column=1, sticky="w", pady=3)
        ttk.Label(form, text="Translate to:").grid(row=1, column=2, sticky="w", padx=(12, 0))
        self.target_lang = tk.StringVar(value=cfg["target_language"])
        ttk.Combobox(form, textvariable=self.target_lang, values=TARGET_LANGUAGES, width=16).grid(row=1, column=3, sticky="w")
        ttk.Label(form, text="Max cards:").grid(row=2, column=0, sticky="w")
        self.max_cards = tk.IntVar(value=cfg["max_cards"])
        ttk.Spinbox(form, from_=5, to=200, textvariable=self.max_cards, width=6).grid(row=2, column=1, sticky="w", pady=3)

        ttk.Label(self, text="Song text:", padding=(10, 0)).pack(anchor="w")
        frame, self.txt = text_widget(self, 16)
        frame.pack(fill="both", expand=True, padx=10, pady=6)
        self.txt.focus_set()

        self.status = ttk.Label(self, padding=(10, 0), foreground="#555")
        self.status.pack(anchor="w")

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        self.api_btn = ttk.Button(bottom, text="Create cards with Gemini API", command=self._generate)
        self.api_btn.pack(side="left")
        ttk.Button(bottom, text="Copy prompt (for gemini.google.com / any AI)", command=self._copy_prompt).pack(side="left", padx=6)
        ttk.Button(bottom, text="Close", command=self.destroy).pack(side="right")

    def _prompt(self):
        lyrics = self.txt.get("1.0", "end").strip()
        if not lyrics:
            messagebox.showwarning("Song text", "Please paste the song text first.", parent=self)
            return None
        cfg = self.app.config
        cfg["song_language"] = self.song_lang.get()
        cfg["target_language"] = self.target_lang.get()
        try:
            cfg["max_cards"] = int(self.max_cards.get())
        except (tk.TclError, ValueError):
            pass
        core.save_config(cfg)
        return core.build_prompt(lyrics, cfg["song_language"], cfg["target_language"], cfg["max_cards"])

    def _copy_prompt(self):
        prompt = self._prompt()
        if not prompt:
            return
        self.clipboard_clear()
        self.clipboard_append(prompt)
        self.update()
        messagebox.showinfo(
            "Prompt copied",
            "The prompt is in your clipboard.\n\n"
            "1. Paste it into Gemini (gemini.google.com) or any other AI chat.\n"
            "2. Copy the table it answers with.\n"
            "3. Paste it into the window that opens next.",
            parent=self,
        )
        name = self.name.get().strip()
        self.destroy()
        TableDialog(self.app, name=name)

    def _generate(self):
        prompt = self._prompt()
        if not prompt:
            return
        if not self.app.config["gemini_api_key"]:
            if messagebox.askyesno(
                "No API key",
                "No Gemini API key is set yet.\n\nYou can get a free one at aistudio.google.com/apikey.\n"
                "Open Settings now?\n\n(Or use 'Copy prompt' to work with the Gemini website instead.)",
                parent=self,
            ):
                SettingsDialog(self.app)
            return

        self.api_btn.state(["disabled"])
        self.status.configure(text="Asking Gemini... this can take up to a minute.")
        result = {}
        cfg = self.app.config

        def work():
            try:
                result["text"] = core.ask_gemini(prompt, cfg["gemini_api_key"], cfg["gemini_model"])
            except core.GeminiError as e:
                result["error"] = str(e)

        thread = threading.Thread(target=work, daemon=True)
        thread.start()

        def poll():
            if thread.is_alive():
                self.after(200, poll)
                return
            if not self.winfo_exists():
                return
            self.api_btn.state(["!disabled"])
            self.status.configure(text="")
            if "error" in result:
                messagebox.showerror("Gemini", result["error"], parent=self)
                return
            name = self.name.get().strip()
            self.destroy()
            TableDialog(self.app, text=result["text"], name=name, title="Check the cards and save")

        self.after(200, poll)


class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("Settings")
        self.resizable(False, False)
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both")

        ttk.Label(f, text="Gemini API key:").grid(row=0, column=0, sticky="w")
        self.key = tk.StringVar(value=app.config["gemini_api_key"])
        ttk.Entry(f, textvariable=self.key, width=48, show="•").grid(row=0, column=1, pady=4)
        ttk.Label(f, text="Get a free key at aistudio.google.com/apikey", foreground="#555").grid(row=1, column=1, sticky="w")
        ttk.Label(f, text="Gemini model:").grid(row=2, column=0, sticky="w")
        self.model = tk.StringVar(value=app.config["gemini_model"])
        ttk.Entry(f, textvariable=self.model, width=48).grid(row=2, column=1, pady=4)
        ttk.Label(f, text=f"Your decks are stored in:\n{core.DECKS_DIR}", foreground="#555").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )

        b = ttk.Frame(f)
        b.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(b, text="Save", command=self._save).pack(side="left", padx=6)
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="left")

    def _save(self):
        self.app.config["gemini_api_key"] = self.key.get().strip()
        self.app.config["gemini_model"] = self.model.get().strip() or core.DEFAULT_CONFIG["gemini_model"]
        core.save_config(self.app.config)
        self.destroy()


class StudyView(ttk.Frame):
    """Show a card, flip it, mark it 'Again' or 'Got it'. 'Again' cards come back later."""

    def __init__(self, app, deck_name, deck_cards, reverse):
        super().__init__(app.root, padding=20)
        self.app = app
        self.reverse = reverse
        self.queue = list(deck_cards)
        random.shuffle(self.queue)
        self.total = len(self.queue)
        self.known = 0
        self.flipped = False

        head = ttk.Frame(self)
        head.pack(fill="x")
        ttk.Button(head, text="← Back to decks", command=app.show_decks).pack(side="left")
        ttk.Label(head, text=deck_name, font=(FONT[0], 14, "bold")).pack(side="left", padx=14)
        self.progress = ttk.Label(head)
        self.progress.pack(side="right")

        self.card = tk.Frame(self, bg="white", highlightbackground="#ccc", highlightthickness=1)
        self.card.pack(fill="both", expand=True, pady=16)
        self.front = tk.Label(self.card, font=BIG, bg="white", wraplength=760)
        self.front.pack(expand=True, pady=(40, 0))
        self.back = tk.Label(self.card, font=MEDIUM, bg="white", fg="#1a5fb4", wraplength=760)
        self.back.pack(expand=True)
        self.note = tk.Label(self.card, font=SMALL, bg="white", fg="#666", wraplength=760)
        self.note.pack(expand=True, pady=(0, 30))
        for w in (self.card, self.front, self.back, self.note):
            w.bind("<Button-1>", lambda e: self.flip())

        self.buttons = ttk.Frame(self)
        self.buttons.pack()
        self.show_btn = ttk.Button(self.buttons, text="Show answer  [Space]", command=self.flip)
        self.again_btn = ttk.Button(self.buttons, text="Again  [1]", command=lambda: self.answer(False))
        self.good_btn = ttk.Button(self.buttons, text="Got it  [2]", command=lambda: self.answer(True))
        self.restart_btn = ttk.Button(self.buttons, text="Study again", command=lambda: app.study(deck_name, reverse))

        app.root.bind("<space>", lambda e: self.flip())
        app.root.bind("<Return>", lambda e: self.flip())
        app.root.bind("1", lambda e: self.answer(False))
        app.root.bind("2", lambda e: self.answer(True))
        self.show_card()

    def unbind_keys(self):
        for key in ("<space>", "<Return>", "1", "2"):
            self.app.root.unbind(key)

    def _sides(self, c):
        return (c.back, c.front) if self.reverse else (c.front, c.back)

    def show_card(self):
        for b in (self.show_btn, self.again_btn, self.good_btn, self.restart_btn):
            b.pack_forget()
        self.progress.configure(text=f"Learned {self.known} / {self.total}   ·   {len(self.queue)} left")
        if not self.queue:
            self.front.configure(text="Done!")
            self.back.configure(text=f"You went through all {self.total} cards.")
            self.note.configure(text="")
            self.restart_btn.pack()
            return
        self.flipped = False
        q, _ = self._sides(self.queue[0])
        self.front.configure(text=q)
        self.back.configure(text="")
        self.note.configure(text="")
        self.show_btn.pack()

    def flip(self):
        if not self.queue or self.flipped:
            return
        self.flipped = True
        c = self.queue[0]
        self.back.configure(text=self._sides(c)[1])
        self.note.configure(text=c.note)
        self.show_btn.pack_forget()
        self.again_btn.pack(side="left", padx=8)
        self.good_btn.pack(side="left", padx=8)

    def answer(self, knew_it):
        if not self.queue or not self.flipped:
            return
        c = self.queue.pop(0)
        if knew_it:
            self.known += 1
        else:
            # Put the card back a few positions later so it comes up again soon.
            self.queue.insert(min(len(self.queue), random.randint(3, 6)), c)
        self.show_card()


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Flashcards")
        self.root.geometry("900x620")
        self.root.minsize(700, 480)
        style = ttk.Style()
        if "clam" in style.theme_names() and sys.platform.startswith("linux"):
            style.theme_use("clam")
        style.configure(".", font=FONT)
        style.configure("Treeview", rowheight=26)
        self.config = core.load_config()
        self.view = None
        self._build_decks_view()
        self.show_decks()

    def _build_decks_view(self):
        self.decks_view = ttk.Frame(self.root, padding=16)
        ttk.Label(self.decks_view, text="My decks", font=(FONT[0], 16, "bold")).pack(anchor="w")

        body = ttk.Frame(self.decks_view)
        body.pack(fill="both", expand=True, pady=10)

        self.deck_list = ttk.Treeview(body, columns=("cards",), show="tree headings", selectmode="browse")
        self.deck_list.heading("#0", text="Deck")
        self.deck_list.heading("cards", text="Cards")
        self.deck_list.column("cards", width=80, anchor="center", stretch=False)
        self.deck_list.pack(side="left", fill="both", expand=True)
        self.deck_list.bind("<Double-1>", lambda e: self._study_selected())

        side = ttk.Frame(body, padding=(14, 0, 0, 0))
        side.pack(side="right", fill="y")
        self.reverse = tk.BooleanVar(value=False)
        for text, cmd in (
            ("▶  Study", self._study_selected),
            (None, None),
            ("♪  New deck from song (AI)…", lambda: SongDialog(self)),
            ("Paste table…", lambda: TableDialog(self)),
            ("Import table file…", self._import_file),
            (None, None),
            ("Edit deck…", self._edit_selected),
            ("Delete deck", self._delete_selected),
            ("Open decks folder", lambda: open_folder(core.DECKS_DIR)),
            ("Settings…", lambda: SettingsDialog(self)),
        ):
            if text is None:
                ttk.Separator(side).pack(fill="x", pady=8)
            else:
                ttk.Button(side, text=text, command=cmd).pack(fill="x", pady=2)
        ttk.Checkbutton(side, text="Reverse (show translation first)", variable=self.reverse).pack(anchor="w", pady=(12, 0))

    def refresh_decks(self, select=None):
        self.deck_list.delete(*self.deck_list.get_children())
        for path in core.list_decks():
            try:
                n = len(core.load_deck(path))
            except (OSError, ValueError):
                n = "?"
            self.deck_list.insert("", "end", iid=str(path), text=path.stem, values=(n,))
            if path.stem == select:
                self.deck_list.selection_set(str(path))
                self.deck_list.see(str(path))

    def show_decks(self):
        if self.view is not None:
            self.view.unbind_keys()
            self.view.destroy()
            self.view = None
        self.refresh_decks()
        self.decks_view.pack(fill="both", expand=True)

    def _selected(self):
        sel = self.deck_list.selection()
        if not sel:
            messagebox.showinfo("Select a deck", "Please select a deck first.")
            return None
        return Path(sel[0])

    def study(self, name, reverse):
        path = core.deck_path(name)
        try:
            deck = core.load_deck(path)
        except (OSError, ValueError) as e:
            messagebox.showerror("Can't open deck", str(e))
            return
        if not deck:
            messagebox.showinfo("Empty deck", "This deck has no cards.")
            return
        if self.view is not None:
            self.view.unbind_keys()
            self.view.destroy()
        self.decks_view.pack_forget()
        self.view = StudyView(self, name, deck, reverse)
        self.view.pack(fill="both", expand=True)

    def _study_selected(self):
        path = self._selected()
        if path:
            self.study(path.stem, self.reverse.get())

    def _edit_selected(self):
        path = self._selected()
        if path:
            TableDialog(self, text=core.cards_to_tsv(core.load_deck(path)), name=path.stem,
                        title="Edit deck", editing=path.stem)

    def _delete_selected(self):
        path = self._selected()
        if path and messagebox.askyesno("Delete deck", f"Really delete '{path.stem}'?"):
            path.unlink(missing_ok=True)
            self.refresh_decks()

    def _import_file(self):
        filename = filedialog.askopenfilename(
            title="Import table",
            filetypes=[
                ("Tables", "*.csv *.tsv *.txt *.md *.xlsx"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return
        try:
            deck = core.load_file(filename)
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
            messagebox.showerror("Can't read file", str(e))
            return
        TableDialog(self, text=core.cards_to_tsv(deck), name=Path(filename).stem, title="Check the cards and save")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
