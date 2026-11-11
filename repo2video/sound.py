"""Original music and sound effects, synthesized from scratch (no samples, no licences to worry about).

score(style, total, scene_starts, cues, voice) -> stereo float32 at 48 kHz:
  five styles (trailer, synthwave, chiptune, news, trap), arranged around the scenes, with sound effects on the
  engine's cues and the music ducked under the voice.
"""
import numpy as np
from scipy.signal import butter, fftconvolve, resample_poly, sosfilt

SR = 48000
RNG = np.random.default_rng(7)  # fixed seed: the same story always sounds the same


def secs(n):
    return np.arange(int(n * SR)) / SR


def hz(semi, base=440.0):
    return base * 2 ** (semi / 12)


def osc(freq, dur, kind="sine", duty=0.5):
    """freq: number or array (for glides)."""
    n = int(dur * SR)
    f = np.broadcast_to(np.asarray(freq, dtype="float64"), (n,)) if np.ndim(freq) else np.full(n, float(freq))
    ph = np.cumsum(f) / SR
    if kind == "sine":
        return np.sin(2 * np.pi * ph)
    frac = ph % 1.0
    if kind == "saw":
        return 2 * frac - 1
    if kind == "square":
        return np.where(frac < duty, 1.0, -1.0)
    if kind == "tri":
        return 4 * np.abs(frac - 0.5) - 1
    raise ValueError(kind)


def noise(dur):
    return RNG.uniform(-1, 1, int(dur * SR))


def env(n, a=0.005, d=0.1, s=0.0, r=0.05, hold=None):
    """ADSR with linear attack, exponential-ish decay. hold = seconds at sustain before release."""
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    h_n = max(0, n - a_n - d_n - r_n) if hold is None else int(hold * SR)
    e = np.concatenate([np.linspace(0, 1, a_n, endpoint=False), s + (1 - s) * np.exp(-5 * np.linspace(0, 1, d_n)),
                        np.full(h_n, s), s * np.linspace(1, 0, r_n)])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def decay(n, k):
    return np.exp(-k * np.arange(n) / SR)


def filt(x, cut, kind="low", order=2):
    cut = np.clip(np.atleast_1d(cut), 20, SR / 2 - 100)
    if kind == "band":
        sos = butter(order, cut, btype="band", fs=SR, output="sos")
    else:
        sos = butter(order, cut[0], btype=kind, fs=SR, output="sos")
    return sosfilt(sos, x)


def sweep(x, c0, c1, kind="low", blocks=48):
    """Time-varying filter: cutoff moves exponentially from c0 to c1 across x."""
    out, edges = np.zeros_like(x), np.linspace(0, len(x), blocks + 1).astype(int)
    for i in range(blocks):
        c = c0 * (c1 / c0) ** ((i + 0.5) / blocks)
        out[edges[i]:edges[i + 1]] = filt(x[max(0, edges[i] - 2048):edges[i + 1]], c, kind)[-(edges[i + 1] - edges[i]):]
    return out


def supersaw(freq, dur, voices=5, spread=0.12):
    return sum(osc(hz(spread * (v - voices // 2), freq), dur, "saw") for v in range(voices)) / voices


# ---------------------------------------------------------------- instruments (return mono arrays)

def kick(d=0.45, punch=1.0):
    t = secs(d)
    f = 45 + 110 * np.exp(-t * 30) * punch
    return np.tanh(2 * osc(f, d) * decay(len(t), 7)) * 0.9 + noise(d) * decay(len(t), 300) * 0.25


def snare(d=0.22):
    n = int(d * SR)
    body = osc(190, d) * decay(n, 25) * 0.5
    return body + filt(noise(d), [1500, 9000], "band") * decay(n, 18) * 0.9


def clap(d=0.25):
    n, x = int(d * SR), np.zeros(int(d * SR))
    for k in (0, 0.011, 0.023):
        i = int(k * SR)
        x[i:] += noise(d - k) * decay(n - i, 40 if k < 0.02 else 14)
    return filt(x, [900, 6000], "band") * 1.2


def hat(d=0.05, open_=False):
    d = 0.28 if open_ else d
    return filt(noise(d), 7000, "high") * decay(int(d * SR), 9 if open_ else 70) * 0.5


def tom(f0=110, d=0.9):
    t = secs(d)
    return np.tanh(1.6 * osc(f0 * (0.6 + 0.4 * np.exp(-t * 6)), d) * decay(len(t), 4.5)) + \
        filt(noise(d), 800) * decay(len(t), 30) * 0.4


def b808(semi, d=0.8, glide_from=None):
    t = secs(d)
    f = hz(semi, 55)
    if glide_from is not None:
        f = hz(glide_from, 55) + (f - hz(glide_from, 55)) * (1 - np.exp(-t * 18))
    return np.tanh(2.5 * osc(f, d) * env(len(t), 0.003, d * 0.9, 0.3, 0.05))


def pluck(semi, d=0.3, base=220, kind="saw", bright=4000):
    n = int(d * SR)
    x = osc(hz(semi, base), d, kind)
    return sweep(x, bright, 300, blocks=8) * decay(n, 9)


def pad(semis, d, base=220, bright=1600):
    x = sum(supersaw(hz(s, base), d) for s in semis) / len(semis)
    return filt(x, bright) * env(int(d * SR), min(0.6, d / 3), 0.1, 0.9, min(0.8, d / 3))


def bell(f, d=1.4):
    n = int(d * SR)
    return sum(a * osc(f * r, d) * decay(n, k) for r, a, k in ((1, 1, 3), (2.76, 0.5, 6), (5.4, 0.25, 10), (8.9, 0.1, 16)))


def square_lead(semi, d, base=440, duty=0.25):
    t = secs(d)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 6 * t) * np.clip(t * 4 - 0.4, 0, 1)
    return osc(hz(semi, base) * vib, d, "square", duty) * env(len(t), 0.004, 0.08, 0.6, 0.04)


# ---------------------------------------------------------------- sound effects

def sfx(name):
    if name == "whoosh":
        d = 0.55
        x = noise(d) * np.sin(np.linspace(0, np.pi, int(d * SR))) ** 2
        return sweep(x, 300, 6000, "low") * 0.9
    if name == "whoosh_down":
        d = 0.5
        return sweep(noise(d) * np.sin(np.linspace(0, np.pi, int(d * SR))) ** 2, 7000, 250) * 0.8
    if name == "impact":
        d = 2.2
        t = secs(d)
        boom = np.tanh(2 * osc(32 + 70 * np.exp(-t * 9), d) * decay(len(t), 2.2))
        crack = filt(noise(d), 2500) * decay(len(t), 14) * 0.7
        return boom + crack
    if name == "braam":
        d = 2.6
        x = sum(supersaw(hz(s, 55), d, 7, 0.2) for s in (0, 7, 12)) / 3
        return np.tanh(2.5 * sweep(x, 120, 2200)) * env(int(d * SR), 0.05, 0.4, 0.7, 1.2) * 0.8
    if name == "riser":
        d = 2.0
        t = secs(d)
        tone = osc(hz(0, 110) * 2 ** (2.5 * t / d), d, "saw") * 0.35
        x = (filt(noise(d), 3000, "high") * 0.5 + tone) * (t / d) ** 2
        return sweep(x, 400, 9000)
    if name == "hit":
        return tom(70, 1.2) * 0.9 + sfx("impact")[: int(1.2 * SR)] * 0.4
    if name == "pop":
        d = 0.12
        t = secs(d)
        return osc(500 + 900 * t / d, d) * decay(len(t), 30) * 0.8
    if name == "tick":
        return filt(noise(0.015), 3000, "high") * decay(int(0.015 * SR), 300) * 0.5
    if name == "type":
        return filt(noise(0.03), [1200, 5000], "band") * decay(int(0.03 * SR), 160) * 0.6
    if name == "ding":
        return bell(1318.5, 1.6) * 0.5
    if name == "chime":  # subway ding-dong
        a, b = bell(659.3, 1.2), bell(523.3, 1.6)
        x = np.zeros(int(2.1 * SR))
        x[: len(a)] += a
        x[int(0.42 * SR):int(0.42 * SR) + len(b)] += b
        return x * 0.45
    if name == "coin":
        a, b = square_lead(-1, 0.07, 1046.5, 0.5), square_lead(4, 0.35, 1046.5, 0.5)
        return np.concatenate([a, b * decay(len(b), 8)]) * 0.35
    if name == "levelup":
        return np.concatenate([square_lead(s, 0.09, 523.25, 0.5) for s in (0, 4, 7, 12, 16, 19, 24)]) * 0.3
    if name == "powerup":
        d = 0.6
        t = secs(d)
        return osc(300 * 2 ** (2 * t / d) * (1 + 0.1 * np.sign(np.sin(2 * np.pi * 30 * t))), d, "square", 0.5) * 0.18 * decay(len(t), 2)
    if name == "sting":  # news sting: brass stab chord + timpani
        d = 1.6
        x = sum(pluck(s, d, 130.8, "saw", 5000) for s in (0, 3, 7, 12)) / 2
        return x + tom(65, 1.6) * 0.8
    if name == "glitch":
        d = 0.25
        x = noise(d)
        step = 24
        x = np.repeat(x[::step], step)[: int(d * SR)] * (RNG.uniform(size=int(d * SR)) > 0.4)
        return np.round(x * 4) / 4 * 0.5
    if name == "sparkle":
        out = np.zeros(int(1.2 * SR))
        for i, s in enumerate((12, 16, 19, 24, 28)):
            b = bell(hz(s, 880), 0.8) * 0.25
            j = int(i * 0.06 * SR)
            out[j:j + len(b)] += b[: len(out) - j]
        return out
    if name == "click":
        return filt(noise(0.02), 2000, "high") * decay(int(0.02 * SR), 200) + osc(1800, 0.02) * decay(int(0.02 * SR), 150) * 0.3
    if name == "shutter":
        return np.concatenate([sfx("click"), np.zeros(int(0.05 * SR)), sfx("click")])
    raise ValueError(name)


# ---------------------------------------------------------------- music

STYLES = {
    # bpm, key base Hz, chord progression (semitones from key), scale
    "trailer": (92, 73.42, [[0, 3, 7], [-4, 0, 3], [3, 7, 10], [-2, 2, 5]]),
    "synthwave": (100, 110.0, [[0, 3, 7], [-4, 0, 3], [3, 7, 10], [-2, 2, 5]]),
    "chiptune": (132, 261.63, [[0, 4, 7], [7, 11, 14], [9, 12, 16], [5, 9, 12]]),
    "news": (116, 130.81, [[0, 3, 7], [0, 3, 7], [-4, 0, 3], [-2, 2, 5]]),
    "trap": (145, 69.3, [[0, 3, 7], [-4, 0, 3], [-5, -2, 2], [-2, 2, 5]]),
}


def bpm_of(style):
    return STYLES[style][0]


def place(track, x, t, gain=1.0, pan=0.0):
    """Add mono x into stereo track at t seconds, equal-power pan."""
    i = int(t * SR)
    if i >= track.shape[1] or len(x) == 0:
        return
    j = min(track.shape[1], i + len(x))
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    track[0, i:j] += x[: j - i] * gain * l * 1.414
    track[1, i:j] += x[: j - i] * gain * r * 1.414


def reverb(track, size=1.8, wet=0.25):
    n = int(size * SR)
    out = track.copy()
    for ch in (0, 1):
        ir = RNG.uniform(-1, 1, n) * np.exp(-6 * np.arange(n) / n)
        ir = filt(ir, 5000) / np.sqrt(np.sum(ir ** 2))
        out[ch] += fftconvolve(track[ch], ir)[: track.shape[1]] * wet
    return out


def music(style, total, starts, lift):
    """The score. starts: scene start times; lift: index of the scene where the song kicks in fully."""
    bpm, base, prog = STYLES[style]
    beat, bar = 60 / bpm, 240 / bpm
    track = np.zeros((2, int((total + 3) * SR)))
    drop = starts[lift] if lift < len(starts) else 0.0
    nbars = int(np.ceil(total / bar)) + 1
    for b in range(nbars):
        t0 = b * bar
        if t0 >= total:
            break
        chord = prog[b % len(prog)]
        full = t0 >= drop - 1e-6
        if style == "trailer":
            if not full:
                place(track, pad([c - 12 for c in chord], bar, base * 2, 700), t0, 0.5)
                place(track, tom(55, 1.6), t0, 0.7)
                place(track, tom(62, 1.2), t0 + 2 * beat, 0.45, -0.2)
            else:
                place(track, pad(chord, bar, base * 4, 2600), t0, 0.45)
                for k in range(4):
                    place(track, kick(0.5, 1.2), t0 + k * beat, 0.85)
                    place(track, hat(), t0 + k * beat + beat / 2, 0.35, 0.3)
                    for e in range(2):
                        place(track, pluck(chord[0] - 12, beat / 2, base * 2, "saw", 900), t0 + k * beat + e * beat / 2, 0.55)
                for k in (1, 3):
                    place(track, snare(), t0 + k * beat, 0.6)
                    place(track, tom(90, 0.6), t0 + k * beat + beat * 0.5, 0.3, 0.4)
                for k in range(8):
                    place(track, pluck(chord[k % 3] + 12, beat / 2, base * 4, "saw", 6000), t0 + k * beat / 2, 0.16, -0.4 + 0.8 * (k % 2))
        elif style == "synthwave":
            place(track, pad(chord, bar, base * 2, 1400 if full else 700), t0, 0.32)
            for k in range(8):
                place(track, pluck(chord[0] - 12 + (12 if k % 2 else 0), beat / 2, base, "saw", 1100), t0 + k * beat / 2, 0.5)
            if full:
                for k in range(4):
                    place(track, kick(), t0 + k * beat, 0.7)
                for k in (1, 3):
                    place(track, snare(0.35), t0 + k * beat, 0.5)
                for k in range(16):
                    note = (chord + [chord[0] + 12])[[0, 1, 2, 3, 2, 1, 2, 3][k % 8]]
                    place(track, pluck(note + 12, beat / 4, base * 2, "saw", 5000), t0 + k * beat / 4, 0.14, 0.5 * np.sin(k))
                    place(track, hat(), t0 + k * beat / 4, 0.12 if k % 2 else 0.2, 0.25)
        elif style == "chiptune":
            for k in range(4):
                place(track, osc(hz(chord[0] - 12, base / 2), beat * 0.9, "tri") * env(int(beat * 0.9 * SR), 0.003, 0.2, 0.6, 0.05), t0 + k * beat, 0.45)
            if full:
                for k in range(4):
                    place(track, filt(noise(0.06), 200) * decay(int(0.06 * SR), 40), t0 + k * beat, 0.9)
                    place(track, hat(0.03), t0 + k * beat + beat / 2, 0.4)
                for k in (1, 3):
                    place(track, filt(noise(0.12), 3000, "high") * decay(int(0.12 * SR), 25), t0 + k * beat, 0.5)
                motif = [0, 2, 1, 2, 0, 1, 2, 3] if b % 2 == 0 else [3, 2, 1, 0, 1, 2, 1, 0]
                for k in range(8):
                    note = (chord + [chord[0] + 12])[motif[k]]
                    place(track, square_lead(note, beat / 2 * 0.85, base), t0 + k * beat / 2, 0.13)
            else:
                for k in range(8):
                    place(track, square_lead(chord[k % 3] + 12, beat / 4, base, 0.125), t0 + k * beat / 2, 0.06)
        elif style == "news":
            place(track, pad(chord, bar, base * 2, 1800), t0, 0.28)
            for k in range(16):
                place(track, hat(0.03), t0 + k * beat / 4, 0.18 if k % 4 else 0.3, 0.2)
            for k in range(8):
                place(track, pluck(chord[0] - 12, beat / 2, base, "square", 900), t0 + k * beat / 2, 0.35)
            if full:
                place(track, tom(65, 1.0), t0, 0.6)
                for k in (0, 2):
                    place(track, kick(), t0 + k * beat, 0.6)
                place(track, snare(), t0 + 3 * beat, 0.35)
        elif style == "trap":
            place(track, pad(chord, bar, base * 4, 2000), t0, 0.22)
            if full:
                place(track, b808(chord[0], bar * 0.7, chord[0] + 5 if b % 4 == 3 else None), t0, 0.75)
                place(track, kick(0.4), t0, 0.7)
                place(track, kick(0.4), t0 + 2.5 * beat, 0.5)
                place(track, clap(), t0 + 2 * beat, 0.6)
                for k in range(8):
                    place(track, hat(0.04), t0 + k * beat / 2, 0.3, 0.3)
                if b % 2 == 1:  # hi-hat roll
                    for k in range(6):
                        place(track, hat(0.025), t0 + 3 * beat + k * beat / 6, 0.22, 0.3)
                for k, s in enumerate([7, 3, 5, 3, 7, 10, 7, 3]):
                    place(track, pluck(s + chord[0], beat * 0.45, base * 8, "square", 7000), t0 + k * beat / 2, 0.1, -0.3)
            else:
                for k in range(4):
                    place(track, pluck(chord[k % 3] + 12, beat * 0.8, base * 8, "tri", 5000), t0 + k * beat, 0.12)
    if style == "trailer" and lift < len(starts):
        place(track, sfx("riser"), max(0, drop - 2.0), 0.55)
        place(track, sfx("impact"), drop, 0.9)
    track = reverb(track, 1.4 if style in ("trailer", "synthwave") else 0.9, 0.22 if style != "chiptune" else 0.08)
    fade = int(1.8 * SR)
    end = int(total * SR)
    track[:, end - fade:end] *= np.linspace(1, 0, fade)
    track[:, end:] = 0
    return track[:, :end]


def duck(music_track, voice, amount=0.6):
    """Sidechain: pull the music down while someone is talking."""
    env_ = np.abs(voice)
    k = int(0.08 * SR)
    env_ = np.convolve(env_, np.ones(k) / k, mode="same")
    env_ = np.clip(env_ / (np.percentile(env_[env_ > 1e-4], 90) if np.any(env_ > 1e-4) else 1), 0, 1)
    return music_track * (1 - amount * env_)


def score(style, total, starts, lift, cues, voice24k):
    """Final mix: voice (24 kHz mono) + score + sfx cues [{t, sfx, gain}] -> stereo 48 kHz, peak-limited."""
    voice = resample_poly(voice24k, 2, 1)[: int(total * SR)] if len(voice24k) else np.zeros(int(total * SR))
    voice = np.pad(voice, (0, max(0, int(total * SR) - len(voice))))
    talking = np.convolve(np.abs(voice), np.ones(2400) / 2400, "same") > 0.01
    if talking.any():  # every voice lands at the same level: -16 dB RMS while speaking
        voice = voice * 10 ** ((-16 - 20 * np.log10(np.sqrt(np.mean(voice[talking] ** 2)) + 1e-9)) / 20)
    m = duck(music(style, total, starts, lift), voice, 0.8) * 0.27  # bed sits ~14 dB under the voice
    fx = np.zeros((2, int((total + 3) * SR)))
    for c in cues:
        place(fx, sfx(c["sfx"]), c["t"], c.get("gain", 0.5), c.get("pan", 0.0))
    fx = fx[:, : m.shape[1]]
    mix = m + fx * 0.5 + voice[None, :]
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)  # soft limiter
    peak = np.max(np.abs(mix)) or 1
    return (mix / peak * 0.93).astype("float32")
