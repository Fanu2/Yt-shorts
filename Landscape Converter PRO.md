
# 📺 Portrait → Landscape Converter PRO (CPU-Only)

Convert portrait (vertical) videos into perfect landscape (horizontal) videos using advanced FFmpeg processing — with a friendly GUI.
This tool is built for **MX Linux**, **Ubuntu**, **Debian**, **Windows**, and **macOS** and works **without GPU**.

---

## ✨ Key Features

### 🎞️ Video Conversion Modes

* **Blur Background** (adjustable strength)
* **Letterbox Mode** (custom color)
* **Zoom-Crop Mode** (adjustable zoom)
* Output resolution: **720p** or **1080p**

### 🎵 Background Music (Optional)

* Add music from an audio file
* Volume control
* Choose **Trim** or **Loop** behavior
* Mix original audio + BGM using FFmpeg’s `amix`

### 🖼️ Watermark Overlay

* Add PNG/JPG watermark
* Position (TL / TR / BL / BR / Center)
* Adjustable opacity
* Adjustable scale (size)

### 🗂️ Batch Processing

* Select individual files
* Auto-detect portrait videos
* Folder scanning
* Multi-file conversion with progress bars

### 👁️ Live Preview

* Shows the **first frame** of the video
* Displays duration & resolution

### ⚙️ Settings

Saved automatically to:

```
~/.portrait2landscape_settings.json
```

### 🪟 Modern GUI

* Designed using Tkinter
* Scrollable main section
* **Always-visible bottom toolbar** with:

  * Start Conversion
  * Stop Conversion
  * Status indicator

---

## 📦 Installation

### 1. Install System Dependencies

#### **Linux (MX, Ubuntu, Debian):**

```bash
sudo apt update
sudo apt install ffmpeg python3 python3-pip
```

#### **Windows:**

* Install Python from [https://python.org](https://python.org)
* Install FFmpeg from [https://ffmpeg.org](https://ffmpeg.org) (or use a ZIP release)

#### **macOS:**

```bash
brew install ffmpeg
```

---

### 2. Install Python Dependencies

```bash
pip3 install pillow opencv-python
```

---

## ▶️ Running the Application

Clone or download your project folder, then run:

```bash
python3 portrait_to_landscape_pro_rewrite.py
```

The GUI will open immediately.

---

## 🧠 How It Works

### Step 1 — Select Videos

You can choose:

* A folder (auto-scans for .mp4, .mov, .mkv, etc.)
* Individual files
  The app will auto-select portrait videos.

### Step 2 — Choose Conversion Settings

Customize:

* Video mode
* Blur strength
* Letterbox color
* Zoom intensity
* Output resolution (720p / 1080p)

### Step 3 — Add Optional BGM or Watermark

Background music:

* Trim or loop
* Adjustable volume

Watermark:

* PNG/JPG supported
* Scale & opacity
* 5 placement options

### Step 4 — Convert

Click **Start Conversion**
A progress bar shows:

* Current video
* Overall batch progress
  All converted files are saved as:

```
<filename>_landscape.mp4
```

---

## 🧪 Example FFmpeg Processing

### Blur Mode

```bash
[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black[fg];
[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,boxblur=20:20[bg];
[bg][fg]overlay=(W-w)/2:(H-h)/2
```

### Watermark Overlay

```bash
[1:v]scale=300:-2,format=rgba,colorchannelmixer=aa=0.8[wm];
[base][wm]overlay=W-w-10:H-h-10
```

### Audio Mix

```bash
[a1][a2]amix=inputs=2:duration=shortest[aout]
```

---

## 📁 Project Structure

```
portrait-to-landscape/
│
├── portrait_to_landscape_pro_rewrite.py   # Main application
└── README.md                               # Documentation (this file)
```

---

## 🛠️ Troubleshooting

### FFmpeg not found

Ensure FFmpeg is installed and in PATH:

```
ffmpeg -version
```

### Black preview window

Some codecs can't be decoded by OpenCV → still convertible with FFmpeg.

### Very slow conversion

Blur mode + 1080p is CPU intensive.
Try:

* 720p
* Lower blur strength
* Zoom or Letterbox mode

---

## 🧩 Future Enhancements (optional)

I can add:

* GPU acceleration (VAAPI/NVENC)
* Real-time preview
* Export presets
* Drag & drop support
* Audio fade-in/out
* Side-by-side comparison preview

Ask anytime!

---

## ❤️ Credits

Built with:

* **Python 3**
* **Tkinter**
* **FFmpeg**
* **OpenCV**
* **Pillow**

---

