@echo off
CALL C:\ProgramData\anaconda3\Scripts\activate.bat
CALL activate speech-to-text
cd %~dp0
python whisper-assistant.py
pause