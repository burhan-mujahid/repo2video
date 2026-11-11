/* repo2video scene engine v2. One file, no dependencies.
 *   Repo2Video.createVideo(rootEl, story) -> { duration, scenes, cues, render(t) }
 * Every pixel is a pure function of t (seconds): the built-in renderer, HyperFrames (hf-seek) and Remotion
 * (useCurrentFrame) all seek it frame by frame. Five show formats share one motion system:
 *   animation registry (composable transforms) · camera with beat punches · per-format transitions ·
 *   seeded particles · film grain · Bit the mascot (lip-syncs to the narration) · karaoke captions.
 * `cues` lists every sound the picture makes (whooshes, impacts, typing, coins) so the soundtrack matches it.
 */
(function (g) {
  "use strict";

  // ------------------------------------------------------------ basics
  const VOICE_AT = 0.45, TR = 0.5;
  const MIN = { coldopen: 6, glitch: 5, reveal: 5, montage: 5, bignum: 4.5, cta: 5, credits: 6,
    ticket: 6, city: 6, network: 7, stop: 6.5, depot: 5, terminus: 5,
    titlescreen: 6, objectives: 6, worldmap: 7, boss: 7, scroll: 6, complete: 6,
    breaking: 6, headlines: 7, numbers: 5, field: 5, signoff: 5.5,
    hook: 3.2, namedrop: 3.2, reasons: 5, mindblown: 3.5, tryit: 4, follow: 4 };
  const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
  const E = {
    out: x => 1 - Math.pow(1 - clamp(x), 3),
    inout: x => { x = clamp(x); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; },
    back: x => { x = clamp(x); const c = 1.9; return 1 + (c + 1) * Math.pow(x - 1, 3) + c * Math.pow(x - 1, 2); },
    elastic: x => { x = clamp(x); return x === 0 || x === 1 ? x : Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * (2 * Math.PI) / 3) + 1; },
    bounce: x => { x = clamp(x); const n = 7.5625, d = 2.75; if (x < 1 / d) return n * x * x; if (x < 2 / d) return n * (x -= 1.5 / d) * x + 0.75; if (x < 2.5 / d) return n * (x -= 2.25 / d) * x + 0.9375; return n * (x -= 2.625 / d) * x + 0.984375; },
    in: x => Math.pow(clamp(x), 3)
  };
  function prng(seed) { let a = seed >>> 0; return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function hash(s) { let h = 2166136261; for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619); return h >>> 0; }
  function el(tag, cls, text, style) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    if (style) e.style.cssText = style;
    return e;
  }
  function svg(tag, attrs, parent) {
    const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  const nwords = s => (s || "").split(/\s+/).filter(Boolean).length;
  const norm = s => String(s).toLowerCase().replace(/[^a-z0-9]/g, "");
  const fit = (text, max, min, per) => Math.max(min, Math.min(max, per / Math.max(1, String(text).length))); // font-size by length

  // ------------------------------------------------------------ formats: look, transitions, captions, sounds
  const FORMATS = {
    trailer: { bg: "#050505", fg: "#f4efe2", accent: "#f5c451", accent2: "#ff5a36", font: "'Bricolage Grotesque','Space Grotesk',sans-serif",
      display: "Anton,'Bebas Neue',Impact,sans-serif", trans: "flash", caps: "letterbox", grain: 0.13, punch: 0.018, push: 0.05,
      cut: "hit", costume: "shades" },
    metro: { bg: "#0a1726", fg: "#eaf2ff", accent: "#ffb000", accent2: "#29c5f6", font: "'Space Grotesk',Inter,sans-serif",
      display: "'Space Grotesk',Inter,sans-serif", trans: "slide", caps: "led", grain: 0.05, punch: 0.006, push: 0.025,
      cut: "whoosh", costume: "cap", lines: ["#ff3b6b", "#29c5f6", "#ffb000", "#3ddc84", "#b36bff", "#ff8a3d", "#f6e05e"] },
    quest: { bg: "#1b1747", fg: "#fff7e0", accent: "#ffd23f", accent2: "#3ddc84", font: "'Space Grotesk',Inter,sans-serif",
      display: "'Press Start 2P',monospace", trans: "iris", caps: "dialog", grain: 0.04, punch: 0.0, push: 0.0,
      cut: "powerup", costume: "crown" },
    news: { bg: "#06122e", fg: "#ffffff", accent: "#e8112d", accent2: "#ffcc00", font: "'Space Grotesk',Inter,sans-serif",
      display: "'Bebas Neue',Anton,Impact,sans-serif", trans: "swoosh", caps: "cc", grain: 0.05, punch: 0.008, push: 0.03,
      cut: "whoosh", costume: "tie" },
    reel: { bg: "#ff2e63", fg: "#ffffff", accent: "#fff200", accent2: "#00e5ff", font: "'Bricolage Grotesque','Space Grotesk',sans-serif",
      display: "'Bricolage Grotesque','Space Grotesk',sans-serif", trans: "punch", caps: "tiktok", grain: 0.06, punch: 0.03, push: 0.06,
      cut: "whoosh", costume: "shades", hues: ["#ff2e63", "#7b2ff7", "#00b894", "#ff7a00", "#0984e3", "#e84393"] }
  };

  // ------------------------------------------------------------ timing (single source of truth)
  function timeline(story) {
    const beat = story.bpm ? 60 / story.bpm : 0, bar = beat * 4, speed = story.voice_speed || 1;
    let t = 0;
    return story.scenes.map((s, i) => {
      const talk = s.audio != null ? s.audio : nwords(s.narration) / (2.5 * speed);
      let d = Math.max(MIN[s.type] || 4, VOICE_AT + talk + 0.9);
      if (beat) d = Math.ceil(d / beat - 1e-6) * beat;                               // cuts land on the beat
      if (bar && i + 1 === story.lift) d = Math.ceil((t + d) / bar - 1e-6) * bar - t;  // the drop lands on a bar
      const r = { start: t, duration: d, voiceAt: t + VOICE_AT, talk: talk };
      t += d;
      return r;
    });
  }

  // words with times (local to the scene): from the voice when measured, else spread evenly
  function wordTimes(s, tm) {
    if (s.words && s.words.length) return s.words.map(w => ({ w: w.w, a: VOICE_AT + w.t0, b: VOICE_AT + w.t1 }));
    const ws = (s.narration || "").split(/\s+/).filter(Boolean), per = tm.talk / Math.max(1, ws.length);
    return ws.map((w, i) => ({ w: w.replace(/`/g, ""), a: VOICE_AT + i * per, b: VOICE_AT + (i + 1) * per }));
  }
  // local time when the narration reaches `phrase` (searching from word index `from`), for sync
  function sayAt(words, phrase, from = 0, fallback = 0) {
    const key = norm(String(phrase).split(/\s+/)[0] || "");
    for (let i = from; i < words.length; i++) if (key && norm(words[i].w).startsWith(key)) return { t: words[i].a, i: i };
    return { t: fallback, i: from };
  }

  // ------------------------------------------------------------ CSS
  const CSS = `
.r2v{position:relative;overflow:hidden;color:var(--fg);background:var(--bg);font-family:var(--font);-webkit-font-smoothing:antialiased}
.r2v *{box-sizing:border-box}
.r2v .layer{position:absolute;inset:0}
.r2v .world{position:absolute;inset:0;transform-origin:50% 50%;isolation:isolate;z-index:0}
.r2v .scene{position:absolute;inset:0;overflow:hidden}
.r2v .center{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}
.r2v .mono{font-family:'JetBrains Mono','SF Mono',Menlo,monospace}
.r2v .disp{font-family:var(--display)}
.r2v canvas{position:absolute;inset:0;pointer-events:none}
.r2v .grain{position:absolute;inset:-64px;pointer-events:none;mix-blend-mode:overlay}
.r2v .vignette{position:absolute;inset:0;pointer-events:none;background:radial-gradient(120% 90% at 50% 50%,transparent 55%,rgba(0,0,0,.55) 100%)}
.r2v .flash{position:absolute;inset:0;background:#fff;pointer-events:none;opacity:0}
.r2v .band{position:absolute;top:-20%;bottom:-20%;width:70%;left:-80%;transform:skewX(-18deg);background:linear-gradient(90deg,var(--accent),#fff 50%,var(--accent));pointer-events:none}
/* captions */
.r2v .cap{position:absolute;left:0;right:0;text-align:center;pointer-events:none}
.r2v .cap .w{display:inline-block;margin:0 .14em;transition:none}
.r2v .cap-letterbox{bottom:1.6%;font-size:1.02em;letter-spacing:.06em;color:#d9d2bf;text-transform:uppercase;font-weight:500}
.r2v .cap-letterbox .w.on{color:#fff}
.r2v .cap-led{bottom:4%}
.r2v .cap-led .box{display:inline-block;background:#120c02;border:2px solid #2b1d05;border-radius:10px;padding:.35em .8em;font-family:'JetBrains Mono',monospace;color:#5a4210;font-size:1.05em;text-transform:uppercase;letter-spacing:.04em;max-width:84%;box-shadow:0 0 0 4px rgba(0,0,0,.4)}
.r2v .cap-led .w.on,.r2v .cap-led .w.done{color:#ffb000;text-shadow:0 0 8px rgba(255,176,0,.8)}
.r2v .cap-dialog{bottom:3%;left:6%;right:6%;text-align:left}
.r2v .cap-dialog .box{position:relative;background:#0b0930;border:4px solid #fff7e0;box-shadow:0 0 0 4px #0b0930,0 0 0 8px #ffd23f;padding:.7em 1em .7em 4.6em;font-family:'Press Start 2P',monospace;font-size:.82em;line-height:1.8;min-height:4.6em;color:#fff7e0}
.r2v .cap-dialog .who{position:absolute;left:.7em;top:.6em;width:3.2em;height:3.2em}
.r2v .cap-dialog .w{opacity:0;margin:0 .25em 0 0}
.r2v .cap-dialog .w.on,.r2v .cap-dialog .w.done{opacity:1}
.r2v .cap-dialog .w.on{color:#ffd23f}
.r2v .cap-cc{bottom:12.5%}
.r2v .cap-cc .box{display:inline-block;background:rgba(0,0,0,.82);padding:.22em .6em;font-size:1.05em;font-weight:600;max-width:80%}
.r2v .cap-cc .w.on{color:var(--accent2)}
.r2v .cap-tiktok{top:66%;padding:0 6%}
.r2v .cap-tiktok .w{font-family:'Bricolage Grotesque',sans-serif;font-weight:800;font-size:2.6em;text-transform:uppercase;color:#fff;
  -webkit-text-stroke:.09em #000;paint-order:stroke fill;text-shadow:0 .08em 0 #000;margin:0 .12em;line-height:1.05}
.r2v .cap-tiktok .w.on{color:var(--accent)}
/* shared pieces */
.r2v .term{background:#0d1117;border-radius:14px;box-shadow:0 30px 80px rgba(0,0,0,.45);overflow:hidden;text-align:left;font-family:'JetBrains Mono',monospace;color:#e6edf3}
.r2v .term .bar{background:#161b22;padding:.7em 1em;display:flex;gap:.45em;align-items:center}
.r2v .term .bar i{width:.8em;height:.8em;border-radius:50%;display:block}
.r2v .term .bar span{margin-left:.8em;color:#8b949e;font-size:.95em}
.r2v .term .body{padding:1em 1.3em 1.2em;font-size:1.3em;line-height:1.7;white-space:pre}
.r2v .term .p{color:#3fb950;margin-right:.6em}
.r2v .cursor{display:inline-block;width:.6em;height:1.1em;background:#e6edf3;vertical-align:-.15em;margin-left:.1em}
.r2v .code{background:#0f1420;border:1px solid rgba(255,255,255,.08);border-radius:14px;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.45);text-align:left}
.r2v .code .hd{display:flex;justify-content:space-between;padding:.55em 1.1em;background:#151b2b;color:#9aa7c0;font-family:'JetBrains Mono',monospace;font-size:.95em}
.r2v .code .hd .ev{color:#7ee0b5}
.r2v .code pre{margin:0;padding:.6em 0;font-family:'JetBrains Mono',monospace;font-size:.98em;line-height:1.5;color:#d8dee9}
.r2v .code .ln{position:relative;padding:0 1.1em 0 4.2em;white-space:pre}
.r2v .code .ln:before{content:attr(data-n);position:absolute;left:0;width:3.2em;text-align:right;color:#4c566a}
.r2v .code .hl{position:absolute;left:0;right:0;top:0;bottom:0;background:rgba(255,200,60,.2);border-left:4px solid #ffc83c;box-shadow:inset 0 0 30px rgba(255,200,60,.15)}
.r2v .code .k{color:#c792ea}.r2v .code .s{color:#c3e88d}.r2v .code .n{color:#f78c6c}.r2v .code .c{color:#697098;font-style:italic}.r2v .code .f{color:#82aaff}.r2v .code .t{color:#ffcb6b}
.r2v .mascot{position:absolute;width:7em;height:7em}
.r2v .hot{box-shadow:0 0 0 5px #fff,0 0 40px rgba(255,255,255,.55)!important;z-index:2}
`;

  // ------------------------------------------------------------ syntax colouring
  const KW = /^(fn|pub|let|mut|const|var|function|return|if|else|for|while|match|impl|struct|enum|trait|use|mod|class|def|import|from|export|default|async|await|new|this|self|Self|true|false|None|null|undefined|in|of|try|catch|except|with|as|type|interface|extends|yield|static|package|func|go|defer|break|continue|raise|elif|lambda|not|and|or|is|super)$/;
  function highlight(line) {
    let out = "", m;
    const re = /(\/\/.*$|#(?!\[).*$|\/\*.*?\*\/)|("(?:\\.|[^"])*"|'(?:\\.|[^'])*'|`[^`]*`)|(\b\d[\d_.]*\b)|([A-Za-z_]\w*)(?=\s*[(!])|([A-Za-z_]\w*)|(\s+|.)/g;
    while ((m = re.exec(line))) {
      if (m[1]) out += '<span class="c">' + esc(m[1]) + "</span>";
      else if (m[2]) out += '<span class="s">' + esc(m[2]) + "</span>";
      else if (m[3]) out += '<span class="n">' + esc(m[3]) + "</span>";
      else if (m[4]) out += KW.test(m[4]) ? '<span class="k">' + m[4] + "</span>" : '<span class="f">' + m[4] + "</span>";
      else if (m[5]) out += KW.test(m[5]) ? '<span class="k">' + m[5] + "</span>" : /^[A-Z]/.test(m[5]) ? '<span class="t">' + m[5] + "</span>" : m[5];
      else out += esc(m[6]);
    }
    return out || "&nbsp;";
  }


  // ------------------------------------------------------------ icons (original, 24x24, filled; no emoji fonts needed)
  const ICONS = {
    flask: "M9 2h6v2h-1v5.2l5.6 9.4A2 2 0 0 1 17.9 22H6.1a2 2 0 0 1-1.7-3.4L10 9.2V4H9zM7.6 16l-1.5 2.6c-.1.2 0 .4.2.4h11.4c.2 0 .3-.2.2-.4L16.4 16z",
    anvil: "M2 5h14a6 6 0 0 1-5 5.9V13h3v3H8v-3h1v-2.1A6 6 0 0 1 2 5zm17 0h3v3h-3zM5 18h14v3H5z",
    castle: "M3 21V8h3V4h2v4h2V4h4v4h2V4h2v4h3v13h-7v-5a2 2 0 0 0-4 0v5z",
    book: "M5 3h13a1 1 0 0 1 1 1v14H7a1 1 0 0 0 0 2h12v2H7a3 3 0 0 1-3-3V4a1 1 0 0 1 1-1zm4 4v2h7V7z",
    house: "M12 3l10 8.5-1.3 1.5L19 11.6V21h-5v-6h-4v6H5v-9.4L3.3 13 2 11.5z",
    robot: "M11 1h2v3h4a3 3 0 0 1 3 3v9a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3h4zM8.5 9a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6zm7 0a1.8 1.8 0 1 0 0 3.6 1.8 1.8 0 0 0 0-3.6zM8 15v1.5h8V15zM0 9h2v6H0zm22 0h2v6h-2z",
    toolbox: "M8 3h8v4h6v14H2V7h6zm2 2v2h4V5zM2 12v2h20v-2z",
    gem: "M6 3h12l5 6.5L12 22 1 9.5zm1.3 2L4.6 8.5h4.2L10 5zm9.4 0H14l1.2 3.5h4.2zM12 5.6 10.9 8.5h2.2z",
    flag: "M4 2h2v20H4zm3 1h13l-3.5 5 3.5 5H7z",
    anchor: "M12 2a3 3 0 0 1 1 5.8V10h4v2h-4v8a7 7 0 0 0 6-6h-2l3-4 3 4h-2a9 9 0 0 1-18 0H1l3-4 3 4H5a7 7 0 0 0 6 6v-8H7v-2h4V7.8A3 3 0 0 1 12 2zm0 2a1 1 0 1 0 0 2 1 1 0 0 0 0-2z",
    tree: "M12 1l6.5 8.5H15l5.5 7.5H13v5h-2v-5H3.5L9 9.5H5.5z",
    rocket: "M12 1c4.5 3 6 7.5 6 12l2.5 3.5V22l-5-2.5H8.5l-5 2.5v-5.5L6 13c0-4.5 1.5-9 6-12zm0 7.5a2.2 2.2 0 1 0 0 4.4 2.2 2.2 0 0 0 0-4.4z",
    tower: "M9 1h6l1 7h-2v2h3l2 12H5l2-12h3V8H8z",
    box: "M12 2l10 4.5v11L12 22 2 17.5v-11zm0 2.2L5.2 7.2 12 10.3l6.8-3.1zM4 8.8v7.4l7 3.2v-7.5z",
    crate: "M2 6h20v15H2zm2 2v5h7V8zm9 0v5h7V8zM4 15v4h7v-4zm9 0v4h7v-4zM5 2h14l3 4H2z",
    city: "M1 22V11h6V3h8v8h3V7h5v15zm8-16v2h2V6zm0 4v2h2v-2zm0 4v2h2v-2zm4-8v2h-1V6zm6 4v2h2v-2zm0 4v2h2v-2z",
    flower: "M12 2a3.5 3.5 0 0 1 3.4 4.3A3.5 3.5 0 1 1 17 13a3.5 3.5 0 1 1-5 4.5V22h-1.5v-4.5A3.5 3.5 0 1 1 7 13a3.5 3.5 0 1 1 1.6-6.7A3.5 3.5 0 0 1 12 2zm0 6.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4z",
    gate: "M1 3h22v3h-2.5v2H17v14h-2.5V8h-5v14H7V8H3.5V6H1z",
    pine: "M12 1l5 7h-2.5l4.5 6h-3l4.5 6H13v3h-2v-3H3.5L8 14H5l4.5-6H7z",
    crystal: "M12 1l5 7-5 15-5-15zM6 8l-5 4 7 7zm12 0 5 4-7 7z",
    mountain: "M1 21 9 6l4.5 7.5L16 10l7 11zm8-11.5L7 13l2 1 2-1z",
    columns: "M12 1l10 5v2H2V6zM3 20h18v3H3zM5 10h3v8H5zm5.5 0h3v8h-3zm5.5 0h3v8h-3z",
    flame: "M12 1c1.5 4.5 7 6.5 7 13a7 7 0 0 1-14 0c0-3.5 2-6 3.5-7 0 2.5 1 4 2.5 4.5C10.5 8 10 5 12 1z",
    cloud: "M7 19A5.5 5.5 0 0 1 6.2 8.1 6.5 6.5 0 0 1 18.4 8 5.5 5.5 0 0 1 18 19z",
    drop: "M12 1s7.5 8.5 7.5 14a7.5 7.5 0 0 1-15 0C4.5 9.5 12 1 12 1z",
    trophy: "M6 2h12v2h4v4a5 5 0 0 1-5 5h-.5A6 6 0 0 1 13 16v3h4v3H7v-3h4v-3a6 6 0 0 1-3.5-3H7a5 5 0 0 1-5-5V4h4zM4 6v2a3 3 0 0 0 2.2 2.9A9 9 0 0 1 6 9V6zm14 0v3a9 9 0 0 1-.2 1.9A3 3 0 0 0 20 8V6z",
    warning: "M12 1l11.5 20.5H.5zM11 8v7h2V8zm0 9v2h2v-2z",
    swords: "M2 2h4l9 9-2 2L4 6zm20 0v4l-9 9-2-2 9-9zM4.5 16.5l3 3L5 22l-3-3zm15 0 2.5 2.5-3 3-2.5-2.5zM6 14l4 4-1.5 1.5-4-4zm12 0 1.5 1.5-4 4L14 18z",
    ticket: "M2 5h20v5a2 2 0 0 0 0 4v5H2v-5a2 2 0 0 0 0-4zm13 2v2h2V7zm0 4v2h2v-2zm0 4v2h2v-2z",
    pointer: "M6 1l14 12.5h-7.2l4 8.2-3 1.5-4-8.3L6 20z",
    check: "M12 1a11 11 0 1 1 0 22 11 11 0 0 1 0-22zm5.3 7.3-6.6 6.6-3.2-3.2-1.6 1.6 4.8 4.8 8.2-8.2z",
    star: "M12 1.5l3.2 6.6 7.3 1-5.3 5.1 1.3 7.2L12 18l-6.5 3.4 1.3-7.2L1.5 9.1l7.3-1z",
    burst: "M12 0l2.4 5.6L20 3l-1.6 5.9L24 10.6l-5 3.4 3 5.3-6-.6L14.6 24 12 19l-2.6 5-1.4-5.9-6 .6 3-5.3-5-3.4 5.6-1.7L4 3l5.6 2.6z",
    arrowdown: "M10.5 2h3v13.4l5-5L20.6 12 12 20.6 3.4 12l2.1-2.1 5 5z",
    bolt: "M14 1 3 14h8l-2 9 12-14h-8z",
    sparkle: "M12 1l2.6 8.4L23 12l-8.4 2.6L12 23l-2.6-8.4L1 12l8.4-2.6z",
    play: "M6 3l15 9-15 9z",
    dot: "M12 4a8 8 0 1 1 0 16 8 8 0 0 1 0-16z"
  };
  function icon(name, color, sizeEm, extra) {
    const s = el("span", "icon", null, `display:inline-flex;width:${sizeEm || 1}em;height:${sizeEm || 1}em;vertical-align:-.15em;${extra || ""}`);
    s.innerHTML = `<svg viewBox="0 0 24 24" width="100%" height="100%"><path d="${ICONS[name] || ICONS.star}" fill="${color || "currentColor"}" fill-rule="evenodd"/></svg>`;
    return s;
  }
  function stopSign(sizeEm) {
    const s = el("span", "icon", null, `display:inline-flex;width:${sizeEm}em;height:${sizeEm}em`);
    s.innerHTML = '<svg viewBox="0 0 100 100" width="100%" height="100%"><polygon points="30,2 70,2 98,30 98,70 70,98 30,98 2,70 2,30" fill="#e8112d" stroke="#fff" stroke-width="5"/>' +
      '<text x="50" y="62" text-anchor="middle" font-family="Anton,Impact,sans-serif" font-size="32" fill="#fff" letter-spacing="1">STOP</text></svg>';
    return s;
  }
  const PATHS = {};
  function iconPath(name) { return PATHS[name] || (PATHS[name] = new Path2D(ICONS[name] || ICONS.star)); }

  // ------------------------------------------------------------ animation kinds: (a, lt) -> writes a.el.__tf / __op
  // Transforms compose: an element can rise AND bob AND punch; the renderer joins them each frame.
  const K = {
    fade: (a, lt) => { a.el.__op *= E.out((lt - a.at) / (a.dur || 0.5)); },
    out: (a, lt) => { a.el.__op *= 1 - E.out((lt - a.at) / (a.dur || 0.4)); },
    rise: (a, lt) => { const p = E.out((lt - a.at) / (a.dur || 0.6)); a.el.__op *= p; a.el.__tf.push(`translateY(${(1 - p) * (a.dist || 40)}px)`); },
    drop: (a, lt) => { const p = E.bounce((lt - a.at) / (a.dur || 0.8)); a.el.__op *= clamp((lt - a.at) * 8); a.el.__tf.push(`translateY(${(1 - p) * -(a.dist || 400)}px)`); },
    slideX: (a, lt) => { const p = E.out((lt - a.at) / (a.dur || 0.6)); a.el.__op *= clamp(p * 3); a.el.__tf.push(`translateX(${(1 - p) * (a.dist || 300)}px)`); },
    pop: (a, lt) => { const p = (lt - a.at) / (a.dur || 0.5); a.el.__op *= clamp(p * 4); a.el.__tf.push(`scale(${lt < a.at ? 0 : E.back(p)})`); },
    slam: (a, lt) => {
      const p = clamp((lt - a.at) / (a.dur || 0.32)), s = 1 + (a.from || 2.6) * Math.pow(1 - p, 2);
      a.el.__op *= clamp(p * 3); a.el.__tf.push(`scale(${s})`); a.el.__blur = Math.max(a.el.__blur || 0, (1 - p) * 10);
    },
    zoomin: (a, lt) => { const p = E.out((lt - a.at) / (a.dur || 1.2)); a.el.__op *= a.hard ? (lt >= a.at ? 1 : 0) : clamp(p * 2.5); a.el.__tf.push(`scale(${(a.from || 1.12) + (1 - (a.from || 1.12)) * p})`); a.el.__blur = Math.max(a.el.__blur || 0, (1 - p) * (a.blur || 0)); },
    flip: (a, lt) => { const p = E.back((lt - a.at) / (a.dur || 0.6)); a.el.__op *= clamp((lt - a.at) * 6); a.el.__tf.push(`perspective(900px) rotateX(${(1 - p) * -95}deg)`); },
    spin: (a, lt) => { a.el.__tf.push(`rotate(${(a.from || 0) + lt * (a.speed || 30)}deg)`); },
    bob: (a, lt) => { a.el.__tf.push(`translateY(${Math.sin((lt + (a.phase || 0)) * (a.speed || 2.4)) * (a.amp || 6)}px)`); },
    wobble: (a, lt) => { a.el.__tf.push(`rotate(${Math.sin((lt + (a.phase || 0)) * (a.speed || 3)) * (a.amp || 4)}deg)`); },
    tilt: (a) => { a.el.__tf.push(`rotate(${a.deg}deg)`); },
    blink: (a, lt) => { if (lt >= a.at) a.el.__op *= Math.floor((lt - a.at) * (a.rate || 2)) % 2 ? 0.08 : 1; },
    type: (a, lt) => { const n = Math.floor(Math.max(0, lt - a.at) * (a.cps || 28)); a.el.textContent = a.text.slice(0, n); },
    count: (a, lt) => { const p = E.out((lt - a.at) / (a.dur || 1.3)); a.el.textContent = a.pre + fmt(a.num * p, a.dec) + a.post; },
    grow: (a, lt) => { a.el.style.width = (a.to * E.out((lt - a.at) / (a.dur || 0.9))) + "%"; },
    growY: (a, lt) => { a.el.style.height = (a.to * E.out((lt - a.at) / (a.dur || 0.9))) + "%"; },
    draw: (a, lt) => { const p = E.inout((lt - a.at) / (a.dur || 0.8)); a.el.style.strokeDashoffset = a.len * (1 - p); a.el.style.opacity = p > 0 ? 1 : 0; },
    on: (a, lt) => { a.el.classList.toggle(a.cls, lt >= a.at && (a.until == null || lt < a.until)); },
    show: (a, lt) => { if (lt < a.at || (a.until != null && lt >= a.until)) a.el.__op = 0; },
    scroll: (a, lt) => { a.el.__tf.push(`translateY(${-lt * (a.speed || 40)}px)`); },
    tear: (a, lt) => { const b = a.beat || 0.6, ph = (lt % b) / b, r = prng(Math.floor(lt / b) * 31 + a.k); a.el.__op *= ph < 0.18 && r() < 0.6 ? 1 : 0; a.el.__tf.push(`translateX(${(r() - 0.5) * 120}px)`); },
    track: (a, lt) => { a.el.style.letterSpacing = (a.from + (a.to - a.from) * E.out((lt - a.at) / (a.dur || 3))) + "em"; },
    shine: (a, lt) => { a.el.style.backgroundPosition = `${-200 + ((lt - a.at) * (a.speed || 60)) % 400}% 0`; },
    shake: (a, lt) => { if (lt < a.at || lt > a.at + (a.dur || 0.4)) return; const r = prng(Math.floor(lt * 60) + 7), k = (a.amp || 10) * (1 - (lt - a.at) / (a.dur || 0.4)); a.el.__tf.push(`translate(${(r() - 0.5) * k}px,${(r() - 0.5) * k}px)`); },
    rgb: (a, lt) => { // chromatic glitch: offsets jump on a seeded schedule
      const r = prng(Math.floor(lt * 14) + (a.seed || 1)), on = lt >= a.at && r() < (a.rate || 0.5), k = on ? (a.amp || 6) : 1.2;
      a.el.style.textShadow = `${k * (r() - 0.3)}px 0 #ff2a55, ${-k * (r() - 0.3)}px 0 #29f1ff`;
      a.el.__tf.push(on ? `translateX(${(r() - 0.5) * k * 2}px) skewX(${(r() - 0.5) * k}deg)` : "");
    },
    drain: (a, lt) => { a.el.style.width = (100 - 100 * E.inout((lt - a.at) / a.dur)) + "%"; },
    unroll: (a, lt) => { const p = E.out((lt - a.at) / (a.dur || 0.9)); a.el.__tf.push(`scaleY(${0.04 + 0.96 * p})`); },
    press: (a, lt) => { if (lt >= a.at && lt < a.at + 0.18) a.el.__tf.push("translateY(6px) scale(.97)"); },
    along: (a, lt) => { // move through points [{x,y,t}] (px, local t)
      const P = a.points; let i = 0;
      while (i < P.length - 1 && lt > P[i + 1].t) i++;
      const p0 = P[i], p1 = P[Math.min(i + 1, P.length - 1)], q = p1.t > p0.t ? E.inout((lt - p0.t) / (p1.t - p0.t)) : 1;
      a.el.__tf.push(`translate(${p0.x + (p1.x - p0.x) * q}px,${p0.y + (p1.y - p0.y) * q}px)`);
    }
  };
  function fmt(x, dec) { return dec ? x.toFixed(dec) : Math.round(x).toLocaleString("en-US"); }

  // ------------------------------------------------------------ Bit, the mascot (SVG, lip-syncs to the voice)
  const COSTUMES = {
    shades: '<path d="M20 36 h60 v5 h-3 l-3 13 q-1 3 -4 3 h-12 q-3 0 -4 -3 l-2 -9 h-4 l-2 9 q-1 3 -4 3 h-12 q-3 0 -4 -3 l-3 -13 h-3z" fill="#111" stroke="#f5c451" stroke-width="2"/><path d="M28 42 l6 0 M58 42 l6 0" stroke="#fff" stroke-width="2.5" stroke-linecap="round" opacity=".85"/>',
    cap: '<path d="M18 28 q32-22 64 0 v6 h-64z" fill="#e8113a"/><rect x="12" y="32" width="76" height="7" rx="3" fill="#0b2140"/><circle cx="50" cy="20" r="5" fill="#ffb000"/><rect x="40" y="27" width="20" height="6" rx="2" fill="#ffb000"/>',
    crown: '<path d="M26 26 l8-16 l8 10 l8-14 l8 14 l8-10 l8 16z" fill="#ffd23f" stroke="#b8860b" stroke-width="2"/><circle cx="50" cy="12" r="3" fill="#ff3b6b"/>',
    tie: '<path d="M44 92 l6-6 l6 6 l-3 14 l-3 4 l-3-4z" fill="#e8112d"/><rect x="34" y="84" width="32" height="6" rx="3" fill="#fff"/>'
  };
  function mascot(fmt, sizeEm) {
    const wrap = el("div", "mascot", null, `width:${sizeEm}em;height:${sizeEm * 1.15}em`);
    const c = FORMATS[fmt];
    wrap.innerHTML = `<svg viewBox="0 0 100 115" width="100%" height="100%" style="overflow:visible">
      <ellipse cx="50" cy="111" rx="26" ry="4" fill="rgba(0,0,0,.25)"/>
      <g class="body">
        <line x1="50" y1="18" x2="50" y2="6" stroke="${c.fg}" stroke-width="3"/><circle class="ant" cx="50" cy="5" r="5" fill="${c.accent}"/>
        <g class="armL"><rect x="6" y="58" width="12" height="26" rx="6" fill="${c.accent2}"/></g>
        <g class="armR"><rect x="82" y="58" width="12" height="26" rx="6" fill="${c.accent2}"/></g>
        <rect x="16" y="18" width="68" height="62" rx="18" fill="${c.accent2}" stroke="rgba(0,0,0,.25)" stroke-width="3"/>
        <rect x="24" y="28" width="52" height="40" rx="12" fill="#0d1020"/>
        <g class="eyes"><rect class="eye" x="34" y="38" width="9" height="14" rx="4.5" fill="#7df9ff"/><rect class="eye" x="57" y="38" width="9" height="14" rx="4.5" fill="#7df9ff"/></g>
        <path class="mouth" d="M41 58 q9 6 18 0" stroke="#7df9ff" stroke-width="3" fill="none" stroke-linecap="round"/>
        <rect x="36" y="80" width="28" height="24" rx="8" fill="${c.accent2}" stroke="rgba(0,0,0,.25)" stroke-width="3"/>
        <g class="costume">${COSTUMES[c.costume] || ""}</g>
      </g></svg>`;
    const q = s => wrap.querySelector(s);
    const body = q(".body"), armL = q(".armL"), armR = q(".armR"), eyes = wrap.querySelectorAll(".eye"), mouth = q(".mouth"), ant = q(".ant");
    return {
      el: wrap,
      // pose: idle | wave | cheer | point | talk ; talking: bool (a word is being spoken now)
      update(lt, pose, talking) {
        const bob = Math.sin(lt * 3.2) * 2.2;
        let jump = 0, aL = 0, aR = 0;
        if (pose === "wave") aR = -130 + Math.sin(lt * 9) * 25;
        if (pose === "cheer") { jump = -Math.abs(Math.sin(lt * 6)) * 14; aL = 150; aR = -150; }
        if (pose === "point") aR = -80;
        body.setAttribute("transform", `translate(0 ${bob + jump})`);
        armL.setAttribute("transform", `rotate(${aL} 12 60)`);
        armR.setAttribute("transform", `rotate(${aR} 88 60)`);
        const blink = (lt % 3.1) < 0.12 ? 0.15 : 1;
        eyes.forEach(e => e.setAttribute("transform", `translate(0 ${45 * (1 - blink)}) scale(1 ${blink})`));
        const open = talking ? 0.35 + 0.65 * Math.abs(Math.sin(lt * 17)) : 0;
        mouth.setAttribute("d", open ? `M41 57 q9 ${4 + open * 10} 18 0 q-9 ${-3 + open * 2} -18 0` : "M41 58 q9 6 18 0");
        ant.setAttribute("opacity", 0.6 + 0.4 * Math.sin(lt * 5));
      }
    };
  }

  // ------------------------------------------------------------ the video
  function createVideo(root, story) {
    const F = FORMATS[story.format] || FORMATS.metro;
    const W = story.width || 1280, H = story.height || 720, base = Math.min(W, H) / 36, portrait = H > W;
    const beat = story.bpm ? 60 / story.bpm : 0;
    if (!document.getElementById("r2v-css")) {
      const st = el("style"); st.id = "r2v-css"; st.textContent = (g.Repo2VideoFonts || "") + CSS; document.head.appendChild(st);
    }
    const stage = el("div", "r2v fmt-" + story.format + (portrait ? " portrait" : ""));
    stage.style.cssText = `width:${W}px;height:${H}px;font-size:${base}px;--bg:${F.bg};--fg:${F.fg};--accent:${F.accent};--accent2:${F.accent2};--font:${F.font};--display:${F.display}`;
    root.appendChild(stage);

    const times = timeline(story), total = times.length ? times[times.length - 1].start + times[times.length - 1].duration : 0;
    const liftAt = times[story.lift || 0] ? times[story.lift || 0].start : 0;
    const cues = [], bursts = [], updaters = [];
    const seed = (story.seed || 1) * 7919;

    const bg = el("div", "layer bg"); stage.appendChild(bg);
    const bgUpdate = BACKGROUNDS[story.format](bg, { W, H, base, F, story, seed });
    const world = el("div", "world"); stage.appendChild(world);
    const fx = el("canvas"); fx.width = W; fx.height = H; stage.appendChild(fx);
    const ctx2d = fx.getContext("2d");
    const overlay = el("div", "layer"); stage.appendChild(overlay);
    const ovUpdate = (OVERLAYS[story.format] || (() => () => {}))(overlay, { W, H, base, F, story, times, total });

    const built = story.scenes.map((s, i) => {
      const tm = times[i], box = el("div", "scene sc-" + s.type), anims = [];
      const words = wordTimes(s, tm);
      const c = {
        s, box, tm, story, W, H, base, F, portrait, words, i,
        A(node, kind, at, o) { anims.push(Object.assign({ el: node, kind, at: at || 0 }, o || {})); if (o && o.sfx) c.cue(at, o.sfx, o.gain, o.pan); return node; },
        cue(at, sfx, gain, pan) { cues.push({ t: +(tm.start + at).toFixed(3), sfx, gain: gain == null ? 0.5 : gain, pan: pan || 0 }); },
        burst(at, x, y, o) { bursts.push(Object.assign({ t: tm.start + at, x, y, n: 40, kind: "confetti", life: 2.2, seed: seed + bursts.length * 101 }, o || {})); },
        mascot(pose, x, y, size, poses) {
          const m = mascot(story.format, size || 7);
          m.el.style.left = x + "px"; m.el.style.top = y + "px";
          box.appendChild(m.el);
          updaters.push({ i, fn: lt => m.update(lt, typeof poses === "function" ? poses(lt) : pose, words.some(w => lt >= w.a && lt < w.b - 0.03)) });
          return m.el;
        },
        say: (phrase, from, fb) => sayAt(words, phrase, from, fb),
        typeSfx(at, text, cps) { for (let k = 0; k < text.length; k += 2) if (text[k] !== " ") c.cue(at + k / (cps || 28), "type", 0.22, 0.2); },
        beat
      };
      (SCENES[s.type] || SCENES.fallback)(c);
      box.style.display = "none";
      world.appendChild(box);
      if (i > 0 && F.cut) c.cue(0, s.type === "reveal" ? "braam" : F.cut, F.cut === "hit" ? 0.55 : 0.4);
      return { box, anims, s, tm, words, i };
    });

    // captions
    const cap = el("div", "cap cap-" + F.caps), capBox = el("div", "box"), capWho = el("div", "who");
    if (F.caps === "dialog") { const m = mascot("quest", 3.2); capWho.appendChild(m.el); m.el.style.position = "relative"; capBox.appendChild(capWho); capWho.__m = m; }
    cap.appendChild(capBox);
    if (story.captions !== false) stage.appendChild(cap);
    const capLines = built.map(b => chunk(b.words, F.caps === "tiktok" ? 3 : F.caps === "dialog" ? 14 : F.caps === "letterbox" ? 12 : 9));
    let capKey = "";

    // film grain: one seeded noise tile, jittered every frame
    const grain = el("div", "grain");
    grain.style.backgroundImage = `url(${noiseTile(seed)})`;
    grain.style.opacity = F.grain;
    stage.appendChild(grain);
    if (story.format !== "quest") stage.appendChild(el("div", "vignette"));
    const flash = el("div", "flash"); stage.appendChild(flash);
    const band = el("div", "band"); band.style.display = "none"; stage.appendChild(band);

    function render(t) {
      t = Math.min(t, total - 1e-4);
      bgUpdate(t);
      // camera: slow push in each scene, plus a punch on every beat once the music drops
      let punch = 0;
      if (beat && t >= liftAt && F.punch) { const since = (t - liftAt) % beat; punch = F.punch * Math.exp(-since * 9); }
      ctx2d.clearRect(0, 0, W, H);
      let active = 0;
      built.forEach((b, i) => { if (t >= b.tm.start) active = i; });
      built.forEach((b, i) => {
        const lt = t - b.tm.start, d = b.tm.duration;
        const showing = i === active || (i === active - 1 && t - built[active].tm.start < TR);
        b.box.style.display = showing ? "block" : "none";
        if (!showing) return;
        // reset composable state, run anims, apply
        const touched = [];
        b.anims.forEach(a => { if (!a.el.__frame || a.el.__frame !== t) { a.el.__frame = t; a.el.__tf = []; a.el.__op = 1; a.el.__blur = 0; touched.push(a.el); } });
        b.anims.forEach(a => K[a.kind](a, lt, d));
        touched.forEach(e => {
          e.style.transform = (e.__base || "") + " " + e.__tf.join(" ");
          e.style.opacity = e.__op;
          if (e.__blur > 0.2) e.style.filter = `blur(${e.__blur}px)`; else if (e.style.filter) e.style.filter = "";
        });
        updaters.forEach(u => { if (u.i === i) u.fn(lt); });
        // transitions
        const tin = clamp(lt / TR), tout = clamp((lt - d) / TR);
        const cam = 1 + F.push * clamp(lt / d) + punch;
        let tf = `scale(${cam})`, op = 1, clip = "";
        if (i === active && i > 0 && tin < 1) {
          if (F.trans === "slide") tf = `translateX(${(1 - E.inout(tin)) * W}px) ` + tf;
          if (F.trans === "iris") clip = `circle(${E.inout(tin) * 75}% at 50% 50%)`;
          if (F.trans === "punch") tf = `scale(${1 + 0.35 * (1 - E.out(tin))}) rotate(${(1 - E.out(tin)) * -4}deg) ` + tf;
          if (F.trans === "flash") tf = `scale(${1 + 0.08 * (1 - E.out(tin))}) ` + tf;
          if (F.trans === "swoosh" && tin < 0.45) op = 0;
        }
        if (i === active - 1) {
          if (F.trans === "slide") tf = `translateX(${-E.inout(tout) * W}px) ` + tf;
          else if (F.trans === "swoosh") op = tout < 0.45 ? 1 : 0;
          else if (F.trans === "punch") { tf = `scale(${1 - 0.15 * E.out(tout)}) ` + tf; op = 1 - E.out(tout * 2); }
          else if (F.trans === "flash") op = 0;
        }
        b.box.style.transform = tf;
        b.box.style.opacity = op;
        b.box.style.clipPath = clip;
        b.box.style.zIndex = i === active ? 2 : 1;
      });
      // flash / swoosh band
      const la = t - built[active].tm.start;
      flash.style.opacity = F.trans === "flash" && active > 0 ? Math.max(0, 0.85 - la * 5) : 0;
      if (F.trans === "swoosh" && active > 0 && la < TR) { band.style.display = "block"; band.style.left = (-80 + 190 * E.inout(la / TR)) + "%"; }
      else band.style.display = "none";
      // particles
      drawBursts(ctx2d, bursts, t, W, H);
      // captions
      captionsAt(t);
      ovUpdate(t);
      grain.style.transform = `translate(${Math.floor(prng(Math.floor(t * 24))() * 64)}px,${Math.floor(prng(Math.floor(t * 24) + 99)() * 64)}px)`;
    }

    function captionsAt(t) {
      const b = built.find(x => t >= x.tm.start && t < x.tm.start + x.tm.duration) || built[built.length - 1];
      const lt = t - b.tm.start, lines = capLines[b.i];
      const line = lines.find(L => lt >= L[0].a - 0.05 && lt < L[L.length - 1].b + 0.35) || null;
      const hide = !line || (story.format === "trailer" && ["coldopen", "reveal", "montage"].indexOf(b.s.type) >= 0) || b.s.type === "hook";
      cap.style.display = hide ? "none" : "block";
      if (hide) return;
      const key = b.i + ":" + lines.indexOf(line);
      if (key !== capKey) {
        capKey = key;
        [...capBox.querySelectorAll(".w")].forEach(n => n.remove());
        line.forEach(w => { const s = el("span", "w", w.w); s.__a = w.a; s.__b = w.b; capBox.appendChild(s); });
      }
      capBox.querySelectorAll(".w").forEach(s => {
        s.classList.toggle("on", lt >= s.__a && lt < s.__b);
        s.classList.toggle("done", lt >= s.__b);
        if (F.caps === "tiktok") s.style.transform = lt >= s.__a && lt < s.__b ? `scale(${1.12 - 0.12 * clamp((lt - s.__a) * 6)})` : "";
      });
      if (capWho.__m) capWho.__m.update(lt, "idle", line.some(w => lt >= w.a && lt < w.b));
    }

    render(0);
    cues.sort((a, b) => a.t - b.t);
    return { duration: total, scenes: times, cues, render, el: stage };
  }

  function chunk(words, maxWords) {
    const out = []; let cur = [];
    words.forEach(w => { cur.push(w); if (cur.length >= maxWords || /[.!?]$/.test(w.w)) { out.push(cur); cur = []; } });
    if (cur.length) out.push(cur);
    return out;
  }

  function noiseTile(seed) {
    const c = document.createElement("canvas"); c.width = c.height = 128;
    const x = c.getContext("2d"), img = x.createImageData(128, 128), r = prng(seed);
    for (let i = 0; i < img.data.length; i += 4) { const v = r() * 255; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255; }
    x.putImageData(img, 0, 0);
    return c.toDataURL();
  }

  // particles: every burst is replayed from its seed at time t (no state between frames)
  function drawBursts(x, bursts, t, W, H) {
    bursts.forEach(b => {
      const age = t - b.t;
      if (age < 0 || age > b.life) return;
      const r = prng(b.seed), cols = b.colors || ["#ffd23f", "#ff3b6b", "#29c5f6", "#3ddc84", "#ffffff", "#b36bff"];
      for (let k = 0; k < b.n; k++) {
        const ang = (b.angle != null ? b.angle : -Math.PI / 2) + (r() - 0.5) * (b.spread || Math.PI * 1.6);
        const sp = (b.speed || 900) * (0.35 + r() * 0.75), size = (b.size || 10) * (0.5 + r()), col = cols[Math.floor(r() * cols.length)];
        const spin = (r() - 0.5) * 14, drag = Math.exp(-age * (b.drag || 1.6));
        const dist = sp * (1 - drag) / (b.drag || 1.6);
        const px = b.x * W + Math.cos(ang) * dist, py = b.y * H + Math.sin(ang) * dist + (b.gravity == null ? 520 : b.gravity) * age * age * 0.5;
        const alpha = clamp(1 - age / b.life) * clamp(age * 20);
        x.save(); x.globalAlpha = alpha; x.translate(px, py); x.rotate(spin * age);
        if (b.kind === "confetti") { x.fillStyle = col; x.fillRect(-size / 2, -size / 4, size, size / 2); }
        else if (b.kind === "sparks") { x.strokeStyle = col; x.lineWidth = 2.5; x.beginPath(); x.moveTo(0, 0); x.lineTo(-Math.cos(ang) * size * 3, -Math.sin(ang) * size * 3); x.stroke(); }
        else if (b.kind === "stars") { x.fillStyle = col; star(x, size); }
        else if (b.kind === "icons") { const ic = b.icons[k % b.icons.length], sc = size * 3 / 24; x.fillStyle = col; x.scale(sc, sc); x.translate(-12, -12); x.fill(iconPath(ic), "evenodd"); }
        else if (b.kind === "pixels") { x.fillStyle = col; const s2 = Math.round(size / 2) * 2; x.fillRect(-s2 / 2, -s2 / 2, s2, s2); }
        x.restore();
      }
    });
  }
  function star(x, s) { x.beginPath(); for (let i = 0; i < 10; i++) { const r = i % 2 ? s * 0.45 : s, a = -Math.PI / 2 + i * Math.PI / 5; x.lineTo(Math.cos(a) * r, Math.sin(a) * r); } x.closePath(); x.fill(); }

  // ------------------------------------------------------------ backgrounds (return update(t))
  const BACKGROUNDS = {
    trailer(bg, o) {
      bg.style.background = "#050505";
      const rays = el("div", "layer", null, "background:conic-gradient(from 0deg at 50% -10%,transparent 0deg,rgba(255,220,150,.07) 8deg,transparent 16deg,transparent 30deg,rgba(255,220,150,.05) 38deg,transparent 46deg,transparent 70deg,rgba(255,220,150,.06) 80deg,transparent 92deg);mix-blend-mode:screen");
      bg.appendChild(rays);
      const cv = el("canvas"); cv.width = o.W; cv.height = o.H; bg.appendChild(cv);
      const x = cv.getContext("2d"), r = prng(o.seed + 5), dust = Array.from({ length: 90 }, () => [r(), r(), r(), r()]);
      return t => {
        rays.style.transform = `rotate(${Math.sin(t * 0.25) * 6}deg)`;
        x.clearRect(0, 0, o.W, o.H);
        dust.forEach(([a, b, c, d]) => {
          const px = ((a + t * 0.006 * (0.5 + c)) % 1) * o.W, py = ((b + Math.sin(t * 0.3 + d * 6) * 0.01 - t * 0.004 * c) % 1 + 1) % 1 * o.H;
          x.fillStyle = `rgba(255,230,180,${0.12 + 0.3 * c * (0.5 + 0.5 * Math.sin(t * 2 + d * 9))})`;
          x.beginPath(); x.arc(px, py, 0.6 + c * 1.8, 0, 7); x.fill();
        });
      };
    },
    metro(bg, o) {
      bg.style.background = "radial-gradient(120% 90% at 70% 10%,#14335a 0%,#0a1726 60%)";
      const cv = el("canvas"); cv.width = o.W; cv.height = o.H; bg.appendChild(cv);
      const x = cv.getContext("2d"), r = prng(o.seed + 9), cols = o.F.lines;
      const tracks = Array.from({ length: 7 }, (_, i) => ({ y: r() * o.H, c: cols[i % cols.length], sp: 40 + r() * 80, w: 3 + r() * 4, ph: r() * 3000 }));
      return t => {
        x.clearRect(0, 0, o.W, o.H);
        x.strokeStyle = "rgba(120,170,255,.06)"; x.lineWidth = 1;
        for (let gx = -((t * 12) % 48); gx < o.W; gx += 48) { x.beginPath(); x.moveTo(gx, 0); x.lineTo(gx, o.H); x.stroke(); }
        for (let gy = 0; gy < o.H; gy += 48) { x.beginPath(); x.moveTo(0, gy); x.lineTo(o.W, gy); x.stroke(); }
        tracks.forEach(k => {
          x.globalAlpha = 0.16; x.strokeStyle = k.c; x.lineWidth = k.w; x.beginPath(); x.moveTo(0, k.y); x.lineTo(o.W, k.y); x.stroke();
          const tx = ((t * k.sp + k.ph) % (o.W + 400)) - 200;
          x.globalAlpha = 0.55; x.fillStyle = k.c; x.fillRect(tx, k.y - k.w * 1.2, 90, k.w * 2.4);
          x.globalAlpha = 1;
        });
      };
    },
    quest(bg, o) {
      bg.style.background = "linear-gradient(180deg,#120f3a 0%,#2b1f6e 55%,#5a3a9e 100%)";
      const cv = el("canvas"); cv.width = o.W; cv.height = o.H; bg.appendChild(cv);
      const x = cv.getContext("2d"), r = prng(o.seed + 3), P = Math.round(o.base * 0.25) * 2;
      const stars = Array.from({ length: 70 }, () => [r() * o.W, r() * o.H * 0.75, r()]);
      const clouds = Array.from({ length: 6 }, () => [r() * o.W, o.H * (0.12 + r() * 0.5), 3 + Math.floor(r() * 5), r()]);
      return t => {
        x.clearRect(0, 0, o.W, o.H); x.imageSmoothingEnabled = false;
        stars.forEach(([sx, sy, k]) => { x.fillStyle = `rgba(255,247,224,${0.3 + 0.7 * (Math.sin(t * 3 + k * 20) > 0.6 ? 1 : 0.3)})`; x.fillRect(Math.round(sx / P) * P, Math.round(sy / P) * P, P, P); });
        clouds.forEach(([cx, cy, w, k]) => {
          const px = Math.round((((cx + t * (10 + 20 * k)) % (o.W + 300)) - 150) / P) * P;
          x.fillStyle = "rgba(255,255,255,.12)";
          for (let i = 0; i < w; i++) x.fillRect(px + i * P * 3, cy - (i % 2) * P * 2, P * 4, P * 3);
        });
        x.fillStyle = "#2a8a4a"; x.fillRect(0, o.H - P * 4, o.W, P * 4);
        x.fillStyle = "#3ddc84"; for (let gx = 0; gx < o.W; gx += P * 2) x.fillRect(gx, o.H - P * 4 - ((gx / P) % 3 === 0 ? P : 0), P, P);
        x.fillStyle = "#6b4226"; x.fillRect(0, o.H - P * 2, o.W, P * 2);
      };
    },
    news(bg, o) {
      bg.style.background = "radial-gradient(110% 90% at 75% 40%,#123a8a 0%,#06122e 65%)";
      const g2 = el("div", "layer"); bg.appendChild(g2);
      const s = svg("svg", { viewBox: "0 0 400 400", width: o.H * 1.05, height: o.H * 1.05, style: `position:absolute;right:${-o.H * 0.18}px;top:${-o.H * 0.02}px;opacity:.28` }, g2);
      svg("circle", { cx: 200, cy: 200, r: 180, fill: "none", stroke: "#5fa8ff", "stroke-width": 1.5 }, s);
      const meridians = [0, 1, 2, 3, 4, 5].map(k => svg("ellipse", { cx: 200, cy: 200, rx: 180, ry: 180, fill: "none", stroke: "#5fa8ff", "stroke-width": 1 }, s));
      [-120, -60, 0, 60, 120].forEach(y => svg("ellipse", { cx: 200, cy: 200 + y, rx: Math.sqrt(180 * 180 - y * y), ry: 10, fill: "none", stroke: "#5fa8ff", "stroke-width": 1 }, s));
      const streak = el("div", "layer", null, "background:linear-gradient(100deg,transparent 40%,rgba(255,255,255,.07) 50%,transparent 60%)");
      bg.appendChild(streak);
      return t => {
        meridians.forEach((m, k) => m.setAttribute("rx", Math.abs(Math.cos(t * 0.35 + k * Math.PI / 6)) * 180));
        streak.style.transform = `translateX(${((t * 260) % (o.W * 2.4)) - o.W * 1.2}px)`;
      };
    },
    reel(bg, o) {
      const layer = el("div", "layer"); bg.appendChild(layer);
      const blobs = [0, 1, 2].map(k => { const b = el("div", null, null, `position:absolute;width:${o.W * 1.2}px;height:${o.W * 1.2}px;border-radius:50%;filter:blur(60px);opacity:.55`); layer.appendChild(b); return b; });
      const cv = el("canvas"); cv.width = o.W; cv.height = o.H; bg.appendChild(cv);
      const x = cv.getContext("2d"), r = prng(o.seed + 1), em = ["sparkle", "flame", "bolt", "burst", "rocket", "star"];
      const floaters = Array.from({ length: 14 }, () => [r(), r(), r(), em[Math.floor(r() * em.length)]]);
      const times = timeline(o.story), hues = o.F.hues;
      return t => {
        let i = 0; times.forEach((tm, k) => { if (t >= tm.start) i = k; });
        layer.style.background = hues[i % hues.length];
        blobs.forEach((b, k) => {
          b.style.background = hues[(i + k + 1) % hues.length];
          b.style.left = (Math.sin(t * 0.6 + k * 2) * 0.4 + 0.1 * k - 0.4) * o.W + "px";
          b.style.top = (Math.cos(t * 0.5 + k * 1.7) * 0.35 + 0.3 * k - 0.3) * o.H + "px";
        });
        x.clearRect(0, 0, o.W, o.H);
        const sc = o.base * 2.2 / 24;
        floaters.forEach(([a, b2, c, e]) => {
          x.save(); x.globalAlpha = 0.22; x.fillStyle = "#fff";
          x.translate(a * o.W, ((b2 - t * 0.04 * (0.5 + c)) % 1 + 1) % 1 * o.H); x.rotate(Math.sin(t + c * 9) * 0.3); x.scale(sc, sc);
          x.fill(iconPath(e), "evenodd"); x.restore();
        });
        x.globalAlpha = 1;
      };
    }
  };

  // ------------------------------------------------------------ overlays (letterbox, LIVE bug, ticker)
  const OVERLAYS = {
    trailer(ov, o) {
      const h = o.H * 0.095;
      ov.appendChild(el("div", null, null, `position:absolute;left:0;right:0;top:0;height:${h}px;background:#000`));
      ov.appendChild(el("div", null, null, `position:absolute;left:0;right:0;bottom:0;height:${h}px;background:#000`));
      return () => {};
    },
    news(ov, o) {
      const live = el("div", null, null, "position:absolute;left:3%;top:4%;display:flex;gap:.5em;align-items:center;font-family:'Bebas Neue',sans-serif;font-size:1.6em;letter-spacing:.06em");
      const dot = el("span", null, null, "display:inline-block;width:.45em;height:.45em;border-radius:50%;background:#fff");
      const tag = el("span", null, null, "background:#e8112d;padding:.05em .45em;display:flex;gap:.35em;align-items:center");
      tag.appendChild(dot); tag.appendChild(el("span", null, "LIVE"));
      live.appendChild(tag);
      live.appendChild(el("span", null, (o.story.name || "").toUpperCase() + " NEWS NETWORK", "background:rgba(0,0,0,.5);padding:.05em .45em"));
      ov.appendChild(live);
      const tick = el("div", null, null, "position:absolute;left:0;right:0;bottom:0;height:8.5%;background:#fff;color:#06122e;display:flex;align-items:center;overflow:hidden;font-weight:700;font-size:1.15em");
      const lab = el("div", null, "LATEST", "flex:none;height:100%;display:flex;align-items:center;padding:0 1em;background:#e8112d;color:#fff;font-family:'Bebas Neue',sans-serif;font-size:1.35em;letter-spacing:.08em;z-index:2");
      const run = el("div", null, null, "white-space:nowrap;padding-left:1em");
      const items = (o.story.ticker && o.story.ticker.length ? o.story.ticker : [o.story.name]).map(s => s.toUpperCase());
      run.textContent = (items.join("    /    ") + "    /    ").repeat(4);
      tick.appendChild(lab); tick.appendChild(run); ov.appendChild(tick);
      return t => { run.style.transform = `translateX(${-(t * 120) % (run.scrollWidth / 4 || 2000)}px)`; dot.style.opacity = Math.floor(t * 1.5) % 2 ? 0.25 : 1; };
    },
    reel(ov, o) {
      const bar = el("div", null, null, "position:absolute;left:6%;right:6%;top:3%;height:6px;border-radius:3px;background:rgba(255,255,255,.35)");
      const fill = el("div", null, null, "height:100%;border-radius:3px;background:#fff;width:0");
      bar.appendChild(fill); ov.appendChild(bar);
      return t => { fill.style.width = (100 * t / o.total) + "%"; };
    }
  };

  // ------------------------------------------------------------ shared builders
  function terminal(c, lines, at, title) {
    const t = el("div", "term"), bar = el("div", "bar");
    ["#ff5f57", "#febc2e", "#28c840"].forEach(col => { const i = el("i"); i.style.background = col; bar.appendChild(i); });
    bar.appendChild(el("span", null, title || "terminal"));
    t.appendChild(bar);
    const body = el("div", "body");
    lines.forEach((line, i) => {
      const row = el("div"), tx = el("span");
      row.appendChild(el("span", "p", "$"));
      row.appendChild(c.A(tx, "type", at, { text: line, cps: 26 }));
      c.typeSfx(at, line, 26);
      c.A(row, "show", at - 0.05);
      if (i === lines.length - 1) row.appendChild(c.A(el("span", "cursor"), "blink", 0, { rate: 2 }));
      body.appendChild(row);
      at += line.length / 26 + 0.45;
    });
    t.appendChild(body);
    t.__end = at;
    return t;
  }
  function codePanel(c, s, hlAt) {
    const code = el("div", "code"), hd = el("div", "hd");
    hd.appendChild(el("span", null, s.path));
    hd.appendChild(el("span", "ev", "L" + s.start + "–" + s.end));
    code.appendChild(hd);
    const pre = el("pre"), lines = s.code.split("\n");
    lines.forEach((ln, i) => {
      const d = el("div", "ln"); d.setAttribute("data-n", s.start + i);
      if ((s.highlight || []).indexOf(i) >= 0) {
        const h = el("span", "hl"); d.appendChild(h); c.A(h, "fade", hlAt, { dur: 0.3, sfx: "pop", gain: 0.3 });
      }
      const tx = el("span"); tx.style.position = "relative"; tx.innerHTML = highlight(ln); d.appendChild(tx);
      pre.appendChild(c.A(d, "rise", 0.35 + i * 0.05, { dist: 10, dur: 0.4 }));
    });
    code.appendChild(pre);
    return code;
  }
  function place(node, css) { node.style.cssText += ";position:absolute;" + css; return node; }

  // ------------------------------------------------------------ scenes
  const SCENES = {
    fallback(c) { c.box.appendChild(place(el("div", "center", c.s.narration), "font-size:2em;padding:10%")); },

    // ===================== TRAILER
    coldopen(c) {
      const wrap = el("div", "center"); c.box.appendChild(wrap);
      let from = 0;
      const n = c.s.lines.length;
      c.s.lines.forEach((line, i) => {
        const at = i === 0 ? 0.3 : c.say(line, from, (c.tm.duration / n) * i).t - 0.1;
        from = c.say(line, from).i + 1;
        const next = i + 1 < n ? c.say(c.s.lines[i + 1], from, (c.tm.duration / n) * (i + 1)).t - 0.15 : c.tm.duration + 1;
        const l = el("div", "disp", line.replace(/…/g, "").toUpperCase(),
          `position:absolute;font-size:${fit(line, 4.2, 2.4, 70)}em;letter-spacing:.06em;line-height:1.05;padding:0 9%;` +
          "background:linear-gradient(100deg,#bfa876 0%,#fff6dc 45%,#bfa876 60%);background-size:300% 100%;-webkit-background-clip:text;color:transparent");
        wrap.appendChild(l);
        c.A(l, "zoomin", at, { from: 1.14, dur: 1.6, blur: 7 });
        c.A(l, "shine", at, { speed: 40 });
        c.A(l, "track", at, { from: 0.02, to: 0.16, dur: Math.max(2, next - at) });
        c.A(l, "out", next - 0.1, { dur: 0.35 });
        c.cue(at, i === n - 1 ? "hit" : "braam", i === n - 1 ? 0.55 : 0.38);
      });
    },
    glitch(c) {
      const wrap = el("div", "center", null, "gap:.3em;padding:0 8%"); c.box.appendChild(wrap);
      c.box.appendChild(place(el("div", null, null, "background:repeating-linear-gradient(0deg,rgba(255,255,255,.04) 0 2px,transparent 2px 5px)"), "inset:0"));
      if (c.s.backdrop) {
        const bd = place(el("div", "mono", null, "white-space:pre;color:rgba(255,60,90,.13);font-size:1.5em;line-height:1.45;text-align:left;filter:blur(.6px)"), "left:6%;top:0");
        bd.textContent = (c.s.backdrop + "\n\n").repeat(6);
        c.box.insertBefore(bd, c.box.firstChild);
        c.A(bd, "scroll", 0, { speed: 38 });
      }
      for (let k = 0; k < 5; k++) {  // horizontal tears that jump on the beat
        const tear = place(el("div", null, null, "height:" + (6 + k * 5) + "px;background:rgba(255,42,85,.35);mix-blend-mode:screen"), "left:0;right:0;top:" + (12 + k * 17) + "%");
        c.box.appendChild(tear);
        c.A(tear, "tear", 0, { beat: c.beat || 0.6, k });
      }
      const lab = el("div", "mono", null, "color:#ff2a55;font-size:1.1em;letter-spacing:.3em;margin-bottom:1em;font-weight:700;display:flex;gap:.6em;align-items:center");
      lab.appendChild(icon("warning", "#ff2a55", 1.1)); lab.appendChild(el("span", null, c.s.label));
      wrap.appendChild(c.A(lab, "blink", 0, { rate: 3 }));
      let from = 0;
      c.s.lines.forEach((line, i) => {
        const at = i === 0 ? 0.4 : c.say(line, from, 0.4 + i * 1.2).t;
        from = c.say(line, from).i + 1;
        const l = el("div", null, line, `font-size:${fit(line, 3.0, 1.7, 80)}em;font-weight:800;line-height:1.1;letter-spacing:-.02em;color:#fff`);
        wrap.appendChild(l);
        c.A(l, "rise", at, { dist: 20, dur: 0.3 });
        c.A(l, "rgb", 0, { seed: i * 13 + 1, amp: 9, rate: 0.35 });
        c.cue(at, "glitch", 0.45, i % 2 ? 0.4 : -0.4);
      });
    },
    reveal(c) {
      const wrap = el("div", "center"); c.box.appendChild(wrap);
      const ring = place(el("div", null, null, "border:3px solid rgba(255,210,120,.9);border-radius:50%;box-shadow:0 0 40px rgba(255,200,90,.6)"), `left:50%;top:50%;width:${c.H * 0.5}px;height:${c.H * 0.5}px;margin:${-c.H * 0.25}px 0 0 ${-c.H * 0.25}px`);
      c.box.appendChild(ring);
      c.A(ring, "zoomin", 0.15, { from: 0.1, dur: 1.4 }); c.A(ring, "out", 0.8, { dur: 0.8 });
      const flare = place(el("div", null, null, "background:linear-gradient(90deg,transparent,rgba(255,230,170,.9),transparent);height:3px;filter:blur(1px)"), `left:-20%;right:-20%;top:50%`);
      c.box.appendChild(flare); c.A(flare, "zoomin", 0.15, { from: 0.2, dur: 0.9 }); c.A(flare, "out", 1.1, { dur: 0.9 });
      const title = el("div", "disp", null, `font-size:${fit(c.s.title, 9.5, 4, 48)}em;letter-spacing:.04em;line-height:1;display:flex;gap:.02em;` +
        "text-shadow:0 0 30px rgba(255,190,80,.45)");
      [...c.s.title.toUpperCase()].forEach((ch, k) => {
        const sp = el("span", null, ch, "display:inline-block;background:linear-gradient(180deg,#fff6dc,#f5c451 60%,#b8862b);-webkit-background-clip:text;color:transparent");
        title.appendChild(c.A(sp, "slam", 0.12 + k * 0.07, { from: 2.2, dur: 0.3 }));
      });
      wrap.appendChild(title);
      c.A(title, "shake", 0.12 + c.s.title.length * 0.07, { amp: 14, dur: 0.45 });
      if (c.s.subtitle) wrap.appendChild(c.A(el("div", null, c.s.subtitle.toUpperCase(), "font-size:1.35em;letter-spacing:.32em;color:#e9dcc0;margin-top:1.2em;max-width:80%;line-height:1.5"), "rise", 1.3, { dist: 16, dur: 0.9 }));
      c.burst(0.2 + c.s.title.length * 0.07, 0.5, 0.5, { kind: "sparks", n: 70, speed: 1300, spread: Math.PI * 2, angle: 0, gravity: 120, life: 1.8, colors: ["#fff6dc", "#f5c451", "#ff9a3c"], size: 8 });
      c.cue(0.2 + c.s.title.length * 0.07, "sparkle", 0.4);
    },
    montage(c) {
      const n = c.s.cards.length, cols = [["#050505", "#f4efe2", "#f5c451"], ["#f5c451", "#050505", "#7a4b00"], ["#f4efe2", "#050505", "#ff5a36"], ["#ff5a36", "#050505", "#fff"]];
      let from = 0;
      const starts = c.s.cards.map((k, i) => { const r = c.say(k.title, from, 0.2 + i * (c.tm.duration / n)); from = r.i + 1; return i === 0 ? 0 : r.t - 0.12; });
      c.s.cards.forEach((k, i) => {
        const [b, f, acc] = cols[i % cols.length], a = starts[i], z = i + 1 < n ? starts[i + 1] : c.tm.duration + 1;
        const slide = place(el("div", "center", null, `background:${b};color:${f};padding:0 10%`), "inset:0");
        slide.appendChild(el("div", "mono", String(i + 1).padStart(2, "0") + " / " + String(n).padStart(2, "0"), `color:${acc};letter-spacing:.3em;font-size:1em;margin-bottom:1.2em`));
        slide.appendChild(el("div", "disp", k.title.toUpperCase(), `font-size:${fit(k.title, 7.5, 3, 60)}em;line-height:.95;letter-spacing:.02em`));
        if (k.body) slide.appendChild(el("div", null, k.body, `font-size:1.25em;margin-top:1.2em;max-width:34em;line-height:1.4;opacity:.8`));
        c.box.appendChild(slide);
        c.A(slide, "show", a, { until: z });
        c.A(slide, "zoomin", a, { from: 1.18, dur: 0.7, hard: true });
        if (i) c.cue(a, "hit", 0.4);
      });
    },
    bignum(c) {
      const rays = place(el("div", null, null, "background:repeating-conic-gradient(from 0deg,rgba(245,196,81,.10) 0deg 6deg,transparent 6deg 18deg);border-radius:50%"), `left:50%;top:50%;width:${c.W * 1.6}px;height:${c.W * 1.6}px;margin:${-c.W * 0.8}px 0 0 ${-c.W * 0.8}px`);
      c.box.appendChild(rays); c.A(rays, "spin", 0, { speed: 8 }); c.A(rays, "fade", 0.2, { dur: 1 });
      const n = c.s.stats.length;
      let from = 0;
      const starts = c.s.stats.map((st, i) => { if (i === 0) return 0.25; const lab = st.label.replace(/^[^:]{0,30}:\s*/, ""); const r = c.say(lab, from, c.tm.duration / 2); from = r.i + 1; return r.t - 0.2; });
      c.s.stats.forEach((st, i) => {
        const a = starts[i], z = i + 1 < n ? starts[i + 1] : c.tm.duration + 1;
        const wrap = el("div", "center", null, "gap:.6em;padding:0 10%"); c.box.appendChild(wrap);
        c.A(wrap, "show", a - 0.01, { until: z });
        const v = el("div", "disp", st.value, `font-size:${fit(st.value, 13, 7, 40)}em;line-height:1;color:#f5c451;text-shadow:0 0 50px rgba(245,196,81,.45)`);
        const m = /^(\D*)([\d,]*\.?\d+)(.*)$/.exec(st.value);
        if (m) c.A(v, "count", a, { pre: m[1], num: parseFloat(m[2].replace(/,/g, "")), post: m[3], dec: (m[2].split(".")[1] || "").length, dur: 1.0 });
        wrap.appendChild(c.A(v, "zoomin", a, { from: 0.6, dur: 1.0 }));
        wrap.appendChild(c.A(el("div", null, st.label.replace(/^[^:]{0,30}:\s*/, "").toUpperCase(), "font-size:1.35em;color:#e9dcc0;max-width:30em;line-height:1.4;letter-spacing:.14em"), "rise", a + 0.6, { dist: 20 }));
        c.A(v, "shake", a + 1.0, { amp: 14, dur: 0.35 });
        c.cue(a + 1.0, "hit", 0.55);
        for (let k = 0; k < 10; k++) c.cue(a + k * 0.1, "tick", 0.22);
        c.burst(a + 1.0, 0.5, 0.42, { kind: "sparks", n: 60, speed: 1300, spread: Math.PI * 2, angle: 0, gravity: 250, life: 1.5, colors: ["#f5c451", "#fff", "#ff9a3c"], size: 7 });
      });
    },
    cta(c) {
      const wrap = el("div", "center", null, "gap:1.8em"); c.box.appendChild(wrap);
      const marquee = el("div", "disp", null, "position:relative;padding:.35em 1.4em;border:4px solid #f5c451;border-radius:10px;font-size:3.4em;letter-spacing:.12em;color:#f5c451;text-shadow:0 0 18px rgba(245,196,81,.7)");
      marquee.appendChild(el("span", null, c.s.kicker));
      for (let k = 0; k < 18; k++) {
        const bulb = el("i", null, null, `position:absolute;width:10px;height:10px;border-radius:50%;background:#fff1c2;box-shadow:0 0 10px #ffd36b;` +
          (k < 9 ? `top:-7px;left:${5 + k * 11}%` : `bottom:-7px;left:${5 + (k - 9) * 11}%`));
        marquee.appendChild(c.A(bulb, "blink", (k % 2) * 0.25, { rate: 2 }));
      }
      wrap.appendChild(c.A(marquee, "zoomin", 0.1, { from: 0.6, dur: 0.6 }));
      const t = terminal(c, c.s.lines, Math.max(1.0, c.say(c.s.lines[0], 0, 1.0).t - 0.1));  // types as it's said
      t.style.minWidth = "30em";
      wrap.appendChild(c.A(t, "rise", 0.6));
      wrap.appendChild(c.A(el("div", null, "IN YOUR TERMINAL · TODAY", "letter-spacing:.4em;color:#cfc6b0;font-size:1em"), "fade", 1.6));
    },
    credits(c) {
      const wrap = el("div", "center", null, "gap:.55em;font-family:'Bebas Neue',sans-serif;color:#e9e2cf;letter-spacing:.08em"); c.box.appendChild(wrap);
      const row = (txt, css, at) => wrap.appendChild(c.A(el("div", null, txt, css), "fade", at, { dur: 0.8 }));
      row(`A ${(c.s.lang || "CODE").toUpperCase()} PRODUCTION`, "font-size:1.4em;letter-spacing:.5em;color:#a99f86", 0.2);
      row(c.s.title.toUpperCase(), `font-family:Anton,sans-serif;font-size:${fit(c.s.title, 7, 3.5, 40)}em;letter-spacing:.06em;color:#f5c451;line-height:1`, 0.5);
      if (c.s.starring.length) row("STARRING  " + c.s.starring.map(x => x.toUpperCase()).join("  ·  "), "font-size:1.5em", 1.0);
      row(`${c.s.files.toLocaleString("en-US")} FILES  ·  ZERO CGI  ·  100% REAL CODE`, "font-size:1.2em;color:#a99f86", 1.3);
      const rating = el("div", null, null, "display:flex;gap:.8em;align-items:center;border:2px solid #e9e2cf;padding:.3em .6em;margin-top:.6em;font-size:1em;text-align:left");
      rating.appendChild(el("div", null, "T", "font-family:Anton,sans-serif;font-size:2.6em;line-height:1;border:2px solid #e9e2cf;padding:0 .2em"));
      rating.appendChild(el("div", null, "RATED T FOR TERMINAL — CONTAINS STRONG OPINIONS, FAST BUILDS AND MILD PERFORMANCE BRAGGING", "max-width:22em;line-height:1.2;font-size:1.05em"));
      wrap.appendChild(c.A(rating, "fade", 1.7));
      if (c.s.url) { const u = row("", "font-family:'JetBrains Mono',monospace;font-size:1em;color:#f5c451;margin-top:.6em;letter-spacing:.05em;display:flex;gap:.6em;align-items:center", 2.1); u.appendChild(icon("star", "#f5c451", 1)); u.appendChild(el("span", null, c.s.url.toUpperCase())); }
      c.mascot("idle", c.W * 0.83, c.H * 0.58, 6.5);
      c.cue(2.1, "sparkle", 0.3);
    },

    // ===================== METRO
    ticket(c) {
      const T = el("div", null, null, `position:absolute;left:50%;top:50%;width:46em;height:20em;margin:-10em 0 0 -23em;background:#f3ead7;color:#13213a;border-radius:16px;display:flex;box-shadow:0 30px 80px rgba(0,0,0,.5);overflow:hidden`);
      const stub = el("div", null, null, "width:11em;background:#ffb000;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.5em;border-right:3px dashed #13213a;font-weight:700;letter-spacing:.12em");
      stub.appendChild(el("div", null, "ADMIT ONE", "font-size:.9em"));
      stub.appendChild(el("div", "mono", (c.s.line || "").toUpperCase(), "font-size:1.6em;text-align:center;padding:0 .4em;word-break:break-all"));
      stub.appendChild(el("div", null, "LINE", "font-size:.9em"));
      T.appendChild(stub);
      const main = el("div", null, null, "flex:1;padding:1.6em 2em;display:flex;flex-direction:column;gap:.7em;position:relative");
      main.appendChild(el("div", null, "THE " + (c.s.line || "").toUpperCase() + " EXPRESS · CODE METRO", "font-size:.95em;letter-spacing:.2em;color:#5b6b85;font-weight:700"));
      const leg = (lab, val) => { const r = el("div", null, null, "display:flex;align-items:baseline;gap:1em"); r.appendChild(el("span", null, lab, "font-size:.9em;letter-spacing:.2em;color:#5b6b85;width:4.5em")); r.appendChild(el("span", "mono", val, `font-size:${fit(val, 2.2, 1.2, 40)}em;font-weight:800`)); return r; };
      if (c.s.from) { main.appendChild(leg("FROM", c.s.from)); main.appendChild(leg("TO", c.s.to)); }
      main.appendChild(el("div", null, `${c.s.stops || 1} STOPS · DEPARTS ${c.s.depart || ""}`, "font-size:.95em;color:#5b6b85;letter-spacing:.08em;margin-top:auto"));
      const bars = el("div", null, null, "position:absolute;right:1.6em;bottom:1.4em;display:flex;gap:2px;height:2.6em"), r = prng(hash(c.s.line || "x"));
      for (let k = 0; k < 28; k++) bars.appendChild(el("i", null, null, `display:block;width:${1 + Math.floor(r() * 4)}px;background:#13213a`));
      main.appendChild(bars);
      const stamp = el("div", null, "VALID", "position:absolute;right:2.2em;top:1.2em;border:4px solid #e8113a;color:#e8113a;font-weight:900;font-size:1.8em;padding:.05em .4em;border-radius:6px;letter-spacing:.1em");
      stamp.__base = "rotate(-14deg)";
      main.appendChild(c.A(stamp, "slam", 1.6, { from: 1.4, dur: 0.25, sfx: "shutter", gain: 0.6 }));
      T.appendChild(main);
      c.box.appendChild(c.A(T, "rise", 0.15, { dist: 200, dur: 0.9 }));
      c.A(T, "wobble", 0, { amp: 0.8, speed: 1.2 });
      c.mascot("wave", c.W * 0.025, c.H * 0.66, 6, lt => (lt < 2.5 ? "wave" : "idle"));
    },
    city(c) {
      c.box.appendChild(place(el("div", null, c.s.heading.toUpperCase() + " · DISTRICT MAP", "font-size:1.6em;font-weight:800;letter-spacing:.08em"), "left:7%;top:7%"));
      const items = c.s.items.filter(x => x.files).slice(0, 7), sum = items.reduce((a, b) => a + b.files, 0) || 1;
      const X0 = c.W * 0.07, Y0 = c.H * 0.18, AW = c.W * 0.86, AH = c.H * 0.66, cols = c.F.lines;
      // slice-and-dice treemap: alternate the cut direction each step
      let x = X0, y = Y0, w = AW, h = AH, left = sum;
      items.forEach((it, k) => {
        const frac = it.files / left, horiz = k % 2 === 0;
        const tw = horiz ? (k === items.length - 1 ? w : w * frac) : w, th = horiz ? h : (k === items.length - 1 ? h : h * frac);
        const tile = place(el("div", null, null, `background:${cols[k % cols.length]};border-radius:10px;padding:.7em .9em;color:#0a1726;overflow:hidden;display:flex;flex-direction:column;justify-content:space-between;border:3px solid #0a1726`),
          `left:${x}px;top:${y}px;width:${tw}px;height:${th}px`);
        tile.appendChild(el("div", "mono", it.name, `font-weight:800;font-size:${tw > 200 && th > 90 ? 1.4 : 0.9}em`));
        tile.appendChild(el("div", null, it.files + " files" + (it.hint ? " · " + it.hint : ""), `font-size:${tw > 200 && th > 90 ? 1.05 : 0.85}em;font-weight:600;opacity:.85`));
        c.box.appendChild(c.A(tile, "pop", 0.4 + k * 0.22, { dur: 0.55, sfx: "pop", gain: 0.3 }));
        if (k === 0) {  // the biggest district lights up when the narrator names it
          const at = c.say("biggest", 0, 3).t;
          const badge = el("div", null, null, "position:absolute;right:.8em;top:.7em;background:#0a1726;color:#ffb000;font-weight:800;font-size:.8em;padding:.25em .6em;border-radius:6px;display:flex;gap:.4em;align-items:center");
          badge.appendChild(icon("star", "#ffb000", 1)); badge.appendChild(el("span", null, "BIGGEST DISTRICT"));
          tile.appendChild(c.A(badge, "pop", at, { sfx: "chime", gain: 0.3 }));
          c.A(tile, "on", at, { cls: "hot" });
        }
        if (horiz) { x += tw; w -= tw; } else { y += th; h -= th; }
        left -= it.files;
      });
    },
    network(c) {
      c.box.appendChild(place(el("div", null, "NETWORK MAP", "font-size:1.6em;font-weight:800;letter-spacing:.08em"), "left:7%;top:7%"));
      c.box.appendChild(place(el("div", null, "every line is a real import", "font-size:1em;color:#8fb3e0"), "left:7%;top:13%"));
      const AW = c.W * 0.86, AH = c.H * 0.68, ox = c.W * 0.07, oy = c.H * 0.2, hub = c.s.hub;
      const ring = c.s.nodes.filter(n => n !== hub), pos = {};
      pos[hub] = { x: ox + AW / 2, y: oy + AH / 2 };
      ring.forEach((n, i) => { const a = -Math.PI / 2 + (i + 0.5) * 2 * Math.PI / ring.length; pos[n] = { x: ox + AW / 2 + Math.cos(a) * AW * 0.38, y: oy + AH / 2 + Math.sin(a) * AH * 0.4 }; });
      const S = svg("svg", { viewBox: `0 0 ${c.W} ${c.H}`, width: c.W, height: c.H, style: "position:absolute;left:0;top:0;overflow:visible" }, c.box);
      const paths = [];
      c.s.edges.forEach((e, i) => {
        const p = pos[e.from], q = pos[e.to]; if (!p || !q) return;
        // metro style: horizontal then 45° then horizontal
        const dx = q.x - p.x, dy = q.y - p.y, mid = p.x + dx / 2 - Math.sign(dx || 1) * Math.abs(dy) / 2;
        const d = Math.abs(dx) > Math.abs(dy) ? `M${p.x},${p.y} L${mid},${p.y} L${mid + Math.sign(dx || 1) * Math.abs(dy)},${q.y} L${q.x},${q.y}` : `M${p.x},${p.y} L${p.x},${p.y + dy / 2} L${q.x},${q.y}`;
        const col = c.F.lines[i % c.F.lines.length];
        const path = svg("path", { d, fill: "none", stroke: col, "stroke-width": 7 + 5 * (e.weight / c.s.edges[0].weight), "stroke-linecap": "round", "stroke-linejoin": "round" }, S);
        const len = 3000; path.style.strokeDasharray = len;
        c.A(path, "draw", 0.9 + i * 0.32, { len, dur: 0.7, sfx: i < 6 ? "whoosh" : null, gain: 0.15 });
        paths.push({ path, col, at: 0.9 + i * 0.32 });
      });
      c.s.nodes.forEach((n, i) => {
        const p = pos[n], isHub = n === hub;
        const st = place(el("div"), `left:${p.x}px;top:${p.y}px;width:0;height:0`);
        const dot = el("div", null, null, `position:absolute;left:${isHub ? -20 : -12}px;top:${isHub ? -20 : -12}px;width:${isHub ? 40 : 24}px;height:${isHub ? 40 : 24}px;border-radius:50%;background:#fff;border:${isHub ? 7 : 5}px solid #0a1726;box-shadow:${isHub ? "0 0 0 5px #fff, 0 0 30px rgba(255,255,255,.6)" : "none"}`);
        st.appendChild(dot);
        const lab = el("div", "mono", n, `position:absolute;left:${isHub ? 30 : 20}px;top:-.75em;white-space:nowrap;background:#0a1726;color:#fff;padding:.15em .5em;border-radius:6px;font-weight:700;font-size:${isHub ? 1.15 : 0.95}em;border:2px solid ${isHub ? "#ffb000" : "rgba(255,255,255,.25)"}`);
        st.appendChild(lab);
        c.box.appendChild(c.A(st, "pop", 0.3 + i * 0.12, { dur: 0.45 }));
      });
      // a train running the busiest line
      if (paths.length) {
        const p = pos[c.s.edges[0].from], q = pos[c.s.edges[0].to];
        const train = place(el("div", null, null, "width:34px;height:16px;margin:-8px 0 0 -17px;border-radius:8px;background:#fff;box-shadow:0 0 18px #fff"), "left:0;top:0");
        c.box.appendChild(train);
        const pts = []; for (let k = 0; k < 6; k++) { pts.push({ x: p.x, y: p.y, t: 2.4 + k * 2 }); pts.push({ x: q.x, y: q.y, t: 3.4 + k * 2 }); }
        c.A(train, "along", 0, { points: pts }); c.A(train, "fade", 2.3);
      }
      c.mascot("point", c.W * 0.88, c.H * 0.74, 5);
    },
    stop(c) {
      const stops = c.s.stops, n = stops.length, idx = c.s.index;
      // the line across the top, the train arriving at this station
      const X0 = c.W * 0.09, X1 = c.W * 0.91, Y = c.H * 0.1, sx = k => X0 + (n > 1 ? (X1 - X0) * k / (n - 1) : (X1 - X0) / 2);
      c.box.appendChild(place(el("div", null, null, `height:10px;border-radius:5px;background:${c.F.lines[0]}`), `left:${X0}px;width:${X1 - X0}px;top:${Y - 5}px`));
      stops.forEach((st, k) => {
        const on = k === idx, done = k < idx;
        const d = place(el("div", null, null, `width:${on ? 34 : 24}px;height:${on ? 34 : 24}px;margin:${on ? -17 : -12}px 0 0 ${on ? -17 : -12}px;border-radius:50%;background:${done ? "#ffb000" : "#fff"};border:5px solid #0a1726;box-shadow:${on ? "0 0 0 4px #fff,0 0 24px #fff" : "none"}`), `left:${sx(k)}px;top:${Y}px`);
        c.box.appendChild(d);
        c.box.appendChild(place(el("div", "mono", st + "()", `transform:translateX(-50%);white-space:nowrap;font-size:${on ? 1.05 : 0.8}em;font-weight:${on ? 800 : 500};color:${on ? "#ffb000" : "#8fb3e0"}`), `left:${sx(k)}px;top:${Y + 22}px`));
      });
      const train = place(el("div", null, null, "width:46px;height:24px;margin:-12px 0 0 -23px;border-radius:12px;background:#ffb000;display:flex;align-items:center;justify-content:center;box-shadow:0 0 20px rgba(255,176,0,.8)"), "left:0;top:0");
      train.appendChild(icon("play", "#0a1726", 0.8));
      c.box.appendChild(train);
      c.A(train, "along", 0, { points: [{ x: sx(Math.max(0, idx - 1)), y: Y, t: 0 }, { x: sx(idx), y: Y, t: 0.9 }] });
      c.cue(0.9, "chime", 0.45);
      // station sign + code
      const sign = place(el("div", null, null, "display:flex;align-items:center;gap:.8em"), `left:7%;top:${c.H * 0.19}px`);
      sign.appendChild(el("div", null, idx === 0 ? "FIRST STOP" : idx === n - 1 ? "FINAL STOP" : "NOW ARRIVING", "background:#ffb000;color:#0a1726;font-weight:800;padding:.2em .6em;border-radius:6px;letter-spacing:.1em;font-size:.95em"));
      sign.appendChild(el("div", "mono", c.s.symbol + "()", "font-size:1.9em;font-weight:800"));
      sign.appendChild(el("div", "mono", "· " + c.s.path, "font-size:1.05em;color:#8fb3e0"));
      c.box.appendChild(c.A(sign, "slideX", 0.7, { dist: -120 }));
      const hlAt = c.say("watch", 0, c.tm.talk * 0.55).t - 0.1;
      const code = place(codePanel(c, c.s, hlAt), `left:7%;right:7%;top:${c.H * 0.28}px;font-size:.86em`);
      c.box.appendChild(c.A(code, "rise", 0.8, { dist: 30 }));
    },
    depot(c) {
      const wrap = el("div", "center", null, "gap:1.4em"); c.box.appendChild(wrap);
      const dh = el("div", null, null, "font-size:2em;font-weight:800;letter-spacing:.06em;display:flex;gap:.5em;align-items:center");
      dh.appendChild(icon("ticket", "#ffb000", 1.1)); dh.appendChild(el("span", null, c.s.heading.toUpperCase()));
      wrap.appendChild(c.A(dh, "rise", 0.1));
      const t = terminal(c, c.s.lines, 0.9, "your machine"); t.style.minWidth = "32em";
      wrap.appendChild(c.A(t, "rise", 0.4));
    },
    terminus(c) {
      const wrap = el("div", "center", null, "gap:1.2em"); c.box.appendChild(wrap);
      const sign = el("div", null, null, "background:#0b2140;border:6px solid #fff;border-radius:18px;padding:.6em 2.2em;box-shadow:0 20px 60px rgba(0,0,0,.5)");
      sign.appendChild(el("div", null, "END OF THE LINE", "font-size:3.4em;font-weight:900;letter-spacing:.06em"));
      sign.appendChild(el("div", null, null, `height:10px;border-radius:5px;margin:.4em 0;background:linear-gradient(90deg,${c.F.lines.join(",")})`));
      sign.appendChild(el("div", "mono", c.s.title, "font-size:1.6em;color:#ffb000;font-weight:700"));
      wrap.appendChild(c.A(sign, "drop", 0.1, { dist: 500, dur: 1.0, sfx: "chime", gain: 0.4 }));
      if (c.s.url) wrap.appendChild(c.A(el("div", "mono", c.s.url, "font-size:1.2em;color:#8fb3e0"), "fade", 1.2));
      c.mascot("wave", c.W * 0.8, c.H * 0.55, 7);
      c.burst(1.1, 0.5, 0.35, { kind: "confetti", n: 60, colors: c.F.lines });
    },

    // ===================== QUEST
    titlescreen(c) {
      const wrap = el("div", "center", null, "gap:1.3em;font-family:'Press Start 2P',monospace"); c.box.appendChild(wrap);
      const shadow = "4px 4px 0 #ff3b6b,8px 8px 0 #29c5f6,12px 12px 0 #0b0930";
      const t = el("div", null, c.s.title.toUpperCase(), `font-size:${fit(c.s.title, 4.2, 2, 30)}em;color:#ffd23f;text-shadow:${shadow};line-height:1.2`);
      wrap.appendChild(c.A(t, "drop", 0.2, { dist: 400, sfx: "powerup", gain: 0.5 }));
      wrap.appendChild(c.A(el("div", null, c.s.subtitle, "font-size:1.05em;color:#fff7e0;letter-spacing:.1em;margin-top:.8em"), "fade", 1.2));
      const press = el("div", null, null, "font-size:1.1em;color:#3ddc84;margin-top:2em;display:flex;gap:.6em;align-items:center");
      press.appendChild(icon("play", "#3ddc84", 0.9)); press.appendChild(el("span", null, "PRESS START"));
      wrap.appendChild(c.A(press, "blink", 1.8, { rate: 2.5 }));
      c.cue(1.8, "coin", 0.45);
      c.box.appendChild(place(el("div", null, "1 PLAYER · 0 BUGS (HOPEFULLY)", "font-family:'Press Start 2P',monospace;font-size:.75em;color:#b9a8ff;text-align:center"), "left:0;right:0;top:7%"));
      c.mascot("cheer", c.W * 0.1, c.H * 0.5, 7, lt => (lt > 1.8 ? "cheer" : "idle"));
      c.burst(1.9, 0.5, 0.35, { kind: "pixels", n: 50, size: 10 });
    },
    objectives(c) {
      const panel = el("div", null, null, "position:absolute;left:12%;right:12%;top:12%;background:#0b0930;border:4px solid #fff7e0;box-shadow:0 0 0 4px #0b0930,0 0 0 8px #ffd23f;padding:1.2em 1.6em;font-family:'Press Start 2P',monospace");
      panel.appendChild(el("div", null, c.s.heading, "font-size:1em;color:#ffd23f;margin-bottom:1em"));
      const xpRow = el("div", null, null, "display:flex;align-items:center;gap:.8em;margin-bottom:1.2em;font-size:.7em");
      xpRow.appendChild(el("span", null, "XP"));
      const bar = el("div", null, null, "flex:1;height:1.3em;background:#2b2568;border:3px solid #fff7e0"), fill = el("div", null, null, "height:100%;width:0;background:linear-gradient(90deg,#3ddc84,#ffd23f)");
      bar.appendChild(fill); xpRow.appendChild(bar);
      const xpTxt = el("span", null, "0/" + c.s.xp); xpRow.appendChild(xpTxt);
      panel.appendChild(xpRow);
      const n = c.s.items.length, step = Math.min(1.2, (c.tm.duration - 2.4) / n);
      c.s.items.forEach((it, k) => {
        const at = 0.9 + k * step, row = el("div", null, null, "display:flex;align-items:center;gap:1em;margin:.7em 0;font-size:.72em");
        const box = el("span", null, "", "width:1.6em;height:1.6em;border:3px solid #fff7e0;display:inline-flex;align-items:center;justify-content:center;color:#3ddc84;flex:none");
        const check = icon("check", "#3ddc84", 1.2); box.appendChild(c.A(check, "pop", at + 0.45));
        row.appendChild(box);
        row.appendChild(el("span", "mono", it, "font-family:'JetBrains Mono',monospace;font-size:1.5em;color:#fff7e0"));
        const plus = el("span", null, "+100 XP", "margin-left:auto;color:#ffd23f"); row.appendChild(c.A(plus, "rise", at + 0.5, { dist: 14 }));
        panel.appendChild(c.A(row, "slideX", at, { dist: 60, dur: 0.4 }));
        c.cue(at + 0.5, "coin", 0.4);
      });
      c.A(fill, "grow", 1.4, { to: 100, dur: n * step });
      c.A(xpTxt, "count", 1.4, { pre: "", num: c.s.xp, post: "/" + c.s.xp, dur: n * step });
      c.box.appendChild(panel);
      const done = 1.4 + n * step;
      const toast = el("div", null, null, "position:absolute;left:50%;bottom:16%;width:30em;margin-left:-15em;background:#ffd23f;color:#0b0930;border:4px solid #0b0930;box-shadow:6px 6px 0 #0b0930;padding:.8em 1em;display:flex;gap:1em;align-items:center;font-family:'Press Start 2P',monospace");
      toast.appendChild(icon("trophy", "#0b0930", 2.2));
      const tx = el("div"); tx.appendChild(el("div", null, "ACHIEVEMENT UNLOCKED", "font-size:.65em;margin-bottom:.5em")); tx.appendChild(el("div", null, c.s.achievement, "font-size:.9em")); toast.appendChild(tx);
      c.box.appendChild(c.A(toast, "drop", done, { dist: 200, dur: 0.6, sfx: "levelup", gain: 0.45 }));
      c.burst(done + 0.3, 0.5, 0.75, { kind: "pixels", n: 60 });
    },
    worldmap(c) {
      c.box.appendChild(place(el("div", null, c.s.heading, "font-family:'Press Start 2P',monospace;font-size:1.1em;color:#ffd23f;text-shadow:3px 3px 0 #0b0930"), "left:6%;top:6%"));
      const zones = c.s.zones, n = zones.length, cols = Math.min(3, n), rows = Math.ceil(n / cols);
      const pts = [];
      const S = svg("svg", { viewBox: `0 0 ${c.W} ${c.H}`, width: c.W, height: c.H, style: "position:absolute;left:0;top:0" }, c.box);
      zones.forEach((z, k) => {
        const row = Math.floor(k / cols), col = row % 2 ? cols - 1 - (k % cols) : k % cols;  // snake path
        const x = c.W * (0.2 + 0.6 * (cols > 1 ? col / (cols - 1) : 0.5)), y = c.H * (0.3 + 0.48 * (rows > 1 ? row / (rows - 1) : 0.5));
        pts.push({ x, y });
        const isl = place(el("div", null, null, "width:17em;margin-left:-8.5em;margin-top:-4.6em;text-align:center"), `left:${x}px;top:${y}px`);
        const blob = el("div", null, null, "background:#3ddc84;border:4px solid #0b0930;border-radius:42% 58% 50% 50%/55% 45% 55% 45%;padding:.5em .4em .6em;box-shadow:0 8px 0 #1c7a45,0 12px 0 rgba(0,0,0,.3)");
        blob.appendChild(icon(z.icon, "#0b0930", 2.4, "margin:0 auto"));
        blob.appendChild(el("div", null, z.zone.toUpperCase(), "font-family:'Press Start 2P',monospace;font-size:.72em;color:#0b0930;margin-top:.3em;line-height:1.5"));
        blob.appendChild(el("div", "mono", z.name + (z.files ? " · " + z.files : ""), "font-size:.95em;color:#0b3a22;font-weight:700"));
        isl.appendChild(blob);
        c.box.appendChild(c.A(isl, "pop", 0.4 + k * 0.25, { sfx: "pop", gain: 0.3 }));
        c.A(isl, "bob", 0, { amp: 4, speed: 1.6, phase: k });
      });
      for (let k = 0; k + 1 < pts.length; k++) {
        const l = svg("line", { x1: pts[k].x, y1: pts[k].y, x2: pts[k + 1].x, y2: pts[k + 1].y, stroke: "#fff7e0", "stroke-width": 5, "stroke-dasharray": "2 16", "stroke-linecap": "round" }, S);
        c.A(l, "fade", 0.6 + k * 0.25);
      }
      // the hero walks the map, stopping at each zone
      const hero = c.mascot("idle", 0, 0, 4.5, lt => "idle");
      hero.style.marginLeft = "-2.25em"; hero.style.marginTop = "-7.8em";
      const walk = Math.max(0.8, (c.tm.duration - 2.2) / Math.max(1, n));
      c.A(hero, "along", 0, { points: pts.map((p, k) => ({ x: p.x, y: p.y, t: 1.2 + k * walk })) });
      pts.forEach((p, k) => c.cue(1.2 + k * walk, "coin", 0.25));
    },
    boss(c) {
      const head = place(el("div", null, null, "display:flex;align-items:center;gap:1em;font-family:'Press Start 2P',monospace"), "left:7%;right:7%;top:7%");
      const bb = el("div", null, null, "font-size:1em;color:#ff3b6b;display:flex;gap:.6em;align-items:center");
      bb.appendChild(icon("swords", "#ff3b6b", 1.2)); bb.appendChild(el("span", null, "BOSS BATTLE"));
      head.appendChild(c.A(bb, "blink", 0, { rate: 1.2 }));
      head.appendChild(el("div", "mono", c.s.symbol, "font-family:'JetBrains Mono',monospace;font-size:1.5em;font-weight:800;color:#fff7e0"));
      const hp = el("div", null, null, "margin-left:auto;display:flex;align-items:center;gap:.6em;font-size:.7em");
      hp.appendChild(el("span", null, "HP"));
      const bar = el("div", null, null, "width:16em;height:1.2em;border:3px solid #fff7e0;background:#2b2568"), fill = el("div", null, null, "height:100%;width:100%;background:linear-gradient(90deg,#ff3b6b,#ffd23f)");
      bar.appendChild(fill); hp.appendChild(bar); head.appendChild(hp);
      c.box.appendChild(c.A(head, "rise", 0.1));
      const code = place(codePanel(c, c.s, 1.2), `left:7%;right:7%;top:${c.H * 0.18}px;border:4px solid #fff7e0;border-radius:0;box-shadow:0 0 0 4px #0b0930,0 0 0 8px #ff3b6b`);
      c.box.appendChild(c.A(code, "zoomin", 0.25, { from: 0.85, dur: 0.5, sfx: "hit", gain: 0.4 }));
      c.A(fill, "drain", 1.0, { dur: c.tm.duration - 1.4 });  // HP drains as you read
      c.cue(c.tm.duration - 0.5, "levelup", 0.35);
    },
    scroll(c) {
      const sc = el("div", null, null, "position:absolute;left:50%;top:50%;width:40em;margin-left:-20em;transform-origin:50% 0;background:linear-gradient(90deg,#d9b77a,#f4e2b8 8%,#f7e9c6 50%,#f4e2b8 92%,#d9b77a);color:#3b2410;padding:1.6em 2.4em 2em;border-radius:6px;box-shadow:0 20px 50px rgba(0,0,0,.5)");
      sc.style.marginTop = "-12em";
      sc.appendChild(el("div", null, c.s.heading, "font-family:'Press Start 2P',monospace;font-size:1em;text-align:center;margin-bottom:1.2em;color:#7a1f10"));
      c.s.items.slice(0, 4).forEach((it, k) => {
        const r = el("div", null, null, "display:flex;gap:.8em;margin:.6em 0;font-size:1.15em;line-height:1.35;font-weight:600");
        r.appendChild(el("span", null, ["I", "II", "III", "IV"][k] + ".", "font-family:'Press Start 2P',monospace;font-size:.6em;color:#7a1f10;padding-top:.5em;width:2.4em;flex:none"));
        r.appendChild(el("span", null, it));
        sc.appendChild(c.A(r, "fade", 0.9 + k * 0.6));
      });
      const seal = el("div", null, null, "position:absolute;right:-1em;bottom:-1em;width:3.4em;height:3.4em;border-radius:50%;background:radial-gradient(circle at 35% 35%,#e04848,#8a1010);color:#ffd3a0;display:flex;align-items:center;justify-content:center;font-size:1.3em;box-shadow:0 4px 10px rgba(0,0,0,.4)");
      seal.appendChild(icon("star", "#ffd3a0", 1.4));
      sc.appendChild(c.A(seal, "slam", 1.2 + Math.min(4, c.s.items.length) * 0.6, { from: 1.5, dur: 0.3, sfx: "hit", gain: 0.3 }));
      c.box.appendChild(sc);
      c.A(sc, "unroll", 0.2, { dur: 0.9, sfx: "whoosh_down", gain: 0.3 });
    },
    complete(c) {
      const wrap = el("div", "center", null, "gap:1.4em;font-family:'Press Start 2P',monospace"); c.box.appendChild(wrap);
      wrap.appendChild(c.A(el("div", null, c.s.title, "font-size:3em;color:#ffd23f;text-shadow:4px 4px 0 #ff3b6b,8px 8px 0 #0b0930"), "zoomin", 0.1, { from: 2, dur: 0.6, sfx: "levelup", gain: 0.5 }));
      const stars = el("div", null, null, "display:flex;gap:.4em;font-size:4em;color:#ffd23f;font-family:'Space Grotesk',sans-serif");
      [0, 1, 2].forEach(k => { const s = icon("star", "#ffd23f", 1, "filter:drop-shadow(0 0 14px rgba(255,210,63,.8))"); stars.appendChild(c.A(s, "pop", 0.9 + k * 0.35, { sfx: "coin", gain: 0.4 })); c.A(s, "wobble", 0, { amp: 8, phase: k }); });
      wrap.appendChild(stars);
      wrap.appendChild(c.A(el("div", null, "NEXT MISSION: PICK AN ISSUE", "font-size:1em;color:#fff7e0"), "fade", 2.0));
      if (c.s.url) wrap.appendChild(c.A(el("div", "mono", c.s.url, "font-family:'JetBrains Mono',monospace;font-size:1em;color:#3ddc84"), "fade", 2.4));
      c.mascot("cheer", c.W * 0.82, c.H * 0.52, 7);
      c.burst(0.9, 0.5, 0.4, { kind: "pixels", n: 90, size: 12 });
      c.burst(2.0, 0.2, 0.5, { kind: "stars", n: 25, colors: ["#ffd23f"], size: 10 });
      c.burst(2.0, 0.8, 0.5, { kind: "stars", n: 25, colors: ["#ffd23f"], size: 10 });
    },

    // ===================== NEWS
    breaking(c) {
      const banner = place(el("div", "disp", c.s.kicker, "background:#e8112d;color:#fff;font-size:5.2em;letter-spacing:.05em;padding:.05em .5em;box-shadow:0 12px 40px rgba(0,0,0,.5)"), `left:6%;top:${c.H * 0.3}px`);
      banner.__base = "skewX(-8deg)";
      c.box.appendChild(c.A(banner, "slideX", 0.1, { dist: -900, dur: 0.45, sfx: "sting", gain: 0.5 }));
      c.A(banner, "shake", 0.55, { amp: 10, dur: 0.3 });
      const lower = place(el("div", null, null, "display:flex;align-items:stretch;box-shadow:0 12px 40px rgba(0,0,0,.5)"), `left:6%;top:${c.H * 0.3 + c.base * 7.4}px`);
      lower.appendChild(el("div", "disp", c.s.title.toUpperCase(), `background:#fff;color:#06122e;font-size:${fit(c.s.title, 4, 2.2, 50)}em;padding:.1em .5em;letter-spacing:.03em`));
      lower.appendChild(el("div", "disp", c.s.subtitle, "background:#ffcc00;color:#06122e;font-size:2em;padding:0 .6em;display:flex;align-items:center;letter-spacing:.06em"));
      c.box.appendChild(c.A(lower, "slideX", 0.6, { dist: -900, dur: 0.5, sfx: "whoosh", gain: 0.3 }));
      c.mascot("idle", c.W * 0.78, c.H * 0.3, 8);
    },
    headlines(c) {
      const items = c.s.items.slice(0, 4), n = items.length, tags = ["TOP STORY", "ALSO TONIGHT", "DEVELOPING", "IN OTHER NEWS"];
      let from = 0;
      const starts = items.map((it, i) => { if (i === 0) return 0.2; const r = c.say(it, from, 0.2 + i * (c.tm.duration - 0.8) / n); from = r.i + 1; return i < 2 && r.t > 0 ? r.t - 0.2 : 0.2 + i * (c.tm.duration - 0.8) / n; });
      items.forEach((it, i) => {
        const a = starts[i], z = i + 1 < n ? starts[i + 1] : c.tm.duration + 1;
        const card = place(el("div", null, null, "box-shadow:0 18px 50px rgba(0,0,0,.5)"), `left:6%;right:22%;top:${c.H * 0.28}px`);
        card.appendChild(el("div", "disp", tags[i], "display:inline-block;background:#e8112d;font-size:1.5em;padding:.05em .5em;letter-spacing:.08em"));
        card.appendChild(el("div", null, it, `background:#fff;color:#06122e;font-weight:800;font-size:${fit(it, 2.6, 1.5, 120)}em;line-height:1.15;padding:.5em .7em`));
        card.appendChild(el("div", "mono", "SOURCE: " + (c.s.evidence || "").toUpperCase(), "background:#06122e;color:#9fb6e0;font-size:.8em;padding:.3em .9em"));
        c.box.appendChild(card);
        c.A(card, "show", a, { until: z });
        c.A(card, "flip", a, { dur: 0.55, sfx: i ? "whoosh" : null, gain: 0.3 });
      });
      c.mascot("idle", c.W * 0.8, c.H * 0.36, 7);
    },
    numbers(c) {
      c.box.appendChild(c.A(place(el("div", "disp", c.s.heading, "font-size:2.6em;letter-spacing:.06em;background:#e8112d;padding:0 .4em"), "left:6%;top:16%"), "slideX", 0.1, { dist: -500 }));
      const row = place(el("div", null, null, "display:flex;gap:1.4em"), "left:6%;right:6%;top:34%");
      c.s.stats.forEach((st, i) => {
        const b = el("div", null, null, "flex:1;background:rgba(255,255,255,.08);border:2px solid rgba(255,255,255,.2);border-top:6px solid #ffcc00;padding:1em 1.2em");
        const v = el("div", "disp", st.value, "font-size:5.5em;line-height:1;color:#fff");
        c.A(v, "count", 0.6 + i * 0.4, { pre: "", num: parseFloat(st.value), post: "", dec: 0, dur: 1.2 });
        b.appendChild(v); b.appendChild(el("div", "disp", st.label.toUpperCase(), "font-size:1.6em;color:#ffcc00;letter-spacing:.06em"));
        row.appendChild(c.A(b, "rise", 0.4 + i * 0.4));
        for (let k = 0; k < 8; k++) c.cue(0.6 + i * 0.4 + k * 0.14, "tick", 0.2);
      });
      c.box.appendChild(row);
    },
    field(c) {
      const t = place(terminal(c, c.s.lines, Math.max(0.8, c.say(c.s.lines[0], 0, 1.0).t - 0.1), "live from the terminal"), "left:8%;right:30%;top:22%");
      c.box.appendChild(c.A(t, "rise", 0.3));
      const lower = place(el("div", null, null, "display:flex"), `left:8%;top:${c.H * 0.62}px`);
      lower.appendChild(el("div", "disp", c.s.kicker, "background:#e8112d;font-size:1.8em;padding:.05em .5em;letter-spacing:.06em"));
      lower.appendChild(el("div", null, "UPGRADE IN ONE LINE", "background:#fff;color:#06122e;font-weight:800;font-size:1.3em;padding:.3em .7em"));
      c.box.appendChild(c.A(lower, "slideX", 0.8, { dist: -700, sfx: "whoosh", gain: 0.25 }));
      c.mascot("point", c.W * 0.74, c.H * 0.3, 7.5);
    },
    signoff(c) {
      const desk = place(el("div", null, null, "background:linear-gradient(180deg,#12306e,#081a44);border-top:6px solid #e8112d"), `left:0;right:0;top:${c.H * 0.64}px;height:${c.H * 0.4}px`);
      c.box.appendChild(desk);
      c.mascot("wave", c.W * 0.5 - c.base * 4.5, c.H * 0.3, 9);
      const plate = place(el("div", null, null, "text-align:center"), `left:0;right:0;top:${c.H * 0.67}px`);
      plate.appendChild(el("div", "disp", c.s.title.toUpperCase(), "font-size:3em;letter-spacing:.05em"));
      if (c.s.url) plate.appendChild(el("div", "mono", c.s.url, "font-size:1em;color:#9fb6e0"));
      c.box.appendChild(c.A(plate, "fade", 0.6));
      c.box.appendChild(c.A(place(el("div", "disp", "GOOD NIGHT", "font-size:2em;letter-spacing:.3em;color:#ffcc00;text-align:center"), "left:0;right:0;top:12%"), "fade", 1.2));
    },

    // ===================== REEL (vertical)
    hook(c) {
      const wrap = el("div", "center", null, "gap:.4em;padding:0 8%"); c.box.appendChild(wrap);
      const emo = stopSign(7); wrap.appendChild(c.A(emo, "pop", 0.05, { dur: 0.4 }));
      c.A(emo, "wobble", 0, { amp: 10, speed: 8 });
      const words = c.s.text.split(" ");
      const line = el("div", null, null, "display:flex;flex-wrap:wrap;justify-content:center;gap:0 .3em");
      words.forEach((w, k) => {
        const at = c.say(w, 0, 0.2 + k * 0.3).t;
        const sp = el("span", null, w.toUpperCase(), "display:inline-block;font-weight:900;font-size:5em;line-height:1;color:#fff;-webkit-text-stroke:.06em #000;paint-order:stroke fill;text-shadow:0 .08em 0 #000");
        line.appendChild(c.A(sp, "slam", at, { from: 1.4, dur: 0.22, sfx: "hit", gain: 0.35 }));
        c.A(sp, "shake", at + 0.2, { amp: 8, dur: 0.25 });
      });
      wrap.appendChild(line);
      const sub = el("div", null, c.s.sub, "font-family:'Permanent Marker',cursive;font-size:2.4em;background:#fff200;color:#000;padding:.1em .5em;margin-top:.6em;border-radius:8px");
      sub.__base = "rotate(-3deg)";
      wrap.appendChild(c.A(sub, "pop", c.say(c.s.sub, 1, 1.2).t, { sfx: "pop", gain: 0.4 }));
    },
    namedrop(c) {
      const wrap = el("div", "center", null, "gap:1em;padding:0 8%"); c.box.appendChild(wrap);
      const t = el("div", null, c.s.title, `font-weight:900;font-size:${fit(c.s.title, 8, 4, 40)}em;line-height:1;letter-spacing:-.03em;color:#fff;-webkit-text-stroke:.05em #000;paint-order:stroke fill;text-shadow:.06em .06em 0 #000`);
      wrap.appendChild(c.A(t, "slam", 0.1, { from: 2, dur: 0.3 }));
      c.A(t, "shake", 0.4, { amp: 14, dur: 0.3 });
      const badge = place(el("div", null, "NEW", "width:5.5em;height:5.5em;border-radius:50%;background:#fff200;color:#000;font-weight:900;font-size:1.3em;display:flex;align-items:center;justify-content:center;border:4px solid #000"), `right:10%;top:${c.H * 0.25}px`);
      c.box.appendChild(c.A(badge, "pop", 0.6, { sfx: "pop", gain: 0.4 }));
      c.A(badge, "spin", 0, { speed: 40 });
      wrap.appendChild(c.A(el("div", null, c.s.subtitle, "background:#fff;color:#111;font-weight:700;font-size:1.5em;line-height:1.3;padding:.6em .8em;border-radius:16px;border:4px solid #000;box-shadow:6px 6px 0 #000"), "rise", 0.8));
      c.burst(0.4, 0.5, 0.42, { kind: "icons", icons: ["flame", "sparkle", "bolt"], colors: ["#fff200", "#ffffff", "#ff8a3d"], n: 16, size: 9, speed: 900, spread: Math.PI * 2, gravity: 400, life: 1.6 });
    },
    reasons(c) {
      const n = c.s.cards.length, nums = ["one", "two", "three"];
      let from = 0;
      const starts = c.s.cards.map((k, i) => { const r = c.say(nums[i], from, 0.9 + i * 1.2); from = r.i + 1; return r.t - 0.1; });
      // the heading owns the screen until reason one lands, then moves up out of the way
      const head = place(el("div", null, c.s.heading.toUpperCase(), "font-weight:900;font-size:4.6em;text-align:center;line-height:1;-webkit-text-stroke:.05em #000;paint-order:stroke fill"), `left:0;right:0;top:${c.H * 0.12}px`);
      head.appendChild(icon("arrowdown", "#fff200", 0.8, "margin-left:.25em;filter:drop-shadow(.06em .06em 0 #000)"));
      c.box.appendChild(c.A(head, "slam", 0.05, { from: 1.5, dur: 0.25 }));
      c.A(head, "along", 0, { points: [{ x: 0, y: c.H * 0.3, t: 0 }, { x: 0, y: c.H * 0.3, t: Math.max(0.3, starts[0] - 0.35) }, { x: 0, y: 0, t: starts[0] }] });
      c.s.cards.forEach((k, i) => {
        const a = starts[i], z = i + 1 < n ? starts[i + 1] : c.tm.duration + 1;
        const card = place(el("div", null, null, "background:#fff;color:#111;border:5px solid #000;border-radius:26px;box-shadow:10px 10px 0 #000;padding:1.4em 1.3em;text-align:center"), `left:9%;right:9%;top:${c.H * 0.26}px`);
        card.appendChild(el("div", null, String(i + 1), "font-weight:900;font-size:7em;line-height:.9;color:transparent;-webkit-text-stroke:.05em #111"));
        card.appendChild(el("div", null, k.title, `font-weight:900;font-size:${fit(k.title, 3.2, 2, 50)}em;line-height:1.05;margin-top:.2em`));
        if (k.body) card.appendChild(el("div", null, k.body, "font-size:1.2em;margin-top:.7em;line-height:1.35;color:#444"));
        card.__base = `rotate(${[-2, 2, -1][i % 3]}deg)`;
        c.box.appendChild(card);
        c.A(card, "show", a, { until: z });
        c.A(card, "pop", a, { dur: 0.4, sfx: "whoosh", gain: 0.35 });
      });
    },
    mindblown(c) {
      const wrap = el("div", "center", null, "gap:.4em;padding:0 8%"); c.box.appendChild(wrap);
      const st = c.s.stats[0], v = el("div", null, st.value, `font-weight:900;font-size:${fit(st.value, 11, 6, 30)}em;line-height:1;color:#fff200;-webkit-text-stroke:.04em #000;paint-order:stroke fill;text-shadow:.05em .05em 0 #000`);
      const m = /^(\D*)([\d,]*\.?\d+)(.*)$/.exec(st.value);
      if (m) c.A(v, "count", 0.2, { pre: m[1], num: parseFloat(m[2].replace(/,/g, "")), post: m[3], dec: 0, dur: 0.9 });
      wrap.appendChild(c.A(v, "pop", 0.1));
      c.A(v, "shake", 1.1, { amp: 16, dur: 0.35 });
      wrap.appendChild(c.A(icon("burst", "#fff200", 6, "filter:drop-shadow(.08em .08em 0 #000)"), "pop", 1.1, { sfx: "hit", gain: 0.5 }));
      c.burst(1.1, 0.5, 0.45, { kind: "icons", icons: ["burst", "sparkle", "star"], colors: ["#fff200", "#ffffff", "#00e5ff"], n: 20, size: 10, speed: 1100, spread: Math.PI * 2, gravity: 500, life: 1.8 });
      for (let k = 0; k < 9; k++) c.cue(0.2 + k * 0.1, "tick", 0.25);
    },
    tryit(c) {
      const wrap = el("div", "center", null, "gap:1.4em;padding:0 7%"); c.box.appendChild(wrap);
      const ti = el("div", null, "TRY IT", "font-weight:900;font-size:3.4em;-webkit-text-stroke:.05em #000;paint-order:stroke fill;display:flex;align-items:center;gap:.2em");
      ti.appendChild(icon("arrowdown", "#fff200", 0.85, "filter:drop-shadow(.06em .06em 0 #000)"));
      wrap.appendChild(c.A(ti, "slam", 0.05, { from: 1.5, dur: 0.25 }));
      const box = el("div", "mono", c.s.lines[0], `background:#111;color:#3dff8c;font-size:${fit(c.s.lines[0], 2.1, 1.2, 40)}em;padding:.9em 1em;border-radius:18px;border:4px solid #fff;box-shadow:8px 8px 0 #000;position:relative`);
      wrap.appendChild(c.A(box, "pop", 0.4, { sfx: "pop", gain: 0.4 }));
      const hand = place(icon("pointer", "#ffffff", 4, "filter:drop-shadow(3px 3px 0 #000)"), "left:58%;top:58%");
      c.box.appendChild(hand);
      c.A(hand, "along", 0, { points: [{ x: 200, y: 260, t: 0 }, { x: 200, y: 260, t: 1.0 }, { x: 0, y: 0, t: 1.5 }, { x: 0, y: 0, t: 9 }] });
      c.A(hand, "fade", 0.9);
      const toast = el("div", null, null, "background:#fff200;color:#000;font-weight:900;font-size:1.6em;padding:.3em .8em;border-radius:99px;border:3px solid #000;display:flex;gap:.4em;align-items:center");
      toast.appendChild(icon("check", "#000", 1)); toast.appendChild(el("span", null, "COPIED"));
      wrap.appendChild(c.A(toast, "pop", 1.6, { sfx: "click", gain: 0.5 }));
    },
    follow(c) {
      const wrap = el("div", "center", null, "gap:1.2em;padding:0 8%"); c.box.appendChild(wrap);
      wrap.appendChild(c.A(el("div", null, c.s.title, `font-weight:900;font-size:${fit(c.s.title, 6, 3.5, 34)}em;-webkit-text-stroke:.05em #000;paint-order:stroke fill;text-shadow:.06em .06em 0 #000`), "slam", 0.05, { from: 1.6, dur: 0.25 }));
      const btn = el("div", null, null, "background:#fff;color:#111;font-weight:900;font-size:2em;padding:.6em 1.2em;border-radius:99px;border:5px solid #000;box-shadow:0 8px 0 #000;display:flex;gap:.5em;align-items:center");
      btn.appendChild(icon("star", "#ffb800", 1.1)); btn.appendChild(el("span", null, "STAR ON GITHUB"));
      wrap.appendChild(c.A(btn, "pop", 0.5));
      c.A(btn, "press", 1.3, { sfx: "click", gain: 0.5 });
      if (c.s.url) wrap.appendChild(c.A(el("div", "mono", c.s.url, "font-size:1.3em;background:rgba(0,0,0,.35);padding:.3em .7em;border-radius:10px"), "fade", 0.9));
      c.burst(1.35, 0.5, 0.5, { kind: "stars", n: 40, colors: ["#fff200", "#fff"], size: 12, speed: 1000, spread: Math.PI * 2, gravity: 300 });
      c.cue(1.35, "sparkle", 0.5);
      c.mascot("cheer", c.W * 0.5 - c.base * 3, c.H * 0.79, 6);
    }
  };

  g.Repo2Video = { createVideo, timeline, FORMATS, mascot, ICONS };
})(typeof globalThis !== "undefined" ? globalThis : window);
