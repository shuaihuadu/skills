"""
Video Creator - TTS Audio Generator
Reads video-config.json and generates narration audio + SRT subtitles for each scene.

Usage:
    python generate_tts.py <path-to-video-config.json>
"""

import asyncio
import json
import os
import sys

import edge_tts


def load_config(config_path: str) -> dict:
    """Load and validate video config."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    if "scenes" not in config:
        print("ERROR: config missing 'scenes' array")
        sys.exit(1)
    return config


async def generate_audio(
    scene_num: int, text: str, voice: str, rate: str, volume: str, output_dir: str
) -> dict:
    """Generate TTS audio for a single scene."""
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f"scene_{scene_num}.mp3")
    subtitle_file = os.path.join(output_dir, f"scene_{scene_num}.srt")

    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    subtitles = edge_tts.SubMaker()

    with open(output_file, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                subtitles.feed(chunk)

    with open(subtitle_file, "w", encoding="utf-8") as f:
        f.write(subtitles.get_srt())

    file_size = os.path.getsize(output_file)
    print(f"  Scene {scene_num}: {output_file} ({file_size / 1024:.1f} KB)")

    return {
        "scene": scene_num,
        "audio_file": output_file,
        "subtitle_file": subtitle_file,
        "text": text,
    }


async def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_tts.py <path-to-video-config.json>")
        sys.exit(1)

    config_path = os.path.abspath(sys.argv[1])
    config = load_config(config_path)

    # Voice settings from config or defaults
    voice = config.get("voice", "zh-CN-YunxiNeural")
    rate = config.get("voiceRate", "-5%")
    volume = config.get("voiceVolume", "+0%")

    # Output to assets/audio/ relative to config file location
    project_dir = os.path.dirname(config_path)
    output_dir = os.path.join(project_dir, "assets", "audio")

    print(f"Voice: {voice}  Rate: {rate}")
    print(f"Output: {output_dir}\n")

    results = []
    for i, scene in enumerate(config["scenes"]):
        narration = scene.get("narration", "")
        if not narration.strip():
            print(f"  Scene {i + 1}: (no narration, skipping)")
            continue
        print(f"Processing scene {i + 1}...")
        result = await generate_audio(i + 1, narration, voice, rate, volume, output_dir)
        results.append(result)

    # Save manifest
    manifest_file = os.path.join(output_dir, "manifest.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Generated {len(results)} audio files.")
    print(f"Manifest: {manifest_file}")


if __name__ == "__main__":
    asyncio.run(main())
