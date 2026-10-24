#!/usr/bin/env python3
"""Beyin Kodu Lab CIN16 — 16:9 belgesel motoru (bulut sürümü, 24 Ekim 2026).
Kullanım: cin16.py plan.json t0 t1 cikti.mp4 [--scale 0.5]
plan.json: {"fps":24,"total":S,"scenes":[{"start","end","base":{...},"els":[...]}], "xfade":0.35}
base türleri: photo{photo,mode:cover|fit,px,focus,z0,z1,dx,dy,tone,credit} · split{photos:[a,b],labels} · bg{} · chapter{n,title} · title{t,sub,photo} · end{}
els: text · pill · stamp · counter · lower · loc · emoji · rotation · scoreboard · checklist · timeline · phone · headline · tag · bars · quote
"""
import json, math, random, subprocess, sys, functools
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter, ImageFont

plan = json.load(open(sys.argv[1])); T0, T1 = float(sys.argv[2]), float(sys.argv[3]); OUT = sys.argv[4]
SC = float(sys.argv[sys.argv.index('--scale') + 1]) if '--scale' in sys.argv else 1.0
FPS = plan.get('fps', 24); W, H = int(1920 * SC), int(1080 * SC); XF = plan.get('xfade', 0.35)
NAVY = (11, 21, 48); YEL = (255, 212, 0); RED = (229, 57, 53); GRN = (46, 204, 113); WHITE = (255, 255, 255); GREY = (170, 180, 200)
COL = {'w': WHITE, 'y': YEL, 'r': RED, 'g': GRN, 'gr': GREY, 'n': NAVY}
FD = '/usr/share/fonts/opentype/inter/'; FB, FX, FS = FD + 'Inter-Black.otf', FD + 'Inter-ExtraBold.otf', FD + 'Inter-SemiBold.otf'
FQ = '/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf'; FE = '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf'
FONTS = {'B': FB, 'X': FX, 'S': FS, 'Q': FQ}

def P(v): return v * SC
@functools.lru_cache(None)
def font(path, size): return ImageFont.truetype(path, max(8, int(size * SC)))
def ease(x): x = min(max(x, 0), 1); return 0.5 - 0.5 * math.cos(math.pi * x)
def oc(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 3
def ob(x, s=1.5): x = min(max(x, 0), 1) - 1; return 1 + (s + 1) * x ** 3 + s * x ** 2

# ---------- ortak katmanlar ----------
rng = np.random.default_rng(7)
GRAIN = [(rng.normal(0, 6.0, (H // 2, W // 2)).astype(np.float32)) for _ in range(6)]
GRAIN = [cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)[:, :, None] for g in GRAIN]
yy, xx = np.mgrid[0:H, 0:W]; r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
VIG = (1 - 0.32 * np.clip(r - 0.55, 0, 1) ** 1.6)[:, :, None].astype(np.float32)

@functools.lru_cache(None)
def ice_bg(seed=0):
    g = np.linspace(0, 1, H)[:, None]
    top = np.array([18, 30, 66]); bot = np.array([5, 9, 24])
    a = (top * (1 - g) + bot * g)[:, None, :].repeat(W, 1).astype(np.float32)
    im = Image.fromarray(a.astype(np.uint8)).convert('RGBA'); gl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(gl)
    rr = random.Random(seed)
    for _ in range(14):
        x, y, rad = rr.uniform(0, W), rr.uniform(0, H), rr.uniform(P(60), P(260))
        d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=(90, 140, 230, rr.randint(10, 26)))
    d.ellipse((W * 0.2, H * 0.1, W * 0.8, H * 0.9), fill=(60, 100, 200, 30))
    im.alpha_composite(gl.filter(ImageFilter.GaussianBlur(P(90))))
    return np.asarray(im.convert('RGB')).astype(np.float32)

SNOW = [(random.Random(i).uniform(0, 1), random.Random(i * 7).uniform(0, 1), random.Random(i * 13).uniform(0.6, 2.4), random.Random(i * 3).uniform(0.02, 0.07)) for i in range(70)]
def snow(img, t, a=1.0):
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for x0, y0, s, sp in SNOW:
        x = (x0 * W + math.sin(t * 0.6 + y0 * 9) * P(20)) % W; y = ((y0 + sp * t) % 1) * H; rad = P(s)
        d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=(220, 235, 255, int(110 * a)))
    img.alpha_composite(ov)

# ---------- metin ----------
@functools.lru_cache(4096)
def text_img(t, fk, size, col, shadow=True, stroke=0, maxw=0):
    f = font(FONTS.get(fk, FB), size)
    if maxw:
        while f.getlength(t) > P(maxw) and f.size > 14: f = ImageFont.truetype(FONTS.get(fk, FB), f.size - 2)
    w = int(f.getlength(t)) + int(P(60)); h = int(f.size * 1.45) + int(P(30))
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ImageDraw.Draw(sh).text((w / 2, h / 2 + P(4)), t, font=f, fill=(0, 0, 0, 200), anchor='mm', stroke_width=int(P(stroke)), stroke_fill=(0, 0, 0))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(P(8))))
    ImageDraw.Draw(im).text((w / 2, h / 2), t, font=f, fill=COL.get(col, col) if isinstance(col, str) else tuple(col), anchor='mm', stroke_width=int(P(stroke)), stroke_fill=(0, 0, 0))
    return im
@functools.lru_cache(512)
def emoji_img(ch, size):
    im = Image.new('RGBA', (160, 160), (0, 0, 0, 0)); ImageDraw.Draw(im).text((80, 80), ch, font=ImageFont.truetype(FE, 109), embedded_color=True, anchor='mm')
    im = im.crop(im.getbbox()); s = P(size) / max(im.size)
    return im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS)
def alpha(im, a):
    if a >= 0.999: return im
    im = im.copy(); im.putalpha(im.getchannel('A').point(lambda v: int(v * max(0, a)))); return im
def put(dst, im, x, y, anchor='mm', a=1.0, s=1.0):
    if a <= 0.003: return
    if abs(s - 1) > 0.002: im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.BILINEAR)
    im = alpha(im, a); w, h = im.size
    ox = {'l': 0, 'm': w / 2, 'r': w}[anchor[0]]; oy = {'t': 0, 'm': h / 2, 'b': h}[anchor[1]]
    dst.alpha_composite(im, (int(P(x) - ox), int(P(y) - oy)))
@functools.lru_cache(256)
def pill_img(t, bg, fg, size=40, fk='B'):
    f = font(FONTS[fk], size); w = int(f.getlength(t) + P(size * 1.4)); h = int(P(size * 1.75))
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), h // 2, fill=tuple(COL.get(bg, bg)) if isinstance(bg, str) else tuple(bg))
    d.text((w / 2, h / 2 + 1), t, font=f, fill=COL.get(fg, fg), anchor='mm'); return im
@functools.lru_cache(64)
def stamp_img(t, kind):
    c = RED if kind == 'no' else (GRN if kind == 'ok' else YEL); f = font(FB, 76)
    w = int(f.getlength(t) + P(90)); h = int(P(130)); im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((P(6), P(6), w - P(7), h - P(7)), int(P(16)), fill=(0, 0, 0, 110), outline=c + (255,), width=int(P(9)))
    d.text((w / 2, h / 2 + 2), t, font=f, fill=c + (255,), anchor='mm'); return im.rotate(-6, expand=True, resample=Image.BICUBIC)

# ---------- fotoğraf ----------
@functools.lru_cache(16)
def load_photo(path, tone):
    im = cv2.imread(path, cv2.IMREAD_COLOR)[:, :, ::-1].astype(np.float32)
    if tone == 'bw': g = im.mean(2, keepdims=True); im = np.repeat(g, 3, 2)
    elif tone == 'dim': im = im * 0.62
    elif tone == 'cold': im = im * np.array([0.88, 0.96, 1.08]); im = im * 0.8
    elif tone == 'warm': im = im * np.array([1.06, 1.0, 0.9])
    im = np.clip(im, 0, 255)
    # hafif sinematik renk: siyahları mavimsi, kontrast
    im = np.clip((im - 128) * 1.06 + 128 + np.array([-2, 0, 6]), 0, 255)
    return im
def warp(src, out_w, out_h, cx, cy, scale):
    """src içinde (cx,cy) merkezli, scale ile out boyuta ölçekle."""
    M = np.array([[scale, 0, out_w / 2 - cx * scale], [0, scale, out_h / 2 - cy * scale]], np.float32)
    return cv2.warpAffine(src, M, (out_w, out_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
@functools.lru_cache(16)
def blurred(path, tone):
    im = load_photo(path, tone); h, w = im.shape[:2]; s = 480 / max(h, w)
    sm = cv2.resize(im, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    sm = cv2.GaussianBlur(sm, (0, 0), 14); return sm * 0.5 + np.array(NAVY, np.float32) * 0.5
def photo_frame(b, p):
    im = load_photo(b['photo'], b.get('tone', 'n')); h, w = im.shape[:2]
    e = ease(p); z = b.get('z0', 1.0) + (b.get('z1', 1.08) - b.get('z0', 1.0)) * e
    fx, fy = b.get('focus', [0.5, 0.42]); dx = b.get('dx', 0) * (e - 0.5); dy = b.get('dy', 0) * (e - 0.5)
    mode = b.get('mode', 'cover' if w / h > 1.2 else 'fit')
    if mode == 'cover':
        s0 = max(W / w, H / h) * z
        cx = fx * w + dx * w; cy = fy * h + dy * h
        cx = min(max(cx, W / s0 / 2), w - W / s0 / 2); cy = min(max(cy, H / s0 / 2), h - H / s0 / 2)
        return warp(im, W, H, cx, cy, s0)
    # fit: bulanık zemin + çerçeveli foto (2.5D: zemin yavaş, foto hızlı)
    bg = blurred(b['photo'], b.get('tone', 'n')); bh, bw = bg.shape[:2]
    sb = max(W / bw, H / bh) * (1.08 + 0.03 * e)
    frame = warp(bg, W, H, bw / 2 - dx * bw * 0.3, bh / 2, sb)
    ph = P(b.get('ph', 940)); s1 = ph / h * z; pw = w * s1
    cxs = P(b.get('px', 0.5) * 1920) + dx * P(120)
    fg = cv2.resize(im, (max(1, int(pw)), max(1, int(ph * z))), interpolation=cv2.INTER_AREA)
    # kenar gölgesi
    y0 = int(H / 2 - fg.shape[0] / 2 + dy * P(60)); x0 = int(cxs - fg.shape[1] / 2)
    sh = np.zeros((H, W), np.float32); cv2.rectangle(sh, (x0 + int(P(10)), y0 + int(P(18))), (x0 + fg.shape[1] + int(P(10)), y0 + fg.shape[0] + int(P(18))), 1.0, -1)
    sh = cv2.GaussianBlur(sh, (0, 0), P(22)); frame = frame * (1 - 0.6 * sh[:, :, None])
    ys, xs = max(0, y0), max(0, x0); ye, xe = min(H, y0 + fg.shape[0]), min(W, x0 + fg.shape[1])
    if ye > ys and xe > xs: frame[ys:ye, xs:xe] = fg[ys - y0:ye - y0, xs - x0:xe - x0]
    return frame

# ---------- sahneler ----------
VR = {}
def video_frame(b, t, p):
    path = b['video']; cap, fps, last, fr = VR.get(path, (None, 25.0, -1, None))
    if cap is None:
        cap = cv2.VideoCapture(path); fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    want = int((b.get('off', 0) + t * b.get('speed', 1.0)) * fps)
    if want < last or fr is None:
        cap.set(cv2.CAP_PROP_POS_FRAMES, want); ok, fr = cap.read(); last = want
    while last < want:
        ok, f2 = cap.read()
        if not ok: break
        fr = f2; last += 1
    VR[path] = (cap, fps, last, fr)
    im = fr[:, :, ::-1].astype(np.float32); h, w = im.shape[:2]
    z = b.get('z0', 1.04) + (b.get('z1', 1.10) - b.get('z0', 1.04)) * ease(p); s0 = max(W / w, H / h) * z
    out = warp(im, W, H, w / 2 + b.get('dx', 0) * w * (ease(p) - 0.5), h / 2, s0)
    if b.get('tone') == 'bw': out = np.repeat(out.mean(2, keepdims=True), 3, 2)
    out = np.clip((out - 128) * 1.05 + 128 + np.array([-4, 0, 8]), 0, 255)
    return out * b.get('vdark', 1.0)
def base_frame(sc, t, p):
    b = sc['base']; k = b.get('k', 'photo')
    if k == 'photo': return photo_frame(b, p)
    if k == 'video': return video_frame(b, t, p)
    if k == 'split':
        fr = ice_bg(3).copy()
        for i, ph in enumerate(b['photos']):
            im = load_photo(ph, 'n'); h, w = im.shape[:2]; tw, th = int(P(760)), int(P(820))
            s = max(tw / w, th / h) * (1.0 + 0.05 * ease(p)); fx, fy = b.get('focus', [[0.5, 0.35], [0.5, 0.35]])[i]
            tile = warp(im, tw, th, min(max(fx * w, tw / s / 2), w - tw / s / 2), min(max(fy * h, th / s / 2), h - th / s / 2), s)
            x0 = int(P(150 + i * 860)); y0 = int(P(150))
            fr[y0:y0 + th, x0:x0 + tw] = tile
        return fr
    return ice_bg(b.get('seed', 1)).copy()

def tup(v):
    if isinstance(v, list): return tuple(tup(x) for x in v)
    return v
def colr(c): c = tup(c); return tuple(COL.get(c, c)) if isinstance(c, str) else c
def draw_els(img, sc, t, p, dur):
    d = ImageDraw.Draw(img)
    for e in sc.get('els', []):
        e = {kk: tup(vv) for kk, vv in e.items()}
        k = e['k']; at = e.get('at', 0); un = e.get('until', 1e9)
        if t < at or t > un: continue
        q = oc((t - at) / e.get('fade', 0.45)); qo = 1 - oc((t - (un - 0.3)) / 0.3) if un < 1e8 else 1; a = q * qo
        if k in FX2: FX2[k](img, e, t, at, a, q, p, dur, sc); d = ImageDraw.Draw(img); continue
        if k == 'text':
            im = text_img(e['t'], e.get('f', 'B'), e.get('size', 72), e.get('col', 'w'), True, e.get('stroke', 0), e.get('maxw', 1700))
            if e.get('box'):
                bx = Image.new('RGBA', (im.size[0] + int(P(30)), im.size[1]), (8, 14, 34, int(170 * a))); put(img, bx, e.get('x', 960), e.get('y', 540) + 15 * (1 - q), e.get('anchor', 'mm'))
            put(img, im, e.get('x', 960) + e.get('slide', 0) * (1 - q), e.get('y', 540) + 15 * (1 - q), e.get('anchor', 'mm'), a)
        elif k == 'pill':
            put(img, pill_img(e['t'], e.get('bg', 'y'), e.get('fg', 'n'), e.get('size', 38)), e.get('x', 960), e.get('y', 120), e.get('anchor', 'mm'), a, 0.85 + 0.15 * q)
        elif k == 'stamp':
            s = 1.9 - 0.9 * oc((t - at) / 0.2); put(img, stamp_img(e['t'], e.get('kind', 'no')), e.get('x', 960), e.get('y', 540), 'mm', min(1, (t - at) * 6), s)
        elif k == 'counter':
            cd = e.get('dur', 1.6); v = e.get('from', 0) + (e['to'] - e.get('from', 0)) * oc((t - at) / cd)
            s = f"{v:.{e['dec']}f}".replace('.', ',') if e.get('dec') else f"{int(round(v)):,}".replace(',', '.')
            put(img, text_img(e.get('prefix', '') + s + e.get('suffix', ''), 'B', e.get('size', 200), e.get('col', 'y')), e.get('x', 960), e.get('y', 500), e.get('anchor', 'mm'), a)
        elif k == 'lower':
            x0, y0 = P(e.get('x', 90)), P(e.get('y', 90)); bar_w = P(8)
            d.rectangle((x0, y0, x0 + bar_w, y0 + P(104) * q), fill=YEL + (int(255 * a),))
            put(img, text_img(e['title'], 'B', e.get('size', 54), 'w', True), e.get('x', 90) + 22 - 40 * (1 - q), e.get('y', 90) + 30, 'lm', a)
            if e.get('sub'): put(img, text_img(e['sub'], 'S', 30, 'y', True), e.get('x', 90) + 24 - 40 * (1 - q), e.get('y', 90) + 82, 'lm', a)
        elif k == 'loc':
            cy = e.get('y', 520)
            put(img, emoji_img('📍', 110), 960, cy - 150, 'mm', a, 0.7 + 0.3 * ob((t - at) / 0.5))
            put(img, text_img(e['city'], 'B', e.get('size', 120), 'w'), 960, cy, 'mm', a)
            lw = P(520) * oc((t - at - 0.2) / 0.6); d.rectangle((P(960) - lw / 2, P(cy + 82), P(960) + lw / 2, P(cy + 88)), fill=YEL + (int(255 * a),))
            put(img, text_img(e['date'], 'X', 46, 'y'), 960, cy + 140, 'mm', min(a, oc((t - at - 0.35) / 0.4)))
        elif k == 'emoji':
            put(img, emoji_img(e['ch'], e.get('size', 120)), e['x'], e['y'], 'mm', a, 0.6 + 0.4 * ob((t - at) / 0.45))
        elif k == 'rotation':
            cx, cy, R = P(e.get('x', 960)), P(e.get('y', 470)), P(e.get('r', 230)); turns = e['turns']; prog = oc((t - at) / e.get('dur', 2.6))
            ang = turns * 360 * prog
            for i in range(int(math.ceil(turns))):
                rr = R - P(26) * i; seg = min(360, max(0, ang - 360 * i))
                if seg <= 0: break
                d.arc((cx - rr, cy - rr, cx + rr, cy + rr), -90, -90 + seg, fill=YEL + (230,), width=int(P(12)))
            th = math.radians(-90 + (ang % 360)); hx, hy = cx + (R) * math.cos(th), cy + R * math.sin(th)
            d.ellipse((hx - P(16), hy - P(16), hx + P(16), hy + P(16)), fill=WHITE + (255,))
            put(img, text_img(f"{turns * prog:.1f}".replace('.', ',').replace(',0', '') if prog < 1 else e['label'], 'B', 110, 'w'), e.get('x', 960), e.get('y', 470), 'mm', a)
            if e.get('sub'): put(img, text_img(e['sub'], 'X', 44, 'y'), e.get('x', 960), e.get('y', 470) + R / SC + 80, 'mm', a)
        elif k == 'scoreboard':
            rows = e['rows']; mx = max(r[1] for r in rows); mn = e.get('min', min(r[1] for r in rows) - 15)
            for i, (nm, sc_, cl) in enumerate(rows):
                ti = at + 0.35 * i; qq = oc((t - ti) / 0.9)
                if t < ti: continue
                y = P(e.get('y', 330) + i * 150); x0 = P(560); wmax = P(900)
                d.rounded_rectangle((x0, y, x0 + wmax, y + P(84)), int(P(14)), fill=(255, 255, 255, 30))
                d.rounded_rectangle((x0, y, x0 + wmax * qq * (sc_ - mn) / (mx - mn), y + P(84)), int(P(14)), fill=colr(cl) + (235,))
                put(img, text_img(f"{i + 1}. {nm}", 'X', 46, 'w'), 530, (y + P(42)) / SC, 'rm', qq)
                put(img, text_img(f"{sc_ * qq + (1 - qq) * mn:.2f}".replace('.', ','), 'B', 50, 'w'), 1480, (y + P(42)) / SC, 'lm', qq)
        elif k == 'checklist':
            for i, it in enumerate(e['items']):
                ti = at + e.get('gap', 0.6) * i
                if t < ti: continue
                qq = oc((t - ti) / 0.35); y = e.get('y', 400) + i * e.get('dy', 120)
                put(img, text_img(it, 'B', e.get('size', 66), 'w'), e.get('x', 760), y, 'lm', qq)
                put(img, text_img(e.get('mark', '✓'), 'B', 70, e.get('mcol', 'g')), e.get('x', 760) - 80, y, 'mm', qq, 0.6 + 0.4 * ob((t - ti) / 0.4))
        elif k == 'timeline':
            pts = e['pts']; x0, x1, y = 260, 1660, e.get('y', 560); prog = oc((t - at) / e.get('dur', 2.0))
            d.rectangle((P(x0), P(y - 3), P(x0 + (x1 - x0) * prog), P(y + 3)), fill=YEL + (255,))
            for i, (lab, val) in enumerate(pts):
                fx = i / (len(pts) - 1); x = x0 + (x1 - x0) * fx
                if prog + 1e-3 < fx: continue
                d.ellipse((P(x - 16), P(y - 16), P(x + 16), P(y + 16)), fill=YEL + (255,))
                put(img, text_img(val, 'B', 64, 'w'), x, y - 80, 'mm'); put(img, text_img(lab, 'S', 34, 'y'), x, y + 70, 'mm')
        elif k == 'phone':
            pw, ph = P(560), P(900); x0, y0 = P(e.get('x', 960)) - pw / 2, P(90 + 40 * (1 - q))
            ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
            od.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), int(P(60)), fill=(15, 18, 28, int(250 * a)), outline=(90, 100, 130, int(255 * a)), width=int(P(6)))
            od.rounded_rectangle((x0 + P(28), y0 + P(260), x0 + pw - P(28), y0 + P(560)), int(P(26)), fill=(255, 255, 255, int(240 * a)))
            img.alpha_composite(ov)
            put(img, text_img(e.get('who', '@alysaliu'), 'X', 32, (40, 40, 60), False), e.get('x', 960) - 230, 90 + 300, 'lm', a)
            for i, ln in enumerate(e['lines']): put(img, text_img(ln, 'X', 46, (20, 24, 40), False), e.get('x', 960) - 230, 90 + 380 + i * 64, 'lm', a)
            put(img, text_img(e.get('tag', 'TEMSİLİ CANLANDIRMA'), 'S', 24, 'gr', False), e.get('x', 960), 90 + 860, 'mm', a)
        elif k == 'headline':
            pw, ph = P(1300), P(640); x0, y0 = P(310), P(180 + 30 * (1 - q)); rot = e.get('rot', -2)
            pg = Image.new('RGBA', (int(pw), int(ph)), (236, 230, 214, 255)); pd = ImageDraw.Draw(pg)
            pd.text((pw / 2, P(60)), e.get('paper', 'SPOR GÜNDEMİ'), font=font(FQ, 56), fill=(40, 40, 40), anchor='mm')
            pd.line((P(40), P(110), pw - P(40), P(110)), fill=(40, 40, 40), width=int(P(4)))
            pd.text((pw / 2, P(250)), e['t'], font=font(FB, 92), fill=(20, 20, 20), anchor='mm')
            if e.get('sub'): pd.text((pw / 2, P(370)), e['sub'], font=font(FS, 42), fill=(60, 60, 60), anchor='mm')
            for k2 in range(5): pd.rectangle((P(60), P(440 + k2 * 34), pw - P(60), P(452 + k2 * 34)), fill=(170, 165, 150))
            pd.text((pw - P(30), ph - P(24)), 'TEMSİLİ', font=font(FS, 22), fill=(120, 110, 100), anchor='rm')
            pg = pg.rotate(rot, expand=True, resample=Image.BICUBIC)
            put(img, pg, 960, 500 + 20 * (1 - q), 'mm', a, 0.92 + 0.08 * ease(p))
        elif k == 'tag':
            put(img, text_img(e.get('t', 'TEMSİLİ CANLANDIRMA'), 'S', 24, 'gr', True), 1880, 40, 'rt', a)
        elif k == 'quote':
            lines = e['lines']; base_y = e.get('y', 540) - (len(lines) - 1) * e.get('lh', 96) / 2
            put(img, text_img('“', 'Q', 220, 'y', False), e.get('x', 960) - e.get('qx', 640), base_y - 70, 'mm', a)
            for i, ln in enumerate(lines):
                ti = at + e.get('gap', 0.0) * i
                if t < ti: continue
                put(img, text_img(ln, 'Q', e.get('size', 78), 'w'), e.get('x', 960), base_y + i * e.get('lh', 96), 'mm', oc((t - ti) / 0.5))
            if e.get('who'): put(img, text_img('— ' + e['who'], 'X', 36, 'y'), e.get('x', 960), base_y + len(lines) * e.get('lh', 96) + 20, 'mm', a)
        elif k == 'bar':  # ince altın çizgi
            lw = P(e.get('w', 400)) * oc((t - at) / 0.6); d.rectangle((P(e['x']) - lw / 2, P(e['y']), P(e['x']) + lw / 2, P(e['y'] + 6)), fill=YEL + (255,))

def chapter_frame(sc, t, p, dur):
    fr = ice_bg(5).copy(); img = Image.fromarray(fr.astype(np.uint8)).convert('RGBA'); snow(img, t, 0.8)
    q = oc((t - 0.15) / 0.7); n = sc['base']['n']; ti = sc['base']['title']
    put(img, text_img(f"{int(n):02d}" if str(n).isdigit() else str(n), 'B', 200, (255, 212, 0, 255), True), 960, 330, 'mm', q * 0.9, 1.0 + 0.04 * p)
    put(img, text_img(f"BÖLÜM {n}" if str(n).isdigit() else "FİNAL", 'X', 40, 'gr'), 960, 470, 'mm', q)
    lw = P(560) * oc((t - 0.4) / 0.8); ImageDraw.Draw(img).rectangle((P(960) - lw / 2, P(520), P(960) + lw / 2, P(526)), fill=YEL + (255,))
    put(img, text_img(ti, 'B', 104, 'w', True, 0, 1700), 960, 610, 'mm', oc((t - 0.6) / 0.6))
    fo = 1 - oc((t - (dur - 0.45)) / 0.45)
    out = np.asarray(img.convert('RGB')).astype(np.float32) * fo
    return out

def end_frame(sc, t, p, dur):
    b = sc['base']; fr = ice_bg(9).copy(); img = Image.fromarray(fr.astype(np.uint8)).convert('RGBA'); snow(img, t, 0.6)
    put(img, text_img('BEYİN KODU LAB', 'B', 64, 'y'), 120, 150, 'lm', oc(t / 0.6))
    put(img, text_img(b.get('kod', 'BEYİN KODU #2'), 'B', 54, 'w'), 120, 240, 'lm', oc((t - 0.3) / 0.6))
    for i, ln in enumerate(b.get('lines', [])): put(img, text_img(ln, 'Q', 46, 'w', True, 0, 760), 120, 340 + i * 70, 'lm', oc((t - 0.6 - 0.2 * i) / 0.6))
    d = ImageDraw.Draw(img)  # bitiş ekranı öğeleri için boş yer (sağ: 2 video, alt-sol: abone)
    for (x0, y0) in ((1040, 250), (1040, 600)):
        d.rounded_rectangle((P(x0), P(y0), P(x0 + 760), P(y0 + 300)), int(P(18)), outline=(255, 255, 255, 60), width=int(P(3)))
    put(img, text_img('Sıradaki hikâye', 'X', 34, 'gr'), 1420, 210, 'mm', oc(t / 0.8))
    return np.asarray(img.convert('RGB')).astype(np.float32)

import os as _os
exec(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'cin16_fx2.py'), encoding='utf-8').read())
SCN = plan['scenes']
def scene_frame(i, t):
    sc = SCN[i]; dur = sc['end'] - sc['start']; tl = t - sc['start']; p = min(max(tl / dur, 0), 1)
    k = sc['base'].get('k', 'photo')
    if k == 'chapter': out = chapter_frame(sc, tl, p, dur)
    elif k == 'end': out = end_frame(sc, tl, p, dur)
    else:
        fr = base_frame(sc, tl, p)
        if sc['base'].get('dark'): fr = fr * sc['base']['dark']
        img = Image.fromarray(np.clip(fr, 0, 255).astype(np.uint8)).convert('RGBA')
        if k in ('bg', 'split') or sc['base'].get('snow'): snow(img, tl, 0.7)
        if sc['base'].get('grad'):
            g = np.zeros((H, W, 4), np.uint8); ramp = np.clip((np.arange(H) / H - sc['base']['grad']) / (1 - sc['base']['grad']), 0, 1) ** 1.2
            g[:, :, 3] = (ramp[:, None] * 210).astype(np.uint8); img.alpha_composite(Image.fromarray(g))
        if sc['base'].get('credit'): put(img, text_img(sc['base']['credit'], 'S', 20, (215, 220, 230), True), 1890, 30, 'rt', 0.9)
        draw_els(img, sc, tl, p, dur)
        out = np.asarray(img.convert('RGB')).astype(np.float32)
    return out

def frame(t):
    # aktif sahne(ler) + çapraz geçiş
    idx = [i for i, s in enumerate(SCN) if s['start'] - XF / 2 <= t < s['end'] + XF / 2]
    cur = [i for i in idx if SCN[i]['start'] <= t < SCN[i]['end']]
    i = cur[0] if cur else idx[-1]
    out = scene_frame(i, t)
    for j in idx:
        if j == i: continue
        bd = SCN[i]['start'] if j < i else SCN[i]['end']
        if SCN[j].get('cut') or SCN[i].get('cut'): continue
        w_ = 0.5 - abs(t - bd) / XF  # sınırda 0.5
        if w_ > 0: out = out * (1 - w_) + scene_frame(j, t) * w_
    gi = int(t * FPS) % len(GRAIN)
    out = out * VIG + GRAIN[gi]
    return np.clip(out, 0, 255).astype(np.uint8)

ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', OUT], stdin=subprocess.PIPE)
n0, n1 = round(T0 * FPS), round(T1 * FPS)
for n in range(n0, n1):
    ff.stdin.write(frame(n / FPS).tobytes())
ff.stdin.close(); ff.wait(); print('ok', T0, T1, n1 - n0)
