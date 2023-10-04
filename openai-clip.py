import clip
import torch
from PIL import Image
import tkinter as tk
from tkinter import filedialog

# Initialize Tkinter
root = tk.Tk()
root.withdraw()

# Open file dialog
file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg")])
if not file_path:
    print("No file selected. Exiting.")
    exit()

# Load the model
device = "cuda" if torch.cuda.is_available() else "cpu"
model, transform = clip.load("ViT-B/32", device=device)

# Prepare a list of generic text prompts
text_prompts = ["what video game is this?"]
text = clip.tokenize(text_prompts).to(device)

# Prepare the image
image = transform(Image.open(file_path)).unsqueeze(0).to(device)

# Calculate features and similarity
with torch.no_grad():
    image_features = model.encode_image(image)
    text_features = model.encode_text(text)
    
    # Pick the top annotation
    image_features /= image_features.norm(dim=-1, keepdim=True)
    text_features /= text_features.norm(dim=-1, keepdim=True)
    similarity = (100.0 * image_features @ text_features.T).softmax(dim=-1)
    values, indices = similarity[0].topk(1)

# Print the result
print(f"Top annotation: {text_prompts[indices]} with similarity of {values[0]:.2f}")
