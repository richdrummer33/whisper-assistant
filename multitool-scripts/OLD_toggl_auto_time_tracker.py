import time
import datetime
import os
import threading
from pynput import keyboard, mouse
import pygetwindow as gw
import requests
from thefuzz import fuzz
from toggl.api_client import TogglClientApi
import json
# Requests approach v9 api: https://engineering.toggl.com/docs/api/time_entry/index.html
import requests
from base64 import b64encode

class TimeTracker:
    def __init__(self):
        # Constants
        self.INACTIVITY_THRESHOLD = 20 * 60  # 20 minutes
        self.EVENING_INACTIVITY_THRESHOLD = 60 * 60  # 1 hour
        self.EVENING_HOUR = 19  # 7 PM
        self.KEYSTROKE_BUFFER_SIZE = 50
        
        # Work apps to monitor
        self.WORK_APPS = ["slack", "unity"]
        
        # Phrases to match
        self.START_PHRASES = ["starting up", "morning", "morning all"]
        self.BACK_PHRASES = ["bac", "back"]
        self.END_PHRASES = ["done for the day", "i'm out", "im out", "heading out", 
                          "calling it", "see you tomorrow", "cya tomorrow", "break", "break 🌴"]
        
        # State tracking
        self.keystroke_buffer = []
        self.timer_running = False
        self.last_activity_time = time.time()
        self.return_activity_time = None
        self.workspace_id = 4149584
        
        # Toggl setup
        self.setup_toggl()
        
        # Start listeners
        self.start_listeners()

    def setup_toggl(self):
        """Initialize Toggl API connection"""
        api_key = os.environ.get("TOGGL_API_KEY")
        if not api_key:
            raise ValueError("TOGGL_API_KEY environment variable not set")

        # Config for Toggl API
        self.toggl = TogglClientApi({
            "token": api_key,
            "user_agent": "Toggl Automater",
            "workspace_id": self.workspace_id  # Workspace ID for the user
        })

    def start_listeners(self):
        """Start keyboard and mouse listeners"""
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def is_work_app_active(self):
        """Check if current window is a work app"""
        active_window = gw.getActiveWindow()
        if not active_window:
            return False
            
        return any(app.lower() in active_window.title.lower() 
                  for app in self.WORK_APPS)

    def check_phrase_match(self, text, phrases, threshold=85):
        """Check if text matches any phrase using fuzzy matching"""
        return any(fuzz.ratio(text.lower(), phrase.lower()) > threshold 
                  for phrase in phrases)

    def start_timer(self, start_time=None):
        """Start Toggl timer"""
        if self.timer_running:
            return
            
        if not start_time:
            start_time = datetime.datetime.utcnow()

        # Modified time entry structure for v9 API
        time_entry = {
            "description": "Work Session",
            "duration": -1,
            "start": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),  # Formatted timestamp
            "pid": 176371721,
            "created_with": "Toggl Automater",
            "workspace_id": 4149584,  # Adding workspace_id explicitly
            "method": "START"
        }
        
        try:
            response = self.toggl.query(
                "/time_entries",
                method="POST",
                json_data=time_entry
            )
            if response.status_code == 200:
                self.timer_running = True
                print(f"Timer started at {start_time.strftime('%H:%M:%S')}")
            else:
                print(f"Failed to start timer. Status: {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error starting timer: {str(e)}")

    def stop_timer(self):
        """Stop current Toggl timer"""
        if not self.timer_running:
            print("No timer is currently running.")
            return

        try:
            # Fetch the current running time entry
            response = self.toggl.query(
                "/me/time_entries/current",  # API v9 endpoint
                method="GET"
            )

            if response.status_code != 200:
                print(f"Failed to get current timer. Status: {response.status_code}")
                print(f"Response: {response.text}")
                return

            current_entry = response.json()
            if not current_entry or 'id' not in current_entry:
                print("No active timer found.")
                self.timer_running = False
                return

            # Stop the timer using API v9 endpoint
            entry_id = current_entry["id"]
            stop_response = self.toggl.query(
                f"/workspaces/{self.workspace_id}/time_entries/{entry_id}/stop",
                method="PATCH",
                json_data={}  # Explicit empty payload (convention may be required)
            )
            
            if stop_response.ok:
                self.timer_running = False
                stop_time = datetime.datetime.utcnow()
                print(f"Timer stopped at {stop_time.strftime('%H:%M:%S')}")

            else:
                # Try the requests approach
                try:
                    # THIS:
                    # Set your credentials
                    email = "richdrummer33@gmail.com"
                    password = "<password>"
                    workspace_id = 4149584  # Your workspace ID
                    time_entry_id = 3708566934  # Replace with the actual running time entry ID

                    # Encode credentials
                    auth_header = b64encode(f"{email}:{password}".encode("ascii")).decode("ascii")

                    # Send PATCH request to stop the timer
                    url = f"https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/time_entries/{time_entry_id}/stop"
                    headers = {
                        "Authorization": f"Basic {auth_header}",
                        "Content-Type": "application/json"
                    }   
                    response = requests.patch(url, headers=headers)

                    # OR:
                    print("Testing to see if requests approach works")
                    data = requests.put('https://api.track.toggl.com/api/v9/workspaces/{workspace_id}/time_entries/{time_entry_id}', 
                                        json='{"billable":"boolean","created_with":"string","description":"string","duration":"integer","duronly":"boolean","pid":"integer","project_id":"integer","start":"string","start_date":"string","stop":"string","tag_action":"string","task_id":"integer","tid":"integer","uid":"Ideally we want object_id type fields, so yeah, those here are for that and proper field as priority, hence if that set, we use that","user_id":"integer","wid":"integer","workspace_id":"integer"}', 
                                        headers={'content-type': 'application/json', 
                                                'Authorization' : 'Basic %s' %  b64encode(b"<email>:<password>").decode("ascii")})
                    print("Requests response:" + data.json())

                except Exception as e:
                    print(f"Failed to stop timer. Code: {stop_response.status_code} | Status: {stop_response.raise_for_status()} | Reason: {stop_response.reason}")
                    print(f"Response: {stop_response.text}")   

                stop_response.raise_for_status()
                print(f"Failed to stop timer. Code: {stop_response.status_code} | Status: {stop_response.raise_for_status()} | Reason: {stop_response.reason}")
                print(f"Response: {stop_response.text}")

        except Exception as e:
            print(f"Error stopping timer: {str(e)}")
            self.timer_running = False



    def on_key_press(self, key):
        """Handle keyboard events"""
        self.last_activity_time = time.time()
        
        # Only process keystrokes in Slack
        if not self.is_work_app_active() or "slack" not in gw.getActiveWindow().title.lower():
            return

        # Add character to buffer
        try:
            if hasattr(key, 'char') and key.char:
                self.keystroke_buffer.append(key.char)
            elif key == keyboard.Key.space:
                self.keystroke_buffer.append(' ')
            elif key == keyboard.Key.backspace and self.keystroke_buffer:
                self.keystroke_buffer.pop()
                
            # Trim buffer if too long
            if len(self.keystroke_buffer) > self.KEYSTROKE_BUFFER_SIZE:
                self.keystroke_buffer = self.keystroke_buffer[-self.KEYSTROKE_BUFFER_SIZE:]

            # Process buffer on Enter
            if key == keyboard.Key.enter:
                buffer_text = ''.join(self.keystroke_buffer)
                self.process_message(buffer_text)
                self.keystroke_buffer.clear()
                
        except AttributeError:
            pass

    def on_mouse_click(self, x, y, button, pressed):
        """Handle mouse events"""
        if pressed:
            self.last_activity_time = time.time()
            
            # If returning from inactivity, note the time
            if (not self.timer_running and 
                self.is_work_app_active() and 
                not self.return_activity_time):
                self.return_activity_time = time.time()

    def process_message(self, message):
        """Process completed Slack message"""
        if self.check_phrase_match(message, self.START_PHRASES):
            print("Starting timer...")
            self.start_timer()
            
        elif self.check_phrase_match(message, self.BACK_PHRASES):
            print("Resuming timer... returned from break.")
            if self.return_activity_time:
                self.start_timer(
                    datetime.datetime.fromtimestamp(self.return_activity_time)
                )
                self.return_activity_time = None
                
        elif self.check_phrase_match(message, self.END_PHRASES):
            print("Stopping timer...")
            self.stop_timer()

    def check_inactivity(self):
        """Check for inactivity and manage timer accordingly"""
        current_time = time.time()
        inactivity_duration = current_time - self.last_activity_time
        
        # Use longer threshold after evening hour
        threshold = (self.EVENING_INACTIVITY_THRESHOLD 
                    if datetime.datetime.now().hour >= self.EVENING_HOUR 
                    else self.INACTIVITY_THRESHOLD)
        
        if inactivity_duration > threshold and self.timer_running:
            print(f"Inactivity detected for {inactivity_duration} seconds - stopping timer...")
            self.stop_timer()

    def run(self):
        """Main loop"""
        try:
            while True:
                self.check_inactivity()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            if self.timer_running:
                print("Stopping timer...")
                self.stop_timer()
            self.keyboard_listener.stop()
            self.mouse_listener.stop()

if __name__ == "__main__":
    tracker = TimeTracker()
    tracker.run()