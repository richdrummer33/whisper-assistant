@echo off
CALL C:\ProgramData\anaconda3\Scripts\activate.bat
CALL activate whisper-assistant
cd \d %~dp0
python whisper-assistant_llm-callbacks.py
pause