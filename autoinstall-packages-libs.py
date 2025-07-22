import subprocess
import shlex
import sys
import re


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


def get_imports(script_name):
    imports = []
    with open(script_name) as f:
        for line in f:
            match = re.match(r'^\s*(?:import|from)\s+(\S+)', line)
            if match:
                package = match.group(1).split('.')[0]
                imports.append(package)
    return imports


def install_missing_packages(script_name):
    imports = get_imports(script_name)
    for package in imports:
        try:
            __import__(package)
        except ImportError:
            print(f"Installing missing package: {package}")
            install_and_import(package)


def run_script(command):
    parts = shlex.split(command)
    script_name = parts[0]
    args = parts[1:]

    sys.argv = [script_name] + args

    install_missing_packages(script_name)

    while True:
        try:
            with open(script_name) as f:
                code = compile(f.read(), script_name, 'exec')
                exec(code, globals())
            break
        except ImportError as e:
            missing_package = str(e).split(" ")[-1].strip("'")
            print(f"Installing missing package: {missing_package}")
            install_and_import(missing_package)
        except Exception as e:
            if 'ffmpeg' in str(e).lower():
                print("FFmpeg is required but not found. Installing FFmpeg...")
                install_ffmpeg()
                print("Retrying script execution...")
                continue
            else:
                raise


if __name__ == "__main__":
    install_and_import("tk")

    from tkinter import Tk
    from tkinter.filedialog import askopenfilename

    Tk().withdraw()
    filename = askopenfilename()

    # if filename:
    #     print("Add arguments and/or press ENTER:")
    #     filename = f"{filename} "
    #     filename += input()
    #     print(f"Running script:\n {filename}")

    run_script(filename)
