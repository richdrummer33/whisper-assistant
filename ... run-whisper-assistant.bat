@echo off
CALL C:\ProgramData\anaconda3\Scripts\activate.bat
CALL activate whisper-assistant
cd %~dp0
python whisper-assistant.py
pause