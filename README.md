
# 🎥 YouTube Shorts Thumbnail Video Maker

Extract all available YouTube Shorts thumbnails from any channel and automatically create a slideshow video.

---

## 📑 Table of Contents

* [Overview](#overview)
* [Features](#features)
* [Installation](#installation)
* [Requirements](#requirements)
* [Usage](#usage)
* [Output Structure](#output-structure)
* [About the YouTube 48-Short Limit](#about-the-youtube-48-short-limit)
* [Future Enhancements](#future-enhancements)
* [License](#license)

---

## 📘 Overview

This tool lets you enter a **YouTube Shorts channel URL**, then:

1. Extracts all Shorts video IDs visible on that page
2. Downloads thumbnails in the highest available quality
3. Saves them in order
4. Creates a slideshow video (`shorts_video.mp4`)

Perfect for:

* Compilation videos
* Thumbnail archiving
* Artistic slideshow creation
* Channel analytics
* Personal media projects

---

## ⭐ Features

### ✔ YouTube Shorts Thumbnail Downloader

Extracts thumbnails in this order (highest available is used):

* `maxresdefault.jpg`
* `hq720.jpg`
* `hqdefault.jpg`

### ✔ GUI Application

No command-line required.

Includes:

* URL input
* Duration per image
* FPS selection
* Folder picker
* Progress dialogs
* Video creation button

### ✔ Slideshow Video Creator

Creates `MP4` video using OpenCV.

### ✔ Clean Thumbnail Organization

Automatically generates a dedicated folder:

```
thumbnails/
    thumb_0001.jpg
    thumb_0002.jpg
    ...
```

---

## 🛠 Installation

Clone or download the repo:

```bash
git clone https://github.com/<yourname>/<repo>
cd <repo>
```

Install required packages:

```bash
pip install -r requirements.txt
```

If Tkinter is missing (Linux):

```bash
sudo apt install python3-tk
```

---

## 📦 Requirements

```
requests
beautifulsoup4
pillow
opencv-python
tk
```

---

## ▶️ Usage

Run:

```bash
python yt_shorts_thumbnail_video.py
```

Steps in the GUI:

1. Enter the YouTube Shorts channel URL
2. Choose an output folder
3. Set:

   * Duration per image
   * FPS
4. Click **Start Processing**

The script will:

* Fetch Shorts video IDs
* Download thumbnails
* Create slideshow video

---

## 📁 Output Structure

```
/chosen_output_folder
    /thumbnails
        thumb_0001.jpg
        thumb_0002.jpg
        ...
    shorts_video.mp4
```

---

## ❗ About the YouTube 48-Short Limit

YouTube only provides **~48 Shorts directly in the HTML of the Shorts page**.

To retrieve **all Shorts**, the script must use one of:

* **yt-dlp (recommended)**
* YouTube Data API
* Internal continuation tokens

If you want, I can upgrade this tool to:

* Fetch all Shorts (not just the first 48)
* Use yt-dlp internally
* Automatically bypass continuation

Just ask!

---

## 🚀 Future Enhancements (Optional)

I can add:

* Fade transitions
* Background music
* Zoom/pan animation (Ken Burns effect)
* Vertical 1080×1920 Shorts format
* Time-based trimming
* yt-dlp integration (fetch ALL Shorts)
* Full video downloads, not only thumbnails

Tell me which features you'd like.

---

## 📄 License

MIT License — free to modify and use.

