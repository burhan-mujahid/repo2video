"""Build the README and website assets from rendered samples.

Usage: python docs/make_assets.py <repo2video-out folder> <repo name>

Writes docs/assets/{banner,architecture}.png, docs/assets/formats/*.jpg, and site/media/* (web-encoded videos,
posters, og.png). Run after rendering the samples with `repo2video <repo> -m all`.
"""
import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from repo2video.render import browser, layout

ROOT = Path(__file__).resolve().parent.parent
ASSETS, MEDIA, FONTS = ROOT / "docs" / "assets", ROOT / "site" / "media", ROOT / "site" / "fonts"
MODES = {"marketing": "trailer", "engineering": "metro", "onboarding": "quest", "release": "news", "social": "reel"}
STILL = {"trailer": ("reveal", 0.55), "metro": ("network", 0.85), "quest": ("worldmap", 0.7), "news": ("breaking", 0.6),
         "reel": ("reasons", 0.6)}


def ff(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *map(str, args)], check=True)


def font_css():
    faces = [("Bricolage Grotesque", "BricolageGrotesque.woff", "200 800"), ("Space Grotesk", "SpaceGrotesk.woff", "300 700"),
             ("JetBrains Mono", "JetBrainsMono.woff", "100 800")]
    return "".join(f"@font-face{{font-family:'{n}';src:url(data:font/woff;base64,{base64.b64encode((FONTS / f).read_bytes()).decode()});font-weight:{w}}}"
                   for n, f, w in faces)


def data_uri(path):
    return "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def shot(html, out, w, h, scale=2):
    with sync_playwright() as p:
        b = browser(p)
        page = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        page.set_content(html)
        page.evaluate("document.fonts.ready.then(() => true)")
        page.screenshot(path=str(out), type="png")
        b.close()


BASE = """<style>{fonts}
*{{box-sizing:border-box;margin:0}}
body{{background:#07080B;color:#ECEAE4;font-family:'Space Grotesk',sans-serif;-webkit-font-smoothing:antialiased}}
.mono{{font-family:'JetBrains Mono',monospace}}
.disp{{font-family:'Bricolage Grotesque',sans-serif;letter-spacing:-.04em}}
</style>"""

LOGO = """<svg viewBox="0 0 64 64" width="{s}" height="{s}"><rect width="64" height="64" rx="15" fill="#0A0B0F"/><rect x="1" y="1" width="62" height="62" rx="14" fill="none" stroke="#2A2E39" stroke-width="2"/>
<path d="M19 21 8.5 32 19 43" fill="none" stroke="#8A8F9C" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M45 21 55.5 32 45 43" fill="none" stroke="#8A8F9C" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M26 20.5v23L44 32z" fill="#F5B544"/></svg>"""

COLORS = {"trailer": "#F5C451", "metro": "#29C5F6", "quest": "#3DDC84", "news": "#FF4458", "reel": "#FF2E8A"}
NAMES = {"trailer": "Trailer", "metro": "Code Metro", "quest": "The Quest", "news": "Breaking News", "reel": "Vertical Short"}


def banner(stills, out, w=1600, h=720):
    cards = "".join(
        f'<div class="card" style="--r:{r}deg;--x:{x}px;--y:{y}px;z-index:{z}"><img src="{data_uri(stills[k])}"><span><i style="background:{COLORS[k]}"></i>{NAMES[k]}</span></div>'
        for k, r, x, y, z in (("metro", -4, 0, 0, 1), ("quest", 3, 230, 150, 2), ("trailer", -2, 40, 300, 3)))
    chips = "".join(f'<span class="chip"><i style="background:{COLORS[k]}"></i>{NAMES[k]}</span>' for k in MODES.values())
    html = BASE.format(fonts=font_css()) + f"""<style>
.wrap{{width:{w}px;height:{h}px;position:relative;overflow:hidden;background:radial-gradient(60% 80% at 80% 40%,rgba(245,181,68,.13),transparent 70%),#07080B}}
.grid{{position:absolute;inset:0;background-image:linear-gradient(#16181F 1px,transparent 1px),linear-gradient(90deg,#16181F 1px,transparent 1px);background-size:56px 56px;
  -webkit-mask-image:radial-gradient(80% 90% at 30% 50%,#000,transparent 80%)}}
.left{{position:absolute;left:96px;top:0;bottom:0;width:720px;display:flex;flex-direction:column;justify-content:center;gap:30px}}
.brand{{display:flex;align-items:center;gap:16px;font:700 34px 'Bricolage Grotesque';letter-spacing:-.03em}}
.brand em{{font-style:normal;color:#F5B544}}
h1{{font:700 84px/0.98 'Bricolage Grotesque';letter-spacing:-.045em}}
h1 span{{background:linear-gradient(100deg,#fff4d6 10%,#F5B544 55%,#e08a2b 95%);-webkit-background-clip:text;color:transparent}}
p{{font-size:22px;color:#8A8F9C;line-height:1.5;max-width:600px}}
.chips{{display:flex;gap:8px;flex-wrap:nowrap}}
.chip{{display:flex;align-items:center;gap:8px;border:1px solid #2A2E39;background:#0F1117;border-radius:99px;padding:7px 12px;font:500 13px 'JetBrains Mono';white-space:nowrap}}
.chip i{{width:8px;height:8px;border-radius:50%;display:block}}
.stack{{position:absolute;left:880px;top:84px;width:640px;height:560px}}
.card{{position:absolute;left:var(--x);top:var(--y);width:480px;transform:rotate(var(--r));border-radius:14px;padding:8px;background:linear-gradient(180deg,#1a1d26,#0d0f14);border:1px solid #2A2E39;box-shadow:0 30px 80px rgba(0,0,0,.65)}}
.card img{{display:block;width:100%;border-radius:8px}}
.card span{{display:flex;align-items:center;gap:8px;padding:9px 4px 2px;font:500 13px 'JetBrains Mono';color:#8A8F9C}}
.card i{{width:7px;height:7px;border-radius:50%;display:block}}
</style><div class="wrap"><div class="grid"></div>
<div class="left"><div class="brand">{LOGO.format(s=52)}<span>repo<em>2</em>video</span></div>
<h1>Turn any repository<br>into a <span>film.</span></h1>
<p>A script built from facts, a voice that reads code, an original score and frame-exact motion design. Five shows from one command.</p>
<div class="chips">{chips}</div></div>
<div class="stack">{cards}</div></div>"""
    shot(html, out, w, h, 1.5)


def architecture(out, w=1600, h=468):
    steps = [("01", "Analyze", "analyze.py", "README, manifests, lockfiles, CHANGELOG, git log. Entry point, call trace, import graph."),
             ("02", "Plan", "plan.py", "Facts become a show: scenes, narration, on-screen text, each with a source."),
             ("03", "Speak", "speech.py", "Names, numbers, heteronyms, phonemes. Kokoro speech with word timings."),
             ("04", "Lay out", "engine.js", "Timing from measured speech, cuts on the beat, a sound cue per action."),
             ("05", "Score", "sound.py", "Synthesized score and effects, ducking, -14 LUFS master."),
             ("06", "Render", "render.py", "Frame-exact capture in headless Chrome, H.264 and AAC.")]
    cells = "".join(f'<div class="s"><b class="mono">{n}</b><h3>{t}</h3><code class="mono">{m}</code><p>{d}</p></div>' for n, t, m, d in steps)
    outs = "".join(f'<span class="o mono">{x}</span>' for x in ("video.mp4", "HyperFrames", "Remotion", "BRIEF.md"))
    html = BASE.format(fonts=font_css()) + f"""<style>
.wrap{{width:{w}px;height:{h}px;padding:56px 64px;background:#07080B;display:flex;flex-direction:column;gap:30px}}
.row{{display:grid;grid-template-columns:repeat(6,1fr);gap:14px}}
.s{{background:#0F1117;border:1px solid #1E2129;border-radius:16px;padding:22px 20px;position:relative;min-height:250px}}
.s:not(:last-child):after{{content:"";position:absolute;right:-15px;top:40px;width:15px;height:2px;background:#F5B544;opacity:.6}}
.s b{{color:#F5B544;font-size:13px;font-weight:500;letter-spacing:.1em}}
h3{{font:700 26px 'Bricolage Grotesque';letter-spacing:-.02em;margin-top:12px}}
code{{display:block;color:#5C6170;font-size:14px;margin-top:4px}}
.s p{{color:#8A8F9C;font-size:15.5px;line-height:1.5;margin-top:14px}}
.contract{{display:flex;align-items:center;gap:18px;border:1px dashed #2A2E39;border-radius:14px;padding:18px 22px}}
.contract .k{{font:500 14px 'JetBrains Mono';color:#F5B544}}
.contract .t{{color:#8A8F9C;font-size:16px;flex:1}}
.o{{border:1px solid #2A2E39;background:#0F1117;border-radius:8px;padding:7px 12px;font-size:14px}}
</style><div class="wrap"><div class="row">{cells}</div>
<div class="contract"><span class="k">story.json</span><span class="t">The contract between planning and rendering: plain JSON that any renderer, editor or agent can read.</span>{outs}</div></div>"""
    shot(html, out, w, h, 1.5)


SIZZLE = [("marketing", "reveal", 0.0, 3.2), ("marketing", "montage", 0.1, 2.4), ("engineering", "network", 0.8, 3.0),
          ("engineering", "stop", 0.3, 2.6), ("onboarding", "objectives", 0.5, 3.0), ("release", "breaking", 0.0, 3.0),
          ("social", "namedrop", 0.0, 2.6), ("marketing", "credits", 0.4, 3.0)]


def sizzle(root, name, out):
    """A ~23 s cut across the formats, with sound, for the website hero."""
    import tempfile
    tmp, parts = Path(tempfile.mkdtemp()), []
    vf = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x07080B,fps=30"
    for k, (mode, scene, off, dur) in enumerate(SIZZLE):
        d = root / f"{name}-{mode}"
        st = json.loads((d / "story.json").read_text())
        times = layout(st)["scenes"]
        i = next((j for j, sc in enumerate(st["scenes"]) if sc["type"] == scene), 0)
        part = tmp / f"p{k}.mp4"
        ff("-ss", f"{times[i]['start'] + off:.2f}", "-t", dur, "-i", d / "video.mp4", "-vf", vf, "-af", "afade=in:d=0.08,afade=out:st=" + str(dur - 0.15) + ":d=0.15",
           "-c:v", "libx264", "-crf", 24, "-preset", "slow", "-c:a", "aac", "-ar", 48000, "-ac", 2, part)
        parts.append(part)
    (tmp / "list.txt").write_text("".join(f"file '{x}'\n" for x in parts))
    ff("-f", "concat", "-safe", 0, "-i", tmp / "list.txt", "-c", "copy", "-movflags", "+faststart", out)
    ff("-ss", 1.6, "-i", out, "-frames:v", 1, "-q:v", 3, out.with_suffix(".jpg"))


def main(root, name):
    root = Path(root)
    (ASSETS / "formats").mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    stills = {}
    for mode, fmt in MODES.items():
        d = root / f"{name}-{mode}"
        st = json.loads((d / "story.json").read_text())
        times = layout(st)["scenes"]
        scene, frac = STILL[fmt]
        i = next((k for k, s in enumerate(st["scenes"]) if s["type"] == scene), 0)
        t = times[i]["start"] + times[i]["duration"] * frac
        still = ASSETS / "formats" / f"{fmt}.jpg"
        vf = "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x07080B"
        ff("-ss", f"{t:.2f}", "-i", d / "video.mp4", "-frames:v", 1, "-vf", vf, "-q:v", 3, still)
        stills[fmt] = still
        ff("-ss", f"{t:.2f}", "-i", d / "video.mp4", "-frames:v", 1, "-q:v", 3, MEDIA / f"{fmt}.jpg")
        ff("-i", d / "video.mp4", "-c:v", "libx264", "-preset", "slow", "-crf", 27, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
           "-movflags", "+faststart", MEDIA / f"{fmt}.mp4")
    sizzle(root, name, MEDIA / "sizzle.mp4")
    banner(stills, ASSETS / "banner.png")
    architecture(ASSETS / "architecture.png")
    shutil.copy(ASSETS / "banner.png", MEDIA / "og.png")
    print("assets written")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
