# Simple CPU implementation of a speech-to-text tool using the whisper model

import whisper
import time
import threading
import os
from datetime import datetime
import simpleaudio as sa # from playsound import playsound
import keyboard as kb
import os
import socket
import yt_dlp
from fuzzywuzzy import fuzz
import json
import warnings
from openai import OpenAI
from mutagen.mp4 import MP4
import ffmpeg
import argparse  # Add this import

# My custom py's
from whisper_transcribe_base import WhisperSpeechToText

# Fields
model = None
model_name = "tiny"
file_ready_counter=0
stop_recording=False
is_recording=False
use_cuda = True

# If there is no folder called FrequencyFerryman in the Music/Playlists folder, create one, then download the rickroll song
playlist_path = os.path.join(os.path.expanduser(
    "~"), "Music", "Playlists", "yt-dl")
if not os.path.exists(playlist_path):
    os.makedirs(playlist_path)
    print("Created folder for playlist")
else:
    print("Folder 'yt-dl' for youtube audio already exists (for optional yt-dl feature)")


ydl_opts = {
    'extract_audio': True,
    'format': 'bestaudio',
    'outtmpl': f'{playlist_path}/%(title)s.%(ext)s',
    'postprocessors': [{  
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'wav',
        'preferredquality': '192',
    }],
}

warnings.filterwarnings("ignore", category=DeprecationWarning)  


def playsound(file_name):
    file_path = os.path.join(os.path.dirname(__file__), file_name)
    if not os.path.exists(file_path):
        print(f"File {file_name} not found")
        return
    wave_obj = sa.WaveObject.from_wave_file(file_path)
    wave_obj.play() # play_obj.wait_done()


def load_model(model_name):
    global model

    # Model selection -> (tiny base small medium large)
    print("loading model...")
    model = whisper.load_model(model_name)

    # Confirmation sound
    playsound("model_loaded.wav")                                 
    print(f"{model_name} model loaded")
    



# ==== TRANSCRIPTION ====
def transcribe_assemblyai(audio_file):
    """Transcribe audio using AssemblyAI"""
    import assemblyai as aai
    
    aai.settings.api_key = "0c18207ba41945eda37bb28ac6af7845"
    transcriber = aai.Transcriber()
    print("Transcribing...")
    
    transcript = transcriber.transcribe(audio_file)
    print("\nTranscription complete!")
    
    print(f"\nTranscript:\n{transcript.text}\n")
    print("Timestamped words:")
    for word in transcript.words:
        print(f"{word.text} [{word.start} - {word.end}]")

    # Add subtitles
    subtitled_file = add_subtitles(audio_file, transcript)
    print(f"Created subtitled file: {subtitled_file}")
        
    return transcript.text


# Main loop for transcribing speech
def transcribe_whisper(wav_file):

    while model is None:
        time.sleep(0.1)
        
    print("Transcribing!")
    result = model.transcribe(wav_file, word_timestamps=True)
    
    try:
        timestamps = result['segments'][0]['words'][0]['start']
        for segment in result['segments']:
            print(''.join(f"{word['word']}[{word['start']}/{word['end']}]" for word in segment['words']))
            print()
    except:
        print("No timestamps available")
    
    return result["text"]


def fuzzy_compare(text1, text2):
    return fuzz.ratio(text1, text2)

        
def handle_client(client_socket):
    while True:
        try:
            # Receive the request
            request_data = client_socket.recv(1024).decode('utf-8')
            if not request_data:
                break

            # Parse the JSON request
            request = json.loads(request_data)

            method = request.get("_method")
            params = request.get("_param")

            # Call the appropriate method
            if method == "transcribe":
                result = transcribe_whisper(params)

            elif method == "compare":
                try:
                    result = fuzzy_compare(params[0], params[1])
                except:
                    result = "Error comparing the strings. The data has this many elements: " + str(len(params)) + " whos content is: " + str(params)
            
            else:
                result = "Unknown method"

            # Send the result back to the client
            response = json.dumps({"result": result})
            print(f"Response: {response}")
            client_socket.send(response.encode('utf-8'))
        except:
            break

    client_socket.close()


def start_server(host='127.0.0.1', port=65432):
    # Check if available
    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).bind((host, port))
    except:
        print(f"Port {port} is already in use. Please try another port")
        return       
    # Start the server 
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(5)
    print(f"Server listening on {host}:{port}")

    while True:
        client_socket, addr = server.accept()
        print(f"Accepted connection from {addr}")
        client_handler = threading.Thread(target=handle_client, args=(client_socket,))
        client_handler.start()

def download_youtube_audio(link):
    with yt_dlp.YoutubeDL(ydl_opts) as DL:
        info_dict = DL.extract_info(link, download=True)
        DL.download(link)
        path_to_dl_file = os.path.join(playlist_path, info_dict['title'] + ".mp3")
        return path_to_dl_file


def open_ai_process():
    # get file "STAR_tREK_ADVENTURES_reference_doc.slide" and generate a modified summary
    return


def save_transcription(file_path, content):
    """Save transcription with proper Unicode handling"""
    try:
        # First attempt - UTF-8 with error handling
        with open(file_path + ".txt", "w", encoding='utf-8', errors='replace') as f:
            f.write(content)
    except Exception as e:
        print(f"First save attempt failed: {e}")
        try:
            # Second attempt - use a different encoding if needed
            with open(file_path + ".txt", "w", encoding='utf-16', errors='replace') as f:
                f.write(content)
        except Exception as e:
            print(f"Second save attempt failed: {e}")
            # Last resort - strip problematic characters
            cleaned_content = ''.join(char for char in content if ord(char) < 65536)
            with open(file_path + ".txt", "w", encoding='utf-8', errors='replace') as f:
                f.write(cleaned_content)
                print("Warning: Some special characters may have been removed from the output.")


# ==== CAPTIONING ====
def add_subtitles(m4a_file, transcript):
    srt = generate_srt(transcript)
    
    # Save SRT file separately
    srt_file = f"{os.path.splitext(m4a_file)[0]}.srt"
    with open(srt_file, 'w') as f:
        f.write(srt)
    print(f"Created SRT file: {srt_file}")
    
    output_file = f"{os.path.splitext(m4a_file)[0]}_subtitled.m4a"
    stream = ffmpeg.input(m4a_file)
    stream = ffmpeg.output(stream, output_file, metadata=f"title='{srt}'")
    ffmpeg.run(stream)
    return output_file

def generate_srt(transcript):
    srt_content = ""
    for i, word in enumerate(transcript.words, 1):
        start = format_timestamp(word.start)
        end = format_timestamp(word.end)
        srt_content += f"{i}\n{start} --> {end}\n{word.text}\n\n"
    return srt_content

def format_timestamp(ms):
    seconds = ms / 1000
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

def convert_to_m4a(input_file):
   output_file = f"{os.path.splitext(input_file)[0]}.m4a"
   os.system(f'ffmpeg -i "{input_file}" -c:a aac -b:a 256k "{output_file}"')
   return output_file

# ==========================================================
# ======== MAIN ========
# ==========================================================

# Modify main to accept command line arguments
def main():
    parser = argparse.ArgumentParser(description='Audio transcription tool')
    parser.add_argument('--file', type=str, help='Path to audio file to transcribe')
    parser.add_argument('--model', type=str, default='tiny', help='Model to use (tiny, base, small, medium, large)')
    parser.add_argument('--engine', type=str, default='whisper', choices=['whisper', 'assemblyai'], 
                       help='Transcription engine to use')
    args = parser.parse_args()

    # Ensure ffmpeg can be found
    os.environ["PATH"] += os.pathsep + os.path.abspath(".")
    model_name = None

    if args.file:
        file = args.file
        model_name = args.model
    else:
        # Original interactive code for manual selection
        print("Press: 'f' to transcribe a file | 'y' to transcribe a Youtube URL")
        user_choice = kb.read_key()
        
        if user_choice == "f":
            import tkinter as tk
            from tkinter.filedialog import askopenfilename
            root = tk.Tk()
            root.withdraw()
            file = askopenfilename()
            if not file:
                print("No file selected")
                root.destroy()
                return
            root.destroy()
        elif user_choice == "y":
            link = input("Enter the Youtube URL: ")
            file = download_youtube_audio(link)
        else:
            print("Invalid input. Please try again")
            return

    if model_name is None or model_name not in ["tiny", "base", "small", "medium", "large"]:
        model_name = "tiny"

    # Load the model
    # load_model(model_name)
    print(f"Loading {model_name} transcriber...")
    transcriber = WhisperSpeechToText(model_name, use_cuda)
    print(f"{model_name} transcriber loaded")
    playsound("model_loaded.wav")

    file_no_ext = file.rsplit(".", 1)[0]
    
    # Convert video files if needed
    if file.split(".")[-1] not in ["wav", "mp3", "m4a"]:
        print("Converting file to mp3...")
        file_as_mp3 = file_no_ext + ".mp3"
        os.system(f'ffmpeg -i "{file}" -vn -acodec libmp3lame "{file_as_mp3}"')
        print(f"File converted! Path: {file_as_mp3}")
        file = file_as_mp3

    # Choose transcription engine
    if args.file:
        engine = args.engine
    else:
        print("Press: 'a' for Whisper | 'b' for AssemblyAI")
        engine = 'whisper' if kb.read_key() == 'a' else 'assemblyai'

    # Transcribe based on selected engine
    if engine == 'whisper':
        print("Transcribing with Whisper...")
        result = transcriber.transcribe(file) # result = transcribe_whisper(file)
        result = result["text"]
    else:
        if file.split(".")[-1] in ["wav"]:
            print("Converting wav to m4a...")
            file = convert_to_m4a(file)
        print("Transcribing with AssemblyAI...")
        result = transcribe_assemblyai(file)
    
    # Save result
    # with open(file + ".txt", "w") as f: f.write(result.)
    save_transcription(file_no_ext, result)

    print(f"Transcription saved to {file}.txt")
    playsound("bell.wav")

if __name__ == "__main__":
    main()
