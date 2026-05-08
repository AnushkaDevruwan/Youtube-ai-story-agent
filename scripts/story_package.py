import os
import sys
import json
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

ROOT = Path("C:/youtube-agent")
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def clean_json_text(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^```", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        raise ValueError("No JSON object found in Gemini response.")

    return text[start:end + 1]


def generate_story_package(topic: str, research_text: str) -> dict:
    prompt = f"""
You are a factual YouTube Shorts storytelling agent.

Create a complete story package for one YouTube Shorts video.

TOPIC:
{topic}

RESEARCH MATERIAL:
{research_text}

STRICT FACTUAL RULES:
- Do not invent events, names, dates, statistics, places, quotes, or claims.
- Use only facts supported by the research material.
- If a detail is uncertain, phrase it carefully.
- Do not create fake news.
- Do not exaggerate beyond the evidence.
- Do not include claims that are not supported.
- The narration must explain the actual historical, technological, military, scientific, or engineering event itself.
- Do not make the story about search engines, missing pages, redirects, drafts, online encyclopedias, or internet search results unless the topic is specifically about that.
- Keep the story suitable for a 35-60 second YouTube Short.

STYLE:
- Cinematic documentary storytelling.
- Simple spoken English.
- Strong hook in first 3 seconds.
- Clear beginning, middle, and ending.
- Suitable for AI-generated visual reconstruction.
- Avoid overly academic wording.
- Keep the narration punchy and dramatic but truthful.

VISUAL ACCURACY RULES:
- Image prompts must show what actually happened, not symbolic or exaggerated versions.
- If the event was a near miss, failed attack, prevented disaster, or avoided catastrophe, do not depict the disaster as if it actually happened.
- Do not show explosions, fireballs, mushroom clouds, dead bodies, gore, destroyed cities, or apocalyptic scenes unless the researched event clearly involved them.
- Do not show modern computers, futuristic screens, cyberpunk visuals, or abstract digital networks unless the topic is specifically about computing or cybersecurity.
- Do not require readable text inside generated images.
- Do not create fake newspaper headlines, fake UI screens, fake labels, fake signs, or fake maps.
- Prefer physical real-world scenes: locations, machines, vehicles, people, equipment, documents, fields, buildings, control rooms, laboratories, aircraft, ships, recovery operations, and historical environments.
- For every story, create a list of visual elements that must be avoided because they would misrepresent the event.

IMAGE PROMPT RULES:
- Every image prompt must be vertical 9:16.
- Cinematic documentary reconstruction.
- Prefer bright, colorful, clearly lit documentary visuals unless the event specifically requires darkness.
- No text inside the image.
- No subtitles inside the image.
- No logos.
- No watermark.
- No graphic gore.
- Avoid showing exact real-person likeness unless essential.
- Make each scene visually different.
- Keep visuals historically or technically respectful.
- Each image prompt must visualize a specific moment from the narration.
- Each scene should show a different visual moment.
- Avoid repeating the same type of image across scenes.
- Prefer concrete visual details such as machines, maps, locations, historical environments, laboratories, military equipment, documents, infrastructure, close-up action, control rooms, researchers, operators, aircraft, vehicles, fields, wreckage, and specific objects mentioned in narration.
- Do not use vague prompts like "dramatic cyber scene" unless the narration specifically requires it.
- Each image must directly match the scene narration and the video title.
- Avoid generic filler imagery.

Return ONLY valid JSON.
No markdown.
No explanation.

Required JSON structure:

{{
  "topic": "string",
  "video_title": "string",
  "narration": "full spoken narration for the entire video",
  "visual_safety": {{
    "style": "bright, cinematic, realistic documentary reconstruction",
    "must_show": [
      "specific real-world visual elements that should appear in this story"
    ],
    "must_avoid": [
      "specific visuals that would be inaccurate, exaggerated, misleading, or off-topic for this story"
    ]
  }},
  "scenes": [
    {{
      "scene_number": 1,
      "scene_narration": "spoken narration for this scene",
      "image_prompt": "detailed image generation prompt"
    }}
  ],
  "metadata": {{
    "title": "YouTube Shorts title under 100 characters",
    "description": "YouTube description with short summary, AI disclosure note, and source section",
    "tags": ["tag1", "tag2", "tag3"],
    "hashtags": ["#Shorts", "#History", "#Technology"],
    "disclosure_note": "AI-generated visual reconstruction based on publicly available information."
  }},
  "sources": [
    {{
      "name": "source name",
      "url": "source url if available"
    }}
  ],
  "risk_warning": "Mention any uncertainty or content risk. If none, say low risk."
}}

The scenes array must contain exactly 10 scenes.
Each scene should cover a short part of the narration.
Each scene must visually match the exact narration for that scene.
Avoid generic filler scenes.

Important:
For near-disaster stories, the visual_safety.must_avoid list must include the disaster outcome if it did not actually happen.
Example: if a nuclear bomb nearly detonated but did not detonate, must_avoid should include "nuclear explosion", "mushroom cloud", "fireball", and "destroyed city".
"""

    last_error = None

    for attempt in range(1, 6):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            cleaned = clean_json_text(response.text)
            return json.loads(cleaned)

        except Exception as e:
            last_error = e
            print(f"Gemini story package attempt {attempt} failed: {e}", file=sys.stderr)
            time.sleep(15 * attempt)

    raise last_error


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if len(sys.argv) < 2:
        print('Usage: python story_package.py "Topic name"', file=sys.stderr)
        sys.exit(1)

    topic = sys.argv[1]
    research_text = sys.stdin.read()

    if not research_text.strip():
        print("No research text received. Pipe research text into this script.", file=sys.stderr)
        sys.exit(1)

    try:
        package = generate_story_package(topic, research_text)

        output_path = OUTPUT_DIR / "story_package.json"
        output_path.write_text(
            json.dumps(package, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        print(f"story_package.json saved to: {output_path}")
        print(json.dumps(package, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error creating story package: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()