# List of libraries to check
libraries = [
    "codecs", "whisper", "time", "threading", "pyaudio", "wave", 
    "winreg", "os", "sys", "string", "torch", "keyboard", "datetime",
    "PyQt5.QtMultimedia", "warnings"
]

# Function to check if a library is installed
def check_library(library):
    try:
        __import__(library)
        print(f"'{library}' is installed.")
    except ImportError:
        print(f"'{library}' is NOT installed.")

# Check each library in the list
for lib in libraries:
    check_library(lib)
