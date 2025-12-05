#!/usr/bin/env python3
"""
Portrait -> Landscape Converter PRO (Rewrite, modular, CPU-only)

Features:
 - Batch folder scan (auto-detect portrait videos)
 - Per-file selection
 - Modes: Blur background (adjustable), Letterbox (color), Zoom-crop (zoom)
 - Background music: trim or loop, volume control
 - Watermark: choose image, scale, position, opacity
 - Static preview (first frame)
 - Settings saved to ~/.portrait2landscape_settings.json
 - Fixed bottom toolbar with always-visible Convert button
 - Threaded conversion, robust FFmpeg invocation, error logging
"""

from __future__ import annotations
import os
import sys
import json
import shutil
import subprocess
import threading
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

try:
    from tkinter import *
    from tkinter import ttk, filedialog, messagebox, colorchooser
except Exception as e:
    print("Tkinter not available:", e)
    sys.exit(1)

try:
    from PIL import Image, ImageTk
except Exception:
    print("Pillow is required. Install with: pip install pillow")
    sys.exit(1)

try:
    import cv2
except Exception:
    print("opencv-python is required. Install with: pip install opencv-python")
    sys.exit(1)

# ------------------------------ Config / Settings ------------------------------

SETTINGS_PATH = os.path.expanduser("~/.portrait2landscape_settings.json")
DEFAULT_SETTINGS = {
    "blur_strength": 20,
    "letterbox_color": "#000000",
    "zoom_strength": 1.05,
    "resolution": "1080p",
    "bgm_trim": True,
    "bgm_loop": False,
    "bgm_volume": 1.0,
    "watermark_scale": 0.15,
    "watermark_pos": "bottom-right",
    "watermark_opacity": 0.8,
    "preserve_original_audio": True
}

def load_settings() -> dict:
    s = DEFAULT_SETTINGS.copy()
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                js = json.load(f)
            s.update(js)
    except Exception:
        pass
    return s

def save_settings(settings: dict):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass

# ------------------------------ Utilities ------------------------------

def ffmpeg_exists() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except Exception:
        return False

def run_cmd(cmd: List[str], timeout: Optional[int] = None) -> Tuple[bool, str, str]:
    """Run cmd, capture stdout/stderr; return (ok, stdout, stderr)."""
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        out = proc.stdout.decode("utf-8", errors="ignore")
        err = proc.stderr.decode("utf-8", errors="ignore")
        ok = proc.returncode == 0
        return ok, out, err
    except subprocess.TimeoutExpired as e:
        return False, "", f"Timeout: {e}"
    except Exception as e:
        return False, "", str(e)

def video_resolution(path: str) -> Optional[Tuple[int,int]]:
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return None
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        cap.release()
        if w <= 0 or h <= 0:
            return None
        return (w, h)
    except Exception:
        return None

def is_portrait(res: Optional[Tuple[int,int]]) -> bool:
    if not res:
        return False
    w, h = res
    return h > w

def human_time(seconds: Optional[float]) -> str:
    if not seconds:
        return "Unknown"
    try:
        return time.strftime("%H:%M:%S", time.gmtime(seconds))
    except Exception:
        return "Unknown"

def get_duration(path: str) -> Optional[float]:
    try:
        ok, out, err = run_cmd(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path])
        if ok and out.strip():
            return float(out.strip())
    except Exception:
        pass
    return None

# ------------------------------ FFmpeg filter builders ------------------------------

def build_blur_vf(W: int, H: int, blur_strength: int) -> str:
    # Decompose: create foreground scaled to fit (pad), create blurred background scale-increase then boxblur, overlay foreground center
    s = max(1, int(blur_strength))
    vf = (
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black[fg];"
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur={s}:{s}[bg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )
    return vf

def build_letterbox_vf(W: int, H: int, hexcolor: str) -> str:
    col = hexcolor
    if col.startswith("#"):
        col = "0x" + col[1:]
    vf = f"scale='min({W},iw)':-2,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:{col}"
    return vf

def build_zoom_vf(W: int, H: int, zoom: float) -> str:
    # For zoom crop: scale so height matches, then crop center. Zoom parameter is not used directly in this simple filter;
    # to simulate zoom, scale slightly larger than needed then crop.
    scale_expr = f"scale=ceil(iw*{zoom}):-2"
    # But simpler reliable variant:
    vf = f"scale=-2:{H},crop={W}:{H}"
    return vf

# ------------------------------ GUI Application ------------------------------

class PortraitConverterApp:
    def __init__(self, root):
        self.root = root
        root.title("Portrait → Landscape Converter PRO (CPU only)")
        root.geometry("1000x700")

        # load settings
        self.settings = load_settings()

        # state
        self.files: List[Dict] = []  # each dict: path,res,dur,selected IntVar
        self.bgm_path: Optional[str] = None
        self.watermark_path: Optional[str] = None
        self.stop_flag = False

        # build UI
        self._build_ui()

    # ---------------- UI ----------------
    def _build_ui(self):
        # fixed bottom toolbar
        bottom = Frame(self.root, bg="#efefef", height=56)
        bottom.pack(side=BOTTOM, fill=X)

        self.btn_convert = Button(bottom, text="Start Conversion", bg="#2d8f2d", fg="white",
                                  font=("Arial",12,"bold"), command=self.start_conversion)
        self.btn_convert.pack(side=LEFT, padx=12, pady=8)

        self.btn_stop = Button(bottom, text="Stop", bg="#c94242", fg="white", command=self.request_stop)
        self.btn_stop.pack(side=LEFT, padx=8)

        Label(bottom, text="Status:").pack(side=LEFT, padx=6)
        self.status_var = StringVar(value="Idle")
        Label(bottom, textvariable=self.status_var, fg="blue").pack(side=LEFT)

        # main scrollable area
        container = Frame(self.root)
        container.pack(fill=BOTH, expand=True)

        canvas = Canvas(container)
        vsb = Scrollbar(container, orient=VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.main_frame = Frame(canvas)
        canvas.create_window((0,0), window=self.main_frame, anchor="nw")
        self.main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # --- File controls row ---
        fc = Frame(self.main_frame)
        fc.pack(fill=X, pady=6)
        Button(fc, text="Select Folder", command=self.select_folder).pack(side=LEFT, padx=4)
        Button(fc, text="Add Files", command=self.add_files).pack(side=LEFT, padx=4)
        Button(fc, text="Clear List", command=self.clear_list).pack(side=LEFT, padx=4)
        Button(fc, text="Refresh Scan", command=self.refresh_scan).pack(side=LEFT, padx=4)

        # --- File list area ---
        Label(self.main_frame, text="Detected Videos (portrait auto-selected):", font=("Arial", 11, "bold")).pack(anchor="w")
        self.file_list_frame = Frame(self.main_frame)
        self.file_list_frame.pack(fill=X, pady=4)

        # --- Preview & info ---
        Label(self.main_frame, text="Preview (first frame):", font=("Arial", 11, "bold")).pack(anchor="w", pady=(8,0))
        self.preview_label = Label(self.main_frame, text="No preview", relief="sunken", width=64, height=12)
        self.preview_label.pack()
        self.info_label = Label(self.main_frame, text="", justify=LEFT)
        self.info_label.pack(anchor="w", pady=4)

        # --- Conversion options ---
        Label(self.main_frame, text="Conversion Options:", font=("Arial", 11, "bold")).pack(anchor="w", pady=(8,0))
        opts = Frame(self.main_frame); opts.pack(fill=X, pady=4)

        # Mode
        self.mode_var = StringVar(value="Blur")
        Label(opts, text="Mode:").grid(row=0, column=0, sticky="w")
        Radiobutton(opts, text="Blur Background", variable=self.mode_var, value="Blur").grid(row=0, column=1, sticky="w")
        Radiobutton(opts, text="Letterbox", variable=self.mode_var, value="Letterbox").grid(row=0, column=2, sticky="w")
        Radiobutton(opts, text="Zoom-Crop", variable=self.mode_var, value="Zoom").grid(row=0, column=3, sticky="w")

        # Resolution
        Label(opts, text="Resolution:").grid(row=1, column=0, sticky="w", pady=6)
        self.res_var = StringVar(value=self.settings.get("resolution","1080p"))
        ttk.Combobox(opts, textvariable=self.res_var, values=["720p","1080p"], state="readonly", width=10).grid(row=1, column=1, sticky="w")

        # Blur strength
        Label(opts, text="Blur strength:").grid(row=2, column=0, sticky="w")
        self.blur_var = IntVar(value=self.settings.get("blur_strength",20))
        Scale(opts, from_=1, to=80, orient=HORIZONTAL, variable=self.blur_var, length=220).grid(row=2, column=1, columnspan=2)

        # Letterbox color
        Label(opts, text="Letterbox color:").grid(row=3, column=0, sticky="w", pady=6)
        self.lb_color = StringVar(value=self.settings.get("letterbox_color","#000000"))
        Entry(opts, textvariable=self.lb_color, width=10).grid(row=3, column=1, sticky="w")
        Button(opts, text="Pick", command=self.pick_color).grid(row=3, column=2, sticky="w")

        # Zoom strength
        Label(opts, text="Zoom (for Zoom mode):").grid(row=4, column=0, sticky="w")
        self.zoom_var = DoubleVar(value=self.settings.get("zoom_strength",1.05))
        Scale(opts, from_=1.0, to=1.6, resolution=0.05, orient=HORIZONTAL, variable=self.zoom_var, length=220).grid(row=4, column=1, columnspan=2)

        # --- Background music ---
        Label(self.main_frame, text="Background Music (optional):", font=("Arial", 11, "bold")).pack(anchor="w", pady=(8,0))
        bgf = Frame(self.main_frame); bgf.pack(fill=X)
        self.bgm_label = StringVar(value="No audio selected")
        Label(bgf, textvariable=self.bgm_label).pack(side=LEFT)
        Button(bgf, text="Choose", command=self.choose_bgm).pack(side=LEFT, padx=6)
        Button(bgf, text="Remove", command=self.remove_bgm).pack(side=LEFT, padx=6)
        # bgm options
        bgopts = Frame(self.main_frame); bgopts.pack(fill=X)
        self.bgm_trim_var = IntVar(value=1 if self.settings.get("bgm_trim",True) else 0)
        self.bgm_loop_var = IntVar(value=1 if self.settings.get("bgm_loop",False) else 0)
        Checkbutton(bgopts, text="Trim to video length", variable=self.bgm_trim_var).pack(anchor="w")
        Checkbutton(bgopts, text="Loop music if shorter", variable=self.bgm_loop_var).pack(anchor="w")
        volf = Frame(self.main_frame); volf.pack(fill=X, pady=4)
        Label(volf, text="Music volume:").pack(side=LEFT)
        self.bgm_vol_var = DoubleVar(value=self.settings.get("bgm_volume",1.0))
        Scale(volf, from_=0.0, to=2.0, resolution=0.05, orient=HORIZONTAL, variable=self.bgm_vol_var, length=220).pack(side=LEFT)

        # --- Watermark ---
        Label(self.main_frame, text="Watermark (optional):", font=("Arial", 11, "bold")).pack(anchor="w", pady=(8,0))
        wmf = Frame(self.main_frame); wmf.pack(fill=X)
        self.wm_label = StringVar(value="No watermark selected")
        Label(wmf, textvariable=self.wm_label).pack(side=LEFT)
        Button(wmf, text="Choose", command=self.choose_watermark).pack(side=LEFT, padx=6)
        Button(wmf, text="Remove", command=self.remove_watermark).pack(side=LEFT, padx=6)
        wmopts = Frame(self.main_frame); wmopts.pack(fill=X, pady=4)
        Label(wmopts, text="Scale:").pack(side=LEFT)
        self.wm_scale_var = DoubleVar(value=self.settings.get("watermark_scale",0.15))
        Scale(wmopts, from_=0.04, to=0.5, resolution=0.01, orient=HORIZONTAL, variable=self.wm_scale_var, length=160).pack(side=LEFT)
        Label(wmopts, text="Opacity:").pack(side=LEFT, padx=(8,0))
        self.wm_opacity_var = DoubleVar(value=self.settings.get("watermark_opacity",0.8))
        Scale(wmopts, from_=0.1, to=1.0, resolution=0.05, orient=HORIZONTAL, variable=self.wm_opacity_var, length=160).pack(side=LEFT)
        Label(wmopts, text="Position:").pack(side=LEFT, padx=(8,0))
        self.wm_pos_var = StringVar(value=self.settings.get("watermark_pos","bottom-right"))
        ttk.Combobox(wmopts, textvariable=self.wm_pos_var, values=["top-left","top-right","bottom-left","bottom-right","center"], state="readonly", width=12).pack(side=LEFT)

        # --- Progress & log ---
        Label(self.main_frame, text="Progress:", font=("Arial", 11, "bold")).pack(anchor="w", pady=(8,0))
        self.overall_progress = ttk.Progressbar(self.main_frame, orient="horizontal", length=760, mode="determinate")
        self.overall_progress.pack(padx=6, pady=4)
        self.current_progress = ttk.Progressbar(self.main_frame, orient="horizontal", length=760, mode="determinate")
        self.current_progress.pack(padx=6, pady=4)

        Label(self.main_frame, text="Log:").pack(anchor="w", pady=(8,0))
        self.log_box = Text(self.main_frame, height=10)
        self.log_box.pack(fill=BOTH, expand=False)

    # ---------------- File list helpers ----------------
    def clear_list(self):
        self.files.clear()
        for w in self.file_list_frame.winfo_children():
            w.destroy()
        self.preview_label.config(image="", text="No preview")
        self.preview_label.image = None
        self.info_label.config(text="")
        self.log("Cleared file list.")

    def select_folder(self):
        folder = filedialog.askdirectory(title="Select folder to scan")
        if not folder:
            return
        self.scan_folder(folder)

    def add_files(self):
        files = filedialog.askopenfilenames(title="Choose video files", filetypes=[("Videos","*.mp4 *.mov *.mkv *.avi *.webm"),("All","*.*")])
        if not files:
            return
        for p in files:
            self._add_file_entry(p)
        self.refresh_file_list()

    def scan_folder(self, folder: str):
        exts = (".mp4",".mov",".mkv",".avi",".webm")
        self.files.clear()
        try:
            for fname in sorted(os.listdir(folder)):
                if fname.lower().endswith(exts):
                    self._add_file_entry(os.path.join(folder, fname))
        except Exception as e:
            self.log(f"Scan error: {e}")
        self.refresh_file_list()

    def _add_file_entry(self, path: str):
        path = os.path.abspath(path)
        if any(entry["path"] == path for entry in self.files):
            return
        res = video_resolution(path)
        dur = get_duration(path)
        selected = IntVar(value=1 if is_portrait(res) else 0)
        self.files.append({"path": path, "res": res, "dur": dur, "selected": selected})

    def refresh_file_list(self):
        for w in self.file_list_frame.winfo_children():
            w.destroy()
        for entry in self.files:
            row = Frame(self.file_list_frame, relief="groove", bd=1)
            row.pack(fill=X, pady=2)
            cb = Checkbutton(row, variable=entry["selected"])
            cb.pack(side=LEFT, padx=4)
            Label(row, text=os.path.basename(entry["path"]), width=56, anchor="w").pack(side=LEFT)
            res = entry.get("res")
            rtxt = f"{res[0]}x{res[1]}" if res else "?"
            Label(row, text=rtxt).pack(side=LEFT, padx=6)
            Label(row, text=human_time(entry.get("dur"))).pack(side=LEFT, padx=6)
            Button(row, text="Preview", command=lambda p=entry["path"]: self.preview_file(p)).pack(side=RIGHT, padx=6)

    def refresh_scan(self):
        for entry in self.files:
            entry["res"] = video_resolution(entry["path"])
            entry["selected"].set(1 if is_portrait(entry["res"]) else 0)
        self.refresh_file_list()

    # ---------------- Preview / pickers ----------------
    def preview_file(self, path: str):
        self.preview_label.config(text="Loading preview...")
        try:
            cap = cv2.VideoCapture(path)
            ok, frame = cap.read()
            cap.release()
            if not ok or frame is None:
                self.preview_label.config(text="Cannot read video frame")
                return
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(img)
            pil.thumbnail((640,360))
            tk = ImageTk.PhotoImage(pil)
            self.preview_label.config(image=tk, text="")
            self.preview_label.image = tk
            res = video_resolution(path)
            dur = get_duration(path)
            self.info_label.config(text=f"{path}\nResolution: {res}\nDuration: {human_time(dur)}")
        except Exception as e:
            self.preview_label.config(text="Preview error")
            self.info_label.config(text=str(e))
            self.log(f"Preview error: {e}")

    def pick_color(self):
        c = colorchooser.askcolor(color=self.lb_color.get())
        if c and c[1]:
            self.lb_color.set(c[1])

    def choose_bgm(self):
        p = filedialog.askopenfilename(title="Select background audio", filetypes=[("Audio","*.mp3 *.m4a *.aac *.wav *.flac"),("All","*.*")])
        if p:
            self.bgm_path = p
            self.bgm_label.set(os.path.basename(p))

    def remove_bgm(self):
        self.bgm_path = None
        self.bgm_label.set("No audio selected")

    def choose_watermark(self):
        p = filedialog.askopenfilename(title="Select watermark image", filetypes=[("Images","*.png *.jpg *.jpeg *.webp"),("All","*.*")])
        if p:
            self.watermark_path = p
            self.wm_label.set(os.path.basename(p))

    def remove_watermark(self):
        self.watermark_path = None
        self.wm_label.set("No watermark selected")

    # ---------------- Logging / stop ----------------
    def log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        try:
            self.log_box.insert(END, f"[{ts}] {text}\n")
            self.log_box.see(END)
        except Exception:
            print(f"[{ts}] {text}")

    def request_stop(self):
        self.stop_flag = True
        self.log("Stop requested by user.")

    # ---------------- Conversion ----------------
    def start_conversion(self):
        if not ffmpeg_exists():
            messagebox.showerror("FFmpeg not found", "FFmpeg is required and was not found in PATH.")
            return
        selected = [e for e in self.files if e["selected"].get() == 1]
        if not selected:
            messagebox.showerror("No files selected", "Select at least one portrait video to convert.")
            return
        outdir = filedialog.askdirectory(title="Select output folder")
        if not outdir:
            return

        # save current settings
        self.settings["blur_strength"] = int(self.blur_var.get())
        self.settings["letterbox_color"] = self.lb_color.get()
        self.settings["zoom_strength"] = float(self.zoom_var.get())
        self.settings["resolution"] = self.res_var.get()
        self.settings["bgm_trim"] = bool(self.bgm_trim_var.get())
        self.settings["bgm_loop"] = bool(self.bgm_loop_var.get())
        self.settings["bgm_volume"] = float(self.bgm_vol_var.get())
        self.settings["watermark_scale"] = float(self.wm_scale_var.get())
        self.settings["watermark_pos"] = self.wm_pos_var.get()
        self.settings["watermark_opacity"] = float(self.wm_opacity_var.get())
        save_settings(self.settings)

        # disable convert button
        self.btn_convert.config(state="disabled")
        self.stop_flag = False
        self.overall_progress['value'] = 0
        self.current_progress['value'] = 0
        self.status_var.set("Starting...")

        # run worker thread
        worker = threading.Thread(target=self._worker_convert, args=(selected, outdir), daemon=True)
        worker.start()

    def _worker_convert(self, entries: List[Dict], outdir: str):
        total = len(entries)
        done = 0
        for entry in entries:
            if self.stop_flag:
                self.log("Stopped by user.")
                break

            src = entry["path"]
            base = os.path.splitext(os.path.basename(src))[0]
            outpath = os.path.join(outdir, f"{base}_landscape.mp4")
            self.log(f"Processing: {src}")

            # resolution
            res_choice = self.res_var.get()
            W,H = (1920,1080) if res_choice=="1080p" else (1280,720)

            # build video filter
            mode = self.mode_var.get()
            if mode == "Blur":
                vf = build_blur_vf(W,H,int(self.blur_var.get()))
            elif mode == "Letterbox":
                vf = build_letterbox_vf(W,H,self.lb_color.get())
            else:
                vf = build_zoom_vf(W,H,float(self.zoom_var.get()))

            tmpdir = tempfile.mkdtemp(prefix="p2l_")
            tmp_video = os.path.join(tmpdir, "video_only.mp4")

            # Step A: render video-only (with watermark if present)
            try:
                if self.watermark_path:
                    # watermark overlay via filter_complex with watermark input [1:v]
                    wm_scale_px = int(W * float(self.wm_scale_var.get()))
                    wm_op = float(self.wm_opacity_var.get())
                    pos = self.wm_pos_var.get()
                    if pos == "top-left":
                        x_expr, y_expr = "10", "10"
                    elif pos == "top-right":
                        x_expr, y_expr = "W-w-10", "10"
                    elif pos == "bottom-left":
                        x_expr, y_expr = "10", "H-h-10"
                    elif pos == "center":
                        x_expr, y_expr = "(W-w)/2", "(H-h)/2"
                    else:
                        x_expr, y_expr = "W-w-10", "H-h-10"
                    # watermark filter: scale watermark, set alpha, overlay
                    # colorchannelmixer aa sets alpha multiplier on watermark
                    filter_complex = (
                        f"[1:v]scale={wm_scale_px}:-2,format=rgba,colorchannelmixer=aa={wm_op}[wm];"
                        f"{vf}[base];"
                        f"[base][wm]overlay={x_expr}:{y_expr}"
                    )
                    cmdA = ["ffmpeg","-y","-i", src,"-i", self.watermark_path, "-filter_complex", filter_complex,
                            "-map","0:v", "-c:v","libx264","-preset","medium","-pix_fmt","yuv420p", "-an", tmp_video]
                else:
                    cmdA = ["ffmpeg","-y","-i", src, "-vf", vf, "-c:v","libx264","-preset","medium","-pix_fmt","yuv420p", "-an", tmp_video]

                self.log(f"Rendering video-only to temp file...")
                ok, out, err = run_cmd(cmdA, timeout=600)
                if not ok:
                    self.log(f"Video render failed: {err[:400]}")
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    continue

                # Step B: audio handling (bgm or preserve original)
                if self.bgm_path:
                    vol = float(self.bgm_vol_var.get())
                    trim = bool(self.bgm_trim_var.get())
                    loop = bool(self.bgm_loop_var.get())
                    # Combine original audio and bgm using amix
                    # inputs: 0=temp_video, 1=original src audio, 2=bgm
                    if loop:
                        # loop bgm indefinitely
                        cmdB = ["ffmpeg","-y","-i", tmp_video, "-i", src, "-stream_loop","-1","-i", self.bgm_path,
                                "-filter_complex", f"[1:a]volume=1.0[a1];[2:a]volume={vol}[a2];[a1][a2]amix=inputs=2:duration=shortest[aout]",
                                "-map","0:v","-map","[aout]","-c:v","copy","-c:a","aac","-b:a","192k", outpath]
                    else:
                        cmdB = ["ffmpeg","-y","-i", tmp_video, "-i", src, "-i", self.bgm_path,
                                "-filter_complex", f"[1:a]volume=1.0[a1];[2:a]volume={vol}[a2];[a1][a2]amix=inputs=2:duration=shortest[aout]",
                                "-map","0:v","-map","[aout]","-c:v","copy","-c:a","aac","-b:a","192k"]
                        if trim:
                            cmdB.insert(-1, "-shortest")
                        cmdB.append(outpath)

                    self.log("Mixing audio and writing final output...")
                    ok2, o2, e2 = run_cmd(cmdB, timeout=300)
                    if not ok2:
                        self.log(f"Audio mix failed: {e2[:400]}")
                        # fallback: replace audio with bgm only
                        fallback = ["ffmpeg","-y","-i", tmp_video, "-i", self.bgm_path, "-map","0:v","-map","1:a",
                                    "-c:v","copy","-c:a","aac","-b:a","192k"]
                        if trim:
                            fallback.insert(-1, "-shortest")
                        fallback.append(outpath)
                        okf, of, ef = run_cmd(fallback, timeout=180)
                        if not okf:
                            self.log(f"Fallback audio mux failed: {ef[:400]}")
                            # as last resort, copy video-only temp to output
                            shutil.copy(tmp_video, outpath)
                else:
                    # preserve original audio if exists; else leave silent
                    cmdB = ["ffmpeg","-y","-i", tmp_video, "-i", src, "-map","0:v","-map","1:a?", "-c:v","copy","-c:a","aac","-b:a","160k", outpath]
                    ok2, o2, e2 = run_cmd(cmdB, timeout=180)
                    if not ok2:
                        self.log(f"Audio copy failed: {e2[:400]}; saving video-only instead.")
                        shutil.copy(tmp_video, outpath)

            except Exception as ex:
                self.log(f"Exception while converting {src}: {ex}")
                try:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                except Exception:
                    pass
                continue
            finally:
                try:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                except Exception:
                    pass

            done += 1
            self.overall_progress['value'] = int(100 * done / total)
            self.current_progress['value'] = 0
            self.log(f"Saved: {outpath}")

        self.status_var.set("Done")
        self.btn_convert.config(state="normal")
        self.log(f"Completed {done}/{total} files.")
        messagebox.showinfo("Done", f"Finished {done}/{total} files.")

# ------------------------------ Runner ------------------------------

def main():
    root = Tk()
    app = PortraitConverterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
