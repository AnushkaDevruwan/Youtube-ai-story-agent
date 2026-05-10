import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
OUTPUT = ROOT / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)

PYTHON_EXE = str(ROOT / "venv" / "Scripts" / "python.exe")

SD_API_URL = os.getenv("SD_API_URL", "http://127.0.0.1:7861")
FORGE_DIR = Path(os.getenv("FORGE_DIR", "C:/stable-diffusion-webui-forge"))
FORGE_BAT = os.getenv("FORGE_BAT", "webui-user.bat")
FORGE_BAT_PATH = FORGE_DIR / FORGE_BAT

FORGE_START_TIMEOUT = int(os.getenv("FORGE_START_TIMEOUT", "600"))  # seconds


def is_forge_running():
    try:
        response = requests.get(f"{SD_API_URL}/sdapi/v1/options", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def wait_for_forge(timeout=600):
    print(f"Waiting for Forge API at {SD_API_URL} ...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if is_forge_running():
            print("Forge API is ready.")
            return True
        time.sleep(3)

    return False


def start_forge():
    """
    Starts Forge only if it is not already running.
    Returns:
        proc: subprocess.Popen object or None
        started_by_script: bool
    """
    if is_forge_running():
        print("Forge is already running. The script will use the existing Forge instance.")
        return None, False

    if not FORGE_BAT_PATH.exists():
        raise FileNotFoundError(f"Forge launcher not found: {FORGE_BAT_PATH}")

    print(f"Starting Forge from: {FORGE_BAT_PATH}")

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_CONSOLE

    proc = subprocess.Popen(
        ["cmd", "/c", str(FORGE_BAT_PATH)],
        cwd=str(FORGE_DIR),
        creationflags=creationflags
    )

    ready = wait_for_forge(timeout=FORGE_START_TIMEOUT)
    if not ready:
        stop_process_tree(proc.pid)
        raise RuntimeError("Forge did not become ready in time.")

    return proc, True


def stop_process_tree(pid):
    """
    Kills the Forge batch process and its child processes on Windows.
    """
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            os.kill(pid, 15)
    except Exception as e:
        print(f"Warning: failed to stop process tree for PID {pid}: {e}")


def stop_forge(proc, started_by_script):
    if proc and started_by_script:
        print("Stopping Forge...")
        stop_process_tree(proc.pid)
        time.sleep(2)
        print("Forge stopped.")
    else:
        print("Forge was not started by this script, so it will be left running.")


def run_script(script_name, args=None, input_text=None, live=False):
    if args is None:
        args = []

    script_path = SCRIPTS / script_name

    if not script_path.exists():
        raise FileNotFoundError(f"Missing script: {script_path}")

    cmd = [PYTHON_EXE, str(script_path)] + args

    if live and input_text is None:
        result = subprocess.run(cmd)

        if result.returncode != 0:
            print(f"\nERROR while running: {script_name}")
            sys.exit(1)

        return ""

    result = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode != 0:
        print(f"\nERROR while running: {script_name}")
        print(result.stderr)
        sys.exit(1)

    return result.stdout.strip()


def extract_topic_from_output(output_text):
    """
    Supports:
    1. JSON array: [{"topic": "..."}]
    2. JSON object: {"topic": "..."}
    3. Plain text fallback: first non-empty line
    """
    output_text = output_text.strip()

    if not output_text:
        raise ValueError("Topic generator returned empty output.")

    try:
        data = json.loads(output_text)

        if isinstance(data, list) and len(data) > 0:
            first = data[0]

            if isinstance(first, dict) and "topic" in first:
                return first["topic"].strip()

            if isinstance(first, str):
                return first.strip()

        if isinstance(data, dict) and "topic" in data:
            return data["topic"].strip()

    except Exception:
        pass

    for line in output_text.splitlines():
        line = line.strip()
        if line:
            return line

    raise ValueError("Could not extract topic from topic_generator output.")


def choose_topic(theme):
    print("[1] Generating topic...")

    try:
        output = run_script("topic_generator.py", [theme])
    except Exception:
        output = run_script("topic_generator.py")

    topic = extract_topic_from_output(output)

    topic_file = OUTPUT / "chosen_topic.txt"
    topic_file.write_text(topic, encoding="utf-8")

    print(f"Chosen topic: {topic}")
    print(f"Saved chosen topic to: {topic_file}")

    return topic


def research_topic(topic):
    print("\n[2] Researching topic...")

    research_text = run_script("research_agent.py", [topic])

    research_file = OUTPUT / "research.txt"
    research_file.write_text(research_text, encoding="utf-8")

    print(f"Research saved to: {research_file}")

    return research_text


def generate_story_package(topic, research_text):
    print("\n[3] Generating story package...")

    output = run_script("story_package.py", [topic], input_text=research_text)

    backup_file = OUTPUT / "story_package_console_output.txt"
    backup_file.write_text(output, encoding="utf-8")

    package_file = OUTPUT / "story_package.json"

    if not package_file.exists():
        raise FileNotFoundError(f"Expected file not created: {package_file}")

    print(f"Story package saved to: {package_file}")

    return package_file


def generate_images():
    print("\n[4] Generating images...")

    output = run_script("generate_images.py")
    print(output)


def prepare_narration():
    print("\n[5] Preparing narration...")

    output = run_script("prepare_narration.py")
    print(output)


def make_voiceover():
    print("\n[6] Generating voiceover...")

    output = run_script("make_voiceover.py")
    print(output)


def make_final_video():
    print("\n[7] Creating final video...")

    # Live mode so MoviePy progress is visible
    run_script("make_short_from_images.py", live=True)

    final_video = OUTPUT / "final_short.mp4"

    if not final_video.exists():
        raise FileNotFoundError(f"Final video not found: {final_video}")

    print(f"\nFinal video created successfully: {final_video}")


def prepare_upload_metadata():
    print("\n[8] Preparing YouTube upload metadata...")

    output = run_script("prepare_upload_metadata.py")
    print(output)

    metadata_file = ROOT / "metadata" / "current_upload.json"

    if not metadata_file.exists():
        raise FileNotFoundError(f"Upload metadata not found: {metadata_file}")

    print(f"Upload metadata ready: {metadata_file}")


def upload_to_youtube():
    print("\n[9] Uploading to YouTube...")

    output = run_script("upload_youtube.py")
    print(output)

    result_file = OUTPUT / "youtube_upload_result.json"

    if result_file.exists():
        print(f"YouTube upload result saved to: {result_file}")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--theme",
        default=os.getenv("DEFAULT_THEME", "technology"),
        help="Theme for topic generation, e.g. technology, history, war"
    )

    parser.add_argument(
        "--upload",
        default=os.getenv("UPLOAD_DEFAULT", "false"),
        help="Upload video to YouTube after generation. true/false"
    )
    
    parser.add_argument(
        "--skip-forge",
        default="false",
        help="Skip Forge start/stop because another process already manages it. true/false"
    )

    args = parser.parse_args()
    upload_enabled = str(args.upload).lower() == "true"

    forge_proc = None
    forge_started_by_script = False

    try:
        print("=== YouTube AI Storytelling Pipeline Started ===\n")
        print(f"Theme: {args.theme}")
        print(f"Upload enabled: {upload_enabled}\n")

        if str(args.skip_forge).lower() == "true":
            print("Forge management skipped. App is managing Forge.")
            forge_proc, forge_started_by_script = None, False
        else:
            forge_proc, forge_started_by_script = start_forge()

        topic = choose_topic(args.theme)
        research_text = research_topic(topic)
        generate_story_package(topic, research_text)
        generate_images()
        prepare_narration()
        make_voiceover()
        make_final_video()
        prepare_upload_metadata()

        if upload_enabled:
            upload_to_youtube()
        else:
            print("\nUpload skipped.")
            print("To upload, run:")
            print("python run_pipeline.py --theme technology --upload true")

        print("\n=== Pipeline completed successfully ===")
        print("Final video:")
        print(ROOT / "output" / "final_short.mp4")

    finally:
        stop_forge(forge_proc, forge_started_by_script)


if __name__ == "__main__":
    main()