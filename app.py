"""STALZONE Name Editor — редактор локализации.

Запуск: python app.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tkinter as tk
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from categories import CATEGORY_INDEX, CATEGORY_ORDER
from detect import LangSource, find_game_dirs, find_lang_files
from langfile import Entry, LangFile

APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
BACKUP_DIR = APP_DIR / "backups"
EXPORT_DIR = APP_DIR / "exports"
MAX_ROWS = 20000

BG = "#f3f5f9"
CARD = "#ffffff"
TEXT = "#1f2937"
MUTED = "#6b7280"
ACCENT = "#2563eb"
BORDER = "#d7dde8"


class LocEditorApp(tk.Tk):
    def __init__(self, smoke: bool = False) -> None:
        super().__init__()
        self.smoke = smoke
        self.title("STALZONE Name Editor")
        self.geometry("1320x840")
        self.minsize(980, 640)
        self.configure(bg=BG)

        self.game_dir: Path | None = None
        self.sources: list[LangSource] = []
        self.lf: LangFile | None = None
        self.entry_by_iid: dict[str, Entry] = {}
        self.selected_entry: Entry | None = None
        self.current_source: LangSource | None = None
        self.current_category = "Все"
        self.sort_col: str | None = None
        self.sort_rev = False
        self._search_job: str | None = None

        self.export_names_var = tk.BooleanVar(value=False)
        self.ops_file_var = tk.StringVar(value="Файл не выбран")
        self.ops_path_var = tk.StringVar(value="")
        self.ops_dirty_var = tk.StringVar(value="")
        self.ops_backup_count_var = tk.StringVar(value="")

        self._configure_style()
        self._build_ui()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(120, self.auto_detect)

    # ---------- оформление ----------

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=("Segoe UI", 10), background=BG, foreground=TEXT)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Strong.TLabel", background=BG, font=("Segoe UI Semibold", 10))
        style.configure(
            "Title.TLabel", background=BG, font=("Segoe UI Semibold", 20), foreground="#0f172a"
        )
        style.configure("Subtitle.TLabel", background=BG, foreground=MUTED)

        style.configure(
            "TButton",
            padding=(12, 6),
            relief="flat",
            borderwidth=1,
            background=CARD,
            bordercolor=BORDER,
            lightcolor=CARD,
            darkcolor=CARD,
            focuscolor=ACCENT,
        )
        style.map(
            "TButton",
            background=[("active", "#e8efff"), ("pressed", "#dbe7ff")],
            foreground=[("disabled", "#9ca3af")],
            bordercolor=[("focus", ACCENT)],
        )
        style.configure(
            "Accent.TButton",
            padding=(14, 6),
            background=ACCENT,
            foreground="#ffffff",
            bordercolor=ACCENT,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#1d4ed8"), ("pressed", "#1e40af")],
            foreground=[("disabled", "#bfdbfe")],
        )

        style.configure(
            "TEntry",
            padding=(7, 5),
            fieldbackground=CARD,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
        )
        style.configure("TCombobox", padding=5, fieldbackground=CARD)
        style.configure("TCheckbutton", background=BG)
        style.map("TCheckbutton", background=[("active", BG)])

        style.configure(
            "TLabelframe",
            background=BG,
            bordercolor=BORDER,
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "TLabelframe.Label",
            background=BG,
            foreground=TEXT,
            font=("Segoe UI Semibold", 10),
        )

        style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure(
            "TNotebook.Tab",
            padding=(20, 9),
            background="#e5eaf3",
            foreground=MUTED,
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", CARD)],
            foreground=[("selected", ACCENT)],
        )

        style.configure(
            "Treeview",
            background=CARD,
            fieldbackground=CARD,
            foreground=TEXT,
            rowheight=28,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#e9eef7",
            foreground="#334155",
            relief="flat",
            padding=(8, 6),
            font=("Segoe UI", 9, "bold"),
        )
        style.map("Treeview.Heading", background=[("active", "#dde6f5")])
        style.map(
            "Treeview",
            background=[("selected", "#dbeafe")],
            foreground=[("selected", "#0f172a")],
        )
        style.configure(
            "Status.TLabel",
            background="#e8edf5",
            foreground=MUTED,
            padding=(14, 7),
        )

    # ---------- интерфейс ----------

    def _build_ui(self) -> None:
        self.status_var = tk.StringVar()
        status = ttk.Label(
            self, textvariable=self.status_var, style="Status.TLabel", anchor="w"
        )
        status.pack(side="bottom", fill="x")

        outer = ttk.Frame(self, padding=(16, 14, 16, 10))
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 12))
        accent_bar = tk.Frame(header, width=4, height=46, bg=ACCENT)
        accent_bar.pack(side="left", fill="y", padx=(0, 12))
        accent_bar.pack_propagate(False)
        titles = ttk.Frame(header)
        titles.pack(side="left", fill="y")
        ttk.Label(titles, text="STALZONE Name Editor", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            titles,
            text="Редактор локализации · предметы, интерфейс и мир игры",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill="both", expand=True)
        editor_tab = ttk.Frame(self.notebook, padding=(0, 12, 0, 0))
        ops_tab = ttk.Frame(self.notebook, padding=(0, 12, 0, 0))
        self.notebook.add(editor_tab, text="Редактор")
        self.notebook.add(ops_tab, text="Файлы и копии")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self._build_editor_tab(editor_tab)
        self._build_ops_tab(ops_tab)

        self._set_status("Поиск игры…")
        self._set_editor_enabled(False)

    def _build_editor_tab(self, tab: ttk.Frame) -> None:
        toolbar = ttk.LabelFrame(tab, text="Игра и файл", padding=10)
        toolbar.pack(fill="x")

        top = ttk.Frame(toolbar)
        top.pack(fill="x")
        ttk.Label(top, text="Папка игры:").pack(side="left")
        self.game_var = tk.StringVar()
        self.game_entry = ttk.Entry(top, textvariable=self.game_var)
        self.game_entry.pack(side="left", fill="x", expand=True, padx=6)
        self._bind_entry_shortcuts(self.game_entry)
        ttk.Button(top, text="Обзор…", command=self.browse_game).pack(side="left")
        ttk.Button(top, text="Найти", command=self.auto_detect).pack(
            side="left", padx=(6, 0)
        )

        file_row = ttk.Frame(toolbar)
        file_row.pack(fill="x", pady=(8, 0))
        ttk.Label(file_row, text="Файл:").pack(side="left")
        self.file_combo = ttk.Combobox(file_row, state="readonly", width=46)
        self.file_combo.pack(side="left", padx=6)
        self.file_combo.bind("<<ComboboxSelected>>", self.on_file_selected)
        self.file_info = ttk.Label(file_row, text="", style="Muted.TLabel")
        self.file_info.pack(side="left", padx=(8, 0))

        main = ttk.Frame(tab)
        main.pack(fill="both", expand=True, pady=(10, 0))
        main.columnconfigure(0, weight=0, minsize=270)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(main, text="Фильтры", padding=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(left, text="Поиск:").pack(anchor="w")
        self.search_var = tk.StringVar()
        search = ttk.Entry(left, textvariable=self.search_var)
        search.pack(fill="x", pady=(2, 5))
        search.bind("<Return>", lambda _event: self.search_items())
        self._bind_entry_shortcuts(search)
        self.search_entry = search
        ttk.Button(
            left,
            text="Поиск предметов",
            style="Accent.TButton",
            command=self.search_items,
        ).pack(fill="x", pady=(0, 8))

        self.only_names_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            left,
            text="Только названия (без описаний)",
            variable=self.only_names_var,
            command=self.on_filter_changed,
        ).pack(anchor="w", pady=(0, 8))

        ttk.Label(left, text="Тип:").pack(anchor="w")
        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True, pady=(2, 0))
        self.cat_list = tk.Listbox(
            list_frame,
            exportselection=False,
            activestyle="none",
            font=("Segoe UI", 10),
            bg=CARD,
            fg=TEXT,
            selectbackground="#dbeafe",
            selectforeground=TEXT,
            borderwidth=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        cat_scroll = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.cat_list.yview
        )
        self.cat_list.configure(yscrollcommand=cat_scroll.set)
        self.cat_list.pack(side="left", fill="both", expand=True)
        cat_scroll.pack(side="right", fill="y")
        self.cat_list.bind("<<ListboxSelect>>", self.on_category_selected)

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)

        tree_frame = ttk.Frame(right)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        columns = ("value", "key", "category")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="browse"
        )
        self.tree.heading("value", text="Название", command=lambda: self.sort_by("value"))
        self.tree.heading("key", text="Ключ", command=lambda: self.sort_by("key"))
        self.tree.heading(
            "category", text="Тип", command=lambda: self.sort_by("category")
        )
        self.tree.column("value", width=430, stretch=True)
        self.tree.column("key", width=440, stretch=True)
        self.tree.column("category", width=180, stretch=False)
        tree_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        tree_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_y.set, xscrollcommand=tree_x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_y.grid(row=0, column=1, sticky="ns")
        tree_x.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda _event: self.new_entry.focus_set())

        editor = ttk.LabelFrame(right, text="Редактирование", padding=10)
        editor.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        editor.columnconfigure(1, weight=1)

        ttk.Label(editor, text="Ключ:").grid(row=0, column=0, sticky="w")
        self.key_var = tk.StringVar()
        ttk.Label(
            editor,
            textvariable=self.key_var,
            style="Muted.TLabel",
            anchor="w",
        ).grid(row=0, column=1, columnspan=3, sticky="ew", padx=(6, 0))

        ttk.Label(editor, text="Было:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.old_var = tk.StringVar()
        old_entry = ttk.Entry(editor, textvariable=self.old_var, state="readonly")
        old_entry.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(8, 0))
        self._bind_entry_shortcuts(old_entry)

        ttk.Label(editor, text="Станет:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.new_var = tk.StringVar()
        self.new_entry = ttk.Entry(editor, textvariable=self.new_var)
        self.new_entry.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=(8, 0))
        self._bind_entry_shortcuts(self.new_entry)
        self.new_entry.bind("<Return>", lambda _event: self.apply_value())
        self.new_entry.bind("<Escape>", lambda _event: self.revert_selected())

        buttons = ttk.Frame(editor)
        buttons.grid(row=2, column=2, sticky="e", padx=(10, 0), pady=(8, 0))
        ttk.Button(buttons, text="Применить", command=self.apply_value).pack(
            side="left"
        )
        ttk.Button(buttons, text="Сбросить", command=self.revert_selected).pack(
            side="left", padx=6
        )
        self.save_button = ttk.Button(
            buttons, text="Сохранить файл", style="Accent.TButton", command=self.save_file
        )
        self.save_button.pack(side="left")

        bottom = ttk.Frame(editor)
        bottom.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        bottom.columnconfigure(0, weight=1)
        self.dirty_var = tk.StringVar(value="Изменений нет")
        ttk.Label(bottom, textvariable=self.dirty_var, style="Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(
            bottom, text="Экспорт и копии →", command=self._show_ops_tab
        ).grid(row=0, column=1, sticky="e")

    def _build_ops_tab(self, tab: ttk.Frame) -> None:
        info = ttk.LabelFrame(tab, text="Текущий файл", padding=12)
        info.pack(fill="x")
        ttk.Label(info, textvariable=self.ops_file_var, style="Strong.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            info, textvariable=self.ops_path_var, style="Muted.TLabel", anchor="w"
        ).pack(anchor="w", pady=(3, 0))
        ttk.Label(
            info, textvariable=self.ops_dirty_var, style="Muted.TLabel", anchor="w"
        ).pack(anchor="w", pady=(3, 0))

        io = ttk.LabelFrame(tab, text="Экспорт и импорт", padding=12)
        io.pack(fill="x", pady=(10, 0))
        ttk.Label(
            io,
            text=(
                "Экспорт сохраняет строки текущего файла в JSON. Импорт ищет строки "
                "по ключу и применяет значения в памяти — после импорта нажми "
                "«Сохранить файл» на вкладке «Редактор»."
            ),
            style="Muted.TLabel",
            wraplength=980,
            justify="left",
        ).pack(anchor="w")
        io_row = ttk.Frame(io)
        io_row.pack(fill="x", pady=(10, 0))
        io_row.columnconfigure(0, weight=1)
        ttk.Checkbutton(
            io_row,
            text="Только названия (без описаний)",
            variable=self.export_names_var,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            io_row,
            text="Экспорт в JSON…",
            style="Accent.TButton",
            command=self.export_current,
        ).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(
            io_row, text="Импорт из JSON…", command=self.import_current
        ).grid(row=0, column=2, padx=(8, 0))

        backups = ttk.LabelFrame(tab, text="Резервные копии", padding=12)
        backups.pack(fill="both", expand=True, pady=(10, 0))
        b_row = ttk.Frame(backups)
        b_row.pack(fill="x")
        ttk.Button(
            b_row,
            text="Создать копию…",
            style="Accent.TButton",
            command=self.create_backup,
        ).pack(side="left")
        ttk.Button(b_row, text="Обновить", command=self._refresh_backups).pack(
            side="left", padx=8
        )
        ttk.Button(b_row, text="Открыть папку", command=self.open_backups).pack(
            side="left"
        )
        ttk.Button(b_row, text="Переименовать", command=self.rename_backup).pack(
            side="left", padx=(8, 0)
        )
        ttk.Label(
            b_row,
            textvariable=self.ops_backup_count_var,
            style="Muted.TLabel",
        ).pack(side="right")

        ttk.Label(
            backups,
            text="Копию можно сохранить в любую папку и под любым именем. "
            "В списке ниже — копии из папки backups.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(8, 0))

        backup_frame = ttk.Frame(backups)
        backup_frame.pack(fill="both", expand=True, pady=(10, 0))
        columns = ("name", "date", "size")
        self.backup_tree = ttk.Treeview(
            backup_frame, columns=columns, show="headings", selectmode="browse"
        )
        self.backup_tree.heading("name", text="Файл")
        self.backup_tree.heading("date", text="Дата")
        self.backup_tree.heading("size", text="Размер")
        self.backup_tree.column("name", width=560, stretch=True)
        self.backup_tree.column("date", width=190, stretch=False)
        self.backup_tree.column("size", width=110, stretch=False, anchor="e")
        b_y = ttk.Scrollbar(
            backup_frame, orient="vertical", command=self.backup_tree.yview
        )
        self.backup_tree.configure(yscrollcommand=b_y.set)
        self.backup_tree.pack(side="left", fill="both", expand=True)
        b_y.pack(side="right", fill="y")
        self.backup_tree.bind("<Double-1>", lambda _event: self.restore_backup())

        restore_row = ttk.Frame(backups)
        restore_row.pack(fill="x", pady=(8, 0))
        ttk.Button(
            restore_row, text="Восстановить выбранную", command=self.restore_backup
        ).pack(side="right")
        ttk.Button(
            restore_row, text="Из файла…", command=self.restore_from_file
        ).pack(side="right", padx=(0, 8))
        ttk.Label(
            restore_row,
            text="Перед восстановлением текущая версия тоже попадёт в копии.",
            style="Muted.TLabel",
        ).pack(side="left")

    def _bind_keys(self) -> None:
        self.bind("<Control-s>", lambda _event: self.save_file())
        self.bind("<Control-f>", lambda _event: self.search_entry.focus_set())
        self.search_var.trace_add("write", self._on_search_changed)

    def _bind_entry_shortcuts(self, entry: ttk.Entry) -> None:
        """Ctrl+A/C/X/V/Z/Y внутри полей ввода."""
        entry.bind("<FocusIn>", self._reset_entry_history)
        entry.bind("<KeyRelease>", self._track_entry_history)
        entry.bind("<Control-a>", self._select_all_entry)
        entry.bind("<Control-A>", self._select_all_entry)
        entry.bind("<Control-c>", self._copy_entry)
        entry.bind("<Control-C>", self._copy_entry)
        entry.bind("<Control-x>", self._cut_entry)
        entry.bind("<Control-X>", self._cut_entry)
        entry.bind("<Control-v>", self._paste_entry)
        entry.bind("<Control-V>", self._paste_entry)
        entry.bind("<Control-z>", self._undo_entry)
        entry.bind("<Control-Z>", self._redo_entry)
        entry.bind("<Control-y>", self._redo_entry)
        entry.bind("<Control-Y>", self._redo_entry)

    @staticmethod
    def _select_all_entry(event: tk.Event) -> str:
        event.widget.selection_range(0, "end")
        event.widget.icursor("end")
        return "break"

    @staticmethod
    def _reset_entry_history(event: tk.Event) -> None:
        widget = event.widget
        widget._undo_stack = [widget.get()]
        widget._redo_stack = []
        widget._undoing = False

    @staticmethod
    def _track_entry_history(event: tk.Event) -> None:
        widget = event.widget
        if getattr(widget, "_undoing", False):
            widget._undoing = False
            return
        stack = getattr(widget, "_undo_stack", None)
        if stack is None:
            widget._undo_stack = [widget.get()]
            widget._redo_stack = []
            return
        text = widget.get()
        if text != stack[-1]:
            stack.append(text)
            if len(stack) > 200:
                del stack[0]
            widget._redo_stack.clear()

    @staticmethod
    def _copy_entry(event: tk.Event) -> str:
        event.widget.event_generate("<<Copy>>")
        return "break"

    @staticmethod
    def _cut_entry(event: tk.Event) -> str:
        event.widget.event_generate("<<Cut>>")
        return "break"

    @staticmethod
    def _paste_entry(event: tk.Event) -> str:
        event.widget.event_generate("<<Paste>>")
        return "break"

    @staticmethod
    def _undo_entry(event: tk.Event) -> str:
        widget = event.widget
        stack = getattr(widget, "_undo_stack", [])
        if not stack:
            return "break"
        text = widget.get()
        if text != stack[-1]:
            stack.append(text)
        if len(stack) <= 1:
            return "break"
        current = stack.pop()
        widget._redo_stack.append(current)
        previous = stack[-1]
        widget._undoing = True
        widget.delete(0, "end")
        widget.insert(0, previous)
        widget.icursor("end")
        return "break"

    @staticmethod
    def _redo_entry(event: tk.Event) -> str:
        widget = event.widget
        redo = getattr(widget, "_redo_stack", [])
        if not redo:
            return "break"
        following = redo.pop()
        widget._undo_stack.append(following)
        widget._undoing = True
        widget.delete(0, "end")
        widget.insert(0, following)
        widget.icursor("end")
        return "break"

    def _show_ops_tab(self) -> None:
        self.notebook.select(1)
        self._refresh_ops_info()
        self._refresh_backups()

    def _on_tab_changed(self, _event: object = None) -> None:
        if self.notebook.index("current") == 1:
            self._refresh_ops_info()
            self._refresh_backups()

    # ---------- поиск игры и файлов ----------

    def auto_detect(self) -> None:
        dirs = find_game_dirs()
        if not dirs:
            self._set_status("Игра не найдена автоматически. Укажи папку вручную.")
            if not self.smoke:
                messagebox.showwarning(
                    "Игра не найдена",
                    "Не удалось найти STALZONE. Нажми «Обзор…» и выбери папку игры.",
                )
            return
        if not self._confirm_discard():
            return
        self._load_game(dirs[0])

    def browse_game(self) -> None:
        initial = str(self.game_dir or APP_DIR)
        chosen = filedialog.askdirectory(title="Папка STALZONE", initialdir=initial)
        if not chosen:
            return
        if not self._confirm_discard():
            return
        self._load_game(Path(chosen))

    def _load_game(self, game_dir: Path) -> None:
        sources = find_lang_files(game_dir)
        if not sources:
            self._set_status(f"В папке нет .lang: {game_dir}")
            if not self.smoke:
                messagebox.showwarning(
                    "Локализация не найдена",
                    "В выбранной папке нет файлов .lang.\n"
                    "Убедись, что это папка STALZONE с modassets.",
                )
            return

        self.game_dir = game_dir
        self.game_var.set(str(game_dir))
        self.sources = sources

        labels = [source.label for source in sources]
        if len(set(labels)) != len(labels):
            labels = [f"{source.label} — {source.path.parent}" for source in sources]
        self._source_labels = labels
        self.file_combo["values"] = labels

        index = next(
            (
                i
                for i, source in enumerate(sources)
                if source.pack == "stalker" and source.lang == "ru"
            ),
            next((i for i, source in enumerate(sources) if source.lang == "ru"), 0),
        )
        self.file_combo.current(index)
        self._load_source(sources[index])
        self._set_status(
            f"Игра: {game_dir} · файлов локализации: {len(sources)}"
        )

    def on_file_selected(self, _event: object = None) -> None:
        index = self.file_combo.current()
        if index < 0 or index >= len(self.sources):
            return
        source = self.sources[index]
        if self.current_source and source.path == self.current_source.path:
            return
        if not self._confirm_discard():
            if self.current_source:
                self.file_combo.current(self.sources.index(self.current_source))
            return
        self._load_source(source)

    def _load_source(self, source: LangSource) -> None:
        try:
            lf = LangFile(source.path, source.pack)
        except OSError as error:
            messagebox.showerror("Ошибка чтения", f"Не удалось прочитать файл:\n{error}")
            return

        self.lf = lf
        self.current_source = source
        self.current_category = "Все"
        self.selected_entry = None
        self.sort_col = None
        self.sort_rev = False
        for column in ("value", "key", "category"):
            self.tree.heading(column, text=column_title(column))
        self.file_info.configure(text=str(source.path))
        self._clear_editor()
        self._rebuild_categories()
        self._refresh_rows()
        self._update_dirty()
        self._refresh_ops_info()
        self._refresh_backups()

    def _confirm_discard(self) -> bool:
        if not self.lf or not self.lf.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Несохранённые изменения",
            "В файле есть несохранённые изменения. Сохранить их?",
        )
        if answer is None:
            return False
        if answer:
            return self.save_file()
        return True

    # ---------- категории и таблица ----------

    def _rebuild_categories(self) -> None:
        if not self.lf:
            return
        entries = [
            entry
            for entry in self.lf.entries
            if not self.only_names_var.get() or entry.kind == "name"
        ]
        counts = Counter(entry.category for entry in entries)

        values = ["Все"]
        labels = [f"Все ({len(entries)})"]
        for category in CATEGORY_ORDER:
            if counts.get(category):
                values.append(category)
                labels.append(f"{category} ({counts[category]})")

        self._category_values = values
        current = self.current_category if self.current_category in values else "Все"
        self.current_category = current

        self.cat_list.delete(0, "end")
        for label in labels:
            self.cat_list.insert("end", label)
        self.cat_list.selection_clear(0, "end")
        self.cat_list.selection_set(values.index(current))
        self.cat_list.see(values.index(current))

    def on_category_selected(self, _event: object = None) -> None:
        selection = self.cat_list.curselection()
        if not selection:
            return
        self.current_category = self._category_values[selection[0]]
        self._refresh_rows()

    def on_filter_changed(self) -> None:
        self._rebuild_categories()
        self._refresh_rows()

    def search_items(self) -> None:
        """Найти предмет по названию или ключу во всех категориях."""
        if not self.lf:
            self._set_status("Сначала выбери файл локализации.")
            return
        query = self.search_var.get().strip()
        if not query:
            self.search_entry.focus_set()
            self._set_status("Введи название предмета и нажми «Поиск предметов».")
            return
        self.only_names_var.set(True)
        self.current_category = "Все"
        self._rebuild_categories()
        self._refresh_rows()
        found = len(self.entry_by_iid)
        self._set_status(f"Поиск «{query}» · найдено: {found}")

    def _refresh_rows(self) -> None:
        if not self.lf:
            return
        only_names = self.only_names_var.get()
        query = self.search_var.get().strip().lower()
        category = self.current_category

        rows = [
            entry
            for entry in self.lf.entries
            if (not only_names or entry.kind == "name")
            and (category == "Все" or entry.category == category)
        ]
        if query:
            rows = [
                entry
                for entry in rows
                if query in entry.value.lower() or query in entry.key.lower()
            ]

        if self.sort_col:
            rows.sort(key=self._sort_key, reverse=self.sort_rev)

        total = len(rows)
        shown = rows[:MAX_ROWS]

        selected_key = self.selected_entry.key if self.selected_entry else None
        self.tree.delete(*self.tree.get_children())
        self.entry_by_iid.clear()
        for entry in shown:
            iid = self.tree.insert(
                "", "end", values=(entry.value, entry.key, entry.category)
            )
            self.entry_by_iid[iid] = entry

        if selected_key:
            for iid, entry in self.entry_by_iid.items():
                if entry.key == selected_key:
                    self.tree.selection_set(iid)
                    self.tree.see(iid)
                    break

        suffix = f" · показано {len(shown)} из {total}" if total > len(shown) else ""
        self._set_status(
            f"{category} · записей: {total}{suffix} · {self.current_source.label if self.current_source else ''}"
        )

    def _sort_key(self, entry: Entry):
        if self.sort_col == "value":
            return entry.value.lower()
        if self.sort_col == "key":
            return entry.key.lower()
        return (CATEGORY_INDEX.get(entry.category, 999), entry.value.lower())

    def sort_by(self, column: str) -> None:
        if self.sort_col == column:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_col = column
            self.sort_rev = False
        for name in ("value", "key", "category"):
            arrow = ""
            if name == self.sort_col:
                arrow = " ▼" if self.sort_rev else " ▲"
            self.tree.heading(name, text=column_title(name) + arrow)
        self._refresh_rows()

    # ---------- редактирование ----------

    def on_select(self, _event: object = None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        entry = self.entry_by_iid.get(selection[0])
        if not entry:
            return
        self.selected_entry = entry
        self.key_var.set(entry.key)
        self.old_var.set(entry.original)
        self.new_var.set(entry.value)
        self._set_editor_enabled(True)

    def apply_value(self) -> None:
        if not self.lf or not self.selected_entry:
            return
        value = self.new_var.get()
        if not value:
            messagebox.showwarning("Пустое название", "Название не может быть пустым.")
            self.new_entry.focus_set()
            return
        try:
            self.lf.set_value(self.selected_entry, value)
        except ValueError as error:
            messagebox.showwarning("Недопустимое значение", str(error))
            return
        self._update_row(self.selected_entry)
        self._update_dirty()

    def revert_selected(self) -> None:
        if not self.lf or not self.selected_entry:
            return
        self.lf.revert(self.selected_entry)
        self.new_var.set(self.selected_entry.value)
        self.old_var.set(self.selected_entry.original)
        self._update_row(self.selected_entry)
        self._update_dirty()

    def _update_row(self, entry: Entry) -> None:
        for iid, candidate in self.entry_by_iid.items():
            if candidate is entry:
                self.tree.item(iid, values=(entry.value, entry.key, entry.category))
                break

    def save_file(self) -> bool:
        if not self.lf:
            return False
        try:
            backup = self.lf.save(BACKUP_DIR)
        except OSError as error:
            messagebox.showerror(
                "Не удалось сохранить",
                f"{error}\n\nЗакрой игру и попробуй снова.",
            )
            return False

        self._update_dirty()
        self._refresh_backups()
        if backup is None:
            self._set_status("Изменений нет — сохранять нечего.")
            return True

        self._set_status(f"Сохранено. Резервная копия: {backup}")
        if not self.smoke:
            messagebox.showinfo(
                "Сохранено",
                f"Файл обновлён:\n{self.lf.path}\n\nРезервная копия:\n{backup}\n\n"
                "Перезапусти игру, чтобы увидеть новые названия.",
            )
        return True

    # ---------- экспорт, импорт, копии ----------

    def export_current(self) -> None:
        if not self.lf:
            self._set_status("Сначала выбери файл локализации.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        default_name = f"{self.lf.pack.replace('/', '_')}_{self.lf.lang}.json"
        chosen = filedialog.asksaveasfilename(
            parent=self,
            title="Экспорт локализации",
            initialdir=str(EXPORT_DIR),
            initialfile=default_name,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Все файлы", "*.*")],
        )
        if not chosen:
            return

        entries = [
            entry
            for entry in self.lf.entries
            if not self.export_names_var.get() or entry.kind == "name"
        ]
        payload = {
            "format": "stalzone-loc",
            "version": 1,
            "source": str(self.lf.path),
            "pack": self.lf.pack,
            "lang": self.lf.lang,
            "entries": [{"key": entry.key, "value": entry.value} for entry in entries],
        }
        try:
            Path(chosen).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as error:
            messagebox.showerror("Ошибка экспорта", str(error))
            return

        self._set_status(f"Экспортировано строк: {len(entries)} · {chosen}")
        if not self.smoke:
            messagebox.showinfo(
                "Экспорт готов",
                f"Сохранено строк: {len(entries)}\n\n{chosen}",
            )

    def import_current(self) -> None:
        if not self.lf:
            self._set_status("Сначала выбери файл локализации.")
            return
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        chosen = filedialog.askopenfilename(
            parent=self,
            title="Импорт локализации",
            initialdir=str(EXPORT_DIR),
            filetypes=[("JSON", "*.json"), ("Все файлы", "*.*")],
        )
        if not chosen:
            return
        try:
            payload = json.loads(Path(chosen).read_text(encoding="utf-8"))
            if isinstance(payload, list):
                items = payload
                meta: dict = {}
            elif isinstance(payload, dict):
                items = payload.get("entries", [])
                meta = payload
            else:
                raise ValueError("Ожидается JSON-объект или массив.")
            if not isinstance(items, list):
                raise ValueError("Поле entries должно быть массивом.")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Ошибка импорта", f"Не удалось прочитать JSON:\n{error}")
            return

        values: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict) or "key" not in item or "value" not in item:
                continue
            values[str(item["key"])] = str(item["value"])
        if not values:
            messagebox.showwarning("Импорт", "В файле нет пар key/value.")
            return

        matches = [entry for entry in self.lf.entries if entry.key in values]
        if not matches:
            messagebox.showwarning(
                "Импорт",
                "Ни один ключ из файла не найден в текущей локализации.",
            )
            return

        source = meta.get("source") or meta.get("pack") or "неизвестный файл"
        if not messagebox.askyesno(
            "Импорт",
            f"Источник: {source}\n\n"
            f"Ключей в JSON: {len(values)}\n"
            f"Строк совпало: {len(matches)}\n\n"
            "Применить значения в памяти? Файл на диске изменится только после "
            "нажатия «Сохранить файл».",
        ):
            return

        applied = 0
        failed = 0
        for entry in matches:
            try:
                self.lf.set_value(entry, values[entry.key])
                applied += 1
            except ValueError:
                failed += 1

        self._refresh_rows()
        self._update_dirty()
        self._refresh_ops_info()
        missing = len(set(values) - {entry.key for entry in matches})
        detail = f"обновлено строк: {applied}"
        if missing:
            detail += f" · ключей не найдено: {missing}"
        if failed:
            detail += f" · пропущено: {failed}"
        self._set_status(f"Импорт: {detail}")
        if not self.smoke:
            messagebox.showinfo(
                "Импорт выполнен",
                f"{detail}.\n\nНе забудь сохранить файл на вкладке «Редактор».",
            )

    def create_backup(self) -> None:
        if not self.lf:
            self._set_status("Сначала выбери файл локализации.")
            return
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = f"{self.lf.pack.replace('/', '_')}_{self.lf.lang}_{stamp}.lang"
        chosen = filedialog.asksaveasfilename(
            parent=self,
            title="Сохранить резервную копию",
            initialdir=str(getattr(self, "_last_backup_dir", BACKUP_DIR)),
            initialfile=default_name,
            defaultextension=".lang",
            filetypes=[("Файл локализации", "*.lang"), ("Все файлы", "*.*")],
        )
        if not chosen:
            return
        try:
            backup = self.lf.copy_to(chosen)
        except OSError as error:
            messagebox.showerror("Ошибка копирования", str(error))
            return

        self._last_backup_dir = backup.parent
        self._refresh_backups()
        self._set_status(f"Резервная копия создана: {backup}")
        if not self.smoke:
            extra = ""
            if backup.parent.resolve() != BACKUP_DIR.resolve():
                extra = "\n\nКопия сохранена вне папки backups и не появится в списке."
            messagebox.showinfo(
                "Копия создана",
                f"Текущий файл сохранён:\n{backup}{extra}",
            )

    def rename_backup(self) -> None:
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning("Переименование", "Выбери копию в списке.")
            return
        backup = Path(selection[0])
        if not backup.is_file() or backup.suffix != ".lang":
            return
        new_name = simpledialog.askstring(
            "Переименовать копию",
            "Новое имя файла:",
            initialvalue=backup.name,
            parent=self,
        )
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            return
        if not new_name.lower().endswith(".lang"):
            new_name += ".lang"
        if any(char in new_name for char in ("/", "\\")) or new_name in (".", ".."):
            messagebox.showwarning(
                "Переименование", "Имя должно быть именем файла без пути."
            )
            return
        target = backup.with_name(new_name)
        if target == backup:
            return
        if target.exists() and not messagebox.askyesno(
            "Переименование",
            f"Файл уже существует:\n{target.name}\n\nЗаменить его?",
        ):
            return
        try:
            backup.replace(target)
        except OSError as error:
            messagebox.showerror("Ошибка переименования", str(error))
            return

        self._refresh_backups()
        if self.backup_tree.exists(str(target)):
            self.backup_tree.selection_set(str(target))
            self.backup_tree.see(str(target))
        self._set_status(f"Копия переименована: {target.name}")

    def restore_backup(self) -> None:
        if not self.lf:
            self._set_status("Сначала выбери файл локализации.")
            return
        selection = self.backup_tree.selection()
        if not selection:
            messagebox.showwarning("Восстановление", "Выбери копию в списке.")
            return
        self._restore_path(Path(selection[0]))

    def restore_from_file(self) -> None:
        if not self.lf:
            self._set_status("Сначала выбери файл локализации.")
            return
        chosen = filedialog.askopenfilename(
            parent=self,
            title="Выбрать файл резервной копии",
            initialdir=str(getattr(self, "_last_backup_dir", BACKUP_DIR)),
            filetypes=[("Файл локализации", "*.lang"), ("Все файлы", "*.*")],
        )
        if chosen:
            self._restore_path(Path(chosen))

    def _restore_path(self, backup: Path) -> None:
        if not self.lf or not backup.is_file() or backup.suffix != ".lang":
            return
        if backup.resolve() == self.lf.path.resolve():
            messagebox.showwarning(
                "Восстановление", "Выбранный файл уже открыт в редакторе."
            )
            return
        if self.lf.dirty and not messagebox.askyesno(
            "Несохранённые изменения",
            "В текущем файле есть несохранённые изменения. Они будут потеряны. "
            "Продолжить восстановление?",
        ):
            return
        if not messagebox.askyesno(
            "Восстановление",
            f"Заменить текущий файл копией?\n\n{backup.name}\n\n"
            "Текущая версия будет предварительно сохранена в резервные копии.",
        ):
            return

        try:
            before = self.lf.create_backup(BACKUP_DIR)
            shutil.copy2(backup, self.lf.path)
        except OSError as error:
            messagebox.showerror("Ошибка восстановления", str(error))
            return

        source = self.current_source
        if source:
            self._load_source(source)
        else:
            self._refresh_backups()
        self._set_status(f"Восстановлено из {backup.name}. Предыдущая версия: {before}")
        if not self.smoke:
            messagebox.showinfo(
                "Восстановлено",
                f"Файл заменён копией:\n{backup.name}\n\n"
                f"Предыдущая версия сохранена:\n{before}\n\n"
                "Перезапусти игру, чтобы увидеть изменения.",
            )

    def open_backups(self) -> None:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(BACKUP_DIR)  # type: ignore[attr-defined]
        except OSError as error:
            messagebox.showerror("Ошибка", str(error))

    def _refresh_ops_info(self) -> None:
        if not self.lf or not self.current_source:
            self.ops_file_var.set("Файл не выбран")
            self.ops_path_var.set("")
            self.ops_dirty_var.set("")
            return
        self.ops_file_var.set(self.current_source.label)
        self.ops_path_var.set(str(self.lf.path))
        count = sum(1 for entry in self.lf.entries if entry.value != entry.original)
        self.ops_dirty_var.set(
            "Изменений нет" if not count else f"Несохранённых изменений: {count}"
        )

    def _refresh_backups(self) -> None:
        tree = getattr(self, "backup_tree", None)
        if tree is None:
            return
        tree.delete(*tree.get_children())
        files: list[Path] = []
        if BACKUP_DIR.exists():
            files = sorted(
                BACKUP_DIR.glob("*.lang"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        self.ops_backup_count_var.set(f"Копий в папке: {len(files)}")
        if not files:
            tree.insert("", "end", iid="__empty__", values=("Копий пока нет", "", ""))
            return
        for path in files[:500]:
            try:
                stat = path.stat()
            except OSError:
                continue
            tree.insert(
                "",
                "end",
                iid=str(path),
                values=(
                    path.name,
                    datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M:%S"),
                    f"{stat.st_size / 1024:.1f} КБ",
                ),
            )

    def _clear_editor(self) -> None:
        self.key_var.set("")
        self.old_var.set("")
        self.new_var.set("")
        self._set_editor_enabled(False)

    def _set_editor_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.new_entry.configure(state=state)
        self.save_button.configure(state="normal" if self.lf else "disabled")

    def _update_dirty(self) -> None:
        if not self.lf:
            self.dirty_var.set("Файл не выбран")
            self._refresh_ops_info()
            return
        count = sum(1 for entry in self.lf.entries if entry.value != entry.original)
        self.dirty_var.set(
            "Изменений нет" if not count else f"Изменено названий: {count}"
        )
        self.title(
            "STALZONE Name Editor"
            + (" *" if count else "")
            + (f" — {self.current_source.label}" if self.current_source else "")
        )
        self._refresh_ops_info()

    def _on_search_changed(self, *_args: object) -> None:
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(220, self._refresh_rows)

    def _set_status(self, text: str) -> None:
        if hasattr(self, "status_var"):
            self.status_var.set(text)

    def on_close(self) -> None:
        if self._confirm_discard():
            self.destroy()


def column_title(column: str) -> str:
    return {"value": "Название", "key": "Ключ", "category": "Тип"}[column]


def main() -> None:
    smoke = "--smoke" in sys.argv
    app = LocEditorApp(smoke=smoke)
    if smoke:
        app.after(2500, app.destroy)
    app.mainloop()


if __name__ == "__main__":
    main()
