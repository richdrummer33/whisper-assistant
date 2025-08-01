# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Simple CPU implementation of a speech-to-text tool using the whisper model
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# 🗃️ Misc Imports
import win32clipboard
from io import BytesIO
import win32con
import time
import subprocess
import threading
import pyaudio
import wave
import pygame
# from playsound import playsound
import keyboard as kb
import psutil
import os
import os.path as osp
import threading

# ⏰ Reminder imports
import json
import tkinter as tk
from tkinter import simpledialog
from datetime import datetime, timedelta
import json
import re
import winreg
import pyperclip

# ⌛ Real-time record/transcribe
import numpy as np
import librosa
import soundfile as sf
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_nonsilent
import traceback

# 📎 Clipboard
from PIL import Image
from clipboardhist import ClipboardHist
clipboard_hist = ClipboardHist(max_size=30)
paste_cooldown = 0.5  # Cooldown period for pasting the last clipboard entry

# ✏️ Custom py classes
from overlay import Overlay

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~ Global Variables ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# NEW 
realtime_transcripts = []  # Store transcribed chunks during real-time mode
realtime_transcript_lock = threading.Lock()  # Protect the transcript list

# User Prefs 🎛️
# If true, types out the transcript one character at a time instead of pasting
USE_REALTIME_TYPING = False     
# If True (default): Use the Keyboard class for intercepting keystrokes. 
# If False (optional): Use keyboard.Listener (async loop) for intercepting keystrokes.
# (one or the other might be more reliable, depending on your system)
USE_KBLIB_LISTENER = True      
VERBOSE_LOGGING = False  # If True, prints debug info to console

# Model Prefs 🎛️
USE_FASTER_WHISPER = True # NOT FUNCTIONAL YET
faster_whisper = None # NOT FUNCTIONAL YET
# ℹ CHANGE THIS TO 'tiny.en' FOR FASTER PERFORMANCE — not as good as small.en, but still plenty good
model_name = "small.en" 
model_inst = None 

# For real-time recording with silence detection
chunks_folder = "speech_chunks"
current_chunk_index = 0
Chunk_Queue = []
realtime_recording = False

# Thread Synchronization
app_lock = threading.RLock()  # Single reentrant lock for all state

openai_client = None
tkinter_loop = False
file_ready_counter = 0

oldest_elem_clipboard = pyperclip.paste()
os.environ["PATH"] += os.pathsep + os.path.abspath(".")  # For ffmpeg exe
file_ct = 1
transcript = ""
_special_char = "⌘"

# Reminder Fields ⏰ 
reminder_file = "reminders.json"
history_file = "history.json"
image_folder = "images/"
history_folder = "history/"
global_use_system_reminder = True

# Operation States 🎙️
Recording = False
Transcribing = False
Reminding = False
ChunkedRecording = False

# Thread Control 🧵 
transcribe_thread = None
recording_thread = None
overlay_thread = None

# Event for canceling operations
cancel_event = threading.Event()
cancel_event.clear()

# Directories 📁
os.makedirs(image_folder, exist_ok=True)
os.makedirs(history_folder, exist_ok=True)

# Logging 🐛
import logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Set __file__ to the current file path
path = os.path.abspath(__file__)
PATH = path.replace(osp.basename(path), "")

REMINDER_SETUP_INSTRUCTIONS = f"""To set up reminders:
    - Create openai account at https://platform.openai.com/signup
    - And funds: https://platform.openai.com/settings/organization/billing/overview ($5 will last years)
    - Generate a secret use-key: https://platform.openai.com/api-keys (secret key that allows GPT requests)
    - Set the key on your PC: Open command prompt, then type 'setx OPENAI_API_KEY sk-...' (replace sk-... with your key)"""

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~   Helper Methods   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def log_states_periodically():
    while True:
        time.sleep(5)  # Log every 5 seconds
        with app_lock:
            logging.info(f"Recording: {Recording} | Transcribing: {Transcribing} | Reminding: {Reminding} | File Counter: {file_ready_counter}")


def play_sound(sound_file_path):
    return
    if not os.path.exists(sound_file_path):
        logging.error(f"Sound file not found: {sound_file_path}")
        return
    try:
        pygame.mixer.music.load(sound_file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
    except Exception as e:
        logging.error(f"Error playing sound {sound_file_path}: {e}")


# plays sound (in this folder) "Record Start.wav" or "Record Stop.wav"
def play_recording_sound(start=True):
    sound_file = "Record Start.wav" if start else "Record Stop.wav"
    sound_path = osp.join(PATH, sound_file)
    if not osp.exists(sound_path):
        logging.error(f"Recording sound file not found: {sound_path}")
        return
    logging.info(f"Playing recording sound: {sound_file}")
    play_sound(sound_path)


# Plays startup sound "Whisper Start.wav"
def play_startup_sound():
    sound_file = "Whisper Start.wav"
    sound_path = osp.join(PATH, sound_file)
    if not osp.exists(sound_path):
        logging.error(f"Startup sound file not found: {sound_path}")
        return
    logging.info(f"Playing startup sound: {sound_file}")
    play_sound(sound_path)
    

def show_overlay():
    try:
        overlay.show()
    except Exception as e:
        print(f"Error showing overlay: {e}")


def hide_overlay():
    try:
        overlay.hide()
    except Exception as e:
        print(f"Error hiding overlay: {e}")


def clipboard_copy_paste(text, position="below_top", paste_immediately=True):
    """
    Copy text to clipboard at the specified position and optionally paste it immediately.
    
    Parameters:
    - text: Text to copy
    - position: Where to place text ("top", "below_top", "append")
    - paste_immediately: Whether to immediately paste the text at cursor
    """
    try:
        # Store original clipboard content for organization
        original_clipboard = pyperclip.paste()
        
        # For immediate pasting, use the raw text
        if paste_immediately:
            # Set clipboard to just the text for pasting
            pyperclip.copy(text)
            time.sleep(0.1)  # Short delay
            kb.press_and_release('ctrl+v')  # Paste it
            time.sleep(0.1)  # Give time for paste to complete
        
        # Now organize clipboard based on position
        if position == "top":
            # Replace clipboard with just the text (already done if paste_immediately)
            if not paste_immediately:
                pyperclip.copy(text)
            
        elif position == "below_top":
            # If original clipboard was empty, just use the text
            if not original_clipboard.strip():
                if not paste_immediately:  # Skip if already done for pasting
                    pyperclip.copy(text)
            else:
                # Find the first line break or create one if none exists
                if '\n' in original_clipboard:
                    first_line_end = original_clipboard.find('\n')
                    first_line = original_clipboard[:first_line_end]
                    rest_of_content = original_clipboard[first_line_end:]
                    
                    # Insert new text after first line
                    new_content = first_line + '\n' + text + rest_of_content
                else:
                    # No line breaks, so add one
                    new_content = original_clipboard + '\n' + text
                    
                # Update clipboard with organized content
                pyperclip.copy(new_content)
            
        elif position == "append":
            # If original clipboard was empty, just use the text
            if not original_clipboard:
                if not paste_immediately:  # Skip if already done for pasting
                    pyperclip.copy(text)
            else:
                # Append to original clipboard
                new_content = original_clipboard + '\n' + text
                pyperclip.copy(new_content)
    
    except Exception as e:
        print(f"Error copying to clipboard: {e}")
        # Fallback to regular copy and paste
        pyperclip.copy(text)
        if paste_immediately:
            try:
                time.sleep(0.1)
                kb.press_and_release('ctrl+v')
            except Exception as paste_e:
                print(f"Error pasting clipboard content: {paste_e}")

    
# Thread-safe state updater
def update_state(recording=None, transcribing=None, reminding=None, realtime_recording=None):
    logging.debug(f"Attempting to acquire state lock from {threading.current_thread().name}")
    
    with app_lock:
        logging.debug(f"Acquired state lock from {threading.current_thread().name}")
        global Recording, Transcribing, Reminding, ChunkedRecording   
        
        if recording is not None:
            old_val = Recording
            Recording = recording
            logging.debug(f"Changed Recording flag from {old_val} to {recording}")

        if transcribing is not None:
            old_val = Transcribing
            Transcribing = transcribing
            logging.debug(f"Changed Transcribing flag from{old_val} to {transcribing}")
    
        if reminding is not None:
            old_val = Reminding
            Reminding = reminding
            logging.debug(f"Changed Reminding flag from {old_val} to {reminding}")

        if realtime_recording is not None:
            old_val = ChunkedRecording
            ChunkedRecording = realtime_recording
            logging.debug(f"Changed Realtime_Recording flag from {old_val} to {realtime_recording}")

        logging.debug(f"State lock released from {threading.current_thread().name}")

        # Notify other threads waiting on this lock
        # app_lock.notify_all() # ??? 
        # logging.debug(f"State lock notified from {threading.current_thread().name}")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~    Core Methods   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Runs loop indefinitely to Whisper-transcribe any new recordings
from pynput import keyboard

# [Fix] 'No new completed recording detected - waiting...' lockup bug
#   -> https://claude.ai/chat/6f53b4e0-ae41-4bfb-a6fb-4a11761e896b
def transcribe_speech():
    import asyncio
    global model_inst, file_ready_counter, file_ct, Reminding, Transcribing, Recording, faster_whisper, transcript
    global realtime_transcripts, ChunkedRecording

    # Bootup: Await model init....
    while True:
        time.sleep(0.1)
        if model_inst is not None or faster_whisper is not None:
            break

    time.sleep(0.5)
    
    ######################
    # /// ASCII LOGO /// #
    ######################
    # Authentic Apple II phosphor green
    apple_green = "\033[38;2;51;255;51m"  # RGB green phosphor color
    console_blue = "\033[38;2;0;170;255m"  # Bright cyan-blue
    reset_color = "\033[0m"
    
    # print(f"Transcription thread initialized and ready")
    os.system('cls' if os.name == 'nt' else 'clear') # clear console
    
    def create_ascii_logo(text):
        return
        from pyfiglet import Figlet
        figlet = Figlet(font="slant")
        ascii_logo = figlet.renderText(text)
        return f"{apple_green}{ascii_logo}{reset_color}"
    
    # Replace 'Your Text Here' with the text you want to convert to ASCII art
    logo_text = "Whisper Transcriber"
    print(create_ascii_logo(logo_text))

    print(f"""{console_blue}Whisper assistant auto-typer/transcriber ready!
          
        Press Alt-Q to speak (listens)
        Press Alt-Q again to transcribe (pastes/types)

        Press Alt-R to speak and set a reminder (listens) 
        Press Alt-R again to set the reminder (LLM automated)
        (Reminders can be one-off, or periodic — daily, weekly, annually)
        (Reminders set in Windows Task Scheduler — works without app running)
          
        Toggle between pasting/realtime-typing with Alt-T 
          
        {reset_color}""")
     
    # Initialize processed counter to current value to catch any files saved during model loading
    with app_lock:
        last_processed_counter = file_ready_counter - 1  # Start one behind to catch existing files
    
    # Check for any recordings that may have been saved while model was loading
    if os.path.exists("transcript.wav") and os.path.getsize("transcript.wav") >= 1000:
        print("Found existing recording from before model loaded - will process it")
        # Force the loop to process this file by setting counter behind current value
        last_processed_counter = file_ready_counter - 1

    while True:
        try:
            # Exit if requested - for complete cancellation (Alt+W)
            if cancel_event.is_set():
                # print(f"Cancel event detected in transcribe thread - skipping this iteration")
                time.sleep(0.1)  # Brief pause
                continue  # Skip this iteration but keep thread alive

            # Initialize local variables
            with app_lock:
                current_transcribing = Transcribing
                current_transcribing_chunks = ChunkedRecording
                current_reminding = Reminding

# ===== REALTIME CHUNKED TRANSCRIPTION =====
            # Handle real-time chunk processing
            if current_transcribing_chunks and Chunk_Queue:
                while Chunk_Queue:
                    chunk_path = Chunk_Queue.pop(0)
                    
                    if os.path.exists(chunk_path) and os.path.getsize(chunk_path) >= 1000:
                        # if VERBOSE_LOGGING: 
                        print(f"🔄 Transcribing chunk: {chunk_path}")
                        
                        try:
                            # Transcribe the chunk
                            if faster_whisper is not None:
                                result = faster_whisper(chunk_path, batch_size=16)
                                if isinstance(result, dict) and 'text' in result:
                                    chunk_transcript = result['text'].strip()
                                elif isinstance(result, list) and len(result) > 0 and 'text' in result[0]:
                                    chunk_transcript = result[0]['text'].strip()
                                else:
                                    chunk_transcript = str(result).strip()
                            else:
                                result = model_inst.transcribe(chunk_path)
                                chunk_transcript = result["text"].strip()
                            
                            if chunk_transcript:
                                # Add to real-time transcripts with thread safety
                                with realtime_transcript_lock:
                                    realtime_transcripts.append(chunk_transcript)
                                
                                print(f"📝 Chunk: {chunk_transcript}")
                                
                                # Update clipboard with current combined transcript
                                with realtime_transcript_lock:
                                    combined_transcript = " ".join(realtime_transcripts)
                                
                                # Copy to clipboard in real-time
                                clipboard_copy_paste(combined_transcript, position="below_top", paste_immediately=False)
                        
                        except Exception as e:
                            print(f"❌ Error transcribing chunk {chunk_path}: {e}")
                    
                    # Clean up processed chunk file
                    try:
                        os.remove(chunk_path)
                    except:
                        pass
                
                # Short pause for real-time processing
                time.sleep(0.1)
                continue

            # Handle end of real-time mode - paste final transcript
            if not current_transcribing_chunks and len(realtime_transcripts) > 0:
                with realtime_transcript_lock:
                    if realtime_transcripts:  # Double-check it's not empty
                        final_transcript = " ".join(realtime_transcripts)
                        print(f"\n🎯 Final real-time transcript:")
                        print(f"\033[33m{final_transcript}\033[0m")
                        
                        # Check typing preference and paste/type the final result
                        with app_lock:
                            should_type = USE_REALTIME_TYPING
                        
                        if should_type:
                            keyboard_controller = keyboard.Controller()
                            type_with_newlines(final_transcript, keyboard_controller)
                        else:
                            clipboard_copy_paste(final_transcript, paste_immediately=True)
                        
                        # Clear the transcripts array
                        realtime_transcripts.clear()
                        print("Real-time transcription complete!")
# ===== END REALTIME CHUNKED TRANSCRIPTION =====

            # Check if there's a new file to process (including files saved during model loading)
            new_file_ready = False
            wait_start = time.time()
            
            while time.time() - wait_start < 5:  # 5 sec timeout (shorter than before)
                with app_lock:
                    # A new file is ready when:
                    # 1. The file counter has increased from our last processed count
                    # 2. We're not currently recording (to avoid processing partial recordings)
                    # 3. OR there's an existing file from before model loading
                    if file_ready_counter > last_processed_counter and not Recording: 
                        new_file_ready = True 
                        break
                
                time.sleep(0.1)
            
            if not new_file_ready:
                # print("No new completed recording detected - waiting...")
                continue
            if VERBOSE_LOGGING: print("🎙️ New completed recording detected! Transcribing...")

            # Validate audio file
            if not os.path.exists("transcript.wav"):
                if VERBOSE_LOGGING: print("❌ transcript.wav does not exist")
                with app_lock:
                    last_processed_counter = file_ready_counter
                continue
                
            file_size = os.path.getsize("transcript.wav")
            if file_size < 1000:
                print(f"❌ Audio file too small: {file_size} bytes")
                with app_lock:
                    last_processed_counter = file_ready_counter
                continue
                
            if VERBOSE_LOGGING: print(f"📁 Processing audio file: {file_size} bytes")
            
            # 🤖👂🏼 Transcribe with Whisper!
            try:
                if faster_whisper is not None:
                    if VERBOSE_LOGGING: print("🔄 Starting Distil-Whisper transcription...")
                    
                    # Call the pipeline - it returns a dict with 'text' key
                    result = faster_whisper("transcript.wav", batch_size=16) # chunk_length_s=25
                    
                    if VERBOSE_LOGGING:print(f"📝 Raw result type: {type(result)}")
                    if VERBOSE_LOGGING:print(f"📝 Raw result: {result}")
                    
                    # Extract text from pipeline result
                    if isinstance(result, dict) and 'text' in result:
                        transcript = result['text'].strip()
                    elif isinstance(result, list) and len(result) > 0 and 'text' in result[0]:
                        # Sometimes pipeline returns a list
                        transcript = result[0]['text'].strip()
                    else:
                        print(f"❌ Unexpected result format: {result}")
                        transcript = str(result).strip()  # Fallback
                        
                else: 
                    print("🔄 Starting standard Whisper transcription...")
                    result = model_inst.transcribe("transcript.wav")
                    transcript = result["text"].strip()
                
                # Check if we got any text
                if transcript and len(transcript) > 0:
                    if VERBOSE_LOGGING: print(f"✅ Transcription successful: '{transcript}'")
                else:
                    if VERBOSE_LOGGING: print("⚠️ Transcription returned empty text")
                    transcript = ""

            except Exception as e:
                print(f"❌ Error transcribing audio: {e}")
                import traceback
                traceback.print_exc()
                
                # Update counter to avoid getting stuck on bad file
                with app_lock:
                    last_processed_counter = file_ready_counter
                continue

            # Thread-safe state check
            with app_lock:
                current_transcribing = Transcribing
                current_reminding = Reminding

            # Handle case where file exists but no transcription flags are set
            # This can happen if recording was stopped before model loaded
            if not current_transcribing and not current_reminding:
                print("Found recording file but no transcription flags set - assuming regular transcription")
                with app_lock:
                    Transcribing = True
                    current_transcribing = True

            if current_transcribing:
                # Print original transcript
                # print("\nOriginal Transcript:")
                print(f"\033[33m{transcript}\033[0m")
                
                # Clean and correct the transcript
                cleaned_transcript = transcript # clean_transcript(transcript, openai_client)
                
                # Print cleaned transcript
                #print("Cleaned Transcript:")
                #print(f"\t\033[32m{cleaned_transcript}\033[0m\n")

                # Check if using keyboard typing or clipboard paste
                with app_lock:
                    should_type = USE_REALTIME_TYPING
                
                if should_type:
                    # Use the keyboard typing method
                    keyboard_controller = keyboard.Controller()
                    type_with_newlines(cleaned_transcript, keyboard_controller)
                else:
                    # Always copy to clipboard
                    clipboard_copy_paste(cleaned_transcript)
                    
                transcript = ""  # Clear the transcript
                print(f"Transcription done!")
                
            elif current_reminding:
                print("\nReminder:"); print("\t\033[32m " + transcript + "\033[0m\n")
                process_reminder(transcript)
        
            # Update file counters after successful processing
            with app_lock:
                # Update our tracking of what we've processed
                last_processed_counter = file_ready_counter
                file_ct = file_ready_counter # This is unused...
                
                # Only reset states if we actually did something
                if Transcribing or Reminding:
                    Transcribing = False
                    Reminding = False
                    # print("Reset Transcribing/Reminding state")
                    print()
        
        except Exception as e:
            print(f"Error in transcription thread: {e}")
            time.sleep(1) # Add a short pause to prevent tight loop if there's a persistent error


Silent_frame_ct = 0
Noisy_frame_ct = 0
Frames = None
SILENCE_DETECT_LOGGING = True  # Set to False to disable chunk processing logs

def silence_detector(data, chunk=1024, fs = 44100, silence_threshold=2E5, max_silence_duration=3.0, min_chunk_duration=1.0):
    global Silent_frame_ct, Noisy_frame_ct, current_chunk_index, Frames, Chunk_Queue

    # CONSTS
    chunk = 1024  # Record in chunks of 1024 samples
    sample_format = pyaudio.paInt32  # 16 bits per sample
    channels = 1
    fs = 44100  # Record at 44100 samples per second
    p = pyaudio.PyAudio()  # Create an interface to PortAudio
    frame_duration = chunk / fs

    # Convert to numpy array, calculate energy, and determine if silent
    audio_data = np.frombuffer(data, dtype=np.int32)
    energy = np.sum(np.abs(audio_data)) / len(audio_data)
    current_is_silent = energy < silence_threshold
    # if SILENCE_DETECT_LOGGING: print(f"Energy: {energy:.4f} (threshold: {silence_threshold}) —> {'Silent' if current_is_silent else 'ACTIVE!'}")
    
    if current_is_silent:
        Silent_frame_ct += 1
        Noisy_frame_ct = 0
    else:
        Silent_frame_ct = 0
        Noisy_frame_ct += 1
    
    # Calculate silence duration
    silence_duration = Silent_frame_ct * frame_duration     # active_duration = active_frame_count * frame_duration
    
    # If silence exceeds max duration, save current chunk and start new one
    if silence_duration >= max_silence_duration and len(Frames) > int(min_chunk_duration * fs / chunk):
        if SILENCE_DETECT_LOGGING: print(f"Detected {silence_duration:.2f}s silence - splitting chunk")
        
        # Filename + path for wav chunk
        chunk_path = os.path.join(chunks_folder, f"chunk_{current_chunk_index:04d}_{int(time.time())}.wav")
        save_frames_to_wav(Frames[:-Silent_frame_ct], chunk_path, channels, sample_format, fs, p)
        
        # Add to transcription queue
        Chunk_Queue.append(chunk_path)
        current_chunk_index += 1
        
        # Keep only the silent frames for the next chunk
        Frames = Frames[-Silent_frame_ct:]
        Silent_frame_ct = 0
        
        if SILENCE_DETECT_LOGGING: print(f"Detected {silence_duration:.2f}s silence - splitting chunk. Saved to {chunk_path} & reset frames")

    # Visual feedback on console for silence detection
    # if SILENCE_DETECT_LOGGING and silence_frame_count % 10 == 0:
    #    if current_is_silent: print(f"Silence: {silence_duration:.1f}s")
    #    else: print(f"Active: {active_duration:.1f}s", end="")


# Fix for record_speech function
def record_speech(silence_chunking=False):
    """Record audio from microphone and save to a WAV file."""
    global file_ready_counter
    global tkinter_loop
    global Recording, Transcribing
    global Silent_frame_ct, Noisy_frame_ct, Frames # For silence detection chunking

    # Reset globals (chunkng mode)
    Silent_frame_ct = 0
    Noisy_frame_ct = 0
    Frames = []  # Initialize array to store frames
    
    # Check recording state under lock, but don't hold the lock for the entire function
    with app_lock:
        if not Recording:
            logging.info("Recording already stopped or not started")
            return
    
    logging.info("Recording thread started")
    try:
        # ==> Recording thread loop ==>
        if not tkinter_loop:
            logging.info("Overlay doesn't exist!")

        update_state(recording=True)
        
        chunk = 1024  # Record in chunks of 1024 samples
        sample_format = pyaudio.paInt32  # 16 bits per sample
        channels = 1
        fs = 44100  # Record at 44100 samples per second
        p = pyaudio.PyAudio()  # Create an interface to PortAudio


        # 🔌 Try to open the stream with 2 channels
        try:
            stream = p.open(format=sample_format,
                            channels=channels,
                            rate=fs,
                            frames_per_buffer=chunk,
                            input=True)
        except OSError as e:
            if e.errno == -9998:  # Invalid number of channels
                logging.info("Stereo not supported, falling back to mono.")
                channels = 1
                stream = p.open(format=sample_format,
                                channels=channels,
                                rate=fs,
                                frames_per_buffer=chunk,
                                input=True)
            else:
                raise e

        # 🟢 ON
        play_recording_sound(start=True) # playsound("C:\\Windows\\Media\\Speech On.wav")
        if tkinter_loop is True:
            try:
                root.after(0, show_overlay)
            except Exception as e:
                logging.info("Overlay not shown due to exception: ", e)

        # 🎙️ REC
        recording_stopped = False
        was_canceled = False
        max_time = 99999  # Maximum recording time in seconds. Will stop recording after this time.
        start_time = time.time()

        print("\nListening...")

        # Clear any previous cancel event
        cancel_event.clear()  

        # Use smaller chunks for reading and check cancellation more frequently (more responsive)
        iter_chunk = min(chunk, 256)  
        
        while not recording_stopped and (time.time() - start_time) < max_time:
            # Check cancel event first -> this is explicit cancellation (Alt+W)
            if cancel_event.is_set():
                print("Canceling!")
                recording_stopped = True
                was_canceled = True
                break
            # Check Recording state under lock -> this is for normal stopping (Alt+Q)
            with app_lock:
                if not Recording:
                    recording_stopped = True
                    break 
            # Read-in audio chunks -> this is the main recording function
            try:
                data = stream.read(iter_chunk, exception_on_overflow=False)
                Frames.append(data)
                if silence_chunking:
                    # If silence chunking is enabled, process the frames for silence detection
                    silence_detector(data=data, chunk=iter_chunk, fs=fs)
            except Exception as e:
                logging.error(f"Error reading audio data: {e}")
                recording_stopped = True
                break

        # Stop and close the stream
        try:
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            logging.error(f"Error closing audio stream: {e}")

        # 🛑 OFF!
        play_recording_sound(start=False) # playsound("C:\\Windows\\Media\\Speech Off.wav")
        if tkinter_loop is True:
            try:
                root.after(0, hide_overlay)
            except Exception as e:
                logging.error("Overlay not hidden due to exception: ", e)

        # Save the recorded data if:
        # 1. We have enough frames
        # 2. This was a normal stop (not canceled with Alt+W)
        if not was_canceled and len(Frames) > 20:
            # print("Normal stop with enough frames - saving recording for transcription")
            # Save the recorded data as a WAV file 💾 
            wf = wave.open("transcript.wav", 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(sample_format))
            wf.setframerate(fs)
            wf.writeframes(b''.join(Frames))
            wf.close()
            # Only increment counter if file was saved successfully
            with app_lock:
                file_ready_counter += 1
                # print(f"Incremented file_ready_counter to {file_ready_counter}")
        else:
            if was_canceled:
                print("Recording was canceled - not saving")
            else:
                print("Recording too short - not saving")
    
    # Handle exceptions from entire recording process
    except Exception as e:
        logging.error(f"Error in recording: {e}", exc_info=True)
    
    # Finally, update state flag! 👋🏼
    finally:
        with app_lock:
            if Recording:  # Only update if it hasn't been changed already
                update_state(recording=False)
                print("Set Recording=False in record_speech")
            
        logging.info("Recording thread completed")

# For real-time recording with silence detection
def save_frames_to_wav(frames, filepath, channels, sample_format, fs, p):
    """Save audio frames to a WAV file"""
    try:
        if frames:
            # Save the recorded data as a WAV file
            wf = wave.open(filepath, 'wb')
            wf.setnchannels(channels)
            wf.setsampwidth(p.get_sample_size(sample_format))
            wf.setframerate(fs)
            wf.writeframes(b''.join(frames))
            wf.close()
            logging.info(f"Chunk saved to {filepath}")
            return True
    except Exception as e:
        logging.error(f"Error saving chunk: {e}")
    return False

# THIS NEEDS TO WORK WITH process_chunk->split_on_silence args!!
def remove_whitespace_wav_on_silence(input_file, output_file, min_silence_ms=4000, silence_thresh=-40, max_silence_ms=8000):
    """
    Process audio by removing silence while maintaining some controlled silence between chunks.
    
    Parameters:
    - input_file: path to input audio file
    - output_file: path to save the processed audio file
    - min_silence_len: minimum silence length in milliseconds to detect as silence
    - silence_thresh: silence threshold in dB
    - max_silence_keep: maximum silence to keep in milliseconds
    """
    try:
        # Load the audio file
        audio = AudioSegment.from_file(input_file)
        
        # Split audio where silence is detected
        audio_chunks = split_on_silence(
            audio,
            min_silence_len=min_silence_ms,
            silence_thresh=silence_thresh,
            keep_silence=min(100, max_silence_ms // 10)  # Keep a small portion at boundaries
        )
        
        # If no chunks were detected, return the original audio
        if not audio_chunks:
            print(f"No audio chunks detected in {input_file}")
            audio.export(output_file, format="wav")
            return output_file
        
        # Combine all audio chunks with controlled silence between them
        combined = AudioSegment.empty()
        for i, chunk in enumerate(audio_chunks):
            combined += chunk
            # Add a small amount of silence between chunks, but not after the last one
            if i < len(audio_chunks) - 1 and max_silence_ms > 0:
                silence_duration = min(300, max_silence_ms)  # Cap at 300ms for natural pauses
                combined += AudioSegment.silent(duration=silence_duration)
        
        # Export the result
        combined.export(output_file, format="wav")
        print(f"Processed audio saved to {output_file}")
        return output_file
    
    except Exception as e:
        print(f"Error in split_on_silence: {e}")
        traceback.print_exc()
        # Return the original file path if processing fails
        return input_file


def process_chunk(chunk_path, current_transcript=""):
    """
    Process a single audio chunk file and return its transcript
    
    Parameters:
    - chunk_path: Path to the WAV file chunk
    - current_transcript: Accumulated transcript so far (for context)
    
    Returns:
    - The transcribed text from this chunk
    """
    global model_inst
    
    try:
        if not os.path.exists(chunk_path):
            print(f"Chunk file not found: {chunk_path}")
            return ""
        
        # Check file size to ensure it's valid
        if os.path.getsize(chunk_path) < 1000:  # Less than 1KB
            print(f"Chunk too small to process: {chunk_path}")
            return ""
        
        print(f"Processing chunk: {chunk_path}")
        
        # First, optionally clean up silence within the chunk itself
        processed_path = chunk_path + ".processed.wav"

        # Args: input_file, output_file, min_silence_ms=500, silence_thresh=-40, max_silence_ms=2000
        remove_whitespace_wav_on_silence(
            chunk_path, 
            processed_path, 
            min_silence_ms=4000,  # 500ms minimum silence to detect
            silence_thresh=-40,   # -40dB threshold for silence
            max_silence_ms=8000 # Keep max 4 seconds of silence
        )
        
        # Use the processed file if it exists, otherwise fall back to original
        if os.path.exists(processed_path) and os.path.getsize(processed_path) >= 1000:
            file_to_transcribe = processed_path
        else:
            file_to_transcribe = chunk_path
        
        # Transcribe the audio
        result = model_inst.transcribe(file_to_transcribe)
        transcript = result["text"].strip()
        
        if transcript:
            print(f"\nChunk transcript: {transcript}")
            
            # Optionally, add the transcript to the clipboard
            if current_transcript:
                full_transcript = current_transcript + " " + transcript
            else:
                full_transcript = transcript
                
            # Copy to clipboard in "below_top" position
            clipboard_copy_paste(full_transcript, position="below_top")
            
            return transcript
        else:
            print("No speech detected in chunk")
            return ""
            
    except Exception as e:
        print(f"Error processing chunk {chunk_path}: {e}")
        traceback.print_exc()
        return ""



def process_chunks_queue():
    """Process chunks from the queue as they become available"""
    global Chunk_Queue, model_inst
    
    # Wait for model to be ready
    while model_inst is None:
        time.sleep(0.1)
    
    print("Chunk processor ready")
    
    # Accumulated transcript for incremental updates
    accumulated_transcript = ""
    
    # Process queue
    processed_chunks = set()
    while True:
        # Exit if requested or not in real-time mode
        with app_lock:
            current_real_time = realtime_recording
        
        if cancel_event.is_set() or not current_real_time:
            if not current_real_time and not cancel_event.is_set():
                # Process any remaining chunks before exiting
                for chunk_path in list(Chunk_Queue):
                    if chunk_path not in processed_chunks:
                        transcript = process_chunk(chunk_path, accumulated_transcript)
                        if transcript:
                            accumulated_transcript += " " + transcript
                        processed_chunks.add(chunk_path)
                        if SILENCE_DETECT_LOGGING: print(f"Processed chunk: {chunk_path}")
            time.sleep(0.1)
            if not current_real_time:
                break
            continue
        
        # Check for new chunks
        if Chunk_Queue:
            # Get the next chunk
            chunk_path = Chunk_Queue[0]
            
            if os.path.exists(chunk_path) and chunk_path not in processed_chunks:
                # Process the chunk and get its transcript
                transcript = process_chunk(chunk_path, accumulated_transcript)
                
                # Update accumulated transcript if we got something
                if transcript:
                    if accumulated_transcript:
                        accumulated_transcript += " " + transcript
                    else:
                        accumulated_transcript = transcript
                
                # Mark as processed
                processed_chunks.add(chunk_path)
            
            # Remove from queue
            Chunk_Queue.pop(0)
        
        # Short delay
        time.sleep(0.1)

# Transcribes automagically between gaps in speech
def record_speech_with_silence_detection():
    """Record audio with real-time silence detection for chunking"""
    global file_ready_counter, tkinter_loop, Recording, realtime_recording, current_chunk_index
    
    # Check recording state
    with app_lock:
        if not realtime_recording or not Recording:
            logging.info("Real-time recording not active")
            return
    
    logging.info("Real-time recording thread started")
    
    try:
        # Update UI state
        update_state(recording=True)
        
        # Initialize audio recording
        chunk = 1024
        sample_format = pyaudio.paInt32
        channels = 2
        fs = 44100
        p = pyaudio.PyAudio()
        
        # Try to open the stream with 2 channels
        try:
            stream = p.open(format=sample_format,
                            channels=channels,
                            rate=fs,
                            frames_per_buffer=chunk,
                            input=True)
        except OSError as e:
            if e.errno == -9998:  # Invalid number of channels
                logging.info("Stereo not supported, falling back to mono.")
                channels = 1
                stream = p.open(format=sample_format,
                                channels=channels,
                                rate=fs,
                                frames_per_buffer=chunk,
                                input=True)
            else:
                raise e
        
        # Play sound and show overlay
        play_recording_sound(start=True) # playsound("C:\\Windows\\Media\\Speech On.wav")
        if tkinter_loop is True:
            try:
                root.after(0, show_overlay)
            except Exception as e:
                logging.info("Overlay not shown due to exception: ", e)
        
        # Initialize variables for silence detection
        frames = []
        silence_threshold = 500  # Adjust based on your microphone sensitivity
        max_silence_duration = 5.0  # 5 seconds max silence before splitting
        min_chunk_duration = 1.0  # Minimum duration for a chunk (in seconds)
        frame_duration = chunk / fs  # Duration of each frame in seconds
        silence_frame_count = 0
        active_frame_count = 0
        
        print("Real-time recording active... Press Alt+A to stop, Alt+W to cancel.")
        
        while True:
            # Check if we should stop
            if cancel_event.is_set() or not Recording or not realtime_recording:
                with app_lock:
                    if not realtime_recording or not Recording:
                        break
            
            # Read audio data
            try:
                data = stream.read(chunk, exception_on_overflow=False)
                frames.append(data)
                
                # Convert to numpy array for processing
                audio_data = np.frombuffer(data, dtype=np.int32)
                
                # Simple energy-based silence detection
                energy = np.sum(np.abs(audio_data)) / len(audio_data)
                
                # Check if current frame is silent
                current_is_silent = energy < silence_threshold
                
                if current_is_silent:
                    silence_frame_count += 1
                    active_frame_count = 0
                else:
                    active_frame_count += 1
                    silence_frame_count = 0
                
                # Calculate silence duration
                silence_duration = silence_frame_count * frame_duration
                active_duration = active_frame_count * frame_duration
                
                # If silence exceeds max duration, save current chunk and start new one
                if silence_duration >= max_silence_duration and len(frames) > int(min_chunk_duration * fs / chunk):
                    print(f"Detected {silence_duration:.2f}s silence - splitting chunk")
                    
                    # Save the current frames as a chunk
                    chunk_path = os.path.join(chunks_folder, f"chunk_{current_chunk_index:04d}_{int(time.time())}.wav")
                    save_frames_to_wav(frames[:-silence_frame_count], chunk_path, channels, sample_format, fs, p)
                    
                    # Add to transcription queue
                    Chunk_Queue.append(chunk_path)
                    
                    # Increment chunk index
                    current_chunk_index += 1
                    
                    # Keep only the silent frames for the next chunk
                    frames = frames[-silence_frame_count:]
                    
                    # Reset silence counter
                    silence_frame_count = 0
                
                # Visual feedback on console for silence detection
                if silence_frame_count % 10 == 0:
                    if current_is_silent:
                        print(f"\rSilence: {silence_duration:.1f}s", end="")
                    else:
                        print(f"\rActive: {active_duration:.1f}s ", end="")
            
            except Exception as e:
                logging.error(f"Error reading audio data: {e}")
                break
        
        # Stop and close the stream
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Play sound and hide overlay
        play_recording_sound(start=False) # playsound("C:\\Windows\\Media\\Speech Off.wav")
        if tkinter_loop is True:
            try:
                root.after(0, hide_overlay)
            except Exception as e:
                logging.error(f"Overlay not hidden: {e}")
        
        # Save any remaining frames as the final chunk
        if len(frames) > int(min_chunk_duration * fs / chunk):
            chunk_path = os.path.join(chunks_folder, f"chunk_{current_chunk_index:04d}_{int(time.time())}.wav")
            save_frames_to_wav(frames, chunk_path, channels, sample_format, fs, p)
            Chunk_Queue.append(chunk_path)
            if SILENCE_DETECT_LOGGING: print(f"Saved final chunk: {chunk_path}")

    except Exception as e:
        logging.error(f"Error in real-time recording: {e}", exc_info=True)
    
    finally:
        # Update state
        with app_lock:
            realtime_recording = False
            Recording = False
        
        logging.info("Real-time recording completed")


def process_reminder(transcript):
    """Process reminder text and create a reminder"""
    system_prompt = (
        "You are an assistant that helps to set reminders. "
        "Extract the text, date/time, and priority ('low' or 'high') from the user's input. "
        "If the user does not specify a priority, assume 'high'. "
        "If the user doesn't say 'reminder' or 'remind me', still set the reminder if a date and/or time is specified. "
        "Output a function call to 'set_reminder' with the extracted information. "
        "The 'date_time' should be in ISO 8601 format (YYYY-MM-DD HH:MM:SS)"
        f"The current time to the second is {datetime.now().isoformat(sep=' ', timespec='seconds')}."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": transcript}
    ]

    functions = [
        {
            "name": "set_reminder",
            "description": "Set a reminder with the given text, date/time, and priority.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reminder_text": {
                        "type": "string",
                        "description": "The reminder text as enterpreted from the transcribed speech. Correct any mistakes in the transcript by considering the context of the message (e.g. certain words sound alike, e.g. 'SNL skid' was probably spoken as 'SNL skit' by the user)."
                    },
                    "date_time": { 
                        "type": "string",
                        "description": "The date and time for the reminder in ISO 8601 format (YYYY-MM-DD HH:MM:SS). \n\nDefaults/fallbacks (if not provided/specified):\nTime: 10am\nDate: Today's date."
                    },
                    "reminder_frequency": {
                        "type": "object",
                        "description": "The frequency of the reminder and additional parameters for periodic reminders. Properties:\nperiod: The type of reminder frequency. Can be 'once', 'weekly', 'monthly', or 'yearly'.\nday: The day of the week for periodic reminders (only used when not 'once').\nmonth: The month for periodic reminders (only used if frequency is 'monthly' or 'yearly').",
                        "properties": {
                            "period": {
                                "type": "string",
                                "enum": ["once", "weekly", "monthly", "yearly"],
                                "description": "The type of reminder frequency."
                            },
                            "day": {
                                "type": "string",
                                "enum": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                                "description": "The day of the week for periodic reminders. Only used if frequency is 'weekly'."
                            },
                            "month": {
                                "type": "string",
                                "enum": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
                                "description": "The month for periodic reminders. Only used if frequency is 'monthly' or 'yearly'."
                            },
                        },
                        "required": ["period"]
                    },
                    "reminder_summary_title": {
                        "type": "string",
                        "description": "Short-title for a popup for this reminder (eg. general topic)."
                    },
                    "priority": {
                        "type": "string",
                        "description": "The priority of the reminder. Can be 'low' or 'high'."
                    },
                },
                "required": ["reminder_text", "date_time", "reminder_frequency", "reminder_summary_title"],
            }
        }
    ]

    try:
        if openai_client is None:
            logging.info("OpenAI client not initialized. Cannot process reminder.")
            return
            
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            functions=functions,
            function_call="auto"
        )

        # Extract function call information
        response_message = response.choices[0].message
        function_name = response_message.function_call.name if response_message.function_call else None
        arguments = response_message.function_call.arguments if function_name else {}

        if function_name:
            # Parse the JSON-formatted arguments
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as json_err:
                logging.error(f"Failed to decode JSON arguments: {json_err}")
                return

            # Extract reminder details
            reminder_str = arguments.get("reminder_text")
            date_time_str = arguments.get("date_time")
            priority = arguments.get("priority", "low")
            frequency_str = arguments.get("reminder_frequency")
            rem_summary_title_str = arguments.get("reminder_summary_title")

            if reminder_str and date_time_str:
                if global_use_system_reminder:
                    try:
                        set_reminder(reminder_str, date_time_str, rem_summary_title_str, frequency_str)
                    except Exception as e:
                        logging.error(f"Error setting reminder: {e}")
                else:
                    save_reminder(reminder_str, date_time_str, priority)
                    logging.error("Reminder set successfully.")
            else:
                logging.error("Missing 'reminder_text' or 'date_time' in the function arguments.")
        
        else:
            logging.error("No function call returned by OpenAI API.\nDid you specify what you want to be reminded about, and when to be reminded?") 
    
    except Exception as e:
        logging.error(f"Error processing reminder with OpenAI: {e}")


def clean_transcript(raw_transcript: str, openai_client) -> str:
    """
    Clean and correct a raw transcript using OpenAI's chat completion.
    
    Args:
        raw_transcript (str): The original transcript from Whisper
        openai_client: The OpenAI client instance
        
    Returns:
        str: The cleaned and corrected transcript
    """
    system_prompt = (
        "You are a transcript correction assistant. Your task is to:"
        "\n1. Remove filler words (um, uh, like, you know, etc)"
        "\n2. Correct likely transcription errors based on context"
        "\n3. Fix punctuation and formatting"
        "\n4. Maintain the original tone and style of speech, preserving casual or informal words, while correcting pauses and filler words"
        "\n5. Break into paragraphs where appropriate"
        "\n6. Correct homophones based on context (e.g. 'their' vs 'there')"
        "\nProvide ONLY the corrected text without any explanations or markup."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please clean and correct this transcript: {raw_transcript}"}
    ]
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )
        
        # Extract the cleaned transcript from the response
        cleaned_transcript = response.choices[0].message.content.strip()
        return cleaned_transcript
        
    except Exception as e:
        logging.error(f"\nError cleaning transcript: {e}")
        return raw_transcript  # Return original transcript if cleaning fails


def type_with_newlines(text: str, keyboard_controller):
    """
    Types out text with proper handling of newlines using Shift+Enter.
    Includes cancellation checks throughout.
    """
    for i, char in enumerate(text):
        # Check if typing should be canceled
        with app_lock:
            if Recording or cancel_event.is_set():
                print("Typing canceled")
                return
            
        try:
            if char == '\n':
                # Press Shift+Enter for newline in chat interfaces
                with keyboard_controller.pressed(keyboard.Key.shift):
                    keyboard_controller.press(keyboard.Key.enter)
                    keyboard_controller.release(keyboard.Key.enter)
                # Add a small delay after newlines for better reliability
                time.sleep(0.05)
            else:
                keyboard_controller.type(char)
                time.sleep(0.002) # 0.0033 is too slow for some characters, 0.0025 is better
            
            # Add occasional checks during typing
            if i % 10 == 0 and i > 0:
                with app_lock:
                    if Recording or cancel_event.is_set():
                        print("Typing canceled")
                        return
                        
        except Exception as e:
            print(f"Error typing character '{char}': {e}")
    

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~ Reminder Functions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# 📝 Save reminder to JSON
def save_reminder(text, date_time_str=None, priority='high'):
    # Parse date_time_str to datetime object
    if date_time_str:
        try:
            date_time = datetime.fromisoformat(date_time_str)
        except ValueError:
            print("Invalid date_time format. Please use YYYY-MM-DD HH:MM:SS format.")
            date_time = datetime.now() + timedelta(minutes=5)
            date_time_str = date_time.isoformat(sep=' ', timespec='minutes')
    else:
        date_time = datetime.now() + timedelta(minutes=5)  # default to 5 minutes later
        date_time_str = date_time.isoformat(sep=' ', timespec='minutes')

    reminder = {
        "text": text,
        "date_time": date_time_str,
        "priority": priority
    }

    try:
        # Load existing reminders
        reminders = []
        if os.path.exists(reminder_file) and os.path.getsize(reminder_file) > 0:
            with open(reminder_file, 'r') as f:
                reminders = json.load(f)

        reminders.append(reminder)

        # Save back to the reminders JSON file
        with open(reminder_file, 'w') as f:
            json.dump(reminders, f, indent=4)

        print(f"Reminder SAVED to {reminder_file}")  # Debugging
    except Exception as e:
        print(f"Error saving reminder: {e}")


# import for reg entry
def get_reminder_ct():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\WhisperTyper") as key:
            reminder_ct, _ = winreg.QueryValueEx(key, "reminder_ct")
    except FileNotFoundError:
        reminder_ct = 1
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\WhisperTyper") as key:
                winreg.SetValueEx(key, "reminder_ct", 0,
                                  winreg.REG_DWORD, reminder_ct)
        except Exception as e:
            print(f"Error creating registry key: {e}")
    except Exception as e:
        print(f"Error accessing registry: {e}")
        reminder_ct = 1
    return reminder_ct


def increment_reminder_ct():
    try:
        reminder_ct = get_reminder_ct()
        reminder_ct += 1
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\WhisperTyper", 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "reminder_ct", 0, winreg.REG_DWORD, reminder_ct)
    except Exception as e:
        print(f"Error incrementing reminder count: {e}")


def format_reminder_fields(title_str, reminder_str, date_time_str):
    try:
        # Parse date_time_str to object
        date_time = datetime.fromisoformat(date_time_str)
        print(f"\nSystem reminder request: '{reminder_str}', at '{date_time}'")

        # Entry starts with Reminder_N_
        N = get_reminder_ct()
        task_name = title_str
        if not task_name.startswith("Reminder_"):
            task_name = f"Reminder_{N}_{task_name}"
        else:
            task_name = task_name.replace("Reminder_", f"Reminder_{N}_")
            
        # Proper caps for title and reminder
        title_str = re.sub(r"(\w)(\w*)", lambda x: x.group(1).upper() +
                        x.group(2).lower(), title_str)
        reminder_str = reminder_str[0].upper() + reminder_str[1:]
        combined_reminder = f"[{title_str}]{reminder_str}"

        # Done!
        return task_name, combined_reminder, date_time
    except Exception as e:
        print(f"Error formatting reminder fields: {e}")
        # Return sensible defaults
        return f"{get_reminder_ct()}_Reminder_{title_str}", f"[{title_str}]{reminder_str}", datetime.now()


def user_reminder_editor_gui(title_str, reminder_str, date_time_str, frequency_tuple):
    try:
        editor_root = tk.Tk()
        editor_root.withdraw()  # Hide the root window

        # Function to make the screen flash green
        def flash_green():
            try:
                flash_window = tk.Toplevel(editor_root)
                flash_window.attributes('-fullscreen', True)
                flash_window.attributes('-topmost', True)
                flash_window.attributes('-alpha', 0.25)
                flash_window.configure(bg='green')
                flash_window.after(500, flash_window.destroy)  # Destroy after 500 ms
            except Exception as e:
                print(f"Error flashing green: {e}")

        # Flash green before showing the edit window
        editor_root.after(100, flash_green)

        # Create a new Tkinter window for editing the reminder
        edit_window = tk.Toplevel(editor_root)
        edit_window.title("Edit Reminder")
        edit_window.attributes('-topmost', True)  # Force window to stay on top
        
        # Center the window on the screen
        edit_window.update_idletasks()
        width = 450  # Increased width for frequency controls
        height = 400  # Increased height for frequency controls
        x = (edit_window.winfo_screenwidth() // 2) - (width // 2)
        y = (edit_window.winfo_screenheight() // 2) - (height // 2)
        edit_window.geometry(f'{width}x{height}+{x}+{y}')
        
        # Create and place labels and entry fields
        tk.Label(edit_window, text="Edit your reminder title:").pack(pady=5)
        title_entry = tk.Entry(edit_window, width=50)
        title_entry.insert(0, title_str)
        title_entry.pack(pady=5)
        
        tk.Label(edit_window, text="Edit your reminder text:").pack(pady=5)
        text_entry = tk.Entry(edit_window, width=50)
        text_entry.insert(0, reminder_str)
        text_entry.pack(pady=5)
        
        tk.Label(edit_window, text="Edit your reminder date/time (YYYY-MM-DD HH:MM:SS):").pack(pady=5)
        datetime_entry = tk.Entry(edit_window, width=50)
        datetime_entry.insert(0, date_time_str)
        datetime_entry.pack(pady=5)

        # Data from llm
        frequency_value = "once"  # Default value
        if frequency_tuple is not None:
            if isinstance(frequency_tuple, dict):
                frequency_value = frequency_tuple.get("period", "once")
            elif isinstance(frequency_tuple, str):
                frequency_value = frequency_tuple
        
        # print(f"DEBUG: frequency_tuple = {frequency_tuple}")
        # print(f"DEBUG: frequency_tuple type = {type(frequency_tuple)}")
        # print(f"DEBUG: frequency_value = {frequency_value}")

        # Frequency controls
        frequency_frame = tk.Frame(edit_window)
        frequency_frame.pack(pady=10)
        
        # Checkbox for enabling frequency
        frequency_enabled = tk.BooleanVar(value=frequency_value != "once")
        # print(f"DEBUG: frequency_enabled initial value = {frequency_enabled.get()}")
        
        frequency_checkbox = tk.Checkbutton(frequency_frame, text="Repeat reminder", variable=frequency_enabled)
        frequency_checkbox.pack(side=tk.LEFT, padx=(0, 10))
        
        # Dropdown for frequency options
        frequency_options = ["once", "weekly", "monthly", "yearly"]
        frequency_var = tk.StringVar(value=frequency_value)
        # print(f"DEBUG: frequency_var initial value = {frequency_var.get()}")
        
        frequency_dropdown = tk.OptionMenu(frequency_frame, frequency_var, *frequency_options)
        frequency_dropdown.pack(side=tk.LEFT)
        
        # Function to toggle frequency dropdown state
        def toggle_frequency_dropdown():
            if frequency_enabled.get():
                frequency_dropdown.config(state="normal")
                # Restore the original frequency value if we're enabling
                if frequency_value != "once":
                    frequency_var.set(frequency_value)
                # print(f"DEBUG: Enabled dropdown, current value = {frequency_var.get()}")
            else:
                frequency_dropdown.config(state="disabled")
                # Only set to "once" if user unchecked the checkbox, not during initialization
                if hasattr(toggle_frequency_dropdown, 'initialized'):
                    frequency_var.set("once")
                # print(f"DEBUG: Disabled dropdown, current value = {frequency_var.get()}")
        
        # Bind checkbox command BEFORE calling the initial toggle
        frequency_checkbox.config(command=toggle_frequency_dropdown)
        
        # Now initialize the dropdown state based on current values
        toggle_frequency_dropdown()
        # Mark as initialized after first call
        toggle_frequency_dropdown.initialized = True

        # Add a button to save and close the window
        result = {'title': title_str, 'text': reminder_str, 'datetime': date_time_str, 'frequency': 'once'}
        def save_and_close():
            try:
                print("Saving reminder...")
                result['title'] = title_entry.get()
                result['text'] = text_entry.get()
                result['datetime'] = datetime_entry.get()
                
                # Handle frequency
                if frequency_enabled.get():
                    result['frequency'] = frequency_var.get()
                else:
                    result['frequency'] = 'once'
                    
                edit_window.quit()
                edit_window.destroy()
            except Exception as e:
                print(f"Error saving reminder: {e}")

        # Add a button to cancel and close the window
        def cancel_and_close():
            try:
                print("Canceling reminder...")
                edit_window.quit()
                edit_window.destroy()
            except Exception as e:
                print(f"Error canceling reminder: {e}")
                print(f"Error canceling reminder: {e}")
            finally:
                with app_lock:
                    update_state(reminding=False, transcribing=False, recording=False)

        # Handle window close event
        def on_closing():
            print("Reminder edit window closed.")
            cancel_and_close()

        edit_window.protocol("WM_DELETE_WINDOW", on_closing)

        # Add buttons and run!
        tk.Button(edit_window, text="Save", command=save_and_close).pack(pady=5)
        tk.Button(edit_window, text="Cancel", command=cancel_and_close).pack(pady=5)
        
        # Run the dialog and wait
        editor_root.mainloop()

        # ensure results are strings
        result['title'] = str(result['title'])
        result['text'] = str(result['text'])
        result['datetime'] = str(result['datetime'])
        result['frequency'] = str(result['frequency'])
        
        return result['title'], result['text'], result['datetime'], result['frequency']
    except Exception as e:
        print(f"Error in reminder editor GUI: {e}")
        return title_str, reminder_str, date_time_str, 'once'  # Return original values with default frequency


def set_reminder(reminder_str, datetime_str, title_str, frequency_tuple):
    print(f"Reminder fields: {reminder_str}, {datetime_str}, {title_str}, {frequency_tuple}")
    # print(f"DEBUG: frequency_tuple type = {type(frequency_tuple)}")
    # print(f"DEBUG: frequency_tuple value = {frequency_tuple}")

    try:
        # Path to reminder popup exe (a exe compiled from the powershell ps1 script of the same name)
        exe_notification_path = os.path.join(
            PATH.replace("\\", "/"), 
            "toast-reminder.exe").replace("\\", "/")

        # Format and edit (user gui)
        task_name, combined_reminder, date_time = format_reminder_fields(title_str, reminder_str, datetime_str)
        title_str, reminder_str, datetime_str, user_frequency = user_reminder_editor_gui(title_str, reminder_str, datetime_str, frequency_tuple)

        # if any are none, then return
        if not title_str or not reminder_str or not datetime_str:
            print("Missing reminder data. Try again!")
            return
        else:
            print(f"Reminder fields: {title_str}, {reminder_str}, {datetime_str}, {user_frequency}")

        # Update period as specified in GUI (same as llm parsed output or modified/corrected by user)
        if user_frequency and user_frequency != 'once':
            if not frequency_tuple:
                frequency_tuple = {"period": user_frequency}
            else:
                frequency_tuple["period"] = user_frequency

        # Validate input parameters (optional but recommended)
        if not isinstance(frequency_tuple, dict):
            logging.error("Frequency must be a dictionary.")
            print("Frequency must be a dictionary.")
            raise ValueError("Frequency must be a dictionary.")
        if not exe_notification_path:
            logging.error("Executable path must be provided.")
            print("Executable path must be provided.")
            raise ValueError("Executable path must be provided.")
        
        # Reformatted combined reminder with edited values
        task_name = f"Reminder_{get_reminder_ct()}_{title_str}"
        combined_reminder = f"[{title_str}]{reminder_str}"
        
        # Construct the command to add the reminder to Task Scheduler
        # Corrected quoting for the -Argument parameter using backticks to escape double quotes
        # This ensures PowerShell interprets the argument correctly
        action_cmd = f'New-ScheduledTaskAction -Execute "{exe_notification_path}" -Argument "`\"{combined_reminder}`\""'
        logging.debug(f"Action Command: {action_cmd}")
        date_time_obj = datetime.fromisoformat(datetime_str)

        # Determine the trigger based on frequency
        trigger_period = frequency_tuple.get("period", "once").lower()
        if trigger_period == "once":
            trigger = f'New-ScheduledTaskTrigger -Once -At "{date_time_obj.strftime("%Y-%m-%dT%H:%M:%S")}"'

        elif trigger_period == "weekly":
            day = frequency_tuple.get("day", "Monday")
            trigger = (
                f'New-ScheduledTaskTrigger -Weekly -At "{date_time_obj.strftime("%H:%M")}" '
                f'-DaysOfWeek {day}'
            )

        elif trigger_period == "monthly":
            day = frequency_tuple.get("day", "Monday") # 2nd arg = default value
            trigger = (
                f'New-ScheduledTaskTrigger -Weekly -At "{date_time_obj.strftime("%H:%M")}" '
                f'-DaysOfWeek {day} -WeeksInterval 4'
            )

        elif trigger_period == "yearly":
            day = frequency_tuple.get("day", "Monday") 
            trigger = (
                f'New-ScheduledTaskTrigger -Weekly -At "{date_time_obj.strftime("%Y-%m-%dT%H:%M:%S")}"'
                f'-DaysOfWeek {day} -WeeksInterval 52'
            )
        else:
            logging.error(f"Unsupported frequency period: {trigger_period}")
            raise ValueError(f"Unsupported frequency period: {trigger_period}")

        logging.debug(f"Trigger Command: {trigger}")
        
        # Construct settings
        settings_cmd = 'New-ScheduledTaskSettingsSet -StartWhenAvailable'
        logging.debug(f"Settings Command: {settings_cmd}")
        
        # Combine all PowerShell commands into a single line separated by semicolons
        os_cmd_set_reminder = (
            f'$action = {action_cmd}; '
            f'$trigger = {trigger}; '
            f'$settings = {settings_cmd}; '
            f'Register-ScheduledTask -TaskName "{task_name}" -Action $action -Trigger $trigger -Settings $settings -Force'
        )
        
        # Debug: Print the constructed PowerShell command
        logging.debug("Constructed PowerShell Command:")
        logging.debug(os_cmd_set_reminder)
        
        # Execute the PowerShell command
        result = subprocess.run(
            ["powershell", "-Command", os_cmd_set_reminder],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Increment reminder count and provide feedback
        increment_reminder_ct()
        logging.info("System reminder added to Task Scheduler with dialog box.")
        logging.debug(f"Command output: {result.stdout}")
    
    except subprocess.CalledProcessError as e:
        logging.error(f"Error adding system reminder: {e}")
        logging.debug(f"Command output: {e.output}")
        logging.debug(f"Command error: {e.stderr}")
    except Exception as ex:
        logging.error(f"An unexpected error occurred: {ex}")

    # print as point-notes each part of the reminder
    print(f"\033[32m\nSET REMINDER:\n -{title_str}\n -{reminder_str}\n -{datetime_str}\n -{frequency_tuple}\033[0m")

# 🗓️ Parse date and time from text
def parse_date_time(text):
    now = datetime.now()
    if "tomorrow" in text:
        return now + timedelta(days=1)
    elif "next week" in text:
        return now + timedelta(weeks=1)
    # 🔧 Return 5 minutes later by default
    return now + timedelta(minutes=5)


def list_clipboard_formats():
    try:
        win32clipboard.OpenClipboard()
        formats = []
        try:
            format = win32clipboard.EnumClipboardFormats(0)
            while format != 0:
                formats.append(format)
                format = win32clipboard.EnumClipboardFormats(format)
        finally:
            win32clipboard.CloseClipboard()
        print("Available clipboard formats:", formats)
    except Exception as e:
        print(f"Error listing clipboard formats: {e}")

# 📎Last im from clippy
def capture_png_from_clipboard():
    image_folder = "./clipboard_images/"
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)

    try:
        win32clipboard.OpenClipboard()

        # Register and check for PNG format
        png_format = win32clipboard.RegisterClipboardFormat("PNG")

        if win32clipboard.IsClipboardFormatAvailable(png_format):
            print("PNG format found in clipboard")
            data = win32clipboard.GetClipboardData(png_format)

            image = Image.open(BytesIO(data))
            img_path = f"{image_folder}image_{int(time.time())}.png"
            image.save(img_path)
            print(f"PNG image saved successfully at: {img_path}")
            return {"type": "image", "path": img_path}

        # Fallback to CF_DIB format if PNG is not available
        elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
            print("CF_DIB format found, attempting to convert to PNG")
            data = win32clipboard.GetClipboardData(win32con.CF_DIB)
            image = Image.open(BytesIO(data))
            img_path = f"{image_folder}image_{int(time.time())}.png"
            image.save(img_path, "PNG")
            print(f"Image converted and saved as PNG at: {img_path}")
            return {"type": "image", "path": img_path}

        else:
            print("No PNG or compatible image format found in clipboard")

            # Debug information
            formats = []
            format_id = 0
            while True:
                try:
                    format_id = win32clipboard.EnumClipboardFormats(format_id)
                    if format_id == 0:
                        break
                    format_name = str(format_id)
                    try:
                        format_name = win32clipboard.GetClipboardFormatName(
                            format_id)
                    except:
                        pass
                    formats.append(f"{format_id}: {format_name}")
                except:
                    break
            print("Available clipboard formats:")
            for fmt in formats:
                print(f"  {fmt}")

    except Exception as e:
        print(f"Error accessing or processing clipboard: {e}")

    finally:
        try:
            win32clipboard.CloseClipboard()
        except:
            pass

    return None


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~ Keyboard Event Handlers ~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Toggle typing preference
def on_alt_t():
    global USE_REALTIME_TYPING
    with app_lock:
        USE_REALTIME_TYPING = not USE_REALTIME_TYPING
    print(f"Keyboard typing is now {'ENABLED' if USE_REALTIME_TYPING else 'DISABLED'}")
    print(f"Transcripts will be {'typed out' if USE_REALTIME_TYPING else 'copied to clipboard'}")

# Real-time transcription with silence detection
def on_alt_a():
    """Toggle real-time transcription mode with silence detection"""
    global recording_thread, ChunkedRecording, Recording, Transcribing
    
    def set_fields():
        # Ensure chunks folder exists
        os.makedirs(chunks_folder, exist_ok=True)
        
        # Clear existing chunks
        for file in os.listdir(chunks_folder):
            if file.endswith(".wav"):
                try:
                    os.remove(os.path.join(chunks_folder, file))
                except:
                    pass
        
        # Reset chunk index
        global current_chunk_index
        current_chunk_index = 0
        
        # Clear queue
        global Chunk_Queue
        Chunk_Queue = []
        
        # Clear cancel event
        cancel_event.clear()
        
        update_state(recording=True, realtime_recording=True, transcribing=True)  
        cancel_event.clear()

    # Do not interrupt running reminders!
    if Reminding:
        print("Cannot run transcription listener! Currently recording for reminders. Press Alt + R to end reminder recording first.")
        return
    
    # Check if already recording for a reminder
    with app_lock:
        # if Reminding:
        #     print("Reminder listener is active... press Alt + R to end reminder transcription.")
        #     return
        if ChunkedRecording or Recording:
            print("Stopped...")
            update_state(recording=False, realtime_recording=False)  # Set state directly
            return
            # IMPORTANT: DON'T set cancel_event for normal stops!
            # Only set it for Alt+W cancellations
            # cancel_event.set()  <-- REMOVED THIS LINE    
        else:
            # Model check
            if model_inst is None and faster_whisper is None:
                print("Model is still loading... Recording will be transcribed once model is ready.")
            # Start recording!
            set_fields()
            # print("\nListening...")
    
    print("Starting real-time transcription... (listening for speech with silence detection)")
    
    # Start recording thread with real-time processing
    recording_thread = threading.Thread(target=record_speech, args=(True,), daemon=True) # OLD: record_speech_with_silence_detection
    recording_thread.start()
    
    # Start the real-time transcription processor
    # transcribe_thread = threading.Thread(target=process_chunks_queue, daemon=True)
    # transcribe_thread.start()

# Toggle recording with hotkey
def on_alt_q():
    global recording_thread, Transcribing, Recording
    print("Alt + Q pressed — toggling transcription...")

    # Do not interrupt running reminders!
    if Reminding:
        print("Cannot run transcription listener! Currently recording for reminders. Press Alt + R to end reminder recording first.")
        return
    
    # Check if already recording for a reminder
    with app_lock:
        # if Reminding:
        #     print("Reminder listener is active... press Alt + R to end reminder transcription.")
        #     return

        if Recording or ChunkedRecording:
            print("Stopped...")
            update_state(recording=False, realtime_recording=False)  # Set state directly
            return
            # IMPORTANT: DON'T set cancel_event for normal stops!
            # Only set it for Alt+W cancellations
            # cancel_event.set()  <-- REMOVED THIS LINE    
        # Else, set flags for start-recording!
        else:
            # Warn user if model isn't loaded yet, but still allow recording
            if model_inst is None and faster_whisper is None:
                print("Model is still loading... Recording will be transcribed once model is ready.")
            
            update_state(recording=True, transcribing=True)  
            # Clear cancel event before starting thread
            cancel_event.clear()
            # print("\nListening...")

    recording_thread = threading.Thread(target=record_speech, daemon=True)
    recording_thread.start()

# Toggle recording with hotkey for setting reminders
def on_alt_r():
    global recording_thread, Reminding
    
    # Skip if no key set on this machine
    if openai_client is None:
        print(f"""OpenAI key is required for reminders feature! {REMINDER_SETUP_INSTRUCTIONS}""")
        return
    
    # Do not interrupt running transcriptions!
    if Transcribing:
        print("Cannot run reminder listener! Currently recording for transcription. Press Alt + Q to end transcription first.")
        return
        
    with app_lock:
        # If currently recording, stop -> transcribe!
        if Recording:
            update_state(recording=False)
            # os.system('cls' if os.name == 'nt' else 'clear')
            print("Stopped listening for reminder...")
            return
        # Else, set flags for start-recording!
        else: 
            # Warn user if model isn't loaded yet, but still allow recording for reminders
            if model_inst is None and faster_whisper is None:
                print("Model is still loading... Reminder will be processed once model is ready.")
            
            update_state(recording=True, reminding=True)
            cancel_event.clear()  # Clear any previous cancel flag

    # Clear the screen
    # if model_inst is not None:
    #     os.system('cls' if os.name == 'nt' else 'clear')
        
    
    print("Listening for reminder...")
    recording_thread = threading.Thread(target=record_speech, daemon=True)
    recording_thread.start()

# ❌ Cancel any transcription (reminder or regular)
def on_alt_w():
    global recording_thread
    
    with app_lock:
        if Recording:
            print("Transcription canceled.")
            # First set the cancel event to interrupt any loops
            cancel_event.set()
            # Then update state flags
            update_state(recording=False, transcribing=False, reminding=False)
            
            # Force the recording thread to stop if it's running
            if recording_thread and recording_thread.is_alive():
                try:
                    print("Joining recording thread...")
                    recording_thread.join(timeout=1.0)
                except:
                    print("Error joining recording thread.")
                    pass
                    
            print("Transcription process terminated.")
        else:
            print("No transcription to cancel.")

# 📜 On user-paste, if the last clipboard entry is from the last transcription, then remove it after a short pause
def on_ctrl_v():
    try:
        # Cooldown period for pasting the last clipboard entry
        time.sleep(0.25)
        # Get the current clipboard content
        with app_lock:
            history = clipboard_hist.history
            if history: 
                latest_entry = history[0]  # Check but don't pop yet
                # if the entry has _special_char at the end, then we want to copy the previous entry in pyperclip to the clipboard
                if latest_entry.endswith(_special_char):
                    history.popleft()  # Now remove it
                    # Get the previous clipboard content
                    if len(history) > 0:
                        # Copy the previous clipboard content to the system clipboard
                        previous_entry = history[0]  # Just check, don't pop
                        pyperclip.copy(previous_entry)
    except Exception as e: 
        print(f"Error in ctrl+v handler: {e}")


# Keep running tabs on the clipboard
def on_ctrl_c():
    try:
        time.sleep(0.25)
        # copy the last clipboard entry from windows into the clipboard
        clipboard_content = pyperclip.paste()
        if clipboard_content:
            with app_lock:
                clipboard_hist.history.appendleft(clipboard_content)    
    except Exception as e:
        print(f"Error copying clipboard content: {e}")

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~    Hotkey Setup    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# === Option 1: Keyboard Library Lister ===
def init_hotkeys_kb():
    """Initialize hotkeys using the keyboard library for synchronous input handling"""
    kb.add_hotkey('alt+q', on_alt_q)     # 🎤 For regular transcription
    kb.add_hotkey('alt+t', on_alt_t)     # ⌨️ Toggle typing vs. pasting
    kb.add_hotkey('alt+w', on_alt_w)     # ❌ Cancel transcription
    kb.add_hotkey('alt+r', on_alt_r)     # ⏰ For setting reminders
    kb.add_hotkey('alt+a', on_alt_a)     # 💨 for continuous real-time transcription.
    print("Hotkeys initialized using the keyboard library")
    # kb.add_hotkey('ctrl+v', on_ctrl_v)   # 📜 For pasting the last clipboard entry
    # kb.add_hotkey('ctrl+c', on_ctrl_c)   # 📎 For copying the current clipboard entry

# === Option 2: Original Keyboard Listener ===
def init_hotkeys_async():
    """Initialize hotkeys using keyboard.Listener for async input handling"""
    pressed = set()
    executed_combinations = set()

    def on_press(key):
        """Check pressed keys and execute commands based on combinations"""
        pressed.add(key)

        for c in COMBINATIONS:
            for keys in c["keys"]:
                if keys.issubset(pressed):
                    # Create a hashable representation of the key combination
                    combo_hash = frozenset(keys)
                    # Only execute if this combination hasn't been executed yet
                    if combo_hash not in executed_combinations:
                        executed_combinations.add(combo_hash)
                        # Execute the command
                        if c["command"] == "transcribe_speech":
                            on_alt_q()
                        elif c["command"] == "set_reminder":
                            on_alt_r()
                        elif c["command"] == "cancel_transcription":
                            on_alt_w()
                        elif c["command"] == "realtime_transcribe_speech":
                            on_alt_a()
                        elif c["command"] == "toggle_typing_mode":
                            on_alt_t()

    def on_release(key):
        """Handle key releases and reset combinations"""
        if key in pressed:
            pressed.remove(key)
        # Clear executed combinations when all keys are released
        if not pressed:
            executed_combinations.clear()

    COMBINATIONS = [
        {
            "keys": [
                { keyboard.Key.alt_l, keyboard.KeyCode(char="q") }
            ],
            "command": "transcribe_speech",  # 🎤 Start/stop regular transcription
        },
        {
            "keys": [
                { keyboard.Key.alt_l, keyboard.KeyCode(char="r") }
            ],
            "command": "set_reminder",
        },
        {
            "keys": [
                { keyboard.Key.alt_l, keyboard.KeyCode(char="w") }
            ],
            "command": "cancel_transcription",
        },
        {
            "keys": [
                { keyboard.Key.alt_l, keyboard.KeyCode(char="t") }
            ],
            "command": "toggle_typing_mode", # ⌨️ Toggle typing (one char at a time) vs. pasting
        },
        # {
        #     "keys": [
        #         { keyboard.Key.alt_l, keyboard.KeyCode(char="a") }
        #     ],
        #     "command": "realtime_transcribe_speech",  # 💨 Start/stop real-time transcription with silence detection
        # },
    ]

    # Subscribe to keyboard events!
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~ Main Program Loop ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def thread_monitor():
    """Monitor threads and restart them if needed, but with proper checks"""
    global transcribe_thread
    global overlay_thread

    while True:
        time.sleep(5)  # Check less frequently
        
        # Check if we should exit
        if cancel_event.is_set():
            time.sleep(0.1)  # Brief pause
            continue  # Skip this iteration
            
        try:
            # Only restart transcribe thread if it's completely dead, not just waiting
            if not transcribe_thread.is_alive():
                # Check if program is exiting
                if cancel_event.is_set():
                    continue
                    
                # Additional check to avoid unnecessary restarts
                with app_lock:
                    # Only restart if we're not already recording or transcribing
                    if not Recording and not Transcribing and not Reminding:
                        print("Transcription thread died, restarting...")
                        new_thread = threading.Thread(target=transcribe_speech, daemon=True)
                        new_thread.start()
                        # Update global variable under lock
                        transcribe_thread = new_thread
            
            # Similar careful check for overlay thread
            if not overlay_thread.is_alive() and tkinter_loop:
                if not cancel_event.is_set():
                    print("Overlay thread died, restarting...")
                    new_overlay = threading.Thread(target=init_overlay, daemon=True)
                    new_overlay.start()
                    overlay_thread = new_overlay
                    
        except Exception as e:
            print(f"Error in thread monitoring: {e}")

def init_hotkey_listener():    
    if USE_KBLIB_LISTENER:
        print("Using keyboard library for hotkey handling...")
        init_hotkeys_kb()
    else:
        print("Using async monitor for hotkey handling...")
        init_hotkeys_async()

    print()
    print("===========================================")
    print("Hotkeys ready:")
    print("- Alt + Q: Start/stop regular transcription")
    print("- Alt + R: Start/stop setting a reminder")
    print("- Alt + W: Cancel any transcription")
    print("- Alt + T: Toggle between keyboard typing and clipboard pasting")
    print("- Ctrl + V: Paste (with special handling for transcriptions)")
    print("- Ctrl + C: Copy to clipboard history")
    print("===========================================")
    print()

def init_overlay():
    global tkinter_loop, root, overlay
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        overlay = Overlay(image_filename="mic.png", root_tk=root)
        hide_overlay()
        tkinter_loop = True
        root.mainloop()
    except Exception as e:
        print(f"Error initializing overlay: {e}")
        tkinter_loop = False


def init_app_priority():
    try:
        p = psutil.Process(os.getpid())
        p.nice(psutil.HIGH_PRIORITY_CLASS)  # Windows specific
    except Exception as e:
        print(f"Error setting process priority: {e}")


def faster_whisper_init():
    global faster_whisper
    
    # NEW
    try:
        from transformers import pipeline
        import torch
        
        # Check CUDA availability
        device = "cuda" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if device == "cuda" else torch.float32
        
        print(f"Initializing Distil-Whisper on device: {device}")
        
        # Initialize the pipeline
        faster_whisper = pipeline(
            "automatic-speech-recognition",
            model="distil-whisper/distil-medium.en", # distil-large-v3",
            torch_dtype=torch_dtype,
            device=device
        )
        print("✅ Faster Whisper model initialized successfully.")
        return
        
    except ImportError as e:
        print(f"❌ Missing required packages: {e}")
        print("Install with: pip install transformers accelerate datasets[audio] torch")
        faster_whisper = None
        return
    except Exception as e:
        print(f"❌ Error initializing Faster Whisper: {e}")
        import traceback
        traceback.print_exc()
        faster_whisper = None
        return
    
    # OLD
    try:
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
        from datasets import load_dataset

        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

        model_id = "distil-whisper/distil-large-v3"

        AutoModelForSpeechSeq2Seq.from_pretrained(
            model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True
        )
        model_inst.to(device)

        processor = AutoProcessor.from_pretrained(model_id)

        faster_whisper = pipeline(
            "automatic-speech-recognition",
            model=model_inst,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            max_new_tokens=128,
            torch_dtype=torch_dtype,
            device=device,
        )

        sample = PATH + "sample.wav"
        result = faster_whisper(sample)
        print(result["text"])
    except Exception as e:
        print(f"Error initializing faster whisper: {e}")
        faster_whisper = None


def init_models(model_name):
    import whisper
    from openai import OpenAI
    global model_inst, openai_client

    try:
        if USE_FASTER_WHISPER:
            print("Loading faster whisper model...")
            faster_whisper_init()
        else:
            print(f"Loading {model_name} model...")
            model_inst = whisper.load_model(model_name)

        # Confirmation sound
        play_startup_sound()
        print(f"{model_name} model loaded")

        # === OpenAI LLM API Key Check ===
        # The reminder feature uses OpenAI's GPT API to enterpret voice commands
        key = os.environ.get("OPENAI_API_KEY")
        
        if key is not None:
            openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        else:
            print(f"""OpenAI API key not found. This is requred for the optional 'reminder' feature, which allows you to set visually invasive popup reminders with plain english speech - reminders that you WILL NOT miss!
            {REMINDER_SETUP_INSTRUCTIONS}
            This is optional, and only necessarry if you wish to use the voice-promptable reminders feature.
            
            Note: 
                - OpenAI's GPT pricing is 'per word' (1 token ~= 0.75 words), and supremely cheap with GPT-4o-mini!
                - Rough cost: Roughly 75¢ for 500 reminder requests. As cheap as they come, with great code-execution (function calling/automation) performance.
            """)
    except Exception as e:
        print(f"Error initializing OpenAI: {e}")
        model_inst = None
        openai_client = None


def cleanup():
    """Clean up resources before exiting"""
    print("Cleaning up resources...")
    cancel_event.set()  # Signal all threads to terminate
    
    global recording_thread, transcribe_thread, overlay_thread
    
    # Stop recording if in progress
    update_state(recording=False, transcribing=False, reminding=False)
    
    # Wait for threads to terminate (with timeout)
    if recording_thread and recording_thread.is_alive():
        recording_thread.join(timeout=2.0)
    
    if transcribe_thread and transcribe_thread.is_alive():
        transcribe_thread.join(timeout=2.0)

    if overlay_thread and overlay_thread.is_alive():
        overlay_thread.join(timeout=2.0)
    
    # Close overlay if it exists
    if tkinter_loop and 'root' in globals():
        try:
            root.quit()
            root.destroy()
        except:
            pass
    
    print("Cleanup complete")


def reset_all_state():
    with app_lock:
        global Recording, Transcribing, Reminding
        Recording = False
        Transcribing = False
        Reminding = False
        cancel_event.clear()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Delete current wav files
    try:
        if os.path.exists("transcript.wav"):
            os.remove("transcript.wav")
    except Exception as e:
        print(f"Error deleting transcript.wav: {e}")

    # 1. Initialize hotkeys and overlay UI icon (mic image)
    try:

        # init pygame mixer inline
        pygame.mixer.init()
        
        # Start threads
        overlay_thread = threading.Thread(target=init_overlay, daemon=True)
        overlay_thread.start()
        
        # Initialize app state
        init_models(model_name)
    except Exception as e:
        print(f"Error during initialization: {e}")

    # 2. Transcribe Thread
    try:
        transcribe_thread = threading.Thread(target=transcribe_speech, daemon=True)
        transcribe_thread.start()
    except Exception as e:
        print(f"Error starting transcription thread: {e}")
    
    # 3. Monitor threads and log states periodically for error recovery
    try:
        monitor_thread = threading.Thread(target=thread_monitor, daemon=True)
        monitor_thread.start()
        print("Monitoring threads...")
    except Exception as e:
        print(f"Error starting monitor thread: {e}")

    # 4. Log states periodically
    try:
        state_logging_thread = threading.Thread(target=log_states_periodically, daemon=True)
        state_logging_thread.start()
        print("Logging states periodically...")
    except Exception as e:
        print(f"Error starting state logging thread: {e}")
    
    try:
        init_app_priority()
        
        # Register cleanup
        import atexit
        atexit.register(cleanup)
        
        # Print instructions
        print("\n=== Model is loaded! ===")

        # Initialize everything
        init_hotkey_listener()

        # Keep the main thread alive
        while True:
            time.sleep(0.5)  # Check more frequently 
            
    except KeyboardInterrupt:
        print("Exiting WhisperTyper...")
        cancel_event.set()
        cleanup()
    except Exception as e:
        print(f"Error in main: {e}")
        cancel_event.set()
        cleanup()