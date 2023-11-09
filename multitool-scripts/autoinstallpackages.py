import subprocess
import sys

# Function to install packages using pip
def install(package):
    try:
        # check if installed already for this version of python
        __import__(package)
        print("Package already installed: " + package)
    except ImportError:
        # install package
        subprocess.call([sys.executable, "-m", "pip", "install", package])
        print("Installed package: " + package)
    except:
        print("Failed to install package: " + package)

# Upgrade pip to the latest version
install("pip --upgrade")

# List of required packages
required_packages = [
    "codecs",
    "whisper",
    "time",
    "subprocess",
    "threading",
    "pyaudio",
    "wave",
    "winreg",
    "openai",
    "string",
    "shutil",
    "os",
    "subprocess",
    "pandas",
    "numpy",
    "pygetwindow",
    "pyautogui",
    "opencv-python",
    "pytesseract",
    "json",
    "warnings",
    "win32clipboard",
    "pyperclip",
    "fuzzywuzzy",
    "pynput",
    "playsound",
    "datetime",
    "PyQt5",
    "elevenlabslib"
]

# if main, run the install function
if __name__ == "__main__":
    for package in required_packages:
        install(package)