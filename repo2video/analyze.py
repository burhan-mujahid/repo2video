"""Read a repo and pull out the facts the videos need. No guessing: code facts carry file:line."""
import html
import json
import os
import re
import subprocess
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

LANGS = {
    ".py": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".rs": "Rust", ".go": "Go", ".java": "Java", ".kt": "Kotlin",
    ".swift": "Swift", ".rb": "Ruby", ".php": "PHP", ".c": "C", ".h": "C", ".cc": "C++", ".cpp": "C++",
    ".hpp": "C++", ".cs": "C#", ".dart": "Dart", ".lua": "Lua", ".sh": "Shell", ".zig": "Zig",
    ".ex": "Elixir", ".exs": "Elixir", ".scala": "Scala", ".vue": "Vue", ".svelte": "Svelte",
}
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", "target", "__pycache__", ".venv", "venv"}
NOT_CORE = re.compile(r"(^|/)(\.|tests?/|__tests__/|spec/|examples?/|bench|docs?/|scripts/|fixtures?/)|[._-]test\b|test_|\.d\.ts$")
DIR_HINTS = {
    "src": "source code", "lib": "library code", "test": "tests", "tests": "tests", "__tests__": "tests",
    "spec": "tests", "docs": "documentation", "doc": "documentation", "examples": "examples",
    "example": "examples", "scripts": "scripts", "bin": "executables", "cmd": "commands", "pkg": "packages",
    "internal": "internal code", "crates": "Rust crates", "packages": "packages", "apps": "apps",
    "assets": "assets", "skills": "agent skills", "hooks": "hooks", "benchmarks": "benchmarks",
    ".github": "CI workflows", "public": "static files", "components": "UI components", "api": "API",
}
ENTRY_NAMES = ["src/main.rs", "main.go", "src/index.ts", "src/index.js", "index.ts", "index.js", "src/main.py",
               "main.py", "app.py", "cli.py", "__main__.py", "src/lib.rs", "src/main.ts", "src/cli.ts"]
DEF_RE = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:pub(?:\([\w:]+\))?\s+)?(?:async\s+)?(?:static\s+)?"
                    r"(?:(?:const|let)\s+(?P<c>\w+)\s*=\s*(?:async\s*)?(?:\(|function|\w+\s*=>)"
                    r"|(?:def|class|function\*?|fn|func(?:\s+\([^)]*\))?|struct|impl|interface|enum|trait)\s+(?P<n>\w+))")
CALL_RE = re.compile(r"(?:\b|::|\.)([A-Za-z_]\w{2,})\s*(?:\(|!\()")
CMD_RE = re.compile(r"^(npm|npx|pnpm|yarn|bun|bunx|pip|pipx|uv|uvx|cargo|go|brew|docker|git clone|curl|make|"
                    r"python3?|deno|gem|dotnet|poetry)\b")
STOP_CALLS = {"print", "len", "str", "int", "range", "list", "dict", "set", "map", "new", "format", "push",
              "append", "get", "join", "split", "require", "println", "Some", "Ok", "Err", "Box", "Vec", "String",
              "isinstance", "super", "self", "this", "console", "log", "error", "exit", "unwrap", "expect",
              "clone", "into", "iter", "collect", "from", "then", "catch", "filter", "find", "keys", "values",
              "cfg", "derive", "default", "test", "assert", "matches", "vec", "write", "writeln", "panic", "todo",
              "Self", "describe", "it", "allow", "include", "concat", "stringify"}
PROBLEM_RE = re.compile(r"\b(problem|without|instead of|tired|no more|stop |hard to|slow|expensive|pain|manual|"
                        r"waste|too many|costly|struggle|annoying|tedious|boilerplate|burn)", re.I)
PROOF_RE = re.compile(r"(\d[\d,.]*\s*(?:[-–]\s*\d[\d,.]*\s*)?(?:%|x\b|×|times|ms\b|seconds|minutes|hours|"
                      r"k\b|K\b|tokens|fewer|faster|less))", re.I)


def files_of(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, text=True, check=True).stdout
        if out:
            return [f for f in out.split("\0") if f]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    files = []
    for d, dirs, names in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        files += [os.path.relpath(os.path.join(d, n), root) for n in names]
    return files


def git(root, *args):
    try:
        return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        return ""


def read(root, rel):
    try:
        return Path(root, rel).read_text(errors="ignore")
    except OSError:
        return ""


def clean_md(s):
    s = re.sub(r"<[^>]+>", "", html.unescape(s))          # html tags
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)           # images and badges
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)       # links -> text
    s = re.sub(r"[*_`]{1,3}([^*_`]+)[*_`]{1,3}", r"\1", s)
    s = re.sub(r":[a-z_]+:|[\u2460-\u2473\u2776-\u277f]", "", s)            # :emoji: codes, circled numbers
    return re.sub(r"\s+", " ", s).strip(" -–—>|")


def clip(s, n):
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def first_sentence(s):
    head = re.split(r"(?<=[.!?])\s", s, maxsplit=1)[0]
    return head if len(head) >= 12 else s


def find_doc(root, *stems):
    for name in sorted(os.listdir(root)):
        if Path(name).stem.lower() in stems and os.path.isfile(os.path.join(root, name)):
            return read(root, name)
    for sub in ("docs", ".github"):  # CONTRIBUTING often lives here
        d = os.path.join(root, sub)
        if os.path.isdir(d):
            for name in sorted(os.listdir(d)):
                if Path(name).stem.lower() in stems:
                    return read(d, name)
    return ""


def parse_md(text):
    """Markdown -> (paragraphs, [(heading, bullet)], [(lang, lines)])."""
    paras, bullets, blocks = [], [], []
    heading, in_code, lang, code, para = "", False, "", [], []
    for line in text.splitlines():
        if line.strip().startswith("```"):
            if in_code:
                blocks.append((lang, code))
                in_code, code = False, []
            else:
                in_code, lang = True, line.strip()[3:].strip().lower()
            continue
        if in_code:
            code.append(line)
            continue
        if line.startswith("#"):
            heading, para = line.lstrip("#").strip().lower(), []
            continue
        m = re.match(r"^\s*(?:[-*+]|\d+\.)\s+(.*)", line)
        if m:
            if not re.fullmatch(r"\[[^\]]*\]\(#[^)]*\)", m.group(1).strip()):  # skip table-of-contents links
                bullets.append((heading, clean_md(m.group(1))))
            continue
        if line.strip():
            para.append(line)
        elif para:
            paras.append(clean_md(" ".join(para)))
            para = []
    if para:
        paras.append(clean_md(" ".join(para)))
    return paras, bullets, blocks


def commands(blocks, name):
    cmds = []
    for lang, lines in blocks:
        if lang not in ("", "sh", "bash", "shell", "console", "zsh", "shellsession", "powershell"):
            continue
        for ln in lines:
            ln = re.sub(r"\s+#.*$", "", ln.strip().removeprefix("$ ")).strip()
            ok = CMD_RE.match(ln) or (name and ln.split(" ")[0] == name.lower())
            if ok and len(ln) <= 72 and "<" not in ln and ln not in cmds:
                cmds.append(ln)
    install = [c for c in cmds if re.search(r"\b(install|add|clone|sync|i)\b|\| *(ba)?sh", c)]
    return install[:1], [c for c in cmds if c not in install][:2]


def manifest(root):
    """Name, description, entry hints, scripts from package.json / pyproject.toml / Cargo.toml / go.mod."""
    info = {"name": "", "description": "", "entries": [], "symbol": "", "scripts": {}, "version": ""}
    try:
        d = json.loads(read(root, "package.json") or "{}")
    except json.JSONDecodeError:
        d = {}
    if d:
        info.update(name=d.get("name", ""), description=d.get("description", ""), version=d.get("version", ""),
                    scripts=d.get("scripts") or {})
        b = d.get("bin")
        info["entries"] += list(b.values()) if isinstance(b, dict) else [b] if b else []
        info["entries"] += [d[k] for k in ("main", "module") if isinstance(d.get(k), str)]
    for fname, key in (("pyproject.toml", "project"), ("Cargo.toml", "package")):
        try:
            d = tomllib.loads(read(root, fname)).get(key, {})
        except tomllib.TOMLDecodeError:
            continue
        info["name"] = info["name"] or d.get("name", "")
        info["description"] = info["description"] or d.get("description", "")
        info["version"] = info["version"] or str(d.get("version", ""))
        for target in d.get("scripts", {}).values():  # "pkg.mod:func"
            mod, _, func = target.partition(":")
            base = mod.replace(".", "/")
            info["entries"] += [base + ".py", f"src/{base}.py", base + "/__init__.py", f"src/{base}/__init__.py"]
            info["symbol"] = info["symbol"] or func
    info["entries"] = [os.path.normpath(e) for e in info["entries"]]
    return info


def setup_steps(root, files, slug, scripts):
    """Clone, install, run, test: the commands a newcomer types, from lockfiles and manifests."""
    fs = set(files)
    steps = [f"git clone https://github.com/{slug}"] if slug else []
    install = next((cmd for f, cmd in [
        ("pnpm-lock.yaml", "pnpm install"), ("yarn.lock", "yarn"), ("bun.lockb", "bun install"),
        ("bun.lock", "bun install"), ("package-lock.json", "npm install"), ("package.json", "npm install"),
        ("uv.lock", "uv sync"), ("poetry.lock", "poetry install"), ("requirements.txt", "pip install -r requirements.txt"),
        ("pyproject.toml", "pip install -e ."), ("Cargo.toml", "cargo build"), ("go.mod", "go build ./..."),
        ("Gemfile", "bundle install")] if f in fs), "")
    runner = install.split(" ")[0] if install.split(" ")[0] in ("pnpm", "yarn", "bun") else "npm"
    run = next((f"{runner} run {s}" for s in ("dev", "start") if s in scripts), "")
    test = (f"{runner} test" if "test" in scripts else
            "cargo test" if "Cargo.toml" in fs else "go test ./..." if "go.mod" in fs else
            "uv run pytest" if "uv.lock" in fs and any("test" in f for f in files) else
            "pytest" if any(re.search(r"(^|/)test_\w+\.py$", f) for f in files) else
            "make test" if re.search(r"^test:", read(root, "Makefile"), re.M) else "")
    return [s for s in (steps + [install, run, test]) if s]


def def_block(lines, i, limit=14):
    """Lines of the definition at i: stops where the indentation returns to the def's own level."""
    base = len(lines[i]) - len(lines[i].lstrip())
    j = i + 1
    while j < len(lines) and j - i < limit:
        ln = lines[j]
        if ln.strip() and len(ln) - len(ln.lstrip()) <= base:
            if ln.strip().startswith("}"):   # closing brace ends the block
                j += 1
                break
            if not ln.strip().startswith((")", "]")):  # ")" may close a multi-line signature
                break
        j += 1
    body = [ln.rstrip().replace("\t", "    ") for ln in lines[i:j]]
    while body and not body[-1].strip():
        body.pop()
    return body


def snippet(path, lines, i, name):
    body, comments = [], 0
    for ln in def_block(lines, i, limit=40):  # keep at most 2 comment-only lines: the video shows code
        comments += bool(re.match(r"\s*(//|#(?!\[)|\*|/\*)", ln))
        if comments <= 2 or not re.match(r"\s*(//|#(?!\[)|\*|/\*)", ln):
            body.append(ln)
        if len(body) == 14:
            break
    return {"path": path, "start": i + 1, "end": i + len(body), "symbol": name,
            "code": "\n".join(clip(ln, 78) for ln in body)}


def index_defs(root, core):
    """name -> [(path, line_index)] for every top-level-ish definition in core files."""
    defs, texts = defaultdict(list), {}
    for f in core[:1500]:  # shortcut: biggest 1500 files only, raise for monorepos if traces stop early
        texts[f] = read(root, f).splitlines()
        for i, ln in enumerate(texts[f]):
            if (m := DEF_RE.match(ln)) and (indent := len(ln) - len(ln.lstrip())) <= 4:
                defs[m.group("c") or m.group("n")].append((f, i, indent))
    return defs, texts


def entry_point(files, core, man, texts, defs):
    """The entry function by name (main, run, cli…), else the first real definition (6+ lines)."""
    fs = set(files)
    cands = list(dict.fromkeys([e for e in man["entries"] if e in fs] + [e for e in ENTRY_NAMES if e in fs] + core[:3]))
    named = re.compile(rf"({re.escape(man['symbol'])}|main|run|cli|app|program|train|create\w*|start)"
                       if man["symbol"] else r"(main|run|cli|app|program|train|create\w*|start)")
    best = None
    for path in cands:
        lines = texts.get(path) or []
        found = sorted(((i, n) for n, locs in defs.items() for p, i, _ in locs if p == path),
                       key=lambda d: (not named.fullmatch(d[1]), d[0]))
        for i, name in found:
            s = snippet(path, lines, i, name)
            if named.fullmatch(name) or s["end"] - s["start"] >= 5:
                return s
            best = best or s
    return best


def call_trace(start, defs, texts, hops=3):
    """Follow the code: from the entry definition, step into the first function it calls that this repo defines."""
    trace, seen = [start], {(start["path"], start["start"])}
    cur = start
    for _ in range(hops):
        lines = texts[cur["path"]]
        body = "\n".join(def_block(lines, cur["start"] - 1, limit=60))
        options = []
        for name in dict.fromkeys(CALL_RE.findall(body)):
            if name in STOP_CALLS or name not in defs or name == cur["symbol"]:
                continue
            lang = LANGS.get(Path(cur["path"]).suffix.lower())
            locs = [l for l in defs[name] if (l[0], l[1] + 1) not in seen and LANGS.get(Path(l[0]).suffix.lower()) == lang]
            # top-level defs first, same package, another file, then shallow paths
            top = cur["path"].split("/")[0]
            locs.sort(key=lambda l: (l[2] > 0, l[0].split("/")[0] != top, l[0] == cur["path"], l[0].count("/")))
            if locs:
                options.append((name, locs[0]))
        # a hand-off into another file says more about the architecture than a local helper
        options.sort(key=lambda o: o[1][0] == cur["path"])
        nxt = None
        if options:
            name, loc = options[0]
            nxt = snippet(loc[0], texts[loc[0]], loc[1], name)
            nxt["called_from"] = f"{cur['symbol']}()"
        if not nxt:
            break
        trace.append(nxt)
        seen.add((nxt["path"], nxt["start"]))
        cur = nxt
    return trace


IMPORT_RES = {
    "py": re.compile(r"^\s*(?:from\s+(\.*[\w.]*)\s+import|import\s+([\w.]+))", re.M),
    "js": re.compile(r"""(?:from\s+|require\(\s*|import\(\s*|import\s+)['"](\.{1,2}/[^'"]+)['"]"""),
    "rs": re.compile(r"^\s*(?:pub\s+)?mod\s+(\w+)\s*;|use\s+crate::(\w+)", re.M),
    "go": re.compile(r'"([\w.\-/]+)"'),
}


def module_of(path):
    """Group files into modules: dir depth 2 for container dirs (src/, packages/…), else the top dir."""
    parts = path.split("/")
    if len(parts) == 1:
        return Path(path).stem
    if parts[0] in ("src", "lib", "packages", "crates", "internal", "pkg", "apps", "cmd") and len(parts) > 2:
        return "/".join(parts[:2])
    return parts[0]


def import_graph(root, core, texts):
    """Edges between modules, from real import statements. Returns nodes (by degree) and weighted edges."""
    fs = set(core)
    gomod = (re.search(r"^module\s+(\S+)", read(root, "go.mod"), re.M) or [None, None])[1]
    edges = Counter()

    def resolve(src, ref, kind):
        base = os.path.dirname(src)
        if kind == "js":
            p = os.path.normpath(os.path.join(base, ref))
            for ext in ("", ".ts", ".tsx", ".js", ".mjs", ".jsx", "/index.ts", "/index.js"):
                if p + ext in fs:
                    return p + ext
        elif kind == "py":
            dots = len(ref) - len(ref.lstrip("."))
            mod = ref.lstrip(".").replace(".", "/")
            bases = [os.path.normpath(os.path.join(base, *[".."] * (dots - 1)))] if dots else ["", "src"]
            for b in bases:
                p = os.path.normpath(os.path.join(b, mod)) if mod else b
                for cand in (p + ".py", p + "/__init__.py"):
                    if cand in fs:
                        return cand
        elif kind == "rs":
            crate = src[: src.index("src/") + 4] if "src/" in src else base + "/"
            for b in (base + "/", crate):
                for cand in (f"{b}{ref}.rs", f"{b}{ref}/mod.rs"):
                    if os.path.normpath(cand) in fs:
                        return os.path.normpath(cand)
        elif kind == "go" and gomod and ref.startswith(gomod + "/"):
            d = ref[len(gomod) + 1:]
            return next((f for f in core if os.path.dirname(f) == d), None)
        return None

    for f in core:
        kind = {".py": "py", ".js": "js", ".mjs": "js", ".cjs": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
                ".rs": "rs", ".go": "go"}.get(Path(f).suffix)
        if not kind or f not in texts:
            continue
        for m in IMPORT_RES[kind].finditer("\n".join(texts[f])):
            ref = next(g for g in m.groups() if g)
            tgt = resolve(f, ref, kind)
            a, b = module_of(f), module_of(tgt) if tgt else None
            if b and a != b:
                edges[(a, b)] += 1
    degree = Counter()
    for (a, b), n in edges.items():
        degree[a] += n
        degree[b] += n
    nodes = [n for n, _ in degree.most_common(7)]
    return {"nodes": nodes, "edges": [{"from": a, "to": b, "weight": n} for (a, b), n in edges.most_common()
                                      if a in nodes and b in nodes][:12]}


def tidy(items, n=5):
    """Release items without issue refs, hashes or near-duplicates."""
    out, keys = [], set()
    for it in items:
        it = clip(first_sentence(re.sub(r"\s*\(?\[?#\d+\]?\)?|\s*\([0-9a-f]{7,}\)", "", it)).rstrip(". "), 70)
        key = " ".join(it.lower().split()[:4])
        if it and key not in keys:
            keys.add(key)
            out.append(it[0].upper() + it[1:])
    return out[:n]


def release_notes(root, files):
    """Latest release: CHANGELOG's first versioned section, else commit subjects since the previous tag."""
    text = find_doc(root, "changelog", "changes", "history", "releases")
    if text:
        m = re.search(r"^#{1,3}\s*\[?v?(\d+\.\d+[\w.\-]*)\]?.*$([\s\S]*?)(?=^#{1,3}\s*\[?v?\d+\.\d+|\Z)", text, re.M)
        if m:
            items = tidy(b for _, b in parse_md(m.group(2))[1] if len(b.split()) >= 2)
            if items:
                return {"version": m.group(1), "items": items, "source": "CHANGELOG"}
    tags = git(root, "tag", "--sort=-creatordate").splitlines()
    rng = [f"{tags[1]}..{tags[0]}"] if len(tags) > 1 else [tags[0], "-n", "30"] if tags else ["-n", "30"]
    subjects = [s for s in git(root, "log", *rng, "--no-merges", "--pretty=%s").splitlines() if s]
    rank = lambda s: 0 if re.match(r"feat", s) else 1 if re.match(r"(fix|perf)", s) else 2
    items = [re.sub(r"^\w+(\([^)]*\))?!?:\s*", "", s) for s in sorted(subjects, key=rank)
             if not re.match(r"(chore|ci|build|docs|test|style|bump|release|merge)\b", s, re.I)]
    stats = git(root, "diff", "--shortstat", *rng[0].split("..")) if ".." in rng[0] else ""
    return {"version": tags[0].lstrip("v") if tags else "", "items": tidy(items),
            "source": "git log " + " ".join(rng), "commits": len(subjects),
            "authors": len(set(git(root, "log", *rng, "--pretty=%an").splitlines()) - {""}),
            "files_changed": int((re.search(r"(\d+) files? changed", stats) or [0, 0])[1])}


def analyze(root):
    root = os.path.abspath(root)
    files = files_of(root)
    sizes = Counter()
    for f in files:
        lang = LANGS.get(Path(f).suffix.lower())
        if lang and os.path.isfile(os.path.join(root, f)):
            sizes[lang] += os.path.getsize(os.path.join(root, f))
    total = sum(sizes.values()) or 1
    langs = [{"name": k, "pct": round(100 * v / total)} for k, v in sizes.most_common(4) if v / total >= 0.03]
    top_lang = langs[0]["name"] if langs else ""

    tops = Counter(f.split("/")[0] for f in files if "/" in f)
    tree = [{"name": d + "/", "files": n, "hint": DIR_HINTS.get(d.lower(), "")} for d, n in tops.most_common(7)
            if not d.startswith(".") or d == ".github"][:6]
    tree += [{"name": f, "files": 0, "hint": ""} for f in sorted(files)
             if "/" not in f and not f.startswith(".") and Path(f).suffix.lower() in LANGS][:max(0, 7 - len(tree))]

    man = manifest(root)
    slug = (m.group(1) if (m := re.search(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?$",
                                           git(root, "config", "--get", "remote.origin.url"))) else "")
    name = (slug.split("/")[-1] if slug else "") or man["name"] or os.path.basename(root)
    paras, bullets, blocks = parse_md(find_doc(root, "readme"))
    install, usage = commands(blocks, name)

    pitch = clip(clean_md(man["description"]) or next((p for p in paras if len(p) >= 40), ""), 160)
    good = [(h, b) for h, b in bullets if len(b.split()) >= 3 and not b.lower().startswith(("http", "see "))]
    feats = [b for h, b in good if re.search(r"feature|why|highlight|what it|key|benefit", h)] or \
            [b for h, b in good if not re.search(r"install|licen|contribut|credit|requirement", h)]
    sentences = [s for p in paras for s in re.split(r"(?<=[.!?])\s+", p) if 20 <= len(s) <= 200]
    problem = next((s for s in sentences if PROBLEM_RE.search(s) and len(s) >= 40), "")
    proof = []
    for s in sentences + [b for _, b in good]:
        if re.search(r"\bnot\b|\bI'm\b|\bI am\b|e\.g\.|`|\b[A-Z_]{6,}\b", s):  # hedges and config talk are not proof
            continue
        if (m := PROOF_RE.search(s)) and len(proof) < 2 and all(p["value"] != m.group(1).strip() for p in proof):
            proof.append({"value": m.group(1).strip(), "label": clip(s, 90)})

    core = sorted((f for f in files if LANGS.get(Path(f).suffix.lower()) and not NOT_CORE.search(f.lower())
                   and os.path.isfile(os.path.join(root, f))),
                  key=lambda f: os.path.getsize(os.path.join(root, f)), reverse=True)
    defs, texts = index_defs(root, core)
    entry = entry_point(files, [c for c in core if LANGS[Path(c).suffix.lower()] == top_lang], man, texts, defs)
    # rules are instructions: keep bullets that tell you to do something
    RULE = re.compile(r"^(please |always |never |do not |don't |make sure |be sure )?(run|open|make|use|add|write|keep|follow|ensure|read|"
                      r"check|fork|create|sign|update|test|format|lint|squash|rebase|describe|link|include|avoid|submit|discuss|"
                      r"file|search|start|wait|ask|document|respect|commit|push|install|build|target)\b", re.I)
    contrib = [clip(first_sentence(b), 80) for _, b in parse_md(find_doc(root, "contributing"))[1]
               if len(b.split()) >= 4 and RULE.match(b) and not re.search(r"\([^)]*,[^)]*\)", b)][:4]  # '(a, b, c)' = a list, not a rule
    setup = setup_steps(root, files, slug, man["scripts"])
    test_cmd = next((c for c in setup if re.search(r"\btest\b|pytest", c)), "")
    if not contrib and test_cmd:
        contrib = [f"Run {test_cmd} before you push"]

    return {
        "name": name, "slug": slug, "version": man["version"],
        "pitch": pitch,
        "problem": clip(problem, 160),
        "features": [clip(f, 110) for f in feats[:4]],
        "proof": proof,
        "languages": langs,
        "file_count": len(files),
        "tree": tree,
        "entry": entry,
        "trace": call_trace(entry, defs, texts) if entry else [],
        "graph": import_graph(root, core, texts),
        "install": install,
        "usage": usage,
        "setup": setup,
        "contributing": contrib,
        "has_tests": any(re.search(r"(^|/)(tests?|__tests__|spec)/|[._]test\.|test_", f) for f in files),
        "release": release_notes(root, files),
    }
