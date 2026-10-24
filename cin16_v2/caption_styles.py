#!/usr/bin/env python3
"""Beyin Kodu Lab altyazı stil kütüphanesi (ASS / libass).
Girdi JSON: [{"w": "Ronaldo", "s": 0.10, "e": 0.52}, ...]   (saniye)
Kullanım: python3 /root/tools/caption_styles.py kelimeler.json cikti.ass --fmt 9x16 --style klasik
Stiller: klasik (varsayılan 9:16), hormozi, karaoke, renkli, sinematik, belgesel (varsayılan 16:9).
"""
import argparse, json, re, sys
from PIL import ImageFont

FONTS = {
    "Inter ExtraBold": "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
    "Inter Black": "/usr/share/fonts/opentype/inter/Inter-Black.otf",
    "Inter SemiBold": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "Poppins": "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "Lora": "/usr/share/fonts/truetype/google-fonts/Lora-Variable.ttf",
}

LAYOUT = {
    "9x16": dict(W=1080, H=1920, x=540, y=1335, an=5, maxw=744),
    "16x9": dict(W=1920, H=1080, x=960, y=985, an=2, maxw=1500),
}

YELLOW, WHITE, BLACK = "&H0000D4FF&", "&H00FFFFFF&", "&H00000000&"
GREEN, RED = "&H0050E04A&", "&H004040FF&"
PALETTE = ["&H0000D4FF&", "&H0050E04A&", "&H00F0D020&", "&H00208CFF&"]

MONEY = re.compile(r"(\d|₺|\$|€|milyon|milyar|bin\b|zengin|servet|para|dolar|lira|kazan|başar|zirve|şampiyon|altın|rekor|nobel|birincilik)", re.I)
FAIL = re.compile(r"(reddedil|başarısız|iflas|kaybet|kovul|yıkıl|hayır|imkânsız|imkansız|bıraktı|düştü|yenil|hata|bilmiyordu|hasar)", re.I)

STYLES = {
    "klasik":    dict(font="Inter ExtraBold", size=70, outline=6, shadow=0, maxwords=3, maxchars=19, upper=False, mode="highlight"),
    "hormozi":   dict(font="Inter Black", size=92, outline=7, shadow=3, maxwords=2, maxchars=14, upper=True, mode="pop"),
    "karaoke":   dict(font="Inter ExtraBold", size=62, outline=5, shadow=0, maxwords=5, maxchars=28, upper=False, mode="karaoke"),
    "renkli":    dict(font="Poppins", size=78, outline=8, shadow=2, maxwords=2, maxchars=16, upper=False, mode="color"),
    "sinematik": dict(font="Lora", size=58, outline=2, shadow=2, maxwords=12, maxchars=60, upper=False, mode="sentence"),
    "belgesel":  dict(font="Inter SemiBold", size=56, outline=4, shadow=1, maxwords=8, maxchars=48, upper=False, mode="highlight"),
}
SIZE_16x9 = {"klasik": 66, "hormozi": 84, "karaoke": 58, "renkli": 70, "sinematik": 52, "belgesel": 56}


def tr_upper(s):
    return s.replace("i", "İ").replace("ı", "I").upper()


def ts(t):
    t = max(t, 0)
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def chunk(words, maxwords, maxchars, sentence_mode=False):
    out, cur = [], []
    for i, w in enumerate(words):
        txt = " ".join(x["w"] for x in cur + [w])
        if cur and (len(cur) >= maxwords or len(txt) > maxchars):
            out.append(cur); cur = []
        cur.append(w)
        end_punct = re.search(r"[.!?…]$", w["w"]) or (not sentence_mode and re.search(r"[,:;]$", w["w"]))
        gap = i + 1 < len(words) and words[i + 1]["s"] - w["e"] > 0.45
        if end_punct or gap:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    merged = []
    for c in out:
        if merged and len(c) == 1 and len(merged[-1]) < maxwords + 1 and \
           len(" ".join(x["w"] for x in merged[-1] + c)) <= maxchars and \
           not re.search(r"[.!?…]$", merged[-1][-1]["w"]) and c[0]["s"] - merged[-1][-1]["e"] < 0.3:
            merged[-1] += c
        else:
            merged.append(c)
    return merged


def fit_size(chunks, st, maxw, upper):
    size = st["size"]
    path = FONTS[st["font"]]
    while size > 30:
        f = ImageFont.truetype(path, size)
        widest = max(f.getlength(tr_upper(" ".join(x["w"] for x in c)) if upper else " ".join(x["w"] for x in c)) for c in chunks)
        if widest + 2 * st["outline"] <= maxw * (2 if st["mode"] in ("sentence",) or st["maxwords"] >= 8 else 1):
            return size
        size -= 2
    return size


def kw_color(word, use_kw):
    if not use_kw:
        return None
    if FAIL.search(word):
        return RED
    if MONEY.search(word):
        return GREEN
    return None


def build(words, fmt="9x16", style="klasik", use_kw=True, offset=0.0):
    L = LAYOUT[fmt]
    st = dict(STYLES[style])
    if fmt == "16x9":
        st["size"] = SIZE_16x9[style]
    chunks = chunk(words, st["maxwords"], st["maxchars"], st["mode"] == "sentence")
    size = fit_size(chunks, st, L["maxw"], st["upper"])
    if fmt == "9x16" and style == "hormozi":
        size = min(size, 84)
    wrap = 0 if st["maxwords"] >= 8 else 2
    bold = -1 if st["font"] in ("Poppins", "Lora") else 0
    prim, sec = (YELLOW, WHITE) if st["mode"] == "karaoke" else (WHITE, YELLOW)
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {L['W']}
PlayResY: {L['H']}
WrapStyle: {wrap}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st['font']},{size},{prim},{sec},{BLACK},&H96000000&,{bold},0,0,0,100,100,0,0,1,{st['outline']},{st['shadow']},{L['an']},60,60,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    pos = f"\\an{L['an']}\\pos({L['x']},{L['y']})"
    up = (lambda s: tr_upper(s)) if st["upper"] else (lambda s: s)
    for ci, c in enumerate(chunks):
        cs, ce = c[0]["s"] + offset, c[-1]["e"] + offset
        nxt = chunks[ci + 1][0]["s"] + offset if ci + 1 < len(chunks) else ce + 0.6
        ce = min(max(ce, cs + 0.35), nxt) if nxt > cs + 0.35 else ce
        if st["mode"] == "sentence":
            txt = " ".join(up(w["w"]) for w in c)
            ev.append(f"Dialogue: 0,{ts(cs)},{ts(ce + 0.25)},Cap,,0,0,0,,{{{pos}\\fad(220,220)}}{txt}")
            continue
        if st["mode"] == "karaoke":
            parts = []
            for i, w in enumerate(c):
                dur = ((c[i + 1]["s"] if i + 1 < len(c) else w["e"]) - w["s"]) * 100
                kc = kw_color(w["w"], use_kw)
                col = f"\\1c{kc}" if kc else "\\1c" + YELLOW
                parts.append(f"{{\\kf{max(int(dur), 1)}{col}}}{up(w['w'])} ")
            pre = f"{{\\kf{max(int((c[0]['s'] + offset - cs) * 100), 0)}}}"
            ev.append(f"Dialogue: 0,{ts(cs)},{ts(ce)},Cap,,0,0,0,,{{{pos}\\fad(80,60)}}{pre}{''.join(parts).rstrip()}")
            continue
        base_col = PALETTE[ci % len(PALETTE)] if st["mode"] == "color" else WHITE
        for i, w in enumerate(c):
            s = w["s"] + offset if i else cs
            e = (c[i + 1]["s"] + offset) if i + 1 < len(c) else ce
            toks = []
            for j, x in enumerate(c):
                kc = kw_color(x["w"], use_kw)
                if j == i:
                    if st["mode"] == "pop":
                        act = kc or (GREEN if ci % 2 else YELLOW)
                    elif st["mode"] == "color":
                        act = kc or WHITE
                    else:
                        act = kc or YELLOW
                    if i == 0:
                        toks.append(f"{{\\c{act}}}{up(x['w'])}")
                    else:
                        grow = "\\t(0,90,\\fscx112\\fscy112)\\t(90,180,\\fscx104\\fscy104)" if st["mode"] != "pop" else "\\fscx106\\fscy106"
                        toks.append(f"{{\\c{act}\\fscx100\\fscy100{grow}}}{up(x['w'])}{{\\fscx100\\fscy100}}")
                else:
                    col = (kc if kc and j < i else base_col) if st["mode"] != "pop" else (kc or WHITE)
                    toks.append(f"{{\\c{col}}}{up(x['w'])}")
            intro = ""
            if i == 0:
                if st["mode"] == "pop":
                    intro = "\\fscx70\\fscy70\\t(0,110,\\fscx108\\fscy108)\\t(110,190,\\fscx100\\fscy100)"
                elif st["mode"] == "color":
                    intro = "\\frz-4\\fscx85\\fscy85\\t(0,120,\\frz2\\fscx105\\fscy105)\\t(120,220,\\frz0\\fscx100\\fscy100)"
                else:
                    intro = "\\fad(70,0)"
            ev.append(f"Dialogue: 0,{ts(s)},{ts(e)},Cap,,0,0,0,,{{{pos}{intro}}}{' '.join(toks)}")
    return hdr + "\n".join(ev) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("words", nargs="?"); ap.add_argument("out", nargs="?")
    ap.add_argument("--fmt", default="9x16", choices=list(LAYOUT))
    ap.add_argument("--style", default="klasik", choices=list(STYLES))
    ap.add_argument("--no-keywords", action="store_true")
    ap.add_argument("--offset", type=float, default=0.0)
    a = ap.parse_args()
    if not a.words:
        print(__doc__); sys.exit(0)
    words = json.load(open(a.words, encoding="utf-8"))
    open(a.out, "w", encoding="utf-8").write(build(words, a.fmt, a.style, not a.no_keywords, a.offset))
    print("yazıldı:", a.out)
