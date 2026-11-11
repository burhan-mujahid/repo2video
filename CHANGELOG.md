# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Reproducible font build: `docs/make_fonts.py` downloads the seven fonts from a pinned commit of google/fonts,
  subsets them and writes `repo2video/fonts.js` and `site/fonts/*.woff`. `fonttools` joins the `dev` extra.
- `publish.yml` uploads each release to PyPI with trusted publishing, after the Release workflow succeeds.

### Changed

- Ready for PyPI (`pip install repo2video` from 0.2.0). The spaCy English model is no longer a URL dependency: it is downloaded
  once (about 13 MB) into `~/.cache/repo2video` on first use, unless it is already installed. spaCy is pinned to 3.8
  to match the model.

## [0.1.0] - 2026-11-11

First public release.

### Added

- Repository analysis: pitch, problem and proof statements, install and usage commands, language mix, folder map,
  entry point detection, a call trace through real function calls, an import graph (Python, JavaScript/TypeScript,
  Rust, Go), contributing rules, and release notes from `CHANGELOG` or `git log`.
- Five show formats, one per mode: `marketing` (trailer), `engineering` (metro), `onboarding` (quest),
  `release` (news) and `social` (9:16 reel). Every line of narration is built from facts in the repository.
- Speech pipeline: name verbalization (`brief.md` is read as "brief dot M D"), number, unit and version
  normalization, part-of-speech heteronym resolution with rule overrides, a technical lexicon, and per-word timings.
- Procedural score and sound design: five original scores and nineteen sound effects synthesized in NumPy,
  beat-quantized scene cuts, cue-driven effects, voice ducking and loudness normalization to -14 LUFS.
- Scene engine: a deterministic, dependency-free renderer with a composable animation system, camera moves,
  per-format transitions, seeded particles, film grain, five caption styles, an SVG icon set and a mascot that
  lip-syncs to the narration.
- Exports: MP4 and GIF, a HyperFrames project, a Remotion project, and `BRIEF.md` for agent video skills.
- Claude Code plugin and skill.

[Unreleased]: https://github.com/burhan-mujahid/repo2video/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/burhan-mujahid/repo2video/releases/tag/v0.1.0
