import time
import sounddevice as sd
import threading

def is_microphone_in_use():
    # Check if microphone is in use by seeing if any stream is active
    return sd.Stream().active

def send_notification(action=None):
    if action is not None:
        action()
    
    #notification.notify(
    #    title='Reminder',
    #    message='This is your reminder!',
    #    app_icon=None,  # You can specify an icon here if you want
    #    timeout=10,  # Duration in seconds the notification is visible
    #)

def start_timer(action=None):
    INTERVAL = 30 * 60  # 30 minutes

    while True:
        time.sleep(INTERVAL)
        
        if not is_microphone_in_use():
            send_notification(action)

if __name__ == '__main__':
    # Create a thread for start_timer function
    timer_thread = threading.Thread(target=start_timer)
    
    # Start the thread
    timer_thread.start()

    # If you have other tasks to perform in main, you can add them here.
    # They will run in parallel with the start_timer function.
