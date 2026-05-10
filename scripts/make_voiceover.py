import asyncio
import os
import shutil
import subprocess
from pathlib import Path

import edge_tts
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
TEXT_FILE = ROOT / "output" / "narration.txt"
AUDIO_DIR = ROOT / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = AUDIO_DIR / "voiceover.mp3"

TTS_ENGINE = os.getenv("TTS_ENGINE", "edge").lower().strip()

# Edge TTS settings
EDGE_VOICE = os.getenv("EDGE_VOICE", "en-US-AndrewNeural")
EDGE_RATE = os.getenv("EDGE_RATE", "+15%")
EDGE_VOLUME = os.getenv("EDGE_VOLUME", "+5%")
EDGE_PITCH = os.getenv("EDGE_PITCH", "+2Hz")

# Kokoro settings
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")


def load_narration():
    if not TEXT_FILE.exists():
        raise FileNotFoundError(f"Missing narration file: {TEXT_FILE}")

    text = TEXT_FILE.read_text(encoding="utf-8").strip()

    if not text:
        raise ValueError("narration.txt is empty")

    return text


async def generate_with_edge(text):
    communicate = edge_tts.Communicate(
        text=text,
        voice=EDGE_VOICE,
        rate=EDGE_RATE,
        volume=EDGE_VOLUME,
        pitch=EDGE_PITCH
    )

    await communicate.save(str(OUTPUT_FILE))

    print(f"Voiceover saved with edge_tts: {OUTPUT_FILE}")


def generate_with_kokoro():
    kokoro_exe = shutil.which("kokoro-tts")

    if not kokoro_exe:
        raise RuntimeError(
            "kokoro-tts command not found. Install it with: pip install kokoro-tts"
        )

    cmd = [
        kokoro_exe,
        str(TEXT_FILE),
        str(OUTPUT_FILE),
        "--format",
        "mp3",
        "--voice",
        KOKORO_VOICE
    ]

    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Kokoro TTS failed.\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    print(f"Voiceover saved with Kokoro TTS: {OUTPUT_FILE}")


async def main():
    text = load_narration()

    if TTS_ENGINE == "kokoro":
        try:
            generate_with_kokoro()
            return
        except Exception as e:
            print(f"Kokoro TTS failed, falling back to edge_tts: {e}")

    await generate_with_edge(text)


if __name__ == "__main__":
    asyncio.run(main())