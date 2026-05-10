import os
import json
import re
import sys
import random
import time
from dotenv import load_dotenv
from google import genai
from pathlib import Path
load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

USED_TOPICS_FILE = OUTPUT_DIR / "used_topics.json"


def load_used_topics():
    if not USED_TOPICS_FILE.exists():
        return []

    try:
        return json.loads(USED_TOPICS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_used_topic(topic):
    used_topics = load_used_topics()

    if topic not in used_topics:
        used_topics.append(topic)

    USED_TOPICS_FILE.write_text(
        json.dumps(used_topics, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

def clean_json_text(text):
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```json", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"^```", "", text).strip()
        text = re.sub(r"```$", "", text).strip()

    start = text.find("[")
    end = text.rfind("]")

    if start != -1 and end != -1:
        return text[start:end + 1]

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:
        return text[start:end + 1]

    raise ValueError("No JSON found in Gemini response")


def generate_topics(theme):
    prompt = f"""
You are a YouTube Shorts topic research agent.

Generate 10 factual storytelling video ideas for this theme:

THEME:
{theme}

Channel niche:
- True stories
- History
- War history
- Technology
- Cybersecurity
- Engineering failures
- Hidden real events
- Near disasters
- Cold War incidents
- Military accidents
- Scientific accidents

Rules:
- Do not invent stories.
- Prefer stories that can be verified from reliable sources.
- Avoid breaking news unless it can be verified.
- Each idea must have strong hook potential.
- Each idea should be suitable for a 45-60 second Short.
- Avoid vague topics.
- Use specific event names.

Return ONLY valid JSON.
No markdown.
No explanation.

Required format:
[
  {{
    "topic": "specific factual event title",
    "why_it_may_trend": "short reason",
    "visual_potential": "short reason",
    "risk_level": "low/medium/high",
    "suggested_angle": "short angle"
  }}
]
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    cleaned = clean_json_text(response.text)
    return json.loads(cleaned)


def main():
    theme = " ".join(sys.argv[1:]).strip() or "history"

    # Simple retry for Gemini temporary overloads
    last_error = None

    for attempt in range(1, 4):
        try:
            topics = generate_topics(theme)

            if not isinstance(topics, list) or not topics:
                raise ValueError("Topic list is empty")

            # Choose one of the top 5 randomly, but avoid previously used topics
            used_topics = set(load_used_topics())

            candidates = [
                topic for topic in topics[:5]
                if topic.get("topic", "").strip() not in used_topics
            ]

            # If all top 5 were already used, fall back to the full list
            if not candidates:
                candidates = [
                    topic for topic in topics
                    if topic.get("topic", "").strip() not in used_topics
                ]

            # If everything was used, reset naturally by allowing all topics again
            if not candidates:
                candidates = topics[:5]

            chosen = random.choice(candidates)
            chosen_topic = chosen.get("topic", "").strip()

            if chosen_topic:
                save_used_topic(chosen_topic)

            print(json.dumps(chosen, ensure_ascii=False))
            return

        except Exception as e:
            last_error = e
            print(f"Topic generation attempt {attempt} failed: {e}", file=sys.stderr)
            time.sleep(5 * attempt)

    raise last_error


if __name__ == "__main__":
    main()