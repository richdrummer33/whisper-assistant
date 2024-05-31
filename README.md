# whisper-assistant

This is a python script using [openai/whisper](https://github.com/openai/whisper) to type with your voice. It simply types what you say, emulating keystrokes. This is my primary way of typing. Works like a charm.

## Deprecated feature

It includes features for an AI assistant, with voice. The defaults are Snoop Dogg and Mr Bean (I can claim I was first to make a Snoop assistant lol). You can change the prompt to be whomever you like, and give it personality as you like (or lack thereof).

## Setup Instructions

**Step 1 (Linux - Ubuntu,Debian):**

    sudo apt-get install python3 python3-pip git ffmpeg

**Step 1 (Windows):**

- Download ffmpeg from https://ffmpeg.org/ , unpack it and paste "ffmpeg.exe" in this folder
- Download and Install git from https://git-scm.com/download/win
- Download and Install python3 from https://www.python.org/downloads/windows/

**Step 1 (MAC OS - not tested):**

Download and Install ffmpeg, git and python3

**Step 2:**

    pip install -r requirements.txt

**Step 3:**

Set up your openai api key and organization in environment variables as follows:

1. Search for "Environment Variables" in the start menu and click on "Edit the system environment variables".
2. Click on "Environment Variables...".
3. Click on "New..." under the "User variables" section.
4. Enter "OPENAI_API_KEY" for the variable name and your OpenAI API key for the variable value.
5. Click "OK" on all windows to close them.
   API key can be found/made here: https://platform.openai.com/account/api-keys
   organization (org) can be found here: https://platform.openai.com/account/org-settings

**Step 4:**

    python3 whisper-typer-tool.py
