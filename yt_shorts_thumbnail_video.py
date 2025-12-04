import os
import re
import requests
from tkinter import *
from tkinter import filedialog, messagebox
from bs4 import BeautifulSoup
import cv2
from PIL import Image
from io import BytesIO

# ------------------ THUMBNAIL SCRAPER ------------------

def extract_video_ids(url):
    """Extract YouTube Short video IDs from the channel page."""
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except:
        messagebox.showerror("Error", "Failed to load URL")
        return []

    html = response.text
    # Find shorts URLs like /shorts/<VIDEOID>
    ids = re.findall(r"\/shorts\/([A-Za-z0-9_-]{11})", html)
    return list(dict.fromkeys(ids))  # remove duplicates


def download_thumbnail(video_id, folder, index):
    """Downloads a max-quality thumbnail for a YouTube short."""
    urls = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hq720.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    ]

    for t_url in urls:
        try:
            r = requests.get(t_url, timeout=5)
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content))
                save_path = os.path.join(folder, f"thumb_{index:04d}.jpg")
                img.save(save_path)
                return True
        except:
            pass

    return False


# ------------------ VIDEO MAKER ------------------

def create_video_from_images(folder, duration, fps):
    images = sorted([f for f in os.listdir(folder) if f.endswith(".jpg")])

    if not images:
        messagebox.showerror("Error", "No thumbnails found.")
        return

    first_img = cv2.imread(os.path.join(folder, images[0]))
    height, width, _ = first_img.shape

    video_path = os.path.join(folder, "shorts_video.mp4")
    writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    for img_name in images:
        img = cv2.imread(os.path.join(folder, img_name))

        for _ in range(duration * fps):
            writer.write(img)

    writer.release()
    messagebox.showinfo("Video Created", f"Saved video:\n{video_path}")


# ------------------ GUI ------------------

def start_process():
    url = url_var.get().strip()
    if "youtube.com" not in url:
        messagebox.showerror("Error", "Enter a valid YouTube Shorts channel URL.")
        return

    out_folder = filedialog.askdirectory(title="Select output folder")
    if not out_folder:
        return

    # Thumbnail save folder
    thumb_folder = os.path.join(out_folder, "thumbnails")
    os.makedirs(thumb_folder, exist_ok=True)

    messagebox.showinfo("Please wait", "Fetching Shorts from channel...")

    video_ids = extract_video_ids(url)

    if not video_ids:
        messagebox.showerror("Error", "No YouTube Shorts found.")
        return

    messagebox.showinfo("Downloading", f"Found {len(video_ids)} Shorts.\nDownloading thumbnails...")

    count = 0
    for idx, vid in enumerate(video_ids, start=1):
        if download_thumbnail(vid, thumb_folder, idx):
            count += 1

    messagebox.showinfo("Download Complete", f"Downloaded {count} thumbnails.")

    # Create video
    fps = int(fps_var.get())
    duration = int(duration_var.get())

    create_video_from_images(thumb_folder, duration, fps)


# ------------------ BUILD GUI WINDOW ------------------

root = Tk()
root.title("YouTube Shorts Thumbnail Video Maker")
root.geometry("600x300")

url_var = StringVar()
fps_var = StringVar(value="30")
duration_var = StringVar(value="1")

Label(root, text="YouTube Shorts Channel URL:", font=("Arial", 12)).pack(pady=5)
Entry(root, textvariable=url_var, width=70).pack()

Label(root, text="Duration per image (seconds):").pack()
Entry(root, textvariable=duration_var).pack()

Label(root, text="FPS (frames per second):").pack()
Entry(root, textvariable=fps_var).pack()

Button(root, text="Start Processing", bg="lightgreen", command=start_process).pack(pady=15)

root.mainloop()

