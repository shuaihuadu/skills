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
import argparse
import http.server
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
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


def subtitle_end_ms(path: Path) -> int:
    text = path.read_text(encoding="utf-8-sig").strip()
    stamp = r"(\d{2,}):([0-5]\d):([0-5]\d),(\d{3})"
    latest = 0
    for block in re.split(r"\n(?:[ \t]*\n)+", text):
        lines = block.splitlines()
        match = re.fullmatch(stamp + r"\s+-->\s+" + stamp, lines[1]) if len(lines) >= 3 else None
        if not match or not lines[0].isdigit() or not "".join(lines[2:]).strip():
            raise ValueError(f"Invalid subtitle cue in {path}: {block[:80]}")
        times = [((int(hour) * 60 + int(minute)) * 60 + int(second)) * 1000 + int(ms)
                 for hour, minute, second, ms in (match.groups()[:4], match.groups()[4:])]
        if times[0] < latest or times[1] <= times[0]:
            raise ValueError(f"Invalid or overlapping subtitle timing in {path}: {lines[1]}")
        latest = times[1]
    return latest


def validate_timeline(config: dict, project_dir: Path):
    scenes = config.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes must be a non-empty array")
    for number, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict) or not isinstance(scene.get("narration"), str):
            raise ValueError(f"Scene {number}: narration must be a string (empty for silence)")
        duration = scene.get("duration")
        if type(duration) is not int or duration <= 0:
            raise ValueError(f"Scene {number}: duration must be a positive integer in milliseconds")
        if not scene["narration"].strip():
            continue
        base = project_dir / "assets" / "audio" / f"scene_{number}"
        audio, subtitle = base.with_suffix(".mp3"), base.with_suffix(".srt")
        for path in (audio, subtitle):
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Scene {number}: missing or empty {path}")
        last_cue = subtitle_end_ms(subtitle)
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                "stream=duration", "-of", "default=nw=1:nk=1", str(audio)], capture_output=True)
        try:
            audio_ms = math.ceil(float(probe.stdout.strip()) * 1000)
        except (ValueError, OverflowError):
            audio_ms = 0
        if probe.returncode or audio_ms <= 0:
            raise ValueError(f"Scene {number}: cannot read audio duration from {audio}")
        for path, needed in ((audio, audio_ms), (subtitle, last_cue)):
            if needed > duration:
                raise ValueError(f"Scene {number}: {path.name} needs {needed} ms; configured {duration} ms")
    total = sum(get_scene_durations(config))
    limit = config.get("maxDurationMs")
    if "maxDurationMs" in config and (type(limit) is not int or limit <= 0 or total > limit):
        raise ValueError(f"Timeline is {total} ms; maxDurationMs is {limit}. Revise narration or pauses.")
    print(f"Timeline OK: {len(scenes)} scenes, {total} ms")


async def record_animation(port: int, total_duration_ms: int, output_dir: Path):
    """Record full HTML animation using Playwright's native video recording."""
    from playwright.async_api import async_playwright

    video_dir = output_dir / "raw_video"
    if video_dir.exists():
        shutil.rmtree(video_dir)
    os.makedirs(video_dir)

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
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_function(
            "Number.isFinite(window.__playbackStartedMs) || !!window.__playbackError", timeout=30000
        )
        error = await page.evaluate("window.__playbackError")
        if error:
            raise ValueError(f"Page startup failed: {error}")
        await page.wait_for_function("end => performance.now() - window.__playbackStartedMs >= end",
                                     arg=total_duration_ms + 400, timeout=total_duration_ms + 30000)
        slate_elapsed = await page.evaluate('''() => new Promise(resolve => requestAnimationFrame(() => {
            const slate = document.createElement('dialog');
            slate.style.cssText = 'all:initial;position:fixed;inset:0;width:100vw;height:100vh;' +
                'background:linear-gradient(to right,#ff00ff 50%,#00ff00 50%)';
            document.documentElement.append(slate);
            slate.showModal();
            resolve((performance.now() - window.__playbackStartedMs) / 1000);
        }))''')
        await page.wait_for_timeout(400)

        await context.close()
        await browser.close()

    video_files = list(video_dir.glob("*.webm"))
    if not video_files:
        print("ERROR: No video file recorded!")
        sys.exit(1)

    raw_video = video_files[0]
    print(f"  Raw video: {raw_video} ({raw_video.stat().st_size / 1024 / 1024:.1f} MB)")
    return raw_video, recording_offset(raw_video, slate_elapsed)


def recording_offset(raw_video: Path, slate_elapsed: float) -> float:
    """Map the browser playback clock to recorded PTS via the trailing calibration slate."""
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-copyts", "-sseof", "-2", "-i", str(raw_video),
        "-vf", "scale=16:4:flags=neighbor,format=rgb24,showinfo", "-fps_mode", "passthrough",
        "-f", "rawvideo", "pipe:1"], capture_output=True, check=True)
    times = re.findall(rb"\bn:\s*\d+\s+pts:\s*\d+\s+pts_time:([\d.]+)", result.stderr)
    stride = 16 * 4 * 3
    if len(result.stdout) != len(times) * stride:
        raise ValueError("Cannot read recording calibration timestamps")
    first_slate = len(times)
    for frame in reversed(range(len(times))):
        row = frame * stride + 2 * 16 * 3
        red, green, blue = result.stdout[row+12:row+15]
        right_red, right_green, right_blue = result.stdout[row+36:row+39]
        if min(red, blue, right_green) < 200 or max(green, right_red, right_blue) > 55:
            break
        first_slate = frame
    if first_slate == 0 or len(times) - first_slate < 2:
        raise ValueError(f"Cannot identify calibration slate: {first_slate}/{len(times)} frames; "
                 f"last frame RGB samples: {result.stdout[-stride+108:-stride+111].hex()}, "
                 f"{result.stdout[-stride+132:-stride+135].hex()}")
    offset = float(times[first_slate]) - slate_elapsed
    if offset < -0.08:
        raise ValueError(f"Recording starts after playback ({offset:.3f} s); cannot align audio")
    print(f"  Calibrated playback start: {offset:.3f} s")
    return max(0, offset)


def concat_audio(config: dict, project_dir: Path, output_dir: Path) -> Path:
    """Concatenate scene audio, padding each to CONFIG duration."""
    padded_dir = output_dir / "padded_audio"
    if padded_dir.exists():
        shutil.rmtree(padded_dir)
    os.makedirs(padded_dir)

    for scene_num, scene in enumerate(config["scenes"], 1):
        audio_path = project_dir / "assets" / "audio" / f"scene_{scene_num}.mp3"
        source = (["-i", str(audio_path)] if scene["narration"].strip() else
                  ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono"])
        target_sec = scene["duration"] / 1000
        padded_path = padded_dir / f"scene_{scene_num}.wav"

        subprocess.run(
            [
                "ffmpeg", "-y",
                *source, "-af", "apad", "-t", f"{target_sec:.3f}",
                "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le",
                str(padded_path),
            ],
            capture_output=True, check=True,
        )
        print(f"  Scene {scene_num}: padded to {target_sec}s")

    audio_list = output_dir / "audio_list.txt"
    with open(audio_list, "w", encoding="utf-8") as f:
        for number in range(1, len(config["scenes"]) + 1):
            f.write(f"file 'padded_audio/scene_{number}.wav'\n")

    combined_audio = output_dir / "combined_audio.wav"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(audio_list),
            "-c:a", "copy",
            str(combined_audio),
        ],
        capture_output=True, check=True,
    )
    print(f"  Combined audio: {combined_audio}")
    return combined_audio


def mux_video_audio(raw_video: Path, combined_audio: Path, output_dir: Path, offset: float, duration_ms: int) -> Path:
    """Mux video + audio into final MP4."""
    final_output = output_dir / "video.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(raw_video),
            "-i", str(combined_audio),
            "-vf", f"trim=start={offset:.6f},setpts=PTS-STARTPTS", "-t", f"{duration_ms / 1000:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config")
    parser.add_argument("--check", action="store_true", help="Validate the shot timeline without recording")
    args = parser.parse_args()
    config_path = os.path.abspath(args.config)
    config = load_config(config_path)
    project_dir = Path(os.path.dirname(config_path))
    try:
        validate_timeline(config, project_dir)
    except (ValueError, OSError) as error:
        sys.exit(f"ERROR: {error}")
    if args.check:
        return

    print("=" * 60)
    print("  Video Creator - Build Pipeline")
    print("=" * 60)

    print("\n[1/7] Checking dependencies...")
    check_dependencies()

    print("\n[2/7] Creating timestamped output directory...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = project_dir / "output" / timestamp
    os.makedirs(output_dir, exist_ok=True)
    print(f"  Output: {output_dir}")

    print("\n[3/7] Setting up project files...")
    setup_project(project_dir, config_path)

    print("\n[4/7] Starting HTTP server...")
    port = 8765
    start_http_server(project_dir, port)

    print("\n[5/7] Recording HTML animation...")
    scene_durations = get_scene_durations(config)
    total_ms = sum(scene_durations)
    print(f"  Total duration: {total_ms / 1000:.1f}s ({len(config['scenes'])} scenes)")
    raw_video, boot_offset = await record_animation(port, total_ms, output_dir)

    print("\n[6/7] Processing audio...")
    combined_audio = concat_audio(config, project_dir, output_dir)

    print("\n[7/7] Producing final MP4...")
    mux_video_audio(raw_video, combined_audio, output_dir, boot_offset, total_ms)

    print("\nDone! 🎬")


if __name__ == "__main__":
    asyncio.run(main())
