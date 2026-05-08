import os
import json
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ROOT = Path("C:/youtube-agent")
PACKAGE_FILE = ROOT / "output" / "story_package.json"
IMAGE_DIR = ROOT / "images" / "raw"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

SD_API_URL = os.getenv("SD_API_URL", "http://127.0.0.1:7861")
TXT2IMG_URL = f"{SD_API_URL}/sdapi/v1/txt2img"
OPTIONS_URL = f"{SD_API_URL}/sdapi/v1/options"

MODEL_NAME = os.getenv("SD_MODEL", "Realistic_Vision_V5.1.safetensors")
WIDTH = int(os.getenv("SD_WIDTH", "448"))
HEIGHT = int(os.getenv("SD_HEIGHT", "768"))
STEPS = int(os.getenv("SD_STEPS", "18"))
CFG_SCALE = float(os.getenv("SD_CFG_SCALE", "7"))
SAMPLER = os.getenv("SD_SAMPLER", "DPM++ 2M Karras")

# General negative prompt for all topics
GLOBAL_NEGATIVE_PROMPT = os.getenv(
    "SD_NEGATIVE_PROMPT",
    "text, subtitles, captions, logo, watermark, signature, fake writing, unreadable text, "
    "bad typography, user interface, website screenshot, search engine page, fake map, "
    "fake newspaper, fake labels, fake signs, blurry, low quality, worst quality, cropped, "
    "duplicate, deformed, bad anatomy, extra fingers, extra hands, disfigured, cartoon, "
    "anime, fantasy, cyberpunk, dark, gloomy, underexposed, murky, monochrome, desaturated, "
    "horror lighting, overly dramatic, exaggerated, inaccurate, misleading, fictional, "
    "graphic gore, dead bodies, blood, disturbing injury"
)


def load_story_package():
    if not PACKAGE_FILE.exists():
        raise FileNotFoundError(f"Missing story package: {PACKAGE_FILE}")

    return json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))


def set_model(model_name: str):
    """
    Tell Forge which checkpoint to use.
    """
    try:
        response = requests.get(OPTIONS_URL, timeout=30)
        response.raise_for_status()
        options = response.json()
        options["sd_model_checkpoint"] = model_name

        set_response = requests.post(OPTIONS_URL, json=options, timeout=60)
        set_response.raise_for_status()

        print(f"Using model: {model_name}")
    except Exception as e:
        print(f"Warning: could not set model automatically: {e}")


def build_negative_prompt(package: dict) -> str:
    visual_safety = package.get("visual_safety", {})
    must_avoid = visual_safety.get("must_avoid", [])

    dynamic_items = []
    if isinstance(must_avoid, list):
        for item in must_avoid:
            item = str(item).strip()
            if item:
                dynamic_items.append(item)

    if dynamic_items:
        return f"{GLOBAL_NEGATIVE_PROMPT}, " + ", ".join(dynamic_items)

    return GLOBAL_NEGATIVE_PROMPT


def build_prompt(scene: dict, package: dict) -> str:
    topic = package.get("topic", "").strip()
    title = package.get("video_title", "").strip()

    visual_safety = package.get("visual_safety", {})
    style = str(
        visual_safety.get(
            "style",
            "bright, cinematic, realistic documentary reconstruction"
        )
    ).strip()

    must_show = visual_safety.get("must_show", [])
    must_avoid = visual_safety.get("must_avoid", [])

    must_show_text = ""
    if isinstance(must_show, list) and must_show:
        must_show_text = ", ".join(str(x).strip() for x in must_show if str(x).strip())

    must_avoid_text = ""
    if isinstance(must_avoid, list) and must_avoid:
        must_avoid_text = ", ".join(str(x).strip() for x in must_avoid if str(x).strip())

    base_prompt = (
        f"{style}. "
        f"Topic: {topic}. "
        f"Video title: {title}. "
        f"Scene number: {scene['scene_number']}. "
        f"Scene narration: {scene['scene_narration']}. "
        f"Create a concrete real-world visual that directly matches this exact scene. "
        f"{scene['image_prompt']} "
    )

    if must_show_text:
        base_prompt += (
            f"Important visual elements to include when relevant: {must_show_text}. "
        )

    if must_avoid_text:
        base_prompt += (
            f"Do not show these inaccurate or misleading elements: {must_avoid_text}. "
        )

    base_prompt += (
        "Prioritize historical and technical accuracy. "
        "Use bright, clear, realistic documentary lighting unless the event clearly requires darkness. "
        "Do not create generic filler imagery. "
        "Do not include readable text, logos, subtitles, or watermarks. "
        "If the event was a near miss or prevented disaster, do not depict the disaster as actually happening."
    )

    return base_prompt


def generate_image(prompt: str, out_path: Path, negative_prompt: str, retries: int = 3):
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "steps": STEPS,
        "cfg_scale": CFG_SCALE,
        "width": WIDTH,
        "height": HEIGHT,
        "sampler_name": SAMPLER,
        "batch_size": 1,
        "n_iter": 1,
        "seed": -1,
        "restore_faces": False,
        "save_images": False
    }

    last_error = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(TXT2IMG_URL, json=payload, timeout=180)
            response.raise_for_status()
            data = response.json()

            images = data.get("images", [])
            if not images:
                raise RuntimeError("Forge returned no images.")

            import base64
            image_bytes = base64.b64decode(images[0])
            out_path.write_bytes(image_bytes)
            return

        except Exception as e:
            last_error = e
            print(f"Attempt {attempt} failed for {out_path.name}: {e}")
            time.sleep(2)

    raise last_error


def main():
    package = load_story_package()

    set_model(MODEL_NAME)

    scenes = package.get("scenes", [])
    if not scenes:
        raise ValueError("No scenes found in story_package.json")

    negative_prompt = build_negative_prompt(package)

    print("\n=== IMAGE GENERATION SETTINGS ===")
    print(f"Model: {MODEL_NAME}")
    print(f"Size: {WIDTH}x{HEIGHT}")
    print(f"Steps: {STEPS}")
    print(f"CFG Scale: {CFG_SCALE}")
    print(f"Sampler: {SAMPLER}")
    print("\nDynamic negative prompt:")
    print(negative_prompt)
    print("=================================\n")

    for scene in scenes:
        scene_number = scene["scene_number"]
        out_path = IMAGE_DIR / f"scene{scene_number}.png"

        prompt = build_prompt(scene, package)

        print(f"Generating scene {scene_number} -> {out_path.name}")
        print(f"Scene prompt preview: {prompt[:300]}...\n")

        generate_image(prompt, out_path, negative_prompt)

    print("All scene images generated successfully.")


if __name__ == "__main__":
    main()