import whisper
import tkinter as tk
import tkinter.filedialog as filedialog
import threading
import time
import torch

device = "cuda"
if device == "cuda":
    torch.cuda.init()
print(f"Using device: {device}")

print("loading model...")
model_name = "base"
model = whisper.load_model(model_name)

_done = False
_raw_transcript = ""

def transcribe_and_save(file_path):
    global _done
    global _raw_transcript
    result = model.transcribe(file_path, verbose = False)
    result = result["text"].strip()
    return result


# windows dialogue to select the audio file
root = tk.Tk()
root.withdraw()
file_path = filedialog.askopenfilename()
root.destroy()

if not file_path:
    print("No file selected.")
    exit()

result = transcribe_and_save(file_path)
# Start the transcription process in a separate thread
#thread = threading.Thread(target=transcribe_and_save, args=(file_path,))
#thread.start()
#while not _done:
#    time.sleep(1)

print("Transcription complete.")
print("Transcript:\n\n" + result)

# create empty file 
file_name = file_path.split("/")[-1].split(".")[0]
text_path = f"C:/git/whisper-assistant/transcriptions/{file_name}.txt"

# create the .txt file in the transcriptions folder as a new file
open(text_path, "x")
# save the transcript to the newly created but empty .txt file
with open(text_path, "w") as f:
    f.write(result)

print(f"Transcript saved to {file_name}")