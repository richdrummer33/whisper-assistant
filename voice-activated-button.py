import sounddevice as sd
import pyautogui
import numpy as np
import time as Time

button_pressed = False  # Flag to keep track of button state
debounce_duration = 1.5  # Set your own debounce duration in seconds
last_time = 0  # To keep track of the last time the audio callback was triggered

def audio_callback(indata, frames, time, status):
    global button_pressed, last_time, debounce_duration
    volume_norm = np.linalg.norm(indata) * 10
    threshold = 10.0  # Set your own threshold
    current_time = Time.time()

    if volume_norm > threshold:
        debounce_duration = 1.0  # Reset the debounce duration
        if not button_pressed:
            pyautogui.keyDown('v')  # Replace 'space' with the key you want to press
            button_pressed = Truev
            print("Key pressed")
    elif debounce_duration > 0:
        # Decrement the debounce duration by the time since the last audio callback.
        debounce_duration -= current_time - last_time

    else:
        if button_pressed:
            pyautogui.keyUp('v')  # Replace 'space' with the key you want to release
            button_pressed = False
            print("Key released")

    last_time = current_time  # Update the last time the audio callback was triggered

# Set your device and channels
device_info = sd.query_devices(None, 'input')
sample_rate = int(device_info['default_samplerate'])

# Start streaming audio
with sd.InputStream(callback=audio_callback, channels=1, samplerate=sample_rate):
    print("Listening...")
    while True:
        pass
