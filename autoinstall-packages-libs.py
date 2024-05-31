###############################################
import subprocess
import shlex
from subprocess import call
import sys


def install_and_import(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    except subprocess.CalledProcessError:
        print(f"Failed to install package {package}")
        sys.exit(1)


def install_ffmpeg():
    try:
        subprocess.run(["powershell", "Set-ExecutionPolicy", "Bypass", "-Scope", "Process", "-Force"], check=True)
        subprocess.run(["powershell", "iex", "((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))"], check=True)
        subprocess.run(["powershell", "choco", "install", "ffmpeg"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while installing FFmpeg: {e}")
        sys.exit(1)


# OG mein
# def run_script(script_name):
#     while True:
#         try:
#             with open(script_name) as f:
#                 code = compile(f.read(), script_name, 'exec')
#                 exec(code, globals())
#             break
#         except ImportError as e:
#             missing_package = str(e).split(" ")[-1].strip("'")
#             print(f"Installing missing package: {missing_package}")
#             install_and_import(missing_package)
#         except Exception as e:
#             # Check for FFmpeg related error
#             if 'ffmpeg' in str(e).lower():
#                 print("FFmpeg is required but not found. Installing FFmpeg...")
#                 install_ffmpeg()
#                 print("Retrying script execution...")
#                 continue  # Retry running the script after installing FFmpeg
#             else:
#                 raise


# Supports command-line args!
def run_script(command):
    parts = shlex.split(command)  # Use shlex to handle spaces in paths and arguments
    script_name = parts[0]
    args = parts[1:]  # Separate script name from the rest of the arguments
    
    sys.argv = [script_name] + args  # Set sys.argv for the script
    
    while True:
        try:
            with open(script_name) as f:
                code = compile(f.read(), script_name, 'exec')
                exec(code, globals())
            break
        except ImportError as e:
            missing_package = str(e).split(" ")[-1].strip("'")
            print(f"Installing missing package: {missing_package}")
            call([sys.executable, "-m", "pip", "install", missing_package])
        except Exception as e:
            print(e)
            break


if __name__ == "__main__":
    # using tkinter to open a file dialog
    install_and_import("tk")

    # import tkinter
    from tkinter import Tk
    from tkinter.filedialog import askopenfilename

    # open a file dialog
    Tk().withdraw()
    filename = askopenfilename()

    # Query for command line args
    if filename:
        # let user modify the command, and then continue the script when user presses enter
        print("Add arguments and/or press ENTER:")
        filename = f"{filename} "   # Add a space after the filename
        filename += input()         # Filename PLUS any additional arguments
        print(f"Running script:\n {filename}")

    run_script(filename)