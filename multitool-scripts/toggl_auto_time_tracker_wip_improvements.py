
##################################################################################
### [Improvements] https://claude.ai/chat/8fa2daac-d663-4ef3-8949-88bc7dd46aaa ###
##################################################################################

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
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("time_tracker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TimeTracker")

class TimeTracker:
    def __init__(self):
        # Constants
        self.INACTIVITY_THRESHOLD = 10 * 60  # 10 minutes
        self.EVENING_INACTIVITY_THRESHOLD = 20 * 60  # 20 minutes
        self.EVENING_HOUR = 19  # 7 PM
        self.KEYSTROKE_BUFFER_SIZE = 1000
        self.WORK_APP_CHECK_INTERVAL = 5  # Check active window every 5 seconds

        # Work keywords to monitor - expanded list based on requirements
        self.WORK_KEYWORDS = [
            "slack", "unity", "gnu", "goodnight universe", "unseen", "jira",
            # Add other work-related keywords if needed
        ]

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
        self.last_work_app_time = None
        self.in_work_app = False
        self.force_stop = False
        
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
        
        # Get projects
        try:
            projects = self.workspace.get_projects(self.workspace_id, active=True)
            
            # Find Unseen project
            unseen_project = next(
                (project for project in projects if project.name.lower() == "unseen"),
                None
            )
            self.unseen_project_id = unseen_project.id if unseen_project else None
            
            # Find GNU project
            gnu_project = next(
                (project for project in projects if project.name.lower() == "gnu" or 
                 "goodnight universe" in project.name.lower()),
                None
            )
            self.gnu_project_id = gnu_project.id if gnu_project else None
            
            if not self.unseen_project_id and not self.gnu_project_id:
                logger.warning("No work projects found. Tracking without project association.")
            else:
                logger.info(f"Found work projects: Unseen={self.unseen_project_id}, GNU={self.gnu_project_id}")
                
        except Exception as e:
            logger.error(f"Failed to fetch projects: {str(e)}")
            
        # Check if there's already a running time entry
        try:
            current_entry = self.user.get_current_time_entry()
            if current_entry:
                self.current_time_entry_id = current_entry.id
                self.timer_running = True
                logger.info(f"Found running time entry with ID: {self.current_time_entry_id}")
        except Exception as e:
            logger.error(f"Failed to check current time entry: {str(e)}")

    def start_listeners(self):
        """Start keyboard and mouse listeners"""
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)
        self.mouse_listener = mouse.Listener(on_click=self.on_mouse_click)
        
        self.keyboard_listener.start()
        self.mouse_listener.start()
        
        # Start a thread to check active window periodically
        self.app_check_thread = threading.Thread(target=self.check_active_app_loop, daemon=True)
        self.app_check_thread.start()

    def check_active_app_loop(self):
        """Periodically check if a work-related app is active"""
        while True:
            try:
                current_work_app_status = self.is_work_app_active()
                
                # Detect transitions between work and non-work apps
                if current_work_app_status and not self.in_work_app:
                    # Transitioning to work app
                    logger.info("Detected switch to work app")
                    self.in_work_app = True
                    self.last_work_app_time = time.time()
                    
                    # If timer not running, start it
                    if not self.timer_running and not self.force_stop:
                        self.start_timer()
                
                elif not current_work_app_status and self.in_work_app:
                    # Transitioning away from work app
                    logger.info("Detected switch away from work app")
                    self.in_work_app = False
                    
                    # We don't immediately stop the timer - inactivity checks will handle that
                
            except Exception as e:
                logger.error(f"Error in app check loop: {str(e)}")
            
            time.sleep(self.WORK_APP_CHECK_INTERVAL)

    def is_work_app_active(self):
        """Check if current window is a work app"""
        try:
            active_window = gw.getActiveWindow()
            if not active_window or not active_window.title:
                return False
                
            # Check if any work keyword is in the window title
            return any(keyword.lower() in active_window.title.lower() 
                      for keyword in self.WORK_KEYWORDS)
        except Exception as e:
            logger.error(f"Error checking active window: {str(e)}")
            return False

    def get_project_for_window(self):
        """Determine which project to use based on active window"""
        try:
            active_window = gw.getActiveWindow()
            if not active_window or not active_window.title:
                return self.unseen_project_id  # Default to Unseen
            
            # Check for GNU/Goodnight Universe
            if any(keyword.lower() in active_window.title.lower() 
                  for keyword in ["gnu", "goodnight universe"]):
                return self.gnu_project_id if self.gnu_project_id else self.unseen_project_id
            
            # Default to Unseen for other work apps
            return self.unseen_project_id
            
        except Exception as e:
            logger.error(f"Error determining project: {str(e)}")
            return self.unseen_project_id

    def check_phrase_match(self, text, phrases, threshold=85):
        """Check if text matches any phrase using fuzzy matching"""
        return any(fuzz.ratio(text.lower(), phrase.lower()) > threshold 
                  for phrase in phrases), text

    def start_timer(self, start_time=None):
        """Start Toggl timer"""
        if self.timer_running or self.force_stop:
            return
            
        if not start_time:
            start_time = datetime.datetime.now(datetime.timezone.utc)

        try:
            # Determine which project to use
            project_id = self.get_project_for_window()
            
            # Create time entry
            response = self.workspace.create_time_entry(
                workspace_id=self.workspace_id,
                start_datetime=start_time,
                created_with="TimeTracker",
                description="Work Session",
                project_id=project_id,
                duration=-1  # Add negative duration for running timer
            )
            
            self.current_time_entry_id = response.id
            self.timer_running = True
            self.force_stop = False
            logger.info(f"Timer started at {start_time.strftime('%H:%M:%S')} with project ID: {project_id}")
            
        except Exception as e:
            logger.error(f"Failed to start timer: {str(e)}")
            # Try to recover by checking current time entry
            try:
                current_entry = self.user.get_current_time_entry()
                if current_entry:
                    self.current_time_entry_id = current_entry.id
                    self.timer_running = True
                    logger.info(f"Recovered running time entry with ID: {self.current_time_entry_id}")
            except Exception as recovery_error:
                logger.error(f"Failed to recover timer state: {str(recovery_error)}")

    def stop_timer(self):
        """Stop current Toggl timer"""
        if not self.timer_running and not self.current_time_entry_id:
            logger.info("Local timer state not found, checking Toggl API...")
            try:
                current_timer = self.user.get_current_time_entry()
                if current_timer:
                    self.current_time_entry_id = current_timer.id
                    self.timer_running = True
                    logger.info(f"Found running timer with ID: {self.current_time_entry_id}")
                else:
                    logger.info("No running timer found!")
                    return
            except Exception as e:
                logger.error(f"Failed to check current timer: {str(e)}")
                return
            
        try:
            if self.current_time_entry_id:
                self.workspace.stop_time_entry(
                    workspace_id=self.workspace_id,
                    time_entry_id=self.current_time_entry_id
                )
                
                stop_time = datetime.datetime.now(datetime.timezone.utc)
                logger.info(f"Timer stopped at {stop_time.strftime('%H:%M:%S')}")
            else:
                logger.warning("No time entry ID found to stop")
                
            self.timer_running = False
            self.current_time_entry_id = None
            self.force_stop = True  # Prevent immediate restart
            
        except Exception as e:
            logger.error(f"Failed to stop timer: {str(e)}")
            # Try alternative approach - force sync with Toggl
            try:
                current_timers = self.user.get_time_entries(
                    workspace_id=self.workspace_id,
                    start_date=(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)),
                    end_date=datetime.datetime.now(datetime.timezone.utc)
                )
                
                for timer in current_timers:
                    if timer.duration is not None and timer.duration < 0:  # Running timer
                        logger.info(f"Found running timer {timer.id}, attempting to stop it")
                        self.workspace.stop_time_entry(
                            workspace_id=self.workspace_id,
                            time_entry_id=timer.id
                        )
                        logger.info(f"Successfully stopped timer {timer.id}")
                        break
                        
                self.timer_running = False
                self.current_time_entry_id = None
                
            except Exception as recovery_error:
                logger.error(f"Failed in recovery attempt to stop timer: {str(recovery_error)}")

    def on_key_press(self, key):
        """Handle keyboard events"""
        self.last_activity_time = time.time()
        
        # Process keystrokes in any application (not just Slack)
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

            # Process buffer on Enter if in a work-related app (expanded from just Slack)
            if key == keyboard.Key.enter and self.is_work_app_active():
                buffer_text = ''.join(self.keystroke_buffer)
                self.process_message(buffer_text)
                self.keystroke_buffer = []
                
        except Exception as e:
            logger.error(f"Error processing keystroke: {str(e)}")

    def on_mouse_click(self, x, y, button, pressed):
        """Handle mouse events"""
        if pressed:
            self.last_activity_time = time.time()
            
            # If returning from inactivity, note the time
            current_in_work_app = self.is_work_app_active()
            if (not self.timer_running and 
                current_in_work_app and 
                not self.return_activity_time and
                not self.force_stop):
                self.return_activity_time = time.time()
                logger.info("Activity detected after inactivity period")

    def process_message(self, message):
        """Process completed message"""
        # Manual start commands
        valid_phrase, matched_text = self.check_phrase_match(message, self.START_PHRASES)
        if valid_phrase:
            logger.info(f"Valid start phrase detected: {matched_text}")
            self.start_timer()
            return
            
        # Back after break commands
        valid_phrase, matched_text = self.check_phrase_match(message, self.BACK_PHRASES)
        if valid_phrase:
            logger.info(f"Valid back phrase detected: {matched_text}")
            if self.return_activity_time:
                self.start_timer(
                    datetime.datetime.fromtimestamp(self.return_activity_time, 
                                                 tz=datetime.timezone.utc)
                )
                self.return_activity_time = None
            else:
                self.start_timer()
            return
                
        # End of work commands
        valid_phrase, matched_text = self.check_phrase_match(message, self.END_PHRASES)
        if valid_phrase:
            logger.info(f"Valid end phrase detected: {matched_text}")
            self.stop_timer()
            return

    def check_inactivity(self):
        """Check for inactivity and manage timer accordingly"""
        try:
            current_time = time.time()
            inactivity_duration = current_time - self.last_activity_time
            
            # Use longer threshold after evening hour
            threshold = (self.EVENING_INACTIVITY_THRESHOLD 
                        if datetime.datetime.now().hour >= self.EVENING_HOUR 
                        else self.INACTIVITY_THRESHOLD)
            
            # Stop timer if:
            # 1. User has been inactive beyond threshold AND timer is running
            # 2. User has been away from work apps for longer than threshold AND timer is running
            if self.timer_running and (
                inactivity_duration > threshold or 
                (not self.in_work_app and 
                 self.last_work_app_time and 
                 current_time - self.last_work_app_time > threshold)
            ):
                reason = "general inactivity" if inactivity_duration > threshold else "away from work apps"
                logger.info(f"Stopping timer due to {reason}")
                self.stop_timer()
                
            # Start timer if:
            # User is in a work app, timer not running, and not forced to stop
            elif self.in_work_app and not self.timer_running and not self.force_stop:
                logger.info("User active in work app, starting timer")
                if self.return_activity_time:
                    self.start_timer(
                        datetime.datetime.fromtimestamp(self.return_activity_time, 
                                                     tz=datetime.timezone.utc)
                    )
                    self.return_activity_time = None
                else:
                    self.start_timer()
                    
        except Exception as e:
            logger.error(f"Error in inactivity check: {str(e)}")

    def sync_with_toggl(self):
        """Sync local state with Toggl API state"""
        try:
            current_entry = self.user.get_current_time_entry()
            
            # If Toggl has a running entry but we don't think we do
            if current_entry and not self.timer_running:
                self.current_time_entry_id = current_entry.id
                self.timer_running = True
                logger.info(f"Synced state: Found running entry {current_entry.id} on Toggl")
                
            # If we think we have a running entry but Toggl doesn't
            elif not current_entry and self.timer_running:
                logger.info("Synced state: No running entry on Toggl but local state thinks timer is running")
                self.timer_running = False
                self.current_time_entry_id = None
                
        except Exception as e:
            logger.error(f"Error syncing with Toggl: {str(e)}")

    def run(self):
        """Main loop"""
        try:
            logger.info("Starting time tracker... Press Ctrl+C to exit.")
            
            # Initial sync with Toggl
            self.sync_with_toggl()
            
            while True:
                # Check for inactivity
                self.check_inactivity()
                
                # Periodically sync with Toggl to ensure consistent state
                if time.time() % 300 < 1:  # Roughly every 5 minutes
                    self.sync_with_toggl()
                
                time.sleep(5)  # Check more frequently
                
        except KeyboardInterrupt:
            if self.timer_running:
                logger.info("Stopping timer before shutdown...")
                self.stop_timer()
            logger.info("Shutting down time tracker...")
            self.keyboard_listener.stop()
            self.mouse_listener.stop()

if __name__ == "__main__":
    tracker = TimeTracker()
    tracker.run()