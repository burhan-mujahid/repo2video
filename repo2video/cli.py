"""repo2video: turn any repo into a narrated video. `repo2video . -m engineering`"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import exports
from .analyze import analyze
from .plan import MODES, plan

EXPORTS = ("mp4", "hyperframes", "remotion", "brief")


def fetch(target):
    """Local folder as-is; GitHub URL or owner/repo cloned (full history, no blobs until needed)."""
    if Path(target).is_dir():
        return target
    m = re.fullmatch(r"(?:https?://github\.com/)?([\w.-]+/[\w.-]+?)(?:\.git)?/?", target)
    if not m:
        sys.exit(f"not a folder or GitHub repo: {target}")
    # shortcut: clones stay in the system temp dir (OS cleans it), add a cache if people re-render often
    dest = Path(tempfile.mkdtemp(prefix="repo2video-")) / m.group(1).split("/")[1]
    print(f"cloning {m.group(1)}…", flush=True)
    subprocess.run(["git", "clone", "-q", "--filter=blob:none", f"https://github.com/{m.group(1)}", str(dest)], check=True)
    return str(dest)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="repo2video", description="Turn any repo into a narrated explainer video.",
                                 epilog="modes:\n" + "\n".join(f"  {k:<12} {v[0]}" for k, v in MODES.items()),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", default=".", help="folder, GitHub URL or owner/repo (default: .)")
    ap.add_argument("-m", "--mode", default="marketing", help=f"{' | '.join(MODES)} | all (default: marketing)")
    ap.add_argument("-o", "--out", help="output folder (default: repo2video-out/<name>-<mode>)")
    ap.add_argument("-e", "--export", default="mp4,brief",
                    help=f"comma list of {', '.join(EXPORTS)} or all (default: mp4,brief)")
    ap.add_argument("--story", help="render an edited story.json instead of analyzing the repo")
    ap.add_argument("--plan-only", action="store_true", help="write facts.json and story.json, render nothing")
    ap.add_argument("--no-voice", action="store_true", help="captions only, no narration audio")
    ap.add_argument("--voice", help="override the mode's Kokoro voice, e.g. af_heart, am_michael, bf_emma, am_fenrir")
    a = ap.parse_args(argv)

    want = set(EXPORTS if a.export == "all" else a.export.split(","))
    if want - set(EXPORTS):
        sys.exit(f"unknown export: {', '.join(want - set(EXPORTS))}")
    if a.story:
        story = json.loads(Path(a.story).read_text())
        facts_path = Path(a.story).with_name("facts.json")
        jobs = [(story, json.loads(facts_path.read_text()) if facts_path.exists() else {"name": story["name"]})]
    else:
        facts = analyze(fetch(a.target))
        modes = list(MODES) if a.mode == "all" else [a.mode]
        jobs = [(plan(facts, m), facts) for m in modes]

    for story, facts in jobs:
        t0 = time.time()
        out = Path(a.out if a.out and len(jobs) == 1 else f"repo2video-out/{story['name']}-{story['mode']}")
        if a.story and not a.out:
            out = Path(a.story).parent
        out.mkdir(parents=True, exist_ok=True)
        print(f"{story['name']} / {story['mode']} -> {out}/")
        (out / "facts.json").write_text(json.dumps(facts, indent=1))
        if a.plan_only:
            (out / "story.json").write_text(json.dumps(story, indent=1))
            continue
        from . import render as R
        clips = None
        if not a.no_voice and want & {"mp4", "hyperframes", "remotion"}:
            print("  voice…", flush=True)
            clips = R.narrate(story, a.voice)
        else:
            for s in story["scenes"]:
                s.pop("audio", None)
                s.pop("words", None)
        (out / "story.json").write_text(json.dumps(story, indent=1))
        wav = out / "soundtrack.wav"
        print("  sound + picture…", flush=True)
        if "mp4" in want:
            lay = R.render(story, out, clips)
        else:
            lay = R.layout(story)
            if want & {"hyperframes", "remotion"}:
                R.soundtrack(story, lay, clips, wav)
        times = lay["scenes"]
        made = ["story.json"] + (["video.mp4", "preview.gif"] if "mp4" in want else [])
        if "brief" in want:
            exports.brief(story, facts, times, out, wav)
            made.append("BRIEF.md")
        if "hyperframes" in want:
            exports.hyperframes(story, times, out, wav)
            made.append("hyperframes/")
        if "remotion" in want:
            exports.remotion(story, times, out, wav)
            made.append("remotion/")
        print(f"  done: {exports.total_of(times):.0f}s video · {', '.join(made)} · {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
