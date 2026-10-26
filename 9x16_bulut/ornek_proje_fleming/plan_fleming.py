#!/usr/bin/env python3
"""Fleming / Penisilin — Kod #9. Sahne kesimleri ve sahne içi zamanlar kelime indeksinden (kelimeler.json)."""
import json, math, functools
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFilter
from engine9 import *

Wd = json.load(open("kelimeler.json"))
DUR = 61.96
ST = [0, 7, 19, 26, 38, 47, 53, 63, 70, 75, 84, 91, 100, 107]
C = [0.0] + [Wd[i]["s"] - 0.12 for i in ST[1:]] + [DUR]
def r(i): return Wd[i]["s"]
def e(i): return Wd[i]["e"]

# ---------------- petri kabı (üretilmiş, gerçekçi)
_rng = np.random.default_rng(11)
MOLD = (-0.30, -0.18)
COL = []
while len(COL) < 300:
    x, y = _rng.uniform(-0.93, 0.93, 2)
    if x * x + y * y < 0.86 ** 2 and (x - MOLD[0]) ** 2 + (y - MOLD[1]) ** 2 > 0.03:
        COL.append((x, y, _rng.uniform(0.010, 0.026)))
COL = np.array(COL)

@functools.lru_cache(maxsize=8)
def dish_img(R, colonies=False):
    S = int(R * 2 + 80); c = S / 2
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    d = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / R
    img = np.zeros((S, S, 4), np.float32)
    # gölge
    sh = np.clip(1 - np.abs(np.sqrt((xx - c) ** 2 + (yy - c - R * 0.06) ** 2) / R - 1.0) / 0.12, 0, 1) * (d > 0.9)
    # agar
    g = np.clip(d, 0, 1)[..., None]
    agar = np.array((247, 232, 168), np.float32) * (1 - g * 0.35) + np.array((196, 170, 92), np.float32) * (g * 0.35)
    inside = (d <= 1.0).astype(np.float32)[..., None]
    img[..., :3] = agar; img[..., 3:4] = inside * 240
    # cam kenar
    rim = np.clip(1 - np.abs(d - 1.02) / 0.035, 0, 1)[..., None]
    img[..., :3] = img[..., :3] * (1 - rim) + 255 * rim
    img[..., 3:4] = np.maximum(img[..., 3:4], rim * 230)
    rim2 = np.clip(1 - np.abs(d - 1.065) / 0.02, 0, 1)[..., None]
    img[..., :3] = img[..., :3] * (1 - rim2 * 0.6) + np.array((200, 225, 235)) * rim2 * 0.6
    img[..., 3:4] = np.maximum(img[..., 3:4], rim2 * 170)
    # parlama
    ang = np.arctan2(yy - c, xx - c)
    hl = np.clip(1 - np.abs(d - 0.93) / 0.03, 0, 1) * np.clip(np.cos(ang + 2.3) * 1.6 - 0.6, 0, 1)
    img[..., :3] = img[..., :3] * (1 - hl[..., None] * 0.7) + 255 * hl[..., None] * 0.7
    out = np.zeros_like(img)
    out[..., 3] = sh * 120
    a = img[..., 3:4] / 255
    out[..., :3] = img[..., :3]
    out[..., 3:4] = np.maximum(out[..., 3:4] * (1 - a), img[..., 3:4])
    if colonies:
        for x, y, rr in COL[::2]:
            cv2.circle(out, (int(c + x * R), int(c + y * R)), max(2, int(rr * R * 1.6)), (240, 190, 60, 255), -1, cv2.LINE_AA)
    return out

@functools.lru_cache(maxsize=1)
def mold_base():
    S = 512; c = S / 2
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    ang = np.arctan2(yy - c, xx - c); d = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / (S * 0.42)
    n = 1 + 0.07 * np.sin(ang * 7 + 1.3) + 0.05 * np.sin(ang * 13 + 0.4) + 0.03 * np.sin(ang * 29)
    dd = d / n
    a = np.clip((1 - dd) / 0.06, 0, 1)
    rng = np.random.default_rng(5); fuzz = cv2.GaussianBlur(rng.random((S, S)).astype(np.float32), (0, 0), 2.2)
    core = np.clip(1 - dd / 0.55, 0, 1)
    colr = np.zeros((S, S, 3), np.float32)
    turq = np.array(TURQ, np.float32) * 0.85 + np.array((30, 120, 90), np.float32) * 0.15
    colr[:] = turq
    colr = colr * (1 - core[..., None]) + np.array((245, 250, 245), np.float32) * core[..., None]
    ring = np.clip(1 - np.abs(dd - 0.78) / 0.12, 0, 1)[..., None]
    colr = colr * (1 - ring * 0.35) + np.array((20, 110, 120), np.float32) * ring * 0.35
    colr *= (0.85 + 0.3 * fuzz[..., None])
    img = np.concatenate([np.clip(colr, 0, 255), (a * (0.9 + 0.1 * fuzz) * 255)[..., None]], axis=2)
    return cv2.GaussianBlur(img, (0, 0), 1.2)

def petri(f, cx, cy, R, mold_r=0.0, halo_r=0.0, t=0.0):
    D = dish_img(R)
    over(f, D, cx - D.shape[1] / 2, cy - D.shape[0] / 2)
    mx, my = cx + MOLD[0] * R, cy + MOLD[1] * R
    if halo_r > 1:
        hal = np.zeros((int(halo_r * 2 + 8), int(halo_r * 2 + 8), 4), np.float32)
        hc = hal.shape[0] // 2
        cv2.circle(hal, (hc, hc), int(halo_r), (255, 252, 230, 120), -1, cv2.LINE_AA)
        hal = cv2.GaussianBlur(hal, (0, 0), 6)
        over(f, hal, mx - hc, my - hc)
    for x, y, rr in COL:
        px, py = cx + x * R, cy + y * R
        dd = math.hypot(px - mx, py - my)
        k = clamp((halo_r - dd) / 45.0) if halo_r > 1 else 0.0
        if k >= 1: continue
        rad = rr * R * (1 - 0.6 * k)
        col = np.array((244, 196, 64)) * (1 - k * 0.8) + np.array(RED) * (k * 0.8)
        a = 1 - k
        if a < 0.02: continue
        x0, y0 = int(px), int(py); rad_i = max(2, int(rad))
        sub = f[y0 - rad_i - 2:y0 + rad_i + 3, x0 - rad_i - 2:x0 + rad_i + 3]
        if sub.size == 0: continue
        tmp = sub.copy()
        cv2.circle(tmp, (rad_i + 2, rad_i + 2), rad_i, tuple(float(v) * 0.75 for v in col), -1, cv2.LINE_AA)
        cv2.circle(tmp, (rad_i + 2, rad_i + 2), max(1, int(rad_i * 0.78)), tuple(float(v) for v in col), -1, cv2.LINE_AA)
        cv2.circle(tmp, (rad_i + 2 - rad_i // 3, rad_i + 2 - rad_i // 3), max(1, rad_i // 4), (255, 250, 225), -1, cv2.LINE_AA)
        sub[:] = sub * (1 - a) + tmp * a
    if mold_r > 2:
        m = cv2.resize(mold_base(), (int(mold_r * 2.38), int(mold_r * 2.38)), interpolation=cv2.INTER_AREA)
        over(f, m, mx - m.shape[1] / 2, my - m.shape[0] / 2)
    return mx, my

# ---------------- portreler
@functools.lru_cache(maxsize=8)
def portrait(path, w, h, fx=0.5, fy=0.3, bw=True):
    im = Image.open(path).convert("L" if bw else "RGB").convert("RGB")
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    ox = int((im.width - w) * fx); oy = int((im.height - h) * fy)
    im = im.crop((ox, oy, ox + w, oy + h)).filter(ImageFilter.UnsharpMask(1.5, 70, 2))
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), 34, fill=255)
    out = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((20, 28, 20 + w, 28 + h), 34, fill=(0, 0, 0, 150))
    out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(12)))
    out.paste(im, (20, 20), m)
    ImageDraw.Draw(out).rounded_rectangle((20, 20, 20 + w - 1, 20 + h - 1), 34, outline=GOLD + (255,), width=5)
    return pil2np(out)

@functools.lru_cache(maxsize=8)
def face_circle(path, box, D):
    im = Image.open(path).convert("L").convert("RGB").crop(box).resize((D, D), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.5, 70, 2))
    m = Image.new("L", (D, D), 0); ImageDraw.Draw(m).ellipse((0, 0, D - 1, D - 1), fill=255)
    out = Image.new("RGBA", (D + 40, D + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", out.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).ellipse((20, 28, 20 + D, 28 + D), fill=(0, 0, 0, 150))
    out = Image.alpha_composite(out, sh.filter(ImageFilter.GaussianBlur(10)))
    out.paste(im, (20, 20), m)
    ImageDraw.Draw(out).ellipse((20, 20, 20 + D - 1, 20 + D - 1), outline=GOLD + (255,), width=7)
    return pil2np(out)

FL_COLOR = "src/fleming_renkli_1943.jpg"
FL_DESK = "src/fleming_masa_bw.jpg"
FLOREY = "src/florey.jpg"; CHAIN = "src/chain.jpg"; PROD = "src/uretim_1943.jpg"

# ---------------- sahneler: fn(f, t, lt, dur)
def s0(f, t, lt, dur):  # KANCA
    card(f, FL_COLOR, lt, dur, "in", 0.04, focus=(0.5, 0.5))
    place(f, text("Imperial War Museums, 1943 · kamu malı", 22, (220, 226, 240), "med"), W / 2, CY + 34, 0.85)
    badge(f, "ÇÖPE ATILACAKTI", "n", t, -1)
    line(f, "YIKANMAYAN", 58, WHITE, 965, t, -1)
    line(f, "1 TABAK", 158, RED, 1070, t, -1, pulse_at=r(3))
    line(f, "MİLYONLARCA HAYAT", 84, GREEN, 1190, t, r(4), pulse_at=r(6))

def s1(f, t, lt, dur):  # LONDRA
    card(f, FL_DESK, lt, dur, "panx", 0.0, bw=True)
    credit(f, "ABD Donanması BUMED arşivi · kamu malı")
    badge(f, "LONDRA · 1928", "n", t, C[1])
    line(f, "ALEXANDER FLEMING", 70, GOLD, 985, t, r(9))
    line(f, "BAKTERİYOLOG · ST MARY'S HASTANESİ", 34, WHITE, 1052, t, r(9) + 0.25, weight="bold")
    stamp(f, "ZEKİ", GREEN, 380, 1160, t, r(15), rot=-5, size=64)
    stamp(f, "DAĞINIK", RED, 680, 1165, t, r(17), rot=4, size=64)

def s2(f, t, lt, dur):  # TATİL — bilgi kartı 1
    glass_panel(f)
    line(f, "TATİLE ÇIKTI", 78, WHITE, 385, t, r(19))
    line(f, "AĞUSTOS 1928", 44, GOLD, 462, t, r(19) + 0.15, weight="xb")
    put_icon(f, "suitcase", 320, 740, 400, t, r(19))
    for k, at in enumerate([r(21), r(22), r(23)]):
        if t >= at:
            D = dish_img(125, True)
            yoff = 60 * (1 - eout((t - at) / 0.25))
            over(f, D, 735 - D.shape[1] / 2, 840 - k * 62 - yoff - D.shape[0] / 2, clamp((t - at) / 0.15))
    place(f, pill("Tabaklar yıkanmadı", 44, (26, 44, 92), WHITE, 34, 18, "xb"), W / 2, 1030, clamp((t - (r(21))) / 0.2))
    place(f, pill("Tezgâhta unutuldu", 44, (26, 44, 92), WHITE, 34, 18, "xb"), W / 2, 1125, clamp((t - (r(22) + 0.2)) / 0.2))

def s3(f, t, lt, dur):  # PETRİ — küf + hale
    glass_panel(f, tint=(20, 34, 72))
    badge(f, "EYLÜL 1928", "sci", t, C[3])
    z = 1.0 + 0.06 * ease(lt / dur)
    slide = 1 - eout((t - C[3]) / 0.5)
    R = 300 * z
    cx = 540 - MOLD[0] * 300 * (z - 1); cy = 790 - MOLD[1] * 300 * (z - 1) + 500 * slide
    grow = ease((t - r(28)) / 0.9)
    mold_r = 105 * grow * z
    halo = 0.0
    if t > r(33):
        halo = (mold_r + 10) + 185 * z * eout((t - r(33)) / 2.4)
    mx, my = petri(f, cx, cy, R, mold_r, halo, t)
    if t >= r(30):
        place(f, pill("KÜF", 46, TURQ, NAVY, 34, 16), mx, my - mold_r - 70, clamp((t - r(30)) / 0.15))
    if t >= r(35):
        place(f, pill("BAKTERİLER", 40, GOLD, NAVY, 30, 14), 790, 500, clamp((t - r(35)) / 0.15))
    stamp(f, "YOK OLMUŞ", RED, 540, 1215, t, r(36), rot=-5, size=76)

def s4(f, t, lt, dur):  # ÇÖP — atmadı, merak etti
    glass_panel(f)
    put_icon(f, "trash", 790, 760, 330, t, C[4], bounce=False)
    p = ease((t - r(38)) / (r(42) + 0.3 - r(38)))
    back = ease((t - r(43)) / 0.5)
    x = 300 + 330 * p * (1 - back) + 340 * back
    y = 760 - 120 * math.sin(p * math.pi) * (1 - back) + 0 * back
    rot = -25 * p * (1 - back)
    D = dish_img(150, True)
    sc = 1.0 + 0.35 * back
    place(f, D, x, y, 1.0, sc, rot)
    if t >= r(43):
        put_icon(f, "xmark", 790, 760, 200, t, r(43))
    if t >= r(45):
        k = clamp((t - r(45)) / 0.3)
        put_icon(f, "magnifier", 400, 720, 360, t, r(45))
        stamp(f, "MERAK ETTİ", GOLD, 540, 1150, t, r(45), rot=0, size=80)
    line(f, "FLEMING ATMADI", 64, WHITE, 400, t, r(43))

def s5(f, t, lt, dur):  # PENİSİLİN — bilgi kartı 2
    glass_panel(f, tint=(20, 34, 72))
    line(f, "KÜFÜN SIRRI", 76, WHITE, 385, t, C[5])
    line(f, "1929", 46, TURQ, 462, t, C[5] + 0.15, weight="xb")
    put_icon(f, "mold", 540, 720, 360, t, r(47))
    place(f, pill("Penicillium küfünden", 42, (26, 44, 92), WHITE, 32, 16, "xb"), W / 2, 1110, clamp((t - r(48)) / 0.2))
    place(f, pill("İlk antibiyotik", 42, (26, 44, 92), WHITE, 32, 16, "xb"), W / 2, 1195, clamp((t - r(51)) / 0.2))
    if r(50) <= t < r(52):
        line(f, "? ? ?", 120, GOLD, 980, t, r(50), until=r(52) - 0.05)
    if t >= r(52):
        line(f, "PENİSİLİN", 132, GOLD, 985, t, r(52), pulse_at=r(52) + 0.05, fade=0.08)

def s6(f, t, lt, dur):  # SORUN — ret merdiveni
    glass_panel(f, tint=(40, 22, 40))
    badge(f, "BÜYÜK SORUN", "neg", t, C[6])
    sh = math.sin(t * 40) * 4 * clamp(1 - (t - r(58)) / 0.4) if t >= r(58) else 0
    put_icon(f, "vial", 540 + sh, 620, 440, t, C[6] + 0.05, alpha=0.85)
    for k, (s, at) in enumerate([("SAFLAŞTIRAMADI", r(58)), ("İLGİLENMEDİ", r(62))]):
        y = 1000 + k * 120
        put_icon(f, "xmark", 190, y, 100, t, at)
        if t >= at:
            place(f, text(s, 66, WHITE, "black", 0, (0, 0, 0), True, 640), 560, y, clamp((t - at) / 0.15))

def s7(f, t, lt, dur):  # 10 YIL RAFTA — sayaç
    glass_panel(f)
    k = ease((t - r(63)) / (r(69) - r(63)))
    yr = 1929 + int(round(10 * k))
    line(f, str(yr), 176, GOLD, 520, t, C[7], fade=0.05)
    line(f, "10 YIL RAFTA", 66, WHITE, 665, t, r(63))
    # raf
    cv2.rectangle(f, (210, 1060), (870, 1084), (70, 86, 128), -1, cv2.LINE_AA)
    cv2.rectangle(f, (250, 1084), (272, 1150), (55, 70, 110), -1); cv2.rectangle(f, (808, 1084), (830, 1150), (55, 70, 110), -1)
    put_icon(f, "vial", 540, 925, 260, t, C[7], bounce=False, alpha=1 - 0.5 * k)
    # toz
    rng = np.random.default_rng(3)
    for i in range(70):
        px = rng.uniform(220, 860); sp = rng.uniform(40, 90); ph = rng.uniform(0, 3)
        py = 760 + ((t * sp + ph * 100) % 300)
        cv2.circle(f, (int(px), int(py)), 2, (150, 160, 180), -1, cv2.LINE_AA)

def s8(f, t, lt, dur):  # SAVAŞ
    glass_panel(f, tint=(34, 18, 30))
    badge(f, "1939", "neg", t, C[8])
    pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi * 1.1)
    ov = np.zeros((CH, CW, 4), np.float32); ov[..., :3] = RED
    yy, xx = np.mgrid[0:CH:8, 0:CW:8]
    pass
    sh = math.sin(t * 31) * 3
    put_icon(f, "helmet", 540 + sh, 640, 430, t, C[8] + 0.05)
    reg = f[CY:CY + CH, CX:CX + CW]
    reg *= (1 - 0.08 * pulse); reg += np.array(RED, np.float32) * 0.08 * pulse
    line(f, "2. DÜNYA", 128, WHITE, 960, t, r(71))
    line(f, "SAVAŞI", 128, RED, 1095, t, r(72))

def s9(f, t, lt, dur):  # OXFORD — Florey + Chain
    glass_panel(f)
    badge(f, "OXFORD · 1940", "sci", t, C[9])
    for (path, cx, at, name, fx) in [(FLOREY, 316, r(76), "HOWARD FLOREY", 0.5), (CHAIN, 764, r(79), "ERNST CHAIN", 1.0)]:
        if t >= at - 0.25:
            k = eout((t - (at - 0.25)) / 0.35)
            place(f, portrait(path, 400, 540, fx, 0.25), cx, 640 + 40 * (1 - k), k)
            line(f, name, 48, GOLD, 945, t, at, weight="black", cx=cx, maxw=420)
    credit(f, "Fotoğraflar: OpenStax Microbiology · CC BY 4.0")
    stamp(f, "BAŞARDILAR", GREEN, 540, 1110, t, r(83), rot=-4, size=74)

def melon_spots(f, cx, cy, R, k):
    rng = np.random.default_rng(9)
    for i in range(9):
        a = rng.uniform(0, 2 * math.pi); d = rng.uniform(0.1, 0.65)
        px, py = cx + math.cos(a) * d * R, cy + math.sin(a) * d * R * 0.85
        rr = rng.uniform(0.06, 0.13) * R * eout(k * 1.4 - i * 0.06)
        if rr > 2:
            m = cv2.resize(mold_base(), (int(rr * 2.4), int(rr * 2.4)), interpolation=cv2.INTER_AREA)
            over(f, m, px - m.shape[1] / 2, py - m.shape[0] / 2, 0.95)

def s10(f, t, lt, dur):  # KAVUN
    glass_panel(f)
    badge(f, "PEORIA, ABD · 1943", "n", t, C[10])
    mv = ease((t - r(89)) / 0.45)
    cx = 540 - 230 * mv; size = 470 - 120 * mv
    put_icon(f, "melon", cx, 700, int(size), t, r(84) - 0.05)
    if t >= r(86):
        melon_spots(f, cx, 700 + size * 0.03, size * 0.42, clamp((t - r(86)) / 0.8))
        place(f, pill("KÜFLÜ KAVUN", 44, TURQ, NAVY, 34, 16), cx, 700 + size * 0.5 + 30, clamp((t - r(86)) / 0.15))
    if t >= r(89):
        put_icon(f, "chart", 780, 690, 340, t, r(89))
    line(f, "ÜRETİM KATLANDI", 80, GREEN, 1140, t, r(90), pulse_at=r(90) + 0.05)

def s11(f, t, lt, dur):  # 1944 — üretim fotoğrafı
    card(f, PROD, lt, dur, "in", 0.04, bw=True)
    credit(f, "Penisilin üretimi, İngiltere 1943 · IWM D 16965 · kamu malı")
    badge(f, "1944", "n", t, r(91))
    put_icon(f, "syringe", 860, 420, 190, t, r(98))
    line(f, "MİLYONLARCA DOZ", 92, GREEN, 1080, t, r(97), pulse_at=r(98))
    line(f, "CEPHEYE ULAŞTI", 54, WHITE, 1175, t, r(99))

FL_FACE = (300, 90, 600, 390)
def s12(f, t, lt, dur):  # NOBEL
    glass_panel(f)
    badge(f, "1945", "win", t, C[12])
    trio = [(FL_DESK, FL_FACE, 240, "FLEMING"), (FLOREY, (240, 300, 880, 940), 540, "FLOREY"), (CHAIN, (900, 300, 1290, 690), 840, "CHAIN")]
    for k, (p, box, cx, nm) in enumerate(trio):
        at = r(103) + 0.12 * k
        if t >= at:
            q = eout((t - at) / 0.3)
            place(f, face_circle(p, box, 250), cx, 600, q, 0.8 + 0.2 * q)
            line(f, nm, 38, WHITE, 770, t, at + 0.1, weight="xb", cx=cx, maxw=280)
    put_icon(f, "medal", 540, 990, 300 if t >= r(103) else 420, t, C[12] + 0.05)
    line(f, "NOBEL ÖDÜLÜ", 78, GOLD, 1205, t, r(105))

def s13(f, t, lt, dur):  # FİNAL
    card(f, FL_COLOR, lt, dur, "in", 0.06, focus=(0.5, 0.5))
    line(f, "BEYİN KODU #9", 84, GOLD, 905, t, r(107), fade=0.4)
    fo = clamp(1 - (t - (r(118) - 0.25)) / 0.3)
    if fo > 0:
        for s, y, at, col in [("Herkesin çöp gördüğü yerde,", 1005, r(110), WHITE), ("meraklı zihin", 1080, r(114), WHITE), ("keşif görür.", 1155, r(116), GOLD)]:
            if t >= at:
                place(f, text(s, 58, col, "xb", 0, (0, 0, 0), True, 820), W / 2, y, clamp((t - at) / 0.35) * fo)
    if t >= r(118):
        place(f, text("En büyük tesadüfün neydi?", 56, WHITE, "xb", 0, (0, 0, 0), True, 820), W / 2, 1010, clamp((t - r(118)) / 0.35))
        if t >= r(124): place(f, text("ŞANS MI?", 64, GOLD, "black"), 330, 1110, clamp((t - r(124)) / 0.3))
        if t >= r(126): place(f, text("MERAK MI?", 64, TURQ, "black"), 750, 1110, clamp((t - r(126)) / 0.3))
        if t >= r(126) + 0.2: place(f, icon("arrow", 80), W / 2, 1222, clamp((t - r(126) - 0.2) / 0.3))

SCENES = [s0, s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12, s13]
NOSUB = {0, 13}
DROP = {7, 9, 10, 15, 16, 17, 18, 53, 54, 56, 57, 78, 19, 20, 30, 35, 36, 37, 43, 44, 45, 46, 52, 55, 58, 62, 63, 64, 68, 71, 72, 73, 75, 76, 77, 79, 80, 83,
        86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 105}

def frame(t):
    i = max(k for k in range(len(SCENES)) if C[k] <= t)
    f = background(t)
    SCENES[i](f, t, t - C[i], C[i + 1] - C[i])
    f *= VIG
    return np.clip(f, 0, 255).astype(np.uint8)

def scene_of(t): return max(k for k in range(len(SCENES)) if C[k] <= t)
