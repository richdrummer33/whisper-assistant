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
# import OcrWindowsAutomation as winauto
import pandas as pd
from pynput import keyboard
from playsound import playsound
from datetime import datetime
from PyQt5.QtMultimedia import QAudioDeviceInfo
from elevenlabslib import *
from elevenlabslib import helpers
import warnings


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

# GPU CUDA for whisper
# device = "cuda" if torch.cuda.is_available() else "cpu"
device = "cuda"
if device == "cuda":
    torch.cuda.init()
print(f"Using device: {device}")

# model loading 
print("loading model...")
model_name = "medium.en"
model = whisper.load_model(model_name).to(device)
playsound("model_loaded.wav")
print(f"{model_name} model loaded")

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


###########################################################################################################
################################ initial setup and environment variables ###################################
###########################################################################################################
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
            print("\nOpenAI GPT API key and organization ID found.", file=sys.stderr)
    except:
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
    

###########################################################################################################
################################ speech synthesis by eleven labs ##########################################
###########################################################################################################
def play_voice(text=""):
    user = ElevenLabsUser(os.getenv("ELEVEN_LABS_API_KEY"))
    voice = user.get_voices_by_name(_elevenLabsVoice)[0]  # This is a list because multiple voices can have the same name
    
    # if there are angle brackets, then trim the text to the text within the brackets
    if("<" in text and ">" in text):
        text = text[text.find("<")+1:text.find(">")]
    # else just trim the text to the first sentence
    #else:
     #   text = text.split(".")[0]
    
    # STREAMING VERSION: voice.generate_stream_audio_v2(text, playbackOptions=PlaybackOptions(runInBackground=True))
    audioData, historyID, outputStream = voice.generate_play_audio_v2(text, playbackOptions=PlaybackOptions(runInBackground=True))
    
    # get reg value and save the audio to a file with the incremented number
    file_number = get_registry_value("AudioFileIndex")
    helpers.save_audio_bytes(audioData, "eleven-labs-responses/" + str(file_number) + "_theirs.wav", "wav")
    
    # save an "after" screenshot for record keeping
    screenshot = get_chat_window_screenshot_pysseract()
    cv2.imwrite("eleven-labs-responses/" + str(file_number) + "_response.png", screenshot)

    for historyItem in user.get_history_items_paginated():
        if historyItem.text == text:
            # The first items are the newest, so we can stop as soon as we find one.
            historyItem.delete()
            break
        
###########################################################################################################
################################ main speech recognition and transcription ################################
###########################################################################################################
def transcribe_speech():
    global file_ready_counter
    global device
    i=1
    print("ready - start transcribing by pressing Alt-M ...\n")
    
    while True:
        # wait for file to be ready
        while file_ready_counter < i:
            time.sleep(0.01)
        
        # define openai api key and organization
        openai.organization = os.getenv("OPENAI_ORG")
        openai.api_key = os.getenv("OPENAI_API_KEY")
        
        # transcribe speech
        # with torch.cuda.device(device):
        result = model.transcribe("test"+str(i)+".wav")
        raw_transcript = result["text"].strip()
        print('\033[96m' + "\nRAW TRANSCRIPTION:\n" + raw_transcript + '\033[0m', file=sys.stderr)
        
        # if "computer" or "computer." is the last string, remove it (voice attack)
        raw_transcript.strip("computer")
        raw_transcript.strip("computer.")
        
        # autocorrect feature
        corrected_dialogue = raw_transcript
        
        # try:
        #     corrected_dialogue = query_gpt_autocorrect(raw_transcript)
        #     print('\033[38;5;208m' + "\nCORRECTED TRANSCRIPTION:\n " + corrected_dialogue + '\033[0m', file=sys.stderr)
        #     _hasKey = True
        # except:
        #     pass
        
        corrected_dialogue = corrected_dialogue.strip() # remove leading and trailing spaces
        corrected_dialogue = corrected_dialogue.lstrip(".,:;!?") # removing any leading punctuation and spaces
        
        # saves a record of the transcription to a log file to folder in appdata
        save_to_logfile(corrected_dialogue)
        
        # if the 1st word spoken is close to the pseudonym, then run a GPT query and overwrite the result
        similarity = check_text_similarity((corrected_dialogue.split(" ")[0]).lower, _pseudonym)
        
        # remove all punctuation from the corrected_dialogue for checking if any of the 1st 3 words is the pseudonym (sometimes there is a comma or period before/after the pseudonym)
        translator = str.maketrans('', '', string.punctuation) # Create a translation table that maps every punctuation character to None
        raw_transcript = corrected_dialogue.translate(translator)
        firstWords = raw_transcript.lower().strip().split(" ")[:3]
        isAQuery                = any(word.lower() == _pseudonym.lower() for word in firstWords) or similarity > 80
        isAnImprovementRequest  = any(word.lower() == _improveKwd.lower() for word in firstWords)
        if(_debug): 
            print ("(info) Is a query: " + str(isAQuery) + "\n(info) Has key: " + str(_hasKey))
            
        #################################################################
        ### WE ARE ASKING THE ASSISTANT FOR INSIGHT - RUN A GPT QUERY ###
        #################################################################
        if _hasKey and isAnImprovementRequest:
            # copy to clipboard
            clipboard_text = get_text_from_clipboard()
            
            # if raw text contains the analyze_text_keyword, then run
            print ("(info) We are asking the assistant to improve text")

            # process the text - runs a GPT rewrite of the copied text
            improvedText = query_gpt_autocorrect(clipboard_text, True)  # RB: Query GPT and overwrite the result with GPT's response
            print('\033[95m' + improvedText + '\033[0m', file=sys.stderr)

            # copy the response to the clipboard between the
            pyperclip.copy(improvedText)
            
        elif _hasKey and isAQuery:
            # save a "before" screenshot for record keeping 
            screenshot = get_chat_window_screenshot_pysseract()
            file_number = increment_registry_value("AudioFileIndex")
            cv2.imwrite("eleven-labs-responses/" + str(file_number) + "_query.png", screenshot)
            
            if(_debug): 
                print ("(info) We are talking to the assistant")
                
            # clear the clipboard
            pyperclip.copy("")
            clipboard_text = ""
            ocr_text = ""   
            
            # if raw text contains the analyze_text_keyword, then run 
            # if the raw_transcript has the analyze_text_keyword, then run 
            # do window OCR for wider context
            # ocr_text = get_window_text_ocr_pysseract()
            
            # process the text - runs a GPT autocorrect
            clipboard_text = "\n" + get_text_from_clipboard()
            
            feedback = ""
            if(clipboard_text != ""):
                feedback = "Asking " + _pseudonym + " about: " + clipboard_text
                
            print(feedback, file=sys.stderr)
            corrected_dialogue = query_gpt_chat(corrected_dialogue + clipboard_text, ocr_text)  # RB: Query GPT and overwrite the result with GPT's response
            print('\033[95m' + "\n" + _pseudonym + " says:\n" + corrected_dialogue + '\033[0m', file=sys.stderr)
            
            # copy the response to the clipboard between the 
            pyperclip.copy(corrected_dialogue)
        
            # get the index from the registry
            file_number = get_registry_value("AudioFileIndex")
            # save the audio to a file
            shutil.copyfile("test"+str(i)+".wav", "eleven-labs-responses/" + str(file_number) + "_ours.wav")

            # speech synthesis eleven labs
            play_voice(corrected_dialogue)
            
        ##################################################################
        ####### REGULAR SPEECH-TO-TEXT TRANSCRIPTION (AUTO-TYPING) #######
        ##################################################################
        else: 
            if(_debug):
                print ("(info) Transcribing speech. No GPT query.")
            
            # remove leading + trailing spaces and leading punctuation 
            corrected_dialogue = corrected_dialogue.strip() 
            corrected_dialogue = corrected_dialogue.lstrip(".,:;!?")    

            # GPT query to correct the text
            # corrected_dialogue = query_gpt_autocorrect(corrected_dialogue, True)
            print('\033[95m' + "\n" + _pseudonym + " says:\n" + corrected_dialogue + '\033[0m', file=sys.stderr)

            # if starts with 'git' then remove trailing period if it exists
            if(corrected_dialogue.lower().startswith("git")):   
                print ("[git command]")
                corrected_dialogue = corrected_dialogue.rstrip(".")
            # if is not a full sentence, then remove any trailing periods
            if(len(corrected_dialogue) < 25):
                corrected_dialogue = corrected_dialogue.rstrip(".")
            
            for char in corrected_dialogue:
                try:
                    pykeyboard.type(char)
                    time.sleep(0.01)
                except Exception as e:
                    print("empty or unknown symbol" + e)    
                    
        os.remove("test"+str(i)+".wav")
        i=i+1

def save_to_logfile(dialogue="", audio_file_path=""):
    now = str(datetime.now()).split(".")[0]
    with codecs.open('transcribe.log', 'a', encoding='utf-8') as f:
        # create folder in %appdata% if does not exist
        appdata_path = os.getenv('APPDATA') + "\\whisper-assistant\\"
        if not os.path.exists(appdata_path):
            os.makedirs(appdata_path)
        # write to appdata folder
        with codecs.open(appdata_path + 'transcribe.log', 'a', encoding='utf-8') as f:            
            f.write(now + " : " + dialogue + "\n")
            if(_debug): 
                print ("(info) saved to log file: " + now + " : " + dialogue + "\n")
        
import numpy as np
import pygetwindow as gw
import pyautogui
import cv2
# install cv2 by running: pip install opencv-python
import pytesseract

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

############################################################################################################
##################################### OCR Text from Active Window ##########################################
############################################################################################################
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

###########################################################################################################
##################################### Auto Mouse Movement #################################################
###########################################################################################################
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
    
    if playVoice:
        play_voice(response.choices[0].message.content)
    
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
            # ...concise version of this:
            #"Your ONLY role is to provide corrections to transcriptions generated by an Automatic Speech Recognition (ASR) AI. DO NOT generate responses or provide answers to any content in the transcriptions. Your task is limited to identifying and correcting mistakes in the transcriptions. \nYour job description:"
            #+ "\n\t1. Rectify inaccuracies where the ASR AI seems to ahve misinterpreted spoken words with similar sounding words."
            #+ "\n\t2. Make necessary grammatical corrections, especially in cases of run-on sentences and punctuation. It's important to maintain my speech style, so use a minimalistic approach."
            #+ "\n\t2. Make necessary formatting corrections. E.g. You can use paragraph formatting, indented point notes - whatever you think it would enhance the content."
            #+ "\n\t3. If the text is correct and does not need any modifications, just return the text as is."
            #+ "\nExample: If the text reads 'yo, how are you doing?' do not modify it to 'hello, how are you doing'; keep the word 'yo'. "
            #+ "An inverse example: If the text reads 'Below, how are you doing' then 'Hello, how are you doing?' was probably what I said and can be corrected as such. "
            #+ "\n\nNotes: "
            #+ "\n\t1: I often discuss programming, particularly in C-Sharp or Python, and frequently ask questions related to the Unity engine, since I'm a developer. "
            #+ "In such cases, I'll often use technical jargon like: '...interface called I in it statics...' which I'd intend to be: '...interface called IInitStatics...'. "
            #+ "I'll also use video game words such as (for example) 'reticle', which is often misinterpreted as 'radical'."
            #+ "I'll also say things that start with the word 'git', which can be translated to a git command. E.g. When I say 'Git add all', that means 'git add -A' (note: git must have a lowercase g). "
            #+ "Don't convert these into non-technical language. Instead, try to predict what they should be in the given context when the context appears programming related. "
            #+ "If I say the person's names Bela (often misenterpreted as Bella), Dylan, Ollie, Kenny, Graham, then put an @ symbol in front like: @Bela."
            #+ "\n\t 2: I may say the word '" + _pseudonym + "' in the sentence (this is someone's name). This word (name) is intentional and should not be changed. "
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
            { keyboard.Key.alt_l, keyboard.KeyCode(char="m")}
        ],
        "command": "start record",
    },
]

########################################################################
######################## record audio ##################################
########################################################################

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
        data = stream.read(chunk) # , always_2d=True) # RB Added always_2d=True. Needed for CUDA? See ref: https://stackoverflow.com/questions/75775272/cuda-and-openai-whisper-enforcing-gpu-instead-of-cpu-not-working
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

# RB startup things
initial_setup_check()
# timer_thread = threading.Thread(breaktimer.start_timer(query_gpt_chat("Hey Snoop, tell me in one sentence that it is time for me to take a break (I'm working).", "", playVoice=True)))
# timer_thread.start()

# transcribe speech in infinte loop
t2 = threading.Thread(target=transcribe_speech)
t2.start()

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
                    t1 = threading.Thread(target=record_speech)
                    t1.start()
                else:
                    if c["command"]=="start record" and is_recording==True:
                        stop_recording=True

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
