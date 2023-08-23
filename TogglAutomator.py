import time
import datetime
import requests
import threading
import os
import GitStatusChecker as git_checker
from pytz import timezone

####################################################################################
# Features: 
#
# Starts/stops timers at start and end of day based on keyword in typed messages
# Starts/stops timers when user goes on break using KEYWORDS in typed message
# Automatically stops timer after 20 minutes of inactivity (accounts for inactivity time in timer duration) 
# Automatically starts timer when user returns from break
#
# Usage notes:
# API key can be found here: https://track.toggl.com/profile
# 
# To set your API key for this script:
# 1. Open the start menu and search for "environment variables", and open "Edit the system environment variables"
# 3. Click "Environment Variables" in the bottom right of the window
# 4. Under "User Variables", click "New"
# 5. Enter "TOGGL_API_KEY" for the name and your API key for the value
#
# TODO:
#   - Mic activity detection
#   - Total work time
#   - End of day time estimation
#   - Better message context detection (e.g. if user types "break" in a sentence, but it's not a break message)
#
####################################################################################

# >>>>>> USER-VARIABLES >>>>>> #
# apps that you use for work - interacting with these - IF their window names contain _project_title in them - means you are working
_work_apps = ["slack", "unity", "visual studio", "code"]    
# work comms app - if this is the window. Keywords (e.g. break, end of day) are only filtered/checked in this one app.
_work_comms_app = "slack"
 # the title of the project you are working on (e.g. your slack team name, or discord server name, visual studio project name, etc.)
_project_title = "unseen"                                  
# phrases that mean "end of day" - if these are typed in slack (or chosen app), the timer will stop and the monitor will stop until next day
_eod_phrases = ["I'm out", "Im out", "done for the day", "wrapping up", "cya tomorrow", "see y'all", "catch y'all", "c u later", "c u monday", "see you monday", "catch you next week", "catch you then", "catch u then"]
# phrases that mean "break" - if these are typed in slack (or chosen app), the timer will stop
_break_phrases = ["break", "breaky"]
# phrases that mean "back from break" - if these are typed in slack (or chosen app), the timer will start
_back_phrases = ["bac"]

# constants
INACTIVITY_THRESHOLD = 20 * 60  # if away 20 mins, then timer stops (it subtracts the 20 mins overage from the timer)
INACTIVITY_DAY_PASSED = 60 * 60 * 6  # if you sent end of day message, then this is how long script will wait to start the timer again when interacting with work apps
EST = timezone('US/Eastern')

# debug flags
_debug_logic = False
_debug_logic_verbose = False
_debug_api = False
# <<<<<< END OF USER-VARIABLES <<<<<< #

# buffer that holds 30 characters that are the last typed characters
_keystroke_buffer = []
_buffer_size = 30

# activity states / flags
_on_break = False
_last_work_activity_time = time.time() - 999  # start at some long time ago so the loop can start when launched
_last_any_activity_time = time.time() - 999  # start at some long time ago so the loop can start when launched
_monitor_loop_permitted = True # the monitor loop can run
_timer_running = False
_day_ended = False
_total_hours = 0

####################################################################################
#############################   MISC METHODS   #####################################
####################################################################################
import winsound

def play_notification_sound(sound_path):
    winsound.PlaySound(sound_path, winsound.SND_FILENAME)
    
def human_readable_datetime():
    readable_datetime_format = "%B %d, %Y %I:%M %p EST"
    return datetime.datetime.now(EST).strftime(readable_datetime_format)

####################################################################################
################################  TOGGL API  #######################################
####################################################################################
from toggl.api_client import TogglClientApi

_key =  os.environ.get("TOGGL_API_KEY")

# toggl api
_credentials = {
    "token": _key,
    "username": "rstuart 33",
    "workspace_id": 4149584,
    "user_agent": "Toggl Automater"  # a name for your client app
}
_toggl_api = TogglClientApi(_credentials)

_response = _toggl_api.get_workspaces()
if _debug_api: print(_response)


def start_new_timer():
    """
    Starts a new timer in toggle that runs until we stop it.
    """
    
    # set flag
    global _timer_running
    _timer_running = True
    
    # Create an instance of the TogglClientApi
    toggl_api = TogglClientApi(_credentials)

    # get now as ISO 8601
    now = datetime.datetime.now(EST).isoformat()

    # Define the time entry details
    time_entry = {
        "time_entry": {
            "description": "",
            "duration": -1,  # example duration in seconds (1 hour); set to a negative number to start a timer
            "start": now,  # ISO 8601 format datetime
            "pid": 176371721,  # replace with your project id from Toggl
            "created_with": "Toggl Automater"
        }
    }

    # Start the timer
    response = toggl_api.create_time_entry(time_entry)
    if _debug_api: print(response)
    
    # notify user
    print("STARTED new timer at: " + human_readable_datetime() + "...\n")
    play_notification_sound("C:\\Windows\\Media\\Speech On.wav")
    os.system("msg * Timer started!")
    

def stop_current_timer(auto = False, playsound = True, self = _toggl_api):
    """
    Stops the current running timer.
    """
    
    # set flag
    global _timer_running
    _timer_running = False
    
    # First, get the current running time entry
    response = self.query("/time_entries/current")
    
    if response.status_code != requests.codes.ok:
        response.raise_for_status()

    current_time_entry = response.json()["data"]

    # If there's no running timer, return
    if not current_time_entry:
        return None

    # Now, stop the timer by setting the stop time to the current time
    time_entry_id = current_time_entry["id"]
    
    # Get the time the timer started
    start_time_str = current_time_entry["start"]
    if start_time_str.endswith('+00:0'):
        start_time_str = start_time_str[:-1] + '0'
    # String has been stripped of the last character, so we can use fromisoformat
    start_time = datetime.datetime.fromisoformat(start_time_str)
    
    # If auto, set the stop time 20 mins before it was auto-stopped
    if auto: 
        stop_time = (datetime.datetime.utcnow() - datetime.timedelta(seconds=INACTIVITY_THRESHOLD))
    else: 
        stop_time = datetime.datetime.utcnow()

    # Attach timezone information to stop_time
    stop_time = stop_time.replace(tzinfo=timezone('UTC'))

    # Round times to nearest 5 minutes
    stop_time -= datetime.timedelta(minutes=stop_time.minute % 5, seconds=stop_time.second, microseconds=stop_time.microsecond)
    start_time -= datetime.timedelta(minutes=start_time.minute % 5, seconds=start_time.second, microseconds=start_time.microsecond)

    updated_data = {
        "time_entry": {
            "stop": stop_time,
            "duration":  int((stop_time - start_time).total_seconds()) # Calculate total duration
        }
    }

    response = self.query(f"/time_entries/{time_entry_id}/stop", method="PUT", json_data=updated_data)
    
    if response.status_code != requests.codes.ok:
        response.raise_for_status()

    if playsound:
        play_notification_sound("C:\\Windows\\Media\\Speech Off.wav")
        
    # notify user
    print("STOPPED timer at: " + human_readable_datetime() + "...\n")
    os.system("msg * Timer stopped!")
    
    # increment total hours
    global _total_hours
    _total_hours += (stop_time - start_time).total_seconds() / 3600
    
    return response.json()


def is_within_working_hours():
    now = datetime.datetime.now(EST)
    return 10 <= now.hour < 22

def is_activity_timeout(last_activity_time, check_day_passed = False):
    threshold = INACTIVITY_THRESHOLD
    if check_day_passed:
        threshold = INACTIVITY_DAY_PASSED
    is_active =  time.time() - last_activity_time <= threshold
    if _debug_logic: print("User is active." if is_active else "User is inactive.")
    return not is_active

####################################################################################
#############################  ACTIVITY CHECKS  ####################################
####################################################################################
import pygetwindow as gw
#from fuzzywuzzy import fuzz

def is_string_in_phrases(string, phrases, fuzzy_threshold__unused):
    for phrase in phrases:
        # remove spaces from phrase
        phrase = phrase.replace(" ", "")
        if phrase.lower() in string.lower():
            print ("Found phrase: " + phrase + " in string: " + string)
            # cleart the buffer
            _keystroke_buffer.clear()
            return True
    return False
    
    #for phrase in phrases:
    #    similarity_score = fuzz.token_set_ratio(phrase, phrases)
    #    if _debug_logic: print("Similarity score: " + str(similarity_score))
    #    if similarity_score >= threshold:
    #        return True
    #return False

def is_work_app_focused(app_names):
    # get the active window
    active_window = gw.getActiveWindow()
    
    if active_window is None:
        return False
    
    if active_window and _debug_logic and _debug_logic_verbose: print(active_window.title)

    # check if active window is one of the specified apps
    for app_name in app_names:
        if not _project_title in active_window.title.lower():
            continue
        if _debug_logic and _debug_logic_verbose: print(app_name.lower(), active_window.title.lower())
        if app_name.lower() in active_window.title.lower():
            return True

def is_any_work_app_open():
    # Get all visible windows
    windows = gw.getAllTitles()
    # iterate thru all the window titles from pygetwindow
    for window in windows:
        if window is None:
            continue
        # iterate thru all the required apps
        for app in _work_apps:
            # if the required app is open, and it has the word _project_title in the title, return True
            if app.lower() in window.lower() and _project_title in window.lower():
                if _debug_logic: print("Required app is open.")
                return True
    
    return False

# query for break message
def query_for_break_slack_message():
    return query_for_specified_messages(_break_phrases, 95)
    
# query for back message
def query_for_back_slack_message():
    return query_for_specified_messages(_back_phrases, 95)

# if slack is the window, check if the buffer contains any of the phrases that mean "eod" 
def query_for_eod_slack_message():
    return query_for_specified_messages(_eod_phrases)

def query_for_specified_messages(messages, fuzzy_threshold = 80):
    if not is_work_app_focused(_work_comms_app):
        return False
    
   # global variables
    global _last_work_activity_time
    global _monitor_loop_permitted
            
    # check if the buffer contains any of the phrases
    if _debug_logic: print("Buffer content: " + str(_keystroke_buffer))
    buffer_string_concat = ''.join(_keystroke_buffer)
    if is_string_in_phrases(buffer_string_concat, messages, fuzzy_threshold):
        return True
    
    return False

# every N interactions, check if the user is interacting with a work window
interaction_check_count = 5 # N interactions (clicks, keystrokes)
interaction_counter = 0
def on_interacted_with_any_window():
    global _last_work_activity_time
    global _last_any_activity_time
    global interaction_counter
    global interaction_check_count
    
    # any activity at all, reset this timer so we know when user got back on the PC
    _last_any_activity_time = time.time()
    #if _debug_logic: print("User interacted with PC " + str(interaction_counter) + " times.")
    
    if interaction_counter >= interaction_check_count:
        if is_work_app_focused(_work_apps):
            if _debug_logic: print("User interacted: " + str(_keystroke_buffer))
            _last_work_activity_time = time.time()
            interaction_counter = 0
        
    interaction_counter += 1
    return gw.getActiveWindow()
    
####################################################################################
##############################  EVENT HANDLERS  ####################################
####################################################################################
from pynput import mouse, keyboard

def handle_new_day_check():
    global _on_break
    global _timer_running
    
    if not (not _on_break and not _timer_running):
        return
    
    global _day_ended
    global _last_work_activity_time
    
    if _day_ended:
        # check if the user is back from EOD (app may have ran overnight)
        if is_activity_timeout(_last_work_activity_time, True): # check day has passed
            print("User is back from EOD - starting timer.")
            threading.Thread(target=start_new_timer).start()
            _day_ended = False
    else:
        # likely app just launched, so check if we are within working hours
        print("Work has commenced! Initialized.")
        init_activity_timers()
        threading.Thread(target=start_new_timer).start()

def buffer_keystroke(key):
    # add the key to the buffer. If the buffer is full, remove the oldest key.
    print("Key pressed: {0}".format(key))
    try:
        char_key = key.char
        if key == keyboard.Key.backspace:
            _keystroke_buffer.pop()
        elif key == keyboard.Key.space:
            char_key = " "
            _keystroke_buffer.append(char_key)
        elif key == keyboard.Key.enter:
            _keystroke_buffer.clear()
        else:
            char_key = key.char          
            _keystroke_buffer.append(char_key)
            if _debug_logic: print(char_key)  
            if len(_keystroke_buffer) > _buffer_size:
                _keystroke_buffer.pop(0)
    except AttributeError:
        pass
    
    return _keystroke_buffer

def on_mouse_button_activity(x, y, button, pressed):
    global _last_work_activity_time
    window = on_interacted_with_any_window()
    if window and is_work_app_focused(_work_apps):
        handle_new_day_check()

def init_activity_timers():
    global _last_work_activity_time
    global _last_any_activity_time
    _last_work_activity_time = time.time()
    _last_any_activity_time = time.time()

def on_keyboard_activity(key):
    global _on_break
    global _monitor_loop_permitted
    global _timer_running
    global _day_ended
    
    window = on_interacted_with_any_window()
    if _debug_logic and _debug_logic_verbose: print(window)
    
    is_new_word_key = key == keyboard.Key.space or key == keyboard.Key.enter
    is_work_app = window and _work_comms_app in window.title.lower()
    
    # if we are typing in the work comms/chat app and hit space or enter, check for keyword phrases
    if is_new_word_key and is_work_app:
        if query_for_break_slack_message():
            if _timer_running:
                to_print = "Break message detected... "
                print("Break message detected! Was the timer running? " + str(_timer_running))
                if _timer_running: 
                    _on_break = True
                    print (to_print + " stopping timer.")
                    threading.Thread(target=stop_current_timer, args=(False, True)).start()
            return
        if query_for_back_slack_message():
            if not _timer_running:
                to_print = "Back from break message detected... "
                if not _timer_running:
                    _on_break = False
                    print (to_print + " restarting timer.")
                    threading.Thread(target=start_new_timer).start()
            return
        if query_for_eod_slack_message():
            print("EOD message detected! Was the timer running? " + str(_timer_running))
            if _timer_running: 
                _day_ended = True
                threading.Thread(target=stop_current_timer, args=(True, True)).start()
            else:
                print("Timer not running at eod message, but it should be!")
                play_notification_sound("C:\\Windows\\Media\\Windows Exclamation.wav")
            _monitor_loop_permitted = False
            return
        
        # else we are in slack, but no keyword phrases were detected - this means work may have commenced (e.g. start of day)!
        handle_new_day_check()
        
        # Buffer the keystroke 
        # If keystroke is 'Enter' then the buffer gets cleared! hence why we check for keyword phrases first.
        buffer_keystroke(key)
            
# Start monitoring mouse and keyboard
_mouse_listener = mouse.Listener(on_click=on_mouse_button_activity)
_keyboard_listener = keyboard.Listener(on_press=on_keyboard_activity)

_mouse_listener.start()
_keyboard_listener.start()

####################################################################################
################################  MAIN LOOP  #######################################
####################################################################################
try:
    time.sleep(1)
    print("Beginning status monitor...")
    
    while True:
        # All the work apps are closed, so we are DEFINITELY done for the day
        if is_activity_timeout(_last_work_activity_time) and _timer_running: 
            if _debug_logic: print("User work activity timed out - stopping timer.")
            threading.Thread(target=stop_current_timer, args=(True, False)).start()
            play_notification_sound("C:\\Windows\\Media\\Speech Sleep.wav")
            # if the time of day is past 7pm, then trigger a git status check
            if datetime.datetime.now().hour >= 19:
                git_checker.status_check()
            
        # Loop to check activity again after N seconds
        if _monitor_loop_permitted:
            time.sleep(15)
            continue
            
        while not _monitor_loop_permitted:
            time.sleep(15)

# ctrl-c to force exit
except KeyboardInterrupt: 
    if _timer_running: 
        threading.Thread(target=stop_current_timer, args=(False, True)).start()
    time.sleep(1)
    print("Timer stopped. Exiting program.")
