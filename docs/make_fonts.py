"""Build the bundled fonts: repo2video/fonts.js (embedded in every video) and site/fonts/*.woff.
Downloads the seven fonts from a pinned commit of github.com/google/fonts, subsets them to Latin plus the
punctuation, arrows, box drawing and shapes the engine draws, and writes WOFF with hinting and all OpenType
features kept. The output is byte-for-byte reproducible.
Usage: python docs/make_fonts.py   (needs the dev extra: pip install -e ".[dev]")"""
import base64
import io
import urllib.request
from pathlib import Path

from fontTools import subset

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "https://raw.githubusercontent.com/google/fonts/c30b221beb0c1da59d563feb91ec8656a1fa972a/"
UNICODES = ("U+0020-007E,U+00A0-00FF,U+2010-2027,U+2030-203A,U+20AC,U+2122,U+2190-2199,U+2500-257F,U+25A0-25FF,"
            "U+2605-2606")
# (family, path in google/fonts, CSS font-weight, file in site/fonts or None), in fonts.js order
FONTS = [
    ("Anton", "ofl/anton/Anton-Regular.ttf", "400", None),
    ("Press Start 2P", "ofl/pressstart2p/PressStart2P-Regular.ttf", "400", None),
    ("Space Grotesk", "ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf", "300 700", "SpaceGrotesk.woff"),
    ("JetBrains Mono", "ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf", "100 800", "JetBrainsMono.woff"),
    ("Bebas Neue", "ofl/bebasneue/BebasNeue-Regular.ttf", "400", None),
    ("Permanent Marker", "apache/permanentmarker/PermanentMarker-Regular.ttf", "400", None),
    ("Bricolage Grotesque", "ofl/bricolagegrotesque/BricolageGrotesque%5Bopsz,wdth,wght%5D.ttf", "200 800",
     "BricolageGrotesque.woff"),
]
HEADER = ("/* Bundled fonts (subset to Latin). Anton, Bebas Neue, Press Start 2P, Space Grotesk, JetBrains Mono, "
          "Bricolage Grotesque: SIL OFL 1.1. Permanent Marker: Apache 2.0. */")


def woff(ttf):
    """TrueType bytes -> subset WOFF bytes."""
    opts = subset.Options(flavor="woff", layout_features=["*"])
    font = subset.load_font(io.BytesIO(ttf), opts)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=subset.parse_unicodes(UNICODES))
    sub.subset(font)
    out = io.BytesIO()
    subset.save_font(font, out, opts)
    return out.getvalue()


def script(data):
    """WOFF bytes, one per entry of FONTS -> the text of fonts.js."""
    css = "".join(f"@font-face{{font-family:'{fam}';src:url(data:font/woff;base64,{base64.b64encode(d).decode()}) "
                  f"format('woff');font-weight:{weight};font-display:block}}"
                  for (fam, _, weight, _), d in zip(FONTS, data, strict=True))
    return f'{HEADER}\nglobalThis.Repo2VideoFonts = "{css}";\n'


def main():
    data = []
    for fam, path, _, site in FONTS:
        with urllib.request.urlopen(SOURCE + path, timeout=60) as r:
            data.append(woff(r.read()))
        if site:
            (ROOT / "site" / "fonts" / site).write_bytes(data[-1])
        print(f"{fam}: {len(data[-1]) // 1024} KB")
    (ROOT / "repo2video" / "fonts.js").write_text(script(data))


if __name__ == "__main__":
    main()
