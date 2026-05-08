from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip
)
import json
import re

ROOT = Path("C:/youtube-agent")

IMAGE_DIR = ROOT / "images" / "raw"
AUDIO_FILE = ROOT / "audio" / "voiceover.mp3"
PACKAGE_FILE = ROOT / "output" / "story_package.json"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_VIDEO = OUTPUT_DIR / "final_short.mp4"

VIDEO_W = 1080
VIDEO_H = 1920
FPS = 30


def load_package():
    if PACKAGE_FILE.exists():
        return json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))
    return {}


def get_scene_files():
    files = []

    for i in range(1, 40):
        file = IMAGE_DIR / f"scene{i}.png"
        if file.exists():
            files.append(file)

    if not files:
        raise FileNotFoundError(f"No scene images found in {IMAGE_DIR}")

    return files


def resize_crop_image(image_path, output_path):
    """
    Resizes/crops any image into 1080x1920 for YouTube Shorts.
    """
    img = Image.open(image_path).convert("RGB")
    src_w, src_h = img.size

    target_ratio = VIDEO_W / VIDEO_H
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        new_h = src_h
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, new_h))
    else:
        new_w = src_w
        new_h = int(src_w / target_ratio)
        top = max((src_h - new_h) // 2, 0)
        img = img.crop((0, top, new_w, top + new_h))

    img = img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
    img.save(output_path)


def make_video_clip(image_path, duration, index):
    temp_dir = ROOT / "images" / "final"
    temp_dir.mkdir(parents=True, exist_ok=True)

    fitted_path = temp_dir / f"fitted_scene{index}.png"
    resize_crop_image(image_path, fitted_path)

    clip = ImageClip(str(fitted_path)).set_duration(duration)

    # Slow zoom-in effect
    zoom_strength = 0.055

    def zoom(t):
        return 1 + zoom_strength * (t / duration)

    clip = clip.resize(zoom)
    clip = clip.set_position(("center", "center"))

    background = CompositeVideoClip(
        [clip],
        size=(VIDEO_W, VIDEO_H)
    ).set_duration(duration)

    return background


def clean_caption_text(text):
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[“”]", '"', text)
    text = re.sub(r"[‘’]", "'", text)
    return text


def split_into_chunks(text, max_words=2):
    text = clean_caption_text(text)

    # Remove some punctuation that looks messy in fast captions.
    text = re.sub(r"[,;:]", "", text)

    words = text.split()
    chunks = []

    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words]).strip()
        if chunk:
            chunks.append(chunk)

    return chunks


def get_font(size):
    candidates = [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf"
    ]

    for path in candidates:
        p = Path(path)
        if p.exists():
            return ImageFont.truetype(str(p), size=size)

    return ImageFont.load_default()


def text_size(draw, text, font, stroke_width=0):
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def render_caption_image(text, out_path):
    """
    Creates a transparent PNG caption image.
    Style:
    - Big white first word
    - Yellow highlighted second word
    - Thick black stroke
    - No ImageMagick required
    """
    text = clean_caption_text(text).upper()

    canvas_w = 1000
    canvas_h = 280

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = get_font(96)
    stroke = 7

    words = text.split()

    if not words:
        img.save(out_path)
        return

    if len(words) >= 2:
        first_part = words[0]
        second_part = " ".join(words[1:])
    else:
        first_part = words[0]
        second_part = ""

    y = 82

    if second_part:
        first_text = first_part + " "
        second_text = second_part

        w1, _ = text_size(draw, first_text, font, stroke)
        w2, _ = text_size(draw, second_text, font, stroke)
        total_w = w1 + w2

        # If text is too wide, use smaller font.
        if total_w > 940:
            font = get_font(78)
            w1, _ = text_size(draw, first_text, font, stroke)
            w2, _ = text_size(draw, second_text, font, stroke)
            total_w = w1 + w2
            y = 92

        x = (canvas_w - total_w) // 2

        draw.text(
            (x, y),
            first_text,
            font=font,
            fill="white",
            stroke_width=stroke,
            stroke_fill="black"
        )

        draw.text(
            (x + w1, y),
            second_text,
            font=font,
            fill=(255, 215, 0),
            stroke_width=stroke,
            stroke_fill="black"
        )
    else:
        w, _ = text_size(draw, first_part, font, stroke)

        if w > 940:
            font = get_font(78)
            w, _ = text_size(draw, first_part, font, stroke)
            y = 92

        x = (canvas_w - w) // 2

        draw.text(
            (x, y),
            first_part,
            font=font,
            fill="white",
            stroke_width=stroke,
            stroke_fill="black"
        )

    img.save(out_path)


def apply_pop_effect(clip, duration):
    """
    Quick pop-in animation at the start of each caption.
    """
    pop_duration = min(0.18, duration * 0.35)

    def scale(t):
        if t < pop_duration:
            progress = t / pop_duration

            if progress < 0.5:
                return 0.78 + (0.42 * (progress / 0.5))  # 0.78 -> 1.20
            return 1.20 - (0.20 * ((progress - 0.5) / 0.5))  # 1.20 -> 1.00

        return 1.0

    return clip.resize(scale)


def create_caption_clips(package, total_duration):
    scenes = package.get("scenes", [])
    if not scenes:
        return []

    caption_dir = ROOT / "output" / "captions"
    caption_dir.mkdir(parents=True, exist_ok=True)

    caption_clips = []
    scene_duration = total_duration / len(scenes)
    counter = 1

    for scene_index, scene in enumerate(scenes):
        scene_start = scene_index * scene_duration
        scene_text = scene.get("scene_narration", "").strip()

        if not scene_text:
            continue

        chunks = split_into_chunks(scene_text, max_words=2)

        if not chunks:
            continue

        # Keep captions fast but readable.
        chunk_duration = max(0.45, scene_duration / len(chunks))

        for chunk_index, chunk in enumerate(chunks):
            start_time = scene_start + chunk_index * chunk_duration

            # Do not let captions exceed scene duration.
            if start_time >= scene_start + scene_duration:
                break

            duration = min(
                chunk_duration,
                (scene_start + scene_duration) - start_time
            )

            caption_path = caption_dir / f"caption_{counter}.png"
            render_caption_image(chunk, caption_path)

            caption_clip = (
                ImageClip(str(caption_path))
                .set_start(start_time)
                .set_duration(duration)
                .set_position(("center", 1405))
            )

            caption_clip = apply_pop_effect(caption_clip, duration)

            caption_clips.append(caption_clip)
            counter += 1

    return caption_clips


def main():
    scene_files = get_scene_files()
    package = load_package()

    if not AUDIO_FILE.exists():
        raise FileNotFoundError(f"Missing voiceover file: {AUDIO_FILE}")

    audio = AudioFileClip(str(AUDIO_FILE))
    total_duration = audio.duration

    scene_duration = total_duration / len(scene_files)

    print(f"Audio duration: {total_duration:.2f}s")
    print(f"Scene count: {len(scene_files)}")
    print(f"Duration per scene: {scene_duration:.2f}s")

    clips = []

    for index, image_path in enumerate(scene_files, start=1):
        print(f"Adding image: {image_path.name}")
        clip = make_video_clip(image_path, scene_duration, index)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    video = video.set_duration(total_duration)

    caption_clips = create_caption_clips(package, total_duration)

    if caption_clips:
        print(f"Adding {len(caption_clips)} pop captions...")
        final = CompositeVideoClip([video] + caption_clips, size=(VIDEO_W, VIDEO_H))
        final = final.set_audio(audio)
        final = final.set_duration(total_duration)
    else:
        print("No captions added. Exporting without captions.")
        final = video

    print(f"Exporting final video to: {OUTPUT_VIDEO}")

    final.write_videofile(
        str(OUTPUT_VIDEO),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium"
    )

    print(f"Final video created: {OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()