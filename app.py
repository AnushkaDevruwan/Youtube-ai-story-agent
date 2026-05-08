import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import requests

ROOT = Path("C:/youtube-agent")
PYTHON_EXE = ROOT / "venv" / "Scripts" / "python.exe"
RUN_PIPELINE = ROOT / "run_pipeline.py"
UPLOAD_SCRIPT = ROOT / "scripts" / "upload_youtube.py"

SD_API_URL = os.getenv("SD_API_URL", "http://127.0.0.1:7861")
FORGE_DIR = Path(os.getenv("FORGE_DIR", "C:/stable-diffusion-webui-forge"))
FORGE_BAT = os.getenv("FORGE_BAT", "webui-user.bat")
FORGE_BAT_PATH = FORGE_DIR / FORGE_BAT
FORGE_START_TIMEOUT = int(os.getenv("FORGE_START_TIMEOUT", "600"))

OUTPUT_DIR = ROOT / "output"
METADATA_DIR = ROOT / "metadata"
IMAGES_RAW_DIR = ROOT / "images" / "raw"

LIBRARY_DIR = Path.home() / "Documents" / "YouTubeAgentVideos"
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def safe_name(text):
    text = text.strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text[:80] or "video"


def load_json(path):
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def copy_if_exists(src, dst):
    src = Path(src)
    dst = Path(dst)

    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def archive_current_output():
    story_file = OUTPUT_DIR / "story_package.json"
    video_file = OUTPUT_DIR / "final_short.mp4"
    metadata_file = METADATA_DIR / "current_upload.json"
    research_file = OUTPUT_DIR / "research.txt"
    topic_file = OUTPUT_DIR / "chosen_topic.txt"

    if not video_file.exists():
        raise FileNotFoundError(f"Final video not found: {video_file}")

    story = load_json(story_file)
    title = story.get("metadata", {}).get("title") or story.get("video_title") or "Generated Video"

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    folder_name = f"{timestamp}_{safe_name(title)}"
    video_folder = LIBRARY_DIR / folder_name
    video_folder.mkdir(parents=True, exist_ok=True)

    copy_if_exists(video_file, video_folder / "final_short.mp4")
    copy_if_exists(story_file, video_folder / "story_package.json")
    copy_if_exists(metadata_file, video_folder / "current_upload.json")
    copy_if_exists(research_file, video_folder / "research.txt")
    copy_if_exists(topic_file, video_folder / "chosen_topic.txt")

    # Copy images
    archived_images = video_folder / "images"
    archived_images.mkdir(exist_ok=True)

    if IMAGES_RAW_DIR.exists():
        for img in IMAGES_RAW_DIR.glob("scene*.png"):
            shutil.copy2(img, archived_images / img.name)

    manifest = {
        "title": title,
        "topic": story.get("topic", ""),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "folder": str(video_folder),
        "video_file": str(video_folder / "final_short.mp4"),
        "story_package": str(video_folder / "story_package.json"),
        "metadata_file": str(video_folder / "current_upload.json"),
        "research_file": str(video_folder / "research.txt"),
        "status": "generated",
        "youtube_url": ""
    }

    (video_folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return video_folder


class YouTubeAgentApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.forge_process = None
        self.forge_started_by_app = False

        self.title("YouTube AI Story Agent")
        self.geometry("1100x720")

        self.log_queue = queue.Queue()
        self.running = False
        self.selected_folder = None

        self.create_top_menu()
        self.create_frames()

        self.show_generate_screen()
        self.after(200, self.process_log_queue)

    def create_top_menu(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        ttk.Button(top, text="Generate", command=self.show_generate_screen).pack(side="left", padx=5)
        ttk.Button(top, text="Library", command=self.show_library_screen).pack(side="left", padx=5)

    def create_frames(self):
        self.generate_frame = ttk.Frame(self)
        self.library_frame = ttk.Frame(self)

        self.build_generate_screen()
        self.build_library_screen()

    def show_generate_screen(self):
        self.library_frame.pack_forget()
        self.generate_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def show_library_screen(self):
        self.generate_frame.pack_forget()
        self.library_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.refresh_library()

    def build_generate_screen(self):
        controls = ttk.LabelFrame(self.generate_frame, text="Generate Videos")
        controls.pack(fill="x", padx=5, pady=5)

        ttk.Label(controls, text="Number of videos:").grid(row=0, column=0, padx=8, pady=8, sticky="w")

        self.count_var = tk.IntVar(value=1)

        self.count_entry = ttk.Entry(controls, width=8, textvariable=self.count_var)
        self.count_entry.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        self.count_slider = ttk.Scale(
            controls,
            from_=1,
            to=10,
            orient="horizontal",
            command=self.slider_changed
        )
        self.count_slider.set(1)
        self.count_slider.grid(row=0, column=2, padx=8, pady=8, sticky="ew")

        controls.columnconfigure(2, weight=1)

        ttk.Label(controls, text="Theme:").grid(row=1, column=0, padx=8, pady=8, sticky="w")

        self.theme_var = tk.StringVar(value="history")
        self.theme_combo = ttk.Combobox(
            controls,
            textvariable=self.theme_var,
            values=["history", "technology", "war", "cybersecurity", "engineering"],
            width=24
        )
        self.theme_combo.grid(row=1, column=1, padx=8, pady=8, sticky="w")

        self.upload_after_generate = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            controls,
            text="Upload each video after generation",
            variable=self.upload_after_generate
        ).grid(row=1, column=2, padx=8, pady=8, sticky="w")

        self.generate_button = ttk.Button(
            controls,
            text="Generate Videos",
            command=self.start_generation
        )
        self.generate_button.grid(row=2, column=0, padx=8, pady=10, sticky="w")

        self.stop_button = ttk.Button(
            controls,
            text="Stop After Current",
            command=self.request_stop,
            state="disabled"
        )
        self.stop_button.grid(row=2, column=1, padx=8, pady=10, sticky="w")

        status_box = ttk.LabelFrame(self.generate_frame, text="Progress")
        status_box.pack(fill="both", expand=True, padx=5, pady=5)

        self.progress_label = ttk.Label(status_box, text="Idle")
        self.progress_label.pack(anchor="w", padx=8, pady=5)

        self.progress_bar = ttk.Progressbar(status_box, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", padx=8, pady=5)

        self.log_text = tk.Text(status_box, height=24, wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

    def slider_changed(self, value):
        self.count_var.set(int(float(value)))

    def log(self, text):
        self.log_queue.put(text)

    def process_log_queue(self):
        try:
            while True:
                text = self.log_queue.get_nowait()
                self.log_text.insert("end", text)
                self.log_text.see("end")
        except queue.Empty:
            pass

        self.after(200, self.process_log_queue)

    def request_stop(self):
        self.running = False
        self.log("\nStop requested. The app will stop after the current video finishes.\n")

    def start_generation(self):
        if self.running:
            messagebox.showwarning("Already running", "Generation is already running.")
            return

        try:
            count = int(self.count_var.get())
            if count < 1:
                raise ValueError()
        except Exception:
            messagebox.showerror("Invalid number", "Enter a valid number of videos.")
            return

        self.running = True
        self.generate_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.progress_bar["value"] = 0
        self.log_text.delete("1.0", "end")

        thread = threading.Thread(
            target=self.generation_worker,
            args=(count, self.theme_var.get(), self.upload_after_generate.get()),
            daemon=True
        )
        thread.start()
    def is_forge_running(self):
        try:
            response = requests.get(
                f"{SD_API_URL}/sdapi/v1/options",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

    def wait_for_forge(self, timeout=600):
        self.log(f"\nStarting Forge API check at {SD_API_URL}...\n")
        start_time = time.time()

        while time.time() - start_time < timeout:
            if self.is_forge_running():
                self.log("Forge status: running.\n")
                return True

            self.log("Forge status: starting...\n")
            time.sleep(5)

        return False

    def start_forge_hidden(self):
        """
        Starts Forge hidden, only if it is not already running.
        Keeps the process reference so the app can stop it later.
        """
        if self.is_forge_running():
            self.log("Forge status: already running. Using existing Forge instance.\n")
            self.forge_process = None
            self.forge_started_by_app = False
            return

        if not FORGE_BAT_PATH.exists():
            raise FileNotFoundError(f"Forge launcher not found: {FORGE_BAT_PATH}")

        self.log("Forge status: starting hidden...\n")

        startupinfo = None
        creationflags = 0

        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # hide window
            creationflags = subprocess.CREATE_NO_WINDOW

        self.forge_process = subprocess.Popen(
            ["cmd", "/c", str(FORGE_BAT_PATH)],
            cwd=str(FORGE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=creationflags
        )

        self.forge_started_by_app = True

        ready = self.wait_for_forge(timeout=FORGE_START_TIMEOUT)

        if not ready:
            self.stop_forge_if_started()
            raise RuntimeError("Forge did not become ready in time.")

    def stop_forge_if_started(self):
        """
        Stops Forge only if this app started it.
        If Forge was already running before the app, it leaves Forge alone.
        """
        if getattr(self, "forge_process", None) and getattr(self, "forge_started_by_app", False):
            self.log("\nForge status: stopping...\n")

            try:
                subprocess.run(
                    ["taskkill", "/PID", str(self.forge_process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
                self.log("Forge status: stopped.\n")
            except Exception as e:
                self.log(f"Forge stop warning: {e}\n")

            self.forge_process = None
            self.forge_started_by_app = False
        else:
            self.log("Forge status: left running because it was not started by this app.\n")    
    def generation_worker(self, count, theme, upload_each):
        try:
            self.progress_label.config(text="Starting Forge...")
            self.log("\n=== Preparing Forge ===\n")

            # Start Forge once before generating multiple videos.
            self.start_forge_hidden()

            for i in range(1, count + 1):
                if not self.running:
                    break

                self.progress_label.config(text=f"Generating video {i} of {count}")
                self.progress_bar["value"] = int(((i - 1) / count) * 100)

                self.log(f"\n=== Starting video {i} of {count} ===\n")

                cmd = [
                    str(PYTHON_EXE),
                    str(RUN_PIPELINE),
                    "--theme",
                    theme,
                    "--upload",
                    "false",
                    "--skip-forge",
                    "true"
                ]

                process = subprocess.Popen(
                    cmd,
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1
                )

                for line in process.stdout:
                    self.log(line)

                process.wait()

                if process.returncode != 0:
                    self.log(f"\nERROR: Pipeline failed for video {i}.\n")
                    break

                self.log("\nArchiving generated video...\n")
                archived_folder = archive_current_output()
                self.log(f"Archived to: {archived_folder}\n")

                if upload_each:
                    self.upload_folder(archived_folder, from_worker=True)

                self.progress_bar["value"] = int((i / count) * 100)

            self.progress_label.config(text="Completed")
            self.progress_bar["value"] = 100
            self.log("\n=== Generation finished ===\n")

        except Exception as e:
            self.log(f"\nAPP ERROR: {e}\n")
            self.progress_label.config(text="Error")

        finally:
            self.log("\n=== Cleaning up ===\n")
            self.stop_forge_if_started()

            self.running = False
            self.generate_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.refresh_library()

    def build_library_screen(self):
        left = ttk.Frame(self.library_frame)
        left.pack(side="left", fill="y", padx=5, pady=5)

        right = ttk.Frame(self.library_frame)
        right.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        ttk.Label(left, text="Generated Videos").pack(anchor="w")

        self.video_list = tk.Listbox(left, width=45, height=30)
        self.video_list.pack(fill="y", expand=True, pady=5)
        self.video_list.bind("<<ListboxSelect>>", self.on_video_select)

        ttk.Button(left, text="Refresh", command=self.refresh_library).pack(fill="x", pady=3)
        ttk.Button(left, text="Open Folder", command=self.open_selected_folder).pack(fill="x", pady=3)
        ttk.Button(left, text="Open Video", command=self.open_selected_video).pack(fill="x", pady=3)
        ttk.Button(left, text="Upload to YouTube", command=self.upload_selected_video).pack(fill="x", pady=3)
        ttk.Button(left, text="Delete Video", command=self.delete_selected_video).pack(fill="x", pady=3)

        self.detail_text = tk.Text(right, wrap="word")
        self.detail_text.pack(fill="both", expand=True)

        self.library_items = []

    def refresh_library(self):
        self.library_items = []

        for folder in sorted(LIBRARY_DIR.iterdir(), reverse=True):
            if folder.is_dir() and (folder / "manifest.json").exists():
                manifest = load_json(folder / "manifest.json")
                title = manifest.get("title", folder.name)
                self.library_items.append((folder, title))

        self.video_list.delete(0, "end")

        for folder, title in self.library_items:
            self.video_list.insert("end", title)

    def on_video_select(self, event=None):
        selection = self.video_list.curselection()

        if not selection:
            return

        index = selection[0]
        folder, title = self.library_items[index]
        self.selected_folder = folder

        self.show_video_details(folder)

    def show_video_details(self, folder):
        manifest = load_json(folder / "manifest.json")
        metadata = load_json(folder / "current_upload.json")
        story = load_json(folder / "story_package.json")

        lines = []
        lines.append(f"Folder: {folder}\n")
        lines.append(f"Title: {manifest.get('title', '')}\n")
        lines.append(f"Topic: {manifest.get('topic', '')}\n")
        lines.append(f"Created: {manifest.get('created_at', '')}\n")
        lines.append(f"Status: {manifest.get('status', '')}\n")

        if manifest.get("youtube_url"):
            lines.append(f"YouTube URL: {manifest.get('youtube_url')}\n")

        lines.append("\n--- YouTube Metadata ---\n")
        lines.append(f"Title:\n{metadata.get('title', '')}\n\n")
        lines.append(f"Description:\n{metadata.get('description', '')}\n\n")
        lines.append(f"Tags:\n{', '.join(metadata.get('tags', []))}\n\n")

        lines.append("\n--- Narration ---\n")
        lines.append(story.get("narration", ""))

        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("end", "".join(lines))

    def open_selected_folder(self):
        if self.selected_folder:
            os.startfile(self.selected_folder)

    def open_selected_video(self):
        if not self.selected_folder:
            return

        video = self.selected_folder / "final_short.mp4"

        if video.exists():
            os.startfile(video)
        else:
            messagebox.showerror("Missing video", "final_short.mp4 not found.")

    def upload_selected_video(self):
        if not self.selected_folder:
            messagebox.showwarning("No selection", "Select a video first.")
            return

        thread = threading.Thread(
            target=self.upload_folder,
            args=(self.selected_folder,),
            daemon=True
        )
        thread.start()

    def upload_folder(self, folder, from_worker=False):
        try:
            folder = Path(folder)
            video_file = folder / "final_short.mp4"
            metadata_file = folder / "current_upload.json"
            result_file = folder / "youtube_upload_result.json"

            if not video_file.exists():
                raise FileNotFoundError("Video file missing.")
            if not metadata_file.exists():
                raise FileNotFoundError("Upload metadata missing.")

            self.log(f"\nUploading to YouTube: {folder.name}\n")

            cmd = [
                str(PYTHON_EXE),
                str(UPLOAD_SCRIPT),
                "--video-file",
                str(video_file),
                "--metadata-file",
                str(metadata_file),
                "--result-file",
                str(result_file)
            ]

            process = subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )

            output_lines = []

            for line in process.stdout:
                output_lines.append(line)
                self.log(line)

            process.wait()

            if process.returncode != 0:
                raise RuntimeError("YouTube upload failed.")

            result = load_json(result_file)
            manifest_file = folder / "manifest.json"
            manifest = load_json(manifest_file)
            manifest["status"] = "uploaded"
            manifest["youtube_url"] = result.get("video_url", "")
            manifest_file.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            self.log(f"Upload completed: {manifest.get('youtube_url', '')}\n")

            if not from_worker:
                self.refresh_library()
                self.show_video_details(folder)

        except Exception as e:
            self.log(f"\nUPLOAD ERROR: {e}\n")
            if not from_worker:
                messagebox.showerror("Upload failed", str(e))

    def delete_selected_video(self):
        if not self.selected_folder:
            messagebox.showwarning("No selection", "Select a video first.")
            return

        confirm = messagebox.askyesno(
            "Delete video",
            "Are you sure you want to delete this generated video folder?"
        )

        if not confirm:
            return

        shutil.rmtree(self.selected_folder, ignore_errors=True)
        self.selected_folder = None
        self.detail_text.delete("1.0", "end")
        self.refresh_library()


if __name__ == "__main__":
    app = YouTubeAgentApp()
    app.mainloop()