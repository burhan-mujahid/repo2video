"""Hand the same story to other tools: HyperFrames, Remotion, or any agent video skill (BRIEF.md)."""
import json
import shutil
from pathlib import Path

from .plan import MODES
from .render import ENGINE, FONTS

# Which look fits each mode, per tool. lemo-opuscar names are its style folders.
STYLE_HINTS = {
    "marketing": {"lemo-opuscar": ["spy-titles", "dark-keynote", "kino-montage"], "hyperframes": "launch"},
    "engineering": {"lemo-opuscar": ["transit-map", "blueprint", "circuit-board"], "hyperframes": "explainer"},
    "onboarding": {"lemo-opuscar": ["pixel-rpg", "microgame", "hd-2d"], "hyperframes": "explainer"},
    "release": {"lemo-opuscar": ["news-package", "caption-news", "briefing-board"], "hyperframes": "launch"},
    "social": {"lemo-opuscar": ["memphis-diorama", "game-show", "caption-news"], "hyperframes": "vertical"},
}
AUDIENCE = {
    "marketing": "people who might use it; they care about outcomes, not code",
    "engineering": "engineers who want to know how it works inside",
    "onboarding": "a new contributor on their first day",
    "release": "existing users deciding whether to upgrade",
    "social": "people scrolling a feed with the sound off",
}


def total_of(times):
    return times[-1]["start"] + times[-1]["duration"]


def hyperframes(story, times, out_dir, wav=None):
    """A HyperFrames project: one composition that redraws from the hf-seek time, plus the voice track."""
    d = Path(out_dir) / "hyperframes"
    (d / "assets").mkdir(parents=True, exist_ok=True)
    shutil.copy(ENGINE, d / "assets" / "repo2video-engine.js")
    shutil.copy(FONTS, d / "assets" / "repo2video-fonts.js")
    if wav and Path(wav).exists():
        shutil.copy(wav, d / "assets" / "soundtrack.wav")
    total, w, h = round(total_of(times), 3), story["width"], story["height"]
    data = json.dumps(story).replace("</", "<\\/")
    (d / "compositions").mkdir(exist_ok=True)
    (d / "compositions" / "film.html").write_text(f"""<template>
  <style>#root {{ position: absolute; inset: 0; }}</style>
  <div id="root" data-composition-id="film" data-no-timeline data-width="{w}" data-height="{h}"><div id="film-stage"></div></div>
  <script src="assets/repo2video-fonts.js"></script>
  <script src="assets/repo2video-engine.js"></script>
  <script>
    (function () {{
      var video = Repo2Video.createVideo(document.getElementById("film-stage"), {data});
      // seek protocol: every frame is drawn from the time HyperFrames asks for
      window.addEventListener("hf-seek", function (e) {{ video.render(e.detail.time); }});
      video.render(0);
    }})();
  </script>
</template>
""")
    audio = (f'\n      <audio id="soundtrack" class="clip" src="assets/soundtrack.wav" data-start="0" data-duration="{total}" '
             'data-track-index="2" data-volume="1"></audio>') if (d / "assets" / "soundtrack.wav").exists() else ""
    (d / "index.html").write_text(f"""<!doctype html>
<html>
  <body>
    <div id="root" data-composition-id="main" data-no-timeline data-start="0" data-duration="{total}" data-width="{w}" data-height="{h}">
      <div id="film" data-composition-id="film" data-composition-src="compositions/film.html" data-no-timeline data-start="0"
           data-duration="{total}" data-track-index="1" data-track-kind="graphics" data-width="{w}" data-height="{h}"></div>{audio}
    </div>
  </body>
</html>
""")
    (d / "README.md").write_text(f"# {story['name']} — {story['mode']} (HyperFrames project)\n\n"
                                 "```sh\nnpx hyperframes preview   # open in the Studio\nnpx hyperframes render    # write the MP4\n```\n\n"
                                 "Scenes come from `story.json` via `assets/repo2video-engine.js`. Edit the story, "
                                 "re-run `repo2video --story story.json --export hyperframes`, or restyle it with the hyperframes skill.\n")
    return d


def remotion(story, times, out_dir, wav=None):
    """A Remotion project: one component that renders the engine at useCurrentFrame()/fps."""
    d = Path(out_dir) / "remotion"
    (d / "src").mkdir(parents=True, exist_ok=True)
    (d / "public").mkdir(exist_ok=True)
    shutil.copy(ENGINE, d / "src" / "engine.js")
    shutil.copy(FONTS, d / "src" / "fonts.js")
    (d / "src" / "story.json").write_text(json.dumps(story, indent=1))
    has_audio = bool(wav and Path(wav).exists())
    if has_audio:
        shutil.copy(wav, d / "public" / "soundtrack.wav")
    (d / "package.json").write_text(json.dumps({
        "name": f"{story['name']}-{story['mode']}-video".lower().replace(".", "-"), "private": True,
        "scripts": {"studio": "remotion studio src/index.ts", "render": "remotion render src/index.ts Repo2Video out/video.mp4"},
        "dependencies": {"@remotion/cli": "^4.0.0", "remotion": "^4.0.0", "react": "^18.3.1", "react-dom": "^18.3.1"},
        "devDependencies": {"typescript": "^5.4.0", "@types/react": "^18.3.0"}}, indent=2))
    (d / "tsconfig.json").write_text(json.dumps({"compilerOptions": {
        "target": "ES2020", "module": "ESNext", "moduleResolution": "bundler", "jsx": "react-jsx", "strict": True,
        "allowJs": True, "resolveJsonModule": True, "esModuleInterop": True, "skipLibCheck": True}}, indent=2))
    (d / "src" / "index.ts").write_text("import { registerRoot } from 'remotion';\nimport { Root } from './Root';\n\nregisterRoot(Root);\n")
    (d / "src" / "Root.tsx").write_text(f"""import {{ Composition }} from 'remotion';
import './fonts.js';
import './engine.js';
import story from './story.json';
import {{ Film }} from './Film';

const FPS = 30;
const times = (globalThis as any).Repo2Video.timeline(story);
const last = times[times.length - 1];

export const Root = () => (
  <Composition id="Repo2Video" component={{Film}} fps={{FPS}} width={{{story['width']}}} height={{{story['height']}}}
    durationInFrames={{Math.ceil((last.start + last.duration) * FPS)}} />
);
""")
    (d / "src" / "Film.tsx").write_text(f"""import {{ AbsoluteFill, {'Audio, staticFile, ' if has_audio else ''}useCurrentFrame, useVideoConfig }} from 'remotion';
import {{ useLayoutEffect, useRef }} from 'react';
import './fonts.js';
import './engine.js';
import story from './story.json';

// The engine draws any frame from time alone, so Remotion just tells it the time.
export const Film = () => {{
  const host = useRef<HTMLDivElement>(null);
  const video = useRef<any>(null);
  const frame = useCurrentFrame();
  const {{ fps }} = useVideoConfig();
  useLayoutEffect(() => {{
    if (!video.current && host.current) video.current = (globalThis as any).Repo2Video.createVideo(host.current, story);
    video.current?.render(frame / fps);
  }}, [frame, fps]);
  return (
    <AbsoluteFill>
      <div ref={{host}} />{'''
      <Audio src={staticFile('soundtrack.wav')} />''' if has_audio else ''}
    </AbsoluteFill>
  );
}};
""")
    (d / "README.md").write_text(f"# {story['name']} — {story['mode']} (Remotion project)\n\n"
                                 "```sh\nnpm install\nnpm run studio   # preview and edit\nnpm run render   # out/video.mp4\n```\n\n"
                                 "Edit `src/story.json` to change text; the scenes are drawn by `src/engine.js`. "
                                 "Swap `Film.tsx` for your own components if you want a different look; the story stays the contract.\n")
    return d


def brief(story, facts, times, out_dir, wav=None):
    """BRIEF.md: the story as a director's brief that any agent video skill can film in its own style."""
    mode, hints = story["mode"], STYLE_HINTS[story["mode"]]
    total = total_of(times) if times else None
    shape = "9:16 vertical" if story["height"] > story["width"] else "16:9"
    lines = [f"# Video brief: {story['name']} ({mode})", "",
             f"- **Purpose:** {MODES[mode][0]}",
             f"- **Audience:** {AUDIENCE[mode]}",
             f"- **Format:** {story.get('format', '')} · **Music:** {story.get('music', '')} at {story.get('bpm', '')} BPM · **Voice:** {story.get('voice', '')}",
             f"- **Shape:** {shape}" + (f", about {round(total)} seconds" if total else ""),
             f"- **Repo:** {'https://github.com/' + facts['slug'] if facts.get('slug') else facts['name']}",
             f"- **Style ideas:** lemo-opuscar `{'`, `'.join(hints['lemo-opuscar'])}` · HyperFrames type `{hints['hyperframes']}`",
             "", "## Rules", "",
             "- Every fact below comes from the repo. Do not add claims, numbers or features that are not here.",
             "- Code on screen is real: show the file path and line range with it.",
             "- Keep the scene order; rewrite the narration freely, as long as it stays true.",
             "", "## Scenes", "", "| # | Time | Scene | On screen | Narration | Evidence |", "|---|---|---|---|---|---|"]
    for i, s in enumerate(story["scenes"]):
        t = f"{times[i]['start']:.1f}s" if times else ""
        lines.append(f"| {i + 1} | {t} | {s['type']} | {on_screen(s)} | {s.get('narration', '').replace('|', '/')} | {s.get('evidence', '')} |")
    code = [s for s in story["scenes"] if s.get("code")]
    if code:
        lines += ["", "## Code shown (verbatim)", ""]
        for s in code:
            lines += [f"`{s['path']}` lines {s['start']}–{s['end']} (`{s['symbol']}`)", "", "```", s["code"], "```", ""]
    if wav and Path(wav).exists():
        lines += ["", "## Sound", "", "`soundtrack.wav` holds the narration, an original score and sound effects, timed to the "
                  "scene table above. Reuse it, or record your own from the narration column."]
    lines += ["", "## How to film this", "",
              "- **lemo-opuscar:** `/lemo-opuscar:lemo-opuscar`, then: *Make the film in BRIEF.md in the "
              f"{hints['lemo-opuscar'][0]} style.*",
              "- **HyperFrames:** `/hyperframes`, then: *Make the video described in BRIEF.md.* "
              "(or start from the ready project: `repo2video --story story.json --export hyperframes`)",
              "- **Remotion:** `repo2video --story story.json --export remotion` gives a ready project.",
              "- **Any other video skill:** point it at this file and `story.json`.", ""]
    path = Path(out_dir) / "BRIEF.md"
    path.write_text("\n".join(lines))
    return path


def on_screen(s):
    """What the scene shows, in one table cell, whatever its type."""
    parts = []
    for k in ("kicker", "title", "subtitle", "label", "heading", "text", "from", "to", "path"):
        if s.get(k):
            parts.append(f"**{s[k]}**" if k == "title" else str(s[k]))
    for k in ("lines", "items", "starring"):
        if s.get(k):
            parts.append("; ".join(f"`{x}`" if k == "lines" else str(x if isinstance(x, str) else x.get("name", "")) for x in s[k]))
    if s.get("cards"):
        parts.append("; ".join(c["title"] for c in s["cards"]))
    if s.get("stats"):
        parts.append("; ".join(f"**{x['value']}** {x['label']}" for x in s["stats"]))
    if s.get("zones"):
        parts.append("; ".join(f"{z['icon']} {z['zone']} = `{z['name']}`" for z in s["zones"]))
    if s.get("edges"):
        parts.append(", ".join(f"{e['from']}→{e['to']}" for e in s["edges"][:6]))
    return " · ".join(parts).replace("|", "\\|").replace("\n", " ")
