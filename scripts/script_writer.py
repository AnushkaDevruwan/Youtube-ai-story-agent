import os
import sys
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def generate_script(topic, research_text):
    prompt = f"""
You are a factual YouTube Shorts storytelling writer.

Topic:
{topic}

Research material:
{research_text}

Task:
Create a 45-60 second YouTube Shorts script.

Strict rules:
- Do not invent facts.
- Use only information supported by the research material.
- If a detail is uncertain, say it carefully.
- Do not create fake news.
- Do not exaggerate beyond the evidence.
- Make the story engaging, cinematic, and descriptive.
- Use simple spoken English.
- Add a strong hook in the first 3 seconds.
- End with a memorable final sentence.
- If the topic is too long, suggest Part 1, Part 2, Part 3.

Return this exact structure:

TITLE:
...

FACT TABLE:
Claim | Evidence from research | Confidence

SCRIPT:
...

SCENE BREAKDOWN:
Scene 1:
Voiceover:
Visual prompt:

Scene 2:
Voiceover:
Visual prompt:

YOUTUBE METADATA:
Title:
Description:
Keywords:
Hashtags:
Disclosure note:
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text

if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "Stuxnet"

    research_text = sys.stdin.read()

    if not research_text.strip():
        print("Please pipe research text into this script.")
        sys.exit(1)

    result = generate_script(topic, research_text)
    print(result)