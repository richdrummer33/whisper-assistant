#!/usr/bin/env python3
"""
Sentence Timestamper - Extract and timestamp sentences from audio and video files
Uses OpenAI's Whisper model to transcribe speech and generate timestamps
Exports results to TXT files with formatted timestamps
"""

# Built-in libraries
import os
import argparse
import time
import re
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

# External libraries
import torch
import whisper
import ffmpeg
import numpy as np
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_nonsilent
import tqdm

def format_timestamp(seconds):
    """Convert seconds to HH:MM:SS format"""
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def extract_audio(input_file, output_file):
    """Extract audio from video file if needed"""
    try:
        # Run ffmpeg to extract audio to a temporary WAV file
        (
            ffmpeg
            .input(input_file)
            .output(output_file, acodec='pcm_s16le', ar='16000', ac=1)
            .run(quiet=True, overwrite_output=True)
        )
        return True
    except ffmpeg.Error as e:
        print(f"Error extracting audio: {e.stderr.decode() if e.stderr else str(e)}")
        return False

def load_whisper_model(model_name="base"):
    """Load the Whisper model with appropriate device selection"""
    print(f"Loading Whisper model '{model_name}'...")
    
    # Check if CUDA is available
    if torch.cuda.is_available():
        device = "cuda"
        print(f"Using GPU: {torch.cuda.get_device_name(0)}")
    else:
        device = "cpu"
        print("Using CPU for inference (this may be slow)")
    
    # Load the model
    model = whisper.load_model(model_name, device=device)
    print(f"Model loaded successfully")
    return model

def split_into_sentences(text, words_with_timestamps):
    """Split transcription into sentences with start/end timestamps"""
    # Define sentence-ending punctuation
    sentence_endings = ['.', '!', '?', ':', ';']
    
    # Sort words by start time, just to be safe
    words_with_timestamps = sorted(words_with_timestamps, key=lambda x: x['start'])
    
    sentences = []
    current_sentence = ""
    current_words = []
    
    # Add a progress bar
    progress_bar = tqdm.tqdm(total=len(words_with_timestamps), desc="Building sentences", unit="word")
    
    for word_data in words_with_timestamps:
        word = word_data["word"]
        current_sentence += word
        current_words.append(word_data)
        
        # Check if this word ends with sentence-ending punctuation
        if any(word.rstrip().endswith(p) for p in sentence_endings):
            # Get start time from first word and end time from last word
            start_time = current_words[0]["start"]
            end_time = current_words[-1]["end"]
            
            sentences.append({
                "text": current_sentence.strip(),
                "start": start_time,
                "end": end_time
            })
            
            # Reset for next sentence
            current_sentence = ""
            current_words = []
        
        # Update progress bar
        progress_bar.update(1)
    
    # Add any remaining text as a sentence
    if current_words:
        start_time = current_words[0]["start"]
        end_time = current_words[-1]["end"]
        
        sentences.append({
            "text": current_sentence.strip(),
            "start": start_time,
            "end": end_time
        })
    
    # Close progress bar
    progress_bar.close()
    
    return sentences

def detect_silence(audio_file, min_silence_len=2000, silence_thresh=-40):
    """
    Detect silent regions in audio file
    
    Parameters:
    - audio_file: path to audio file
    - min_silence_len: minimum silence length in ms
    - silence_thresh: silence threshold in dB
    
    Returns:
    - List of non-silent chunks with start/end times
    """
    print(f"Analyzing audio for silent regions...")
    
    # Load the audio file
    audio = AudioSegment.from_file(audio_file)
    
    # Detect non-silent chunks
    non_silent_ranges = detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh
    )
    
    # Convert to a more usable format
    chunks = []
    for i, (start_ms, end_ms) in enumerate(non_silent_ranges):
        chunks.append({
            "index": i,
            "start_time": start_ms / 1000.0,  # Convert to seconds
            "end_time": end_ms / 1000.0       # Convert to seconds
        })
    
    print(f"Detected {len(chunks)} non-silent regions")
    return chunks, audio

def transcribe_with_progress(audio_file, model, chunks, full_audio, language=None):
    """
    Transcribe audio with progress bar, processing by silence chunks
    
    Parameters:
    - audio_file: path to audio file (used as fallback)
    - model: loaded Whisper model
    - chunks: list of audio chunks with timing info
    - full_audio: full AudioSegment object
    - language: optional language code
    
    Returns:
    - List of words with timing info
    """
    all_words = []
    
    # Create progress bar
    progress_bar = tqdm.tqdm(total=len(chunks), desc="Transcribing chunks", unit="chunk")
    
    # Process each chunk
    for chunk in chunks:
        # Extract this portion of audio
        chunk_audio = full_audio[int(chunk["start_time"]*1000):int(chunk["end_time"]*1000)]
        
        # Save to temporary file
        temp_file = f"temp_chunk_{chunk['index']}.wav"
        chunk_audio.export(temp_file, format="wav")
        
        try:
            # Set options for transcription
            options = {
                "word_timestamps": True,
            }
            if language:
                options["language"] = language
            
            # Transcribe this chunk
            result = model.transcribe(temp_file, **options)
            
            # Adjust word timestamps to be relative to the original audio
            if "segments" in result:
                for segment in result['segments']:
                    for word in segment['words']:
                        # Adjust start and end times
                        word['start'] += chunk["start_time"]
                        word['end'] += chunk["start_time"]
                        
                        # Add to all_words
                        all_words.append({
                            "word": word['word'],
                            "start": word['start'],
                            "end": word['end']
                        })
            
            # Clean up temporary file
            os.remove(temp_file)
            
        except Exception as e:
            print(f"\nError transcribing chunk {chunk['index']}: {e}")
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
        # Update progress bar
        progress_bar.update(1)
    
    # Close progress bar
    progress_bar.close()
    
    print(f"Transcription complete: {len(all_words)} words detected")
    return all_words

def transcribe_and_timestamp(audio_file, model, language=None):
    """
    Transcribe audio and extract sentence timestamps using silence detection
    for improved chunking and progress tracking
    """
    # First, detect silent regions to split audio into chunks
    chunks, full_audio = detect_silence(audio_file)
    
    # If no chunks were detected or only one, fall back to regular transcription
    if len(chunks) <= 1:
        print("No significant silent regions found. Processing as a single file...")
        
        # Set options for transcription
        options = {
            "word_timestamps": True,
        }
        if language:
            options["language"] = language
        
        # Show a fake progress bar for the single file
        print("Transcribing... (this may take a while for long files)")
        fake_progress = tqdm.tqdm(total=100, desc="Transcribing", unit="%")
        
        # Perform transcription
        result = model.transcribe(audio_file, **options)
        fake_progress.update(100)
        fake_progress.close()
        
        # Extract all words with their timestamps
        words_with_timestamps = []
        for segment in result["segments"]:
            for word in segment["words"]:
                words_with_timestamps.append({
                    "word": word["word"],
                    "start": word["start"],
                    "end": word["end"]
                })
    else:
        # Transcribe with the chunking approach to show progress
        words_with_timestamps = transcribe_with_progress(
            audio_file, model, chunks, full_audio, language
        )
    
    # Combine all the words into a single text
    all_text = " ".join([w["word"] for w in words_with_timestamps])
    
    # Split into sentences
    sentences = split_into_sentences(all_text, words_with_timestamps)
    
    return sentences

def export_to_txt(sentences, output_file):
    """Export sentences with timestamps to a text file"""
    # Create directory if it doesn't exist
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with open(output_file, 'w', encoding='utf-8') as f:
        for sentence in sentences:
            timestamp = format_timestamp(sentence["start"])
            f.write(f"[{timestamp}] {sentence['text']}\n")
    
    print(f"Timestamps exported to {output_file}")
    
    # Attempt to open the output directory for the user
    try:
        if os.name == 'nt':  # Windows
            os.startfile(os.path.dirname(os.path.abspath(output_file)))
        elif os.name == 'posix':  # macOS and Linux
            if os.path.exists('/usr/bin/open'):  # macOS
                os.system(f'open "{os.path.dirname(os.path.abspath(output_file))}"')
            else:  # Linux
                os.system(f'xdg-open "{os.path.dirname(os.path.abspath(output_file))}" &')
    except:
        # If opening the directory fails, just continue
        pass

def select_file():
    """Open a file dialog to select an input file"""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Set a reasonable window title and icon
    root.title("Select Audio/Video File")
    
    filetypes = (
        ("All supported files", "*.mp3 *.wav *.flac *.ogg *.mp4 *.mkv *.avi *.mov *.webm"),
        ("Audio files", "*.mp3 *.wav *.flac *.ogg"),
        ("Video files", "*.mp4 *.mkv *.avi *.mov *.webm"),
        ("All files", "*.*")
    )
    
    file_path = filedialog.askopenfilename(
        title="Select an audio or video file",
        filetypes=filetypes
    )
    
    root.destroy()
    return file_path

def select_output_file(default_filename):
    """Open a file dialog to select an output file"""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    
    # Set a reasonable window title
    root.title("Save Transcript File")
    
    filetypes = (
        ("Text files", "*.txt"),
        ("Markdown files", "*.md"),
        ("All files", "*.*")
    )
    
    file_path = filedialog.asksaveasfilename(
        title="Save transcript as",
        filetypes=filetypes,
        defaultextension=".txt",
        initialfile=os.path.basename(default_filename)
    )
    
    root.destroy()
    return file_path

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Extract and timestamp sentences from audio/video files")
    parser.add_argument("--input_file", help="Path to the audio or video file (optional, will open file dialog if not provided)")
    parser.add_argument("--model", default="base", choices=["tiny", "base", "small", "medium", "large"],
                      help="Whisper model to use (default: base)")
    parser.add_argument("--language", help="Language code (optional, auto-detected if not specified)")
    parser.add_argument("--output", help="Output file path (default: input filename with .txt extension)")
    parser.add_argument("--min_silence", type=int, default=2000, 
                      help="Minimum silence length in milliseconds for splitting audio (default: 2000)")
    parser.add_argument("--silence_thresh", type=int, default=-40, 
                      help="Silence threshold in dB (default: -40)")
    args = parser.parse_args()
    
    # If input file is not provided, open file dialog
    if args.input_file:
        input_file = args.input_file
    else:
        print("Please select an audio or video file...")
        input_file = select_file()
        
        # If user cancels the file dialog
        if not input_file:
            print("No file selected. Exiting.")
            return
    
    # Verify input file exists
    if not os.path.isfile(input_file):
        print(f"Error: Input file '{input_file}' not found")
        return
    
    # Determine output file path
    if args.output:
        output_file = args.output
    else:
        input_path = Path(input_file)
        default_output = str(input_path.with_suffix('.txt'))
        
        # Ask user if they want to specify output location
        print("Default output file:", default_output)
        choice = input("Do you want to specify a different output file? (y/n) [n]: ").strip().lower()
        
        if choice == 'y':
            print("Please select where to save the output file...")
            output_path = select_output_file(default_output)
            
            # If user cancels the save dialog
            if not output_path:
                print("No output location selected. Using default location.")
                output_file = default_output
            else:
                output_file = output_path
        else:
            output_file = default_output
    
    # Load the Whisper model
    model = load_whisper_model(args.model)
    
    # Extract audio if input is not an audio file
    input_ext = os.path.splitext(input_file)[1].lower()
    if input_ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv']:
        print("Extracting audio from video file...")
        temp_audio = "temp_audio.wav"
        if not extract_audio(input_file, temp_audio):
            print("Failed to extract audio. Please ensure ffmpeg is installed.")
            return
        audio_file = temp_audio
    else:
        audio_file = input_file
    
    try:
        # Print file info
        print(f"\nProcessing file: {input_file}")
        print(f"Model: {args.model}")
        if args.language:
            print(f"Language: {args.language}")
        print(f"Silence detection: {args.min_silence}ms at {args.silence_thresh}dB threshold")
        print(f"Output file: {output_file}")
        print("-" * 50)
        
        # Start a timer to track total processing time
        start_time = time.time()
        
        # Transcribe and timestamp
        sentences = transcribe_and_timestamp(audio_file, model, args.language)
        
        # Export to text file
        export_to_txt(sentences, output_file)
        
        # Calculate and display elapsed time
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)
        
        print("-" * 50)
        print(f"Successfully processed {input_file}")
        print(f"Found {len(sentences)} sentences")
        print(f"Processing time: {minutes} min {seconds} sec")
        print(f"Output saved to {output_file}")
        
    finally:
        # Clean up temporary files
        if input_ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv']:
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
                
        # Clean up any temporary chunk files that might be left
        for temp_file in os.listdir('.'):
            if temp_file.startswith('temp_chunk_') and temp_file.endswith('.wav'):
                try:
                    os.remove(temp_file)
                except:
                    pass

if __name__ == "__main__":
    main()
