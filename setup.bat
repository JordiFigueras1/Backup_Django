@echo off
REM Check if Python is installed
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo Python is not installed or not added to PATH.
    echo Please install Python and ensure it is added to PATH.
    pause
    exit /b 1
)

REM Create a virtual environment named '.venv'
python -m venv .venv

REM Check if the virtual environment was created successfully
IF NOT EXIST ".venv\Scripts\activate" (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

REM Activate the virtual environment
call .venv\Scripts\activate

REM Upgrade pip, setuptools, and wheel
pip install --upgrade pip setuptools wheel

REM Install meson and ninja within the virtual environment
pip install meson ninja

pip install matplotlib==3.9.2 --only-binary :all:

REM Install packages from requirements.txt
IF EXIST "mysite\requirements.txt" (
    pip install -r mysite\requirements.txt
) ELSE (
    echo requirements.txt not found.
    pause
    exit /b 1
)

REM Deactivate the virtual environment
deactivate

echo Virtual environment setup complete with requirements installed.
pause
