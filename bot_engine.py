"""
Ядро бота: цикл кликов по уровням.

Логика:
  лвл 1 → клик по точке → пауза → лвл 2 → ... → лвл N (до какого)
  → клик "забрать деньги" → отдых → сброс на лвл 1 → повтор.

Работает в отдельном потоке. Управляется флагом running.
"""
import threading
import time

import pyautogui

import config
import storage


class BotEngine:
    def __init__(self, on_status=None, on_log=None):
        """
        on_status — callback(str) для обновления статуса в GUI
        on_log    — callback(str) для лога событий
        """
        self.running = False
        self._thread = None
        self.on_status = on_status
        self.on_log = on_log
        self.settings = {}

    # --- управление ---
    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    def is_running(self):
        return self.running

    # --- вспомогательные ---
    def _log(self, msg):
        if self.on_log:
            self.on_log(msg)

    def _status(self, msg):
        if self.on_status:
            self.on_status(msg)

    def _click(self, point, delay_after=0.3):
        """Клик по точке с паузой после."""
        if not point:
            return False
        pyautogui.click(int(point[0]), int(point[1]))
        if delay_after:
            time.sleep(delay_after)
        return True

    # --- главный цикл ---
    def _run(self):
        cal = storage.load_all()
        line = self.settings.get("line", config.LINE_MANUAL)
        max_level = self.settings.get("max_level", config.MAX_LEVEL)
        collect_level = self.settings.get("collect_level", config.MAX_LEVEL)
        rest = self.settings.get("rest_after_collect", 30)
        step_delay = self.settings.get("step_delay", config.DEFAULT_STEP_DELAY)

        profile = cal.get(line, {"levels": {}, "collect": None})

        self._status(f"Старт. Линия: {config.LINE_NAMES.get(line, line)}")
        self._log(f"Цикл: уровни 1..{max_level}, забор на {collect_level}, отдых {rest}с")

        while self.running:
            # проход по уровням
            for lv in range(1, max_level + 1):
                if not self.running:
                    break
                point = profile["levels"].get(lv)
                if not point:
                    self._log(f"[!] лвл {lv}: точка не откалибрована, пропуск")
                    continue
                self._status(f"Уровень {lv}/{max_level} (кэф {config.level_info(lv)[0]}x)")
                self._click(point, step_delay)

            # забор денег
            if not self.running:
                break
            collect_point = profile.get("collect")
            if collect_point:
                self._status(f"Забор денег на уровне {collect_level}")
                self._log(f"Забираю деньги (кэф {config.level_info(collect_level)[0]}x)")
                self._click(collect_point, 0.5)
            else:
                self._log("[!] точка забора не откалибрована")

            # отдых
            if not self.running:
                break
            self._status(f"Отдых {rest}с, затем сброс на лвл 1")
            self._log(f"Отдых {rest}с...")
            self._sleep(rest)

            if not self.running:
                break
            self._log("Сброс на лвл 1, новый цикл")

        self._status("Остановлено")
        self._log("Бот остановлен")

    def _sleep(self, seconds):
        """Прерываемый сон (реагирует на stop)."""
        end = time.time() + seconds
        while self.running and time.time() < end:
            time.sleep(0.1)