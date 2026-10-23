"""Metin-ses hizalama (internet / model gerektirmez).
Bilinen senaryo + temiz anlatim (ElevenLabs) icin kelime zamanlari uretir.

Yontem:
 1. Ses 16 kHz mono, 10 ms enerji zarfi (dBFS); konusma / sessizlik ayrimi
 2. Sessizlik araliklari (>= 90 ms) aday sinirlar
 3. Noktalama sonlari (. ? ! : ; ,) hece oranli tahmini zamanlarla sessizliklere
    dinamik programlama ile esler (cumle sonlari uzun sessizlige guclu baglanir)
 4. Iki capa arasindaki kelimeler, yalnizca sesli karelere hece agirligiyla dagitilir
Dogruluk: cumle/virgul sinirlarinda ~30 ms, cumle icinde ~100-200 ms (altyazi icin yeterli).

Kullanim: python hizala.py ses.mp3 metin.txt cikti.json
Cikti: [{"w": kelime, "s": baslangic, "e": bitis}, ...] (metindeki sirayla, her kelime bir kez)
"""
import sys, json, re, subprocess, math
import numpy as np

V = set("aeıioöuüâîûAEIİOÖUÜÂÎÛ")


def hece(w):
    n = sum(1 for c in w if c in V)
    if re.search(r"\d", w):
        n = max(n, 2 * len(re.sub(r"\D", "", w)))
    return max(1, n)


def zarf(ses, sr=16000, hop=0.01):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", ses, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    h = int(sr * hop); n = len(x) // h
    fr = x[:n * h].reshape(n, h)
    db = 10 * np.log10((fr ** 2).mean(1) + 1e-10)
    return db, hop, len(x) / sr


def sessizlikler(db, hop, min_sn=0.09):
    ref = np.percentile(db, 95)
    sil = db < max(ref - 18, -50)   # ElevenLabs: zemin ~-70 dB, konusma ~-30 dB
    out = []; i = 0; n = len(sil)
    while i < n:
        if sil[i]:
            j = i
            while j < n and sil[j]:
                j += 1
            if (j - i) * hop >= min_sn:
                out.append((i * hop, j * hop))
            i = j
        else:
            i += 1
    return out, ~sil


def _dp(P, ends, S, w_pen, s_pen, dist_k=0.6):
    """P: capa kelime indeksleri, ends: tahmini bitis zamanlari, S: sessizlikler. Monoton esleme."""
    nP, nS = len(P), len(S)
    D = np.full((nP + 1, nS + 1), 1e9); B = np.zeros((nP + 1, nS + 1), np.int8); D[0, 0] = 0
    for j in range(1, nS + 1):
        D[0, j] = D[0, j - 1] + s_pen(S[j - 1])
    for k in range(1, nP + 1):
        D[k, 0] = D[k - 1, 0] + w_pen(P[k - 1])
        for j in range(1, nS + 1):
            cm = D[k - 1, j - 1] + abs(ends[k - 1] - S[j - 1][0]) * dist_k
            cp = D[k - 1, j] + w_pen(P[k - 1]); cs = D[k, j - 1] + s_pen(S[j - 1])
            m = min(cm, cp, cs); D[k, j] = m; B[k, j] = 0 if m == cm else (1 if m == cp else 2)
    k, j = nP, nS; out = {}
    while k > 0 and j > 0:
        if B[k, j] == 0:
            out[P[k - 1]] = S[j - 1]; k -= 1; j -= 1
        elif B[k, j] == 1:
            k -= 1
        else:
            j -= 1
    return out


def _tahmin(idx, wts, pw, t0, t1):
    """idx kelimeleri icin [t0,t1] araliginda hece+duraklama oranli bitis tahmini."""
    tot = sum(wts[i] + pw[i] for i in idx) or 1
    sc = (t1 - t0) / tot; acc = t0; e = {}
    for i in idx:
        acc += wts[i] * sc; e[i] = acc; acc += pw[i] * sc
    return e


def hizala(ses, metin):
    toks = re.findall(r"[^\s]+", metin)
    db, hop, dur = zarf(ses)
    sils, voiced = sessizlikler(db, hop, 0.06)
    sp0 = sils[0][1] if sils and sils[0][0] < 0.05 else 0.0
    sp1 = sils[-1][0] if sils and sils[-1][1] > dur - 0.05 else dur
    inner = [s for s in sils if s[0] > sp0 + 0.05 and s[1] < sp1 - 0.05]
    wts = [hece(t) + 0.4 for t in toks]
    SE = lambda t: t.endswith((".", "?", "!", "...", ":", '."', '?"', '!"', ':"'))
    pw = [2.4 if SE(t) else (0.8 if t.endswith((",", ";", ',"')) else 0.0) for t in toks]
    # 1) cumle sonlari -> sessizlikler; cumle suresi / hece orani tutarliligiyla DP (her cumle sonu bir sessizlige)
    cand = [s for s in inner if s[1] - s[0] >= 0.1]
    P = [i for i, t in enumerate(toks) if SE(t) and i < len(toks) - 1]
    rate = (sp1 - sp0) / sum(wts[i] + pw[i] * 0.0 for i in range(len(toks)))
    rate *= 0.8   # duraklamalar haric konusma payi
    syl = []; prev = -1
    for a in P + [len(toks) - 1]:
        syl.append(sum(wts[prev + 1:a + 1])); prev = a
    nP, nS = len(P), len(cand)
    starts = [sp0] + [c[1] for c in cand]          # j=0: konusma basi
    INF = 1e18
    D = np.full((nP + 1, nS + 1), INF); Bk = np.full((nP + 1, nS + 1), -1, np.int32); D[0, 0] = 0.0
    def seg_cost(k, jp, j_end_t, jj=None):
        d = j_end_t - starts[jp]
        if d <= 0.2:
            return INF
        e = syl[k] * rate
        c = abs(math.log(d / e)) * 4.0
        return c
    for k in range(1, nP + 1):
        for j in range(k, nS + 1):
            t_end = cand[j - 1][0]
            best = INF; bj = -1
            lo = max(k - 1, j - 25)
            for jp in range(lo, j):
                if D[k - 1, jp] >= INF:
                    continue
                c = D[k - 1, jp] + seg_cost(k - 1, jp, t_end)
                # aradaki atlanan uzun sessizlikler cezasi
                for q in range(jp, j - 1):
                    L = cand[q][1] - cand[q][0]
                    if L > 0.3:
                        c += (L - 0.3) * 6
                if c < best:
                    best, bj = c, jp
            L = cand[j - 1][1] - cand[j - 1][0]
            D[k, j] = best - min(L, 0.7) * 1.5; Bk[k, j] = bj
    # son cumle: kalan sure
    fin = [(D[nP, j] + (seg_cost(nP, j, sp1) if D[nP, j] < INF else INF), j) for j in range(nP, nS + 1)]
    _, j = min(fin)
    A = {}
    for k in range(nP, 0, -1):
        A[P[k - 1]] = cand[j - 1]; j = Bk[k, j]
    # 2) her cumle icinde virguller -> yakin sessizlikler (>= 0.07 sn, +-0.4 sn)
    cuts = sorted(A); bounds = []; prev, t0 = -1, sp0
    for a in cuts + [len(toks) - 1]:
        t1 = A[a][0] if a in A else sp1
        idx = list(range(prev + 1, a + 1))
        e = _tahmin(idx, wts, pw, t0, t1)
        C = [i for i in idx[:-1] if pw[i] > 0]
        Sl = [s for s in inner if t0 < s[0] < t1 - 0.05]
        if C and Sl:
            B2 = _dp(C, [e[i] for i in C], Sl, lambda i: 0.35, lambda s: 0.12 + max(0, (s[1] - s[0]) - 0.25) * 2, 1.0)
            for c, sv in B2.items():
                if abs(e[c] - sv[0]) < 0.45:
                    A[c] = sv
        if a in A:
            prev, t0 = a, A[a][1]
        else:
            prev = a
    # 3) capalar arasi dagitim (sesli karelere hece agirligiyla)
    cuts = sorted(A)
    regions = []; wi = 0; t0 = sp0
    for a in cuts:
        regions.append((wi, a, t0, A[a][0])); wi = a + 1; t0 = A[a][1]
    regions.append((wi, len(toks) - 1, t0, sp1))
    out = [None] * len(toks)
    vc = np.cumsum(voiced.astype(np.float64)) * hop
    for a, b, ta, tb in regions:
        if a > b:
            continue
        ia = int(ta / hop); ib = min(max(ia + 1, int(tb / hop)), len(vc) - 1)
        v0, v1 = vc[ia], vc[ib]
        ws = wts[a:b + 1]; tw = sum(ws)
        def at(vt):
            idx = int(np.searchsorted(vc[ia:ib + 1], vt)) + ia
            return min(idx * hop, tb)
        cum = 0
        for k2, w in enumerate(ws):
            s_ = at(v0 + (v1 - v0) * cum / tw); cum += w
            e_ = at(v0 + (v1 - v0) * cum / tw)
            out[a + k2] = {"w": toks[a + k2], "s": round(max(s_, ta), 3), "e": round(max(e_, s_ + 0.05), 3)}
    return out, {"sure": round(dur, 2), "cumle_capa": len([c for c in A if SE(toks[c])]), "cumle": len(P), "toplam_capa": len(A)}


if __name__ == "__main__":
    words, info = hizala(sys.argv[1], open(sys.argv[2], encoding="utf-8").read())
    json.dump(words, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(info)
