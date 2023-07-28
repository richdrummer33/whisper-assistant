import codecs
import whisper
import time
import subprocess
import threading
import pyaudio
import wave
import winreg
import os
import sys
import openai
import time
from pynput import keyboard
from playsound import playsound
from datetime import datetime
from PyQt5.QtMultimedia import QAudioDeviceInfo
import warnings

######## FYI (SETUP) ########
# Set up your openai api key and organization in environment variables as follows:

#   1. Search for "Environment Variables" in the start menu and click on "Edit the system environment variables".
#   2. Click on "Environment Variables...".
#   3. Click on "New..." under the "User variables" section.
#   4. Enter "OPENAI_API_KEY" for the variable name and your OpenAI API key for the variable value.
#   5. Click "OK" on all windows to close them.

# API key can be found/made here: https://platform.openai.com/account/api-keys
# organization (org) can be found here: https://platform.openai.com/account/org-settings

######## TODO ########
# 1. Search google for the answer to a question
# 2. Give Snoop a voice
# 3. Chat history with Snoop - keeps a record of all convos in an indexed database
# 4. Specify a personality for the assistant by "Hey, Shaskespeare, can you do this for me?" 
# 5. OCR a window for context and then respond to a question, as specified in my query
# 6. Search a specific website for the answer to a question, as specified in my query
# 7. Search a specific link for the answer to a question, as specified in my query (simiar to 2 probably)
# 8. AI commands that can perform operations in windows

# load model. Model selection -> (tiny base small medium large)
print("loading model...")
model_name = "tiny"
model = whisper.load_model(model_name)
playsound("model_loaded.wav")
print(f"{model_name} model loaded")

pseudonym = "snoop"  # RB: Pseudonym to be used for the assistant
analyze_text_commands = ["help me out", "help me", "help", "help me out with this", "help me out with this text", "help me out with this", "can you do this", "analyze this", "analyze this text", "analyze this text for me", "what is this"]
#random_prompt_surprise = " When you're done responding to the query, explain how living inside my computer is great, and all of the reasons why, and respond like it's another entirely disconnected thought, and start with 'Ps.'."

file_ready_counter=0
stop_recording=False
is_recording=False
pykeyboard= keyboard.Controller()

# RB: List available gpt models 
# models = openai.Model.list() # World of knowledge, Bill Gates is my daddy, fo' shizzle!
# print(models.data[0].id)

########
### OCR (image-text to text-text): https://chat.openai.com/share/a33eefce-2ea0-4732-ba4e-4b31a9102300 
### Image captioning to text: https://github.com/ttengwang/Caption-Anything
########

def transcribe_speech():
    global file_ready_counter
    i=1
    print("ready - start transcribing by pressing F8 ...\n")
    
    while True:
        while file_ready_counter<i:
            time.sleep(0.01)
        
        openai.organization = os.getenv("OPENAI_ORG")
        openai.api_key = os.getenv("OPENAI_API_KEY")

        result = model.transcribe("test"+str(i)+".wav")
        spoken_dialogue = result["text"]
        
        # saves a record of the transcription to a log file to folder in appdata
        now = str(datetime.now()).split(".")[0]
        with codecs.open('transcribe.log', 'a', encoding='utf-8') as f:
            appdata_path = os.getenv('APPDATA') + "\\whisper-assistant\\"
            if not os.path.exists(appdata_path):
                os.makedirs(appdata_path)
            # write to appdata folder
            with codecs.open(appdata_path + 'transcribe.log', 'a', encoding='utf-8') as f:            
                f.write(now+" : "+result["text"]+"\n")
            
        # if the 1st word spoken is close to the pseudonym, then run a GPT query and overwrite the result
        similarity = check_text_similarity((corrected_dialogue.split(" ")[0]).lower, pseudonym)
        
        if spoken_dialogue.strip().split(" ")[0].lower().__contains__(pseudonym.lower()) or similarity > 80:
            # if the first spoken text is the analyze_text_keyword then copy the text to the clipboard for inquiry
            if query_gpt_is_inquiry_or_request(corrected_dialogue): # analyze_text_commands.lower() in  corrected_dialogue.lower():
                # process the text - runs a GPT autocorrect
                corrected_dialogue = process_prompt_text(spoken_dialogue)
                clipboard_text = "\n" + get_text_from_clipboard()
                corrected_dialogue = corrected_dialogue[len(analyze_text_commands):]  # remove the 1st word from the spoken text
                corrected_dialogue = corrected_dialogue.strip()
                corrected_dialogue = corrected_dialogue.lstrip(".,:;!?")  # removing any leading punctuation and spaces
                corrected_dialogue = corrected_dialogue.strip()
            
            feedback = "Asking " + pseudonym + "..."
            if(clipboard_text != ""):
                feedback = "Asking " + pseudonym + " about: " + clipboard_text
            print(feedback, file=sys.stderr)
            corrected_dialogue = query_gpt(corrected_dialogue + clipboard_text)  # RB: Query GPT and overwrite the result with GPT's response
            print(pseudonym + " says:\n" + corrected_dialogue, file=sys.stderr)
            pyperclip.copy(corrected_dialogue)
        else: 
            # Regular speech-to-text transcription, with autocorrect
            # GetWindowText()
            corrected_dialogue = process_prompt_text(spoken_dialogue)
            for char in corrected_dialogue:
                try:
                    pykeyboard.type(char)
                    time.sleep(0.0025)
                except Exception as e:
                    print("empty or unknown symbol" + e)    
                    
        os.remove("test"+str(i)+".wav")
        i=i+1

def process_prompt_text(spoken_dialogue=""):
     # trim any leading or trailing spaces
    spoken_dialogue = spoken_dialogue.strip()
    print('\033[96m' + "\nRAW TRANSCRIPTION:\n" + spoken_dialogue + '\033[0m', file=sys.stderr)
        
    # autocorrect the transcription
    corrected_dialogue = query_gpt_autocorrect(spoken_dialogue).strip()
    print('\033[38;5;208m' + "\nCORRECTED TRANSCRIPTION:\n " + corrected_dialogue + '\033[0m', file=sys.stderr)
    return corrected_dialogue

import numpy as np
import pygetwindow as gw
import pyautogui
import easyocr

windowText = ""
def get_window_text_ocr():
    # Clear the window text
    windowText = ""
    # Create an OCR reader
    reader = easyocr.Reader(['en'])  # replace 'en' with the language you want
    # Get the active window
    active_window = gw.getActiveWindow()

    # Check if the window is visible and has a non-zero size
    if active_window.visible and active_window.width > 0 and active_window.height > 0:
        # Take a screenshot of the active window
        screenshot = pyautogui.screenshot(region=(active_window.left, active_window.top, active_window.width, active_window.height))
        # Convert the image into a numpy array
        screenshot_np = np.array(screenshot)

        # Print the name of the app
        print(f"App Name: {active_window.title}")

        # Use OCR to recognize the text in the image
        #if "Slack" in active_window.title:
        recognized_texts = reader.readtext(screenshot_np)
        texts = [item[1] for item in recognized_texts]  # Extract only the text from each tuple
        windowText = " ".join(texts)  # Join all recognized texts into a single string
        windowText = "Here are the messages that I am responding to, for your reference and for context (a direct and unprocessed OCR conversion from Slack): " + windowText
        print(f"Text: {windowText}")
    else:
        print("No active visible window.")

styleGuide = "Rephrase what I said to be in the style of shakespeare. Feel free to add deeep insights and metaphors like shakespear would if the context of the provided text can be reflected in shakespeare's philosphy and actual known life experience. " # "Fix run on sentences and puncuation. Don't change my style of speech. Use a light touch. "

# [FYI] gpt models: https://platform.openai.com/docs/guides/gpt
def query_gpt(string=""):
    parameters = {
        'model': 'gpt-4',
        'messages': [
            {"role": "system", "content": "You are a helpful assistant. You speak exactly like snoop dogg, but as brilliant as Bill Gates." }, #+ random_prompt_surprise},  
            {"role": "user", "content": string}
        ]
    }
    response = openai.ChatCompletion.create(**parameters)
    return response.choices[0].message.content

def query_gpt_is_inquiry_or_request(string=""):
    parameters = {
        'model': 'gpt-3.5-turbo',
        'messages' : [
            { "role": "system", "content": 
                    "You are to return the word 'yes' if this text is asking for your input, seeking insight, looking for help, or requesting a specialized role or task to be performed. "
                  + "You are to return the word 'No' otherwise. " 
                  + "\nOnly return the word 'yes' OR 'no' and nothing else. "
            },
            { "role": "user", "content": string }
        ]
    }
    response = openai.ChatCompletion.create(**parameters)

    # Extract the assistant's reply
    assistant_reply = response.choices[0].message.content.lower()

    if 'yes' in assistant_reply:
        print("\n\n[support query]")
        return True
    else:
        print("\n\n[transcript only]")
        return False

def query_gpt_autocorrect(string=""):
    parameters = {
        'model': 'gpt-3.5-turbo', # 'gpt-3.5-turbo',
        'messages': [
        { "role": "system","content": 
            "Your primary role is to refine transcriptions generated by an Automatic Speech Recognition (ASR) AI. The task involves the following:"
            + "\n1. Rectifying inaccuracies where the ASR AI has misinterpreted spoken words for similar sounding alternatives."
            + "\n2. Predicting and replacing the misinterpreted words based on the context you can derive."
            + "\n3. Making necessary grammatical corrections, especially in cases of run-on sentences and punctuation. It's important to maintain my speech style, so use a minimalistic approach."
            + "For instance, if I say 'yo, how are you doing?' do not modify it to 'hello, how are you doing' as the intent is to preserve the original speaking style."
            + "\n\nEnsure to only make changes to words that are wrongly recognized by the ASR AI. " 
            + "\nKeep in mind that I often discuss programming, particularly in C-Sharp or Python, and frequently ask questions related to the Unity engine, since I'm a developer. "
            + "I use technical jargon like '...interface called I init statics' which should be corrected to '...interface called IInitStatics'. "
            + "Don't convert these into non-technical language, instead, try to predict what they should be in the given context, particularly when the context appears programming related. "
            + windowText
        },
            {"role": "user", "content": string}
        ]
    }
    response = openai.ChatCompletion.create(**parameters)
    return response.choices[0].message.content
    
from fuzzywuzzy import fuzz
def check_text_similarity(text1, text2):
    similarity_score = fuzz.token_set_ratio(text1, text2)
    return similarity_score

import win32clipboard
import pyperclip
def get_text_from_clipboard():
    win32clipboard.OpenClipboard()
    try:
        selected_text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    except TypeError:
        selected_text = ""
    finally:
        win32clipboard.CloseClipboard()
    return selected_text

def set_registry_value(path, name, value):
    try:
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, path)
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(registry_key, name, 0, winreg.REG_SZ, value)
        winreg.CloseKey(registry_key)
        return True
    except WindowsError:
        return False

#keyboard events
pressed = set()

COMBINATIONS = [
    {
        "keys": [
            # {keyboard.Key.ctrl ,keyboard.Key.shift, keyboard.KeyCode(char="r")},
            # {keyboard.Key.ctrl ,keyboard.Key.shift, keyboard.KeyCode(char="R")},
            # tilda key
            { keyboard.Key.f24 },
            { keyboard.Key.alt_l, keyboard.KeyCode(char="m")}
        ],
        "command": "start record",
    },
]

#------------

def get_max_channels():
    audio_info = QAudioDeviceInfo.defaultInputDevice()  # or QAudioDeviceInfo.defaultOutputDevice()
    max_channels = audio_info.supportedChannelCounts()[-1]
    # print it
    print("Max channels:", max_channels)
    return max_channels

#record audio
def record_speech():
    global file_ready_counter
    global stop_recording
    global is_recording
    
    # clear the clipboard
    pyperclip.copy("")

    is_recording=True
    chunk = 1024  # Record in chunks of 1024 samples
    sample_format = pyaudio.paInt16  # 16 bits per sample
    #channels = 2
    # get info with get_default_input_device_info()["maxInputChannels"]
    channels = 1 # get_max_channels()
    fs = 44100  # Record at 44100 samples per second
    p = pyaudio.PyAudio()  # Create an interface to PortAudio
    stream = p.open(format=sample_format,
                channels=channels,
                rate=fs,
                frames_per_buffer=chunk,
                input=True)

    frames = []  # Initialize array to store frames

    print("\ntranscription started...")
    playsound("on.wav")

    while stop_recording==False:
        data = stream.read(chunk)
        frames.append(data)

    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    # Terminate the PortAudio interface
    p.terminate()
    playsound("off.wav")
    print('processing...')

    # Save the recorded data as a WAV file
    warnings.filterwarnings("ignore")
    wf = wave.open("test"+str(file_ready_counter+1)+".wav", 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(sample_format))
    wf.setframerate(fs)
    wf.writeframes(b''.join(frames))
    wf.close()

    stop_recording=False
    is_recording=False
    file_ready_counter=file_ready_counter+1

#------------

#transcribe speech in infinte loop
t2 = threading.Thread(target=transcribe_speech)
t2.start()

#hot key events
def on_press(key):
    pressed.add(key)

def on_release(key):
    global pressed
    do_record()
    pressed = set()

def on_key_press(event):
    if event.name == '~':
        do_record()
        print("Tilde key pressed")

def do_record():
    global stop_recording
    global is_recording
    for c in COMBINATIONS:
        for keys in c["keys"]:
            if keys.issubset(pressed):
                if c["command"]=="start record" and stop_recording==False and is_recording==False:
                    t1 = threading.Thread(target=record_speech)
                    t1.start()
                else:
                    if c["command"]=="start record" and is_recording==True:
                        stop_recording=True

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
