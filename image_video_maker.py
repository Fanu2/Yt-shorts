#!/usr/bin/env python3
"""
Upgraded Thumbnail & Image Video Maker
- Crossfade transitions between images
- Background music (trimmed to video length)
- Progress bar, threaded processing
- Shuffle option
- Output filename selector
- Resolution selection (480p/720p/1080p/Original)
- Zoom-crop image fit
- Re-encode via ffmpeg to H.264 + add audio
"""

import os
import re
import requests
import subprocess
import threading
import tempfile
import shutil
import math
import random
import sys
from io import BytesIO
from tkinter import *
from tkinter import filedialog, messagebox, ttk
import cv2
from PIL import Image
import numpy as np

# ------------------ Utility helpers ------------------

def safe_int(v, default):
    try:
        return int(v)
    except Exception:
        return default

def ensure_folder_writable(folder):
    try:
        test_path = os.path.join(folder, ".write_test")
        with open(test_path, "w") as f:
            f.write("test")
        os.remove(test_path)
        return True
    except Exception:
        return False

def run_ffmpeg(cmd_args):
    try:
        completed = subprocess.run(cmd_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return completed
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr.decode("utf-8", errors="ignore"))

# ------------------ Safe widget state ------------------

def set_widget_state(parent, state):
    """Recursively set widget state where supported (safe)."""
    for widget in parent.winfo_children():
        try:
            widget.configure(state=state)
        except Exception:
            pass
        # Recurse into children (frames, etc.)
        set_widget_state(widget, state)

# ------------------ Thumbnail downloader (optional) ------------------

def extract_video_ids(url):
    """Extract YouTube Shorts IDs from a channel page (best-effort)."""
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        r.raise_for_status()
        html = r.text
        ids = re.findall(r"shorts/([A-Za-z0-9_-]{11})", html)
        return list(dict.fromkeys(ids))
    except Exception:
        return []

def download_thumbnail(video_id, folder, index):
    urls = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hq720.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    ]
    for u in urls:
        try:
            r = requests.get(u, timeout=6)
            if r.status_code == 200:
                img = Image.open(BytesIO(r.content)).convert("RGB")
                save_path = os.path.join(folder, f"thumb_{index:04d}.jpg")
                img.save(save_path, quality=92)
                return True
        except Exception:
            continue
    return False

# ------------------ Image resizing / zoom-crop ------------------

def zoom_crop_and_resize(pil_img, target_w, target_h):
    """Zoom-crop center and resize to target resolution (fills frame)."""
    iw, ih = pil_img.size
    target_ratio = target_w / target_h
    src_ratio = iw / ih

    if src_ratio > target_ratio:
        # source wider: crop width
        new_h = ih
        new_w = int(ih * target_ratio)
        left = (iw - new_w) // 2
        top = 0
    else:
        # source taller: crop height
        new_w = iw
        new_h = int(iw / target_ratio)
        left = 0
        top = (ih - new_h) // 2

    cropped = pil_img.crop((left, top, left + new_w, top + new_h))
    resized = cropped.resize((target_w, target_h), Image.LANCZOS)
    return resized

# ------------------ Main slideshow creation with crossfade ------------------

def create_slideshow_thread(folder, output_path, duration_sec, fps, resolution, shuffle,
                            crossfade_frames, bgm_path, trim_music,
                            update_progress, on_done):
    """
    Core render function running in a background thread.
    - crossfade_frames: number of frames used for the crossfade between images
    - trim_music: whether to trim music to video length
    """
    try:
        # Validate and gather images
        images = sorted([f for f in os.listdir(folder) if f.lower().endswith((".jpg",".jpeg",".png"))])
        if not images:
            on_done(False, "No images found in selected folder.")
            return

        if shuffle:
            random.shuffle(images)

        # Determine target resolution
        first_pil = Image.open(os.path.join(folder, images[0])).convert("RGB")
        if resolution is None:
            target_w, target_h = first_pil.size
        else:
            target_w, target_h = resolution

        # create temporary directory
        tmp_dir = tempfile.mkdtemp(prefix="thumbvid_")
        raw_video = os.path.join(tmp_dir, "raw_video.mp4")

        # open VideoWriter with avc1 then fallback
        fourcc = cv2.VideoWriter_fourcc(*"avc1")
        writer = cv2.VideoWriter(raw_video, fourcc, fps, (target_w, target_h))
        if not writer.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(raw_video, fourcc, fps, (target_w, target_h))
        if not writer.isOpened():
            on_done(False, "Failed to open VideoWriter. Missing codecs.")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return

        total_images = len(images)
        frames_per_image = max(1, int(duration_sec * fps))
        total_frames = total_images * frames_per_image
        frames_written = 0

        update_progress(0, "Rendering frames...")

        # Preload PIL images to speed blending and resizing
        pil_images = []
        for img_name in images:
            img_path = os.path.join(folder, img_name)
            try:
                pil = Image.open(img_path).convert("RGB")
            except Exception:
                pil = None
            pil_images.append(pil)

        # Render frames with crossfade
        for idx in range(total_images):
            pil_curr = pil_images[idx]
            if pil_curr is None:
                # skip unreadable
                frames_written += frames_per_image
                update_progress(min(100, int(100 * frames_written / total_frames)),
                                f"Skipping unreadable image {idx+1}/{total_images}")
                continue

            # Prepare current frame (zoom-crop)
            curr_frame_pil = zoom_crop_and_resize(pil_curr, target_w, target_h)
            curr_bgr = cv2.cvtColor(np.array(curr_frame_pil), cv2.COLOR_RGB2BGR)

            # Determine next frame for crossfade; if last image, next is black
            if idx + 1 < total_images and pil_images[idx + 1] is not None:
                next_frame_pil = zoom_crop_and_resize(pil_images[idx + 1], target_w, target_h)
                next_bgr = cv2.cvtColor(np.array(next_frame_pil), cv2.COLOR_RGB2BGR)
            else:
                next_bgr = np.zeros_like(curr_bgr)  # fade to black on last image

            # For frames_per_image frames: first part static, last crossfade_frames are blending
            stable_frames = frames_per_image - crossfade_frames
            if stable_frames < 0:
                stable_frames = 0  # in case crossfade_frames > frames_per_image

            # write stable frames
            for _ in range(stable_frames):
                writer.write(curr_bgr)
                frames_written += 1
                if frames_written % max(1, fps//2) == 0 or frames_written == total_frames:
                    pct = int(100 * frames_written / total_frames)
                    update_progress(pct, f"Rendering frames... ({frames_written}/{total_frames})")

            # write crossfade frames
            for f in range(crossfade_frames):
                alpha = (f + 1) / max(1, crossfade_frames)  # 0..1 blending factor for next_frame
                blended = (curr_bgr.astype("float32") * (1 - alpha) + next_bgr.astype("float32") * alpha).astype("uint8")
                writer.write(blended)
                frames_written += 1
                if frames_written % max(1, fps//2) == 0 or frames_written == total_frames:
                    pct = int(100 * frames_written / total_frames)
                    update_progress(pct, f"Rendering frames... ({frames_written}/{total_frames})")

        writer.release()
        update_progress(85, "Re-encoding & adding audio (ffmpeg)...")

        # Build ffmpeg command
        final_tmp = os.path.join(tmp_dir, "final.mp4")
        if bgm_path and os.path.exists(bgm_path):
            # ffmpeg: input raw video + audio file -> encode libx264 & aac, trim audio to video length (-shortest)
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", raw_video, "-i", bgm_path,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
                "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                final_tmp
            ]
        else:
            # No audio: just re-encode video to H264 YUV420p
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", raw_video,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
                final_tmp
            ]

        try:
            run_ffmpeg(ffmpeg_cmd)
        except Exception as e:
            # If ffmpeg fails, attempt to move raw video directly
            try:
                shutil.move(raw_video, output_path)
                shutil.rmtree(tmp_dir, ignore_errors=True)
                on_done(True, f"Saved raw video (ffmpeg failed). Video at: {output_path}\nffmpeg error:\n{e}")
                return
            except Exception as e2:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                on_done(False, f"ffmpeg failed and fallback save failed:\n{e}\n{e2}")
                return

        # Move final file to output_path
        try:
            shutil.move(final_tmp, output_path)
        except Exception:
            try:
                shutil.copy(final_tmp, output_path)
            except Exception as e:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                on_done(False, f"Failed to save final video to destination: {e}")
                return

        # cleanup
        shutil.rmtree(tmp_dir, ignore_errors=True)
        update_progress(100, "Completed")
        on_done(True, f"Video saved: {output_path}")

    except Exception as exc:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
        on_done(False, f"Error during generation: {exc}")

# ------------------ GUI ------------------

root = Tk()
root.title("Thumbnail & Image Video Maker — Upgraded (Crossfade)")
root.geometry("760x480")

# Variables
url_var = StringVar()
fps_var = StringVar(value="30")
duration_var = StringVar(value="1")
outname_var = StringVar(value="generated_video.mp4")
shuffle_var = IntVar(value=0)
resolution_var = StringVar(value="720p")
bgm_var = StringVar(value="")
crossfade_ms_var = StringVar(value="500")  # crossfade length in milliseconds

# Layout
padx = 8
Label(root, text="YouTube Shorts Channel URL (optional):", font=("Arial", 11)).grid(row=0, column=0, sticky="w", padx=padx, pady=6)
Entry(root, textvariable=url_var, width=70).grid(row=0, column=1, columnspan=3, pady=6, sticky="w")

Label(root, text="Duration per image (seconds):").grid(row=1, column=0, sticky="w", padx=padx)
Entry(root, textvariable=duration_var, width=8).grid(row=1, column=1, sticky="w")

Label(root, text="FPS:").grid(row=1, column=2, sticky="e")
Entry(root, textvariable=fps_var, width=8).grid(row=1, column=3, sticky="w")

Label(root, text="Crossfade (ms):").grid(row=2, column=0, sticky="w", padx=padx)
Entry(root, textvariable=crossfade_ms_var, width=10).grid(row=2, column=1, sticky="w")

Label(root, text="Resolution:").grid(row=2, column=2, sticky="e")
resolution_menu = ttk.Combobox(root, textvariable=resolution_var, values=["480p", "720p", "1080p", "Original"], width=12, state="readonly")
resolution_menu.grid(row=2, column=3, sticky="w")

Label(root, text="Output filename:").grid(row=3, column=0, sticky="w", padx=padx, pady=6)
Entry(root, textvariable=outname_var, width=40).grid(row=3, column=1, columnspan=2, sticky="w", pady=6)

# background music chooser
Label(root, text="Background music (optional):").grid(row=4, column=0, sticky="w", padx=padx)
Entry(root, textvariable=bgm_var, width=50).grid(row=4, column=1, columnspan=2, sticky="w")
def choose_bgm():
    p = filedialog.askopenfilename(title="Select audio file", filetypes=[("Audio files", "*.mp3 *.wav *.aac *.m4a *.flac"), ("All files", "*.*")])
    if p:
        bgm_var.set(p)
Button(root, text="Browse", command=choose_bgm).grid(row=4, column=3, sticky="w")

Checkbutton(root, text="Shuffle images", variable=shuffle_var).grid(row=5, column=0, sticky="w", padx=padx, pady=8)

progress = ttk.Progressbar(root, orient="horizontal", length=520, mode="determinate")
progress.grid(row=6, column=0, columnspan=3, padx=padx, pady=6)
status_label = Label(root, text="Idle")
status_label.grid(row=6, column=3, sticky="w")

# Buttons frame
btn_frame = Frame(root)
btn_frame.grid(row=7, column=0, columnspan=4, pady=12)

def callback_download_thumbnails():
    url = url_var.get().strip()
    if "youtube.com" not in url:
        messagebox.showerror("Error", "Please enter a valid YouTube channel/shorts URL.")
        return
    out_dir = filedialog.askdirectory(title="Select output folder for thumbnails")
    if not out_dir:
        return
    thumb_folder = os.path.join(out_dir, "thumbnails")
    os.makedirs(thumb_folder, exist_ok=True)
    if not ensure_folder_writable(thumb_folder):
        messagebox.showerror("Error", "Cannot write to folder.")
        return

    def dl_thread():
        try:
            status_label.config(text="Fetching page...")
            ids = extract_video_ids(url)
            if not ids:
                messagebox.showerror("Error", "No shorts found or failed to fetch.")
                status_label.config(text="Idle")
                return
            total = len(ids)
            count = 0
            for i, vid in enumerate(ids, start=1):
                status_label.config(text=f"Downloading thumbnail {i}/{total}...")
                if download_thumbnail(vid, thumb_folder, i):
                    count += 1
                progress['value'] = int(100 * i / total)
            progress['value'] = 0
            messagebox.showinfo("Download complete", f"Downloaded {count} thumbnails to:\n{thumb_folder}")
            status_label.config(text="Idle")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")
            status_label.config(text="Idle")

    threading.Thread(target=dl_thread, daemon=True).start()

def callback_make_from_folder():
    src_folder = filedialog.askdirectory(title="Select folder containing images")
    if not src_folder:
        return
    start_render_process(src_folder)

def start_render_process(folder):
    # validate folder
    if not os.path.isdir(folder):
        messagebox.showerror("Error", "Selected folder does not exist.")
        return
    if not ensure_folder_writable(folder):
        messagebox.showerror("Error", "Cannot write to selected folder.")
        return

    fps = safe_int(fps_var.get(), 30)
    duration = safe_int(duration_var.get(), 1)
    crossfade_ms = safe_int(crossfade_ms_var.get(), 500)
    crossfade_frames = max(0, int(round((crossfade_ms / 1000.0) * fps)))
    shuffle = bool(shuffle_var.get())
    outname = outname_var.get().strip() or "generated_video.mp4"

    # output folder chooser
    outdir = filedialog.askdirectory(title="Select folder to save output file")
    if not outdir:
        return
    output_path = os.path.join(outdir, outname)

    # parse resolution
    res_choice = resolution_var.get()
    res_map = {"480p": (854, 480), "720p": (1280, 720), "1080p": (1920, 1080), "Original": None}
    resolution = res_map.get(res_choice, (1280, 720))

    bgm = bgm_var.get().strip() or None
    trim_music = True  # default behaviour: trim music to video length

    # disable UI widgets
    set_widget_state(root, "disabled")

    def update_progress(pct, status_text):
        progress['value'] = pct
        status_label.config(text=status_text)

    def on_done(success, message):
        def finish():
            set_widget_state(root, "normal")
            progress['value'] = 0
            status_label.config(text="Idle")
            if success:
                messagebox.showinfo("Done", message)
            else:
                messagebox.showerror("Error", message)
        root.after(50, finish)

    # start background worker
    worker = threading.Thread(
        target=create_slideshow_thread,
        kwargs={
            "folder": folder,
            "output_path": output_path,
            "duration_sec": duration,
            "fps": fps,
            "resolution": resolution,
            "shuffle": shuffle,
            "crossfade_frames": crossfade_frames,
            "bgm_path": bgm,
            "trim_music": trim_music,
            "update_progress": lambda p, s: root.after(0, update_progress, p, s),
            "on_done": lambda ok, msg: root.after(0, on_done, ok, msg),
        },
        daemon=True
    )
    worker.start()

btn_dl = Button(btn_frame, text="Download Shorts Thumbnails", bg="lightgreen", command=callback_download_thumbnails)
btn_dl.grid(row=0, column=0, padx=8)
btn_folder = Button(btn_frame, text="Make Video From Folder Images", bg="skyblue", command=callback_make_from_folder)
btn_folder.grid(row=0, column=1, padx=8)
btn_quit = Button(btn_frame, text="Quit", command=root.destroy)
btn_quit.grid(row=0, column=2, padx=8)

root.mainloop()
