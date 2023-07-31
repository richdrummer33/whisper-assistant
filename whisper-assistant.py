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
import string
from pynput import keyboard
from playsound import playsound
from datetime import datetime
from PyQt5.QtMultimedia import QAudioDeviceInfo
import warnings

######## USER SETUP ########
# Set up your openai api key and organization in environment variables as follows:

#   1. Search for "Environment Variables" in the start menu and click on "Edit the system environment variables".
#   2. Click on "Environment Variables...".
#   3. Click on "New..." under the "User variables" section.
#   4. Enter "OPENAI_API_KEY" for the variable name and your OpenAI API key for the variable value.
#   5. Click "OK" on all windows to close them.

# API key can be found/made here: https://platform.openai.com/account/api-keys
# organization (org) can be found here: https://platform.openai.com/account/org-settings

######## TODO (DEV NOTES) ########
# • Search google for the answer to a question
# • Give Snoop a voice
# • Chat history with Snoop - keeps a record of all convos in an indexed database
# • Specify a personality for the assistant by "Hey, Shaskespeare, can you do this for me?" 
# • OCR a window for context and then respond to a question, as specified in my query
# • Search a specific website for the answer to a question, as specified in my query
# • Search a specific link for the answer to a question, as specified in my query (simiar to 2 probably)
# • AI commands that can perform operations in windows
# • Clean UI

# load model. Model selection -> (tiny base small medium large)
print("loading model...")
model_name = "tiny"
model = whisper.load_model(model_name)
playsound("model_loaded.wav")
print(f"{model_name} model loaded")

pseudonym = "Snoop"  # RB: Pseudonym to be used for the assistant
analyze_text_commands = ["help me out", "help me", "help", "help me out with this", "help me out with this text", "help me out with this", "can you do this", "analyze this", "analyze this text", "analyze this text for me", "what is this"]
#random_prompt_surprise = " When you're done responding to the query, explain how living inside my computer is great, and all of the reasons why, and respond like it's another entirely disconnected thought, and start with 'Ps.'."

file_ready_counter=0
stop_recording=False
is_recording=False
pykeyboard= keyboard.Controller()

_debug = True
_noMic = False

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
        # wait for file to be ready
        while file_ready_counter<i:
            time.sleep(0.01)
        
        # define openai api key and organization
        openai.organization = os.getenv("OPENAI_ORG")
        openai.api_key = os.getenv("OPENAI_API_KEY")

        # get spoken word as text from wav file 
        result = model.transcribe("test"+str(i)+".wav")
        spoken_dialogue = result["text"].strip()
        print('\033[96m' + "\nRAW TRANSCRIPTION:\n" + spoken_dialogue + '\033[0m', file=sys.stderr)
        
        # autocorrect feauture
        corrected_dialogue = query_gpt_autocorrect(spoken_dialogue)
        print('\033[38;5;208m' + "\nCORRECTED TRANSCRIPTION:\n " + corrected_dialogue + '\033[0m', file=sys.stderr)
        
        # saves a record of the transcription to a log file to folder in appdata
        save_to_logfile(corrected_dialogue)
        
        # if the 1st word spoken is close to the pseudonym, then run a GPT query and overwrite the result
        similarity = check_text_similarity((corrected_dialogue.split(" ")[0]).lower, pseudonym)
        
        # remove all punctuation from the corrected_dialogue for checking if the 1st or 2nd word is the pseudonym (sometimes there is a comma or period before/after the pseudonym)
        translator = str.maketrans('', '', string.punctuation) # Create a translation table that maps every punctuation character to None
        corrected_dialogue_noPunc = corrected_dialogue.translate(translator)
        
        # gets first 2 words in the dialogue. For checking if we are talking to the assistant (said name of assistant).
        firstWords = corrected_dialogue_noPunc.lower().strip().split(" ")[:2]
        
        # if we are talking to the assistant, then run a GPT query and overwrite the result with GPT's response
        if any(word.lower() == pseudonym.lower() for word in firstWords) or similarity > 80:
            
            if(_debug): 
                print ("(info) We are talking to the assistant")
                
            clipboard_text = ""
            
            isQuery = query_gpt_is_inquiry_or_request(corrected_dialogue)
            if(_debug): 
                print("(info) isQuery: " + str(isQuery))
            
            # if the first spoken text is the analyze_text_keyword then copy the text to the clipboard for inquiry
            if isQuery: # analyze_text_commands.lower() in  corrected_dialogue.lower():
                
                if(_debug): 
                    print ("We are asking the assistant to analyze text")
                    
                # do window OCR for wider context
                get_window_text_ocr()
                # process the text - runs a GPT autocorrect
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
            print('\033[95m' + "\n" + pseudonym + " says:\n" + corrected_dialogue + '\033[0m', file=sys.stderr)
            pyperclip.copy(corrected_dialogue)
            
        else: 
            # Regular speech-to-text transcription, with autocorrect
            # GetWindowText()
            if(_debug):
                print ("(info) Transcribing speech. No GPT query.")
                
            for char in corrected_dialogue:
                try:
                    pykeyboard.type(char)
                    time.sleep(0.0025)
                except Exception as e:
                    print("empty or unknown symbol" + e)    
                    
        os.remove("test"+str(i)+".wav")
        i=i+1

def save_to_logfile(dialogue=""):
    now = str(datetime.now()).split(".")[0]
    with codecs.open('transcribe.log', 'a', encoding='utf-8') as f:
        # create folder in %appdata% if does not exist
        appdata_path = os.getenv('APPDATA') + "\\whisper-assistant\\"
        if not os.path.exists(appdata_path):
            os.makedirs(appdata_path)
        # write to appdata folder
        with codecs.open(appdata_path + 'transcribe.log', 'a', encoding='utf-8') as f:            
            f.write(now + " : " + dialogue + "\n")
        
import numpy as np
import pygetwindow as gw
import pyautogui
import easyocr
import cv2

windowText = ""
def get_window_text_ocr():
    # Clear the window text
    ocrPromptText = ""
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
        # Resize the image using OpenCV instead of 'PIL.Image.ANTIALIAS'
        model_height = 64  # Set the desired model height for easyocr
        img_height = screenshot_np.shape[0]
        img_width = screenshot_np.shape[1]
        ratio = model_height / img_height
        resized_img = cv2.resize(screenshot_np, (int(img_width * ratio), model_height), interpolation=cv2.INTER_LINEAR)

        recognized_texts = reader.readtext(resized_img, add_margin=0.55, width_ths=0.7, link_threshold=0.8, decoder='beamsearch', beamWidth=10)
        texts = [item[1] for item in recognized_texts]  # Extract only the text from each tuple
        ocrWindowText = " ".join(texts)  # Join all recognized texts into a single string
        ocrPromptText = "Here is an OCR output of the text in the application that I am looking at (the focused window): " + ocrWindowText + "\n The focused window's application name is: " + active_window.title;
        print("\n[OCR output]\n" + ocrPromptText)
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
                    "Please return the word 'yes' if the provided text explicitly asks a question for or about you, requests your expertise, " 
                    + "seeks assistance, or designates a specific role or task for you to execute. If the text does not meet these conditions, "
                    + "return the word 'no'. Respond with 'yes' or 'no' only."
            },
            { "role": "user", "content": string }
        ]
    }
    response = openai.ChatCompletion.create(**parameters)

    # Extract the assistant's reply
    assistant_reply = response.choices[0].message.content.lower()
    
    if(_debug): 
        print ("(info) is query GPT response: " + assistant_reply)

    if 'yes' in assistant_reply:
        print("\n[support query]")
        return True
    else:
        print("\n\n[transcript only]")
        return False

def query_gpt_autocorrect(string=""):
    parameters = {
        'model': 'gpt-3.5-turbo', # 'gpt-3.5-turbo',
        'messages': [
        { "role": "system","content": 
            "Your primary role is to refine transcriptions generated by an Automatic Speech Recognition (ASR) AI. Your task involves the following:"
            + "\n\t1. Rectify inaccuracies where the ASR AI has misinterpreted spoken words with similar sounding words."
            + "\n\t2. Predict and replace the misinterpreted words with the words that you think I really said."
            + "\n\t3. Make necessary grammatical corrections, especially in cases of run-on sentences and punctuation. It's important to maintain my speech style, so use a minimalistic approach."
            + "For instance, if the text says 'yo, how are you doing?' do not modify it to 'hello, how are you doing' "
            + "And if the text says 'Hello, how are you doing?' do not modify it to 'Yo, how are you doing?'. In the context, it's unlikely that ASR mistook 'hello' (2 syllabals) for 'yo' (1 syllable), and vice-versa. "
            + "It's key that you preserve my manner of speech. "
            + "\n\nNote: I often discuss programming, particularly in C-Sharp or Python, and frequently ask questions related to the Unity engine, since I'm a developer. "
            + "In such cases, I'll often use technical jargon like: '...interface called I in it statics...' which I'd intend to be: '...interface called IInitStatics...'. "
            + "Don't convert these into non-technical language. Instead, try to predict what they should be in the given context when the context appears programming related. "
            + "\n\n MOST IMPORTANTLY: DO NOT RESPOND WITH AN ANSWER OR YOUR THOUGHTS - ONLY MAKE CORRECTIONS. "
            + windowText
        },
            {"role": "user", "content": string}
        ]
    }
    response = openai.ChatCompletion.create(**parameters).choices[0].message.content
    response = response.strip() # remove leading and trailing spaces
    response = response.lstrip(".,:;!?") # removing any leading punctuation and spaces
    return response
    
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
    chunk = 1024  # Record in chunks of 1024 samplesSure, I'll do my best to rectify any inaccuracies and make necessary grammatical corrections. Please provide me with the text that needs refinement.
    sample_format = pyaudio.paInt16  # 16 bits per sample
    #channels = 2
    # get info with get_default_input_device_info()["maxInputChannels"]
    channels = 1 # get_max_channels()
    fs = 44100  # Record at 44100 samples per second
    p = pyaudio.PyAudio()  # Create an interface to PortAudio
    try:
        stream = p.open(format=sample_format,
                    channels=channels,
                    rate=fs,
                    frames_per_buffer=chunk,
                    input=True)
    except Exception as e:
        print(e + "\n\nIt's likey that no microphone is connected. ")
        return
    
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
