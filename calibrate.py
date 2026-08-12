"""
Логика калибровки: пользователь наводит мышь на точку и нажимает
горячую клавишу (или Enter), координаты фиксируются.

Калибровка работает в отдельном потоке, пока GUI скрыто/свёрнуто,
чтобы пользователь мог кликнуть по игровому окну.
"""
import threading
import time

import pyautogui
from pynput import mouse

import storage


class Calibrator:
    """Интерактивная калибровка одной точки."""

    def __init__(self, line, level=None, is_collect=False, on_done=None):
        """
        line      — левая/правая/ручная
        level     — номер уровня (None для кнопки забора)
        is_collect— True если калибруем кнопку 'забрать деньги'
        on_done   — callback(point, level, is_collect)
        """
        self.line = line
        self.level = level
        self.is_collect = is_collect
        self.on_done = on_done
        self._stop = False

    def start(self):
        """Запускает калибровку (блокирующе). Вызвать в потоке."""
        listener = mouse.Listener(on_click=self._on_click)
        listener.start()

        # даём пользователю 5 секунд навести курсор
        # (считаем от первого движения, но проще: фиксированный таймаут)
        print("[калибровка] наведите курсор на точку и кликните ЛКМ")
        print(f"[калибровка] цель: {'забрать деньги' if self.is_collect else 'уровень ' + str(self.level)}")
        deadline = time.time() + 15
        while time.time() < deadline and not self._stop:
            time.sleep(0.05)
        listener.stop()

    def _on_click(self, x, y, button, pressed):
        if button == mouse.Button.left and pressed:
            self._stop = True
            if self.on_done:
                self.on_done((x, y), self.level, self.is_collect)
            return False  # отключить слушатель


def calibrate_point(line, level=None, is_collect=False, on_done=None):
    """Запускает калибровку в отдельном потоке (не блокирует GUI)."""
    cal = Calibrator(line, level, is_collect, on_done)
    t = threading.Thread(target=cal.start, daemon=True)
    t.start()
    return t