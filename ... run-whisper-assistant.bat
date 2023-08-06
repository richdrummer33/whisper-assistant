title whisper-assistant

Rem a batch script that starts whisper-typer-tool.py with python3 when windows boots
Rem Put this file in the startup folder
Rem Author: Richard Beare

setlocal

Rem cd to c:/Git/whisper-timestamped/
cd /d %~dp0

Rem run whisper-typer-tool.py with python3
start "whisper" cmd /K python3 whisper-assistant.py

Rem run the PowerShell script to move the window
Rem powershell.exe -File "MoveToNewDesktop.ps1" "whisper"

Rem timeout /t 2

Rem for /f "tokens=*" %%a in ('nircmd findhwnd "whisper"') do set hwnd=%%a
rem nircmd win min %hwnd%