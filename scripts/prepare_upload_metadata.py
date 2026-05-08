import json
from pathlib import Path

ROOT = Path("C:/youtube-agent")
PACKAGE_FILE = ROOT / "output" / "story_package.json"
METADATA_DIR = ROOT / "metadata"
METADATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = METADATA_DIR / "current_upload.json"


def main():
    if not PACKAGE_FILE.exists():
        raise FileNotFoundError(f"Missing story package: {PACKAGE_FILE}")

    package = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))
    metadata = package.get("metadata", {})

    title = metadata.get("title") or package.get("video_title") or "AI Story Short"
    description = metadata.get("description", "").strip()
    hashtags = metadata.get("hashtags", [])
    tags = metadata.get("tags", [])

    sources = package.get("sources", [])
    disclosure_note = metadata.get(
        "disclosure_note",
        "AI-generated visual reconstruction based on publicly available information."
    )

    source_text = ""
    if sources:
        source_text += "\n\nSources:\n"
        for source in sources:
            name = source.get("name", "Source")
            url = source.get("url", "")
            source_text += f"- {name}: {url}\n"

    hashtag_text = " ".join(hashtags)

    full_description = (
        f"{description}\n\n"
        f"{disclosure_note}\n"
        f"{source_text}\n"
        f"{hashtag_text}"
    ).strip()

    # YouTube title limit is 100 characters
    title = title[:100]

    payload = {
        "title": title,
        "description": full_description,
        "tags": tags,
        "categoryId": "27",  # Education
        "privacyStatus": "private",
        "selfDeclaredMadeForKids": False
    }

    OUTPUT_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"Upload metadata saved to: {OUTPUT_FILE}")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()