#!/usr/bin/env bash
# ============================================
#  Сборка .app для macOS
#  Запускать на macOS: bash build_macos.sh
# ============================================
set -e
cd "$(dirname "$0")"

echo "[1/4] Создание виртуального окружения..."
if [ ! -d venv ]; then
    python3 -m venv venv
fi

echo "[2/4] Установка зависимостей..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo "[3/4] Проверка, что код компилируется..."
python -m py_compile main.py bot_engine.py config.py calibrate.py storage.py hotkey.py

echo "[4/4] Сборка clicker_bot.app..."
# БЕЗ --onefile: на macOS --onefile даёт бинарь, а не .app-бандл
pyinstaller --windowed --name clicker_bot \
    --osx-bundle-identifier com.clicker.bot \
    main.py

echo
echo "Готово! Приложение: dist/clicker_bot.app"
echo
echo "Чтобы отдать кому-то — заархивируй:"
echo "  cd dist && zip -r clicker_bot-macos.zip clicker_bot.app"
echo
echo "ВАЖНО: при первом запуске дай приложению разрешение в"
echo "Системные настройки → Конфиденциальность и безопасность →"
echo "  • Управление компьютером (Accessibility)"
echo "  • Мониторинг ввода (Input Monitoring) — для горячей клавиши"
