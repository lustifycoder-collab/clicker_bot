@echo off
REM ============================================
REM  Сборка .exe для Windows
REM  Запускать на Windows: двойной клик или cmd
REM ============================================
cd /d "%~dp0"

echo [1/3] Создание виртуального окружения...
if not exist venv (
    python -m venv venv
)

echo [2/3] Установка зависимостей...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [3/3] Сборка clicker_bot.exe...
pyinstaller --onefile --windowed --name clicker_bot ^
    main.py

echo.
echo Готово! Файл: dist\clicker_bot.exe
pause