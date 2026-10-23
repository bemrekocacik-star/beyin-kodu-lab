"""Gercek anlatimi plana hazirlar:
 - kelime zamanlarini (araclar/hizala.py ciktisi) okur
 - basa 0.6 sn sessizlik, her bolum basligindan once nefes araligi ekler (gap >= CH_DUR + 0.6)
 - audio/anlatim.wav (48 kHz stereo) + audio/kelimeler.json (kaydirilmis zamanlar) yazar
Kullanim: python ses_hazirla.py audio/anlatim_ham.mp3 audio/kelimeler_ham.json
"""
import sys, json, re, subprocess
import numpy as np
from plan_salk import SEG, CH_DUR

SR = 48000
LEAD = 0.6
ses, kj = sys.argv[1], sys.argv[2]
W = json.load(open(kj, encoding="utf-8"))
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", ses, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
x = np.frombuffer(raw, np.float32).reshape(-1, 2)

# bolum basliklarindan once gelen kelime indeksleri
cut_idx = []; wi = 0
for text, sc, para, purpose in SEG:
    if not text:
        if wi > 0:
            cut_idx.append(wi)          # wi = bolumden sonraki ilk kelime
        continue
    wi += len(re.findall(r"[^\s]+", text))

ins = []   # (orijinal zaman, eklenecek sure)
for i in cut_idx:
    gap = W[i]["s"] - W[i - 1]["e"]
    need = CH_DUR + 0.6 - gap
    if need > 0:
        ins.append((W[i - 1]["e"] + gap * 0.5, need))

parts = [np.zeros((int(LEAD * SR), 2), np.float32)]; last = 0
for t, add in ins:
    k = int(t * SR); parts += [x[last:k], np.zeros((int(add * SR), 2), np.float32)]; last = k
parts.append(x[last:])
y = np.concatenate(parts)


def shift(t):
    return round(t + LEAD + sum(a for tt, a in ins if tt <= t), 3)


W2 = [dict(w, s=shift(w["s"]), e=shift(w["e"])) for w in W]
json.dump(W2, open("audio/kelimeler.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "audio/anlatim.wav"], input=y.tobytes())
print(f"{len(ins)} bolum araligi eklendi (+{sum(a for _, a in ins):.2f} sn), anlatim {len(y) / SR:.2f} sn")
