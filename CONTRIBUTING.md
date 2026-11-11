# Contributing

Thank you for taking the time to improve repo2video. This guide covers the development setup, the conventions the
codebase follows, and what a good pull request looks like.

## Development setup

```sh
git clone https://github.com/burhan-mujahid/repo2video
cd repo2video
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
```

You also need `ffmpeg` on your `PATH`. The voice model (about 120 MB) downloads on the first voiced render; the test
suite does not need it.

## Running the checks

```sh
python -m pytest -q          # analysis, formats, pronunciation, timing, exports and a short render
python -m pyflakes repo2video tests docs
node --check repo2video/engine.js
```

## Conventions

- **Facts only.** Narration and on-screen text are built from what the repository says. A new scene type must not
  introduce claims, numbers or features that are not in `facts.json`.
- **Determinism.** Everything `engine.js` draws is a pure function of time. No `Date`, no unseeded randomness, no
  timers, no network access. This is what lets HyperFrames and Remotion render the same frames.
- **Small changes.** Prefer the smallest change that fully solves the problem. Reuse existing helpers before adding
  new ones, and do not add a dependency for a few lines of code.
- **One self-check per new behavior.** New logic (a parser, a pronunciation rule, a timing rule) ships with an
  assertion in `tests/test_core.py`.
- **Pronunciation rules** live in `repo2video/speech.py`. Add the failing sentence to `test_pronunciation` first,
  then the rule.

## Pull requests

1. Open an issue first for anything larger than a bug fix, so the approach can be agreed before you build it.
2. Keep each pull request focused on one change and describe what changed and why.
3. Include before and after frames (`ffmpeg -ss <t> -i video.mp4 -frames:v 1 frame.png`) for visual changes.
4. Make sure the checks above pass.

By contributing you agree that your contributions are licensed under the MIT License.
