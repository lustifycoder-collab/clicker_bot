"""
Ядро бота: стратегия ставок + распознавание результата по цвету.

Логика одного раунда:
  клик по кнопке ставки/боя → клик по уровню (лвл 1) → пауза
  → чтение пикселя результата → зелёный = выигрыш, красный = проигрыш.

Стратегия ставок (мартингейл-подобная):
  серия 1: 50 x 0.1  → если все 50 проиграли → серия 2
  серия 2: 5  x 1.0  → если все 5 проиграли  → серия 3
  серия 3: 5  x 2.0  → если все 5 проиграли  → сброс на серию 1

  Проигрыш: пауза, затем следующая ставка той же серии (всегда лвл 1).
  Выигрыш: сброс на первую серию (0.1).

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

    @staticmethod
    def _hex_to_rgb(hex_color):
        """'#rrggbb' -> (r, g, b). Возвращает None при невалидном значении."""
        try:
            hex_color = hex_color.strip().lstrip('#')
            if len(hex_color) != 6:
                return None
            return (int(hex_color[0:2], 16),
                    int(hex_color[2:4], 16),
                    int(hex_color[4:6], 16))
        except (ValueError, AttributeError):
            return None

    def _click(self, point, delay_after=0.3):
        """Клик по точке с паузой после. Не роняет поток при сбое.
        Пауза прерываемая — stop() срабатывает мгновенно, а не через delay."""
        if not point:
            return False
        try:
            pyautogui.click(int(point[0]), int(point[1]))
        except pyautogui.FailSafeException:
            # FailSafe: мышь в углу экрана — пользователь хочет аварийно остановить.
            self._log("[!] FailSafe: мышь в углу, бот остановлен")
            self.running = False
            return False
        except Exception as e:
            self._log(f"[!] ошибка клика ({point[0]},{point[1]}): {e}")
            return False
        if delay_after:
            self._sleep(delay_after)
        return True

    def _read_pixel(self, point):
        """Читает цвет пикселя в точке. Возвращает (r, g, b) или None при сбое."""
        if not point:
            return None
        try:
            return pyautogui.pixel(int(point[0]), int(point[1]))
        except Exception as e:
            self._log(f"[!] ошибка чтения пикселя ({point[0]},{point[1]}): {e}")
            return None

    @staticmethod
    def _color_match(pixel, target, tolerance):
        """Совпадает ли пиксель с эталоном в пределах допуска на каждый канал."""
        if pixel is None or target is None:
            return False
        return all(abs(p - t) <= tolerance for p, t in zip(pixel, target))

    # --- главный цикл ---
    def _run(self, gen_token):
        try:
            self._run_inner(gen_token)
        except Exception as e:
            # любое непойманное исключение не должно оставлять running=True навсегда
            self._status("Ошибка: " + str(e))
            self._log(f"[!] ошибка в цикле: {e}")
        finally:
            if getattr(self, "_gen_token", None) == gen_token:
                self.running = False
                self._status("Остановлено")
                if self.on_stopped:
                    self.on_stopped()

    def _run_inner(self, gen_token):
        cal = storage.load_all()
        line = self.settings.get("line", config.LINE_MANUAL)

        # --- параметры стратегии ---
        strategy = self.settings.get("bet_strategy", config.DEFAULT_BET_STRATEGY)
        if not isinstance(strategy, list) or not strategy:
            strategy = config.DEFAULT_BET_STRATEGY
        # нормализуем: [(ставка, раз), ...]
        stages = []
        for s in strategy:
            try:
                bet = float(s[0])
                times = int(s[1])
                if bet > 0 and times > 0:
                    stages.append((bet, times))
            except (TypeError, ValueError, IndexError):
                continue
        if not stages:
            stages = config.DEFAULT_BET_STRATEGY

        # --- параметры распознавания цвета ---
        win_rgb = self._hex_to_rgb(self.settings.get("win_color", config.DEFAULT_WIN_COLOR))
        lose_rgb = self._hex_to_rgb(self.settings.get("lose_color", config.DEFAULT_LOSE_COLOR))
        tolerance = max(0, self._safe_int(self.settings.get("color_tolerance"), config.DEFAULT_COLOR_TOLERANCE))
        result_delay = max(0.0, self._safe_float(self.settings.get("result_delay"), config.DEFAULT_RESULT_DELAY))
        # пауза после проигрыша (остановка перед следующей ставкой той же серии)
        lose_pause = max(0.0, self._safe_float(self.settings.get("lose_pause"), config.DEFAULT_LOSE_PAUSE))

        profile = cal.get(line, {"levels": {}, "collect": None})

        # обязательные точки: уровень 1, кнопка ставки, пиксель результата
        level_point = profile["levels"].get(1)
        bet_point = profile.get("bet")
        result_point = profile.get("result_pixel")
        if not level_point:
            self._status("Ошибка: точка уровня 1 не откалибрована")
            self._log("[!] точка уровня 1 не откалибрована, бот не запущен")
            return
        if not bet_point:
            self._status("Ошибка: кнопка ставки/боя не откалибрована")
            self._log("[!] кнопка ставки/боя не откалибрована, бот не запущен")
            return
        if not result_point:
            self._status("Ошибка: пиксель результата не откалиброван")
            self._log("[!] пиксель результата не откалиброван, бот не запущен")
            return
        if not win_rgb or not lose_rgb:
            self._status("Ошибка: неверные цвета выигрыша/проигрыша")
            self._log("[!] неверные цвета выигрыша/проигрыша в настройках")
            return

        self._status(f"Старт. Линия: {config.LINE_NAMES.get(line, line)}")
        self._log(f"Стратегия: {', '.join(f'{t}x{b}' for b, t in stages)}")
        self._log(f"Цвет: выигрыш {self.settings.get('win_color')}, "
                  f"проигрыш {self.settings.get('lose_color')}, допуск {tolerance}")

        stage_idx = 0   # индекс текущей ступени
        attempts_left = stages[0][1]  # сколько ставок осталось в текущей серии

        while self.running:
            bet, times = stages[stage_idx]
            if attempts_left <= 0:
                # серия исчерпана — переход на следующую ступень или сброс на первую
                stage_idx += 1
                if stage_idx >= len(stages):
                    stage_idx = 0
                    self._log("Все серии проиграны — сброс на первую ступень (0.1)")
                attempts_left = stages[stage_idx][1]
                continue

            if not self.running or getattr(self, "_gen_token", None) != gen_token:
                return

            self._status(f"Ставка {bet} — осталось {attempts_left} из {times} (ступень {stage_idx + 1}/{len(stages)})")
            self._log(f"Раунд: ставка {bet}, осталось {attempts_left}/{times}")

            # 1) клик по кнопке ставки/боя
            self._click(bet_point, 0.4)
            # 2) клик по уровню (лвл 1)
            self._click(level_point, 0.5)
            # 3) пауза, чтобы игра показала результат
            self._sleep(result_delay)
            if not self.running or getattr(self, "_gen_token", None) != gen_token:
                return

            # 4) читаем цвет результата
            pixel = self._read_pixel(result_point)
            if self._color_match(pixel, win_rgb, tolerance):
                self._log(f"ВЫИГРЫШ (ставка {bet}) — сброс на первую ступень")
                self._status(f"ВЫИГРЫШ {bet} — сброс на 0.1")
                stage_idx = 0
                attempts_left = stages[0][1]
            elif self._color_match(pixel, lose_rgb, tolerance):
                self._log(f"Проигрыш (ставка {bet}) — осталось {attempts_left - 1}/{times}")
                self._status(f"Проигрыш {bet} — пауза, затем снова")
                attempts_left -= 1
                # остановка перед следующей ставкой той же серии
                self._sleep(lose_pause)
            else:
                # цвет не совпал ни с выигрышем, ни с проигрышем —
                # не угадываем, считаем раунд неопределённым и повторяем ту же ставку.
                self._log(f"[!] цвет результата не распознан {pixel} — повтор раунда")
                self._status("Цвет не распознан — повтор")

        self._log("Бот остановлен")

    def _sleep(self, seconds):
        """Прерываемый сон (реагирует на stop и на смену поколения потока)."""
        gen = getattr(self, "_gen_token", None)
        end = time.time() + seconds
        while self.running and gen == getattr(self, "_gen_token", None) \
                and time.time() < end:
            time.sleep(0.1)