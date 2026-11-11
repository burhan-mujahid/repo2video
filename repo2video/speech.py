"""Text -> how a person would say it -> Kokoro phonemes -> audio with word timings.

Three layers, each fixing what the one below gets wrong:
1. speakable(): names are read with their symbols ("brief.md" -> "brief dot M D", "main/skills" -> "main slash skills"),
   plain prose keeps its punctuation silent; numbers, units, versions and abbreviations become words.
2. misaki G2P with spaCy part-of-speech tags handles most heteronyms (read/read, close/close, use/use, record/record).
3. overrides(): what misaki misses — noun/verb stress pairs (EXport vs exPORT), "ship it live" (laiv),
   "have you read" (red) — plus a lexicon of tech words (config, README, JSON, nginx…).
"""
import importlib
import io
import os
import re
import shutil
import sys
import urllib.request
import zipfile
from functools import lru_cache
from importlib import metadata

# ---------------------------------------------------------------- 1. text -> spoken words

SEP = {".": "dot", "/": "slash", "\\": "backslash", "_": "underscore", "-": "dash", "::": "colon colon", ":": "colon",
       "@": "at", "#": "hash", "~": "tilde", "+": "plus", "=": "equals", "*": "star", "->": "arrow", "=>": "arrow"}
NAME_WORDS = {"src": "source", "cmd": "command", "cmds": "commands", "pkg": "package", "pkgs": "packages",
              "cfg": "config", "ctx": "context", "tmp": "temp", "std": "standard", "stdin": "standard in",
              "stdout": "standard out", "stderr": "standard error", "impl": "impl", "repo": "repo", "dir": "dir",
              "msg": "message", "req": "request", "res": "response", "auth": "auth", "db": "D B", "fn": "F N",
              "num": "num", "str": "string", "eslint": "E S lint", "vite": "veet", "tsconfig": "T S config"}
EXT = {"md": "M D", "mdx": "M D X", "rs": "R S", "js": "J S", "mjs": "M J S", "cjs": "C J S", "ts": "T S", "tsx": "T S X",
       "jsx": "J S X", "py": "P Y", "json": "JSON", "yaml": "YAML", "yml": "YAML", "toml": "TOML", "sh": "S H",
       "html": "H T M L", "css": "C S S", "go": "go", "rb": "R B", "c": "C", "h": "H", "cpp": "C P P", "java": "java",
       "kt": "K T", "swift": "swift", "txt": "text", "lock": "lock", "env": "env", "sql": "S Q L", "svg": "S V G",
       "png": "P N G", "gif": "GIF", "mp4": "M P 4", "wav": "wave", "zip": "zip", "dart": "dart", "vue": "view"}
SHORT_WORDS = {"go", "do", "to", "in", "on", "is", "it", "of", "up", "me", "my", "by", "we", "no", "so", "at", "an",
               "or", "if", "as", "be", "he", "us", "am", "oh", "ok", "hi"}
PHRASES = [(r"\be\.g\.", "for example"), (r"\bi\.e\.", "that is"), (r"\betc\.", "et cetera"), (r"\bvs\.?(?=\s)", "versus"),
           (r"\bw/(?=\s)", "with"), (r"\bapprox\.", "approximately"), (r"\band/or\b", "and or"), (r"\b24/7\b", "24 7"),
           (r"\bI/O\b", "I O"), (r"\bon/off\b", "on off"), (r"\byes/no\b", "yes or no"), (r"\bread/write\b", "read write"),
           (r"(?<=\s)&(?=\s)", "and"), (r"(?<=\s)(?:->|→)(?=\s)", "to"), (r"(?<=\s)[—–](?=\s)", ","), (r"…", ",")]
UNITS = {"%": "percent", "x": "times", "×": "times", "ms": "milliseconds", "s": "seconds", "sec": "seconds",
         "k": "thousand", "K": "thousand", "M": "million", "B": "billion", "kb": "kilobytes", "KB": "kilobytes",
         "mb": "megabytes", "MB": "megabytes", "gb": "gigabytes", "GB": "gigabytes", "TB": "terabytes",
         "fps": "frames per second", "px": "pixels", "min": "minutes", "h": "hours", "LOC": "lines of code"}
CALL = "\x00"


def is_name(core, ticked):
    """Is this token a name (file, path, identifier, package, flag)? Names get their symbols read aloud."""
    if ticked or CALL in core:
        return True
    return bool(re.search(r"[A-Za-z0-9][/\\][A-Za-z0-9._-]", core)          # paths, owner/repo
                or re.search(r"[A-Za-z0-9]\.[A-Za-z]", core)                # file.ext, domain.com, a.b
                or re.search(r"[A-Za-z0-9]_[A-Za-z0-9]", core)              # snake_case
                or "::" in core
                or re.match(r"^(--?|@|\.)[A-Za-z]", core)                    # --flags, @scope, .github
                or re.search(r"[a-z][A-Z]", core))                          # camelCase / PascalCase


def word_parts(w):
    return re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", w)


def say_name(core):
    """'src/lib.rs' -> 'source slash lib dot R S', 'register_all()' -> 'register underscore all'."""
    core = re.sub(r"^[a-z]+://", "", core).replace(CALL, "")
    toks = re.findall(r"::|->|=>|[A-Za-z]+|\d+|[./\\_\-@:#~+=*]", core)
    out = []
    for i, t in enumerate(toks):
        if t in SEP:
            out.append(SEP[t])
            continue
        if not re.match(r"[A-Za-z]", t):
            out.append(t)
            continue
        last_ext = i == len(toks) - 1 and i > 0 and toks[i - 1] == "." and t.lower() in EXT
        if last_ext:
            out.append(EXT[t.lower()])
            continue
        for p in word_parts(t):
            lo = p.lower()
            if lo in NAME_WORDS:
                out.append(NAME_WORDS[lo])
            elif (len(p) == 2 and lo not in SHORT_WORDS) or (len(p) <= 5 and not re.search(r"[aeiouy]", lo)):
                out.append(" ".join(p.upper()))                      # 'ai' -> 'A I', 'rtk' -> 'R T K'
            else:
                out.append(p)
    return " ".join(out)


def say_number(core):
    """Versions, units, ranges and '~' into words. Returns None when the token is not numeric."""
    m = re.fullmatch(r"(v)?(\d+(?:\.\d+){2,3})", core) or re.fullmatch(r"(v)(\d+(?:\.\d+)?)", core)
    if m:
        return ("version " if m.group(1) else "") + " point ".join(m.group(2).split("."))
    m = re.fullmatch(r"(~)?(\d[\d,]*(?:\.\d+)?)(?:\s?[-–]\s?(\d[\d,]*(?:\.\d+)?))?(\+)?(%|x|×|ms|s|sec|k|K|M|B|kb|KB|mb|MB|gb|GB|TB|fps|px|min|h|LOC)?", core)
    if m and (m.group(1) or m.group(3) or m.group(4) or m.group(5)):
        about, a, b, plus, unit = m.groups()
        words = ("about " if about else "") + a.replace(",", "") + (f" to {b.replace(',', '')}" if b else "")
        return words + (" plus" if plus else "") + (f" {UNITS[unit]}" if unit else "")
    m = re.fullmatch(r"#(\d+)", core)
    return f"number {m.group(1)}" if m else None


def speakable(text):
    """Display text -> [(display_token, spoken_text)]. Spoken text keeps prosody punctuation (, . ! ?) only."""
    t = " " + text.replace("()", CALL) + " "
    for pat, rep in PHRASES:
        t = re.sub(pat, rep, t)
    out = []
    for raw in re.findall(r"`[^`]+`[^\s]*|\S+", t):
        ticked = raw.startswith("`")
        m = re.match(r"^`([^`]+)`(.*)$", raw) if ticked else \
            re.match(r"^([\"'“‘(\[{]*)(.*?)([\"'”’)\]}]*[.,!?;:]*[\"'”’)\]}]*)$", raw)
        core, tail = (m.group(1), m.group(2)) if ticked else (m.group(2), m.group(3))
        if core.endswith(".") and is_name(core[:-1], ticked):  # 'brief.md.' : the last dot ends the sentence
            core, tail = core[:-1], "." + tail
        punct = (re.findall(r"[.,!?;:]", tail) or [""])[-1].replace(";", ",").replace(":", ",")
        display = raw.replace(CALL, "()").replace("`", "")
        if not core:
            out.append((display, punct))
            continue
        spoken = say_number(core)
        if spoken is None and out and core in UNITS and len(core) > 1 and re.search(r"\d$", out[-1][1]):
            spoken = UNITS[core]                                     # '25 ms' -> '25 milliseconds'
        if spoken is None:
            spoken = say_name(core) if is_name(core, ticked) else core.replace(CALL, "")
        out.append((display, spoken + punct))
    return out


# ---------------------------------------------------------------- 2+3. spoken words -> phonemes

# noun/adjective form, verb form (misaki notation). misaki often gives one stress for both.
STRESS = {
    "export": ("ˈɛkspˌɔɹt", "ɛkspˈɔɹt"), "import": ("ˈɪmpˌɔɹt", "ɪmpˈɔɹt"), "reset": ("ɹˈisˌɛt", "ɹisˈɛt"),
    "update": ("ˈʌpdˌAt", "ʌpdˈAt"), "upgrade": ("ˈʌpɡɹˌAd", "ʌpɡɹˈAd"), "insert": ("ˈɪnsˌɜɹt", "ɪnsˈɜɹt"),
    "increase": ("ˈɪnkɹˌis", "ɪnkɹˈis"), "decrease": ("dˈikɹˌis", "dikɹˈis"), "object": ("ˈɑbʤˌɛkt", "əbʤˈɛkt"),
    "project": ("pɹˈɑʤˌɛkt", "pɹəʤˈɛkt"), "present": ("pɹˈɛzᵊnt", "pɹizˈɛnt"), "produce": ("pɹˈOdˌus", "pɹədˈus"),
    "progress": ("pɹˈɑɡɹˌɛs", "pɹəɡɹˈɛs"), "permit": ("pˈɜɹmˌɪt", "pəɹmˈɪt"), "convert": ("kˈɑnvˌɜɹt", "kənvˈɜɹt"),
    "extract": ("ˈɛkstɹˌækt", "ɪkstɹˈækt"), "conflict": ("kˈɑnflˌɪkt", "kənflˈɪkt"), "contrast": ("kˈɑntɹˌæst", "kəntɹˈæst"),
    "console": ("kˈɑnsˌOl", "kənsˈOl"), "subject": ("sˈʌbʤˌɛkt", "səbʤˈɛkt"), "refuse": ("ɹˈɛfjˌus", "ɹəfjˈuz"),
    "attribute": ("ˈætɹəbjˌut", "ətɹˈɪbjut"), "record": ("ɹˈɛkəɹd", "ɹəkˈɔɹd"), "rewrite": ("ɹˈiɹˌIt", "ɹiɹˈIt"),
    "redo": ("ɹˈidˌu", "ɹidˈu"), "reboot": ("ɹˈibˌut", "ɹibˈut"), "rerun": ("ɹˈiɹˌʌn", "ɹiɹˈʌn"),
    "download": ("dˈWnlˌOd", "dˈWnlˌOd"), "transfer": ("tɹˈænsfəɹ", "tɹænsfˈɜɹ"), "survey": ("sˈɜɹvˌA", "səɹvˈA"),
    "suspect": ("sˈʌspˌɛkt", "səspˈɛkt"), "address": ("ˈædɹˌɛs", "ədɹˈɛs"), "combine": ("kˈɑmbˌIn", "kəmbˈIn"),
}
PLURALS = {w + "s": (n + "s" if n[-1] not in "sz" else n + "ɪz", v + "s" if v[-1] not in "sz" else v + "ɪz")
           for w, (n, v) in STRESS.items() if not w.endswith("s")}
LEXICON = {
    "config": "kˈɑnfɪɡ", "configs": "kˈɑnfɪɡz", "repo": "ɹˈipO", "repos": "ɹˈipOz", "monorepo": "mˈɑnOɹˌipO",
    "readme": "ɹˈid mˌi", "json": "ʤˈAsᵊn", "yaml": "jˈæmᵊl", "toml": "tˈɑmᵊl", "gif": "ɡˈɪf", "regex": "ɹˈɛʤˌɛks",
    "async": "ˈAsˌɪŋk", "sudo": "sˈudu", "nginx": "ˈɛnʤᵊnˌɛks", "github": "ɡˈɪthˌʌb", "gitlab": "ɡˈɪtlˌæb",
    "kubectl": "kˈub kəntɹˌOl", "linux": "lˈɪnəks", "postgres": "pˈOstɡɹˌɛs", "redis": "ɹˈɛdɪs", "sqlite": "ˌɛs kjˌu ˈɛl ˌIt",
    "oauth": "ˈO ˌɔθ", "wasm": "wˈɑzᵊm", "numpy": "nˈʌmpI", "pypi": "pˈI pˈI", "pytest": "pˈI tˈɛst", "vitest": "vˈi tˈɛst",
    "claude": "klˈɔd", "openai": "ˌOpᵊn ˌA ˈI", "codex": "kˈOdˌɛks", "kokoro": "kˈOkəɹO", "ffmpeg": "ˌɛf ˌɛf ˈɛm pˌɛɡ",
    "deno": "dˈinO", "tauri": "tˈWɹi", "vue": "vjˈu", "svelte": "svˈɛlt", "npx": "ˌɛn pˌi ˈɛks", "npm": "ˌɛn pˌi ˈɛm",
    "pnpm": "pˌi ˌɛn pˌi ˈɛm", "uv": "jˌu vˈi", "uvx": "jˌu vˌi ˈɛks", "cli": "sˌi ˌɛl ˈI", "api": "ˌA pˌi ˈI",
    "apis": "ˌA pˌi ˈIz", "llm": "ˌɛl ˌɛl ˈɛm", "llms": "ˌɛl ˌɛl ˈɛmz", "ui": "jˌu ˈI", "ux": "jˌu ˈɛks", "ci": "sˌi ˈI",
    "env": "ˈɛnv", "init": "ɪnˈɪt", "args": "ˈɑɹɡz", "stdin": "stˈændəɹd ˈɪn", "cron": "kɹˈɑn", "bash": "bˈæʃ",
    "zsh": "zˈi ʃˈɛl", "gpu": "ʤˌi pˌi jˈu", "cpu": "sˌi pˌi jˈu", "ios": "ˌI ˌO ˈɛs", "macos": "mˈæk ˌO ˈɛs",
    "typescript": "tˈIpskɹˌɪpt", "javascript": "ʤˈɑvəskɹˌɪpt", "rust": "ɹˈʌst", "golang": "ɡˈOlˌæŋ", "lol": "ˌɛl ˌO ˈɛl",
    "mcp": "ˌɛm sˌi pˈi", "sdk": "ˌɛs dˌi kˈA", "url": "jˌu ˌɑɹ ˈɛl", "urls": "jˌu ˌɑɹ ˈɛlz", "pr": "pˌi ˈɑɹ", "prs": "pˌi ˈɑɹz",
    "changelog": "ʧˈAnʤlˌɔɡ", "dotfiles": "dˈɑtfˌIlz", "localhost": "lˈOkᵊlhˌOst", "webhook": "wˈɛbhˌʊk",
}
SUBJECTS = {"i", "we", "you", "they", "who", "people", "to", "will", "would", "can", "could", "should", "must", "might",
            "may", "don't", "do", "does", "did", "'ll", "devs", "developers", "users", "teams"}


def _live(prev, tag, lo):
    """'we live in…' / 'to live' / 'where it lives' -> verb (liv); 'goes live', 'ship it live', 'a live demo' -> laiv."""
    if lo in ("lives", "lived", "living"):
        return None if prev in ("the", "our", "their", "your", "his", "her", "my", "save", "saves", "nine") else \
            {"lives": "lˈɪvz", "lived": "lˈɪvd", "living": "lˈɪvɪŋ"}[lo]
    return "lˈɪv" if prev in SUBJECTS else "lˈIv"


def overrides(tokens):
    """Fix misaki where context says otherwise. tokens: misaki MToken list (text, tag, phonemes)."""
    words = [t for t in tokens if t.text.strip()]
    for i, t in enumerate(words):
        lo = t.text.lower()
        prev = words[i - 1].text.lower() if i else ""
        window = {w.text.lower() for w in words[max(0, i - 3):i]}
        verb = (t.tag or "").startswith("VB")
        if lo in LEXICON:
            t.phonemes = LEXICON[lo]
        elif lo in STRESS or lo in PLURALS:
            noun, vb = STRESS.get(lo) or PLURALS[lo]
            # 'the export', 'an update' are nouns even when the tagger hesitates
            t.phonemes = noun if prev in ("the", "a", "an", "this", "that", "every", "each", "your", "our", "its", "new",
                                          "latest", "big", "next", "first") else (vb if verb else noun)
        elif lo in ("live", "lives", "lived", "living"):
            t.phonemes = _live(prev, t.tag, lo) or t.phonemes
        elif lo == "read" and window & {"have", "has", "had", "'ve", "been", "was", "were", "already", "just", "is", "are"}:
            t.phonemes = "ɹˈɛd"
        elif lo == "tear" and verb:
            t.phonemes = "tˈɛɹ"
        elif lo == "wind" and i + 1 < len(words) and words[i + 1].text.lower() in ("up", "down"):
            t.phonemes = "wˈInd"
        elif lo == "bass":
            t.phonemes = "bˈAs"
        elif lo == "lead" and (verb or (i + 1 < len(words) and (words[i + 1].tag or "").startswith("NN"))):
            t.phonemes = "lˈid"
    return tokens


SPACY_MODEL = "en_core_web_sm-3.8.0"  # for spacy 3.8, pinned in pyproject.toml
SPACY_URL = f"https://github.com/explosion/spacy-models/releases/download/{SPACY_MODEL}/{SPACY_MODEL}-py3-none-any.whl"


def ensure_wheel(name, url, cache):
    """Make package `name` importable without pip: if it is not installed, unpack its wheel from `url` into `cache`
    once and put that folder on sys.path. The wheel's .dist-info makes it look installed to spaCy and misaki."""
    try:
        metadata.distribution(name)
        return
    except metadata.PackageNotFoundError:
        pass
    target = cache / url.rsplit("/", 1)[-1].removesuffix(".whl")
    if not target.exists():
        print(f"  downloading {name} (one time)…", flush=True)
        part = target.with_name(target.name + ".part")
        shutil.rmtree(part, ignore_errors=True)
        with urllib.request.urlopen(url, timeout=120) as r:
            zipfile.ZipFile(io.BytesIO(r.read())).extractall(part)
        part.rename(target)
    sys.path.insert(0, str(target))
    importlib.invalidate_caches()


@lru_cache(maxsize=1)
def g2p():
    from .render import CACHE
    ensure_wheel("en_core_web_sm", SPACY_URL, CACHE)
    import espeakng_loader
    from phonemizer.backend.espeak.wrapper import EspeakWrapper
    EspeakWrapper.set_library(espeakng_loader.get_library_path())
    os.environ.setdefault("ESPEAK_DATA_PATH", espeakng_loader.get_data_path())
    from misaki import en, espeak
    return en.G2P(trf=False, british=False, fallback=espeak.EspeakFallback(british=False))


def phonemes(spoken):
    """Spoken sentence -> Kokoro phoneme string, with overrides applied."""
    _, tokens = g2p()(spoken)
    overrides(tokens)
    return "".join((t.phonemes or "") + t.whitespace for t in tokens).strip()


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9`\"'“(])", text.strip()) if s.strip()]


# ---------------------------------------------------------------- audio + word timings

PAUSE = {".": 0.32, "!": 0.34, "?": 0.36, ",": 0.12, "": 0.0}


def synth(tts, text, voice, speed=1.0, sr=24000):
    """Speak text. Returns (samples, words) where words = [{w: display word, t0, t1}] relative to the clip start."""
    import numpy as np
    clips, words, t = [], [], 0.0
    for sent in sentences(text):
        pairs = speakable(sent)
        spoken = " ".join(s for _, s in pairs if s).strip()
        if not spoken.strip(".,!? "):
            continue
        ph = phonemes(spoken)
        audio, _ = tts.create(ph, voice=voice, speed=speed, is_phonemes=True)
        dur = len(audio) / sr
        weights = [max(1, len(re.sub(r"[^a-z0-9]", "", s.lower()))) + (3 if s[-1:] in ".!?," else 0) for _, s in pairs]
        total, acc = sum(weights), 0.0
        for (disp, _), wgt in zip(pairs, weights):
            if not re.search(r"\w", disp):
                acc += wgt
                continue
            words.append({"w": disp, "t0": round(t + dur * acc / total, 3), "t1": round(t + dur * (acc + wgt) / total, 3)})
            acc += wgt
        gap = PAUSE.get(sent.strip()[-1:], 0.2)
        clips += [audio, np.zeros(int(gap * sr), dtype="float32")]
        t += dur + gap
    if not clips:
        return np.zeros(0, dtype="float32"), []
    return np.concatenate(clips[:-1]), words
