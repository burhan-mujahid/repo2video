---
name: repo2video
description: Turn a code repository into a narrated, scored video in one of five show formats - marketing (a movie trailer), engineering (a subway ride through the code, one stop per function), onboarding (a video-game quest), release (a breaking-news broadcast) and social (a 9:16 short). Use when the user asks for a video, trailer, explainer, demo, launch video, walkthrough, onboarding video, release video, reel or short about a repo, or says /repo2video. Exports to MP4, HyperFrames, Remotion and a BRIEF.md that lemo-opuscar or any other video skill can film in its own style.
argument-hint: "[path|owner/repo] [marketing|engineering|onboarding|release|social|all]"
license: MIT
---

# repo2video

The CLI finds the facts, writes a first script, voices it, scores it and renders it. Your job is to make the script great and keep it true.

## 1. Set up (once)

```sh
repo2video --help || pip install git+https://github.com/burhan-mujahid/repo2video
```

Needs Python 3.11+, ffmpeg and Chrome (or `python -m playwright install chromium`). The first voiced render downloads the Kokoro model (~120 MB) to `~/.cache/repo2video`.

## 2. Pick the mode

| The user wants | Mode | The show |
|---|---|---|
| launch, promo, landing page, "sell it", Product Hunt | `marketing` | movie trailer: cold open, the problem, title slam, montage, numbers, credits |
| how it works, architecture, code walkthrough | `engineering` | subway ride: ticket, district map, network map from real imports, one stop per function call |
| new contributors, first day, getting started | `onboarding` | video-game quest: objectives with XP, world map of folders, a boss fight with the first file to read |
| what's new, changelog, version announcement | `release` | breaking news: LIVE bug, headlines from the changelog, the numbers, a ticker |
| Shorts, Reels, TikTok, X, vertical, teaser | `social` | 9:16 short: hook, three reasons, the big number, try it |

Unclear: ask once. Several audiences: `-m all` makes all five.

## 3. Plan, then make the script great

```sh
repo2video <path|owner/repo> -m <mode> --plan-only -o r2v/<mode>
```

This writes `facts.json` (what the repo says, with file:line) and `story.json` (the scenes). Improve it:

- Read the README and the code at every `evidence` range before you write about it.
- Rewrite `narration` with energy and in the format's voice: a trailer narrator, a train conductor, a game guide, a news anchor, a creator talking to camera. Short sentences, one idea per scene, under 25 words (social: under 12).
- **Names go in backticks** (`` `src/lib.rs` ``, `` `register_all()` ``). The voice then reads their symbols: "source slash lib dot R S", "register underscore all". Plain words outside backticks are read normally, and words like live, read, record, export and update are pronounced by context.
- Marketing and social speak to outcomes. Engineering names real functions and files. Onboarding talks to a newcomer ("you").
- You may edit on-screen text (`title`, `subtitle`, `lines`, `cards`, `items`, `heading`), drop scenes or reorder them. Keep `type`.
- Never invent a feature, number or claim. If the repo does not say it, it does not go in. Keep `code`, `path`, `start` and `end` exactly as written: they are verified.

## 4. Render

```sh
repo2video --story r2v/<mode>/story.json -e mp4,brief        # add hyperframes,remotion if asked
```

Output in the same folder: `video.mp4`, `preview.gif` (README-sized), `soundtrack.wav` (voice, original score and sound effects), `BRIEF.md`.

Check the result: `ffmpeg -ss <t> -i video.mp4 -frames:v 1 f.png` at a few scene midpoints (scene start times are in `BRIEF.md`) and look at them. Text running off the frame means it is too long: shorten it and render again.

## 5. Other tools and styles

The story is the contract, so any renderer can film it:

- **HyperFrames:** `-e hyperframes` writes a project that passes `npx hyperframes check`. Preview it with `npx hyperframes preview`, or hand it to the `/hyperframes` skill to restyle.
- **Remotion:** `-e remotion` writes a project: `npm install && npm run render`.
- **lemo-opuscar** (or any film-style skill): give it `BRIEF.md`. It lists the scenes, the verbatim code, the evidence and styles that fit the mode. Say: *Make the film in BRIEF.md in the <style> style.*

## Options

`--voice` picks any Kokoro voice (defaults per mode: am_fenrir, am_michael, af_heart, bf_emma, af_bella). `--no-voice` renders captions and music only.
