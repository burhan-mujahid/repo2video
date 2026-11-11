"""Facts -> story.json. Each mode is a show format with its own script, look, music, voice and sound.

  marketing   -> TRAILER  a movie trailer: cold open, the problem, the title slam, the montage, the credits
  engineering -> METRO    a ride on the code's subway: ticket, city map, network map, one stop per function
  onboarding  -> QUEST    a video game: title screen, objectives with XP, world map, boss fight, level complete
  release     -> NEWS     a breaking-news broadcast: LIVE bug, headlines, the numbers, sign-off, a ticker
  social      -> REEL     a 9:16 short: hook, three reasons, the number, try it, follow

story.json is the contract every renderer reads. Names in narration go in backticks so the voice reads their symbols.
Every line is built from facts; nothing is invented.
"""
import re
import zlib

MODES = {
    # mode: (purpose, format, w, h, music, voice, speed)
    "marketing": ("Launch or promo, cut like a movie trailer: the problem, the title slam, outcomes, proof, the credits.",
                  "trailer", 1280, 720, "trailer", "am_fenrir", 0.92),
    "engineering": ("Under the hood, as a subway ride: city map, network map from real imports, one stop per function call.",
                    "metro", 1280, 720, "synthwave", "am_michael", 1.0),
    "onboarding": ("First day for a contributor, as a video game quest: objectives with XP, world map, boss fight.",
                   "quest", 1280, 720, "chiptune", "af_heart", 1.04),
    "release": ("What's new, as a breaking-news broadcast: headlines, the numbers, how to upgrade.",
                "news", 1280, 720, "news", "bf_emma", 1.0),
    "social": ("A 9:16 short under 30 seconds: hook, three reasons, the number, try it.",
               "reel", 720, 1280, "trap", "af_bella", 1.12),
}

KINDS = ["CLI proxy", "CLI", "library", "framework", "toolkit", "tool", "engine", "server", "proxy", "plugin", "extension",
         "agent", "skill", "app", "platform", "SDK", "API", "compiler", "runtime", "editor", "database", "bot", "system"]
ZONES = {  # onboarding world map: folder hint -> place in the game world (icon names from engine.js ICONS)
    "tests": ("Testing Grounds", "flask"), "source code": ("The Forge", "anvil"), "library code": ("The Core Keep", "castle"),
    "documentation": ("The Library", "book"), "examples": ("Training Village", "house"), "CI workflows": ("Robot Factory", "robot"),
    "scripts": ("Tool Shed", "toolbox"), "assets": ("Treasure Vault", "gem"), "benchmarks": ("Speed Track", "flag"),
    "hooks": ("Hook Harbor", "anchor"), "agent skills": ("Skill Tree", "tree"), "executables": ("Launch Pad", "rocket"),
    "commands": ("Command Tower", "tower"), "packages": ("Market Square", "box"), "Rust crates": ("Crate Docks", "crate"),
    "apps": ("App City", "city"), "UI components": ("Pixel Gardens", "flower"), "API": ("Gateway", "gate"),
}
WILD = [("Mystery Woods", "pine"), ("Crystal Caves", "crystal"), ("Dragon Peak", "mountain"), ("Sunken Ruins", "columns"),
        ("Lava Fields", "flame"), ("Cloud Isle", "cloud"), ("Frozen Lake", "drop")]


# ---------------------------------------------------------------- helpers

def pick(seed, options):
    """Deterministic variety: the same repo always gets the same line, different repos get different ones."""
    return options[zlib.crc32(seed.encode()) % len(options)]


def sentence(s):
    s = re.sub(r"^(?:[^\w`]|[\u2460-\u2473\u2776-\u277f])+", "", s.strip()).strip()
    s = s[:1].upper() + s[1:]
    return s if not s or s[-1] in ".!?" else s + "."


def full(texts):
    return [t for t in texts if t and not t.endswith("…")]


def lower_first(s):
    return s[:1].lower() + s[1:] if s[:2] != s[:2].upper() else s


def tick(name):
    """Backticks make the voice read a name with its symbols ('src/lib.rs' -> 'source slash lib dot R S')."""
    return f"`{name}`" if name else ""


def kind_of(pitch):
    lo = pitch.lower()
    return next((k for k in KINDS if re.search(rf"\b{re.escape(k.lower())}\b", lo)), "project")


def tagline(pitch, name):
    """'Rust Token Killer - High-performance CLI proxy…' -> 'Rust Token Killer' (the bit before a dash/colon)."""
    head = re.split(r"\s+[-–—:|]\s+", pitch, maxsplit=1)[0].strip()
    return head if 2 <= len(head.split()) <= 6 and head.lower() != name.lower() else ""


def pain(pitch):
    """What the project fights, from its own pitch: 'minimize LLM token consumption' -> 'LLM token consumption'."""
    m = re.search(r"\b(?:minimi[sz]es?|reduces?|cuts?|saves?|stops?|eliminates?|kills?|avoids?|fix(?:es)?|prevents?|"
                  r"removes?|shrinks?|compress(?:es)?)\s+(?:your\s+|the\s+)?([\w\s'-]{4,48}?)(?:[.,;]|\s+(?:by|with|for|in|from)\b|$)",
                  pitch, re.I)
    return m.group(1).strip() if m else ""


def split_card(text):
    for sep in (" — ", " – ", ": ", ". "):
        head, _, rest = text.partition(sep)
        if rest and 2 <= len(head) <= 42:
            return head.rstrip("."), rest
    return text.rstrip("."), ""


def cards(f, n=3):
    """Outcome cards. API notes ('.optsWithGlobals() returns…') are reference docs, not selling points."""
    good = [x for x in f["features"] if not re.search(r"\(\)|^\.|^[a-z]+[A-Z]|`", x)]
    return [dict(zip(("title", "body"), split_card(x))) for x in good[:n]]


def phrases(text, n=3):
    """A long sentence -> up to n short lines for kinetic type."""
    parts = [p.strip() for p in re.split(r",\s+|;\s+|\s+—\s+|\s+(?=without\b|but\b|so\b)", text.rstrip(".")) if p.strip()]
    if len(parts) > n:  # keep every word: the tail joins the last line
        parts = parts[:n - 1] + [" ".join(parts[n - 1:])]
    return parts if len(parts) > 1 else [text.rstrip(".")]


def lang(f):
    return f["languages"][0]["name"] if f["languages"] else ""


def short_proof(p):
    label = re.sub(r"^[^:]{0,30}:\s*", "", p["label"]).strip()  # 'Install & forget: up to 90%…' -> 'up to 90%…'
    if label.endswith("…"):  # cut text is never read aloud: keep the clauses that are whole
        label = label.rsplit(",", 1)[0] if "," in label else ""
    return sentence(label) if len(label.split()) >= 3 else ""


# ---------------------------------------------------------------- the five formats

def trailer(f):
    name, kind, pitch = f["name"], kind_of(f["pitch"]), f["pitch"]
    enemy = pain(pitch)
    lines = ([f"In a world drowning in {lower_first(enemy)}…", f"one {lang(f)} {kind}" if lang(f) else f"one {kind}",
              "dares to fight back."] if enemy else
             [pick(name, ["In a world that never stops shipping…", "In a world running on duct tape and deadlines…",
                          "In a world where every second counts…"]),
              f"one {lang(f)} {kind}" if lang(f) else f"one {kind}", "changes everything."])
    s = [{"type": "coldopen", "lines": lines, "narration": " ".join(lines).replace("… ", "… ")}]
    if f["problem"]:
        grim = re.search(r"\b(without|slow|pain|manual|hard|waste|tired|expensive|costly|broken|boilerplate|burn|struggle)", f["problem"], re.I)
        s.append({"type": "glitch", "label": "THE PROBLEM" if grim else "THE MISSION", "lines": phrases(f["problem"]),
                  "backdrop": (f["entry"] or {}).get("code", ""), "narration": sentence(f["problem"])})
    tag = tagline(pitch, name)
    s.append({"type": "reveal", "title": name, "subtitle": tag or pitch, "lift": True,
              "narration": f"{name}. " + (f"{tag}." if tag else sentence(pitch) if len(pitch.split()) <= 12 else "")})
    cs = cards(f, 4)
    if cs:
        s.append({"type": "montage", "cards": cs, "narration": " ".join(sentence(c["title"]) for c in cs if not c["title"].endswith("…"))})
    if f["proof"]:
        said = " ".join(full(short_proof(p) for p in f["proof"][:2]))
        stats = [dict(p, label=short_proof(p).rstrip(".") or p["label"]) for p in f["proof"][:2]]  # whole clauses on screen too
        s.append({"type": "bignum", "stats": stats, "narration": said or "The numbers don't lie."})
    cmds = (f["install"] + f["usage"])[:2]
    if cmds:
        # say the friendliest one: a 'curl … | sh' installer is shown, not read aloud
        say = next((c for c in cmds if not re.search(r"curl|wget|\|", c)), "")
        s.append({"type": "cta", "kicker": "NOW SHOWING", "lines": cmds,
                  "narration": f"One command. {tick(say)}." if say else "Now showing, in your terminal."})
    starring = [n for n in f["graph"]["nodes"][:3]] or [t["name"].rstrip("/") for t in f["tree"][:3]]
    s.append({"type": "credits", "title": name, "starring": starring, "lang": lang(f), "files": f["file_count"],
              "url": f"github.com/{f['slug']}" if f["slug"] else "",
              "narration": pick(name, [f"{name}. Rated T, for terminal.", f"{name}. Now playing on GitHub.",
                                       f"{name}. Coming soon, to a terminal near you."])})
    return s


def metro(f):
    name, tr = f["name"], f["trace"]
    first, last = (tr[0]["symbol"] + "()", tr[-1]["symbol"] + "()") if tr else ("", "")
    s = [{"type": "ticket", "line": name, "from": first, "to": last, "depart": tr[0]["path"] if tr else "",
          "stops": len(tr),
          "narration": (f"All aboard the {name} express! Today we ride from {tick(first)} all the way to {tick(last)}."
                        if len(tr) > 1 else f"All aboard! Today we're touring the {name} codebase.")}]
    dirs = [t for t in f["tree"] if t["files"]]
    if dirs:
        big = dirs[0]
        s.append({"type": "city", "heading": f"{f['file_count']} files", "items": f["tree"], "lift": True,
                  "narration": f"Welcome to {name} city: {f['file_count']} files" + (f", mostly {lang(f)}" if lang(f) else "") +
                               f". The biggest district is {tick(big['name'].rstrip('/'))}, with {big['files']} files."})
    g = f["graph"]
    if len(g["nodes"]) >= 2 and g["edges"]:
        indeg = {}
        for e in g["edges"]:
            indeg[e["to"]] = indeg.get(e["to"], 0) + 1
        hub = max(indeg, key=indeg.get)
        s.append({"type": "network", "heading": "Network map", "nodes": g["nodes"], "edges": g["edges"], "hub": hub,
                  "lift": not dirs,
                  "narration": f"Here's the network map. Every line is a real import. {tick(hub)} is the central station"
                               + (f": {indeg[hub]} lines run through it." if indeg[hub] > 1 else ".")})
    for i, step in enumerate(tr):
        nxt = tr[i + 1]["symbol"] if i + 1 < len(tr) else ""
        lines = step["code"].split("\n")
        hl = [k for k, ln in enumerate(lines) if nxt and re.search(rf"\b{re.escape(nxt)}\s*(\(|!)", ln)][:1]
        where = tick(step["path"])
        said = (f"First stop: {tick(step['symbol'] + '()')}, in {where}." if i == 0 else
                f"Final stop: {tick(step['symbol'] + '()')}, in {where}." if i == len(tr) - 1 else
                f"Next stop: {tick(step['symbol'] + '()')}, in {where}.")
        if nxt and hl:
            said += f" Watch this line: it hands off to {tick(nxt + '()')}."
        s.append({"type": "stop", "path": step["path"], "start": step["start"], "end": step["end"], "symbol": step["symbol"],
                  "code": step["code"], "highlight": hl, "stops": [t["symbol"] for t in tr], "index": i,
                  "evidence": f"{step['path']}:{step['start']}-{step['end']}", "narration": said})
    build = [c for c in f["setup"] if not c.startswith("git clone")]
    if build:
        s.append({"type": "depot", "heading": "Ride it yourself", "lines": build,
                  "narration": f"Want to ride it yourself? {'Just' if len(build) < 3 else 'Run'} {len(build)} command{'s' * (len(build) != 1)}."})
    s.append({"type": "terminus", "title": name, "url": f"github.com/{f['slug']}" if f["slug"] else "",
              "narration": f"End of the line! Thanks for riding the {name} line."})
    return s


def quest(f):
    name = f["name"]
    s = [{"type": "titlescreen", "title": name, "subtitle": "THE ONBOARDING QUEST",
          "narration": f"Player one, welcome to {name}! Your quest: go from zero, to your first pull request."}]
    if f["setup"]:
        xp = 100 * len(f["setup"])
        verbs = [v for v, k in (("clone it", "git clone"), ("install it", "install"), ("build it", "build"), ("sync it", "sync"),
                                ("run it", " run "), ("test it", "test")) if any(k in c for c in f["setup"])]
        s.append({"type": "objectives", "heading": "LEVEL 1: GET IT RUNNING", "items": f["setup"], "xp": xp, "lift": True,
                  "achievement": "First Build",
                  "narration": "Level one: get it running. " + (sentence(", ".join(verbs[:-1]) + ", and " + verbs[-1]) if len(verbs) > 1
                                                                  else "Three commands stand between you and glory.")
                               + f" That's {xp} XP!"})
    zones, wild = [], iter(WILD)
    for t in f["tree"][:6]:
        zname, icon = ZONES.get(t["hint"]) or next(wild)
        zones.append({"name": t["name"].rstrip("/"), "zone": zname, "icon": icon, "files": t["files"]})
    if zones:
        named = [z for z in zones if z["name"] and any(z["zone"] == v[0] for v in ZONES.values())][:2]
        said = "This is the world map. " + " ".join(
            sentence(f"{tick(z['name'])} is {'' if z['zone'].startswith('The ') else 'the '}{z['zone']}") for z in named) if named \
            else "This is the world map."
        s.append({"type": "worldmap", "heading": "WORLD MAP", "zones": zones, "narration": said})
    boss = next((t for t in f["trace"] if t["end"] - t["start"] >= 4), f["entry"])
    if boss:
        s.append({"type": "boss", "path": boss["path"], "start": boss["start"], "end": boss["end"], "symbol": boss["symbol"],
                  "code": boss["code"], "highlight": [0], "evidence": f"{boss['path']}:{boss['start']}-{boss['end']}",
                  "narration": f"Your first boss: {tick(boss['symbol'])}, in {tick(boss['path'])}. "
                               "Read it, and the rest of the map makes sense."})
    rules = f["contributing"]
    if rules:
        s.append({"type": "scroll", "heading": "RULES OF THE GUILD", "items": rules,
                  "narration": "Before your first pull request, read the rules of the guild. " +
                               (f"Rule one: {lower_first(sentence(full(rules)[0]))}" if full(rules) else "")})
    s.append({"type": "complete", "title": "QUEST COMPLETE", "subtitle": "Next mission: pick an issue",
              "url": f"github.com/{f['slug']}/issues" if f["slug"] else "",
              "narration": "Quest complete! Your next mission: pick an issue, and make your first contribution. Good luck, hero."})
    return s


def news(f):
    r, name = f["release"], f["name"]
    if not r["items"]:
        raise SystemExit("release mode needs a CHANGELOG or git history (clone without --depth 1)")
    released = r["source"] == "CHANGELOG" or ".." in r["source"] or bool(r["version"])
    ver = (r["version"] or f["version"]) if released else ""
    label = f"{name} v{ver}" if ver else name
    items = r["items"]
    s = [{"type": "breaking", "kicker": "BREAKING NEWS" if released else "DEVELOPING STORY", "title": label,
          "subtitle": "RELEASED" if released else "RECENT CHANGES", "lift": True,
          "narration": (f"Breaking news tonight: {name} {ver} has just landed. We go live to the repo." if ver else
                        f"Developing story: big changes are moving through {name}. We go live to the repo.")}]
    said = f"Top story: {lower_first(sentence(full(items)[0]))}" if full(items) else ""
    if len(full(items)) > 1:
        said += f" Also tonight: {lower_first(sentence(full(items)[1]))}"
    s.append({"type": "headlines", "items": items, "evidence": r["source"], "narration": said or "Here are tonight's headlines."})
    if r.get("commits"):
        stats = [{"value": str(r["commits"]), "label": "commits"}, {"value": str(r["authors"]), "label": "contributors"}]
        if r.get("files_changed"):
            stats.append({"value": str(r["files_changed"]), "label": "files changed"})
        s.append({"type": "numbers", "heading": "BY THE NUMBERS", "stats": stats, "evidence": r["source"],
                  "narration": f"By the numbers: {r['commits']} commits, from {r['authors']} contributor{'s' * (r['authors'] != 1)}."})
    upgrade = [c for c in f["install"] if name.lower().split(".")[0] in c.lower()]
    if released and upgrade:
        s.append({"type": "field", "kicker": "LIVE FROM THE TERMINAL", "lines": upgrade,
                  "narration": f"Upgrading takes one line: {tick(upgrade[0])}."})
    s.append({"type": "signoff", "title": label, "url": f"github.com/{f['slug']}" if f["slug"] else "",
              "narration": pick(name, ["That's the news. Back to you in the terminal.",
                                       "And that's tonight's release. Stay curious, and keep shipping."])})
    return s


def reel(f):
    name, kind = f["name"], kind_of(f["pitch"])
    proof = next((short_proof(p) for p in f["proof"] if short_proof(p)), "")
    s = [{"type": "hook", "text": "Stop scrolling.", "sub": f"This {kind} is wild." if kind != "project" else "You need to see this.",
          "narration": f"Stop scrolling. This {kind} is wild." if kind != "project" else "Stop scrolling. You need to see this."}]
    s.append({"type": "namedrop", "title": name, "subtitle": f["pitch"], "lift": True, "narration": f"It's called {name}."})
    cs = cards(f, 3)
    if cs:
        nums = ("One", "Two", "Three")
        s.append({"type": "reasons", "heading": f"{len(cs)} reasons", "cards": cs,
                  "narration": f"{len(cs)} reasons you'll love it. " +
                               " ".join(f"{nums[i]}: {lower_first(sentence(c['title']))}" for i, c in enumerate(cs) if not c["title"].endswith("…"))})
    if f["proof"]:
        s.append({"type": "mindblown", "stats": f["proof"][:1], "narration": proof or "The numbers are wild."})
    if f["install"]:
        s.append({"type": "tryit", "lines": f["install"][:1], "narration": f"Try it in one line: {tick(f['install'][0])}."})
    s.append({"type": "follow", "title": name, "url": f"github.com/{f['slug']}" if f["slug"] else "",
              "narration": "Star it on GitHub. You're welcome."})
    return s


FORMATS = {"trailer": trailer, "metro": metro, "quest": quest, "news": news, "reel": reel}


def plan(facts, mode):
    if mode not in MODES:
        raise SystemExit(f"unknown mode {mode!r}; pick one of: {', '.join(MODES)}")
    _, fmt, w, h, style, voice, speed = MODES[mode]
    scenes = FORMATS[fmt](facts)
    lift = next((i for i, s in enumerate(scenes) if s.pop("lift", False)), 0)
    ticker = [x for x in facts["release"]["items"]] if fmt == "news" else []
    from .sound import bpm_of
    return {"version": 2, "mode": mode, "format": fmt, "name": facts["name"], "width": w, "height": h,
            "music": style, "bpm": bpm_of(style), "voice": voice, "voice_speed": speed, "lift": lift, "ticker": ticker,
            "seed": zlib.crc32(facts["name"].encode()) % 1000, "scenes": scenes}
