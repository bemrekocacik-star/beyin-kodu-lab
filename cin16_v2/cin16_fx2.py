# CIN16 V2 efekt katmanı — cin16.py içinde exec ile yüklenir (aynı globaller: P, W, H, put, text_img, emoji_img, font, oc, ob, ease ...)
from PIL import ImageOps
FSERB = '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf'
FSERC = '/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed-Bold.ttf'
FSER = '/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed.ttf'
GOLD = (255, 200, 60); SILV = (205, 212, 225); BRNZ = (205, 127, 50)

def newlayer(): return Image.new('RGBA', (W, H), (0, 0, 0, 0))
def glow_comp(img, lay, rad=10, twice=False):
    g = lay.filter(ImageFilter.GaussianBlur(P(rad))); img.alpha_composite(g)
    if twice: img.alpha_composite(g)
    img.alpha_composite(lay)

# ---- buz kristalleri (parıltı) ----
CRY = [(random.Random(i * 31).random(), random.Random(i * 17).random(), random.Random(i * 5).uniform(7, 17),
        random.Random(i * 11).uniform(0, 6.28), random.Random(i * 23).uniform(1.1, 2.4)) for i in range(48)]
def star(d, x, y, r, a, col=(235, 245, 255)):
    c = col + (int(255 * min(1, a)),); w1 = max(1, int(P(2.2)))
    d.line((x - r, y, x + r, y), fill=c, width=w1); d.line((x, y - r, x, y + r), fill=c, width=w1)
    rr = r * 0.32; d.line((x - rr, y - rr, x + rr, y + rr), fill=c, width=1); d.line((x - rr, y + rr, x + rr, y - rr), fill=c, width=1)
    d.ellipse((x - P(2.5), y - P(2.5), x + P(2.5), y + P(2.5)), fill=c)
def crystals(img, t, a=1.0, n=20, box=(0, 0, 1920, 1080), seed=0):
    if a <= 0.01: return
    lay = newlayer(); d = ImageDraw.Draw(lay); x0, y0, x1, y1 = box
    for (u, v, s, ph, w) in CRY[seed:seed + n]:
        b = max(0.0, math.sin(t * w + ph)) ** 3
        if b < 0.05: continue
        star(d, P(x0 + (x1 - x0) * u), P(y0 + (y1 - y0) * ((v - 0.012 * t) % 1)), P(s) * (0.55 + 0.45 * b), b * a)
    glow_comp(img, lay, 5)

# ---- ışık süpürmesi (metin üzerinde) ----
def sweep_img(im, pos, k=0.85):
    if pos <= 0 or pos >= 1: return im
    w, h = im.size; band = Image.new('L', (w, h), 0); d = ImageDraw.Draw(band)
    cx = -0.25 * w + pos * 1.5 * w; bw = 0.12 * w
    d.polygon([(cx - bw, h), (cx, 0), (cx + bw, 0), (cx, h)], fill=255); band = band.filter(ImageFilter.GaussianBlur(max(1, bw * 0.35)))
    m = np.minimum(np.asarray(band, np.float32), np.asarray(im.getchannel('A'), np.float32)) * k
    hl = Image.new('RGBA', (w, h), (255, 250, 225, 0)); hl.putalpha(Image.fromarray(m.astype(np.uint8)))
    out = im.copy(); out.alpha_composite(hl); return out

@functools.lru_cache(8)
def pin_img(size):
    s = int(P(size)); im = Image.new('RGBA', (s, int(s * 1.45)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    r = s / 2 * 0.92; cx = s / 2; cy = r + 2
    d.polygon([(cx - r * 0.8, cy + r * 0.5), (cx + r * 0.8, cy + r * 0.5), (cx, s * 1.42)], fill=YEL + (255,))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=YEL + (255,)); d.ellipse((cx - r * 0.38, cy - r * 0.38, cx + r * 0.38, cy + r * 0.38), fill=NAVY + (255,))
    return im

def fx_loc2(img, e, t, at, a, q, p, dur, sc):
    x, y = e.get('x', 110), e.get('y', 700); tt = t - at
    lay = newlayer(); d = ImageDraw.Draw(lay); px, py = x + 45, y - 15
    for k2 in range(2):
        rp = (tt * 0.7 + k2 * 0.5) % 1.0; rr = P(18 + 75 * rp)
        d.ellipse((P(px) - rr, P(py + 52) - rr * 0.33, P(px) + rr, P(py + 52) + rr * 0.33), outline=YEL + (int(210 * (1 - rp) * a),), width=max(1, int(P(3))))
    img.alpha_composite(lay)
    drop = 1 - ob(tt / 0.6); put(img, pin_img(64), px, py - 140 * drop, 'mm', min(1, tt * 4) * a)
    city = sweep_img(text_img(e['city'], 'B', e.get('size', 104), 'w', True, 0, 1500), (tt - 0.6) / 1.3)
    put(img, city, x + 85 - 30 * (1 - q), y - 18, 'lm', a)
    lw = e.get('lw', 560) * oc((tt - 0.25) / 0.7); ImageDraw.Draw(img).rectangle((P(x + 118), P(y + 50), P(x + 118 + lw), P(y + 56)), fill=YEL + (int(255 * a),))
    put(img, text_img(e['date'], 'X', 42, 'y'), x + 88, y + 102, 'lm', min(a, oc((tt - 0.45) / 0.4)))
    crystals(img, t, 0.7 * a, 14, (0, 0, 1920, 640))

# ---- dönüş sarmalı (3B perspektif, iz, parçacık) ----
def fx_rot2(img, e, t, at, a, q, p, dur, sc):
    cx, cy, R = e.get('x', 960), e.get('y', 560), e.get('r', 380); tilt = e.get('tilt', 0.27); turns = e['turns']; rise = e.get('rise', 60)
    prog = oc((t - at) / e.get('dur', 2.4)); N = int(turns * 96)
    def pt(th): return (P(cx + R * math.sin(th)), P(cy + R * tilt * math.cos(th) - rise * th / (2 * math.pi) + rise * turns / 2))
    pts = [pt(turns * 2 * math.pi * i / N) for i in range(N + 1)]
    lay = newlayer(); d = ImageDraw.Draw(lay)
    d.line(pts, fill=(200, 220, 255, int(45 * a)), width=max(1, int(P(2))))
    nn = max(1, int(N * prog))
    for i in range(1, nn + 1):
        f = i / nn; th = turns * 2 * math.pi * i / N; front = math.cos(th) > 0
        wdt = int(P((7 + 12 * f) * (1.2 if front else 0.7))); c = YEL if front else (200, 170, 40)
        d.line((pts[i - 1], pts[i]), fill=c + (int((50 + 205 * f ** 1.5) * a),), width=max(1, wdt))
    hx, hy = pts[nn]; rh = P(15)
    d.ellipse((hx - rh, hy - rh, hx + rh, hy + rh), fill=(255, 255, 255, int(255 * a)))
    rr = random.Random(int(t * 24))
    for j in range(14):
        idx = max(0, nn - j * 3); sx, sy = pts[idx]; jj = P(rr.uniform(-22, 22)); s2 = P(rr.uniform(1.5, 4))
        d.ellipse((sx + jj - s2, sy + jj * 0.6 - s2, sx + jj + s2, sy + jj * 0.6 + s2), fill=(255, 245, 200, int(a * 220 * (1 - j / 14))))
    glow_comp(img, lay, 12, True)
    v = turns * prog; lbl = (f"{v:.1f}".replace('.', ',')) if prog < 1 else e['label']
    num = text_img(lbl, 'B', 150, 'y' if prog >= 1 else 'w')
    if prog >= 1: num = sweep_img(num, (t - at - e.get('dur', 2.4)) / 0.9)
    put(img, num, cx, cy - R * tilt - rise * turns / 2 - 120, 'mm', a, 1 + 0.08 * (1 - oc((t - at - e.get('dur', 2.4)) / 0.4)) * (prog >= 1))
    if e.get('sub'): put(img, text_img(e['sub'], 'X', 46, 'y'), cx, cy + R * tilt + rise * turns / 2 + 70, 'mm', a)
    crystals(img, t, 0.6 * a, 12, seed=20)

# ---- gerçekçi gazete ----
@functools.lru_cache(4)
def paper_tex(w, h, seed):
    g = np.random.default_rng(seed); base = np.array([233, 226, 208], np.float32)
    n = cv2.GaussianBlur(cv2.resize(g.normal(0, 1, (h // 6, w // 6)).astype(np.float32), (w, h)), (0, 0), 3)
    fine = g.normal(0, 3.5, (h, w)).astype(np.float32)
    yy2, xx2 = np.mgrid[0:h, 0:w]; vg = ((xx2 - w / 2) / (w / 2)) ** 2 + ((yy2 - h / 2) / (h / 2)) ** 2
    im = base[None, None, :] + (n * 7 + fine)[:, :, None] - (vg * 20)[:, :, None] * np.array([1.0, 1.1, 1.6])
    fold = np.exp(-((xx2 - w * 0.5) / (w * 0.006)) ** 2) * 18; im -= fold[:, :, None]
    return np.clip(im, 0, 255).astype(np.uint8)
BODY = ("Kaliforniyalı genç patenci, buz üzerinde yaşından beklenmeyen bir olgunlukla yarıştı. Üçlü aksel ve dörtlü atlayışlarıyla "
        "hakemlerin ve seyircilerin dikkatini çekti. Antrenörleri, disiplinli çalışmasının ve cesur programlarının altını çiziyor. "
        "Uzmanlar, önümüzdeki yıllarda olimpiyat kürsüsü için en güçlü adaylardan biri olabileceğini söylüyor. ") * 6
def wrap_lines(txt, f, maxw):
    out, cur = [], ''
    for wd in txt.split():
        tr = (cur + ' ' + wd).strip()
        if f.getlength(tr) > maxw and cur: out.append(cur); cur = wd
        else: cur = tr
    if cur: out.append(cur)
    return out
@functools.lru_cache(4)
def news_page(title, sub, photo, paper, date, cap):
    pw, ph = int(P(1200)), int(P(790)); pg = Image.fromarray(paper_tex(pw, ph, len(title))).convert('RGBA'); d = ImageDraw.Draw(pg); ink = (30, 28, 26, 255)
    d.text((pw / 2, P(64)), paper, font=font(FSERB, 70), fill=ink, anchor='mm')
    d.line((P(40), P(112), pw - P(40), P(112)), fill=ink, width=max(1, int(P(3)))); d.line((P(40), P(120), pw - P(40), P(120)), fill=ink, width=1)
    d.text((P(44), P(137)), date, font=font(FSER, 21), fill=ink, anchor='lm'); d.text((pw / 2, P(137)), 'SAYI 1.284', font=font(FSER, 21), fill=ink, anchor='mm')
    d.text((pw - P(44), P(137)), 'SPOR', font=font(FSERB, 21), fill=ink, anchor='rm'); d.line((P(40), P(154), pw - P(40), P(154)), fill=ink, width=1)
    sz = 104; f = font(FSERC, sz)
    while f.getlength(title) > pw - P(80): sz -= 4; f = font(FSERC, sz)
    d.text((pw / 2, P(228)), title, font=f, fill=ink, anchor='mm')
    if sub: d.text((pw / 2, P(306)), sub, font=font(FQ, 36), fill=(70, 64, 58, 255), anchor='mm')
    x0, y0, phw, phh = int(P(44)), int(P(345)), int(P(560)), int(P(380))
    src = Image.open(photo).convert('L'); src = ImageOps.fit(src, (phw, phh), Image.LANCZOS, centering=(0.5, 0.35))
    src = ImageOps.autocontrast(src, cutoff=1); arr = np.asarray(src, np.float32)
    arr = arr + np.random.default_rng(3).normal(0, 9, arr.shape); arr = np.clip(arr * 0.86 + 18, 0, 255)
    tint = np.stack([arr * 0.97 + 6, arr * 0.94 + 6, arr * 0.86 + 6], 2).clip(0, 255).astype(np.uint8)
    pg.paste(Image.fromarray(tint).convert('RGBA'), (x0, y0)); d.rectangle((x0, y0, x0 + phw, y0 + phh), outline=ink, width=1)
    d.text((x0, y0 + phh + P(18)), cap, font=font(FQ, 20), fill=(70, 64, 58, 255), anchor='lm')
    fb = font(FSER, 19); cw = P(260); lh = P(25)
    for ci in range(2):
        cx0 = P(636) + ci * (cw + P(26)); yy3 = P(352); lines = wrap_lines(BODY[ci * 300:], fb, cw)
        if ci == 0: d.text((cx0, yy3 - P(6)), 'K', font=font(FSERB, 64), fill=ink, anchor='lt'); lines = wrap_lines(BODY[1:], fb, cw)
        for li, ln in enumerate(lines):
            yl = yy3 + li * lh
            if yl > ph - P(50): break
            ind = P(54) if (ci == 0 and li < 3) else 0
            d.text((cx0 + ind, yl), ln if not ind else ln, font=fb, fill=(55, 52, 48, 255))
        if ci == 0: d.line((cx0 + cw + P(13), P(350), cx0 + cw + P(13), ph - P(50)), fill=(120, 115, 105, 255), width=1)
    d.text((pw - P(30), ph - P(22)), 'TEMSİLİ CANLANDIRMA', font=font(FS, 18), fill=(130, 120, 110, 255), anchor='rm')
    return pg
def fx_news2(img, e, t, at, a, q, p, dur, sc):
    pg = news_page(e['t'], e.get('sub', ''), e['photo'], e.get('paper', 'SPOR GÜNDEMİ'), e.get('date', ''), e.get('cap', ''))
    arr = np.asarray(pg); ph_, pw_ = arr.shape[:2]; tt = t - at; ent = oc(tt / 0.9)
    s = (0.95 + 0.08 * ease(min(1, tt / max(dur - at, 0.1)))) ; rot = math.radians(e.get('rot', -2) * (1 + 1.5 * (1 - ent)))
    cx, cy = P(960), P(560 + 260 * (1 - ent)); persp = 0.05 * (1 - 0.6 * ease(min(1, tt / 3)))
    hw, hh = pw_ * s / 2, ph_ * s / 2
    cs = [(-hw * (1 - persp), -hh), (hw * (1 - persp), -hh), (hw, hh), (-hw, hh)]
    dst = np.float32([(cx + x * math.cos(rot) - y * math.sin(rot), cy + x * math.sin(rot) + y * math.cos(rot)) for x, y in cs])
    M = cv2.getPerspectiveTransform(np.float32([(0, 0), (pw_, 0), (pw_, ph_), (0, ph_)]), dst)
    wp = cv2.warpPerspective(arr, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    al = wp[:, :, 3].astype(np.float32) / 255
    shd = cv2.GaussianBlur(np.roll(np.roll(al, int(P(22)), 0), int(P(14)), 1), (0, 0), P(18))
    base = np.asarray(img, np.float32).copy(); base[:, :, :3] *= (1 - 0.65 * shd * a)[:, :, None]
    # üstten ışık: sayfanın üst köşesinde hafif parlama
    light = np.clip(1.06 - 0.12 * (np.arange(H)[:, None] / H), 0.9, 1.1)
    pa = (al * a)[:, :, None]; base[:, :, :3] = base[:, :, :3] * (1 - pa) + np.clip(wp[:, :, :3] * light[:, :, None], 0, 255) * pa
    img.paste(Image.fromarray(base.astype(np.uint8), 'RGBA'))

# ---- buzlu cam kartlar ----
def frost(img, box, r, tintc=(14, 24, 52, 120)):
    x0, y0, x1, y1 = [int(v) for v in box]; x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0: return
    reg = img.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(P(16)))
    reg.alpha_composite(Image.new('RGBA', reg.size, tintc))
    m = Image.new('L', reg.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, reg.size[0] - 1, reg.size[1] - 1), int(r), fill=255)
    img.paste(reg, (x0, y0), m)
    d = ImageDraw.Draw(img); d.rounded_rectangle((x0, y0, x1 - 1, y1 - 1), int(r), outline=(255, 255, 255, 80), width=max(1, int(P(2))))
    hl = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0)); hd = ImageDraw.Draw(hl)
    for k2 in range(int((y1 - y0) * 0.4)): hd.line((0, k2, x1 - x0, k2), fill=(255, 255, 255, int(26 * (1 - k2 / ((y1 - y0) * 0.4)))))
    img.paste(Image.alpha_composite(img.crop((x0, y0, x1, y1)), hl), (x0, y0), m)
@functools.lru_cache(8)
def glow_disc(size, col=YEL):
    s = int(P(size)); im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((s * 0.18, s * 0.18, s * 0.82, s * 0.82), fill=col + (120,)); im = im.filter(ImageFilter.GaussianBlur(s * 0.1))
    d = ImageDraw.Draw(im); d.ellipse((s * 0.2, s * 0.2, s * 0.8, s * 0.8), fill=(20, 32, 70, 235), outline=col + (255,), width=max(1, int(P(3))))
    return im
def fx_cards(img, e, t, at, a, q, p, dur, sc):
    items = e['items']; n = len(items); cw, ch = e.get('cw', 440), e.get('ch', 300); gap = e.get('gap', 50)
    x0 = 960 - (n * cw + (n - 1) * gap) / 2; y = e.get('y', 560)
    for i, it in enumerate(items):
        ic, lab, ti = it[0], it[1], it[2]
        if t < ti: continue
        qq = oc((t - ti) / 0.55); bob = math.sin((t - ti) * 1.5 + i * 1.3) * 5
        cx = x0 + i * (cw + gap) + cw / 2; cy = y + 70 * (1 - qq) + bob
        if qq > 0.05: frost(img, (P(cx - cw / 2), P(cy - ch / 2), P(cx + cw / 2), P(cy + ch / 2)), P(26))
        sp = 0.6 + 0.4 * ob((t - ti) / 0.55)
        put(img, glow_disc(150, YEL if not (len(it) > 3 and it[3]) else GOLD), cx, cy - ch * 0.17, 'mm', qq, sp)
        put(img, emoji_img(ic, 84), cx, cy - ch * 0.17, 'mm', qq, sp)
        put(img, text_img(lab, 'B', e.get('size', 44), 'w', True, 0, cw - 20), cx, cy + ch * 0.29, 'mm', qq)
    crystals(img, t, 0.6 * a, 12, seed=5)

# ---- kontrol listesi v2 ----
def fx_checks2(img, e, t, at, a, q, p, dur, sc):
    for i, (ic, lab) in enumerate(e['items']):
        ti = at + e.get('gap', 1.1) * i
        if t < ti: continue
        qq = oc((t - ti) / 0.45); y = e.get('y', 360) + i * e.get('dy', 150); x0 = 960 - 450 - 60 * (1 - qq)
        frost(img, (P(x0), P(y - 58), P(x0 + 900), P(y + 58)), P(22))
        put(img, emoji_img(ic, 64), x0 + 70, y, 'mm', qq, 0.7 + 0.3 * ob((t - ti) / 0.45))
        put(img, text_img(lab, 'B', 56, 'w', True, 0, 640), x0 + 130, y, 'lm', qq)
        cp = oc((t - ti - 0.35) / 0.45)
        if cp > 0:
            lay = newlayer(); d = ImageDraw.Draw(lay); ccx, ccy = P(x0 + 830), P(y)
            d.ellipse((ccx - P(32), ccy - P(32), ccx + P(32), ccy + P(32)), outline=GRN + (255,), width=int(P(5)))
            p1, p2, p3 = (ccx - P(15), ccy + P(1)), (ccx - P(4), ccy + P(13)), (ccx + P(17), ccy - P(12))
            if cp < 0.4: d.line((p1, (p1[0] + (p2[0] - p1[0]) * cp / 0.4, p1[1] + (p2[1] - p1[1]) * cp / 0.4)), fill=GRN + (255,), width=int(P(7)))
            else:
                f2 = (cp - 0.4) / 0.6; d.line((p1, p2, (p2[0] + (p3[0] - p2[0]) * f2, p2[1] + (p3[1] - p2[1]) * f2)), fill=GRN + (255,), width=int(P(7)), joint='curve')
            glow_comp(img, lay, 6)
    crystals(img, t, 0.5 * a, 10, seed=8)

# ---- alıntı v2 ----
def fx_quote2(img, e, t, at, a, q, p, dur, sc):
    lines = e['lines']; lh = e.get('lh', 100); by = e.get('y', 520) - (len(lines) - 1) * lh / 2; x = e.get('x', 960)
    qm = text_img('“', 'Q', 520, (255, 212, 0, 60), False); put(img, qm, x - 560 + 25 * math.sin(t * 0.4), by + 40 - 12 * t / max(dur, 1), 'mm', a)
    for i, ln in enumerate(lines):
        words = ln.split(); ti0 = at + e.get('gap', 0.9) * i
        f = font(FQ, e.get('size', 76)); tot = f.getlength(ln) / SC; cx = x - tot / 2
        for j, wd in enumerate(words):
            tj = ti0 + 0.16 * j
            if t < tj: cx += (f.getlength(wd + ' ')) / SC; continue
            qq = oc((t - tj) / 0.5); wi = text_img(wd, 'Q', e.get('size', 76), 'y' if wd.strip(',.').lower() in e.get('hi', ()) else 'w')
            ww = f.getlength(wd) / SC; put(img, wi, cx + ww / 2, by + i * lh + 18 * (1 - qq), 'mm', qq * a)
            cx += f.getlength(wd + ' ') / SC
    lw = 520 * oc((t - at - 1.4) / 0.8); ImageDraw.Draw(img).rectangle((P(x - lw / 2), P(by + len(lines) * lh - 20), P(x + lw / 2), P(by + len(lines) * lh - 15)), fill=YEL + (int(255 * a),))
    if e.get('who'): put(img, text_img('— ' + e['who'], 'X', 36, 'gr'), x, by + len(lines) * lh + 30, 'mm', min(a, oc((t - at - 1.6) / 0.5)))
    crystals(img, t, 0.6 * a, 14, seed=12)

# ---- nöral ağ (beyin) ----
NEU = []
_r = random.Random(42)
while len(NEU) < 46:
    u, v = _r.uniform(-1, 1), _r.uniform(-1, 1)
    if ((abs(u) - 0.48) / 0.55) ** 2 + (v / 0.95) ** 2 < 1 or (u / 0.9) ** 2 + ((v + 0.1) / 0.75) ** 2 < 1: NEU.append((u, v, _r.uniform(0, 6.28)))
NEDGE = sorted({tuple(sorted((i, j))) for i, (u, v, _) in enumerate(NEU) for j in sorted(range(len(NEU)), key=lambda k: (NEU[k][0] - u) ** 2 + (NEU[k][1] - v) ** 2)[1:4]})
def fx_neuro(img, e, t, at, a, q, p, dur, sc):
    cx, cy, rw, rh = e.get('x', 960), e.get('y', 360), e.get('w', 330), e.get('h', 230); tt = t - at
    pos = [(P(cx + u * rw), P(cy + v * rh)) for u, v, _ in NEU]; lay = newlayer(); d = ImageDraw.Draw(lay)
    for k2, (i, j) in enumerate(NEDGE):
        g = oc((tt - 0.02 * k2 % 1.2) / 0.6)
        if g <= 0: continue
        (x1, y1), (x2, y2) = pos[i], pos[j]; d.line((x1, y1, x1 + (x2 - x1) * g, y1 + (y2 - y1) * g), fill=(120, 190, 255, int(110 * a)), width=max(1, int(P(2))))
        fr = (tt * 0.7 + k2 * 0.137) % 1
        if g >= 1 and k2 % 2 == 0:
            px_, py_ = x1 + (x2 - x1) * fr, y1 + (y2 - y1) * fr; d.ellipse((px_ - P(4), py_ - P(4), px_ + P(4), py_ + P(4)), fill=YEL + (int(240 * a),))
    for i, (x_, y_) in enumerate(pos):
        b = 0.55 + 0.45 * math.sin(t * 2.2 + NEU[i][2]); rr = P(5 + 4 * b) * min(1, tt * 2)
        d.ellipse((x_ - rr, y_ - rr, x_ + rr, y_ + rr), fill=(200, 230, 255, int(255 * a * (0.5 + 0.5 * b))))
    glow_comp(img, lay, 9, True)

# ---- formül (kısa + serbest = toplam) ----
def fx_formula(img, e, t, at, a, q, p, dur, sc):
    cards = e['cards']; ops = e['ops']; cw, ch = 440, 320; xs = [330, 960, 1590]; y = e.get('y', 560)
    for i, (ic, lab, sub, ti) in enumerate(cards):
        if t < ti: continue
        qq = oc((t - ti) / 0.55); cy = y + 80 * (1 - qq); cx = xs[i]; gold = i == 2
        if gold:
            lay = newlayer(); ImageDraw.Draw(lay).rounded_rectangle((P(cx - cw / 2), P(cy - ch / 2), P(cx + cw / 2), P(cy + ch / 2)), int(P(28)), outline=GOLD + (int(255 * qq * (0.6 + 0.4 * math.sin(t * 3))),), width=int(P(6)))
            img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(P(14))))
        frost(img, (P(cx - cw / 2), P(cy - ch / 2), P(cx + cw / 2), P(cy + ch / 2)), P(28), (40, 34, 10, 150) if gold else (14, 24, 52, 130))
        sp = 0.6 + 0.4 * ob((t - ti) / 0.55)
        put(img, glow_disc(150, GOLD if gold else YEL), cx, cy - 70, 'mm', qq, sp); put(img, emoji_img(ic, 84), cx, cy - 70, 'mm', qq, sp)
        put(img, text_img(lab, 'B', 46, 'y' if gold else 'w', True, 0, cw - 30), cx, cy + 50, 'mm', qq)
        put(img, text_img(sub, 'S', 28, 'gr', True, 0, cw - 30), cx, cy + 108, 'mm', qq)
        if gold: crystals(img, t, qq, 10, (cx - 260, cy - 200, cx + 260, cy + 200), seed=30)
    for i, (sym, ti) in enumerate(ops):
        if t < ti: continue
        qq = oc((t - ti) / 0.4); put(img, text_img(sym, 'B', 110, 'y'), (xs[i] + xs[i + 1]) / 2, y, 'mm', qq, 0.5 + 0.5 * ob((t - ti) / 0.4))

# ---- bayrak + madalya ----
@functools.lru_cache(8)
def flag_img(code, w=96):
    h = int(P(w * 0.62)); w2 = int(P(w)); im = Image.new('RGBA', (w2, h), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
    if code == 'USA':
        for k2 in range(13):
            if k2 % 2 == 0: d.rectangle((0, h * k2 / 13, w2, h * (k2 + 1) / 13), fill=(178, 34, 52))
        d.rectangle((0, 0, w2 * 0.42, h * 7 / 13), fill=(60, 59, 110))
        for r_ in range(4):
            for c_ in range(5): x_, y_ = w2 * 0.05 + c_ * w2 * 0.08, h * 0.07 + r_ * h * 0.125; d.ellipse((x_, y_, x_ + 2, y_ + 2), fill=(255, 255, 255))
    elif code == 'JPN':
        rr = h * 0.3; d.ellipse((w2 / 2 - rr, h / 2 - rr, w2 / 2 + rr, h / 2 + rr), fill=(188, 0, 45))
    d.rectangle((0, 0, w2 - 1, h - 1), outline=(0, 0, 0, 90)); return im
@functools.lru_cache(8)
def medal_img(col, n, size=86, ribbon=False):
    s = int(P(size)); hh = int(s * (1.7 if ribbon else 1.0)); im = Image.new('RGBA', (s, hh), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    off = hh - s
    if ribbon:
        d.polygon([(s * 0.2, 0), (s * 0.45, 0), (s * 0.62, off + s * 0.2), (s * 0.4, off + s * 0.2)], fill=(30, 60, 160))
        d.polygon([(s * 0.8, 0), (s * 0.55, 0), (s * 0.38, off + s * 0.2), (s * 0.6, off + s * 0.2)], fill=(190, 30, 45))
    c = np.array(col, np.float32)
    for k2 in range(s // 2, 0, -1):
        f = k2 / (s / 2); cc = tuple(int(v) for v in np.clip(c * (0.7 + 0.5 * (1 - f)), 0, 255)); d.ellipse((s / 2 - k2, off + s / 2 - k2, s / 2 + k2, off + s / 2 + k2), fill=cc + (255,))
    d.ellipse((s * 0.12, off + s * 0.12, s * 0.88, off + s * 0.88), outline=tuple(int(v * 0.65) for v in col) + (255,), width=max(1, int(P(3))))
    d.text((s / 2, off + s / 2 + 1), str(n), font=font(FB, size * 0.42), fill=(40, 30, 10, 255), anchor='mm'); return im

def fx_score2(img, e, t, at, a, q, p, dur, sc):
    rows = e['rows']; mx = max(r[1] for r in rows); mn = e.get('min', 200); px0, py0, pw, ph = 260, e.get('y', 300), 1400, 150 * len(rows) + 60
    if a > 0.05: frost(img, (P(px0), P(py0 - 40), P(px0 + pw), P(py0 - 40 + ph)), P(30), (10, 18, 44, 150))
    meds = [GOLD, SILV, BRNZ]
    for i, (nm, sc_, code) in enumerate(rows):
        ti = at + 0.5 + 0.45 * i; qq = oc((t - ti) / 1.1)
        if t < ti: continue
        y = py0 + 30 + i * 150; win = i == 0
        put(img, medal_img(meds[i], i + 1), px0 + 80, y + 42, 'mm', min(1, (t - ti) * 4), 0.6 + 0.4 * ob((t - ti) / 0.5))
        put(img, flag_img(code), px0 + 185, y + 42, 'mm', min(1, (t - ti) * 4))
        put(img, text_img(nm, 'X', 44, 'y' if win else 'w'), px0 + 240, y + 42, 'lm', qq)
        bx0, bw = px0 + 700, 480; fill = bw * qq * (sc_ - mn) / (mx - mn)
        lay = newlayer(); ld = ImageDraw.Draw(lay); ld.rounded_rectangle((P(bx0), P(y + 22), P(bx0 + bw), P(y + 62)), int(P(12)), fill=(255, 255, 255, 34)); img.alpha_composite(lay)
        lay = newlayer(); ld = ImageDraw.Draw(lay)
        c0 = np.array(meds[i] if win else (150, 170, 210), np.float32)
        ld.rounded_rectangle((P(bx0), P(y + 22), P(bx0 + max(24, fill)), P(y + 62)), int(P(12)), fill=tuple(int(v) for v in c0) + (240,))
        if win: glow_comp(img, lay, 10)
        else: img.alpha_composite(lay)
        put(img, text_img(f"{sc_ * qq + (1 - qq) * mn:.2f}".replace('.', ','), 'B', 50, 'y' if win else 'w'), bx0 + bw + 30, y + 42, 'lm', qq)
    tw = at + 0.5 + 1.6
    if t > tw:
        sw = (t - tw) / 1.0
        if 0 < sw < 1:
            lay = newlayer(); ld = ImageDraw.Draw(lay); xs_ = P(px0 + pw * sw)
            ld.polygon([(xs_ - P(60), P(py0 + 10)), (xs_, P(py0 + 10)), (xs_ - P(30), P(py0 + 140)), (xs_ - P(90), P(py0 + 140))], fill=(255, 255, 230, 70))
            img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(P(8))))
        crystals(img, t, min(1, (t - tw) * 2) * a, 16, (px0, py0 - 60, px0 + pw, py0 + 160), seed=3)

# ---- 2002 → 2026 zaman yayı ----
def fx_tl2(img, e, t, at, a, q, p, dur, sc):
    (l1, y1), (l2, y2) = e['pts']; xa, xb, y = 470, 1450, e.get('y', 540); tt = t - at; pr = oc(tt / e.get('dur', 2.0))
    lay = newlayer(); d = ImageDraw.Draw(lay); N = 80; pts = []
    for i in range(N + 1):
        f = i / N; pts.append((P(xa + (xb - xa) * f), P(y - 230 * math.sin(math.pi * f))))
    for i in range(0, int(N * pr), 2): d.line((pts[i], pts[min(N, i + 1)]), fill=YEL + (int(200 * a),), width=int(P(4)))
    hx, hy = pts[int(N * pr)]; d.ellipse((hx - P(12), hy - P(12), hx + P(12), hy + P(12)), fill=(255, 255, 255, int(255 * a)))
    glow_comp(img, lay, 10, True)
    put(img, medal_img(SILV, '02', 130, True), xa, y + 40, 'mm', min(1, tt * 3) * a)
    put(img, text_img(y1, 'B', 70, 'w'), xa, y + 205, 'mm', a); put(img, text_img(l1, 'S', 36, 'gr'), xa, y + 255, 'mm', a)
    if pr > 0.97:
        q2 = oc((tt - e.get('dur', 2.0)) / 0.5); pulse = 1 + 0.04 * math.sin(t * 4)
        put(img, glow_disc(300, GOLD), xb, y + 75, 'mm', q2 * 0.8)
        put(img, medal_img(GOLD, '26', 150, True), xb, y + 40, 'mm', q2, (0.6 + 0.4 * ob((tt - e.get('dur', 2.0)) / 0.5)) * pulse)
        put(img, text_img(y2, 'B', 70, 'y'), xb, y + 205, 'mm', q2); put(img, text_img(l2, 'S', 36, 'w'), xb, y + 255, 'mm', q2)
        crystals(img, t, q2, 14, (xb - 300, y - 200, xb + 300, y + 260), seed=18)
    yr = int(round(2002 + 24 * pr)); put(img, text_img(str(yr), 'B', 64, 'w'), 960, y - 300, 'mm', a)

# ---- HIZ / ADRENALİN / KONTROL (kinetik) ----
def fx_kin(img, e, t, at, a, q, p, dur, sc):
    for (wd, ti, mode, y, col) in e['words']:
        if t < ti: continue
        tt = t - ti; im = text_img(wd, 'B', e.get('size', 140), col)
        if mode == 'speed':
            x = 960 - 1400 * (1 - oc(tt / 0.28))
            if tt < 0.45:
                for g in range(1, 6): put(img, im, x - g * 70 * (1 - oc(tt / 0.45)), y, 'mm', 0.16 * (6 - g) / 5)
                lay = newlayer(); ld = ImageDraw.Draw(lay); rr = random.Random(int(t * 24))
                for _ in range(16):
                    ly = P(y + rr.uniform(-110, 110)); lx = P(rr.uniform(0, 1920)); ll = P(rr.uniform(120, 420))
                    ld.line((lx, ly, lx + ll, ly), fill=(255, 255, 255, int(120 * (1 - tt / 0.45))), width=max(1, int(P(2))))
                img.alpha_composite(lay)
            put(img, im, x, y, 'mm', 1)
        elif mode == 'punch':
            s = 1.7 - 0.7 * ob(tt / 0.3); amp = 14 * max(0, 1 - tt / 0.45); rr = random.Random(int(t * 48))
            put(img, im, 960 + rr.uniform(-amp, amp), y + rr.uniform(-amp, amp), 'mm', min(1, tt * 8), s)
            if tt < 0.3: put(img, glow_disc(500, (255, 120, 60)), 960, y, 'mm', 0.5 * (1 - tt / 0.3))
        elif mode == 'lock':
            s = 1.12 - 0.12 * oc(tt / 0.35); put(img, im, 960, y, 'mm', min(1, tt * 5), s)
            bw = im.size[0] / SC / 2 + 40 + 120 * (1 - oc((tt - 0.15) / 0.35)); ba = min(1, max(0, (tt - 0.1) * 5))
            lay = newlayer(); ld = ImageDraw.Draw(lay); hh_ = 85; c = YEL + (int(255 * ba),); wl = int(P(8))
            for sgn in (-1, 1):
                xx_ = P(960 + sgn * bw); ld.line((xx_, P(y - hh_), xx_, P(y + hh_)), fill=c, width=wl)
                ld.line((xx_, P(y - hh_), xx_ - sgn * P(34), P(y - hh_)), fill=c, width=wl); ld.line((xx_, P(y + hh_), xx_ - sgn * P(34), P(y + hh_)), fill=c, width=wl)
            glow_comp(img, lay, 8)

# ---- katmanlı başlık (BIRAKMAK = YENİLMEK?) ----
@functools.lru_cache(8)
def outline_text(t_, size):
    f = font(FB, size); w = int(f.getlength(t_) + P(40)); h = int(f.size * 1.4)
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ImageDraw.Draw(im).text((w / 2, h / 2), t_, font=f, fill=(0, 0, 0, 0), anchor='mm', stroke_width=max(1, int(P(3))), stroke_fill=(255, 255, 255, 255)); return im
def fx_layered(img, e, t, at, a, q, p, dur, sc):
    tt = t - at
    put(img, outline_text(e['big'], 300), 960 - 60 + 120 * p, 520, 'mm', 0.16 * min(1, tt))
    l1 = text_img(e['l1'], 'B', 120, 'w'); put(img, l1, 960, 400 - 10 * p, 'mm', oc((tt) / 0.6), 0.94 + 0.06 * oc(tt / 0.8))
    put(img, text_img(e['l2'], 'B', 78, 'gr'), 960, 525, 'mm', oc((tt - 0.6) / 0.6))
    ts = e['t2'] - at
    if tt > ts:
        sw = oc((tt - ts) / 0.5); w2 = text_img(e['l2'], 'B', 78, 'gr').size[0] / SC - 40
        ImageDraw.Draw(img).rectangle((P(960 - w2 / 2), P(522), P(960 - w2 / 2 + w2 * sw), P(530)), fill=YEL + (255,))
        im3 = sweep_img(text_img(e['l3'], 'B', 110, 'y'), (tt - ts - 0.6) / 1.0)
        put(img, im3, 960, 690 + 20 * (1 - oc((tt - ts - 0.3) / 0.5)), 'mm', oc((tt - ts - 0.3) / 0.5))
        crystals(img, t, oc((tt - ts) / 0.8), 14, seed=26)

FX2 = {'loc2': fx_loc2, 'rot2': fx_rot2, 'news2': fx_news2, 'cards': fx_cards, 'checks2': fx_checks2, 'quote2': fx_quote2,
       'neuro': fx_neuro, 'formula': fx_formula, 'score2': fx_score2, 'tl2': fx_tl2, 'kin': fx_kin, 'layered': fx_layered}
