#!/usr/bin/env python3
"""Telifsiz müzik + efekt (numpy sentez) — Fleming. İleri bakışlı kısma (kelimeden 0,3 sn önce iner)."""
import json, numpy as np, wave
SR = 48000; D = 62.0; N = int(SR * D)
t = np.arange(N) / SR
L = np.zeros(N); Rr = np.zeros(N)
rng = np.random.default_rng(1)

def env(a, b, fi=1.0, fo=1.0):
    e = np.clip((t - a) / fi, 0, 1) * np.clip((b - t) / fo, 0, 1); return e
def note(f0, a, dur, amp, dec=1.5, pan=0.0, harm=(1, .35, .12)):
    i0 = int(a * SR); n = int(dur * SR); tt = np.arange(n) / SR
    s = sum(h * np.sin(2 * np.pi * f0 * (k + 1) * tt) for k, h in enumerate(harm))
    s *= np.exp(-tt * dec) * np.clip(tt / 0.01, 0, 1) * amp
    j = min(N, i0 + n); s = s[:j - i0]
    L[i0:j] += s * (1 - pan) ; Rr[i0:j] += s * (1 + pan)
def pad(freqs, a, b, amp, fi=1.5, fo=1.5):
    e = env(a, b, fi, fo) * amp
    s = sum(np.sin(2 * np.pi * f * t + k) * (1 + 0.15 * np.sin(2 * np.pi * 0.13 * t + k)) for k, f in enumerate(freqs)) / len(freqs)
    det = sum(np.sin(2 * np.pi * f * 1.003 * t) for f in freqs) / len(freqs)
    L[:] += e * s; Rr[:] += e * (0.6 * s + 0.4 * det)

A1 = 55.0
# 0-14.4 karanlık açılış (drone ≤0.05)
pad([A1, A1 * 1.5, A1 * 2], 0, 14.6, 0.05, 0.4, 1.0)
# 14.4-27.4 gizem: pad + parıltı
pad([110, 130.8, 164.8], 14.3, 27.6, 0.045, 0.8, 1.0)
for k, a in enumerate(np.arange(20.4, 27.3, 0.75)):
    note([440, 523.25, 659.25, 523.25][k % 4], a, 1.6, 0.035, 2.2, pan=0.3 * (-1) ** k)
# 27.4-38.2 sorun + savaş: kısık kalp atışı + düşük drone
pad([A1, 82.4], 27.3, 38.4, 0.05, 0.8, 0.6)
for a in np.arange(27.6, 38.2, 0.92 if True else 1):
    for d_, amp in [(0, 0.16), (0.2, 0.10)]:
        note(52, a + d_, 0.35, amp, 14, harm=(1, .2))
# 38.2-49.4 umut arpeji (C-G-Am-F), yükselen
prog = [[261.6, 329.6, 392.0], [196.0, 246.9, 293.7], [220.0, 261.6, 329.6], [174.6, 220.0, 261.6]]
k = 0
for a in np.arange(38.3, 49.3, 0.28):
    ch = prog[int((a - 38.3) / 2.24) % 4]
    amp = 0.03 + 0.03 * (a - 38.3) / 11
    note(ch[k % 3] * (2 if k % 6 >= 3 else 1), a, 1.2, amp, 3.0, pan=0.35 * np.sin(k)); k += 1
for i, ch in enumerate(prog * 2):
    a = 38.3 + i * 2.24
    if a < 49.3: pad([c / 2 for c in ch], a, min(a + 2.4, 49.6), 0.035, 0.4, 0.4)
# riser 48.6-49.4
rs = env(48.4, 49.45, 1.0, 0.05) * np.sin(2 * np.pi * (200 + 900 * np.clip((t - 48.4) / 1.05, 0, 1)) * t) * 0.03
L += rs; Rr += rs
# 49.4-51.8 zafer (triumph) — Kod'dan 0,6 sn önce biter
for ch, a in [([261.6, 329.6, 392.0, 523.3], 49.45), ([349.2, 440.0, 523.3, 698.5], 50.6)]:
    pad(ch, a, min(a + 1.25, 51.79), 0.06, 0.05, 0.25)
# 52.4-62 sakin final
pad([130.8, 196.0, 261.6], 52.45, 62.0, 0.035, 1.2, 1.6)

def burst(a, dur, amp, lo, hi, rise=True):
    i0 = int(a * SR); n = int(dur * SR); x = rng.standard_normal(n)
    X = np.fft.rfft(x); fr = np.fft.rfftfreq(n, 1 / SR); X[(fr < lo) | (fr > hi)] = 0
    x = np.fft.irfft(X, n); tt = np.arange(n) / n
    e = np.sin(np.pi * tt) ** 2 if rise else np.exp(-tt * 6)
    s = x / (np.abs(x).max() + 1e-9) * e * amp
    L[i0:i0 + n] += s * 0.9; Rr[i0:i0 + n] += s
# efektler (yalnız duraklamalarda): 2 whoosh + 3 özel
burst(14.08, 0.45, 0.10, 300, 3000)            # whoosh: petri sahnesine geçiş
burst(34.6, 0.45, 0.09, 300, 3000)             # whoosh: savaş
for f0 in (1318.5, 1975.5): note(f0, 18.5, 1.6, 0.05, 2.0, harm=(1, .2))   # chime: hale
note(48, 30.0, 0.6, 0.22, 7, harm=(1, .3, .1))  # thud: ilgilenmedi öncesi
note(65.4, 51.95, 1.8, 0.16, 2.5, harm=(1, .5, .25)); note(261.6, 51.95, 2.0, 0.05, 2.0)  # yumuşak final vuruşu

# ileri bakışlı kısma
W = json.load(open("kelimeler.json"))
g = np.ones(N)
for w in W:
    a, b = int(max(w["s"] - 0.3, 0) * SR), int(min(w["e"] + 0.08, D) * SR)
    g[a:b] = 0.15
for a_, b_ in [(45.2, 46.3), (35.9, 37.0), (29.9, 30.8)]:
    g[int(a_ * SR):int(b_ * SR)] = np.minimum(g[int(a_ * SR):int(b_ * SR)], 0.05)
k = int(0.12 * SR); g = np.convolve(g, np.ones(k) / k, "same")
M = np.stack([L * g, Rr * g], 1)
M = M / (np.abs(M).max() + 1e-9) * 0.7
with wave.open("muzik.wav", "wb") as f:
    f.setnchannels(2); f.setsampwidth(2); f.setframerate(SR)
    f.writeframes((M * 32767).astype(np.int16).tobytes())
print("muzik.wav", D)
