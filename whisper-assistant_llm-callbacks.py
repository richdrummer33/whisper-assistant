import torch
print("torch ver: " + torch.__version__)
import codecs
import whisper
import time
import threading
import pyaudio
import wave
import winreg
import os
import sys
import string
from pynput import keyboard
from datetime import datetime
from PyQt5.QtMultimedia import QAudioDeviceInfo
import warnings


# >>> NOTE NOTE NOTE >>>
# CONDA CMD FOR INSANELY-FAST-WHISPER:
# **************************************
#   set HF_DATASETS_OFFLINE=1 && set TRANSFORMERS_OFFLINE=1 && huggingface-cli login --token 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 && python whisper-assistant_llm-callbacks.py
# **************************************
# <<< NOTE NOTE NOTE <<< 

# USING SOCKET TO ANOTHER CONDA LLM SESSION INSTEAD OF RUNNING IT IN THIS SCRIPT, DUE TO PERFORMANCE ISSUES
# 
#   Imports the folder (which lives in this directory) that contains 
#   the python scripts for open source llms. going to use mistral.py
# 
# sys.path.insert(1, 'open_source_llm')
# from open_source_llm.mistral_class import MistralChatbot

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

#################

# import json
# from transformers import AutoModel, AutoConfig
# 
# # Path to your JSON configuration file
# config_file_path = './small.en.config.json'
# 
# # Read and parse the JSON file
# with open(config_file_path, 'r') as file:
#     config_params = json.load(file)
# 
# AutoConfig.register("small.en", config_params)
# AutoModel.register(config_params, model)

#################

model_name = "small.en"
model = None
pipe = None
audio_data = None

# NOTE REF: https://github.com/Vaibhavs10/insanely-fast-whisper
# insanely fast whisper
try:
    from transformers import pipeline
    print(f"Loading {model_name} for insanely-fast-whisper with pipeline...")
    pipe = pipeline(
        "automatic-speech-recognition",
        model="D:\\Data\\LLM-models\\whisper\\whisper-large-v3", # "openai/whisper-medium.en",
        torch_dtype=torch.float16,
        device="cuda", # or mps for Mac devices
        model_kwargs={"use_flash_attention_2": True}, # set to False for old GPUs
    )
except Exception as e:
    print(e)
    print(f"\nPipeline error. Loading {model_name} with whisper api instead...")
    model = whisper.load_model(model_name).to(device)
    print(f"{model_name} model loaded!")

print(f"Insanely-fast-whisper done {model_name}!")

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

# local llm variables
# mistral = MistralChatbot()
_default_llm_system_message = "Simply clean up and correct the grammar, punctuation, seemingly misinterpreted words, in the provided transcribed text, to the best of your ability"

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
##################################### local llm querying  #################################################
###########################################################################################################

_transcribed_text = ""
_transcribed_text_to_send = None

# USING SOCKET TO ANOTHER CONDA LLM SESSION INSTEAD
# def on_transcription_complete():
#     # create a thread to run the local llm query loop
#     t3_llm = threading.Thread(target=query_local_llm)
#     t3_llm.start()
# 
# def query_local_llm():
#     global _transcribed_text
#     print("Local llm query thread started...")
# 
#     mistral.generate_output_instruct(_default_llm_system_message, _transcribed_text)
#     print("Local llm query thread stopped.")


###########################################################################################################
################################ main speech recognition and transcription ################################
###########################################################################################################

def transcribe_speech(): # callbacks can eb methods outside this function, which is threaded
    global file_ready_counter
    global device
    global transcription_complete
    global _transcribed_text
    global _transcribed_text_to_send
    global audio_data

    i=1
    correct_dialogue = ""
    print("ready - start transcribing by pressing Alt-M ...\n")
    
    while True:
        # wait for file to be ready
        while file_ready_counter < i:
            time.sleep(0.01)

        # transcribe speech
        # with torch.cuda.device(device):
        if model is not None:
            result = model.transcribe(torch.from_numpy(audio_data), language = "en", fp16=False)# "test"+str(i)+".wav") # before "insanely fast whisper"

        # insanely fast whisper
        elif pipe is not None:
            raw_transcript = pipe("test"+str(i)+".wav", 
                chunk_length_s=30,
                batch_size=24,
                return_timestamps=True)

        print('\033[96m' + "\n?RAW TRANSCRIPTION?:\n" + raw_transcript + '\033[0m', file=sys.stderr)
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
        similarity = 0
        
        # remove all punctuation from the corrected_dialogue for checking if any of the 1st 3 words is the pseudonym (sometimes there is a comma or period before/after the pseudonym)
        translator = str.maketrans('', '', string.punctuation) # Create a translation table that maps every punctuation character to None
        raw_transcript = corrected_dialogue.translate(translator)
        firstWords = raw_transcript.lower().strip().split(" ")[:3]
        isAQuery                = any(word.lower() == _pseudonym.lower() for word in firstWords) or similarity > 80
        isAnImprovementRequest  = any(word.lower() == _improveKwd.lower() for word in firstWords)
        if(_debug): 
            print ("(info) Is a query: " + str(isAQuery) + "\n(info) Has key: " + str(_hasKey))
            
        ##################################################################
        ####### REGULAR SPEECH-TO-TEXT TRANSCRIPTION (AUTO-TYPING) #######
        ##################################################################
        if True: 
            #if(_debug):
            print ("(info) Transcribing speech. No GPT query.")
            
            # remove leading + trailing spaces and leading punctuation 
            corrected_dialogue = corrected_dialogue.strip() 
            corrected_dialogue = corrected_dialogue.lstrip(".,:;!?")    

            # GPT query to correct the text
            # corrected_dialogue = query_gpt_autocorrect(corrected_dialogue, True)
            # print('\033[95m' + "\n" + _pseudonym + " says:\n" + corrected_dialogue + '\033[0m', file=sys.stderr)

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
            
            # Text streams onto the terminal window
            # corrected_dialogue = mistral.generate_output(prompt=corrected_dialogue) 
        
        os.remove("test"+str(i)+".wav")
        i=i+1
        
        print("transcript complete")
        _transcribed_text = corrected_dialogue
        _transcribed_text_to_send = corrected_dialogue
        

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

########################################################################
######################## record audio ##################################
########################################################################

def get_max_channels():
    audio_info = QAudioDeviceInfo.defaultInputDevice()  # or QAudioDeviceInfo.defaultOutputDevice()
    max_channels = audio_info.supportedChannelCounts()[-1]
    # print it
    print("Max channels:", max_channels)
    return max_channels

# New for newer version torch Dec 2023
import numpy as np

#record audio
def record_speech():
    global file_ready_counter
    global stop_recording
    global is_recording
    global audio_data

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
    # playsound("on.wav")

    while stop_recording==False:
        data = stream.read(chunk) # , always_2d=True) # RB Added always_2d=True. Needed for CUDA? See ref: https://stackoverflow.com/questions/75775272/cuda-and-openai-whisper-enforcing-gpu-instead-of-cpu-not-working
        frames.append(data)
    
    # NOTE (Dec 2023): 
    #   For newer version torch: 2.2.0.dev20231201+cu118 
    #   Attempts to address RuntimeError: expected scalar type Float but found Half ) 
    # Convert frames to a single bytes object
    audio_bytes = b''.join(frames)
    # Convert bytes data to numpy array of type int16 (as per pyaudio.paInt16)
    audio_data = np.frombuffer(audio_bytes, dtype=np.int16)
    # Normalize and convert to float32
    audio_data = audio_data.astype(np.float32) / np.iinfo(np.int16).max

    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    # Terminate the PortAudio interface
    p.terminate()
    #playsound("off.wav")
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


# Sends messages from the transcription to any listening sockets
import socket
def socket_server():
    global _transcribed_text_to_send

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('localhost', 12345))  # Bind to localhost on port 12345
    server.listen()
    print("Server listening...")
    conn, addr = server.accept()

    with conn:
        print('Connected by', addr)
        while True:
            # Wait for _transcribed_text_to_send to have data
            while _transcribed_text_to_send is None:
                time.sleep(0.1)

            # Send the data
            conn.sendall(_transcribed_text_to_send.encode())
            _transcribed_text_to_send = None

            # Receive acknowledgment, if applicable
            # ack = conn.recv(1024)
            # if ack:
            #    print("Acknowledgment received:", ack.decode())

#------------

# timer_thread = threading.Thread(breaktimer.start_timer(query_gpt_chat("Hey Snoop, tell me in one sentence that it is time for me to take a break (I'm working).", "", playVoice=True)))
# timer_thread.start()

# clear console
os.system('cls' if os.name=='nt' else 'clear')

# transcribe speech in infinte loop
t2 = threading.Thread(target=transcribe_speech)
t2.start()

# sends messages from all new transcriptions to any listening sockets
t3 = threading.Thread(target=socket_server)
t3.start()


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