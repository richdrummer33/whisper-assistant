title whisper-assistant

Rem a batch script that starts whisper-typer-tool.py with python3 when windows boots
Rem Put this file in the startup folder
Rem Author: Richard Beare

setlocal

Rem cd to c:/Git/whisper-timestamped/
cd /d %~dp0

Rem run whisper-typer-tool.py with python3
start "whisper" cmd /K python3.11 TogglAutomator.py
