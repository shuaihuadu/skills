"""
Video Creator - Video Build Pipeline
Records HTML animation via Playwright and combines with TTS audio using FFmpeg.

Usage:
    python build_video.py <path-to-video-config.json>

Pipeline:
  1. Verify AI-generated src/index.html exists
  2. Start local HTTP server
  3. Launch headless Chromium, record full animation
  4. Pad + concatenate scene audio
  5. Mux video + audio into final MP4
"""

import asyncio
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Skill asset paths
SKILL_DIR = Path(__file__).parent.parent


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    if "scenes" not in config:
        print("ERROR: config missing 'scenes' array")
        sys.exit(1)
    return config


def check_dependencies():
    """Verify required tools are available."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("ERROR: ffmpeg not found. Install from https://ffmpeg.org/download.html")
        sys.exit(1)
    try:
        from playwright.async_api import async_playwright  # noqa: F401
    except ImportError:
        print("ERROR: playwright not installed. Run:")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)


def setup_project(project_dir: Path, config_path: str):
    """Prepare project's src/ directory.

    Expects AI-generated src/index.html. Exits with error if not found.
    """
    src_dir = project_dir / "src"
    custom_html = src_dir / "index.html"
    if custom_html.exists():
        print("  Using AI-generated src/index.html")
    else:
        print("ERROR: src/index.html not found!")
        print("  AI must generate src/index.html before running build_video.py.")
        print("  See references/HTML-CONTRACT.md for the required conventions.")
        sys.exit(1)

    # Copy config into project root so the HTML can load it as ../video-config.json
    config_in_project = project_dir / "video-config.json"
    if Path(config_path).resolve() != config_in_project.resolve():
        shutil.copy2(config_path, config_in_project)
        print(f"  Copied config → video-config.json")


def start_http_server(root_dir: Path, port: int) -> threading.Thread:
    """Start a local HTTP server in a background thread."""
    os.chdir(root_dir)

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

    httpd = http.server.HTTPServer(("127.0.0.1", port), QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    print(f"  HTTP server at http://127.0.0.1:{port}")
    return thread


def get_scene_durations(config: dict) -> list:
    return [s["duration"] for s in config["scenes"]]


async def record_animation(port: int, total_duration_ms: int, output_dir: Path):
    """Record full HTML animation using Playwright's native video recording."""
    from playwright.async_api import async_playwright

    video_dir = output_dir / "raw_video"
    if video_dir.exists():
        shutil.rmtree(video_dir)
    os.makedirs(video_dir)

    boot_offset_sec = 0.0

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(video_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        url = f"http://127.0.0.1:{port}/src/index.html?headless=true"
        print(f"  Opening {url}")
        t0 = time.monotonic()
        await page.goto(url)

        # Wait for the animation engine to signal playback has started
        await page.wait_for_function(
            "window.__playbackStartedMs !== undefined", timeout=30000
        )
        boot_offset_sec = time.monotonic() - t0
        print(f"  Boot delay: {boot_offset_sec:.2f}s")

        wait_ms = total_duration_ms + 500
        print(f"  Recording for {wait_ms / 1000:.1f}s...")
        await page.wait_for_timeout(wait_ms)

        await context.close()
        await browser.close()

    video_files = list(video_dir.glob("*.webm"))
    if not video_files:
        print("ERROR: No video file recorded!")
        sys.exit(1)

    raw_video = video_files[0]
    print(f"  Raw video: {raw_video} ({raw_video.stat().st_size / 1024 / 1024:.1f} MB)")
    return raw_video, boot_offset_sec


def trim_video_start(raw_video: Path, offset_sec: float, output_dir: Path) -> Path:
    """Trim the beginning of the video to skip the page boot delay."""
    if offset_sec < 0.1:
        return raw_video
    trimmed = output_dir / "trimmed_video.webm"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", f"{offset_sec:.3f}",
            "-i", str(raw_video),
            "-c", "copy",
            str(trimmed),
        ],
        capture_output=True, check=True,
    )
    print(f"  Trimmed {offset_sec:.2f}s from video start")
    return trimmed


def concat_audio(config: dict, project_dir: Path, output_dir: Path) -> Path:
    """Concatenate scene audio, padding each to CONFIG duration."""
    manifest_file = project_dir / "assets" / "audio" / "manifest.json"
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    scene_durations = get_scene_durations(config)
    padded_dir = output_dir / "padded_audio"
    if padded_dir.exists():
        shutil.rmtree(padded_dir)
    os.makedirs(padded_dir)

    for entry in sorted(manifest, key=lambda x: x["scene"]):
        scene_num = entry["scene"]
        audio_path = Path(entry["audio_file"]).resolve()
        target_sec = scene_durations[scene_num - 1] / 1000.0
        padded_path = padded_dir / f"scene_{scene_num}_padded.mp3"

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-af", f"apad=whole_dur={target_sec}",
                "-c:a", "libmp3lame", "-b:a", "192k",
                str(padded_path),
            ],
            capture_output=True, check=True,
        )
        print(f"  Scene {scene_num}: padded to {target_sec}s")

    audio_list = output_dir / "audio_list.txt"
    with open(audio_list, "w", encoding="utf-8") as f:
        for i in range(1, len(scene_durations) + 1):
            padded_path = (padded_dir / f"scene_{i}_padded.mp3").resolve()
            f.write(f"file '{padded_path}'\n")

    combined_audio = output_dir / "combined_audio.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(audio_list),
            "-c:a", "libmp3lame", "-b:a", "192k",
            str(combined_audio),
        ],
        capture_output=True, check=True,
    )
    print(f"  Combined audio: {combined_audio}")
    return combined_audio


def mux_video_audio(raw_video: Path, combined_audio: Path, output_dir: Path) -> Path:
    """Mux video + audio into final MP4."""
    final_output = output_dir / "video.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(raw_video),
            "-i", str(combined_audio),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            str(final_output),
        ],
        capture_output=True, check=True,
    )
    size_mb = final_output.stat().st_size / 1024 / 1024
    print(f"\n{'=' * 60}")
    print(f"  Final video: {final_output}")
    print(f"  Size: {size_mb:.1f} MB")
    print(f"{'=' * 60}")
    return final_output


async def main():
    if len(sys.argv) < 2:
        print("Usage: python build_video.py <path-to-video-config.json>")
        sys.exit(1)

    config_path = os.path.abspath(sys.argv[1])
    config = load_config(config_path)
    project_dir = Path(os.path.dirname(config_path))

    print("=" * 60)
    print("  Video Creator - Build Pipeline")
    print("=" * 60)

    print("\n[1/8] Checking dependencies...")
    check_dependencies()

    print("\n[2/8] Creating timestamped output directory...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = project_dir / "output" / timestamp
    os.makedirs(output_dir, exist_ok=True)
    print(f"  Output: {output_dir}")

    print("\n[3/8] Setting up project files...")
    setup_project(project_dir, config_path)

    print("\n[4/8] Starting HTTP server...")
    port = 8765
    start_http_server(project_dir, port)

    print("\n[5/8] Recording HTML animation...")
    scene_durations = get_scene_durations(config)
    total_ms = sum(scene_durations)
    print(f"  Total duration: {total_ms / 1000:.1f}s ({len(config['scenes'])} scenes)")
    raw_video, boot_offset = await record_animation(port, total_ms, output_dir)

    print("\n[6/8] Trimming boot delay from video...")
    trimmed_video = trim_video_start(raw_video, boot_offset, output_dir)

    print("\n[7/8] Processing audio...")
    combined_audio = concat_audio(config, project_dir, output_dir)

    print("\n[8/8] Producing final MP4...")
    mux_video_audio(trimmed_video, combined_audio, output_dir)

    print("\nDone! 🎬")


if __name__ == "__main__":
    asyncio.run(main())
