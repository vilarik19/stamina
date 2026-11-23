from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont

from stamina.core.metrics import compute_result
from stamina.core.progress import ProgressStore
from stamina.core.textgen import generate_practice_text
from stamina.core.users import User, UserStore, sanitize_username


@dataclass(frozen=True)
class Lesson:
    id: str
    title: str
    layout: str
    text: str
    kind: str = "fixed"  # fixed|digits


class AppState:
    def __init__(self, user: User) -> None:
        self.data_dir = Path.cwd() / "stamina_data"
        self.user_store = UserStore(self.data_dir)
        self.user = user
        self.progress = ProgressStore(self.data_dir / "users" / sanitize_username(user.username))
        self.lesson_data = _load_lessons()
        self.layouts: Dict[str, Dict[str, Any]] = self.lesson_data["layouts"]
        self.lessons: List[Lesson] = [
            Lesson(**item) for item in self.lesson_data.get("lessons", [])
        ]
        self.active_layout = "ru" if "ru" in self.layouts else next(iter(self.layouts.keys()), "ru")

    def switch_user(self, user: User) -> None:
        self.user = user
        self.progress = ProgressStore(self.data_dir / "users" / sanitize_username(user.username))


def _load_lessons() -> Dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / "lessons_ru.json"
    return json.loads(path.read_text(encoding="utf-8"))


class MainWindow(ttk.Frame):
    def __init__(self, master: tk.Tk, state: AppState) -> None:
        super().__init__(master)
        self.state = state
        self.master.title("Тренажёр слепой печати")
        self.master.geometry("980x640")
        _maximize(self.master)
        self.pack(fill="both", expand=True)

        self._build_layout()

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        top.columnconfigure(2, weight=1)

        ttk.Label(top, text="Тренажёр слепой печати", font=("Segoe UI", 27, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(top, text=f"Пользователь: {self.state.user.username}").grid(row=1, column=0, sticky="w")

        ttk.Label(top, text="Раскладка:").grid(row=0, column=1, sticky="e", padx=(20, 6))
        self.user_label = top.grid_slaves(row=1, column=0)[0]
        self.layout_var = tk.StringVar(value=self.state.active_layout)
        layout_names = {k: v.get("name", k) for k, v in self.state.layouts.items()}
        self.layout_combo = ttk.Combobox(
            top,
            textvariable=self.layout_var,
            values=list(layout_names.keys()),
            width=10,
            state="readonly",
        )
        self.layout_combo.grid(row=0, column=2, sticky="w")
        self.layout_combo.bind("<<ComboboxSelected>>", self._on_layout_changed)

        ttk.Button(top, text="Статистика", command=self._open_stats).grid(row=0, column=3, padx=(12, 0))
        ttk.Button(top, text="Сменить пользователя", command=self._switch_user).grid(row=0, column=4, padx=(8, 0))

        body = ttk.Notebook(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.lesson_tab = LessonTab(body, self.state, on_start=self._start_lesson)
        self.practice_tab = PracticeTab(body, self.state, on_start=self._start_practice)
        body.add(self.lesson_tab, text="Уроки")
        body.add(self.practice_tab, text="Тренировка")

    def _on_layout_changed(self, _evt: object = None) -> None:
        self.state.active_layout = self.layout_var.get()
        self.user_label.configure(text=f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ: {self.state.user.username}")
        self.user_label.configure(text=f"User: {self.state.user.username}")
        self.lesson_tab.refresh()
        self.practice_tab.refresh()

    def _start_lesson(self, lesson: Lesson) -> None:
        if getattr(lesson, "kind", "fixed") == "digits":
            lesson = Lesson(
                id=lesson.id,
                title=lesson.title,
                layout=lesson.layout,
                text=_generate_digits_text(groups=18, group_size=5),
                kind=lesson.kind,
            )
        TypingWindow(self.master, self.state, mode="lesson", lesson=lesson)

    def _start_practice(self, allowed: str) -> None:
        text = generate_practice_text(allowed, word_count=30)
        lesson = Lesson(id="practice", title="Тренировка", layout=self.state.active_layout, text=text)
        TypingWindow(self.master, self.state, mode="practice", lesson=lesson)

    def _open_stats(self) -> None:
        StatsWindow(self.master, self.state)

    def _switch_user(self) -> None:
        # Окно выбора пользователя должно быть без масштабирования шрифтов.
        # Также нельзя запускать вложенный mainloop на основном root (VS Code/Windows могут зависать).
        user = pick_user_standalone(self.state.user_store)
        if user is None:
            return
        if user.username == self.state.user.username:
            return
        self.state.switch_user(user)
        top_frames = self.grid_slaves(row=0, column=0)
        if top_frames:
            user_labels = top_frames[0].grid_slaves(row=1, column=0)
            if user_labels:
                user_labels[0].configure(text=f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ: {self.state.user.username}")
        self.lesson_tab.refresh()
        self.practice_tab.refresh()


class LessonTab(ttk.Frame):
    def __init__(self, master: ttk.Notebook, state: AppState, *, on_start) -> None:
        super().__init__(master)
        self.state = state
        self.on_start = on_start
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(self, text="Выбери урок и нажми «Начать».").grid(row=0, column=0, sticky="w", padx=10, pady=10)

        self.tree = ttk.Treeview(self, columns=("title", "layout"), show="headings", height=14)
        self.tree.heading("title", text="Урок")
        self.tree.heading("layout", text="Раскладка")
        self.tree.column("title", width=720, anchor="w")
        self.tree.column("layout", width=120, anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        bottom = ttk.Frame(self)
        bottom.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom.columnconfigure(0, weight=1)
        self.hint = ttk.Label(bottom, text="")
        self.hint.grid(row=0, column=0, sticky="w")
        ttk.Button(bottom, text="Начать", command=self._start_selected).grid(row=0, column=1, sticky="e")

        self.refresh()
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update_hint())
        self.tree.bind("<Double-1>", lambda _e: self._start_selected())

    def refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        active = self.state.active_layout
        for lesson in self.state.lessons:
            if lesson.layout != active:
                continue
            self.tree.insert("", "end", iid=lesson.id, values=(lesson.title, lesson.layout))
        self._update_hint()

    def _update_hint(self) -> None:
        selected = self.tree.selection()
        if not selected:
            self.hint.configure(text="Подсказка: начинай с домашнего ряда и работай без спешки.")
            return
        lesson = next((l for l in self.state.lessons if l.id == selected[0]), None)
        if not lesson:
            return
        self.hint.configure(text=f"Длина текста: {len(lesson.text)} символов")

    def _start_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        lesson = next((l for l in self.state.lessons if l.id == selected[0]), None)
        if lesson:
            self.on_start(lesson)


class PracticeTab(ttk.Frame):
    def __init__(self, master: ttk.Notebook, state: AppState, *, on_start) -> None:
        super().__init__(master)
        self.state = state
        self.on_start = on_start
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        ttk.Label(self, text="Символы для тренировки (можно менять):").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        self.allowed_var = tk.StringVar(value=self._default_allowed())
        self.allowed_entry = ttk.Entry(self, textvariable=self.allowed_var)
        self.allowed_entry.grid(row=1, column=0, sticky="ew", padx=10)

        ttk.Button(self, text="Начать тренировку", command=self._start).grid(row=1, column=1, padx=10)

        self.note = ttk.Label(
            self,
            text="Совет: сначала тренируй 8 клавиш домашнего ряда, затем добавляй новые.",
            foreground="#555",
        )
        self.note.grid(row=3, column=0, sticky="w", padx=10, pady=10)

    def refresh(self) -> None:
        self.allowed_var.set(self._default_allowed())

    def _default_allowed(self) -> str:
        layout = self.state.layouts.get(self.state.active_layout, {})
        return layout.get("allowed_default", "asdf jkl;")

    def _start(self) -> None:
        allowed = self.allowed_var.get()
        if not allowed.strip():
            messagebox.showwarning("Пусто", "Укажи хотя бы один символ для генерации.")
            return
        self.on_start(allowed)


class TypingWindow(tk.Toplevel):
    def __init__(self, master: tk.Tk, state: AppState, *, mode: str, lesson: Lesson) -> None:
        super().__init__(master)
        self.state = state
        self.mode = mode
        self.lesson = lesson
        self.target = lesson.text
        self.typed = ""
        self.started_at_ms: int | None = None
        self._finished = False

        self.title(f"{lesson.title} — печатай без просмотра клавиатуры")
        self.geometry("980x640")
        _center_window(self, 860, 520)
        try:
            self.transient(master)
            self.lift()
            self.attributes("-topmost", True)
            self.after(200, lambda: self.attributes("-topmost", False))
            self.focus_force()
            self.grab_set()
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build()
        self._render()
        self._focus_input()

    def _close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text=self.lesson.title, font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        self.info_label = ttk.Label(header, text="")
        self.info_label.grid(row=0, column=1, sticky="e")

        self.text = tk.Text(self, wrap="word", height=12, padx=12, pady=12, font=("Consolas", 21))
        self.text.grid(row=1, column=0, sticky="nsew", padx=12)
        self.text.configure(state="disabled")

        self.text.tag_configure("correct", foreground="#1a7f37")
        self.text.tag_configure("wrong", foreground="#cf222e")
        self.text.tag_configure("next", background="#ffd8a8")
        self.text.tag_configure("rest", foreground="#111")

        bottom = ttk.Frame(self)
        bottom.grid(row=3, column=0, sticky="ew", padx=12, pady=12)
        bottom.columnconfigure(0, weight=1)

        self.entry_var = tk.StringVar()
        self.entry = ttk.Entry(bottom, textvariable=self.entry_var)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<KeyPress>", self._on_keypress)
        self.entry.bind("<KeyRelease>", self._on_changed)

        ttk.Button(bottom, text="Заново", command=self._reset).grid(row=0, column=1, padx=(10, 0))
        ttk.Button(bottom, text="Закрыть", command=self.destroy).grid(row=0, column=2, padx=(8, 0))

        hint = ttk.Label(
            self,
            text="Старт: печатай в поле внизу. Таймер начнётся с первого символа. Backspace разрешён.",
            foreground="#555",
        )
        hint.grid(row=4, column=0, sticky="w", padx=12, pady=(0, 12))

    def _focus_input(self) -> None:
        self.after(50, lambda: self.entry.focus_set())

    def _reset(self) -> None:
        self.started_at_ms = None
        self.typed = ""
        self.entry_var.set("")
        self._render()
        self._focus_input()

    def _on_keypress(self, _evt: tk.Event) -> None:
        if self.started_at_ms is None:
            self.started_at_ms = self._now_ms()

    def _on_changed(self, _evt: tk.Event) -> None:
        self.typed = self.entry_var.get()
        self._render()
        # Завершаем после ввода последнего символа, даже если есть ошибки.
        if not self._finished and len(self.typed) >= len(self.target):
            self._finish()

    def _finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        if self.started_at_ms is None:
            # Если пользователь вставил текст сразу целиком, считаем стартом текущий момент.
            self.started_at_ms = self._now_ms()
        if self.started_at_ms is None:
            return
        # Ограничиваем ввод длиной эталонного текста.
        if len(self.typed) > len(self.target):
            self.typed = self.typed[: len(self.target)]
            self.entry_var.set(self.typed)
        duration_sec = (self._now_ms() - self.started_at_ms) / 1000.0
        result = compute_result(self.target, self.typed, duration_sec)
        self.state.progress.add_attempt(
            mode=self.mode,
            lesson_id=None if self.mode == "practice" else self.lesson.id,
            layout=self.lesson.layout,
            result=result,
        )
        # Модальный результат после последнего символа.
        self.entry.configure(state="disabled")
        try:
            self.grab_release()
        except Exception:
            pass
        dialog = ResultsWindow(self, self.lesson.title, result)
        self.wait_window(dialog)
        self._close()

    def _render(self) -> None:
        correct_upto = 0
        wrong_upto = 0
        for idx, ch in enumerate(self.typed):
            if idx >= len(self.target):
                wrong_upto = idx + 1
                break
            if ch == self.target[idx]:
                correct_upto = idx + 1
            else:
                wrong_upto = idx + 1
                break

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.target)
        self.text.tag_add("rest", "1.0", "end")

        if correct_upto > 0:
            self.text.tag_add("correct", f"1.0", f"1.0+{correct_upto}c")
        if wrong_upto > correct_upto:
            self.text.tag_add("wrong", f"1.0+{correct_upto}c", f"1.0+{wrong_upto}c")

        next_pos = min(len(self.target), len(self.typed))
        if next_pos < len(self.target):
            self.text.tag_add("next", f"1.0+{next_pos}c", f"1.0+{min(next_pos+1, len(self.target))}c")

        self.text.configure(state="disabled")

        duration_sec = 0.0
        if self.started_at_ms is not None:
            duration_sec = (self._now_ms() - self.started_at_ms) / 1000.0
        interim = compute_result(self.target, self.typed, max(duration_sec, 0.0001 if self.typed else 0.0))
        self.info_label.configure(
            text=f"WPM {interim.wpm:.1f} | Точность {interim.accuracy*100:.1f}% | Ошибки {interim.errors}"
        )

    def _now_ms(self) -> int:
        return int(self.tk.call("clock", "milliseconds"))


class ResultsWindow(tk.Toplevel):
    def __init__(self, master: tk.Misc, title: str, result) -> None:
        super().__init__(master)
        self.title("Результат")
        self.geometry("520x360")
        _center_window(self, 520, 360)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        try:
            self.transient(master)
            self.grab_set()
            self.lift()
            self.attributes("-topmost", True)
            self.after(200, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except Exception:
            pass
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        # Центрируем блок целиком по окну.
        content = ttk.Frame(frame)
        content.pack(expand=True)
        content.columnconfigure(0, weight=1)

        ttk.Label(content, text=title, font=("Segoe UI", 18, "bold"), justify="center", anchor="center").grid(
            row=0, column=0, sticky="ew", pady=(0, 14)
        )
        for i, line in enumerate(
            [
                f"Время: {result.duration_sec:.1f} сек",
                f"Скорость: {result.wpm:.1f} WPM / {result.cpm:.0f} CPM",
                f"Точность: {result.accuracy*100:.1f}%",
                f"Ошибки: {result.errors}",
            ],
            start=1,
        ):
            ttk.Label(content, text=line, justify="center", anchor="center").grid(row=i, column=0, sticky="ew", pady=2)

        ttk.Button(content, text="Закрыть", command=self.destroy).grid(row=10, column=0, pady=(16, 0))


def _generate_digits_text(*, groups: int, group_size: int, seed: int | None = None) -> str:
    rng = random.Random(seed)
    parts: list[str] = []
    for _ in range(max(1, int(groups))):
        parts.append("".join(str(rng.randint(0, 9)) for _ in range(max(1, int(group_size)))))
    return " ".join(parts)


class StatsWindow(tk.Toplevel):
    def __init__(self, master: tk.Tk, state: AppState) -> None:
        super().__init__(master)
        self.state = state
        self.title("Статистика")
        self.geometry("860x520")
        _maximize(self)
        try:
            self.transient(master)
            self.grab_set()
            self.lift()
            self.focus_force()
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._close)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text=f"Пользователь: {self.state.user.username}", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(header, text="Обновить", command=self._refresh).grid(row=0, column=1, sticky="e")

        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.attempts_tab = ttk.Frame(self.notebook)
        self.records_tab = ttk.Frame(self.notebook)
        self.attempts_tab.columnconfigure(0, weight=1)
        self.attempts_tab.rowconfigure(0, weight=1)
        self.records_tab.columnconfigure(0, weight=1)
        self.records_tab.rowconfigure(0, weight=1)
        self.notebook.add(self.attempts_tab, text="Попытки")
        self.notebook.add(self.records_tab, text="Рекорды")

        self.attempts_tree = ttk.Treeview(
            self.attempts_tab,
            columns=("ts", "mode", "lesson", "layout", "wpm", "acc", "errors", "dur"),
            show="headings",
        )
        for key, title, width in [
            ("ts", "UTC", 180),
            ("mode", "Режим", 110),
            ("lesson", "Урок", 220),
            ("layout", "Раскладка", 100),
            ("wpm", "WPM", 90),
            ("acc", "Точность", 110),
            ("errors", "Ошибки", 90),
            ("dur", "Сек", 90),
        ]:
            self.attempts_tree.heading(key, text=title)
            self.attempts_tree.column(key, width=width, anchor="center" if key != "lesson" else "w")
        self.attempts_tree.grid(row=0, column=0, sticky="nsew")

        self.records_tree = ttk.Treeview(
            self.records_tab,
            columns=("key", "best_wpm", "best_acc", "best_errors", "attempts"),
            show="headings",
        )
        for key, title, width, anchor in [
            ("key", "Урок / режим", 420, "w"),
            ("best_wpm", "Лучший WPM", 140, "center"),
            ("best_acc", "Лучшая точность", 160, "center"),
            ("best_errors", "Минимум ошибок", 160, "center"),
            ("attempts", "Попыток", 120, "center"),
        ]:
            self.records_tree.heading(key, text=title)
            self.records_tree.column(key, width=width, anchor=anchor)
        self.records_tree.grid(row=0, column=0, sticky="nsew")

        self._refresh()

    def _close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _refresh(self) -> None:
        for item in self.attempts_tree.get_children():
            self.attempts_tree.delete(item)
        for item in self.records_tree.get_children():
            self.records_tree.delete(item)
        data = self.state.progress.load()
        attempts = list(data.get("attempts", []))[-200:]

        # Попытки
        if not attempts:
            self.attempts_tree.insert("", "end", iid="empty", values=("—", "—", "—", "—", "0.0", "—", "0", "0.0"))
        else:
            for i, a in enumerate(reversed(attempts)):
                dur = float(a.get("duration_sec", 0.0))
                typed = int(a.get("typed_chars", 0))
                wpm = ((typed / 5.0) / dur) * 60.0 if dur > 0 else 0.0
                acc = (int(a.get("correct_chars", 0)) / typed) if typed > 0 else 1.0
                self.attempts_tree.insert(
                    "",
                    "end",
                    iid=str(i),
                    values=(
                        a.get("timestamp_utc", ""),
                        a.get("mode", ""),
                        a.get("lesson_id", "") or "—",
                        a.get("layout", ""),
                        f"{wpm:.1f}",
                        f"{acc*100:.1f}%",
                        a.get("errors", 0),
                        f"{dur:.1f}",
                    ),
                )

        # Рекорды (по уроку/режиму)
        def record_key(a: Dict[str, Any]) -> str:
            mode = str(a.get("mode", "") or "")
            lesson_id = str(a.get("lesson_id", "") or "")
            if mode == "practice" or lesson_id in ("", "—"):
                return "Тренировка"
            # Пытаемся найти красивое название урока.
            lesson = next((l for l in self.state.lessons if l.id == lesson_id), None)
            return lesson.title if lesson else f"Урок: {lesson_id}"

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for a in attempts:
            grouped.setdefault(record_key(a), []).append(a)

        for i, (key, group) in enumerate(sorted(grouped.items(), key=lambda x: x[0].lower())):
            best_wpm = 0.0
            best_acc = 0.0
            min_errors: int | None = None
            for a in group:
                dur = float(a.get("duration_sec", 0.0))
                typed = int(a.get("typed_chars", 0))
                wpm = ((typed / 5.0) / dur) * 60.0 if dur > 0 else 0.0
                acc = (int(a.get("correct_chars", 0)) / typed) if typed > 0 else 1.0
                errors = int(a.get("errors", 0))
                best_wpm = max(best_wpm, wpm)
                best_acc = max(best_acc, acc)
                min_errors = errors if min_errors is None else min(min_errors, errors)

            self.records_tree.insert(
                "",
                "end",
                iid=f"r{i}",
                values=(
                    key,
                    f"{best_wpm:.1f}",
                    f"{best_acc*100:.1f}%",
                    str(min_errors if min_errors is not None else 0),
                    str(len(group)),
                ),
            )


def _apply_theme(root: tk.Tk, *, scale_fonts: bool) -> None:
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    if not scale_fonts:
        return
    try:
        scale = 1.5  # было x2, уменьшаем на 25%
        for name in ["TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont", "TkTooltipFont"]:
            try:
                f = tkfont.nametofont(name)
            except Exception:
                continue
            size = int(f.cget("size") or 10)
            if size > 0:
                f.configure(size=max(8, int(size * scale)))
        # Treeview: делаем строки выше, иначе текст обрежется.
        try:
            style = ttk.Style(root)
            base = tkfont.nametofont("TkDefaultFont")
            style.configure("Treeview", rowheight=int(base.cget("size")) + 14)
        except Exception:
            pass
    except Exception:
        pass


def _center_window(win: tk.Toplevel | tk.Tk, width: int, height: int) -> None:
    try:
        win.update_idletasks()
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = max(0, int((screen_w - width) / 2))
        y = max(0, int((screen_h - height) / 2))
        win.geometry(f"{width}x{height}+{x}+{y}")
    except Exception:
        pass


def _maximize(win: tk.Toplevel | tk.Tk) -> None:
    try:
        win.state("zoomed")
        return
    except Exception:
        pass
    try:
        w = win.winfo_screenwidth()
        h = win.winfo_screenheight()
        win.geometry(f"{w}x{h}+0+0")
    except Exception:
        pass


def main(*, user: User | None = None) -> None:
    # Отдельный скрытый root для выбора пользователя:
    # так окно выбора точно появляется и не остаётся "лишнего" окна.
    if user is None:
        # Не withdraw(): на некоторых системах Toplevel на скрытом root может не отрисоваться.
        # Делаем root "невидимым": 1x1 и прозрачным.
        store = UserStore(Path.cwd() / "stamina_data")
        user = pick_user_standalone(store)
        if user is None:
            return

    root = tk.Tk()
    _apply_theme(root, scale_fonts=True)
    state = AppState(user)
    MainWindow(root, state)
    try:
        root.lift()
        root.attributes("-topmost", True)
        root.after(200, lambda: root.attributes("-topmost", False))
        root.focus_force()
    except Exception:
        pass
    root.mainloop()


def pick_user(master: tk.Tk, store: UserStore) -> User | None:
    return pick_user_standalone(store)
    dialog = UserPicker(master, store)

    # Надёжнее, чем wait_window без mainloop (в некоторых IDE окно может не "всплыть").
    def _on_close() -> None:
        try:
            master.quit()
        except Exception:
            pass

    dialog.bind("<Destroy>", lambda e: _on_close() if e.widget is dialog else None)
    try:
        master.after(0, dialog._bring_to_front)  # type: ignore[attr-defined]
    except Exception:
        pass
    master.mainloop()
    return dialog.result


def pick_user_standalone(store: UserStore) -> User | None:
    """Выбор пользователя в отдельном root без масштабирования шрифтов."""
    picker = UserPickerRoot(store)
    picker.mainloop()
    return picker.result


class UserPickerRoot(tk.Tk):
    def __init__(self, store: UserStore) -> None:
        super().__init__()
        _apply_theme(self, scale_fonts=False)
        self.store = store
        self.result: User | None = None
        self.selected_username: str | None = None
        self._cancel_allowed = True

        self.title("Выбор пользователя")
        self.geometry("420x360")
        self.resizable(False, False)
        _center_window(self, 420, 360)
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(100, lambda: self.attributes("-topmost", False))
            self.grab_set()
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Пользователь", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.help_label = ttk.Label(frame, text="", foreground="#555")
        self.help_label.grid(row=0, column=0, sticky="e")

        self.listbox = tk.Listbox(frame, height=10, exportselection=False)
        self.listbox.grid(row=1, column=0, sticky="nsew", pady=(10, 8))

        ttk.Label(frame, text="Новый пользователь:").grid(row=2, column=0, sticky="w", pady=(10, 4))
        self.new_var = tk.StringVar()
        self.new_entry = ttk.Entry(frame, textvariable=self.new_var)
        self.new_entry.grid(row=3, column=0, sticky="ew")

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(0, weight=1)

        ttk.Button(buttons, text="Выбрать", command=self._select).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(buttons, text="Создать", command=self._create).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(buttons, text="Отмена", command=self._cancel).grid(row=0, column=3, padx=(8, 0))

        self.listbox.bind("<<ListboxSelect>>", self._on_select_changed)
        self.listbox.bind("<Double-1>", lambda _e: self._select())
        self.bind("<Escape>", lambda _e: self._cancel())
        self.after(50, lambda: self.new_entry.focus_set())

        self._reload()
        if self.listbox.size() == 0:
            self._cancel_allowed = False
            self.help_label.configure(text="Создай первого пользователя")
            messagebox.showinfo("Первый запуск", "Создай пользователя (кнопка «Создать»), затем выбери его.")
        else:
            self.help_label.configure(text="Выбери или создай пользователя")

        self._bring_to_front()

    def _bring_to_front(self) -> None:
        try:
            _center_window(self, 420, 360)
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(100, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except Exception:
            pass

    def _reload(self) -> None:
        self.listbox.delete(0, "end")
        for u in self.store.list_users():
            self.listbox.insert("end", u.username)
        if self.listbox.size() > 0:
            self.listbox.selection_set(0)
            self.selected_username = self.listbox.get(0)

    def _on_select_changed(self, _evt: tk.Event) -> None:
        selection = self.listbox.curselection()
        if selection:
            self.selected_username = self.listbox.get(selection[0])

    def _select(self) -> None:
        if self.listbox.size() == 0:
            messagebox.showinfo("Нет пользователей", "Сначала создай пользователя.")
            return
        selection = self.listbox.curselection()
        if selection:
            username = self.listbox.get(selection[0])
        elif self.selected_username:
            username = self.selected_username
        else:
            return
        self.result = User(username=username)
        self._close()

    def _create(self) -> None:
        name = self.new_var.get()
        safe = sanitize_username(name)
        if not safe.strip():
            messagebox.showwarning("мя", "Введи имя пользователя.")
            return
        user = self.store.add_user(safe)
        self._reload()
        for i in range(self.listbox.size()):
            if self.listbox.get(i) == user.username:
                self.listbox.selection_clear(0, "end")
                self.listbox.selection_set(i)
                break
        self.new_var.set("")
        self._cancel_allowed = True

    def _cancel(self) -> None:
        if not self._cancel_allowed:
            messagebox.showinfo("Нужно создать", "Создай пользователя, чтобы продолжить.")
            return
        self.result = None
        self._close()

    def _close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

