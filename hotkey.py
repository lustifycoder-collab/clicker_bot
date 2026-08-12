"""
Глобальная горячая клавиша toggle (вкл/выкл бота).

Работает через pynput.keyboard.GlobalHotKeys — кроссплатформенно
(Windows и macOS). Запускается в отдельном потоке.
"""
import threading

from pynput import keyboard


class HotkeyManager:
    def __init__(self, hotkey, on_toggle):
        """
        hotkey    — строка, например 'f8'
        on_toggle — callback() вызывается при нажатии
        """
        self.hotkey = hotkey
        self.on_toggle = on_toggle
        self._listener = None
        self._thread = None

    def start(self):
        if self._listener:
            return
        self._listener = keyboard.GlobalHotKeys({self.hotkey: self._toggle})
        self._thread = threading.Thread(target=self._listener.run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    def set_hotkey(self, hotkey):
        """Сменить горячую клавишу (перезапуск слушателя)."""
        self.hotkey = hotkey
        self.stop()
        self.start()

    def _toggle(self):
        if self.on_toggle:
            self.on_toggle()