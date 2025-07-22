import time
import datetime
import os
import threading
from pynput import keyboard, mouse
import pygetwindow as gw
from thefuzz import fuzz
from toggl_python.auth import TokenAuth
from toggl_python.entities.user import CurrentUser
from toggl_python.entities.workspace import Workspace

class TimeTracker:
    def __init__(self):
        # Constants
        self.INACTIVITY_THRESHOLD = 20 * 60  # 20 minutes
        self.EVENING_INACTIVITY_THRESHOLD = 60 * 60  # 1 hour
        self.EVENING_HOUR = 19  # 7 PM
        self.KEYSTROKE_BUFFER_SIZE = 1000
        
        # Work apps to monitor
        self.WORK_APPS = ["slack", "unity"]
        
        # Phrases to match
        self.START_PHRASES = ["starting up", "morning", "morning all"]
        self.BACK_PHRASES = ["bac", "back"]
        self.END_PHRASES = ["done for the day", "i'm out", "im out", "heading out", 
                          "calling it", "see you tomorrow", "cya tomorrow", "break", "taking break"]
        
        # State tracking
        self.keystroke_buffer = []
        self.timer_running = False
        self.last_activity_time = time.time()
        self.return_activity_time = None
        self.current_time_entry_id = None
        
        # Toggl setup
        self.setup_toggl()
        
        # Start listeners
        self.start_listeners()


    def setup_toggl(self):
        """Initialize Toggl API connection"""
        api_key = os.environ.get("TOGGL_API_KEY")
        if not api_key:
            raise ValueError("TOGGL_API_KEY environment variable not set")
            
        self.auth = TokenAuth(token=api_key)
        self.user = CurrentUser(auth=self.auth)
        
        # Get user info and setup workspace
        user_data = self.user.me()
        self.workspace_id = user_data.default_workspace_id
        self.workspace = Workspace(auth=self.auth)
        
        # Get Unseen project ID
        try:
            projects = self.workspace.get_projects(self.workspace_id, active=True)
            unseen_project = next(
                (project for project in projects if project.name.lower() == "unseen"),
                None
            )
            self.unseen_project_id = unseen_project.id if unseen_project else None
            if not self.unseen_project_id:
                print("Warning: 'Unseen' project not found")
            else:
                print(f"Found Unseen project with ID: {self.unseen_project_id}")
        except Exception as e:
            print(f"Failed to fetch projects: {str(e)}")

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
                  for phrase in phrases), text

    def start_timer(self, start_time=None):
        """Start Toggl timer"""
        if self.timer_running:
            return
            
        if not start_time:
            start_time = datetime.datetime.now(datetime.timezone.utc)

        try:
            # Calculate duration in seconds from start time to now
            response = self.workspace.create_time_entry(
                workspace_id=self.workspace_id,
                start_datetime=start_time,
                created_with="TimeTracker",
                description="Work Session",
                project_id=self.unseen_project_id if hasattr(self, 'unseen_project_id') else None,
                duration=-1  # Add negative duration for running timer
            )
            
            self.current_time_entry_id = response.id
            self.timer_running = True
            print(f"Timer started at {start_time.strftime('%H:%M:%S')}")
            print(f"Response: {response}")
        except Exception as e:
            print(f"Failed to start timer: {str(e)}")

    def stop_timer(self):
        """Stop current Toggl timer"""
        if not self.timer_running or not self.current_time_entry_id:
            print("Local timer state not found, checking Toggl API...")
            try:
                current_timer = self.user.get_current_time_entry()
                if current_timer:
                    self.current_time_entry_id = current_timer.id
                    self.timer_running = True
                else:
                    print("No running timer found!")
                    return
            except Exception as e:
                print(f"Failed to check current timer: {str(e)}")
                return
            
        try:
            self.workspace.stop_time_entry(
                workspace_id=self.workspace_id,
                time_entry_id=self.current_time_entry_id
            )
            
            stop_time = datetime.datetime.now(datetime.timezone.utc)
            print(f"Timer stopped at {stop_time.strftime('%H:%M:%S')}")
            self.timer_running = False
            self.current_time_entry_id = None
        except Exception as e:
            print(f"Failed to stop timer: {str(e)}")

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
                try: 
                    self.keystroke_buffer.clear()
                except AttributeError: 
                    self.keystroke_buffer = []
                
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
        valid_phrase, message = self.check_phrase_match(message, self.START_PHRASES)
        if valid_phrase:
            print(f"Valid keyphrase: {message} - starting timer...")
            self.start_timer()
            
        valid_phrase, message = self.check_phrase_match(message, self.BACK_PHRASES)
        if valid_phrase:
            print(f"Valid keyphrase: {message} - starting timer...")
            if self.return_activity_time:
                self.start_timer(
                    datetime.datetime.fromtimestamp(self.return_activity_time, 
                                                  tz=datetime.timezone.utc)
                )
                self.return_activity_time = None
                
        valid_phrase, message = self.check_phrase_match(message, self.END_PHRASES)
        if valid_phrase:
            print(f"Valid keyphrase: {message} - stopping timer...")
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
            print("Starting time tracker... Press Ctrl+C to exit.")
            while True:
                self.check_inactivity()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            if self.timer_running:
                print("Stopping timer...")
                self.stop_timer()
            print("Shutting down time tracker...")
            self.keyboard_listener.stop()
            self.mouse_listener.stop()

if __name__ == "__main__":
    tracker = TimeTracker()
    tracker.run()

# import time
# import datetime
# import os
# import threading
# from pynput import keyboard, mouse
# import pygetwindow as gw
# import requests
# from thefuzz import fuzz
# from toggl.TogglPy import Toggl
# 
# class TimeTracker:
#     def __init__(self):
#         # Constants
#         self.INACTIVITY_THRESHOLD = 20 * 60  # 20 minutes
#         self.EVENING_INACTIVITY_THRESHOLD = 60 * 60  # 1 hour
#         self.EVENING_HOUR = 19  # 7 PM
#         self.KEYSTROKE_BUFFER_SIZE = 1000
#         
#         # Work apps to monitor
#         self.WORK_APPS = ["slack", "unity"]
#         
#         # Phrases to match
#         self.START_PHRASES = ["starting up", "morning", "morning all"]
#         self.BACK_PHRASES = ["bac", "back"]
#         self.END_PHRASES = ["done for the day", "i'm out", "im out", "heading out", 
#                           "calling it", "see you tomorrow", "cya tomorrow"]
#         
#         # State tracking
#         self.keystroke_buffer = []
#         self.timer_running = False
#         self.last_activity_time = time.time()
#         self.return_activity_time = None
#         
#         # Toggl setup
#         self.setup_toggl()
#         
#         # Start listeners
#         self.start_listeners()
# 
#     def setup_toggl(self):
#         """Initialize Toggl API connection"""
#         api_key = os.environ.get("TOGGL_API_KEY")
#         if not api_key:
#             raise ValueError("TOGGL_API_KEY environment variable not set")
#             
#         self.toggl = Toggl()
#         self.toggl.setAPIKey(api_key)
#         
#         # Set workspace ID
#         self.workspace_id = 4149584
#         
#         # Verify connection
#         self.toggl.request("https://api.track.toggl.com/api/v9/me")
# 
#     def start_listeners(self):
#         """Start keyboard and mouse listeners"""
#         self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
#         self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
#         
#         self.keyboard_listener.start()
#         self.mouse_listener.start()
# 
#     def is_work_app_active(self):
#         """Check if current window is a work app"""
#         active_window = gw.getActiveWindow()
#         if not active_window:
#             return False
#             
#         return any(app.lower() in active_window.title.lower() 
#                   for app in self.WORK_APPS)
# 
#     def check_phrase_match(self, text, phrases, threshold=85):
#         """Check if text matches any phrase using fuzzy matching"""
#         return any(fuzz.ratio(text.lower(), phrase.lower()) > threshold 
#                   for phrase in phrases), text
# 
#     def start_timer(self, start_time=None):
#         """Start Toggl timer"""
#         if self.timer_running:
#             return
#             
#         if not start_time:
#             start_time = datetime.datetime.utcnow()
# 
#         data = {
#             "description": "Work Session",
#             "created_with": "TimeTracker",
#             "wid": self.workspace_id,
#             "start": start_time.isoformat(),
#             "duration": -1
#         }
#         
#         response = self.toggl.startTimeEntry(data)
#         
#         if response is not None:
#             self.timer_running = True
#             print(f"Timer started at {start_time.strftime('%H:%M:%S')}")
#         else:
#             print("Failed to start timer!")
# 
#     def stop_timer(self):
#         """Stop current Toggl timer"""
#         if not self.timer_running:
#             return
#             
#         current_timer = self.toggl.currentRunningTimeEntry()
#         if current_timer:
#             entry_id = current_timer['id']
#             self.toggl.stopTimeEntry(entry_id)
#             
#             stop_time = datetime.datetime.utcnow()
#             print(f"Timer stopped at {stop_time.strftime('%H:%M:%S')}")
#             self.timer_running = False
#         else:
#             print("No running timer found!")
# 
#     def on_key_press(self, key):
#         """Handle keyboard events"""
#         self.last_activity_time = time.time()
#         
#         # Only process keystrokes in Slack
#         if not self.is_work_app_active() or "slack" not in gw.getActiveWindow().title.lower():
#             return
# 
#         # Add character to buffer
#         try:
#             if hasattr(key, 'char') and key.char:
#                 self.keystroke_buffer.append(key.char)
#             elif key == keyboard.Key.space:
#                 self.keystroke_buffer.append(' ')
#             elif key == keyboard.Key.backspace and self.keystroke_buffer:
#                 self.keystroke_buffer.pop()
#                 
#             # Trim buffer if too long
#             if len(self.keystroke_buffer) > self.KEYSTROKE_BUFFER_SIZE:
#                 self.keystroke_buffer = self.keystroke_buffer[-self.KEYSTROKE_BUFFER_SIZE:]
# 
#             # Process buffer on Enter
#             if key == keyboard.Key.enter:
#                 buffer_text = ''.join(self.keystroke_buffer)
#                 self.process_message(buffer_text)
#                 try: 
#                     self.keystroke_buffer.clear()
#                 except AttributeError: 
#                     self.keystroke_buffer = []
#                 
#         except AttributeError:
#             pass
# 
#     def on_mouse_click(self, x, y, button, pressed):
#         """Handle mouse events"""
#         if pressed:
#             self.last_activity_time = time.time()
#             
#             # If returning from inactivity, note the time
#             if (not self.timer_running and 
#                 self.is_work_app_active() and 
#                 not self.return_activity_time):
#                 self.return_activity_time = time.time()
# 
#     def process_message(self, message):
#         """Process completed Slack message"""
#         valid_phrase, message = self.check_phrase_match(message, self.START_PHRASES)
#         if valid_phrase:
#             print(f"Valid keyphrase: {message} - starting timer...")
#             self.start_timer()
#             
#         valid_phrase, message = self.check_phrase_match(message, self.BACK_PHRASES)
#         if valid_phrase:
#             print(f"Valid keyphrase: {message} - starting timer...")
#             if self.return_activity_time:
#                 self.start_timer(
#                     datetime.datetime.fromtimestamp(self.return_activity_time)
#                 )
#                 self.return_activity_time = None
#                 
#         valid_phrase, message = self.check_phrase_match(message, self.END_PHRASES)
#         if valid_phrase:
#             print(f"Valid keyphrase: {message} - stopping timer...")
#             self.stop_timer()
# 
#     def check_inactivity(self):
#         """Check for inactivity and manage timer accordingly"""
#         current_time = time.time()
#         inactivity_duration = current_time - self.last_activity_time
#         
#         # Use longer threshold after evening hour
#         threshold = (self.EVENING_INACTIVITY_THRESHOLD 
#                     if datetime.datetime.now().hour >= self.EVENING_HOUR 
#                     else self.INACTIVITY_THRESHOLD)
#         
#         if inactivity_duration > threshold and self.timer_running:
#             print(f"Inactivity detected for {inactivity_duration} seconds - stopping timer...")
#             self.stop_timer()
# 
#     def run(self):
#         """Main loop"""
#         try:
#             print("Starting time tracker... Press Ctrl+C to exit.")
#             while True:
#                 self.check_inactivity()
#                 time.sleep(60)  # Check every minute
#                 
#         except KeyboardInterrupt:
#             if self.timer_running:
#                 print("Stopping timer...")
#                 self.stop_timer()
#             print("Shutting down time tracker...")
#             self.keyboard_listener.stop()
#             self.mouse_listener.stop()
# 
# if __name__ == "__main__":
#     tracker = TimeTracker()
#     tracker.run()