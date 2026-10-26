#!/usr/bin/env python3
"""Beyin Kodu Lab 9:16 bulut motoru (reels_engine v4.1 tarifleriyle uyumlu çekirdek).
cv2 + PIL; kart, rozet, yazı, ikon, damga, sayaç, cam panel, arka plan."""
import functools, math, os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
NAVY = (11, 21, 48); GOLD = (255, 212, 0); TURQ = (60, 200, 208)
RED = (229, 57, 53); GREEN = (46, 204, 113); WHITE = (255, 255, 255)
CX, CY, CW, CH = 84, 272, 912, 1018  # kart
FD = "/usr/share/fonts/opentype/inter/"
FONT = {"black": FD + "Inter-Black.otf", "xb": FD + "Inter-ExtraBold.otf", "bold": FD + "Inter-Bold.otf",
        "semi": FD + "Inter-SemiBold.otf", "med": FD + "Inter-Medium.otf"}

def ease(x): x = min(max(x, 0.0), 1.0); return x * x * (3 - 2 * x)
def eout(x): x = min(max(x, 0.0), 1.0); return 1 - (1 - x) ** 3
def clamp(x, a=0.0, b=1.0): return min(max(x, a), b)

def tr_upper(s): return s.replace("i", "İ").replace("ı", "I").upper()

# ---------------- kompozisyon
def over(dst, rgba, x, y, alpha=1.0):
    """dst: HxWx3 float32; rgba: hxwx4 float32 (0-255). x,y sol üst (int)."""
    if alpha <= 0.003: return
    h, w = rgba.shape[:2]
    x0, y0 = max(int(x), 0), max(int(y), 0)
    x1, y1 = min(int(x) + w, dst.shape[1]), min(int(y) + h, dst.shape[0])
    if x1 <= x0 or y1 <= y0: return
    src = rgba[y0 - int(y):y1 - int(y), x0 - int(x):x1 - int(x)]
    a = src[..., 3:4] * (alpha / 255.0)
    reg = dst[y0:y1, x0:x1]
    reg *= (1 - a); reg += src[..., :3] * a

def place(dst, rgba, cx, cy, alpha=1.0, scale=1.0, rot=0.0):
    if alpha <= 0.003: return
    if abs(scale - 1) > 1e-3 or abs(rot) > 1e-3:
        h, w = rgba.shape[:2]
        if abs(rot) > 1e-3:
            M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, scale)
            c, s = abs(M[0, 0]), abs(M[0, 1]); nw, nh = int(h * s + w * c) + 2, int(h * c + w * s) + 2
            M[0, 2] += nw / 2 - w / 2; M[1, 2] += nh / 2 - h / 2
            rgba = cv2.warpAffine(rgba, M, (nw, nh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        else:
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            rgba = cv2.resize(rgba, (nw, nh), interpolation=cv2.INTER_LINEAR if scale > 1 else cv2.INTER_AREA)
    h, w = rgba.shape[:2]
    over(dst, rgba, cx - w / 2, cy - h / 2, alpha)

def pil2np(im): return np.asarray(im.convert("RGBA"), dtype=np.float32)

@functools.lru_cache(maxsize=512)
def text(s, size, color=WHITE, weight="black", stroke=0, scol=(0, 0, 0), shadow=True, maxw=0):
    f = ImageFont.truetype(FONT[weight], size)
    while maxw and f.getlength(s) > maxw and size > 20:
        size -= 2; f = ImageFont.truetype(FONT[weight], size)
    l, t, r, b = f.getbbox(s, stroke_width=stroke)
    pad = 24 + stroke
    im = Image.new("RGBA", (r - l + 2 * pad, b - t + 2 * pad), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - l, pad - t + 6), s, font=f, fill=(0, 0, 0, 170), stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(8)))
    ImageDraw.Draw(im).text((pad - l, pad - t), s, font=f, fill=color + (255,), stroke_width=stroke, stroke_fill=scol + (255,))
    return pil2np(im)

@functools.lru_cache(maxsize=128)
def icon(name, size):
    im = Image.open(f"ic/{name}.png").convert("RGBA").resize((size, size), Image.LANCZOS)
    return pil2np(im)

def put_icon(dst, name, cx, cy, size, t, at, bounce=True, alpha=1.0, rot=0.0):
    if t < at: return
    k = t - at
    a = clamp(k / 0.18) * alpha
    sc = 1.0
    if bounce:
        sc = 0.6 + 0.4 * eout(k / 0.22) + (0.12 * math.sin(clamp((k - 0.22) / 0.25) * math.pi) if k > 0.22 else 0)
    place(dst, icon(name, size), cx, cy, a, sc, rot)

def rrect_mask(w, h, r):
    m = Image.new("L", (w, h), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    return np.asarray(m, dtype=np.float32)[..., None] / 255.0

@functools.lru_cache(maxsize=64)
def pill(s, size=40, bg=GOLD, fg=NAVY, padx=34, pady=16, weight="black", maxw=620, alpha_bg=255):
    f = ImageFont.truetype(FONT[weight], size)
    while f.getlength(s) + 2 * padx > maxw and size > 22:
        size -= 2; f = ImageFont.truetype(FONT[weight], size)
    l, t, r, b = f.getbbox(s); tw, th = r - l, b - t
    w, h = int(tw + 2 * padx), int(th + 2 * pady)
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((20, 26, 20 + w, 26 + h), h // 2, fill=(0, 0, 0, 140))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((20, 20, 20 + w, 20 + h), h // 2, fill=bg + (alpha_bg,))
    d.text((20 + padx - l, 20 + pady - t), s, font=f, fill=fg + (255,))
    return pil2np(im)

BADGE = {"n": (GOLD, NAVY), "neg": (RED, WHITE), "win": (GREEN, NAVY), "sci": (TURQ, NAVY)}
def badge(dst, s, kind="n", t=1.0, at=0.0):
    if t < at: return
    bg, fg = BADGE[kind]
    a = clamp((t - at) / 0.15)
    place(dst, pill(s, 46, bg, fg, 40, 18), W / 2, 215, a, 0.92 + 0.08 * eout((t - at) / 0.2))

@functools.lru_cache(maxsize=32)
def stamp_img(s, col, size=78):
    f = ImageFont.truetype(FONT["black"], size)
    l, t, r, b = f.getbbox(s); tw, th = r - l, b - t
    w, h = tw + 70, th + 50
    im = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((10, 10, 10 + w, 10 + h), 18, fill=(11, 21, 48, 150), outline=col + (255,), width=9)
    d.text((10 + 35 - l, 10 + 25 - t), s, font=f, fill=col + (255,))
    return pil2np(im)

def stamp(dst, s, col, cx, cy, t, at, rot=-6, size=78):
    if t < at: return
    k = t - at
    sc = 1.35 - 0.35 * eout(k / 0.16)
    place(dst, stamp_img(s, col, size), cx, cy, clamp(k / 0.08), sc, rot)

# ---------------- arka plan
_BG = None
def background(t):
    global _BG
    if _BG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W / 2) / W) ** 2 + ((yy - H * 0.42) / H) ** 2)
        g = np.clip(1.0 - d * 1.25, 0, 1)[..., None]
        base = np.array(NAVY, np.float32); hi = np.array((26, 44, 92), np.float32)
        _BG = base * (1 - g) + hi * g
        rng = np.random.default_rng(7)
        background.parts = rng.random((46, 4))
    f = _BG.copy()
    for px, py, ps, pv in background.parts:
        x = (px * W + t * (8 + 14 * pv)) % W; y = (py * H - t * (10 + 20 * ps)) % H
        cv2.circle(f, (int(x), int(y)), int(2 + 3 * ps), (60 + 40 * pv, 80 + 40 * pv, 130 + 40 * pv), -1, cv2.LINE_AA)
    return f

# ---------------- kart (fotoğraf)
CARD_MASK = rrect_mask(CW, CH, 56)
_border = Image.new("RGBA", (CW + 40, CH + 40), (0, 0, 0, 0))
_sh = Image.new("RGBA", _border.size, (0, 0, 0, 0))
ImageDraw.Draw(_sh).rounded_rectangle((20, 30, 20 + CW, 30 + CH), 56, fill=(0, 0, 0, 160))
_sh = _sh.filter(ImageFilter.GaussianBlur(16))
CARD_SHADOW = pil2np(_sh)
ImageDraw.Draw(_border).rounded_rectangle((20, 20, 20 + CW - 1, 20 + CH - 1), 56, outline=GOLD + (255,), width=5)
CARD_BORDER = pil2np(_border)

@functools.lru_cache(maxsize=16)
def card_base(path, bw=False, cover=False, focus=(0.5, 0.5), grad=True, tone=None, margin=1.10):
    """Fotoğraf kart görüntüsü (contain + bulanık dolgu). margin: hareket payı için büyük üretim."""
    im = Image.open(path).convert("RGB")
    if bw: im = im.convert("L").convert("RGB")
    bw_, bh_ = int(CW * margin), int(CH * margin)
    # bulanık dolgu
    s = max(bw_ / im.width, bh_ / im.height)
    fill = im.resize((int(im.width * s) + 2, int(im.height * s) + 2), Image.LANCZOS)
    fx, fy = (fill.width - bw_) // 2, (fill.height - bh_) // 2
    fill = fill.crop((fx, fy, fx + bw_, fy + bh_)).filter(ImageFilter.GaussianBlur(28))
    fill = Image.blend(fill, Image.new("RGB", fill.size, NAVY), 0.45)
    if cover:
        s = max(bw_ / im.width, bh_ / im.height)
    else:
        s = min(bw_ / im.width, bh_ / im.height)
    ph = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.2, 60, 2))
    ox = int((bw_ - ph.width) * focus[0]); oy = int((bh_ - ph.height) * focus[1])
    fill.paste(ph, (ox, oy))
    a = np.asarray(fill, np.float32)
    if tone is not None:
        a = a * 0.72 + np.array(tone, np.float32) * 0.28
    if grad:
        yy = np.linspace(0, 1, bh_)[:, None, None]
        g = np.clip((yy - 0.45) / 0.55, 0, 1) ** 1.3 * 0.88
        a = a * (1 - g) + np.array(NAVY, np.float32) * g
    return a

def card(dst, path, lt, dur, motion="in", amp=0.04, alpha=1.0, **kw):
    base = card_base(path, **kw)
    bh_, bw_ = base.shape[:2]
    p = ease(lt / max(dur, 0.1))
    s0 = CW / bw_
    if motion == "in": sc = s0 * (1.0 + amp * p)
    elif motion == "out": sc = s0 * (1.0 + amp * (1 - p))
    else: sc = s0 * (1.0 + amp * 0.5)
    dx = dy = 0.0
    if motion == "panx": dx = (p - 0.5) * 40
    if motion == "pany": dy = (p - 0.5) * 40
    M = np.array([[sc, 0, CW / 2 - bw_ / 2 * sc + dx], [0, sc, CH / 2 - bh_ / 2 * sc + dy]], np.float32)
    img = cv2.warpAffine(base, M, (CW, CH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    over(dst, CARD_SHADOW, CX - 20, CY - 20, alpha)
    rgba = np.concatenate([img, CARD_MASK * 255], axis=2)
    over(dst, rgba, CX, CY, alpha)
    over(dst, CARD_BORDER, CX - 20, CY - 20, alpha)

def glass_panel(dst, alpha=1.0, tint=(26, 44, 92)):
    p = np.zeros((CH, CW, 4), np.float32); p[..., :3] = tint; p[..., 3] = 150
    p[..., 3:4] *= CARD_MASK
    over(dst, CARD_SHADOW, CX - 20, CY - 20, alpha * 0.6)
    over(dst, p, CX, CY, alpha)
    over(dst, CARD_BORDER, CX - 20, CY - 20, alpha)

def credit(dst, s, alpha=0.9):
    place(dst, text(s, 24, (220, 226, 240), "med", 0, shadow=True), W / 2, CY + CH - 34, alpha)

def line(dst, s, size, color, cy, t, at, weight="black", maxw=840, pulse_at=None, fade=0.18, cx=W / 2, until=None):
    if t < at: return
    a = clamp((t - at) / fade)
    if until is not None and t > until: a *= clamp(1 - (t - until) / 0.2)
    sc = 0.94 + 0.06 * eout((t - at) / 0.22)
    if pulse_at is not None and t >= pulse_at:
        sc *= 1 + 0.07 * math.sin(clamp((t - pulse_at) / 0.3) * math.pi)
    place(dst, text(s, size, color, weight, 0, shadow=True, maxw=maxw), cx, cy, a, sc)

def flash(dst, t, at, dur=0.25, strength=0.55):
    if at <= t < at + dur:
        k = 1 - (t - at) / dur
        dst *= (1 - strength * k); dst += 255 * strength * k

def vignette_cache():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * 0.8)) ** 2 + ((yy - H / 2) / (H * 0.8)) ** 2)
    return np.clip(1 - 0.35 * d ** 2, 0.55, 1)[..., None]
VIG = vignette_cache()
