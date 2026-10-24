#!/usr/bin/env python3
"""Beyin Kodu Lab: seslendirme metnini ElevenLabs sesine kelime kelime oturtur (transkript gerekmez).
Kullanım: python3 /root/tools/align.py ses.mp3 metin.txt kelimeler.json [--spoken '{"1994’te":"bindokuzyüzdoksandörtte"}']
"""
import argparse, json, re, subprocess
ap = argparse.ArgumentParser(); ap.add_argument("voice"); ap.add_argument("text"); ap.add_argument("out")
ap.add_argument("--spoken", default="{}"); ap.add_argument("--noise", default="-35dB"); a = ap.parse_args()
SPOK = json.loads(a.spoken)
words = open(a.text, encoding="utf-8").read().replace("**", "").split()
L = [len(re.sub(r"[^\wçğıöşüâîû]", "", SPOK.get(w, w).lower())) + 1 for w in words]
out = subprocess.run(["ffmpeg", "-hide_banner", "-i", a.voice, "-af", f"silencedetect=noise={a.noise}:d=0.2", "-f", "null", "-"], capture_output=True, text=True).stderr
ss = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]; se = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
DUR = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.voice], capture_output=True, text=True).stdout)
lead = se[0] if ss and ss[0] < 0.05 else 0.0
gaps = []
for s0, e0 in zip(ss, se):
    if s0 < 0.05 or e0 >= DUR - 0.05: continue
    if gaps and s0 - gaps[-1][1] < 0.1: gaps[-1] = (gaps[-1][0], e0)
    else: gaps.append((s0, e0))
end_speech = ss[-1] if len(ss) > len(se) or (se and se[-1] >= DUR - 0.05) else DUR
iv = []; t = lead
for s0, e0 in gaps: iv.append((t, s0)); t = e0
iv.append((t, end_speech))
tot = sum(e0 - s0 for s0, e0 in iv); gfrac = []; acc = 0
for k in range(len(gaps)): acc += iv[k][1] - iv[k][0]; gfrac.append(acc / tot)
cands = list(range(len(words) - 1)); TC = sum(L)
cf = {i: sum(L[:i + 1]) / TC for i in cands}
PEN = {i: (0 if re.search(r"[,.;:!?…]$", words[i]) else 0.025) for i in cands}
G, C = len(gaps), len(cands); INF = 1e9
dp = [[INF] * (C + 1) for _ in range(G + 1)]; bk = [[0] * (C + 1) for _ in range(G + 1)]
for j in range(C + 1): dp[0][j] = 0
for g in range(1, G + 1):
    for j in range(1, C + 1):
        o = dp[g][j - 1]; n = dp[g - 1][j - 1] + abs(gfrac[g - 1] - cf[cands[j - 1]]) + PEN[cands[j - 1]]
        dp[g][j], bk[g][j] = (n, 1) if n < o else (o, 0)
g, j = G, C; assign = {}
while g > 0:
    if bk[g][j] == 1: assign[g - 1] = cands[j - 1]; g -= 1
    j -= 1
res = []; start = 0
for k, bi in enumerate([assign[k] for k in range(G)] + [len(words) - 1]):
    ws = list(range(start, bi + 1)); s0, e0 = iv[k]; sl = sum(L[i] for i in ws); t = s0
    for i in ws:
        d = (e0 - s0) * L[i] / sl; res.append({"w": words[i].replace("’", "'"), "s": round(t, 3), "e": round(t + d, 3)}); t += d
    start = bi + 1
json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
print(f"{len(words)} kelime, {G} duraklama, maliyet {dp[G][C]:.3f}, ses {DUR:.2f} sn")
for k in range(G): print(f"  {gaps[k][0]:6.2f} sn  <- {words[assign[k]]}")
