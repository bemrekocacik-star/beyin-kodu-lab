#!/usr/bin/env python3
"""Beyin Kodu Lab hizalama v2 (ASR'siz, uzun anlatım için): sessizlik aralıklarını kelime sınırlarına
hece-hızı tutarlılığıyla (DP) eşler. Türkçede hece = ünlü sayısı -> süre tahmini çok kararlı.
Kullanım: python3 align2.py ses.mp3 metin.txt kelimeler.json [--noise=-32dB] [--min=0.18]"""
import argparse, json, math, re, subprocess
import numpy as np
ap = argparse.ArgumentParser(); ap.add_argument("voice"); ap.add_argument("text"); ap.add_argument("out")
ap.add_argument("--noise", default="-32dB"); ap.add_argument("--min", type=float, default=0.18); a = ap.parse_args()
words = open(a.text, encoding="utf-8").read().split()
V = "aeıioöuüâîûAEIİOÖUÜ"
def syl(w):
    w2 = re.sub(r"[^\wçğıöşüâîûÇĞİÖŞÜ]", "", w)
    if re.fullmatch(r"\d+", w2): return max(1, len(w2))
    n = sum(1 for c in w2 if c in V)
    return max(1, n) + 0.15
S = np.array([syl(w) for w in words])
out = subprocess.run(["ffmpeg", "-hide_banner", "-i", a.voice, "-af", f"silencedetect=noise={a.noise}:d={a.min}", "-f", "null", "-"], capture_output=True, text=True).stderr
ss = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]; se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
DUR = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.voice], capture_output=True, text=True).stdout)
sil = list(zip(ss, se + [DUR] * (len(ss) - len(se))))
lead = sil[0][1] if sil and sil[0][0] < 0.05 else 0.0
tail = sil[-1][0] if sil and sil[-1][1] >= DUR - 0.05 else DUR
gaps = [(s, e) for s, e in sil if s > 0.05 and e < DUR - 0.05]
# konuşma blokları
blocks = []; t = lead
for s, e in gaps: blocks.append((t, s)); t = e
blocks.append((t, tail))
B = len(blocks); N = len(words)
r0 = sum(e - s for s, e in blocks) / S.sum()
cs = np.concatenate([[0], np.cumsum(S)])
punct = np.array([1 if re.search(r"[,.;:!?…]$", w) else 0 for w in words])
# dp[b][j]: ilk b blok, ilk j kelime ile bitti. Bir blok >=1 kelime. Bir blok sonu kelime sınırına denk.
INF = 1e18
dp = np.full((B + 1, N + 1), INF); bk = np.zeros((B + 1, N + 1), dtype=np.int32)
dp[0][0] = 0
exp_j = lambda b: cs.searchsorted(sum(e - s for s, e in blocks[:b]) / r0)
for b in range(1, B + 1):
    d = blocks[b - 1][1] - blocks[b - 1][0]
    ej = exp_j(b); lo = max(0, ej - 150); hi = min(N, ej + 150) if b < B else N
    if b == B: lo = N
    for j in range(lo, hi + 1):
        best = INF; arg = 0
        ilo = max(0, j - 40)
        prev = dp[b - 1][ilo:j + 1]
        if prev.min() >= INF: continue
        sylls = cs[j] - cs[ilo:j + 1]
        rate = d / np.maximum(sylls, 0.5)
        c = prev + np.log(rate / r0) ** 2 * (1 + min(d, 3)) + (0 if (j == N or j == 0 or punct[j - 1]) else 0.35)
        c[-1] = prev[-1] + (0.05 if d < 0.25 else 3.0 + d)  # kelimesiz blok (nefes/gürültü)
        k = int(np.argmin(c)); dp[b][j] = c[k]; bk[b][j] = ilo + k
res = [None] * N; j = N
for b in range(B, 0, -1):
    i = bk[b][j]; s, e = blocks[b - 1]
    if i == j: continue
    tot = S[i:j].sum(); x = s
    for k in range(i, j):
        dd = (e - s) * S[k] / tot; res[k] = {"w": words[k], "s": round(x, 3), "e": round(x + dd, 3)}; x += dd
    j = i
json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
print(f"{N} kelime, {B} blok, maliyet {dp[B][N]:.2f}, hız {1/r0:.2f} hece/sn, ses {DUR:.2f} sn")
