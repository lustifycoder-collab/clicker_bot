@echo off
REM ============================================
REM  Сборка .exe для Windows
REM  Запускать на Windows: двойной клик или cmd
REM ============================================
cd /d "%~dp0"

echo [1/4] Создание виртуального окружения...
if not exist venv (
    python -m venv venv
)

echo [2/4] Установка зависимостей...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [3/4] Проверка, что код компилируется...
python -m py_compile main.py bot_engine.py config.py calibrate.py storage.py hotkey.py
if errorlevel 1 (
    echo ОШИБКА: код не компилируется, сборка отменена
    pause
    exit /b 1
)

echo [4/4] Сборка clicker_bot.exe...
pyinstaller --onefile --windowed --name clicker_bot ^
    main.py

echo.
echo Готово! Файл: dist\clicker_bot.exe
pause
