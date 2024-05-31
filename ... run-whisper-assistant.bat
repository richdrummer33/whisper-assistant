@echo off
CALL C:\ProgramData\anaconda3\Scripts\activate.bat
CALL activate openai-whisper
cd %~dp0
python whisper-assistant.py
pause