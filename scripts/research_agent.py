import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path("C:/youtube-agent")
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RESEARCH_FILE = OUTPUT_DIR / "research.txt"

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def grounded_research(topic: str) -> str:
    prompt = f"""
You are a factual research assistant for a YouTube Shorts historical storytelling agent.

Research this topic using Google Search grounding:

TOPIC:
{topic}

Task:
Create a factual research brief for a 45-60 second YouTube Short.

Rules:
- Research the actual event, not search result pages.
- Do not discuss whether a webpage exists.
- Do not talk about search engines, redirects, drafts, missing pages, or Wikipedia page availability.
- Use reliable sources where possible: official archives, museums, government documents, credible historical sources, reputable journalism, or encyclopedic sources.
- Do not invent facts.
- Include dates, locations, people/organizations, objects, and consequences if supported.
- If a claim is uncertain or disputed, mark it as uncertain.
- Focus on concrete real-world details that can become visuals.

Return this structure:

TITLE:
A clear factual topic title.

RESEARCH BRIEF:
5-8 bullet points with factual details.

VISUAL FACTS:
5-10 concrete visual elements that should appear in the video.

SOURCE NOTES:
List source names or URLs if available.

DO NOT INCLUDE:
- search result page descriptions
- website UI descriptions
- "page does not exist"
- redirects
- drafts
- generic internet research commentary
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )
    )

    return response.text


def main():
    topic = " ".join(sys.argv[1:]).strip()

    if not topic:
        print('Usage: python research_agent.py "topic name"', file=sys.stderr)
        sys.exit(1)

    try:
        result = grounded_research(topic)

        # Write file directly as UTF-8. This avoids PowerShell encoding corruption.
        RESEARCH_FILE.write_text(result, encoding="utf-8")

        print(result)
        print(f"\nResearch saved to: {RESEARCH_FILE}", file=sys.stderr)

    except Exception as e:
        print(f"Research failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()