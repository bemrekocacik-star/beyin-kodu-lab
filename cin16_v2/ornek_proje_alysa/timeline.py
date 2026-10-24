"""Ses zaman çizelgesi: anlatıma bölüm kartı / nefes araları ekler; kelime zamanlarını final zamana taşır."""
import json, re, subprocess
W = json.load(open('kelimeler.json'))
seg = []; cur = []
for i, w in enumerate(W):
    cur.append(i)
    if re.search(r'[.!?:]$', w['w']): seg.append(cur); cur = []
S0 = lambda k: W[seg[k][0]]['s']; S1 = lambda k: W[seg[k][-1]]['e']
# (ses zamanı, süre, tür, ad)
INS = [
    ((S1(3) + S0(4)) / 2, 1.6, 'pause', 'birak'),
    ((S1(14) + S0(15)) / 2, 5.0, 'title', 'baslik'),
    ((S1(14) + S0(15)) / 2 + 0.001, 5.5, 'chapter', '1'),
    ((S1(31) + S0(32)) / 2, 1.2, 'pause', 'kazandi'),
    ((S1(44) + S0(45)) / 2, 6.0, 'chapter', '2'),
    ((S1(67) + S0(68)) / 2, 6.0, 'chapter', '3'),
    ((S1(86) + S0(87)) / 2, 6.0, 'chapter', '4'),
    ((S1(106) + S0(107)) / 2, 1.5, 'pause', 'kendim'),
    ((S1(117) + S0(118)) / 2, 6.0, 'chapter', '5'),
    ((S1(143) + S0(144)) / 2, 5.0, 'moment', 'sampiyon'),
    ((S1(146) + S0(147)) / 2, 6.0, 'chapter', '6'),
]
VOICE_END = 438.126
END_SCREEN = 20.0
def f(t):
    """ses zamanı -> final zaman"""
    return t + sum(d for p, d, _, _ in INS if p <= t)
inserts_final = []
for p, d, k, n in INS:
    st = f(p) - d  # eklemenin final başlangıcı
    inserts_final.append({'voice_t': p, 'start': round(st, 3), 'dur': d, 'kind': k, 'name': n})
TOTAL = f(VOICE_END) + END_SCREEN
Wf = [{'w': w['w'], 's': round(f(w['s']), 3), 'e': round(f(w['e']), 3)} for w in W]
json.dump({'inserts': inserts_final, 'total': round(TOTAL, 3), 'voice_end_final': round(f(VOICE_END), 3),
           'sent': [{'k': k, 's': round(f(S0(k)), 3), 'e': round(f(S1(k)), 3), 'txt': ' '.join(W[i]['w'] for i in s)} for k, s in enumerate(seg)]},
          open('tl.json', 'w'), ensure_ascii=False, indent=1)
json.dump(Wf, open('kelimeler_final.json', 'w'), ensure_ascii=False)
# anlatım izini sessizlik ekleyerek kur
cuts = sorted(set(round(p, 3) for p, _, _, _ in INS))
parts = []; prev = 0.0
fc = []; inputs = []
for i, c in enumerate(cuts):
    fc.append(f"[i{i}]atrim={prev}:{c},asetpts=PTS-STARTPTS[a{i}]")
    d = sum(dd for p, dd, _, _ in INS if round(p, 3) == c)
    fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{d}[s{i}]")
    parts += [f"[a{i}]", f"[s{i}]"]; prev = c
n = len(cuts)
fc.append(f"[i{n}]atrim={prev},asetpts=PTS-STARTPTS[a{n}]"); parts.append(f"[a{n}]")
fc.insert(0, "[0:a]aresample=48000,aformat=channel_layouts=mono,asplit=" + str(n + 1) + "".join(f"[i{k}]" for k in range(n + 1)))
fc.append(f"anullsrc=r=48000:cl=mono,atrim=0:{END_SCREEN}[send]"); parts.append("[send]")
fc.append("".join(parts) + f"concat=n={len(parts)}:v=0:a=1[o]")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", "anlatim.mp3", "-filter_complex", ";".join(fc),
                "-map", "[o]", "-ar", "48000", "-ac", "1", "anlatim_tl.wav"], check=True)
print('toplam', round(TOTAL, 2), 'sn =', int(TOTAL // 60), 'dk', round(TOTAL % 60, 1), 'sn')
