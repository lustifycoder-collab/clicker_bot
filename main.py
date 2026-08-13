"""
Главный GUI бота-кликера (Tkinter).

Вкладки:
  1. Управление — статус, старт/стоп, горячая клавиша, лог.
  2. Настройки — отдых, линия, до какого лвла, лвл забора, задержка.
  3. Калибровка — выбор линии, калибровка точек по уровням и забора.

Кроссплатформенно: Windows + macOS.

Потокобезопасность: все обращения к Tkinter-виджетам идут только из
главного потока через очередь _ui_queue + root.after.
"""
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import config
import storage
from bot_engine import BotEngine
from hotkey import HotkeyManager


def _log_ts(msg):
    return f"[{time.strftime('%H:%M:%S')}] {msg}"


class ClickerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Бот-кликер — Telegram Mini App")
        self.root.geometry("720x560")
        self.root.resizable(False, False)

        # очередь для безопасного обновления UI из других потоков
        self._ui_queue = queue.Queue()
        self.root.after(100, self._poll_ui)

        # движок и хоткей
        self.engine = BotEngine(on_status=self._enqueue_status, on_log=self._enqueue_log,
                               on_stopped=self._enqueue_engine_stopped)
        self._calibrating = False
        self._calib_timer = None
        self.hotkey = None

        # состояние
        self.settings = dict(config.DEFAULT_SETTINGS)
        saved = storage.load_settings()
        if saved:
            # #5: валидируем типы — повреждённые значения из JSON не должны
            # ронять создание виджетов (IntVar/DoubleVar) на старте.
            try:
                self.settings["line"] = str(saved["line"])
                self.settings["max_level"] = int(saved["max_level"])
                self.settings["collect_level"] = int(saved["collect_level"])
                self.settings["rest_after_collect"] = int(saved["rest_after_collect"])
                self.settings["step_delay"] = float(saved["step_delay"])
                self.settings["hotkey"] = str(saved["hotkey"])
            except (KeyError, TypeError, ValueError):
                # любое испорченное поле — оставляем дефолт, применяем частично
                pass

        self.var_line = tk.StringVar(value=self.settings["line"])
        self.var_max_level = tk.IntVar(value=self.settings["max_level"])
        self.var_collect_level = tk.IntVar(value=self.settings["collect_level"])
        self.var_rest = tk.IntVar(value=self.settings["rest_after_collect"])
        self.var_delay = tk.DoubleVar(value=self.settings["step_delay"])
        self.var_hotkey = tk.StringVar(value=self.settings["hotkey"])
        self.var_status = tk.StringVar(value="Готов")

        self._build_ui()
        self._start_hotkey()

    # ---------- UI ----------
    def _build_ui(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_control = self._build_control(nb)
        self.tab_settings = self._build_settings(nb)
        self.tab_calib = self._build_calibration(nb)

    def _build_control(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Управление")

        # статус
        st = ttk.Label(tab, textvariable=self.var_status, font=("", 13, "bold"))
        st.pack(pady=(12, 4))

        # кнопки
        btns = ttk.Frame(tab)
        btns.pack(pady=6)
        self.btn_start = ttk.Button(btns, text="▶ Старт", command=self._toggle)
        self.btn_start.pack(side="left", padx=5)
        self.btn_stop = ttk.Button(btns, text="■ Стоп", command=self._stop)
        self.btn_stop.pack(side="left", padx=5)

        # горячая клавиша
        hk = ttk.Frame(tab)
        hk.pack(pady=6)
        ttk.Label(hk, text="Горячая клавиша (вкл/выкл):").pack(side="left")
        self.ent_hotkey = ttk.Entry(hk, textvariable=self.var_hotkey, width=6)
        self.ent_hotkey.pack(side="left", padx=6)
        ttk.Button(hk, text="Применить", command=self._apply_hotkey).pack(side="left")

        # лог
        ttk.Label(tab, text="Лог:").pack(anchor="w", padx=10)
        self.txt_log = tk.Text(tab, height=18, state="disabled")
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        return tab

    def _build_settings(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Настройки")

        form = ttk.Frame(tab)
        form.pack(padx=20, pady=16, anchor="w")

        # линия
        ttk.Label(form, text="Линия:").grid(row=0, column=0, sticky="w", pady=4)
        line_box = ttk.Combobox(
            form, textvariable=self.var_line, state="readonly", width=20,
            values=[config.LINE_LEFT, config.LINE_MANUAL, config.LINE_RIGHT],
        )
        line_box.grid(row=0, column=1, sticky="w", pady=4)

        # до какого лвла
        ttk.Label(form, text="До какого лвла:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Spinbox(form, from_=1, to=config.MAX_LEVEL, textvariable=self.var_max_level,
                    width=5).grid(row=1, column=1, sticky="w", pady=4)

        # лвл забора
        ttk.Label(form, text="Лвл забора денег:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Spinbox(form, from_=1, to=config.MAX_LEVEL, textvariable=self.var_collect_level,
                    width=5).grid(row=2, column=1, sticky="w", pady=4)

        # отдых
        ttk.Label(form, text="Отдых после забора (сек):").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Spinbox(form, from_=0, to=3600, textvariable=self.var_rest,
                    width=8).grid(row=3, column=1, sticky="w", pady=4)

        # задержка между уровнями
        ttk.Label(form, text="Задержка между кликами (сек):").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Spinbox(form, from_=0.1, to=10, increment=0.1, textvariable=self.var_delay,
                    width=8).grid(row=4, column=1, sticky="w", pady=4)

        ttk.Button(tab, text="💾 Сохранить настройки", command=self._save_settings).pack(pady=10)

        # таблица уровней (вшита, не редактируется)
        ttk.Label(tab, text="Таблица уровней (авто):").pack(anchor="w", padx=20)
        tree = ttk.Treeview(tab, columns=("kef", "cells"), show="headings", height=12)
        tree.heading("kef", text="Кэф")
        tree.heading("cells", text="Ячеек")
        tree.column("kef", width=120, anchor="center")
        tree.column("cells", width=120, anchor="center")
        for lv, (kef, cells) in config.LEVELS.items():
            tree.insert("", "end", iid=str(lv), values=(f"{lv}: {kef}x", cells))
        tree.pack(fill="both", expand=True, padx=20, pady=(4, 12))
        return tab

    def _build_calibration(self, nb):
        tab = ttk.Frame(nb)
        nb.add(tab, text="Калибровка")

        top = ttk.Frame(tab)
        top.pack(padx=16, pady=10, fill="x")
        ttk.Label(top, text="Линия:").pack(side="left")
        self.cal_line = ttk.Combobox(top, state="readonly", width=14,
                                     values=[config.LINE_LEFT, config.LINE_MANUAL, config.LINE_RIGHT])
        self.cal_line.set(config.LINE_MANUAL)
        self.cal_line.pack(side="left", padx=6)

        self.lbl_cal_hint = ttk.Label(tab, text="Выберите линию и уровень, затем нажмите «Калибровать».\n"
                                                "Бот даст 15 сек: наведите курсор на точку и кликните ЛКМ.",
                                      foreground="#555")
        self.lbl_cal_hint.pack(pady=4)

        # список уровней
        mid = ttk.Frame(tab)
        mid.pack(fill="both", expand=True, padx=16)
        self.cal_tree = ttk.Treeview(mid, columns=("point",), show="headings", height=12)
        self.cal_tree.heading("point", text="Точка")
        self.cal_tree.column("point", width=200, anchor="center")
        for lv in range(1, config.MAX_LEVEL + 1):
            self.cal_tree.insert("", "end", iid=f"level_{lv}", values=(f"Уровень {lv}",))
        self.cal_tree.insert("", "end", iid="collect", values=("Забрать деньги",))
        self.cal_tree.pack(fill="both", expand=True)

        btns = ttk.Frame(tab)
        btns.pack(pady=10)
        ttk.Button(btns, text="🎯 Калибровать выбранное", command=self._calibrate_selected).pack(side="left", padx=5)
        ttk.Button(btns, text="🧹 Очистить линию", command=self._clear_line).pack(side="left", padx=5)
        ttk.Button(btns, text="🔄 Обновить список", command=self._refresh_calib).pack(side="left", padx=5)
        return tab

    # ---------- потокобезопасный UI ----------
    def _enqueue_status(self, msg):
        """Из любого потока: кладём обновление статуса в очередь."""
        self._ui_queue.put(("status", msg))

    def _enqueue_log(self, msg):
        """Из любого потока: кладём строку лога в очередь."""
        self._ui_queue.put(("log", msg))

    def _poll_ui(self):
        """Главный поток: разбирает очередь и обновляет виджеты."""
        try:
            while True:
                kind, payload = self._ui_queue.get_nowait()
                if kind == "status":
                    self.var_status.set(payload)
                elif kind == "log":
                    self.txt_log.configure(state="normal")
                    self.txt_log.insert("end", _log_ts(payload) + "\n")
                    self.txt_log.see("end")
                    self.txt_log.configure(state="disabled")
                elif kind == "calib_done":
                    # калибровка завершилась (клик или таймаут)
                    self._restore_window()
                    self._calibrating = False
                elif kind == "refresh_calib":
                    self._refresh_calib()
                elif kind == "restore":
                    self._restore_window()
                elif kind == "engine_stopped":
                    # движок сам остановился (ошибка/завершение) — синхронизируем кнопку
                    self.btn_start.config(text="▶ Старт")
                elif kind == "toggle":
                    self._toggle()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_ui)

    # ---------- логика ----------
    def _append_log(self, msg):
        """Прямая запись в лог. Вызывать ТОЛЬКО из главного потока."""
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", _log_ts(msg) + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _toggle(self):
        """Вызывается из главного потока (кнопка) или из потока хоткея."""
        if self.engine.is_running():
            self.engine.stop()
            self.btn_start.config(text="▶ Старт")
        else:
            if not self._save_settings(silent=True):
                return
            self.engine.settings = dict(self.settings)
            self.engine.start()
            self.btn_start.config(text="⏸ Стоп")

    def _stop(self):
        self.engine.stop()
        self.btn_start.config(text="▶ Старт")

    def _save_settings(self, silent=False):
        try:
            self.settings["line"] = self.var_line.get()
            self.settings["max_level"] = int(self.var_max_level.get())
            self.settings["collect_level"] = int(self.var_collect_level.get())
            self.settings["rest_after_collect"] = int(self.var_rest.get())
            self.settings["step_delay"] = float(self.var_delay.get())
            self.settings["hotkey"] = self.var_hotkey.get().strip() or config.DEFAULT_HOTKEY
        except (ValueError, tk.TclError):
            if not silent:
                messagebox.showerror("Ошибка", "Проверьте значения полей (целые числа, задержка — число с точкой).")
            return False
        # sanity: забор не раньше 1, и не больше max_level
        self.settings["collect_level"] = min(
            self.settings["collect_level"], self.settings["max_level"])
        self.settings["collect_level"] = max(1, self.settings["collect_level"])
        self.settings["max_level"] = max(1, self.settings["max_level"])
        storage.save_settings(self.settings)
        if not silent:
            self._append_log("Настройки сохранены")
        return True

    def _apply_hotkey(self):
        if not self._save_settings(silent=True):
            return
        self._start_hotkey()
        self._append_log(f"Горячая клавиша: {self.settings['hotkey']}")

    def _start_hotkey(self):
        # единая точка смены/установки хоткея: set_hotkey сам делает stop+start
        if self.hotkey:
            self.hotkey.set_hotkey(self.settings["hotkey"])
        else:
            self.hotkey = HotkeyManager(self.settings["hotkey"], self._on_hotkey,
                                        on_error=self._enqueue_log)
            self.hotkey.start()

    def _on_hotkey(self):
        """Хоткей срабатывает в потоке pynput — не трогаем Tkinter напрямую.
        Кладём событие в очередь, главный поток разберёт его через _poll_ui."""
        self._ui_queue.put(("toggle", None))

    # ---------- калибровка ----------
    def _calibrate_selected(self):
        if not self._save_settings(silent=True):
            return
        # защита от одновременной калибровки двух точек (два слушателя мыши)
        if getattr(self, "_calibrating", False):
            messagebox.showinfo("Калибровка", "Калибровка уже идёт — дождитесь завершения")
            return
        sel = self.cal_tree.selection()
        if not sel:
            messagebox.showinfo("Калибровка", "Выберите уровень или «Забрать деньги»")
            return
        self._calibrating = True
        line = self.cal_line.get()
        item = sel[0]

        def on_done(point, level, is_collect):
            # выполняется в потоке калибровки — НЕ трогаем Tkinter напрямую,
            # шлём всё в главный поток через очередь
            if is_collect:
                storage.set_collect(line, point)
                self._enqueue_log(f"Точка забора ({line}): {point[0]},{point[1]}")
            else:
                storage.set_point(line, level, point)
                self._enqueue_log(f"Уровень {level} ({line}): {point[0]},{point[1]}")
            self._ui_queue.put(("refresh_calib", None))

        if item == "collect":
            self._minimize_for_calib(lambda: self._run_calib(line, None, True, on_done))
        else:
            lv = int(item.split("_")[1])
            self._minimize_for_calib(lambda: self._run_calib(line, lv, False, on_done))

    def _enqueue_calib_done(self):
        self._ui_queue.put(("calib_done", None))

    def _enqueue_engine_stopped(self):
        self._ui_queue.put(("engine_stopped", None))

    def _minimize_for_calib(self, action):
        self.root.iconify()
        # даём окну время свернуться, затем стартуем калибровку.
        # Timer регистрируем как non-daemon child — при закрытии приложения
        # отменяем через _cancel_calib_timer.
        self._calib_timer = threading.Timer(1.0, action)
        self._calib_timer.daemon = True
        self._calib_timer.start()

    def _cancel_calib_timer(self):
        t = getattr(self, "_calib_timer", None)
        if t:
            t.cancel()
            self._calib_timer = None

    def _run_calib(self, line, level, is_collect, on_done):
        from calibrate import calibrate_point
        # on_finish вызывается сразу после клика ИЛИ таймаута —
        # окно восстанавливается без фиксированной задержки 16с.
        # on_timeout — отдельный callback только при таймауте (нет клика).
        def on_timeout():
            self._enqueue_log("[!] калибровка не завершена: таймаут 15с, точка не сохранена")
        calibrate_point(line, level, is_collect, on_done,
                        on_finish=self._enqueue_calib_done,
                        on_timeout=on_timeout)

    def _restore_window(self):
        try:
            self.root.deiconify()
            self.root.lift()
        except Exception:
            pass

    def _clear_line(self):
        line = self.cal_line.get()
        if messagebox.askyesno("Очистка", f"Очистить все точки линии «{line}»?"):
            storage.clear_line(line)
            self._append_log(f"Линия «{line}» очищена")
            self._refresh_calib()

    def _refresh_calib(self):
        line = self.cal_line.get()
        cal = storage.load_all()
        prof = cal.get(line, {"levels": {}, "collect": None})
        for lv in range(1, config.MAX_LEVEL + 1):
            pt = prof["levels"].get(lv)
            label = f"Уровень {lv}" + (f"  [{pt[0]},{pt[1]}]" if pt else "  —")
            self.cal_tree.item(f"level_{lv}", values=(label,))
        cp = prof.get("collect")
        clabel = "Забрать деньги" + (f"  [{cp[0]},{cp[1]}]" if cp else "  —")
        self.cal_tree.item("collect", values=(clabel,))

    def on_close(self):
        self.engine.stop()
        self._cancel_calib_timer()
        if self.hotkey:
            self.hotkey.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = ClickerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()