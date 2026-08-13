"""
Глобальная горячая клавиша toggle (вкл/выкл бота).

Работает через pynput.keyboard.GlobalHotKeys — кроссплатформенно
(Windows и macOS). Запускается в отдельном потоке.
"""
import threading

from pynput import keyboard


class HotkeyManager:
    def __init__(self, hotkey, on_toggle, on_error=None):
        """
        hotkey    — строка, например 'f8'
        on_toggle — callback() вызывается при нажатии
        on_error  — callback(str) при неудачной установке клавиши
        """
        self.hotkey = hotkey
        self.on_toggle = on_toggle
        self.on_error = on_error
        self._listener = None
        self._thread = None

    def start(self):
        if self._listener:
            return
        try:
            self._listener = keyboard.GlobalHotKeys({self.hotkey: self._toggle})
        except Exception as e:
            # невалидный хоткей (мусор из поля ввода) не должен ронять
            # приложение — просто не стартуем слушатель
            self._listener = None
            if self.on_error:
                self.on_error(f"Не удалось установить горячую клавишу «{self.hotkey}»: {e}")
            return
        self._thread = threading.Thread(target=self._listener.run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None
        if self._thread:
            # дождаться завершения потока, чтобы не было конфликта при рестарте
            self._thread.join(timeout=2.0)
            self._thread = None

    def set_hotkey(self, hotkey):
        """Сменить горячую клавишу и перезапустить слушатель.
        Единая точка смены клавиши — используется из GUI."""
        self.hotkey = hotkey
        self.stop()
        self.start()

    @property
    def is_active(self):
        """Активен ли слушатель (для синхронизации UI)."""
        return self._listener is not None

    def _toggle(self):
        if self.on_toggle:
            self.on_toggle()