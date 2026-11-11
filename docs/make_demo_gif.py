"""Build docs/demo.gif: a few seconds from each of the five shows, cut together.
Usage: python docs/make_demo_gif.py <repo2video-out folder> <repo name>"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from repo2video.render import layout

# (mode, scene type, seconds into that scene, clip length)
PICKS = [("marketing", "reveal", 0.0, 2.6), ("marketing", "montage", 0.2, 1.8), ("engineering", "network", 0.6, 2.6),
         ("engineering", "stop", 0.2, 2.2), ("onboarding", "objectives", 0.6, 2.6), ("release", "breaking", 0.0, 2.2),
         ("social", "namedrop", 0.0, 2.0)]


def main(root, name):
    root, tmp = Path(root), Path(tempfile.mkdtemp())
    parts = []
    for k, (mode, scene, off, dur) in enumerate(PICKS):
        d = root / f"{name}-{mode}"
        if not d.exists():
            continue
        st = json.loads((d / "story.json").read_text())
        times = layout(st)["scenes"]
        i = next((j for j, s in enumerate(st["scenes"]) if s["type"] == scene), 0)
        pad = "scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2:color=0x111111"
        part = tmp / f"p{k}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{times[i]['start'] + off:.2f}", "-t", str(dur), "-i", str(d / "video.mp4"),
                        "-an", "-vf", f"fps=12,{pad}", str(part)], check=True)
        parts.append(part)
    (tmp / "list.txt").write_text("".join(f"file '{p}'\n" for p in parts))
    out = Path(__file__).parent / "assets" / "demo.gif"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"), "-vf",
                    "split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
                    str(out)], check=True)
    print(out, out.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
