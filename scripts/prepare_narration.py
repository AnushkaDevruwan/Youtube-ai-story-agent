import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILE = ROOT / "output" / "story_package.json"
OUTPUT_FILE = ROOT / "output" / "narration.txt"

def main():
    if not PACKAGE_FILE.exists():
        raise FileNotFoundError(f"Missing story package: {PACKAGE_FILE}")

    package = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))

    narration = package.get("narration", "").strip()

    if not narration:
        raise ValueError("No narration found in story_package.json")

    OUTPUT_FILE.write_text(narration, encoding="utf-8")

    print(f"Narration saved to: {OUTPUT_FILE}")
    print("\nNarration preview:\n")
    print(narration)

if __name__ == "__main__":
    main()