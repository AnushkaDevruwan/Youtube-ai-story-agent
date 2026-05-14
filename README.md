# YouTube AI Story Agent

A free, fully local AI pipeline for generating and publishing factual YouTube Shorts — no paid image APIs required.

The app chains together AI research, script writing, image generation, voiceover synthesis, and video assembly into a single automated workflow, with a desktop GUI for managing generation and your video library.

---

## Features

- **Automated pipeline** — topic research → script → images → voiceover → video → YouTube upload
- **Local image generation** — uses Stable Diffusion Forge (no paid API)
- **AI research grounding** — Gemini API with Google Search grounding for factual accuracy
- **Text-to-speech** — Edge TTS (default) or Kokoro TTS
- **Pop captions** — 2-word OpenCV-rendered captions with pop animation
- **Ken Burns effect** — subtle zoom in/out motion on each scene
- **Batch processing** — generate multiple videos in one run
- **Forge lifecycle management** — starts and stops Forge silently in the background, hidden from CMD
- **Video library** — browse, preview, and manage all generated videos
- **YouTube upload** — OAuth-authenticated upload with auto-generated titles, descriptions, tags, and hashtags
- **Per-video archiving** — each video saved with its metadata, narration, images, and story package

---

## How It Works

```
Topic Generator  →  Research Agent  →  Story Package  →  Image Generation
                                                                ↓
YouTube Upload  ←  Upload Metadata  ←  Final Video  ←  Voiceover + Assembly
```

Each step is a standalone script in `/scripts/`, orchestrated by `run_pipeline.py` and managed by the desktop app (`app.py`).

---

## Tech Stack

| Component | Tool |
|---|---|
| AI Research & Scripting | Gemini 2.5 Flash (Google GenAI) |
| Image Generation | Stable Diffusion Forge (local) |
| Text-to-Speech | Edge TTS / Kokoro TTS |
| Video Assembly | MoviePy |
| Caption Rendering | OpenCV (cv2) |
| Desktop GUI | Tkinter |
| YouTube Upload | YouTube Data API v3 |

---

## Project Structure

```
youtube-ai-story-agent/
│
├── app.py                  # Desktop GUI (Generate + Library screens)
├── run_pipeline.py         # CLI pipeline runner
├── start_app.bat           # One-click launcher (Windows)
│
├── scripts/
│   ├── topic_generator.py          # Generates trending factual topic ideas
│   ├── research_agent.py           # Gemini grounded research
│   ├── story_package.py            # Generates full story JSON (narration, scenes, metadata)
│   ├── generate_images.py          # Sends prompts to Stable Diffusion Forge API
│   ├── prepare_narration.py        # Extracts narration text from story package
│   ├── make_voiceover.py           # Generates voiceover audio
│   ├── make_short_from_images.py   # Assembles final video with captions
│   ├── prepare_upload_metadata.py  # Formats YouTube metadata
│   └── upload_youtube.py           # Uploads video via YouTube Data API
│
├── output/                 # Generated story packages, narration, final video
├── audio/                  # Voiceover audio files
├── images/
│   ├── raw/                # Scene images from Stable Diffusion
│   └── final/              # Cropped/resized scene images
├── metadata/               # YouTube upload metadata
├── prompts/                # Example prompt files
│
├── .env.example            # Environment variable template
├── requirements.txt        # Python dependencies
└── README.md
```

---

## Requirements

- Python 3.10+
- [Stable Diffusion WebUI Forge](https://github.com/lllyasviel/stable-diffusion-webui-forge) installed locally
- A Gemini API key ([Google AI Studio](https://aistudio.google.com/))
- A Google Cloud project with YouTube Data API v3 enabled (for upload)
- FFmpeg (required by MoviePy)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/anushkadevruwan/youtube-ai-story-agent.git
cd youtube-ai-story-agent
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Mac/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```env
GEMINI_API_KEY=your_gemini_api_key_here
FORGE_DIR=C:\path\to\stable-diffusion-webui-forge
SD_MODEL=Realistic_Vision_V5.1.safetensors
```

### 5. Set up YouTube upload (optional)

- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Enable the **YouTube Data API v3**
- Create OAuth 2.0 credentials and download as `client_secret.json`
- Place `client_secret.json` in the project root

### 6. Launch the app

```bash
start_app.bat       # Windows (double-click)
# or
python app.py
```

---

## Usage

### Desktop App

1. Open the **Generate** tab
2. Set the number of videos and choose a theme (history, technology, war, etc.)
3. Optionally enable **Upload each video after generation**
4. Click **Generate Videos**
5. Monitor progress in the live log
6. Switch to the **Library** tab to view, preview, or upload completed videos

### CLI (without GUI)

```bash
python run_pipeline.py --theme history --upload false
```

```bash
# Upload enabled
python run_pipeline.py --theme technology --upload true
```

---

## Themes

| Theme | Description |
|---|---|
| `history` | Historical events and turning points |
| `technology` | Engineering breakthroughs and tech stories |
| `war` | Military history and conflicts |
| `cybersecurity` | Cyberattacks, hacking incidents, digital warfare |
| `engineering` | Engineering failures and near-disasters |

---
## Known Issues

- **Caption timing drift** — captions are timed based on estimated word counts per scene
  rather than actual audio alignment, so they can fall out of sync with the voiceover
- **Captions disappear early** — captions stop before the video ends in some cases due
  to the duration estimation cutting off sooner than the audio
- **Inaccurate generated images** — Stable Diffusion occasionally produces images that
  do not match the scene narration, especially for abstract or historical topics where
  visual reference is limited
- **No Whisper/forced alignment** — audio-synced captions are not yet implemented;
  planned as a future improvement
## Content Safety

The pipeline includes built-in factual accuracy guardrails:

- Gemini research uses Google Search grounding to avoid invented facts
- Story prompts explicitly instruct the model not to depict events that did not happen (e.g. no explosions for a near-miss story)
- Image prompts block text, logos, gore, and misleading visuals
- Each story package includes a `visual_safety` block with `must_show` and `must_avoid` lists
- All generated videos include an AI disclosure note in the YouTube description

---

## Notes

- Forge is started silently (hidden CMD window) and kept alive for the full batch
- If Forge is already running when the app starts, it will use the existing instance and leave it running when done
- Generated videos are archived to `~/Documents/YouTubeAgentVideos/` with full metadata
- Used topics are tracked in `output/used_topics.json` to avoid repetition

---

## License

MIT License — free to use, modify, and distribute.

---

> **Disclaimer:** This tool is designed for educational and informational content creation. All generated videos include an AI disclosure note. Users are responsible for verifying factual accuracy before publishing.
