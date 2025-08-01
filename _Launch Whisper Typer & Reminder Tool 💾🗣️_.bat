@echo off

:: Check if virtual environment exists and packages are installed
echo Checking for existing virtual environment...
cd /d %~dp0
if exist ".venv" (
    if exist ".venv\pyvenv.cfg" (
        echo Virtual environment found. Checking if packages are installed...
        call .venv\Scripts\activate.bat
        python -c "import whisper, pyaudio, pynput" >nul 2>&1
        if %errorlevel% equ 0 (
            echo Required packages are already installed. Launching Whisper transcribe script...
            cd /d %~dp0
            python whisper-typer-tool-CPU.py
            pause
            exit /b
        ) else (
            echo Some packages missing in virtual environment. Will reinstall...
        )
        call deactivate >nul 2>&1
    )
)

:: Check if the script is running as admin
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo Requesting administrative privileges...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
    pushd "%CD%"
    CD /D "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed. Installing Python 3.12.8...
    :: Download and install latest stable Python (change version as needed)
    powershell -Command "Invoke-WebRequest -Uri https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe -OutFile python-installer.exe"
    start /wait python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    if %errorlevel% neq 0 (
        echo Failed to install Python. Exiting...
        pause
        exit /b 1
    )
    del python-installer.exe
    echo Python installed successfully. Please restart this script.
    pause
    exit /b 0
)

:: Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment. Exiting...
        pause
        exit /b 1
    )
)

:: Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Failed to activate virtual environment. Exiting...
    pause
    exit /b 1
)

:: Ensure pip is up to date
echo Upgrading pip...
python -m pip install --upgrade pip

:: Install packages from requirements.txt if it exists, otherwise install individually
if exist "requirements.txt" (
    echo Installing packages from requirements.txt...
    pip install -r requirements.txt
    if %errorlevel% equ 0 (
        goto InstallComplete
    ) else (
        echo Failed to install some packages from requirements.txt. Trying individual installation...
    )
)

:InstallComplete
echo All packages installed successfully!

:: Wait for 1 second
timeout /t 1 /nobreak >nul

:: Kill any existing instances of the specific Python script, including admin instances
echo Checking for running instances...
powershell -Command "Get-Process | Where-Object {$_.CommandLine -like '*whisper-typer-tool-CPU.py*'} | Stop-Process -Force" >nul 2>&1

:: Name the terminal window "Whisper Typer Tool"
title Whisper Typer Tool

:: Running as admin, continue with launching the Python script
echo Launching Whisper Typer Tool...
cd /d %~dp0
python whisper-typer-tool-CPU.py
pause
