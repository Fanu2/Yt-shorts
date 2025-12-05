#!/usr/bin/env python3
import os
import re
import requests
from tkinter import *
from tkinter import filedialog, messagebox
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

# -----------------------------
# Extract Video IDs from Search
# -----------------------------
def extract_video_ids(search_url):
    """Extracts YouTube video IDs from a search results page."""
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        html = requests.get(search_url, headers=headers).text
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open URL:\n{e}")
        return []

    # Pattern for standard YouTube video links: /watch?v=XXXXXXXXXXX
    ids = re.findall(r"watch\?v=([A-Za-z0-9_-]{11})", html)

    # Remove duplicates while keeping order
    seen = set()
    unique_ids = []
    for vid in ids:
        if vid not in seen:
            unique_ids.append(vid)
            seen.add(vid)

    return unique_ids


# -----------------------------
# Download Thumbnail
# -----------------------------
def download_thumbnail(video_id, out_folder, index):
    """Download the highest-resolution thumbnail available."""
    urls = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hq720.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    ]

    for url in urls:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content))
                save_path = os.path.join(out_folder, f"thumb_{index:04d}_{video_id}.jpg")
                img.save(save_path)
                return True
        except:
            pass

    return False


# -----------------------------
# MAIN PROCESS
# -----------------------------
def start_download():
    url = url_var.get().strip()

    if "youtube.com" not in url:
        messagebox.showerror("Error", "Enter a valid YouTube search URL.")
        return

    out_folder = filedialog.askdirectory(title="Select destination folder")
    if not out_folder:
        return

    messagebox.showinfo("Please Wait", "Extracting video IDs...")

    video_ids = extract_video_ids(url)

    if not video_ids:
        messagebox.showerror("Error", "No videos found in this search.")
        return

    messagebox.showinfo("Downloading", f"Found {len(video_ids)} videos.\nDownloading thumbnails...")

    count = 0
    for i, vid in enumerate(video_ids, start=1):
        if download_thumbnail(vid, out_folder, i):
            count += 1

    messagebox.showinfo("Done", f"Downloaded {count} thumbnails\nSaved in:\n{out_folder}")


# -----------------------------
# GUI
# -----------------------------
root = Tk()
root.title("YouTube Search → Image Downloader")
root.geometry("650x250")

url_var = StringVar()

Label(root, text="Enter YouTube Search URL:", font=("Arial", 12)).pack(pady=10)
Entry(root, textvariable=url_var, width=70).pack()

Button(root, text="Download Images", bg="lightgreen", font=("Arial", 12),
       command=start_download).pack(pady=20)

Label(root, text="Example: https://www.youtube.com/results?search_query=sensuous+songs+english",
      fg="gray").pack()

root.mainloop()

