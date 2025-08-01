# Simple CPU implementation of a speech-to-text tool using the whisper model

# Built-in libraries
# import socket
import time
import threading
import os
import json
import warnings
import torch
import traceback

# External libraries
import whisper
from fuzzywuzzy import fuzz
import simpleaudio as sa

# Audio processing libraries
# import librosa
# import numpy as np
# import soundfile as sf
from pydub import AudioSegment
from pydub.silence import split_on_silence, detect_nonsilent

class WhisperSpeechToText:
    """
    A class for speech-to-text conversion using OpenAI's Whisper model.
    
    Features:
    - Automatic silence detection and removal
    - Audio splitting at silence points for better transcription
    - Word-level timestamps
    - CUDA support for GPU acceleration
    """
    
    def __init__(self, model_name="small.en", use_cuda=None):
        """
        Initialize the WhisperSpeechToText class.
        
        Args:
            model_name (str): Whisper model to use. Options: tiny.en, base.en, small.en, medium.en, large
            use_cuda (bool): Whether to use CUDA if available. If None, auto-detect
        """
        self.model = None
        self.model_name = model_name
        self.model_lock = threading.Lock()
        self.audio_length_seconds = 0
        
        # Determine device
        if use_cuda is None:
            self.use_cuda = torch.cuda.is_available()
        else:
            self.use_cuda = use_cuda and torch.cuda.is_available()
        
        # Whisper prompt for context (currently unused but available)
        self.whisper_prompt = (
            "This audio is dialogue from \"Goodnight Universe,\" a narrative-driven video game featuring multiple characters.\n\n"
            "The captions must accurately represent spoken dialogue, maintaining correct spelling, punctuation, and formatting. "
            "Also, include explicit word(s) (very occasional and unlikely) - and the very occasional and unlikely emotional and vocal *expressions, like 'oof', 'aww', 'hmm', and *actions like [sigs], [laughs], [lauging], [singing], [growling].\n\n"
            "Just for context, main characters include:\n"
            "   - Narrator (an alien consciousness inhabiting a baby named Isaac, the player character, protagonist)\n"
            "   - Rebecca (Isaac's mother)\n"
            "   - Simon (Isaac's father)\n"
            "   - Cleo (Isaac's sister)\n"
            "   - Wendy (an employee at Aio Industries)\n"
            "   - Elliot Rant (CEO of Aio Industries, antagonist)\n"
            "   - Angus (Isaac's grandpa)\n"
            "   - Gilbert the Goat (a cartoon character appearing as a toy and vehicle)\n\n"
            "IMPORTANT: Do not add *ANYTHING* (context, words, names,etc) that is not in the audio, nor 'interpret' the dialogue. And if ever unsure, do your best to guess the word(s)."
        )
    
    def load_model(self):
        """Load the Whisper model."""
        print()

        if self.use_cuda:
            print(f"CUDA is available. Using GPU: {torch.cuda.get_device_name(0)}")
            device = "cuda"
        else:
            print("CUDA is not available. Using CPU.")
            device = "cpu"
        
        print(f"Loading {self.model_name} model...")
        self.model = whisper.load_model(self.model_name, device=device)
        print(f"{self.model_name} model loaded with {torch.cuda.get_device_name(0) if self.use_cuda else 'CPU'}")
        
        # Play confirmation sound if available
        self._play_sound("model_loaded.wav")
    
    def _play_sound(self, file_name):
        """
        Play a UI notification sound.
        
        Args:
            file_name (str): Path to the sound file
        """
        if not os.path.exists(file_name):
            print(f"Sound file {file_name} not found")
            return
        try:
            wave_obj = sa.WaveObject.from_wave_file(file_name)
            wave_obj.play()
        except Exception as e:
            print(f"Error playing sound {file_name}: {e}")
    
    def remove_silence(self, input_file, output_file="processed.wav", 
                      min_silence_len=560, silence_thresh=-40):
        """
        Remove silence from audio file using pydub.
        
        Args:
            input_file (str): Path to input audio file
            output_file (str): Path to save processed audio
            min_silence_len (int): Minimum silence length in milliseconds (560ms < 600ms whisper max-gap-length)
            silence_thresh (int): Silence threshold in dB
            
        Returns:
            str: Path to the output file
        """
        # Load the audio file
        audio = AudioSegment.from_file(input_file)
        
        # Split audio where silence is detected
        audio_chunks = split_on_silence(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh,
            keep_silence=100  # keep 100ms of silence at the beginning and end of each chunk
        )
        
        # Combine all audio chunks
        combined = AudioSegment.empty()
        for chunk in audio_chunks:
            combined += chunk
        
        # Export the result
        combined.export(output_file, format="wav")
        print(f"Removed silence and saved to {output_file}")
        
        return output_file
    
    def split_audio_on_silence(self, input_file, output_dir="split_audio", 
                              min_silence_len=560, silence_thresh=-40):
        """
        Split audio file at silence points while preserving timing information.
        
        Args:
            input_file (str): Path to input audio file
            output_dir (str): Directory to save split audio files
            min_silence_len (int): Minimum silence length in milliseconds
            silence_thresh (int): Silence threshold in dB
            
        Returns:
            list: List of dictionaries containing file_path, start_time, and end_time
        """
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Load the audio file
        audio = AudioSegment.from_file(input_file)
        
        # Detect non-silent chunks
        print(f"Detecting non-silent ranges with min_silence_len={min_silence_len}ms, silence_thresh={silence_thresh}dB")
        non_silent_ranges = detect_nonsilent(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh
        )
        
        # If no non-silent ranges found, return empty result
        if not non_silent_ranges:
            print("No non-silent ranges found in the audio")
            return []
        
        # Split and save each non-silent chunk
        result = []
        for i, (start_ms, end_ms) in enumerate(non_silent_ranges):
            chunk = audio[start_ms:end_ms]
            output_file = os.path.join(output_dir, f"chunk_{i:03d}.wav")
            chunk.export(output_file, format="wav")
            
            # Store timing information in seconds to match whisper's timestamp format
            result.append({
                "file_path": output_file,
                "start_time": start_ms / 1000.0,  # Convert to seconds
                "end_time": end_ms / 1000.0       # Convert to seconds
            })
        
        # Save timing information to JSON file
        timing_file = os.path.join(output_dir, "timing_info.json")
        with open(timing_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        print(f"Split audio into {len(result)} chunks and saved to {output_dir}")
        print(f"Timing information saved to {timing_file}")
        
        return result
    
    def transcribe_with_silence_removal(self, wav_file):
        """
        Transcribe audio after removing silence (legacy method).
        
        Args:
            wav_file (str): Path to WAV file
            
        Returns:
            dict: Dictionary containing transcription text and word timestamps
        """
        # Ensure model is loaded
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            
            # Remove silence from the audio file
            wav_nogaps = self.remove_silence(wav_file, "processed.wav")
            
            # Transcribe the audio
            result = self.model.transcribe(wav_nogaps, word_timestamps=True, no_speech_threshold=1.2)
            
            # Print words with timestamps for debugging
            try:
                for segment in result['segments']:
                    print(''.join(f"{word['word']}[{word['start']}/{word['end']}]" for word in segment['words']))
                    print()
            except Exception as e:
                print(f"No timestamps available: {e}")
            
            # Extract words with timestamps
            words = []
            if "segments" in result:
                for segment in result['segments']:
                    for word in segment['words']:
                        words.append({
                            "word": word['word'], 
                            "start": word['start'], 
                            "end": word['end']
                        })
            
            return {"text": result['text'], "words": words}
    
    def transcribe_with_split_silence(self, wav_file, min_silence_len=560, silence_thresh=-40):
        """
        Split audio on silence and transcribe each chunk while preserving timing information.
        
        Args:
            wav_file (str): Path to input WAV file
            min_silence_len (int): Minimum silence length in milliseconds
            silence_thresh (int): Silence threshold in dB
            
        Returns:
            dict: Dictionary containing transcription results with timing information
        """
        # Ensure model is loaded
        if self.model is None:
            print("Loading Whisper model...")
            self.load_model()
            if self.model is None:
                raise RuntimeError("Model not loaded. Call load_model() first.")
        
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            
            # Split the audio file at silence points
            output_dir = "split_audio"
            chunks_info = self.split_audio_on_silence(
                wav_file,
                output_dir=output_dir,
                min_silence_len=min_silence_len,
                silence_thresh=silence_thresh
            )
            
            if not chunks_info:
                print("No speech detected in the audio")
                return {"text": "", "words": [], "chunks": []}
            
            # Transcribe each chunk
            all_text = ""
            all_words = []
            chunk_results = []
            
            # Use lock to ensure thread safety when using the model
            with self.model_lock:
                try:
                    for chunk_info in chunks_info:
                        chunk_file = chunk_info["file_path"]
                        chunk_start = chunk_info["start_time"]
                        
                        if self.audio_length_seconds > 0:
                            progress = (chunk_start / self.audio_length_seconds) * 100
                        else:
                            progress = 0
                        print(f"Transcribing chunk: {chunk_file} (starts at {chunk_start:.2f}s | progress: {progress:.2f}%)")
                        
                        # Transcribe this chunk
                        result = self.model.transcribe(chunk_file, word_timestamps=True, no_speech_threshold=1.2)
                        
                        # Store the chunk result
                        chunk_text = result["text"].strip()
                        chunk_results.append({
                            "file_path": chunk_file,
                            "start_time": chunk_start,
                            "end_time": chunk_info["end_time"],
                            "text": chunk_text
                        })

                        # Print the chunk text
                        print(f"Chunk text: {chunk_text}")
                        
                        # Adjust word timestamps to be relative to the original audio
                        if "segments" in result:
                            for segment in result['segments']:
                                for word in segment['words']:
                                    # Adjust start and end times
                                    word['start'] += chunk_start
                                    word['end'] += chunk_start
                                    
                                    # Add to all_words
                                    all_words.append({
                                        "word": word['word'],
                                        "start": word['start'],
                                        "end": word['end']
                                    })
                                    
                                    # Print with adjusted timestamps
                                    print(f"{word['word']}[{word['start']:.2f}/{word['end']:.2f}]", end="")
                                print()  # Newline after each segment
                        
                        # Add this chunk's text to the overall text
                        all_text += " " + chunk_text
                        
                except Exception as e:
                    print(f"Error during transcription: {e}")
                    traceback.print_exc()
                    return {"text": "", "words": [], "chunks": []}
            
            # Construct the response with all information
            response = {
                "text": all_text.strip(),
                "words": all_words,
                "chunks": chunk_results
            }
            
            return response
    
    def transcribe(self, wav_file, method="split_silence", **kwargs):
        """
        Main transcription method with multiple approaches.
        
        Args:
            wav_file (str): Path to WAV file
            method (str): Transcription method ("split_silence" or "remove_silence")
            **kwargs: Additional arguments for the chosen method
            
        Returns:
            dict: Transcription results
        """
        if not kwargs:
            kwargs = {
                "min_silence_len": 560,
                "silence_thresh": -40
            }
            print(f"Using default values: {kwargs}")
        else:
            print(f"Using provided values: {kwargs}")

        # Try get the length (seconds) of the audio file
        try:
            audio = AudioSegment.from_file(wav_file)
            self.audio_length_seconds = len(audio) / 1000.0
            print(f"Audio length: {self.audio_length_seconds:.2f} seconds")
        except Exception as e:
            print(f"Error checking len of audio file: {e}")
        
        if method == "split_silence":
            return self.transcribe_with_split_silence(wav_file, **kwargs)
        elif method == "remove_silence":
            return self.transcribe_with_silence_removal(wav_file)
        else:
            raise ValueError(f"Unknown method: {method}. Use 'split_silence' or 'remove_silence'")


# Example usage
if __name__ == "__main__":
    # Ensure ffmpeg can be found - adds to path in this session
    os.environ["PATH"] += os.pathsep + os.path.abspath(".")
    
    # Create and use the class
    stt = WhisperSpeechToText(model_name="small.en")
    stt.load_model()
    
    # Play confirmation sound
    stt._play_sound("model_loaded.wav")
    
    # Transcribe audio
    result = stt.transcribe("test.wav", method="split_silence", 
                           min_silence_len=560, silence_thresh=-40)
    
    print("\nTranscription Results:")
    print(f"Text: {result['text']}")
    print(f"Number of words: {len(result['words'])}")
    print(f"Number of chunks: {len(result['chunks'])}")