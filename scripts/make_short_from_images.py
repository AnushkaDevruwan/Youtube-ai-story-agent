from pathlib import Path
from PIL import Image
from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip
)
import json
import re
import cv2
import numpy as np
import faulthandler
faulthandler.enable()


ROOT = Path(__file__).resolve().parents[1]

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

    clip = (
        ImageClip(str(fitted_path))
        .set_duration(duration)
        .set_position(("center", "center"))
    )

    return clip


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

def render_caption_image(text, out_path):
    """
    Creates a transparent PNG caption image using OpenCV instead of Pillow.
    Style:
    - Big white first word
    - Yellow highlighted remaining words
    - Thick black outline
    - Transparent background
    """
    text = clean_caption_text(text).upper()

    canvas_w = 1000
    canvas_h = 280

    # Transparent BGRA canvas
    img = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)

    if not text.strip():
        cv2.imwrite(str(out_path), img)
        return

    words = text.split()

    if len(words) >= 2:
        first_part = words[0]
        second_part = " ".join(words[1:])
    else:
        first_part = words[0]
        second_part = ""

    first_text = first_part + (" " if second_part else "")
    second_text = second_part

    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 2.4
    thickness = 4
    outline_thickness = 10

    def measure(txt, scale):
        (w, h), baseline = cv2.getTextSize(txt, font, scale, thickness)
        return w, h, baseline

    w1, h1, _ = measure(first_text, font_scale)
    w2, h2, _ = measure(second_text, font_scale) if second_text else (0, 0, 0)
    total_w = w1 + w2

    # Shrink text until it fits
    while total_w > 940 and font_scale > 1.0:
        font_scale -= 0.12
        w1, h1, _ = measure(first_text, font_scale)
        w2, h2, _ = measure(second_text, font_scale) if second_text else (0, 0, 0)
        total_w = w1 + w2

    x = max((canvas_w - total_w) // 2, 20)
    y = 165

    def draw_text_with_outline(image, text_value, pos, text_color):
        px, py = pos

        # black outline
        for dx, dy in [(-2, -2), (-2, 0), (-2, 2),
                       (0, -2),           (0, 2),
                       (2, -2),  (2, 0),  (2, 2)]:
            cv2.putText(
                image,
                text_value,
                (px + dx, py + dy),
                font,
                font_scale,
                (0, 0, 0, 255),
                outline_thickness,
                cv2.LINE_AA
            )

        # main text
        cv2.putText(
            image,
            text_value,
            (px, py),
            font,
            font_scale,
            text_color,
            thickness,
            cv2.LINE_AA
        )

    # Draw first word in white
    draw_text_with_outline(img, first_text, (x, y), (255, 255, 255, 255))

    # Draw second part in yellow
    if second_text:
        draw_text_with_outline(img, second_text, (x + w1, y), (0, 215, 255, 255))  # yellow in BGRA

    cv2.imwrite(str(out_path), img)

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

        chunk_duration = max(0.45, scene_duration / len(chunks))

        for chunk_index, chunk in enumerate(chunks):
            start_time = scene_start + chunk_index * chunk_duration

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

    print("DEBUG: Before concatenate_videoclips", flush=True)
    video = concatenate_videoclips(clips, method="compose")
    print("DEBUG: After concatenate_videoclips", flush=True)

    print("DEBUG: Before set_audio", flush=True)
    video = video.set_audio(audio)
    video = video.set_duration(total_duration)
    print("DEBUG: After set_audio", flush=True)

    print("DEBUG: Before create_caption_clips", flush=True)
    caption_clips = create_caption_clips(package, total_duration)
    print("DEBUG: After create_caption_clips", flush=True)

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
        threads=1,
        preset="ultrafast",
        logger="bar"
    )

    print(f"Final video created: {OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()