import os
import json
import re
import sys
import random
import time
from dotenv import load_dotenv
from google import genai

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


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

            # Choose one of the top 5 randomly so the channel does not repeat the same style too much
            candidates = topics[:5]
            chosen = random.choice(candidates)

            print(json.dumps(chosen, ensure_ascii=False))
            return

        except Exception as e:
            last_error = e
            print(f"Topic generation attempt {attempt} failed: {e}", file=sys.stderr)
            time.sleep(5 * attempt)

    raise last_error


if __name__ == "__main__":
    main()