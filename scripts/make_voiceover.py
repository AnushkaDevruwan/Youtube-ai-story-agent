import asyncio
from pathlib import Path
import edge_tts

ROOT = Path("C:/youtube-agent")
TEXT_FILE = ROOT / "output" / "narration.txt"
AUDIO_DIR = ROOT / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = AUDIO_DIR / "voiceover.mp3"

# Good voices to try:
# en-US-AndrewNeural
# en-US-GuyNeural
# en-US-AriaNeural
# en-US-JennyNeural
VOICE = "en-US-AndrewNeural"

RATE = "+15%"
VOLUME = "+5%"
PITCH = "+2Hz"


async def main():
    if not TEXT_FILE.exists():
        raise FileNotFoundError(f"Missing narration file: {TEXT_FILE}")

    text = TEXT_FILE.read_text(encoding="utf-8").strip()

    if not text:
        raise ValueError("narration.txt is empty")

    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate=RATE,
        volume=VOLUME,
        pitch=PITCH
    )

    await communicate.save(str(OUTPUT_FILE))

    print(f"Voiceover saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())