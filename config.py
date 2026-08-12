"""
Конфигурация бота-кликера для Telegram Mini App игры.

Содержит таблицу уровней (кэф, ячейки) и настройки по умолчанию.
"""

# Таблица уровней: номер -> (кэф, количество ячеек)
LEVELS = {
    1:  (1.02,  6),
    2:  (1.27,  5),
    3:  (1.70,  4),
    4:  (2.55,  3),
    5:  (3.40,  4),
    6:  (4.25,  5),
    7:  (5.10,  6),
    8:  (6.38,  5),
    9:  (8.59,  4),
    10: (12.75, 3),
    11: (21.25, 5),
    12: (25.50, 6),
}

MAX_LEVEL = max(LEVELS.keys())

# Типы линий (пресеты калибровки)
LINE_LEFT = "left"      # левая линия
LINE_RIGHT = "right"    # правая линия
LINE_MANUAL = "manual"  # ручная калибровка

LINE_NAMES = {
    LINE_LEFT: "Левая линия",
    LINE_RIGHT: "Правая линия",
    LINE_MANUAL: "Ручная калибровка",
}

# Задержка между кликами уровней в секундах (по умолчанию)
DEFAULT_STEP_DELAY = 0.8

# Горячая клавиша по умолчанию (вкл/выкл)
DEFAULT_HOTKEY = "f8"

# Настройки по умолчанию
DEFAULT_SETTINGS = {
    "rest_after_collect": 30,   # отдых после забора денег, секунды
    "line": LINE_MANUAL,        # выбранная линия
    "max_level": 12,            # до какого лвла доходить
    "collect_level": 12,        # на каком лвле забирать деньги
    "hotkey": DEFAULT_HOTKEY,
    "step_delay": DEFAULT_STEP_DELAY,
}


def level_info(level: int):
    """Возвращает (кэф, ячейки) для уровня."""
    return LEVELS.get(level, (1.0, 1))


def total_multiplier(max_level: int) -> float:
    """Суммарный кэф от 1 до max_level (произведение кэфов)."""
    m = 1.0
    for lv in range(1, max_level + 1):
        m *= LEVELS[lv][0]
    return round(m, 2)