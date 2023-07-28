# whisper-assistant

This is a python script using [openai/whisper](https://github.com/openai/whisper) to type with your voice amd respond to inquiries, with personality (if you so desire).

After you start the script you just press **ALT-M** to start/stop the listener. After the listener is finsihed, it will attempt to autocorrect what you said in case of any misheard words (using gpt). It will then ype what you said starting at the current cursor position in any editor, input field etc.

It also can act as an assistant when you start by saying "snoop" after activating the mic listener. The assistant currently has snoop dogg persona, which you can change.

This is forked from https://github.com/dynamiccreator/whisper-typer-tool.

Note: Check the gpt model in the code where it sends the api request. E.g. gpt-4. At the time of writing, not everyone has access to gpt4 (tradeoff: gpt4 is slower).


# Setup Instructions

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

- Search for "Environment Variables" in the start menu and click on "Edit the system environment variables".
- Click on "Environment Variables...".
- Click on "New..." under the "User variables" section.
- Enter "OPENAI_API_KEY" for the variable name and your OpenAI API key for the variable value.
- Click "OK" on all windows to close them.

API key(s) can be found/made here: https://platform.openai.com/account/api-keys

Your organization (org) can be found here: https://platform.openai.com/account/org-settings

**Step 4:**

    python3 whisper-assistant.py
    or 
    run this: _run-whisper-assistant.bat
