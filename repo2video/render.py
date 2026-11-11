"""story.json -> MP4 + GIF.
voice (speech.py, Kokoro) -> layout and sound cues (engine.js in Chrome) -> score + mix (sound.py) -> frames -> ffmpeg."""
import json
import math
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ENGINE, FONTS = HERE / "engine.js", HERE / "fonts.js"
CACHE = Path(os.environ.get("REPO2VIDEO_CACHE", Path.home() / ".cache" / "repo2video"))
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MODEL_FILES = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")
VOICE_SR, FPS = 24000, 30


def page_html(story):
    data = json.dumps(story).replace("</", "<\\/")
    return ("<!doctype html><html><head><meta charset='utf-8'><style>html,body{margin:0;background:#000}</style>"
            f"</head><body><div id='root'></div><script>{FONTS.read_text()}</script><script>{ENGINE.read_text()}</script>"
            f"<script>window.video=Repo2Video.createVideo(document.getElementById('root'),{data});</script></body></html>")


def tts_engine():
    try:
        from kokoro_onnx import Kokoro
    except ImportError:
        sys.exit("Voice needs kokoro-onnx: pip install kokoro-onnx   (or pass --no-voice)")
    CACHE.mkdir(parents=True, exist_ok=True)
    for f in MODEL_FILES:
        if not (CACHE / f).exists():
            print(f"  downloading voice model {f} (one time)…", flush=True)
            urllib.request.urlretrieve(MODEL_URL + f, CACHE / (f + ".part"))
            (CACHE / (f + ".part")).rename(CACHE / f)
    return Kokoro(str(CACHE / MODEL_FILES[0]), str(CACHE / MODEL_FILES[1]))


def narrate(story, voice=None):
    """Speak every scene. Stores scene['audio'] (seconds) and scene['words'] (timings) so picture follows voice."""
    from .speech import synth
    tts = tts_engine()
    clips = []
    for s in story["scenes"]:
        samples, words = synth(tts, s.get("narration") or "", voice or story.get("voice", "af_heart"),
                               s.get("voice_speed", story.get("voice_speed", 1.0)))
        s["audio"], s["words"] = round(len(samples) / VOICE_SR, 3), words
        clips.append(samples)
    return clips


def browser(p):
    for launch in (lambda: p.chromium.launch(channel="chrome"), p.chromium.launch):
        try:
            return launch()
        except Exception:
            continue
    sys.exit("No Chrome found. Install one with: python -m playwright install chromium")


def open_page(p, story):
    b = browser(p)
    page = b.new_page(viewport={"width": story["width"], "height": story["height"]})
    page.set_content(page_html(story))
    page.evaluate("document.fonts.ready.then(() => true)")
    layout = page.evaluate("({scenes: video.scenes, cues: video.cues, duration: video.duration})")
    return b, page, layout


def layout(story):
    """Scene timing and sound cues, exactly as the engine computes them."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b, _, lay = open_page(p, story)
        b.close()
    return lay


def soundtrack(story, lay, clips, path):
    """Voice placed at each scene's voice start, the score, the cues; written as 48 kHz stereo WAV."""
    import numpy as np
    import soundfile as sf
    from . import sound
    total = lay["duration"]
    voice = np.zeros(int((total + 1) * VOICE_SR), dtype="float32")
    for clip, tm in zip(clips or [], lay["scenes"]):
        if len(clip):
            at = int(tm["voiceAt"] * VOICE_SR)
            voice[at:at + len(clip)] += clip[: len(voice) - at]
    mix = sound.score(story.get("music", "synthwave"), total, [s["start"] for s in lay["scenes"]], story.get("lift", 0),
                      lay["cues"], voice[: int(total * VOICE_SR)])
    sf.write(path, mix.T, sound.SR)
    return path


def render(story, out_dir, clips=None):
    """Write video.mp4, preview.gif and soundtrack.wav into out_dir. Returns the layout."""
    from playwright.sync_api import sync_playwright
    out_dir = Path(out_dir)
    wav = out_dir / "soundtrack.wav"
    with sync_playwright() as p:
        b, page, lay = open_page(p, story)
        total = lay["duration"]
        soundtrack(story, lay, clips, wav)
        mp4 = out_dir / "video.mp4"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-", "-i", str(wav),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS),
               "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(mp4)]
        frames = math.ceil(total * FPS)
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            for i in range(frames):
                page.evaluate("t => video.render(t)", i / FPS)
                enc.stdin.write(page.screenshot(type="jpeg", quality=90))
                if i % (FPS * 5) == 0:
                    print(f"\r  frames {i}/{frames}", end="", flush=True)
        finally:
            enc.stdin.close()
            enc.wait()
            b.close()
    print(f"\r  frames {frames}/{frames}")
    if enc.returncode:
        sys.exit("ffmpeg failed")
    w, h = story["width"], story["height"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-t", str(min(8, total)), "-i", str(mp4), "-vf",
                    f"fps=10,scale={560 if w >= h else 320}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];"
                    "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle", str(out_dir / "preview.gif")], check=True)
    return lay
