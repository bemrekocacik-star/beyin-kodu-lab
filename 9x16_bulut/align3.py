#!/usr/bin/env python3
"""Beyin Kodu Lab hizalama v6.1-bulut (align2 v6.1 eşdeğeri): sessizlik parçaları + hece çekirdeği
zirveleri + noktalama DP + parça içi parçalı-doğrusal eşleme + SENKRON KAPISI.
Kullanım: python3 align3.py ses.mp3 metin.txt kelimeler.json [--spoken JSON] [--debug]
Çıkış kodu 1 = SENKRON KAPISI: KALDI (render yapılmaz)."""
import argparse, json, re, subprocess, sys
import numpy as np
from scipy.signal import find_peaks

ap = argparse.ArgumentParser()
ap.add_argument("voice"); ap.add_argument("text"); ap.add_argument("out")
ap.add_argument("--spoken", default="{}"); ap.add_argument("--debug", action="store_true")
ap.add_argument("--noise", default="-40dB"); ap.add_argument("--min", type=float, default=0.15)
a = ap.parse_args()
SP = json.loads(a.spoken)
words = open(a.text, encoding="utf-8").read().split()
N = len(words)
V = set("aeıioöuüâîûAEIİOÖUÜÂÎÛ")

def syl(w):
    base = re.sub(r"[^\wçğıöşüâîûÇĞİÖŞÜ']", "", w)
    stem = base.split("'")[0]
    rest = base[len(stem):]
    say = SP.get(stem, stem) + rest
    n = sum(1 for c in say if c in V)
    return max(1, n)

S = np.array([syl(w) for w in words], float)
def pun(w):
    if re.search(r"[.?!…]+[\"”']?$", w): return 0.0
    if re.search(r"[,;:\"”]$", w): return 0.15
    return 0.9
P = np.array([pun(w) for w in words])

# --- ses
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", a.voice, "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                     capture_output=True).stdout
x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
DUR = len(x) / 16000
out = subprocess.run(["ffmpeg", "-hide_banner", "-i", a.voice, "-af", f"silencedetect=noise={a.noise}:d={a.min}",
                      "-f", "null", "-"], capture_output=True, text=True).stderr
ss = [float(v) for v in re.findall(r"silence_start: ([\d.]+)", out)]
se = [float(v) for v in re.findall(r"silence_end: ([\d.]+)", out)]
sil = list(zip(ss, se + [DUR] * (len(ss) - len(se))))
lead = sil[0][1] if sil and sil[0][0] < 0.05 else 0.0
tail = sil[-1][0] if sil and sil[-1][1] >= DUR - 0.05 else DUR
gaps = [(s, e) for s, e in sil if s > 0.05 and e < DUR - 0.05]
blocks = []; t = lead
for s, e in gaps: blocks.append((t, s)); t = e
blocks.append((t, tail))

# --- hece çekirdekleri: 300-2500 Hz zarfı
F = np.fft.rfft(x); fr = np.fft.rfftfreq(len(x), 1 / 16000)
F[(fr < 300) | (fr > 2500)] = 0
xb = np.fft.irfft(F, len(x))
hop = 160; win = 320
nfr = (len(xb) - win) // hop
env = np.sqrt(np.array([np.mean(xb[i * hop:i * hop + win] ** 2) for i in range(nfr)]) + 1e-12)
env = np.convolve(env, np.hanning(5) / np.hanning(5).sum(), "same")
edb = 20 * np.log10(env + 1e-9)
tt = (np.arange(nfr) * hop + win / 2) / 16000
pk, _ = find_peaks(edb, distance=7, prominence=3.0, height=edb.max() - 35)
nuc = tt[pk]

blk = []
for (s, e) in blocks:
    n = nuc[(nuc > s + 0.02) & (nuc < e - 0.02)]
    blk.append((s, e, n))
B = len(blk)
spk = sum(e - s for s, e, _ in blk)
r0 = S.sum() / spk  # hece/sn
cs = np.concatenate([[0], np.cumsum(S)])

INF = 1e18
dp = np.full((B + 1, N + 1), INF); bk = np.zeros((B + 1, N + 1), int); dp[0][0] = 0
for b in range(1, B + 1):
    s, e, n = blk[b - 1]; d = e - s
    exp = 0.5 * len(n) + 0.5 * d * r0
    for j in range(0, N + 1):
        if b == B and j != N: continue
        ilo = max(0, j - 40)
        prev = dp[b - 1][ilo:j + 1]
        if prev.min() >= INF: continue
        syl_ = cs[j] - cs[ilo:j + 1]
        c = prev + np.log(np.maximum(syl_, 0.5) / max(exp, 0.5)) ** 2 * (1 + min(d, 3)) * 4 + (0 if j in (0, N) else P[j - 1])
        c[-1] = prev[-1] + (0.05 if d < 0.25 else 3.0 + 3 * d)
        k = int(np.argmin(c)); dp[b][j] = c[k]; bk[b][j] = ilo + k

assign = []; j = N
for b in range(B, 0, -1):
    i = bk[b][j]; assign.append((b - 1, i, j)); j = i
assign.reverse()

res = [None] * N; fails = []; notes = []
for bi, i, j in assign:
    s, e, n = blk[bi]; d = e - s
    if i == j:
        if d > 0.4: fails.append(f"boş parça {s:.2f}-{e:.2f}")
        continue
    Ssum = S[i:j].sum(); rate = Ssum / d
    if not (2.5 <= rate <= 9.5): fails.append(f"hece hızı {rate:.1f}/sn parça {s:.2f}-{e:.2f} ({' '.join(words[i:j])[:50]})")
    mid = P[j - 1] > 0.5 and j != N
    if mid:
        if len(n) and abs(Ssum - len(n)) / max(Ssum, len(n)) > 0.35:
            fails.append(f"cümle ortası bölünme + hece tutmuyor {s:.2f}-{e:.2f} ({int(Ssum)} vs {len(n)})")
        else:
            notes.append(f"not: doğal duraklama {e:.2f} sn '{words[j-1]}'")
    m = len(n)
    if m >= 2:
        bnd = [s] + [(n[k] + n[k + 1]) / 2 for k in range(m - 1)] + [e]
    else:
        bnd = [s, e]; m = 1
    qx = np.linspace(0, m, m + 1)
    pos = np.concatenate([[0], np.cumsum(S[i:j])])
    tm = np.interp(pos * m / Ssum, qx, bnd)
    for k in range(i, j):
        res[k] = {"w": words[k], "s": round(float(tm[k - i]), 3), "e": round(float(tm[k - i + 1]), 3)}
    if a.debug:
        print(f"[{s:6.2f}-{e:6.2f}] hece {int(Ssum):2d} çekirdek {len(n):2d} hız {rate:4.1f} | {' '.join(words[i:j])}")

if any(r is None for r in res): fails.append("eksik kelime")
else:
    if [r["w"] for r in res] != words: fails.append("kelime sırası bozuk")
    if any(res[k]["s"] > res[k + 1]["s"] for k in range(N - 1)): fails.append("zaman sırası bozuk")
    if abs(res[-1]["e"] - tail) > 0.3: fails.append(f"son kelime sonu {res[-1]['e']:.2f} / ses {tail:.2f}")
json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
json.dump({"pauses": [[round(s, 3), round(e, 3)] for s, e in gaps], "tail": tail, "dur": DUR},
          open(a.out.replace(".json", "_duraklama.json"), "w"))
print(f"{N} kelime, {B} parça, {len(nuc)} hece çekirdeği, ortalama {r0:.2f} hece/sn, ses {DUR:.2f} sn")
for t_ in notes: print(t_)
if fails:
    for f in fails: print("HATA:", f)
    print("SENKRON KAPISI: KALDI ✗"); sys.exit(1)
print("SENKRON KAPISI: GEÇTİ ✓")
