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
    def __init__(self, on_status=None, on_log=None, on_stopped=None):
        """
        on_status  — callback(str) для обновления статуса в GUI
        on_log     — callback(str) для лога событий
        on_stopped — callback() при самостоятельной остановке (ошибка/завершение),
                     чтобы GUI мог синхронизировать кнопку «Старт/Стоп»
        """
        self.running = False
        self._thread = None
        self.on_status = on_status
        self.on_log = on_log
        self.on_stopped = on_stopped
        self.settings = {}

    # --- управление ---
    def start(self):
        if self.running:
            return
        # токен поколения: старый поток в finally не должен сбрасывать
        # running у нового потока, если пользователь быстро сделал стоп→старт.
        self._gen = getattr(self, "_gen", 0) + 1
        self._gen_token = self._gen
        self.running = True
        self._thread = threading.Thread(target=self._run, args=(self._gen_token,), daemon=True)
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

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _click(self, point, delay_after=0.3):
        """Клик по точке с паузой после. Не роняет поток при сбое.
        Пауза прерываемая — stop() срабатывает мгновенно, а не через delay."""
        if not point:
            return False
        try:
            pyautogui.click(int(point[0]), int(point[1]))
        except pyautogui.FailSafeException:
            # FailSafe: мышь в углу экрана — пользователь хочет аварийно остановить.
            # Это не штатная ситуация: останавливаем бота, а не продолжаем кликать в никуда.
            self._log("[!] FailSafe: мышь в углу, бот остановлен")
            self.running = False
            return False
        except Exception as e:
            # координаты вне экрана, окно закрыто и т.п. — не убиваем весь цикл,
            # логируем и идём дальше.
            self._log(f"[!] ошибка клика ({point[0]},{point[1]}): {e}")
            return False
        if delay_after:
            self._sleep(delay_after)
        return True

    # --- главный цикл ---
    def _run(self, gen_token):
        try:
            self._run_inner(gen_token)
        except Exception as e:
            # любое непойманное исключение не должно оставлять running=True
            # навсегда (UI зависнет на «работает», а поток уже мёртв)
            self._status("Ошибка: " + str(e))
            self._log(f"[!] ошибка в цикле: {e}")
        finally:
            # сбрасываем running только если мы — актуальное поколение потока.
            # Иначе новый поток (после быстрого стоп→старт) был бы убит.
            if getattr(self, "_gen_token", None) == gen_token:
                self.running = False
                self._status("Остановлено")
                if self.on_stopped:
                    self.on_stopped()

    def _run_inner(self, gen_token):
        cal = storage.load_all()
        line = self.settings.get("line", config.LINE_MANUAL)
        # clamp: настройки могут быть испорчены вручную в JSON
        max_level = max(1, min(self._safe_int(self.settings.get("max_level"), config.MAX_LEVEL), config.MAX_LEVEL))
        collect_level = max(1, min(self._safe_int(self.settings.get("collect_level"), config.MAX_LEVEL), max_level))
        rest = max(0, self._safe_int(self.settings.get("rest_after_collect"), 30))
        step_delay = max(0.0, self._safe_float(self.settings.get("step_delay"), config.DEFAULT_STEP_DELAY))

        profile = cal.get(line, {"levels": {}, "collect": None})

        # точка забора обязательна — без неё бот бессмысленно кликает
        collect_point = profile.get("collect")
        if not collect_point:
            self._status("Ошибка: точка забора не откалибрована")
            self._log("[!] точка забора не откалибрована, бот не запущен")
            return

        # точка уровня, на котором забираем деньги, тоже обязательна:
        # без неё мы не дойдём до кнопки забора, а крутиться вхолостую не имеет смысла.
        if collect_level not in profile["levels"]:
            self._status(f"Ошибка: точка уровня {collect_level} не откалибрована")
            self._log(f"[!] точка уровня {collect_level} не откалибрована, бот не запущен")
            return

        self._status(f"Старт. Линия: {config.LINE_NAMES.get(line, line)}")
        self._log(f"Цикл: уровни 1..{max_level}, забор на {collect_level}, отдых {rest}с, "
                  f"суммарный кэф {config.total_multiplier(max_level)}x")

        while self.running:
            # поднимаемся по уровням до max_level; на collect_level забираем деньги.
            for lv in range(1, max_level + 1):
                # если запущен новый поток (быстрый стоп→старт) — старый
                # должен мгновенно прекратить кликать, а не доводить цикл до конца.
                if not self.running or getattr(self, "_gen_token", None) != gen_token:
                    return
                point = profile["levels"].get(lv)
                if not point:
                    self._log(f"[!] лвл {lv}: точка не откалибрована, пропуск")
                    continue
                self._status(f"Уровень {lv}/{max_level} (кэф {config.level_info(lv)[0]}x)")
                self._click(point, step_delay)
                # на нужном уровне — забор денег.
                # #1: пауза дольше, чтобы игра успела обработать клик уровня,
                #     прежде чем кликнем по кнопке забора. Применяется ВСЕГДА,
                #     в том числе когда забор идёт на последнем уровне (collect_level == max_level),
                #     где step_delay уже прошёл — но игра могла не успеть.
                # #2: если точки уровня нет — не забираем (кнопка вряд ли активна),
                #     логируем пропуск вместо слепого клика по забору.
                if lv == collect_level and self.running and \
                        getattr(self, "_gen_token", None) == gen_token:
                    self._sleep(0.6)
                    self._status(f"Забор денег на уровне {collect_level}")
                    self._log(f"Забираю деньги (кэф {config.level_info(collect_level)[0]}x)")
                    self._click(collect_point, 0.5)

            # отдых
            if not self.running or getattr(self, "_gen_token", None) != gen_token:
                return
            self._status(f"Отдых {rest}с, затем сброс на лвл 1")
            self._log(f"Отдых {rest}с...")
            self._sleep(rest)

            if not self.running or getattr(self, "_gen_token", None) != gen_token:
                return
            self._log("Сброс на лвл 1, новый цикл")

        # финальные статусы "Остановлено" ставит _run в finally
        self._log("Бот остановлен")

    def _sleep(self, seconds):
        """Прерываемый сон (реагирует на stop и на смену поколения потока).
        Старый поток при быстром стоп→старт выходит из сна мгновенно,
        не дожидаясь конца паузы."""
        gen = getattr(self, "_gen_token", None)
        end = time.time() + seconds
        while self.running and gen == getattr(self, "_gen_token", None) \
                and time.time() < end:
            time.sleep(0.1)