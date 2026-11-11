"""Self-check: analyzer facts, the five show formats, pronunciation, beat-synced timing, sound, exports, a short render.
Run: python -m pytest tests  (or: python tests/test_core.py)"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from repo2video import exports, sound
from repo2video.analyze import analyze
from repo2video.plan import MODES, plan
from repo2video.render import layout, render
from repo2video.speech import phonemes, speakable

FILES = {
    "README.md": "# tinycli\n\n![badge](https://x/y.svg)\n\nTinycli turns slow manual release chores into one command, without config.\n\n"
                 "## Features\n\n- Fast: releases in under 3 seconds\n- Safe: never pushes without a clean tree\n\n"
                 "## Install\n\n```sh\npip install tinycli\ntinycli ship\n```\n",
    "pyproject.toml": '[project]\nname = "tinycli"\nversion = "1.2.0"\ndescription = "Ship releases in one command. Cuts manual release chores."\n'
                      '[project.scripts]\ntinycli = "tinycli.cli:main"\n',
    "tinycli/__init__.py": "",
    "tinycli/cli.py": "from tinycli.core import ship\n\n\ndef main():\n    args = parse()\n    ship(args)\n    return 0\n\n\n"
                      "def parse():\n    return []\n",
    "tinycli/core.py": "def ship(args):\n    check_tree()\n    tag = make_tag()\n    print(tag)\n    return tag\n\n\n"
                       "def check_tree():\n    return True\n\n\ndef make_tag():\n    return 'v1'\n",
    "tests/test_cli.py": "def test_x():\n    assert True\n",
    "CHANGELOG.md": "# Changelog\n\n## 1.2.0\n\n- Add dry-run flag (#12)\n- Fix tag order (abc1234f)\n\n## 1.1.0\n\n- Old\n",
    "CONTRIBUTING.md": "# Contributing\n\n- Open an issue before a big change\n",
}


def make_repo():
    root = Path(tempfile.mkdtemp()) / "tinycli"
    for rel, text in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", "https://github.com/acme/tinycli.git"], check=True)
    return root


def said(text):
    return " ".join(s for _, s in speakable(text))


def test_pronunciation():
    # names read their symbols; plain prose keeps punctuation silent
    assert said("Open brief.md and main/skills.") == "Open brief dot M D and main slash skills."
    assert said("See register_all() in src/lib.rs.") == "See register underscore all in source slash lib dot R S."
    assert said("Star github.com/rtk-ai/rtk now.") == "Star github dot com slash R T K dash A I slash R T K now."
    assert said("A high-performance, command-line tool.") == "A high-performance, command-line tool."
    assert said("Pass --dry-run or `npm install`.") == "Pass dash dash dry dash run or N P M install."
    assert said("v0.49.0 cuts ~75% in 25 ms, 10x faster.") == "version 0 point 49 point 0 cuts about 75 percent in 25 milliseconds, 10 times faster."
    # heteronyms by context
    ph = lambda s: phonemes(said(s))
    assert "lˈIv" in ph("Ship it live.") and "lˈIv" in ph("Your app goes live.") and "lˈIv" in ph("A live demo.")
    assert "lˈɪv" in ph("We live in the terminal.") and "lˈɪvz" in ph("Where the code lives.")
    assert "ɹˈɛd" in ph("Have you read it?") and "ɹˈid" in ph("Read the docs.")
    assert "ʌpdˈAt" in ph("Update your config.") and "ˈʌpdˌAt" in ph("The update is out.")
    assert "ɛkspˈɔɹt" in ph("Export the video.") and "ˈɛkspˌɔɹt" in ph("The export is ready.")
    assert "ɹˈisˌɛt" in ph("Do a reset.") and "ɹisˈɛt" in ph("Reset the cache.")
    assert "ɹˈid mˌi" in ph("Open the README.") and "kˈɑnfɪɡ" in ph("Edit the config.")


def test_everything():
    root = make_repo()
    f = analyze(str(root))
    assert f["name"] == "tinycli" and f["slug"] == "acme/tinycli"
    assert (f["entry"]["path"], f["entry"]["start"], f["entry"]["symbol"]) == ("tinycli/cli.py", 4, "main")
    assert [t["symbol"] for t in f["trace"]][:2] == ["main", "ship"] and f["trace"][1]["path"] == "tinycli/core.py"
    assert f["release"]["version"] == "1.2.0" and f["release"]["items"] == ["Add dry-run flag", "Fix tag order"]

    stories = {m: plan(f, m) for m in MODES}
    assert [stories[m]["format"] for m in MODES] == ["trailer", "metro", "quest", "news", "reel"]
    assert stories["social"]["height"] > stories["social"]["width"]
    tr = [s["type"] for s in stories["marketing"]["scenes"]]
    assert tr[0] == "coldopen" and "reveal" in tr and tr[-1] == "credits" and not any("code" in s for s in stories["marketing"]["scenes"])
    stops = [s for s in stories["engineering"]["scenes"] if s["type"] == "stop"]
    assert stops[0]["evidence"] == "tinycli/cli.py:4-7" and stops[0]["highlight"] and "`tinycli/cli.py`" in stops[0]["narration"]
    assert any(s["type"] == "objectives" for s in stories["onboarding"]["scenes"])
    assert "1.2.0" in stories["release"]["scenes"][0]["narration"] and stories["release"]["ticker"]
    for st in stories.values():
        assert all(s["narration"] and "…" not in s["narration"].replace("… ", "") for s in st["scenes"]), st["mode"]

    # timing: cuts on beats, the drop on a bar; cues come from the engine
    st = stories["marketing"]
    lay = layout(st)
    beat = 60 / st["bpm"]
    assert all(abs(t["duration"] / beat - round(t["duration"] / beat)) < 1e-6 for t in lay["scenes"])
    lift = lay["scenes"][st["lift"]]["start"] / (4 * beat)
    assert abs(lift - round(lift)) < 1e-6 and lay["cues"]
    out = Path(tempfile.mkdtemp())
    exports.hyperframes(st, lay["scenes"], out)
    assert "data-no-timeline" in (out / "hyperframes" / "index.html").read_text()
    assert "hf-seek" in (out / "hyperframes" / "compositions" / "film.html").read_text()
    assert (out / "hyperframes" / "assets" / "repo2video-fonts.js").exists()
    exports.remotion(st, lay["scenes"], out)
    assert json.loads((out / "remotion" / "src" / "story.json").read_text())["format"] == "trailer"
    assert "tinycli/cli.py:4-7" in exports.brief(stories["engineering"], f, layout(stories["engineering"])["scenes"], out).read_text()

    # every sound effect the engine can ask for exists
    for c in lay["cues"]:
        assert len(sound.sfx(c["sfx"])) > 0

    short = dict(st, scenes=st["scenes"][:2], lift=0)
    if shutil.which("ffmpeg"):
        lay2 = render(short, out)
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                str(out / "video.mp4")], capture_output=True, text=True).stdout
        assert abs(float(probe) - lay2["duration"]) < 0.15
        assert (out / "preview.gif").stat().st_size > 0 and (out / "soundtrack.wav").exists()


if __name__ == "__main__":
    test_pronunciation()
    test_everything()
    print("ok")
