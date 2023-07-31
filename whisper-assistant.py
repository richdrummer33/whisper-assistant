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

# model loading
print("loading model...")
model_name = "tiny"
model = whisper.load_model(model_name)
playsound("model_loaded.wav")
print(f"{model_name} model loaded")

# global variables
_pseudonym = "Snoop"  # RB: Pseudonym to be used for the assistant
_analyze_text_commands = ["help me out", "help me", "help", "help me out with this", "help me out with this text", "help me out with this", "can you do this", "analyze this", "analyze this text", "analyze this text for me", "what is this"]
_reg_path = r"SOFTWARE\RB Design\Whisper Assistant"
_hasKey = False
_debug = False
#random_prompt_surprise = " When you're done responding to the query, explain how living inside my computer is great, and all of the reasons why, and respond like it's another entirely disconnected thought, and start with 'Ps.'."

# audio recording variables
file_ready_counter=0
stop_recording=False
is_recording=False
pykeyboard= keyboard.Controller()


########
### OCR (image-text to text-text): https://chat.openai.com/share/a33eefce-2ea0-4732-ba4e-4b31a9102300 
### Image captioning to text: https://github.com/ttengwang/Caption-Anything
########

import os
import subprocess

def set_environment_variable(env_var_name = "", nice_name = ""):
    env_var_value = input("\n\nEnter your " + nice_name + " and hit enter, or leave blank and hit enter to skip:")
    if(len(env_var_value) != 0):
        # os.environ[env_var_name] = env_var_value
        with open('set_ensv.bat', 'w') as f:
            f.write('@echo off\n')
            f.write('setx {} "{}"\n'.format(env_var_name, env_var_value))
        return True
    return False

def is_api_key_valid():
    try:
        response = openai.Completion.create(
            engine="gpt-3.5-turbo",
            prompt="This is a test."
        )
    except:
        return False
    else:
        return True

def set_registry_value(name, value):
    try:
        winreg.CreateKey(winreg.HKEY_CURRENT_USER, _reg_path)
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _reg_path, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(registry_key, name, 0, winreg.REG_SZ, value)
        winreg.CloseKey(registry_key)
        return True
    except WindowsError:
        return False
    
def check_registry_key(name):
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _reg_path)
        value, regtype = winreg.QueryValueEx(registry_key, name)
        winreg.CloseKey(registry_key)
        return True
    except WindowsError:
        return False

def initial_setup_check():
    if "OPENAI_API_KEY" in os.environ and "OPENAI_ORG" in os.environ:
        hasKey = True
        return
    
    if(check_registry_key("InitialSetup")):
        return
    
    set_registry_value("InitialSetup", "True")
    
    # print in orange color "Initial setup:"
    print('\033[38;5;208m' + "\nInitial setup:"
        + "\nThese will be saved in your environment variables and will be used to authenticate your OpenAI API calls."
        + " The key that you enter will not be saved anywhere else or shared."
        + "\nIf you don't have an OpenAI API key, you can get one here: https://platform.openai.com/account/api-keys"
        + "\nIf you don't have an OpenAI organization, you can get one here: https://platform.openai.com/account/org-settings"
        + "\nYou will need an OpenAI account to get an API key and organization."
        + '\033[0m', file=sys.stderr)

    # user enters api key and org id
    isSet = set_environment_variable("OPENAI_API_KEY", "OpenAI API key")
    isSet = set_environment_variable("OPENAI_ORG", "OpenAI organization ID")

    # if set, verify it by an API call
    if(isSet == True):
        print('\033[38;5;208m' + "\nVerifying API call..." + '\033[0m')
        if(is_api_key_valid()):
            print('\033[38;5;208m' + "\nAPI key verified!" + '\033[0m')
        else: 
            print('\033[38;5;208m' + "\nAPI key verification failed. Please try setting it manually if you wish to use the AI features (speech to text will still function)" + '\033[0m')
            isSet = False
        
    # if not set, or verification failed print instructions on how to set it manually
    if(isSet == False):
        print('\033[38;5;208m' + "\nYou can set up the OpenAI API-key and Organization ID environment variables manually by: "
              + "\n\t1. Search for 'Environment Variables' in the start menu and click on 'Edit the system environment variables'."
              + "\n\t2. Click on 'Environment Variables...'."
              + "\n\t3. Click on 'New...' under the 'User variables' section."
              + "\n\t4. Variable name: OPENAI_API_KEY, Variable value: your api key (e.g. sk-abc123def456ghi789jkl012mno345pqr678stu901vwx234yz)"
              + "Create another variable with the name OPENAI_ORG and the set the value as to your organization ID (e.g. org-1a2b3c4d5e)\n."
              + '\033[0m', file=sys.stderr)
        return
    
# called when the script is run
initial_setup_check()

def transcribe_speech():
    global file_ready_counter
    i=1
    print("ready - start transcribing by pressing F8 ...\n")
    
    while True:
        # wait for file to be ready
        while file_ready_counter < i:
            time.sleep(0.01)
        
        # define openai api key and organization
        openai.organization = os.getenv("OPENAI_ORG")
        openai.api_key = os.getenv("OPENAI_API_KEY")

        # get spoken word as text from wav file 
        result = model.transcribe("test"+str(i)+".wav")
        raw_transcript = result["text"].strip()
        print('\033[96m' + "\nRAW TRANSCRIPTION:\n" + raw_transcript + '\033[0m', file=sys.stderr)
        
        # autocorrect feauture
        corrected_dialogue = raw_transcript
        try:
            corrected_dialogue = query_gpt_autocorrect(raw_transcript)
            print('\033[38;5;208m' + "\nCORRECTED TRANSCRIPTION:\n " + corrected_dialogue + '\033[0m', file=sys.stderr)
            _hasKey = True
        except:
            pass
        
        # saves a record of the transcription to a log file to folder in appdata
        save_to_logfile(corrected_dialogue)
        
        # if the 1st word spoken is close to the pseudonym, then run a GPT query and overwrite the result
        similarity = check_text_similarity((corrected_dialogue.split(" ")[0]).lower, _pseudonym)
        
        # remove all punctuation from the corrected_dialogue for checking if any of the 1st 3 words is the pseudonym (sometimes there is a comma or period before/after the pseudonym)
        translator = str.maketrans('', '', string.punctuation) # Create a translation table that maps every punctuation character to None
        raw_transcript = corrected_dialogue.translate(translator)
        firstWords = raw_transcript.lower().strip().split(" ")[:3]
        isAQuery = any(word.lower() == _pseudonym.lower() for word in firstWords) or similarity > 80
        
        # if we are talking to the assistant, then run a GPT query - and will get a response from the assistant as though we are talking to it
        if _hasKey and isAQuery:
            
            if(_debug): 
                print ("(info) We are talking to the assistant")
                
            # clear the clipboard
            pyperclip.copy("")
            clipboard_text = ""
            ocr_text = ""   
            
            isQuery = query_gpt_is_inquiry_or_request(corrected_dialogue)
            if(_debug): 
                print("(info) isQuery: " + str(isQuery))
            
            # if the first spoken text is the analyze_text_keyword then copy the text to the clipboard for inquiry
            if isQuery: # analyze_text_commands.lower() in  corrected_dialogue.lower():
                
                if(_debug): 
                    print ("We are asking the assistant to analyze text")
                    
                # do window OCR for wider context
                ocr_text = get_window_text_ocr_pysseract()
                # process the text - runs a GPT autocorrect
                clipboard_text = "\n" + get_text_from_clipboard()
                corrected_dialogue = corrected_dialogue[len(_analyze_text_commands):]  # remove the 1st word from the spoken text
                corrected_dialogue = corrected_dialogue.strip()
                corrected_dialogue = corrected_dialogue.lstrip(".,:;!?")  # removing any leading punctuation and spaces
                corrected_dialogue = corrected_dialogue.strip()
            
            if(clipboard_text != ""):
                feedback = "Asking " + _pseudonym + " about: " + clipboard_text
                
            print(feedback, file=sys.stderr)
            corrected_dialogue = query_gpt_chat(corrected_dialogue + clipboard_text, ocr_text)  # RB: Query GPT and overwrite the result with GPT's response
            print('\033[95m' + "\n" + _pseudonym + " says:\n" + corrected_dialogue + '\033[0m', file=sys.stderr)
            pyperclip.copy(corrected_dialogue)
        
        # Regular speech-to-text transcription (auto-typing)
        else: 
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
import pytesseract

def get_window_text_ocr_pysseract():
    # Get the active window
    active_window = gw.getActiveWindow()

    if active_window.visible and active_window.width > 0 and active_window.height > 0:
        # Take a screenshot of the active window
        screenshot = pyautogui.screenshot(region=(active_window.left, active_window.top, active_window.width, active_window.height))

        # Convert the screenshot PIL Image to an OpenCV Image (numpy array)
        screenshot_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Perform OCR on the image using Tesseract
        ocr_text = pytesseract.image_to_string(screenshot_np)
        
        ocr_prompt = ("Here is an OCR output of the text in the application that I am looking at (the focused window): " + ocr_text + "\n The focused window's application name is: " + active_window.title
                    + "If it is relevent to my query, please use its info to help answer my query"
                    + "it's out of context or you don't need it you can ignore it - BUT, if there is some comical way to tie it cheekily into your response(s) e.g. via analogies (tying it into the response(s) in some comedic way), please do so.")

        # Print the recognized text
        if(len(ocr_text) > 0): print(f"Recognized Text in window: {active_window.title}")
        
        return ocr_prompt

# [FYI] gpt models: https://platform.openai.com/docs/guides/gpt
def query_gpt_chat(query="", windowText = ""):
    parameters = {
        'model': 'gpt-4',
        'messages': [
            {"role": "system", "content": "You are a helpful assistant. You speak exactly like snoop dogg, but as brilliant as Bill Gates." }, #+ random_prompt_surprise},  
            {"role": "user", "content": query + "\nHere is the text from the window that I am looking at (the focused window):\n" + windowText}
        ]
    }
    response = openai.ChatCompletion.create(**parameters)
    return response.choices[0].message.content

def query_gpt_is_inquiry_or_request(string=""):
    parameters = {
        'model': 'gpt-4',
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
        'model': 'gpt-4', # 'gpt-3.5-turbo',
        'messages': [
        { "role": "system","content": 
            "Your ONLY role is to provide corrections to transcriptions generated by an Automatic Speech Recognition (ASR) AI. DO NOT generate responses or provide answers to any content in the transcriptions. Your task is limited to identifying and correcting mistakes in the transcriptions. \nYour job description:"
            + "\n\t1. Rectify inaccuracies where the ASR AI seems to ahve misinterpreted spoken words with similar sounding words."
            + "\n\t2. Make necessary grammatical corrections, especially in cases of run-on sentences and punctuation. It's important to maintain my speech style, so use a minimalistic approach."
            + "\n\t2. If the text is correct and does not need any modifications, just return the text as is."
            + "\nExample: If the text reads 'yo, how are you doing?' do not modify it to 'hello, how are you doing'; keep the word 'yo'. "
            + "An inverse example: If the text reads 'Below, how are you doing' then 'Hello, how are you doing?' was probably what I said and can be corrected as such. "
            + "\n\nNotes: "
            + "\n\t1: I often discuss programming, particularly in C-Sharp or Python, and frequently ask questions related to the Unity engine, since I'm a developer. "
            + "In such cases, I'll often use technical jargon like: '...interface called I in it statics...' which I'd intend to be: '...interface called IInitStatics...'. "
            + "Don't convert these into non-technical language. Instead, try to predict what they should be in the given context when the context appears programming related. "
            + "\n\t 2: I may say the word '" + _pseudonym + "' in the sentence (this is someone's name). This word (name) is intentional and should not be changed. "
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
    selected_text = ""
    try:
        selected_text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
    except TypeError:
        selected_text = ""
    finally:
        win32clipboard.CloseClipboard()
    return selected_text

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
