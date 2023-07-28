import time
import pygetwindow as gw
import pyautogui
import pytesseract
from pytesseract import Output
from PIL import ImageGrab

original_text = "Hello, world!"
amended_text = "Hello, universe!"
    
def find_and_replace_text(original_text, amended_text):
    # Wait for the user to activate the target window
    print("Please activate the window where you want to edit the text...")
    while True:
        time.sleep(3)
        # Grab a screenshot of the active window
        #screenshot = ImageGrab.grab()
        
        # get the active window
        active_win = gw.getActiveWindow()

        # get the window's location
        left, top, width, height = active_win.left, active_win.top, active_win.width, active_win.height

        # capture screenshot of the active window
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        #screenshot.show()
        
        # Use Tesseract to find the original text in the screenshot
        d = pytesseract.image_to_data(screenshot, output_type=Output.DICT)
        
        # split the original text and OCR output into words
        #original_words = original_text.split()
        ocr_words = d['text']
        found = False
        # clear the console
        print("\033c", end="")
        # print the OCR output
        print("OCR output: " + " " + " ".join(ocr_words))
    
        for i in range(len(ocr_words)):
                # check if the sequence starting at index i matches the original_words
                 ocr_text = " ".join(d['text'])
        
        if original_text in ocr_text:
            start_index = ocr_text.index(original_text)
            end_index = start_index + len(original_text)
            
            word_indexes = [i for i, word in enumerate(d['text']) if start_index <= d['left'][i] < end_index]
            if not word_indexes:
                print(f'Could not find "{original_text}" in the OCR output')
            else:
                x, y, w, h = d['left'][min(word_indexes)], d['top'][min(word_indexes)], \
                            d['width'][max(word_indexes)], d['height'][max(word_indexes)]
                print("Found text at: " + str(x) + ", " + str(y) + ", " + str(w) + ", " + str(h))  
                found = True
                break

        if found:
            break
            
        time.sleep(10)

    # Move the mouse to the center of the found text and click to focus the text field
    pyautogui.click(x + w // 2, y + h // 2)

    # Select the text to replace
    pyautogui.hotkey('ctrl', 'a')
    
    # Type the amended text
    pyautogui.typewrite(amended_text)

if __name__ == "__main__":
    # Example usage:
    find_and_replace_text(original_text, amended_text)
# Hello, world!