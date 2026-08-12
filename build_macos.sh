#!/usr/bin/env bash
# ============================================
#  Сборка .app для macOS
#  Запускать на macOS: bash build_macos.sh
# ============================================
set -e
cd "$(dirname "$0")"

echo "[1/3] Создание виртуального окружения..."
if [ ! -d venv ]; then
    python3 -m venv venv
fi

echo "[2/3] Установка зависимостей..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo "[3/3] Сборка clicker_bot.app..."
pyinstaller --onefile --windowed --name clicker_bot \
    main.py

echo
echo "Готово! Приложение: dist/clicker_bot.app"
echo
echo "ВАЖНО: дай приложению разрешение в"
echo "Системные настройки → Конфиденциальность → Управление компьютером"