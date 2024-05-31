#region SETUP

import codecs
import whisper
import time
import threading
import pyaudio
import wave
import winreg
import os
import sys
import openai
import time
import string
import shutil
import torch
import warnings
import numpy as np
import pandas as pd
import keyboard as kb
import speech_recognition as sr
import win32api, win32process, win32con # FOR SETTING APP PRIORITY TO PREVENT UNRESPONSIVE BEHAVIORS
from pynput import keyboard
from playsound import playsound
from datetime import datetime
from PyQt5.QtMultimedia import QAudioDeviceInfo
from elevenlabslib import *
from elevenlabslib import helpers
# import OcrWindowsAutomation as winauto


#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
#>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

# NOTES FOR USERS:
# API key can be found/made here: https://platform.openai.com/account/api-keys
# organization (org) can be found here: https://platform.openai.com/account/org-settings
# How to manually (if you so desire) set your api-key & org-id in Windows:
#   1. Search for "Environment Variables" in the start menu and click on "Edit the system environment variables".
#   2. Click on "Environment Variables...".
#   3. Click on "New..." under the "User variables" section.
#   4. Enter "OPENAI_API_KEY" for the variable name and your OpenAI API key for the variable value.
#   5. Click "OK" on all windows to close them.
# These can also be set up automatically when you run this script for the first time.

#<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
#<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

######## TODO (DEV NOTES) ########
# • [seperate script?] Checks if I've pushed to git on current branch and main branch at EOD and/or yells at me if I walk away at EOD and/or interrrupts sleep if I didn't push.
# • [seperate script?] Auto STARTS/STOPS TOGGL. Detects when I'm in front of computer and says hello, maybe via mouse movement.
# • AI monitors my writing (writing adjacent to my slack profile pic recog via cv2) and provides "ding" sfx - provides suggestions if the text has negative tones
# • Break timer - if working or doing personal projects, takes mouse & kb control away and forces me to take break as long as not in meeting. Is resistant to keystrokes (fights back)
# • Auto-GUI interactions - do things like "find this file" and allow pyautogui to do it 
# • Can perform searches and analysis on projects/data 
#       • Can keyword-index contents of files using Everything - for basic keyword searches
#       • Can index relevant folder data with llama, and perform queries on them (can it also do custom indexing of files? E.g. by keyword or tag?)
# • Record audio in chunks and take screencaps of the whisper window in chunks, and then process the chunks in parallel. This will allow for a more responsive UI.
# • Special voice commands like 'context...' or 'reply...'
# • Chat history with assistant - keeps a record of all convos in an indexed database
# • Integrate lang-chain to give memory and enhanced functionality to the assistant
# • Auto-GUI interactions
#   • Do things like "find this file" and allow pyautogui to do it (https://github.com/vincentbavitz/bezmouse)
#   • Have assistant (optional) muse or comment as he does it (each action is feedback to GPT)
# • Fix Lockup bug and - make sure all processes canceled when toggling mic state 
# • Stream Deck integration
# • It doesn't always detect the hotkey. Make sure it's running in the background properly.
# • User prefs:
#       • List the GPT models and allow users to select which one they want to use. 
#           ~ Set the GPT models in a config file and inform the user that they can change it there if they wish.
#       • Allow users to define their assistant's name and personality when they launch this app.
#           ~ Set the assistant's name and personality in a config file and inform the user that they can change it there if they wish.
#       • Allow users to define their own hotkey for toggling the mic state.
#           ~ Set the assistant's name and personality in a config file and inform the user that they can change it there if they wish.
#       • Allow users to define their name. 
# • Search google for the answer to a question if unsure
# • Specify a personality for the assistant by "Hey, Shaskespeare, can you do this for me?" 
# • OCR a window for context and then respond to a question, as specified in my query
# • Search a specific website for the answer to a question, as specified in my query
# • Search a specific link for the answer to a question, as specified in my query (simiar to 2 probably)
# • AI commands that can perform operations in windows
# • Clean UI

######## VOICE IDEAS ########
# • GLADOS
# • The G-Man
# • Snoop Dogg
# • Eli Vance
# • Dr. Kleiner
# (other video game characters:)
# • Wheatley
# • Cave Johnson
# • Cave Johnson's assistant
# • Cave Johnson's assistant's assistant
# • Cave Johnson's assistant's assistant's assistant

# Set process priority
pid = win32api.GetCurrentProcessId()
handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
win32process.SetPriorityClass(handle, win32process.HIGH_PRIORITY_CLASS)

# GPU CUDA for whisper
# device = "cuda" if torch.cuda.is_available() else "cpu"

# thread for loading model

# model loading 
# thread for loading model
model = None
def load_model_thread():
    global model

    device = "cuda"
    if device == "cuda":
        torch.cuda.init()
    print(f"Using device: {device}")

    model_name = "small.en"
    print("loading model " + model_name + "...", file=sys.stderr)
    model = whisper.load_model(model_name).to(device)
    # clear the console
    os.system('cls' if os.name == 'nt' else 'clear')
    
# global variables
_fullName = "Mr Bean"
_pseudonym = "bean"  # RB: Pseudonym to be used for the assistant
_improveKwd = "correct"
_windowsAutomationKeyword = "windows"
_elevenLabsVoice = "DrNeab"
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

#endregion

##############################################
################ OPENAI SETUP ################
##############################################
#region OPENAI

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
    parameters = {
        'model': 'gpt-3.5-turbo',
        'messages' : [
            {"role": "user", "content": 
                "Say 'yes'" 
            }
        ]
    }
    try:
        response = openai.ChatCompletion.create(**parameters).choices[0].message.content
    except:
        return False
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
    
def get_registry_value(name):
    try:
        registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _reg_path)
        value, regtype = winreg.QueryValueEx(registry_key, name)
        winreg.CloseKey(registry_key)
        return value
    except WindowsError:
        return 0
    
# increments a registry value by 1 and returns the new value
def increment_registry_value(name):
    try:
        # if the key does not exist, then create it
        if(check_registry_key(name) == False):
            # create the key
            set_registry_value(name, "0")
            
        # get the value
        value = get_registry_value(name)
        # increment the value
        new_value = int(value) + 1
        # set the new value
        set_registry_value(name, str(new_value))
        # return the new value
        return new_value
    
    except WindowsError:
        return 0

def initial_setup_check():
    global _hasKey  # This is the crucial part
    try:
        _hasKey = is_api_key_valid()
        if _hasKey:
            os.system('cls' if os.name == 'nt' else 'clear')
    except:
        print("\nOpenAI GPT API key and organization ID NOT FOUND!", file=sys.stderr)
        _hasKey = False
    
    # if the folder eleven-labs-responses does not exist, then create it
    if not os.path.exists("eleven-labs-responses"):
        os.makedirs("eleven-labs-responses")
    
    if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_ORG"):
        if(check_registry_key("KeyFound") == False):
            set_registry_value("KeyFound", "True")
            print('\033[38;5;208m' 
                + "\nAPI key and organization ID found. "
                + "You can make AI queries by saying 'Hey, " + _pseudonym + ", ...' " + 
                + "or simply '"+ _pseudonym + ", ...' (e.g. 'Hey, " + _pseudonym + ", what is the mass of an unladen swallow?')\n"
                + '\033[0m', file=sys.stderr)
        hasKey = True
        return
    
    if(check_registry_key("InitialSetup")):
        set_registry_value("KeyFound", "False")
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

#endregion
 
#########################################################
####### main speech recognition and transcription #######
#########################################################
def transcribe_speech():
    global file_ready_counter
    global device
    i=1

    print("Awaiting model loading...", file=sys.stderr)

    # await async model loading
    while model == None:
        time.sleep(0.1)
    
    print("ready - start transcribing by pressing Alt-M ...\n")
    playsound("model_loaded.wav")
    
    while True:
        # wait for file to be ready
        while file_ready_counter < i:
            time.sleep(0.01)
        
        # transcribe speech
        # with torch.cuda.device(device):
        print('processing...')
        result = model.transcribe("test"+str(i)+".wav")
        transcript = result["text"].strip()

        # print the transcript
        print('\033[38;5;155m' + transcript + '\033[0m', file=sys.stderr)
        # print(, file=sys.stderr)
        
        # strip and clean
        transcript = transcript.strip() # remove leading and trailing spaces

        # IF GIT COMMAND: Remove trailing period if starts with 'git'
        if(transcript.lower().startswith("git")):   
            print ("[git command]")
            transcript = transcript.rstrip(".")

        # IF NOT FULL SENTENCE: Remove any trailing periods
        if(len(transcript) < 25):
            transcript = transcript.rstrip(".")
        
        # FINALLY: Type it out!
        for char in transcript:
            try:
                # Cancel hotkey
                if kb.is_pressed('alt') and kb.is_pressed('w'): 
                    break

                # Keystroke
                pykeyboard.type(char)
                time.sleep(0.0075)
                
            except Exception as e:
                print("empty or unknown symbol" + e)    
                    
        # Done!
        # Delete the file
        os.remove("test"+str(i)+".wav")
        i=i+1

######################################################### 
##################### Extra features ####################
#########################################################
#region EXTRAS

import pygetwindow as gw
import pyautogui
import cv2
import pytesseract

############################
### OCR Text from Window ###
############################
# returns an image of the active window
def get_chat_window_screenshot_pysseract():
    # Get the list of all windows with 'whisper' in their title
    whisper_windows = gw.getWindowsWithTitle('whisper')

    # Loop through the list of windows
    for window in whisper_windows:
        if window.visible and window.width > 0 and window.height > 0:
            # Take a screenshot of the window
            screenshot = pyautogui.screenshot(region=(window.left, window.top, window.width, window.height))

            # Convert the screenshot PIL Image to an OpenCV Image (numpy array)
            screenshot_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            # Return the screenshot and stop the function
            return screenshot_np

    # If no suitable window was found, return None
    return None

# returns the text from the active window and stores the OCR dataframe for later access by auto gui feature (mouse movements, etc.)
def get_window_text_ocr_pysseract():
    # Get the active window
    active_window = gw.getActiveWindow()

    if active_window.visible and active_window.width > 0 and active_window.height > 0:
        # Take a screenshot of the active window
        screenshot = pyautogui.screenshot(region=(active_window.left, active_window.top, active_window.width, active_window.height))

        # Convert the screenshot PIL Image to an OpenCV Image (numpy array)
        screenshot_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        # Perform OCR on the image using Tesseract
        # ocr_text = pytesseract.image_to_string(screenshot_np)
        
        # Perform OCR on the image using Tesseract and get the result as data 
        ocr_data = pytesseract.image_to_data(screenshot_np, output_type=pytesseract.Output.DATAFRAME)
        # use pandas to format and print the data
        pd.set_option('display.max_columns', None)
        if(_debug and len(ocr_data) > 0) : print("\n" + ocr_data)
        
        ocr_prompt = (f"OCR output from focused window '{active_window.title}':\n{ocr_data}\n"
                    "If relevant, include this in your answer. If not, ignore it. "
                    "But if there's a fun way to relate this info to your response, please do so!")

        # Print the recognized text
        if(len(ocr_data) > 0): print(f"Recognized Text in window: {active_window.title}")
        
        return ocr_prompt

###########################
### Auto Mouse Movement ###
###########################
def instruct_mouse_movement(ocr_df, target_text, deviation=50, speed=5):
    '''
    Instructs the mouse to move to the location of the given target text.
    The location is found using the OCR dataframe from Tesseract.

    Parameters:
    ocr_df (pandas.DataFrame): The OCR dataframe from Tesseract.
    target_text (str): The text string to move the mouse to.
    deviation (int): The deviation for the bezier curve points.
    speed (int): The speed multiplier for the mouse movement.

    Returns:
    bool: True if successful, False otherwise.
    '''
    # Find rows in the dataframe that contains the target text
    target_rows = ocr_df[ocr_df['text'] == target_text]

    # If no such rows exist, return False
    if target_rows.empty:
        return False

    # Select the first row that contains the target text
    target_row = target_rows.iloc[0]

    # Compute the center point of the bounding box for the target text
    center_x = target_row['left'] + target_row['width'] / 2
    center_y = target_row['top'] + target_row['height'] / 2

    # Instruct the mouse to move to the center of the bounding box
    # move_to_area(center_x, center_y, target_row['width'], target_row['height'], deviation, speed)

    return True

#def perform_gui_actions(actions):
#    winauto.perform_gui_sequence_of_operations(actions)

import json
def gpt_gui_actions():
    my_custom_functions = [ {
        'name': 'perform_gui_actions',
        'description': 'Perform a sequence of GUI operations including mouse movements, clicks, and keyboard actions.',
        'parameters': {
            'type': 'array',
            'items': {
                'oneOf': [
                    {
                        'type': 'object',
                        'properties': {
                            'text': {
                                'type': 'string',
                                'description': 'Text element to move the cursor to'
                            },
                            'click_action': {
                                'type': 'string',
                                'description': 'Click action to perform, either left mouse button (lmb) or right mouse button (rmb)'
                            }
                        },
                        'required': ['text', 'click_action']
                    },
                    {
                        'type': 'object',
                        'properties': {
                            'keystrokes': {
                                'type': 'string',
                                'description': 'Characters to be typed using pykeyboard'
                            }
                        },
                        'required': ['keystrokes']
                    },
                    {
                        'type': 'object',
                        'properties': {
                            'key_action': {
                                'type': 'string',
                                'description': 'Key action to be performed using pykeyboard'
                            }
                        },
                        'required': ['key_action']
                    }
                ]
            }
        }
    }
    ]
    
   # Assume 'text_click_tuples' is the list of tuples you want to process
    response = openai.ChatCompletion.create(
    model = 'gpt-3.5-turbo',
    messages = [{'role': 'user', 'content': "open 'This PC'"}],
    functions = my_custom_functions,
    function_call = 'auto'
    )   
    
    if response.get("function_call"):
        function_name = response["function_call"]["name"]
        function_args = json.loads(response["function_call"]["arguments"])

    print(response)

# [FYI] gpt models: https://platform.openai.com/docs/guides/gpt
def query_gpt_chat(query="", windowText = "", playVoice = False):
    parameters = {
        'model': 'gpt-4',
        'messages': [
            {"role": "system", "content":
                "Embody " + _fullName + " - you speek exactly like " + _fullName + " and have his personality. But you are as smart and knowledgeable as Bill Gates. "
                 "For inquiries that truly demand a detailed response, provide a two sentence summary <in angled brackets> upfront with the key details -not *too* short. "
                + "follow this with the detailed response only if necessarry. "
                + "For straightforward inquiries, just a summary <in angled brackets> will suffice. "
                + "Remember, you are speaking to Richard who is an experienced software dev and engineer."
                },
            {"role": "user", "content":  query + "\nHere is the text from the focused window:\n" + windowText}
            
            # OLD verbose version:
            #{"role": "system", "content": 
            #    "You are a helpful assistant. You speak like Mr. Bean (do your best), but are as brilliant as Bill Gates. "
            # +  "Despite your 'Mr. Bean' nature, you are skilled at being concise in your responses, with a few 'beanisms' sprinked in here and there in some responses."
            # +  "Yor audience is smart. If you feel that you need to respond with more than one paragraph worth of text, then provide a shortened response (one, max two, sentences) <within angle brackets> at the top, and provide a full version below, without brackets. "
            # +  "If you feel that a short response is all that is necessary, then provide only the short response <within angle brackets>. "
            # +  "FYI: My name is Richard."
            # },
            #{"role": "user", "content": query + "\nHere is the text from the window that I am looking at (the focused window):\n" + windowText}
        ]
    }
    response = openai.ChatCompletion.create(**parameters)
    
    # if playVoice:
    #     play_voice(response.choices[0].message.content)
    
    return response.choices[0].message.content

def query_gpt_autocorrect(string="", improveWriting = False):
    role1 = ""
    role2 = ""
    
    if improveWriting:
        role1 = "Your ONLY role is to improve the text. "
        role2 = "Your task is limited to reformatting the text.\n"
    else:
        role1 = "Your ONLY role is to provide corrections to transcriptions generated by an Automatic Speech Recognition (ASR) AI. "
        role2 = "Your task is limited to identifying and correcting mistakes in the transcriptions.\n"
    print("GPT correcting text")
    parameters = {
        'model': 'gpt-3.5-turbo', # 'gpt-4',
        'messages': [
        { "role": "system","content": 
            # GPT-4 made a more...
            role1
            + "DO NOT generate responses or provide answers to any content in the transcriptions. "
            + role2
            + "Your job description:"
            + "".join([
                "\n\t1. Rectify inaccuracies where the ASR AI seems to have misinterpreted spoken words with similar sounding words.",
                "\n\t2. Make necessary grammatical corrections, especially in cases of run-on sentences and punctuation. Maintain my speech style; be minimalistic.",
                "\n\t3. Predict formatting (e.g. paragraph formatting, point notes).",
                "\n\t4. If the text appears correct, return the text as-is."
            ])
            + "\nExample: If the provided text is: 'yo, how are you doing?', keep it as-is. If the text is: 'Below, how are you doing', change it to 'Hello, how are you doing?'."
            + "\n\nNotes:"
            + "".join([
                "\n\t1. As a developer, I often discuss programming, particularly in C-Sharp or Python, and Unity engine. I use technical jargon, game words, and git commands.",
                "\n\t2. Don't convert these into non-technical language, try to predict what they should be in the programming context.",
                "\n\t3. Prepend '@' to names Bela, Dylan, Ollie, Kenny, and Graham (e.g., @Bela).",
                "\n\t4. If I say the word '" + _pseudonym + "', it's someone's name and should not be changed."
            ])
        },
            {"role": "user", "content": string}
        ]
    }
    print("GPT correcting text RESPONSE")
    response = openai.ChatCompletion.create(**parameters).choices[0].message.content
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
            # { keyboard.Key.f11 },
            { keyboard.Key.alt_l, keyboard.KeyCode(char="q")}
        ],
        "command": "start record",
    },
]
#endregion

#########################################################
################## record audio #########################
#########################################################
#region RECORD

def get_max_channels():
    audio_info = QAudioDeviceInfo.defaultInputDevice()  # or QAudioDeviceInfo.defaultOutputDevice()
    max_channels = audio_info.supportedChannelCounts()[-1]
    # print it
    print("Max channels:", max_channels)
    return max_channels

def play_beep_async():
    t3 = threading.Thread(target=async_recorder_timeout_beeper)
    t3.start()

# PLAY SOUND for final N seconds of recording, e.g. 3 seconds (defined in async_record_speech function)
do_countdown_beep = False
def async_recorder_timeout_beeper():
    playsound("beep.wav")


# RECORD AUDIO
def async_record_speech():
    global file_ready_counter
    global stop_recording
    global is_recording
    global do_countdown_beep

    # Set rec flag
    is_recording=True
    
    # Set recording settings
    sample_format = pyaudio.paInt16  # 16 bits per sample
    channels = 1 # get_max_channels()
    frames = []  # Initialize array to store frames
    chunk = 1024  # Record in chunks of 1024 samplesSure, I'll do my best to rectify any inaccuracies and make necessary grammatical corrections. Please provide me with the text that needs refinement.
    fs = 44100  # Record at 44100 samples per second

    # Open the mic input stream
    p = pyaudio.PyAudio()  # Create an interface to PortAudio
    try:
        stream = p.open (
                format=sample_format,
                channels=channels,
                rate=fs,
                frames_per_buffer=chunk,
                input=True
            )
    except Exception as e:
        print(e + "\n\nIt's likey that no microphone is connected. ")
        return
    
    # Limit recording duration to prevent lockups
    max_duration = 100
    start_time = time.time()                    # get current time
    rec_time_limit = start_time + max_duration  # time limit for recording

    # for timeout sfx
    num_ticks = 3                            
    tick_count = num_ticks                      # for the last "tick_counter" seconds, beep every second
    ticks_ct = 0                                 # used as a flag to prevent the beep from playing again until the final tick_counter seconds     

    # no-talk detection
    # a) voice level
    voice_level_threshold = np.sqrt(np.mean(np.frombuffer(stream.read(chunk), dtype=np.int16)**2)) * 2
    # b) timer
    check_quiet_period = 1
    quiet_time_limit = 60
    quiet_grace_period = 5                            # num seconds to wait for voice input before resetting the the record timer
    last_voice_detected_time = start_time + check_quiet_period
    quiet_timer_expired = False


    # Start-stream notification!
    print("\nRecording...")
    playsound("on.wav")

    # Record audio stream!
    cur_time = time.time()
    voice_level = 0
    while stop_recording==False and cur_time < rec_time_limit:
        
        # round time to nearest second
        cur_time = time.time()

        # Read chunk and load it into numpy array
        data = stream.read(chunk)
        frames.append(data)

        # Check if:
        # 1) voice is detected and reset no-talk timer if so, else 
        # 2) check if no-talk timer has expired and stop recording if so
        if cur_time > last_voice_detected_time + check_quiet_period:
            np_data = np.frombuffer(data, dtype=np.int16)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                voice_level = np.sqrt(np.mean(np_data**2))
            # 1) If voice IS detected, then reset the no-talk timer
            # !Extend the recording time limit cause we talked - and the aim is justto mitigate long gaps in speech (not simply long files)
            if voice_level > voice_level_threshold:
                last_voice_detected_time = cur_time
                rec_time_limit = cur_time + max_duration  # extend the recording time limit
                tick_count = num_ticks                    # reset the tick counter
                quiet_timer_expired = False
            # 2) If voice IS NOT detected, then check if the no-talk timer has expired
            # !Clamp the recording time limit to the "no_talk_limit" to prevent long gaps in speech
            elif cur_time > last_voice_detected_time + quiet_time_limit and quiet_timer_expired == False:
                rec_time_limit = cur_time + quiet_grace_period + 0.1 # Allow the user to interject for a little while
                quiet_timer_expired = True

        # beep every second for the last "tick_counter" seconds (played via async_record_speech function)
        time_remaining = rec_time_limit - cur_time
        # if the beep_ct is 0 and we surpassed 75% of teh time limit, then play the beep
        if (time_remaining < max_duration * 0.75 and ticks_ct == 0):
            # print info
            print("Time warning: " + str(time_remaining))
            play_beep_async()
            ticks_ct += 1                # used as a flag to prevent the beep from playing again until the final tick_counter seconds
        elif (time_remaining < tick_count and tick_count > 0):
            # print info
            print("Time ticker: " + str(time_remaining))
            play_beep_async()
            ticks_ct += 1                # not really necessary, but just in case we want to do something with it later
            tick_count -= 1           # decrement the tick counter
            do_countdown_beep = True    # async_record_speech will play the beep!

    # Stop and close the stream
    stream.stop_stream()
    stream.close()

    # Terminate the PortAudio interface
    p.terminate()

    if time.time() < rec_time_limit - 0.1:
        warnings.filterwarnings("ignore") # this is to suppress the warning: "WavFileWarning: Chunk (non-data) not understood, skipping it."
        wf = wave.open("test"+str(file_ready_counter+1)+".wav", 'wb') # OPEN the wav file
        wf.setnchannels(channels) # set channels to "channels" means that it will be the same as the input
        wf.setsampwidth(p.get_sample_size(sample_format)) # set sample width to the same as the input
        wf.setframerate(fs) # set framerate to the same as the input
        wf.writeframes(b''.join(frames)) # write the frames to the file
        wf.close() # CLOSE the wav file
        file_ready_counter=file_ready_counter + 1 # increment the counter for the file name
        playsound("off.wav")
    else:
        playsound("error.wav")

    # Reset flags
    stop_recording=False
    is_recording=False

#endregion

#region MAIN
    
# RB startup things
initial_setup_check()
# timer_thread = threading.Thread(breaktimer.start_timer(query_gpt_chat("Hey Snoop, tell me in one sentence that it is time for me to take a break (I'm working).", "", playVoice=True)))
# timer_thread.start()

# transcribe speech in infinte loop
t2 = threading.Thread(target=transcribe_speech)
t2.start()

# Call the load_model_thread function in a separate thread
tload = threading.Thread(target=load_model_thread)
tload.start()

# hot key events
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
                    t1 = threading.Thread(target=async_record_speech)
                    t1.start()
                else:
                    if c["command"]=="start record" and is_recording==True:
                        stop_recording=True

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

#endregion