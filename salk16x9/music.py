"""Ozgun sentez muzik + ses efektleri (telifsiz, kodla uretilir) ve 4 kanalli miks.
Kullanim: python3 music.py timeline.json out.wav [--narration voice.wav]
Olaylar sahne zamanlarindan okunur; sahne suresi degisince muzik de kayar.
"""
import json, sys, argparse, math, math
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import build_timeline, subtitles

SR = 48000


def lp(x, fc, order=2):
    return sosfilt(butter(order, fc, "low", fs=SR, output="sos"), x)

def hp(x, fc, order=2):
    return sosfilt(butter(order, fc, "high", fs=SR, output="sos"), x)

def env_adsr(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e

def saw(f, t, detune=0.0):
    out = 0
    for d in (-detune, 0, detune):
        ph = (f * (1 + d) * t) % 1.0
        out = out + (2 * ph - 1)
    return out / 3

def pad(freqs, dur, t0, total, gain=0.08, cutoff=900, a=1.5, r=1.5):
    n = int(dur * SR); t = np.arange(n) / SR
    x = sum(saw(f, t, 0.004) for f in freqs) / len(freqs)
    x = lp(x, cutoff, 2) * env_adsr(n, a, r) * gain
    out = np.zeros(int(total * SR)); s = int(t0 * SR)
    out[s:s + n] += x[: len(out) - s]
    return out

def impact(t0, total, gain=0.5, f0=52):
    n = int(2.6 * SR); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (f0 * t + 30 * (1 - np.exp(-t * 18)) / 18)) * np.exp(-t * 2.2)
    rng = np.random.default_rng(1)
    noise = lp(rng.normal(0, 1, n), 1800) * np.exp(-t * 9) * 0.35
    x = (body + noise) * gain
    out = np.zeros(int(total * SR)); s = int(t0 * SR)
    out[s:s + n] += x[: len(out) - s]
    return out

def riser(t0, t1, total, gain=0.12):
    n = int((t1 - t0) * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(2)
    x = rng.normal(0, 1, n)
    # zamanla acilan filtre: parcalara bolup kesim frekansini arttir
    y = np.zeros(n); seg = SR // 20
    for i in range(0, n, seg):
        fc = 300 + 5000 * (i / n) ** 2
        y[i:i + seg] = lp(x[i:i + seg], fc, 1)
    y *= (np.linspace(0, 1, n) ** 2) * gain
    out = np.zeros(int(total * SR)); s = int(t0 * SR)
    out[s:s + n] += y
    return out

def tick(t0, t1, total, period=0.833, gain=0.10):
    out = np.zeros(int(total * SR))
    n = int(0.12 * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(4)
    k = 0
    tt = t0
    while tt < t1:
        hit = (np.sin(2 * np.pi * 70 * t) * np.exp(-t * 35) * (0.9 if k % 2 == 0 else 0.6)
               + hp(rng.normal(0, 1, n), 3000) * np.exp(-t * 80) * 0.15) * gain
        s = int(tt * SR); out[s:s + n] += hit[: len(out) - s]
        tt += period; k += 1
    return out

def bell(t0, total, freqs=(523.25, 659.25, 783.99, 1046.5), gain=0.08):
    n = int(3.0 * SR); t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * (1.2 + i * 0.4)) for i, f in enumerate(freqs))
    x = x / len(freqs) * gain * env_adsr(n, 0.01, 0.3)
    out = np.zeros(int(total * SR)); s = int(t0 * SR)
    out[s:s + n] += x[: len(out) - s]
    return out

def whoosh(t0, total, dur=0.9, gain=0.10):
    """Yumusak gecis sesi: filtrelenmis gurultu, yukselip alcalan kesim frekansi."""
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(int(t0 * 100) % 9999)
    x = rng.normal(0, 1, n)
    y = np.zeros(n); seg = SR // 40
    for i in range(0, n, seg):
        u = i / n
        fc = 400 + 3800 * math.sin(math.pi * u) ** 2
        y[i:i + seg] = lp(x[i:i + seg], fc, 1)
    env = np.sin(np.pi * np.linspace(0, 1, n)) ** 1.5
    out = np.zeros(int(total * SR)); s0 = int(max(t0 - dur * 0.5, 0) * SR)
    seg_ = (y * env * gain)[: len(out) - s0]
    out[s0:s0 + len(seg_)] += seg_
    return out


# ---- fiziksel olay sesleri (kagit / masa) - hepsi sentez, telifsiz ----
def _place(out, sig, t0):
    s0 = int(max(t0, 0) * SR)
    seg = sig[: max(len(out) - s0, 0)]
    out[s0:s0 + len(seg)] += seg
    return out


def _bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)


def sfx_event(kind, t0, total, gain=1.0, dur=None, seed=0):
    out = np.zeros(int(total * SR))
    rng = np.random.default_rng(seed + int(t0 * 1000))
    if kind == "air":          # hava hareketi: yukselen filtreli gurultu
        d = dur or 0.8; n = int(d * SR); x = rng.normal(0, 1, n); y = np.zeros(n); seg = SR // 40
        for i in range(0, n, seg):
            u = i / n; y[i:i + seg] = lp(x[i:i + seg], 300 + 2600 * u ** 2, 1)
        return _place(out, y * (np.linspace(0, 1, n) ** 2) * 0.10 * gain, t0 - d)
    if kind == "body":         # tok govde temasi (masa + kagit kutlesi)
        n = int(0.16 * SR); t = np.arange(n) / SR
        y = np.sin(2 * np.pi * 72 * t) * np.exp(-t * 32) + lp(rng.normal(0, 1, n), 450) * np.exp(-t * 45) * 0.8
        return _place(out, y * 0.55 * gain, t0)
    if kind == "slap":         # keskin kagit saplamasi
        n = int(0.07 * SR); t = np.arange(n) / SR
        y = _bp(rng.normal(0, 1, n), 1200, 6500) * np.exp(-t * 70)
        return _place(out, y * 0.45 * gain, t0)
    if kind == "tick":         # kose inisi
        n = int(0.025 * SR); t = np.arange(n) / SR
        return _place(out, hp(rng.normal(0, 1, n), 3000) * np.exp(-t * 220) * 0.18 * gain, t0)
    if kind == "resonance":    # masa tini
        n = int(0.3 * SR); t = np.arange(n) / SR
        return _place(out, np.sin(2 * np.pi * 88 * t) * np.exp(-t * 14) * 0.16 * gain, t0)
    if kind == "bass":         # kisa, kontrollu bas vurgusu (patlama degil)
        n = int(0.6 * SR); t = np.arange(n) / SR
        y = np.sin(2 * np.pi * (40 * t + 18 * (1 - np.exp(-t * 20)) / 20)) * np.exp(-t * 5.5)
        return _place(out, y * 0.42 * gain, t0)
    if kind == "scrape":       # yerlesme surtunmesi
        d = dur or 0.25; n = int(d * SR)
        env = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
        return _place(out, _bp(rng.normal(0, 1, n), 1800, 5200) * env * 0.05 * gain, t0)
    if kind == "room":         # ortam tonu
        d = dur or 4.0; n = int(d * SR)
        env = np.minimum(1, np.minimum(np.arange(n) / (0.4 * SR), (n - np.arange(n)) / (0.4 * SR)))
        return _place(out, lp(rng.normal(0, 1, n), 220) * env * 0.035 * gain, t0)
    if kind == "crowd":        # uzak kalabalik mirildanmasi: bant gecirgen gurultu + yavas genlik dalgasi
        d = dur or 5.0; n = int(d * SR); tt = np.arange(n) / SR
        y = _bp(rng.normal(0, 1, n), 300, 2400)
        am = 0.6 + 0.25 * np.sin(2 * np.pi * 0.7 * tt + 1.3) + 0.15 * np.sin(2 * np.pi * 1.9 * tt)
        env = np.minimum(1, np.minimum(tt / 0.6, (d - tt) / 0.8))
        return _place(out, y * am * env * 0.05 * gain, t0)
    if kind == "dust":         # cok hafif toz/yuzey sesi
        n = int(0.5 * SR); t = np.arange(n) / SR
        return _place(out, _bp(rng.normal(0, 1, n), 2500, 8000) * np.exp(-t * 9) * 0.03 * gain, t0)
    return out


def reverb(x, rt=2.4, mix=0.28):
    n = int(rt * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(9)
    ir = rng.normal(0, 1, n) * np.exp(-t * 6.9 / rt)
    ir = lp(ir, 5000) ; ir /= np.sqrt(np.sum(ir ** 2))
    wet = fftconvolve(x, ir)[: len(x)]
    return x * (1 - mix) + wet * mix


MOODS = {
    "tension": ([55.0, 82.41, 110.0, 130.81, 164.81], 700, 0.10),      # La minor
    "dark":    ([49.0, 73.42, 98.0, 116.54, 146.83], 550, 0.10),       # Sol minor (daha karanlik)
    "curious": ([65.41, 98.0, 130.81, 155.56, 196.0], 900, 0.08),      # Do minor, acik
    "hope":    ([87.31, 130.81, 174.61, 220.0, 261.63], 1400, 0.10),   # Fa major
    "resolve": ([65.41, 98.0, 130.81, 164.81, 196.0, 261.63], 1600, 0.09),  # Do major
}


def build_cues(tl, sc, total):
    """timeline['music'] yoksa bolum basliklarindan otomatik ruh hali cikarir."""
    m = tl.get("music")
    if m:
        return m["moods"], m.get("hits", []), m.get("risers", []), m.get("drops", [])
    S = {s["id"]: s for s in sc}
    if "s5_isim" in S:  # 16:9 deneme (eski) duzeni
        return ([[0, "tension"], [S["s6_karar"]["start"] - 0.2, "hope"], [S["s7_logo"]["start"], "resolve"]],
                [[0.25, 0.35, 48], [S["s5_isim"]["start"] + 0.22, 0.55, 44], [S["s7_logo"]["start"] + 0.05, 0.3, 58]],
                [[S["s5_isim"]["start"] - 1.5, S["s5_isim"]["start"] + 0.2]], [])
    moods = [[0, "tension"]]
    hits = [[s["start"] + 0.15, 0.4, 48] for s in sc if s["type"] == "chapter"]
    return moods, hits, [], []


def build(tl_path, narration=None):
    tl = json.load(open(tl_path, encoding="utf-8"))
    sc, total = build_timeline(tl)
    T = total + 0.2
    moods, hits, risers, drops = build_cues(tl, sc, total)
    music = np.zeros(int(T * SR))
    for i, (t0, mood) in enumerate(moods):
        t1 = moods[i + 1][0] if i + 1 < len(moods) else total
        freqs, cut, gain = MOODS[mood]
        music += pad(freqs, (t1 - t0) + 1.2, max(t0 - 0.6, 0), T, gain=gain, cutoff=cut, a=1.4, r=1.4)
    # gerilim bolumlerinde ince ust ses
    for i, (t0, mood) in enumerate(moods):
        t1 = moods[i + 1][0] if i + 1 < len(moods) else total
        if mood in ("tension", "dark", "curious") and t1 - t0 > 4:
            music += pad([220.0, 261.63, 329.63], t1 - t0, t0, T, gain=0.022, cutoff=1500, a=2.5, r=1.0)
    music = reverb(music, 2.8, 0.35)
    sfx = np.zeros(int(T * SR))
    for t0, g, f0 in hits:
        sfx += impact(t0, T, gain=g, f0=f0)
    for a, b in risers:
        sfx += riser(a, b, T)
    for b in tl.get("bells", []):
        sfx += bell(b, T, gain=0.06)
    ticks = tl.get("ticks")
    if ticks:
        for a, b in ticks:
            sfx += tick(a, b, T)
    elif "s5_isim" in {s["id"] for s in sc}:
        S = {s["id"]: s for s in sc}
        sfx += tick(S["s2_sayac"]["start"] + 0.2, S["s5_isim"]["start"] - 0.4, T)
        sfx += bell(S["s6_karar"]["start"] + 1.15, T, gain=0.06)
        sfx += bell(S["s7_logo"]["start"] + 0.9, T, (783.99, 987.77, 1174.66, 1567.98), gain=0.06)
    # sahneye bagli ses olaylari (gorsel olay zaman kodlarina kilitli)
    for sp in sc:
        for ev in sp.get("soundEffects", []):
            tt = sp["start"] + ev.get("t", 0)
            k = ev.get("type")
            if k == "impact":
                sfx += impact(tt, T, gain=ev.get("gain", 0.4), f0=ev.get("f0", 48))
            elif k == "riser":
                sfx += riser(tt - ev.get("dur", 1.4), tt, T, gain=ev.get("gain", 0.12))
            elif k == "bell":
                sfx += bell(tt, T, gain=ev.get("gain", 0.06))
            elif k == "whoosh":
                sfx += whoosh(tt, T, gain=ev.get("gain", 0.10))
            elif k == "silence":
                drops.append([tt, tt + ev.get("dur", 0.3)])
            else:
                sfx += sfx_event(k, tt, T, gain=ev.get("gain", 1.0), dur=ev.get("dur"))
    sfx = reverb(sfx, 1.2, 0.12)

    # vuruslar/sessizlik anlari: muzik dususu (yumusak) kisa sessizlik (reveal oncesi muzik dususu)
    for d0, d1 in drops:
        i0, i1 = int(d0 * SR), int(d1 * SR)
        k = int(0.25 * SR)
        env = np.ones(len(music))
        env[i0:i1] = 0.08
        env = np.convolve(env, np.ones(k) / k, mode="same")
        music *= env
    # ducking: anlatim varsa konusma araliklarinda muzik -9 dB (yumusak gecis)
    duck = np.ones(len(music))
    speech = [(a, b) for a, b, _ in subtitles(sc)]
    if narration is not None:
        g = 10 ** (-9 / 20)
        for a, b in speech:
            i0, i1 = int(max(a - 0.25, 0) * SR), int(min(b + 0.35, T) * SR)
            duck[i0:i1] = np.minimum(duck[i0:i1], g)
        k = int(0.4 * SR)
        duck = np.convolve(duck, np.ones(k) / k, mode="same")
    mix = music * duck + sfx
    if narration is not None:
        mix[: len(narration)] += narration[: len(mix)]
    fi, fo = int(0.3 * SR), int(1.2 * SR)
    mix[:fi] *= np.linspace(0, 1, fi)
    end = int(total * SR)
    mix[end - fo:end] *= np.linspace(1, 0, fo)
    mix[end:] = 0
    st = np.stack([mix, mix], 1)
    d = int(0.012 * SR)
    st[d:, 1] = mix[:-d] * 0.35 + mix[d:] * 0.65
    return st, total


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("timeline"); ap.add_argument("out")
    a = ap.parse_args()
    st, total = build(a.timeline)
    st = st / (np.max(np.abs(st)) + 1e-9) * 0.7
    import wave
    pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    print("wrote", a.out, total)
