@echo off
REM Initialize Conda (only needed if it's not initialized already)
IF NOT DEFINED CONDA_EXE (
    echo Initializing Conda...
    call C:\path\to\conda\Scripts\activate.bat
)

REM Check if Conda is installed
conda --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo Conda is not installed or not added to PATH.
    echo Please install Miniconda or Anaconda and ensure it is added to PATH.
    pause
    exit /b 1
)

REM Create a Conda environment named 'myenv' (or choose your environment name)
conda create -n myenv python=3.11 -y

REM Activate the Conda environment
call conda activate myenv

REM Install packages from requirements.txt
IF EXIST "mysite\requirements.txt" (
    pip install -r mysite\requirements.txt
) ELSE (
    echo requirements.txt not found.
    pause
    exit /b 1
)

REM Deactivate the Conda environment
call conda deactivate

echo Conda environment setup complete with requirements installed.
pause
