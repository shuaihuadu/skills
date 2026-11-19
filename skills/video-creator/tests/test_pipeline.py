import json
import array
import subprocess
import sys
import tempfile
import unittest
import re
import shutil
import wave
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import build_video


class TimelineChecks(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.audio = self.root / 'assets' / 'audio'
        self.audio.mkdir(parents=True)
        self.config = {'scenes': [{'narration': '', 'duration': 400},
                                  {'narration': 'Tone', 'duration': 600}]}
        self.srt = self.audio / 'scene_2.srt'
        self.srt.write_text('1\n00:00:00,000 --> 00:00:00,250\nTone\n', encoding='utf-8')
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'sine=frequency=1000:duration=0.3', str(self.audio / 'scene_2.mp3')], check=True)

    def check(self):
        build_video.validate_timeline(self.config, self.root)

    def test_silent_shot_without_assets(self):
        self.check()

    def test_all_silent_generation_and_mix(self):
        for scene in self.config['scenes']:
            scene['narration'] = '  '
        config = self.root / 'video-config.json'
        config.write_text(json.dumps(self.config), encoding='utf-8')
        self.audio.rename(self.root / 'old')
        subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPTS / 'generate_tts.py'), str(config)], check=True)
        self.assertEqual(json.loads((self.audio / 'manifest.json').read_text()), [])
        shutil.copy2(self.root / 'old' / 'scene_2.mp3', self.audio / 'scene_2.mp3')
        self.check()
        mixed = build_video.concat_audio(self.config, self.root, self.root)
        with wave.open(str(mixed)) as audio:
            self.assertEqual(audio.getnframes(), 48000)
            self.assertFalse(any(audio.readframes(48000)))

    def test_missing_and_malformed_subtitles(self):
        self.srt.unlink()
        with self.assertRaisesRegex(ValueError, 'scene_2.srt'):
            self.check()
        self.srt.write_text('1\n00:00:00,000 --> 00:00:00,100\nOK\n\n2\nbroken\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'scene_2.srt'):
            self.check()

    def test_audio_and_subtitle_overrun(self):
        self.config['scenes'][1]['duration'] = 275
        with self.assertRaisesRegex(ValueError, 'scene_2.mp3'):
            self.check()
        self.config['scenes'][1]['duration'] = 600
        self.srt.write_text('1\n00:00:00,000 --> 00:00:00,700\nTone\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'scene_2.srt'):
            self.check()

    def test_hard_limit_and_missing_audio(self):
        self.config['maxDurationMs'] = 999
        with self.assertRaisesRegex(ValueError, 'maxDurationMs'):
            self.check()
        del self.config['maxDurationMs']
        (self.audio / 'scene_2.mp3').unlink()
        with self.assertRaisesRegex(ValueError, 'scene_2.mp3'):
            self.check()

    def test_invalid_build_stops_before_recording(self):
        self.srt.unlink()
        config = self.root / 'video-config.json'
        config.write_text(json.dumps(self.config), encoding='utf-8')
        result = subprocess.run([sys.executable, str(SCRIPTS / 'build_video.py'), str(config)],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('scene_2.srt', result.stderr)
        self.assertFalse((self.root / 'output').exists())

    def test_encoded_flash_and_tone(self):
        config = self.root / 'video-config.json'
        config.write_text(json.dumps(self.config), encoding='utf-8')
        stage = self.root / 'src'
        stage.mkdir()
        (stage / 'index.html').write_text('''<!doctype html><style>html{background:black}</style>
            <script>setTimeout(() => {
                const origin = performance.now(); window.__playbackStartedMs = origin;
                function tick() { const elapsed = performance.now() - origin;
                    document.documentElement.style.background = elapsed >= 400 && elapsed < 700 ? 'white' : 'black';
                    requestAnimationFrame(tick); } tick();
            }, 850)</script>''', encoding='utf-8')
        subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPTS / 'build_video.py'), str(config)], check=True)
        movie, = self.root.glob('output/*/video.mp4')
        streams = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                  '-of', 'json', str(movie)]))['streams']
        video, audio = streams
        self.assertEqual((video['codec_name'], video['width'], video['height'], audio['codec_name']),
                 ('h264', 1920, 1080, 'aac'))
        def decode(options):
            return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(movie), *options, 'pipe:1'])
        frames = decode(['-an', '-vf', 'fps=25,scale=1:1', '-pix_fmt', 'gray', '-f', 'rawvideo'])
        flash = next(index * 40 for index, value in enumerate(frames) if value > 200)
        samples = array.array('h', decode(['-vn', '-ar', '48000', '-ac', '1', '-f', 's16le']))
        tone = next(index / 48 for index, value in enumerate(samples) if abs(value) > 512)
        print(f'Encoded flash={flash} ms, tone={tone:.1f} ms, delta={flash-tone:+.1f} ms')
        self.assertEqual(len(frames), 25)
        self.assertLess(abs(tone - 400), 5)
        self.assertLessEqual(abs(flash - tone), 41)

    def test_browser_caption_contract(self):
        from playwright.sync_api import sync_playwright
        skill = SCRIPTS.parent
        reference = (skill / 'references' / 'HTML-CONTRACT.md').read_text(encoding='utf-8')
        html = re.search(r'```html\n(<!DOCTYPE html>.*?)\n```', reference, re.S).group(1)
        sample = skill / 'assets' / 'prism' / 'src'
        scenes = [{'narration': 'Tone', 'duration': 600}, {'narration': '', 'duration': 600}]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            requests = []
            page.on('request', lambda request: requests.append(request.url))
            page.route('**/src/index.html*', lambda route: route.fulfill(body=html, content_type='text/html'))
            page.route('**/captions.js', lambda route: route.fulfill(path=sample / 'captions.js', content_type='text/javascript'))
            page.route('**/video-config.json', lambda route: route.fulfill(json={'scenes': scenes}))
            page.route('**/scene_1.srt', lambda route: route.fulfill(body=cue_text))
            url = 'http://test.invalid/src/index.html?headless=true'
            cue_text = '1\n00:00:00,000 --> 00:00:00,600\nTone'
            page.goto(url)
            page.wait_for_function("document.querySelector('#subtitle-text').textContent === 'Tone'")
            page.wait_for_function("document.querySelector('#subtitle-text').textContent === ''")
            self.assertFalse(any('scene_2.' in request for request in requests))
            cue_text += '\n\n2\nbroken'
            for html in (html, (sample / 'index.html').read_text(encoding='utf-8')):
                page.goto(url)
                page.wait_for_function('window.__playbackError?.includes("scene_1.srt")')
                self.assertFalse(page.evaluate('Number.isFinite(window.__playbackStartedMs)'))
            browser.close()