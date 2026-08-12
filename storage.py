"""
Хранилище калибровок.
Сохраняет координаты кликов для каждой линии (left/right/manual)
в JSON-файл. Формат:

{
  "left":  { "levels": {1: [x, y], 2: [x, y], ...}, "collect": [x, y] },
  "right": { "levels": {...}, "collect": [x, y] },
  "manual":{ "levels": {...}, "collect": [x, y] }
}
"""
import json
import os

from config import LINE_LEFT, LINE_RIGHT, LINE_MANUAL

ALL_LINES = [LINE_LEFT, LINE_RIGHT, LINE_MANUAL]

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


def _default_profile():
    return {"levels": {}, "collect": None}


def _default_data():
    return {line: _default_profile() for line in ALL_LINES}


def _load_raw():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_raw(data):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_all():
    """Возвращает полную структуру калибровок (все линии)."""
    data = _load_raw()
    calibrations = data.get("calibrations", {})
    result = _default_data()
    for line in ALL_LINES:
        prof = calibrations.get(line, {})
        result[line]["levels"] = {int(k): v for k, v in prof.get("levels", {}).items()}
        result[line]["collect"] = prof.get("collect")
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