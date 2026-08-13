"""
Логика калибровки: пользователь наводит мышь на точку и кликает ЛКМ,
координаты фиксируются.

Калибровка работает в отдельном потоке, пока GUI скрыто/свёрнуто,
чтобы пользователь мог кликнуть по игровому окну.

Потокобезопасность: для остановки используется threading.Event.
По завершении (клик или таймаут) вызывается on_done, а GUI
восстанавливается сразу через callback on_finish.
"""
import threading

import pyautogui
from pynput import mouse

import storage


class Calibrator:
    """Интерактивная калибровка одной точки."""

    def __init__(self, line, level=None, is_collect=False, on_done=None, on_finish=None, on_timeout=None):
        """
        line      — левая/правая/ручная
        level     — номер уровня (None для кнопки забора)
        is_collect— True если калибруем кнопку 'забрать деньги'
        on_done   — callback(point, level, is_collect) при успешном клике
        on_finish — callback() при завершении (клик или таймаут)
        on_timeout— callback() только при таймауте (клик не был сделан)
        """
        self.line = line
        self.level = level
        self.is_collect = is_collect
        self.on_done = on_done
        self.on_finish = on_finish
        self.on_timeout = on_timeout
        self._stop = threading.Event()
        self._clicked = False
        self._bounds = (0, 0)

    def start(self):
        """Запускает калибровку (блокирующе). Вызвать в потоке."""
        # защита от ложных/негативных координат (клик за пределами экрана).
        # Используем pyautogui.size() вместо создания Tk root в не-главном
        # потоке — Tk не потокобезопасен и может упасть/повиснуть.
        try:
            sw, sh = pyautogui.size()
        except Exception:
            # если размер экрана не получить — не ограничиваем координаты
            sw = sh = 1 << 30
        self._bounds = (sw, sh)

        listener = mouse.Listener(on_click=self._on_click)
        listener.start()

        print("[калибровка] наведите курсор на точку и кликните ЛКМ")
        print(f"[калибровка] цель: {'забрать деньги' if self.is_collect else 'уровень ' + str(self.level)}")
        # ждём клик или таймаут 15 секунд
        self._stop.wait(15.0)
        listener.stop()

        if not self._clicked and self.on_timeout:
            self.on_timeout()

        if self.on_finish:
            self.on_finish()

    def _on_click(self, x, y, button, pressed):
        # игнорируем клики вне экрана или уже обработанные
        if self._clicked:
            return False
        if button != mouse.Button.left or not pressed:
            return True
        sw, sh = self._bounds
        if not (0 <= x < sw and 0 <= y < sh):
            print("[калибровка] клик за пределами экрана игнорирован")
            return True
        self._clicked = True
        self._stop.set()
        if self.on_done:
            self.on_done((x, y), self.level, self.is_collect)
        return False  # отключить слушатель


def calibrate_point(line, level=None, is_collect=False, on_done=None, on_finish=None, on_timeout=None):
    """Запускает калибровку в отдельном потоке (не блокирует GUI)."""
    cal = Calibrator(line, level, is_collect, on_done, on_finish, on_timeout)
    t = threading.Thread(target=cal.start, daemon=True)
    t.start()
    return t