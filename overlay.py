import tkinter as tk
from PIL import Image, ImageTk, ImageEnhance
import sys
import os
import threading

class Overlay:

    root = None
    image_path = None
    image_folder = os.path.join(os.getenv("USERPROFILE"), "Pictures")
    
    def __init__(self, image_filename="mic.png", root_tk=None):
        """
        Initialize UI desktop icon Overlay class.

        Parameters:
        image_filename (str): The filename of the image to display. Defaults to 'mic.png'.
        root_tk (Tk): The Tkinter root window. If None, a new Tk instance will be created. Defaults to None.
        """
        
        # create root window if not provided
        if root_tk is not None: this_root = root_tk
        else: this_root = tk.Tk()
        self.root = this_root
        
        # get script path
        print(f"Folder path: {Overlay.image_folder} Image filename: {image_filename}")
        self.image_path = os.path.join(Overlay.image_folder, image_filename)
        print(f"Image path: {self.image_path}")  # Debug: Print the full image path

        # set window attributes
        self.root.overrideredirect(True)
        self.root.geometry("+15+15")
        self.root.attributes("-topmost", True, "-transparentcolor", "black")
        self.label = tk.Label(self.root, bg='black')
        self.label.pack()

        # Load and set initial image
        self.original_image = Image.open(self.image_path).convert("RGBA")
        self.image = self.original_image.copy()
        self.photo = ImageTk.PhotoImage(self.image)
        self.label.config(image=self.photo)
        self.alpha = 0.25  # Start alpha at 25%



    def animate_alpha(self):
        # Start with alpha at 25%
        min_alpha = 0.25
        lerp_rate = 0.025

        self.alpha = min_alpha
        lerp_up = True

        def update_alpha():
            nonlocal lerp_up
            if lerp_up:
                self.alpha += lerp_rate
                if self.alpha > 1:
                    self.alpha = 1
                    lerp_up = False
            else:
                self.alpha -= lerp_rate
                if self.alpha < min_alpha:
                    self.alpha = min_alpha
                    lerp_up = True

            # set alpha and update image
            self.image = self.original_image.copy()
            self.image.putalpha(int(255 * self.alpha))
            self.photo = ImageTk.PhotoImage(self.image)
            self.label.config(image=self.photo)
            self.root.after(50, update_alpha)

        update_alpha()


    def show(self):
        self.image = self.original_image.copy()  # Reset image to original
        self.alpha = 0.25  # Reset alpha to 25%
        self.root.deiconify()
        threading.Thread(target=self.animate_alpha, daemon=True).start()


    def hide(self):
        self.root.withdraw()


def toggle_overlay(action):
    if action == 'show':
        overlay.show()
    elif action == 'hide':
        overlay.hide()
    this_root.update()

if __name__ == "__main__":    
    this_root = tk.Tk()
    overlay = Overlay(root_tk=this_root)

    action = 'show'
    toggle_overlay(action)
    this_root.mainloop()
