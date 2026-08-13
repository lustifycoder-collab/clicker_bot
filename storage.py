"""
Хранилище калибровок.
Сохраняет координаты кликов для каждой линии (left/right/manual)
в JSON-файл. Формат:

{
  "left":  { "levels": {1: [x, y], 2: [x, y], ...}, "collect": [x, y] },
  "right": { "levels": {...}, "collect": [x, y] },
  "manual":{ "levels": {...}, "collect": [x, y] }
}

Путь файла:
  - при запуске из исходников — рядом с этим скриптом;
  - при PyInstaller onefile — НЕ во временной папке _MEIPASS (она новая
    при каждом запуске), а рядом с исполняемым файлом, либо в каталоге
    данных пользователя.
"""
import json
import os
import sys
import threading

from config import LINE_LEFT, LINE_RIGHT, LINE_MANUAL

ALL_LINES = [LINE_LEFT, LINE_RIGHT, LINE_MANUAL]

# Общая блокировка: защищает файл settings.json от одновременных
# чтения/записи из разных потоков (калибровка + бот могут работать
# одновременно), чтобы не повредить JSON.
_LOCK = threading.RLock()


def _settings_path():
    """Определяет стабильный путь для settings.json."""
    # PyInstaller onefile: __file__ указывает на _MEIPASS (временная папка).
    # Сохраняем рядом с exe, если каталог доступен для записи.
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidate = os.path.join(exe_dir, "settings.json")
        # exe может лежать в защищённом месте (Program Files) — тогда
        # падаем на каталог данных пользователя.
        try:
            test = os.path.join(exe_dir, ".write_test")
            with open(test, "w") as f:
                f.write("")
            os.remove(test)
            return candidate
        except OSError:
            pass
        # fallback: каталог данных пользователя
        home = os.path.expanduser("~")
        appdata = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
        base = appdata or home
        data_dir = os.path.join(base, "clicker_bot")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, "settings.json")
    # исходники: рядом со скриптом
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


SETTINGS_PATH = _settings_path()


def _default_profile():
    return {"levels": {}, "collect": None}


def _default_data():
    return {line: _default_profile() for line in ALL_LINES}


def _load_raw():
    """Читает JSON. При повреждении файла — сохраняет резервную копию
    повреждённого файла в settings.json.bak (чтобы данные не пропали
    безвозвратно), затем возвращает пустой словарь."""
    with _LOCK:
        if not os.path.exists(SETTINGS_PATH):
            return {}
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError) as e:
            # не выбрасываем ошибку: повреждённый файл не должен ронять приложение.
            # Но и не теряем данные молча — копируем битый файл в .bak.
            try:
                with open(SETTINGS_PATH, "rb") as src, \
                        open(SETTINGS_PATH + ".bak", "wb") as dst:
                    dst.write(src.read())
            except OSError:
                pass
            return {}


def _save_raw(data):
    # Атомарная запись через временный файл + переименование.
    # Не оставляет "полузаписанный" JSON при сбое/аварийном завершении.
    with _LOCK:
        tmp = SETTINGS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SETTINGS_PATH)


def load_all():
    """Возвращает полную структуру калибровок (все линии).
    Устойчив к повреждённому JSON: невалидные ключи/значения пропускаются.
    """
    data = _load_raw()
    calibrations = data.get("calibrations", {})
    if not isinstance(calibrations, dict):
        calibrations = {}
    result = _default_data()
    for line in ALL_LINES:
        prof = calibrations.get(line, {})
        if not isinstance(prof, dict):
            prof = {}
        levels_raw = prof.get("levels", {})
        levels = {}
        if isinstance(levels_raw, dict):
            for k, v in levels_raw.items():
                # ключ может быть мусором/не числом; значение — не списком
                if isinstance(v, (list, tuple)) and len(v) >= 2:
                    try:
                        levels[int(k)] = [int(v[0]), int(v[1])]
                    except (ValueError, TypeError):
                        continue
        result[line]["levels"] = levels
        cp = prof.get("collect")
        if isinstance(cp, (list, tuple)) and len(cp) >= 2:
            try:
                result[line]["collect"] = [int(cp[0]), int(cp[1])]
            except (ValueError, TypeError):
                result[line]["collect"] = None
    return result


def save_all(calibrations):
    """Сохраняет полную структуру калибровок."""
    data = _load_raw()
    data["calibrations"] = calibrations
    _save_raw(data)


def set_point(line, level, point):
    """Сохранить точку клика для уровня."""
    cal = load_all()
    cal[line]["levels"][level] = [int(point[0]), int(point[1])]
    save_all(cal)


def set_collect(line, point):
    """Сохранить точку кнопки 'забрать деньги'."""
    cal = load_all()
    cal[line]["collect"] = [int(point[0]), int(point[1])]
    save_all(cal)


def clear_line(line):
    """Очистить все точки конкретной линии."""
    cal = load_all()
    cal[line] = _default_profile()
    save_all(cal)


def load_settings():
    """Загружает настройки приложения."""
    data = _load_raw()
    return data.get("settings", {})


def save_settings(settings):
    """Сохраняет настройки приложения."""
    data = _load_raw()
    data["settings"] = settings
    _save_raw(data)