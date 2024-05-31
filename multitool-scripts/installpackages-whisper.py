import subprocess
import sys

# HOW TO USE:
#   1. run script in any conda environment
#   2. pick the py script you want to install packages for
#   3. let it run!

# Function to install packages using pip
def install(package):
    installed = True
    try:
        # check if installed already for this version of python
        __import__(package)
        print("Package already installed: " + package)
        installed = True
    except ImportError:
        # install package
        subprocess.call([sys.executable, "-m", "pip", "install", package])
        print("Installed package: " + package)
        installed = True
    except:
        print("Failed to install package: " + package)
        installed = False
    return installed
    

# Upgrade pip to the latest version
install("pip --upgrade")

# List of required packages
required_packages = [
    "pytorch",
    "codecs",
    "openai-whisper",
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

def install_all():
    install_success = True

    for package in required_packages:
        install_success = install(package)

    return install_success

# if main, run the install function
if __name__ == "__main__":
    install_success = False

    while install_success == False:
        install_success = install_all()
        if install_success == False:
            print("Failed to install all packages. Retrying...")
        else:
            print("All packages installed successfully!")