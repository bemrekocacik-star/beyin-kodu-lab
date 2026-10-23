"""Beyin Kodu Lab - Cinematic Story Engine 16:9 (bulut yedek motoru: Python + OpenCV + FFmpeg)
Kullanim: python3 engine.py timeline.json out.mp4 [--scale 0.5] [--frames a-b] [--stills t1,t2,...]
Tum yerlesimler 1920x1080 koordinatinda tasarlanir, --scale ile kucultulur.
"""
import json, sys, os, math, subprocess, argparse, functools, shutil
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont


def _find_font_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    for d in (os.environ.get("BKL_FONTS", ""), os.path.join(here, "fonts"), "/usr/share/fonts/opentype/inter"):
        if d and os.path.isfile(os.path.join(d, "InterDisplay-Black.otf")):
            return d + os.sep
    sys.exit("Inter fontlari bulunamadi (fonts klasoru).")


def imread(path, flags=cv2.IMREAD_COLOR):
    """Windows'ta Turkce karakterli yollar icin guvenli okuma."""
    data = np.fromfile(path, dtype=np.uint8)
    im = cv2.imdecode(data, flags) if data.size else None
    if im is None:
        raise FileNotFoundError(path)
    return im


def imwrite(path, img):
    ok, buf = cv2.imencode(os.path.splitext(path)[1] or ".jpg", img)
    buf.tofile(path)


FONT_DIR = _find_font_dir()
def _find_ffmpeg():
    p = os.environ.get("BKL_FFMPEG")
    if p and os.path.isfile(p):
        return p
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg_yolu.txt")
    if os.path.isfile(f):
        p = open(f, encoding="utf-8-sig").read().strip()
        if os.path.isfile(p):
            return p
    return shutil.which("ffmpeg") or "ffmpeg"


FFMPEG = _find_ffmpeg()
F_BLACK = FONT_DIR + "InterDisplay-Black.otf"
F_BOLD = FONT_DIR + "Inter-Bold.otf"
F_SEMI = FONT_DIR + "Inter-SemiBold.otf"
F_MED = FONT_DIR + "Inter-Medium.otf"

YELLOW = (24, 197, 245)      # BGR  #F5C518
TEAL = (208, 224, 63)        # BGR  #3FE0D0
WHITE = (255, 255, 255)
SAFE_X, SAFE_Y = 96, 54
QC = {"safe_violations": []}


# ---------- yardimcilar ----------
def ease(t):
    t = min(max(t, 0.0), 1.0)
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2

def ease_out(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3

def lerp(a, b, t):
    return a + (b - a) * t

def prog(t, a, b):
    return min(max((t - a) / (b - a), 0.0), 1.0) if b > a else float(t >= a)

HQ = {"on": False}   # final render: kubik ornekleme


@functools.lru_cache(maxsize=10)
def _load_enhanced(path):
    """Arsiv fotografi iyilestirme: kucukse Lanczos ile buyut, hafif gurultu azaltma,
    CLAHE ile yerel kontrast, olculu keskinlestirme (unsharp mask). Bir kez hesaplanir."""
    im = imread(path)
    h, w = im.shape[:2]
    long_side = max(h, w)
    if long_side < 1800:
        k = 1800 / long_side
        im = cv2.resize(im, (int(w * k), int(h * k)), interpolation=cv2.INTER_LANCZOS4)
    im = cv2.bilateralFilter(im, 5, 18, 5)
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8))
    lab[..., 0] = clahe.apply(lab[..., 0])
    im = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR).astype(np.float32) / 255.0
    blur = cv2.GaussianBlur(im, (0, 0), 1.6)
    im = np.clip(im + 0.45 * (im - blur), 0, 1)
    im.setflags(write=False)
    return im


def load(path, enhance=True):
    if enhance and path.lower().endswith((".jpg", ".jpeg")):
        return _load_enhanced(path).copy()
    return imread(path).astype(np.float32) / 255.0


class Canvas:
    def __init__(self, W, H, s):
        self.W, self.H, self.s = W, H, s

    def place(self, img, scale, cx, cy, angle=0.0, border=cv2.BORDER_REFLECT101):
        """img'yi (1920 koordinatinda) cx,cy merkezine scale ile yerlestir."""
        sc = scale * self.s
        if sc < 0.8:  # mipmap: once alan-ortalamasiyla kucult -> yavas zoomda titreme/moire olmaz
            k = round(min(1.0, sc * 1.25), 2)
            key = (id(img), k)
            cache = self.__dict__.setdefault("_mip", {})
            if key not in cache:
                if len(cache) > 48:
                    cache.clear()
                cache[key] = (img, cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_AREA))
            img = cache[key][1]
            sc = sc / k
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, sc)
        M[0, 2] += cx * self.s - w / 2
        M[1, 2] += cy * self.s - h / 2
        fl = cv2.INTER_CUBIC if HQ["on"] else cv2.INTER_LINEAR
        return cv2.warpAffine(img, M, (self.W, self.H), flags=fl, borderMode=border)

    def cover(self, img):
        h, w = img.shape[:2]
        return max(1920 / w, 1080 / h)


# ---------- metin ----------
@functools.lru_cache(maxsize=160)
def text_rgba(text, font, size, color_bgr, tracking=0, scale=1.0, shadow=0):
    """Metni premultiplied BGRA float32 dizisi olarak dondurur (cache'li)."""
    px = max(1, int(round(size * scale)))
    f = ImageFont.truetype(font, px)
    tr = tracking * scale
    widths = [f.getlength(ch) for ch in text]
    asc, desc = f.getmetrics()
    W = int(sum(widths) + tr * max(len(text) - 1, 0)) + 4
    H = asc + desc + 4
    pad = int(shadow * scale * 3) + 2
    im = Image.new("L", (W + 2 * pad, H + 2 * pad), 0)
    d = ImageDraw.Draw(im)
    x = pad
    for ch, cw in zip(text, widths):
        d.text((x, pad), ch, font=f, fill=255)
        x += cw + tr
    a = np.asarray(im, np.float32) / 255.0
    col = np.array(color_bgr, np.float32) / 255.0
    rgb = a[..., None] * col
    if shadow:
        sh = cv2.GaussianBlur(a, (0, 0), shadow * scale)
        sh = np.roll(np.roll(sh, int(2 * scale), 0), int(2 * scale), 1) * 0.85
        alpha = a + sh * (1 - a)
        rgb = rgb  # shadow is black: contributes alpha only
    else:
        alpha = a
    out = np.dstack([rgb, alpha]).astype(np.float32)
    out.setflags(write=False)
    return out, pad


def over(dst, rgba, x, y, opacity=1.0, check_safe=True, s=1.0, tag="", pad=0):
    """Premultiplied rgba'yi dst uzerine (x,y piksel, olcekli koordinat) bindir."""
    if opacity <= 0.001:
        return
    h, w = rgba.shape[:2]
    x, y = int(round(x)), int(round(y))
    H, W = dst.shape[:2]
    if check_safe and opacity > 0.5:
        sx, sy = SAFE_X * s, SAFE_Y * s
        gx0, gy0, gx1, gy1 = x + pad, y + pad, x + w - pad, y + h - pad
        if gx0 < sx - 4 * s or gy0 < sy - 4 * s or gx1 > W - sx + 4 * s or gy1 > H - sy + 4 * s:
            QC["safe_violations"].append(tag)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[..., 3:4] * opacity
    dst[y0:y1, x0:x1] = dst[y0:y1, x0:x1] * (1 - a) + src[..., :3] * opacity


def draw_text(cv, dst, text, font, size, color, x, y, opacity=1.0, tracking=0, anchor="lt", shadow=6, check_safe=True, tag=None, reveal=None):
    """x,y 1920 koordinatinda; anchor: lt (sol-ust) | mt (orta-ust).
    reveal (0..1): metin gorunmez bir maskenin altindan yukselerek girer (profesyonel belgesel girisi)."""
    rgba, pad = text_rgba(text, font, size, color, tracking, cv.s, shadow)
    if reveal is not None:
        r = ease_out(reveal)
        if r <= 0.001:
            return 0, 0
        if r < 0.999:
            h = rgba.shape[0]
            dy = int((1 - r) * h * 0.9)
            sh = np.zeros_like(rgba)
            sh[dy:] = rgba[:h - dy]
            rgba = sh
        opacity = opacity * min(1.0, r * 1.6)
    px, py = x * cv.s - pad, y * cv.s - pad
    if anchor == "mt":
        px = x * cv.s - rgba.shape[1] / 2
    over(dst, rgba, px, py, opacity, check_safe, cv.s, tag or text, pad)
    return rgba.shape[1] / cv.s, rgba.shape[0] / cv.s


def text_width(text, font, size, tracking=0):
    f = ImageFont.truetype(font, size)
    return sum(f.getlength(c) for c in text) + tracking * max(len(text) - 1, 0)


# ---------- renk & doku ----------
def grade(img, mode):
    if mode == "bw_cool":
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        g = np.clip((g - 0.5) * 1.12 + 0.48, 0, 1)
        out = np.dstack([g * 1.03 + 0.012, g * 1.0, g * 0.95])
        return np.clip(out, 0, 1)
    if mode == "warm":
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        g = np.clip((g - 0.5) * 1.08 + 0.52, 0, 1)
        out = np.dstack([g * 0.78, g * 0.95, np.clip(g * 1.08 + 0.03, 0, 1)])
        return out
    if mode == "teal":
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        g = np.clip((g - 0.45) * 1.35 + 0.45, 0, 1)
        lo = np.array([0.09, 0.06, 0.01]); mid = np.array([0.82, 0.88, 0.25]); hi = np.array([1.0, 1.0, 0.92])
        t = g[..., None]
        out = np.where(t < 0.6, lo + (mid - lo) * (t / 0.6), mid + (hi - mid) * ((t - 0.6) / 0.4))
        return out.astype(np.float32)
    if mode == "desat":
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[..., None]
        return img * 0.65 + g * 0.35
    return img


class FX:
    def __init__(self, W, H, seed=7):
        rng = np.random.default_rng(seed)
        hw, hh = W // 2, H // 2
        self.grain = [cv2.resize(rng.normal(0, 1, (hh, hw)).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR) for _ in range(12)]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        self.vig = np.clip(1 - 0.42 * np.clip(r - 0.45, 0, None) ** 1.6, 0, 1)[..., None].astype(np.float32)
        self.xx, self.yy = xx, yy
        self.W, self.H = W, H
        # sol koyu gradyan (metin okunurlugu)
        gx = np.clip(1 - xx / (W * 0.62), 0, 1) ** 1.4
        self.left_dark = (1 - 0.78 * gx)[..., None].astype(np.float32)
        # alt gradyan (altyazi)
        gy = np.clip((yy - H * 0.70) / (H * 0.30), 0, 1) ** 1.5
        self.bottom_dark = (1 - 0.55 * gy)[..., None].astype(np.float32)

    def apply_grain(self, img, frame, amt=0.035):
        g = self.grain[frame % 12]
        if frame % 2:
            g = g[::-1]
        return img + g[..., None] * amt

    def circle_mask(self, cx, cy, r, feather=2.0):
        d = np.sqrt((self.xx - cx) ** 2 + (self.yy - cy) ** 2)
        return np.clip((r - d) / feather + 0.5, 0, 1)[..., None]


# ---------- sahneler ----------
class Scene:
    def __init__(self, spec, cv, fx):
        self.spec, self.cv, self.fx = spec, cv, fx
        self.p = spec.get("params", {})
        self.d = spec.get("duration", spec.get("end", 0) - spec.get("start", 0))
        self.setup()

    def setup(self):
        pass

    def caption(self, img, t):
        cap = self.spec.get("caption")
        if not cap:
            return
        a = prog(t, 0.4, 1.0) * (1 - prog(t, self.d - 0.5, self.d))
        s = self.cv.s
        hh, ww = int(78 * s), min(img.shape[1], int((SAFE_X + 30 + text_width(cap, F_MED, 19, 1.2)) * s))
        g = np.linspace(1, 0, ww, dtype=np.float32)[None, :, None] ** 0.6 * np.linspace(1, 0, hh, dtype=np.float32)[:, None, None]
        img[:hh, :ww] *= (1 - 0.45 * a * g)   # aciklama okunabilsin diye hafif koyu zemin
        draw_text(self.cv, img, cap, F_MED, 19, (225, 225, 225), SAFE_X, SAFE_Y, opacity=0.72 * a, tracking=1.2, shadow=4)


_TEX = {}
def navy_bg(cv, fx, t, glow=(0.10, 0.06, 0.02), center=(0.5, 0.45)):
    W, H = cv.W, cv.H
    base = np.array([0.075, 0.040, 0.020], np.float32)
    cx = center[0] + 0.03 * math.sin(t * 0.35)
    cy = center[1] + 0.02 * math.cos(t * 0.27)
    d = np.sqrt(((fx.xx - W * cx) / W) ** 2 + ((fx.yy - H * cy) / H) ** 2)
    g = np.clip(1 - d * 1.6, 0, 1)[..., None] ** 2
    if (W, H) not in _TEX:
        rng = np.random.default_rng(77)
        n = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 2.5 * cv.s + 0.5)
        _TEX[(W, H)] = (n / (np.abs(n).max() + 1e-6))[..., None] * 0.012
    return (base + g * np.array(glow, np.float32) + _TEX[(W, H)]).astype(np.float32)


def dust(cv, img, t, n=70, seed=3, color=(0.75, 0.85, 1.0), amt=0.25):
    rng = np.random.default_rng(seed)
    xs = rng.uniform(0, 1920, n); ys = rng.uniform(0, 1080, n)
    sp = rng.uniform(4, 18, n); ph = rng.uniform(0, 6.28, n); sz = rng.uniform(1.2, 3.2, n)
    layer = np.zeros(img.shape[:2], np.float32)
    for i in range(n):
        x = (xs[i] + t * sp[i]) % 1920
        y = (ys[i] - t * sp[i] * 0.4 + 8 * math.sin(t * 0.7 + ph[i])) % 1080
        a = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 1.3 + ph[i]))
        cv2.circle(layer, (int(x * cv.s), int(y * cv.s)), max(1, int(sz[i] * cv.s)), a, -1, cv2.LINE_AA)
    layer = cv2.GaussianBlur(layer, (0, 0), 1.2 * cv.s + 0.3)
    img += layer[..., None] * np.array(color, np.float32) * amt


class YearCard(Scene):
    def render(self, t, f):
        cv, fx = self.cv, self.fx
        img = navy_bg(cv, fx, t)
        dust(cv, img, t)
        zoom = lerp(1.0, 1.04, ease(t / self.d))
        year = self.p["year"]
        size = 330 * zoom
        a = ease_out(prog(t, 0.15, 1.1))
        sc = lerp(1.10, 1.0, ease_out(prog(t, 0.15, 1.3)))
        sz = size * sc
        w = text_width(year, F_BLACK, sz, 6 * sc)
        draw_text(cv, img, year, F_BLACK, sz, YELLOW, 960 - w / 2, 540 - sz * 0.62, opacity=a, tracking=6 * sc, shadow=10)
        # cizgi
        lw = 560 * ease(prog(t, 0.8, 1.7)) * zoom
        y = int((540 + 150 * zoom) * cv.s)
        cv2.line(img, (int((960 - lw / 2) * cv.s), y), (int((960 + lw / 2) * cv.s), y), np.array(YELLOW) / 255.0, max(1, int(4 * cv.s)), cv2.LINE_AA)
        k = self.p["kicker"]
        ka = ease(prog(t, 1.1, 1.8))
        kw = text_width(k, F_SEMI, 30, 10)
        draw_text(cv, img, k, F_SEMI, 30, (235, 235, 235), 960 - kw / 2, 540 - 255 * zoom, opacity=0.8 * ka, tracking=10)
        return img


class CardCounter(Scene):
    def setup(self):
        src = load(self.spec["visualAssets"][0])
        self.card = grade(src, "desat")
        bg = cv2.GaussianBlur(src, (0, 0), 22)
        self.bg = bg * 0.30
        h, w = src.shape[:2]
        # golge
        pad = 80
        sh = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
        sh[pad:pad + h, pad:pad + w] = 1
        self.shadow = cv2.GaussianBlur(sh, (0, 0), 28)
        self.pad = pad

    def render(self, t, f):
        cv, fx = self.cv, self.fx
        u = ease(t / self.d)
        img = cv.place(self.bg, cv.cover(self.bg) * lerp(1.15, 1.10, u), lerp(1000, 920, u), 540)
        sc = lerp(1.06, 1.12, u)
        ang = lerp(-4.0, -2.2, u)
        cx, cy = lerp(545, 570, u), lerp(545, 535, u)
        sh = cv.place(self.shadow, sc, cx + 18, cy + 26, ang, border=cv2.BORDER_CONSTANT)
        img *= (1 - 0.75 * sh[..., None])
        # kart (alfa ile)
        h, w = self.card.shape[:2]
        alpha = np.ones((h, w), np.float32)
        card = cv.place(self.card, sc, cx, cy, ang, border=cv2.BORDER_CONSTANT)
        am = cv.place(alpha, sc, cx, cy, ang, border=cv2.BORDER_CONSTANT)[..., None]
        img = img * (1 - am) + card * am
        # sayac
        v = int(round(self.p["value"] * ease_out(prog(t, 0.5, 2.6)) / 100.0) * 100)
        num = self.p["prefix"] + f"{v:,}".replace(",", ".")
        na = ease_out(prog(t, 0.35, 0.9))
        draw_text(cv, img, self.p["label"], F_BOLD, 40, WHITE, 1110, 385, opacity=na, tracking=4)
        draw_text(cv, img, num, F_BLACK, 140, YELLOW, 1100, 432, opacity=na, tracking=2, shadow=10)
        draw_text(cv, img, self.p["sub"], F_MED, 30, (230, 230, 230), 1112, 615, opacity=0.75 * ease(prog(t, 1.0, 1.6)), tracking=6)
        bar = 420 * ease(prog(t, 0.6, 2.6))
        cv2.rectangle(img, (int(1112 * cv.s), int(675 * cv.s)), (int((1112 + bar) * cv.s), int(681 * cv.s)), np.array(YELLOW) / 255.0, -1)
        self.caption(img, t)
        return img


class ArchivalPush(Scene):
    def setup(self):
        self.img = grade(load(self.spec["visualAssets"][0]), self.p.get("grade", "bw_cool"))

    def render(self, t, f):
        cv, p = self.cv, self.p
        u = ease(t / self.d)
        base = self.cv.cover(self.img)
        z = lerp(p["z0"], p["z1"], u)
        cx = 960 + 1920 * lerp(p["x0"], p["x1"], u)
        cy = 540 + 1080 * lerp(p.get("y0", 0), p.get("y1", 0), u)
        img = cv.place(self.img, base * z, cx, cy)
        img *= self.fx.bottom_dark
        self.caption(img, t)
        return img


class Microscope(Scene):
    def setup(self):
        src = load(self.spec["visualAssets"][0])
        self.em = grade(src, "teal")
        self.cx, self.cy, self.r = 1290, 470, 350

    def render(self, t, f):
        cv, fx = self.cv, self.fx
        u = ease(t / self.d)
        img = navy_bg(cv, fx, t, glow=(0.16, 0.13, 0.02), center=(0.66, 0.48))
        # ince izgara
        step = int(80 * cv.s)
        grid = np.zeros(img.shape[:2], np.float32)
        off = int((t * 6) * cv.s) % step
        grid[:, off::step] = 1; grid[off::step, :] = 1
        img += grid[..., None] * np.array([0.05, 0.05, 0.01], np.float32)
        dust(cv, img, t, n=40, seed=11, color=(0.9, 1.0, 0.4), amt=0.18)
        # mikroskop gorusu
        z = lerp(1.0, 1.28, u)
        em = cv.place(self.em, (2 * self.r / self.em.shape[1]) * 1.25 * z, self.cx, self.cy, angle=lerp(0, 7, u))
        m = fx.circle_mask(self.cx * cv.s, self.cy * cv.s, self.r * cv.s, 2.0)
        # kenarda hafif karartma (lens)
        d = np.sqrt((fx.xx - self.cx * cv.s) ** 2 + (fx.yy - self.cy * cv.s) ** 2) / (self.r * cv.s)
        lens = np.clip(1 - 0.55 * np.clip(d - 0.55, 0, None) ** 1.5 * 2.2, 0.2, 1)[..., None]
        img = img * (1 - m) + em * lens * m
        # tarama cizgisi
        sy = (self.cy - self.r) + 2 * self.r * ((t * 0.45) % 1.0)
        band = np.exp(-((fx.yy - sy * cv.s) / (10 * cv.s)) ** 2)[..., None] * m
        img += band * np.array([0.10, 0.12, 0.03], np.float32)
        # halka + parilti
        ring = np.zeros(img.shape[:2], np.float32)
        cv2.circle(ring, (int(self.cx * cv.s), int(self.cy * cv.s)), int((self.r + 6) * cv.s), 1.0, max(1, int(3 * cv.s)), cv2.LINE_AA)
        # tik isaretleri (donen)
        for i in range(72):
            a = math.radians(i * 5 + t * 8)
            r1 = self.r + 22; r2 = r1 + (16 if i % 6 == 0 else 7)
            p1 = (int((self.cx + r1 * math.cos(a)) * cv.s), int((self.cy + r1 * math.sin(a)) * cv.s))
            p2 = (int((self.cx + r2 * math.cos(a)) * cv.s), int((self.cy + r2 * math.sin(a)) * cv.s))
            cv2.line(ring, p1, p2, 0.7, max(1, int(2 * cv.s)), cv2.LINE_AA)
        glow = cv2.GaussianBlur(ring, (0, 0), 9 * cv.s)
        teal = np.array(TEAL, np.float32) / 255.0
        img += (ring * 0.9 + glow * 1.4)[..., None] * teal * ease(prog(t, 0.0, 0.8))
        hud = self.p["hud"]
        hw = text_width(hud, F_SEMI, 22, 5)
        draw_text(cv, img, hud, F_SEMI, 22, TEAL, self.cx - hw / 2, self.cy - self.r - 70, opacity=0.9 * ease(prog(t, 0.6, 1.2)), tracking=5, shadow=0)
        # alt bilgi (lower third)
        la = ease_out(prog(t, 0.6, 1.4))
        dx = lerp(-30, 0, la)
        cv2.rectangle(img, (int((SAFE_X + 24 + dx) * cv.s), int(612 * cv.s)), (int((SAFE_X + 30 + dx) * cv.s), int(712 * cv.s)), np.array(YELLOW) / 255.0 * la, -1)
        draw_text(cv, img, self.p["title"], F_BOLD, 46, WHITE, SAFE_X + 50 + dx, 612, reveal=prog(t, 0.6, 1.2), tracking=2)
        draw_text(cv, img, self.p["sub"], F_MED, 30, (225, 225, 225), SAFE_X + 52 + dx, 672, opacity=0.8 * la, tracking=1)
        self.caption(img, t)
        return img


class PortraitParallax(Scene):
    def setup(self):
        src = load(self.spec["visualAssets"][0])
        mask = imread(self.spec["visualAssets"][1], cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
        if mask.shape != src.shape[:2]:  # iyilestirme sirasinda buyutulen fotografa uyumla
            mask = cv2.resize(mask, (src.shape[1], src.shape[0]), interpolation=cv2.INTER_LINEAR)
        h, w = mask.shape
        # arka plan: kisiyi sil (dusuk cozunurlukte inpaint) + bulanik
        sw = 480; sh = int(h * sw / w)
        small = (cv2.resize(src, (sw, sh)) * 255).astype(np.uint8)
        mk = (cv2.dilate(cv2.resize(mask, (sw, sh)), np.ones((9, 9), np.uint8)) > 0.2).astype(np.uint8) * 255
        plate = cv2.inpaint(small, mk, 12, cv2.INPAINT_TELEA).astype(np.float32) / 255.0
        plate = cv2.resize(plate, (w, h), interpolation=cv2.INTER_CUBIC)
        self.bg = cv2.GaussianBlur(grade(plate, "bw_cool"), (0, 0), 14) * 0.42
        self.fg = grade(src, "bw_cool")
        self.mask = mask

    def render(self, t, f):
        cv, fx = self.cv, self.fx
        u = ease(t / self.d)
        bgs = cv.cover(self.bg) * lerp(1.04, 1.08, u)
        img = cv.place(self.bg, bgs, lerp(1010, 960, u), 600)
        # on plan kisi (sag tarafta, daha hizli hareket = derinlik)
        s = (1180 / self.fg.shape[0]) * lerp(1.0, 1.07, u)
        cx, cy = lerp(1300, 1275, u), lerp(560, 548, u)
        fg = cv.place(self.fg, s, cx, cy, border=cv2.BORDER_CONSTANT)
        am = cv.place(self.mask, s, cx, cy, border=cv2.BORDER_CONSTANT)[..., None]
        # kenar isigi (rim) - hafif
        img = img * (1 - am) + fg * am
        img *= fx.left_dark
        # isim (harf harf)
        name = self.p["name"]
        x = SAFE_X + 40
        y = 400
        size = 148
        f_ = ImageFont.truetype(F_BLACK, size)
        cx_ = x
        for i, ch in enumerate(name):
            a = ease_out(prog(t, 0.25 + i * 0.045, 0.65 + i * 0.045))
            dy = lerp(28, 0, a)
            if ch != " ":
                draw_text(cv, img, ch, F_BLACK, size, WHITE, cx_, y + dy, opacity=a, shadow=10, tag="name")
            cx_ += f_.getlength(ch) + 4
        lw = (cx_ - x) * ease(prog(t, 0.9, 1.6))
        cv2.rectangle(img, (int(x * cv.s), int((y + 190) * cv.s)), (int((x + lw) * cv.s), int((y + 197) * cv.s)), np.array(YELLOW) / 255.0, -1)
        draw_text(cv, img, self.p["sub"], F_MED, 36, (230, 230, 230), x + 2, y + 222, opacity=0.85 * ease(prog(t, 1.2, 1.8)), tracking=2)
        self.caption(img, t)
        return img


class ArchivalKinetic(Scene):
    def setup(self):
        self.img = grade(load(self.spec["visualAssets"][0]), self.p.get("grade", "warm"))

    def render(self, t, f):
        cv, fx = self.cv, self.fx
        u = ease(t / self.d)
        img = cv.place(self.img, cv.cover(self.img) * lerp(1.16, 1.04, u), lerp(1000, 980, u), 540)
        img *= fx.left_dark
        y = 360
        for text, kind, t0 in self.p["lines"]:
            a = ease_out(prog(t, t0, t0 + 0.5))
            if kind == "big":
                sc = lerp(1.08, 1.0, a)
                draw_text(cv, img, text, F_BLACK, 104 * sc, YELLOW, SAFE_X + 40, y + lerp(20, 0, a), opacity=a, tracking=1, shadow=12)
                y += 132
            else:
                draw_text(cv, img, text, F_SEMI, 54, WHITE, SAFE_X + 44, y, reveal=prog(t, t0, t0 + 0.55), shadow=8)
                y += 82
        self.caption(img, t)
        return img


class Logo(Scene):
    def setup(self):
        lg = imread(self.spec["visualAssets"][0]).astype(np.float32) / 255.0
        self.logo = lg
        h, w = lg.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt((xx - w / 2) ** 2 + (yy - h / 2) ** 2) / (w / 2)
        self.lmask = np.clip((0.985 - r) / 0.02, 0, 1).astype(np.float32)

    def render(self, t, f):
        cv, fx = self.cv, self.fx
        img = navy_bg(cv, fx, t, glow=(0.02, 0.07, 0.14), center=(0.5, 0.45))
        dust(cv, img, t, n=50, seed=5, color=(0.4, 0.7, 1.0), amt=0.2)
        a = ease_out(prog(t, 0.0, 0.9))
        s = (520 / self.logo.shape[1]) * lerp(0.92, 1.0, a) * lerp(1.0, 1.03, ease(t / self.d))
        lg = cv.place(self.logo, s, 960, 470, border=cv2.BORDER_CONSTANT)
        m = cv.place(self.lmask, s, 960, 470, border=cv2.BORDER_CONSTANT)[..., None] * a
        img = img * (1 - m) + lg * m
        # isik suzulmesi
        sx = lerp(400, 1520, ease(prog(t, 0.9, 1.9)))
        sweep = np.exp(-(((fx.xx - fx.yy * 0.35) - sx * cv.s) / (60 * cv.s)) ** 2)[..., None] * m * 0.35
        img += sweep
        tag = self.p["tag"]
        tw = text_width(tag, F_BOLD, 30, 8)
        draw_text(cv, img, tag, F_BOLD, 30, YELLOW, 960 - tw / 2, 770, opacity=ease(prog(t, 1.0, 1.6)), tracking=8)
        return img



# ===================== EK SAHNE TIPLERI (v2) =====================
def blurred_plate(path, sigma=18, dark=0.32, grade_mode="bw_cool"):
    im = grade(load(path), grade_mode)
    return cv2.GaussianBlur(im, (0, 0), sigma) * dark


def dark_overlay(img, amt):
    return img * (1 - amt)


class ChapterTitle(Scene):
    """BOLUM n + buyuk baslik. Arka plan: bulanik gorsel ya da lacivert."""
    def setup(self):
        a = self.spec.get("visualAssets") or []
        self.bg = blurred_plate(a[0], 20, 0.30) if a else None

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        u = ease(t / self.d)
        if self.bg is not None:
            img = cv.place(self.bg, cv.cover(self.bg) * lerp(1.12, 1.04, u), 960, 540)
        else:
            img = navy_bg(cv, fx, t)
        dust(cv, img, t, n=45, seed=21, amt=0.18)
        k = p.get("num", "")
        a1 = ease_out(prog(t, 0.1, 0.6))
        kw = text_width(k, F_BOLD, 30, 12)
        draw_text(cv, img, k, F_BOLD, 30, YELLOW, 960 - kw / 2, 400, reveal=prog(t, 0.05, 0.55), tracking=12)
        title = p["title"]
        size = p.get("size", 132)
        tr = lerp(40, 8, ease_out(prog(t, 0.25, 1.3)))
        a2 = ease_out(prog(t, 0.25, 0.9))
        tw = text_width(title, F_BLACK, size, tr)
        draw_text(cv, img, title, F_BLACK, size, WHITE, 960 - tw / 2, 450, reveal=prog(t, 0.25, 0.95), tracking=tr, shadow=12)
        lw = 380 * ease(prog(t, 0.7, 1.5))
        y = int(625 * cv.s)
        cv2.line(img, (int((960 - lw / 2) * cv.s), y), (int((960 + lw / 2) * cv.s), y), np.array(YELLOW) / 255.0, max(1, int(3 * cv.s)), cv2.LINE_AA)
        sub = p.get("sub")
        if sub:
            sw = text_width(sub, F_MED, 32, 2)
            draw_text(cv, img, sub, F_MED, 32, (230, 230, 230), 960 - sw / 2, 655, opacity=0.85 * ease(prog(t, 0.9, 1.5)), tracking=2)
        # bolum ilerleme gostergesi (izleyici yapinin neresinde oldugunu gorur)
        tot, idx = p.get("total"), p.get("index")
        if tot:
            seg = 70; gapx = 14; wtot = tot * seg + (tot - 1) * gapx; x0 = 960 - wtot / 2
            pa = ease(prog(t, 0.9, 1.4))
            for i in range(tot):
                col = np.array(YELLOW) / 255.0 if i < idx else (np.array(YELLOW) / 255.0 * 0.35 if i == idx else np.array((0.35, 0.35, 0.35)))
                if i == idx:
                    col = np.array(YELLOW) / 255.0 * (0.4 + 0.6 * ease(prog(t, 1.2, 1.8)))
                xa = x0 + i * (seg + gapx)
                cv2.rectangle(img, (int(xa * cv.s), int(745 * cv.s)), (int((xa + seg) * cv.s), int(751 * cv.s)), col * pa, -1)
        # isik suzulmesi
        sx = lerp(-200, 2100, ease(prog(t, 0.2, 1.6)))
        img += np.exp(-(((fx.xx + fx.yy * 0.5) - sx * cv.s) / (90 * cv.s)) ** 2)[..., None] * 0.06
        return img


class QuoteCard(Scene):
    def setup(self):
        a = self.spec.get("visualAssets") or []
        self.bg = blurred_plate(a[0], 12, 0.30, self.p.get("grade", "bw_cool")) if a else None

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        u = ease(t / self.d)
        if self.bg is not None:
            img = cv.place(self.bg, cv.cover(self.bg) * lerp(1.05, 1.12, u), lerp(980, 940, u), 540)
        else:
            img = navy_bg(cv, fx, t)
        lines = p["quote"].split("\n")
        size = p.get("size", 64)
        lh = size * 1.32
        y0 = 540 - lh * len(lines) / 2 - 20
        draw_text(cv, img, "“", F_BLACK, 220, YELLOW, 150, y0 - 120, opacity=ease_out(prog(t, 0.0, 0.5)), shadow=0)
        for i, ln in enumerate(lines):
            t0 = p.get("t0", 0.25) + i * p.get("step", 0.55)
            a = ease_out(prog(t, t0, t0 + 0.5))
            col = YELLOW if i in p.get("highlight", []) else WHITE
            draw_text(cv, img, ln, F_SEMI if col == WHITE else F_BLACK, size, col, 270, y0 + i * lh, reveal=prog(t, t0, t0 + 0.6), shadow=8)
        who = p.get("who")
        if who:
            ta = p.get("who_t", 0.6 + len(lines) * 0.55)
            draw_text(cv, img, "— " + who, F_MED, 32, (225, 225, 225), 274, y0 + len(lines) * lh + 30, opacity=0.85 * ease(prog(t, ta, ta + 0.5)), tracking=2)
        self.caption(img, t)
        return img


class TimelineYears(Scene):
    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        img = navy_bg(cv, fx, t)
        dust(cv, img, t, n=35, seed=31, amt=0.15)
        items = p["items"]; act = p.get("active", len(items) - 1); prev = p.get("from", max(act - 1, 0))
        x0, x1, y = 230, 1690, 560
        n = len(items)
        xs = [x0 + (x1 - x0) * i / max(n - 1, 1) for i in range(n)]
        s = cv.s
        cv2.line(img, (int(x0 * s), int(y * s)), (int(x1 * s), int(y * s)), (0.35, 0.35, 0.35), max(1, int(3 * s)), cv2.LINE_AA)
        pr = ease(prog(t, 0.3, 1.4))
        xe = lerp(xs[prev], xs[act], pr)
        cv2.line(img, (int(x0 * s), int(y * s)), (int(xe * s), int(y * s)), np.array(YELLOW) / 255.0, max(1, int(5 * s)), cv2.LINE_AA)
        title = p.get("title")
        if title:
            tw = text_width(title, F_BOLD, 34, 8)
            draw_text(cv, img, title, F_BOLD, 34, (235, 235, 235), 960 - tw / 2, 300, opacity=0.85 * ease(prog(t, 0, 0.5)), tracking=8)
        for i, (yr, lab) in enumerate(items):
            on = xs[i] <= xe + 1
            isact = i == act
            r = (16 if isact else 10) * (1 + (0.12 * math.sin(t * 5) if isact and pr >= 1 else 0))
            col = np.array(YELLOW) / 255.0 if on else np.array((0.55, 0.55, 0.55))
            cv2.circle(img, (int(xs[i] * s), int(y * s)), max(2, int(r * s)), col, -1, cv2.LINE_AA)
            ys = 74 if isact else 46
            yw = text_width(yr, F_BLACK, ys, 1)
            draw_text(cv, img, yr, F_BLACK, ys, YELLOW if isact else (200, 200, 200), xs[i] - yw / 2, y - 50 - ys, opacity=1.0 if (on or not isact) else 0.6, tracking=1, shadow=6)
            lw_ = text_width(lab, F_MED, 26, 1)
            la = 1.0 if (on and not isact) else ease(prog(t, 1.2, 1.7)) if isact else 0.55
            draw_text(cv, img, lab, F_MED if not isact else F_BOLD, 26, WHITE, xs[i] - lw_ / 2, y + 34, opacity=la, tracking=1)
        return img


class BarChart(Scene):
    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        img = navy_bg(cv, fx, t, glow=(0.06, 0.05, 0.03))
        s = cv.s
        title = p.get("title", "")
        draw_text(cv, img, title, F_BOLD, 40, WHITE, SAFE_X + 40, 140, reveal=prog(t, 0, 0.6), tracking=3)
        sub = p.get("sub")
        if sub:
            draw_text(cv, img, sub, F_MED, 26, (200, 200, 200), SAFE_X + 42, 196, opacity=0.8 * ease(prog(t, 0.3, 0.8)), tracking=2)
        bars = p["bars"]; vmax = max(b[1] for b in bars)
        base_y, top_y = 860, 330
        n = len(bars); bw = 240; gap = 200; x_left = 960 - (n * bw + (n - 1) * gap) / 2
        for i, (lab, val, disp) in enumerate(bars):
            t0 = 0.5 + i * p.get("step", 0.9)
            g = ease_out(prog(t, t0, t0 + 1.0))
            x = x_left + i * (bw + gap)
            h = max((base_y - top_y) * (val / vmax) * g, 3 * g)
            col = np.array(YELLOW) / 255.0 if i == 0 else np.array(TEAL) / 255.0
            cv2.rectangle(img, (int(x * s), int((base_y - h) * s)), (int((x + bw) * s), int(base_y * s)), col * (0.9 if i else 1.0), -1)
            cur = int(round(val * g))
            txt = f"{cur:,}".replace(",", ".") if disp is None else (disp if g >= 0.999 else f"{cur:,}".replace(",", "."))
            tw = text_width(txt, F_BLACK, 56, 1)
            draw_text(cv, img, txt, F_BLACK, 56, WHITE, x + bw / 2 - tw / 2, base_y - h - 80, opacity=ease(prog(t, t0, t0 + 0.3)), tracking=1, shadow=6)
            lw_ = text_width(lab, F_BOLD, 34, 3)
            draw_text(cv, img, lab, F_BOLD, 34, (230, 230, 230), x + bw / 2 - lw_ / 2, base_y + 22, opacity=ease(prog(t, t0 - 0.3, t0)), tracking=3)
        cv2.line(img, (int((x_left - 60) * s), int(base_y * s)), (int((x_left + n * bw + (n - 1) * gap + 60) * s), int(base_y * s)), (0.6, 0.6, 0.6), max(1, int(2 * s)))
        note = p.get("note")
        if note:
            draw_text(cv, img, note, F_MED, 22, (190, 190, 190), SAFE_X + 42, 1080 - SAFE_Y - 40, opacity=0.7 * ease(prog(t, 2.0, 2.5)), tracking=1)
        return img


def person_icon(img, cx, cy, h, col, s, alpha=1.0):
    head = h * 0.22
    layer = np.zeros(img.shape[:2], np.float32)
    cv2.circle(layer, (int(cx * s), int((cy - h * 0.62) * s)), max(2, int(head * s)), 1.0, -1, cv2.LINE_AA)
    cv2.ellipse(layer, (int(cx * s), int((cy) * s)), (max(2, int(h * 0.33 * s)), max(2, int(h * 0.36 * s))), 0, 180, 360, 1.0, -1, cv2.LINE_AA)
    a = layer[..., None] * alpha
    img[:] = img * (1 - a) + np.array(col, np.float32) * a


class FamilyIcons(Scene):
    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        img = navy_bg(cv, fx, t)
        s = cv.s
        people = p["people"]  # [label, height, t_on]
        n = len(people)
        xs = [960 + (i - (n - 1) / 2) * 300 for i in range(n)]
        glow = np.zeros(img.shape[:2], np.float32)
        for i, (lab, h, ton) in enumerate(people):
            on = ease_out(prog(t, ton, ton + 0.4))
            col = np.array((0.30, 0.30, 0.32)) * (1 - on) + (np.array(YELLOW) / 255.0) * on
            person_icon(img, xs[i], 700, h * 1.4, col, s)
            if on > 0:
                cv2.circle(glow, (int(xs[i] * s), int((700 - h * 0.5) * s)), int(h * 0.75 * s), on, -1)
            lw_ = text_width(lab, F_BOLD, 30, 3)
            draw_text(cv, img, lab, F_BOLD, 30, WHITE, xs[i] - lw_ / 2, 750, opacity=0.35 + 0.65 * on, tracking=3)
        glow = cv2.GaussianBlur(glow, (0, 0), 40 * s)
        img += glow[..., None] * np.array(YELLOW, np.float32) / 255.0 * 0.18
        title = p.get("title")
        if title:
            tw = text_width(title, F_BLACK, 70, 2)
            draw_text(cv, img, title, F_BLACK, 70, WHITE, 960 - tw / 2, 170, reveal=prog(t, 0, 0.6), tracking=2, shadow=8)
        return img


class DotField(Scene):
    def setup(self):
        rng = np.random.default_rng(5)
        self.cols, self.rows = 46, 18
        self.order = rng.permutation(self.cols * self.rows)

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        img = navy_bg(cv, fx, t)
        s = cv.s
        N = self.cols * self.rows
        g = ease(prog(t, 0.4, p.get("fill_dur", 3.2)))
        k = int(N * g)
        lit = np.zeros(N, bool); lit[self.order[:k]] = True
        x0, y0, dx = 330, 360, 28
        for i in range(N):
            r, c = divmod(i, self.cols)
            col = np.array(YELLOW) / 255.0 if lit[i] else np.array((0.22, 0.22, 0.26))
            cv2.circle(img, (int((x0 + c * dx) * s), int((y0 + r * dx) * s)), max(1, int(8 * s)), col, -1, cv2.LINE_AA)
        val = int(p["value"] * g)
        num = f"{val:,}".replace(",", ".")
        draw_text(cv, img, num, F_BLACK, 110, WHITE, SAFE_X + 40, 150, opacity=ease_out(prog(t, 0.2, 0.7)), tracking=2, shadow=8)
        draw_text(cv, img, p["label"], F_BOLD, 34, YELLOW, SAFE_X + 44, 290 - 10, opacity=ease(prog(t, 0.5, 1.0)), tracking=6)
        note = p.get("note")
        if note:
            draw_text(cv, img, note, F_MED, 24, (200, 200, 200), x0, y0 + self.rows * dx + 20, opacity=0.75 * ease(prog(t, 1.0, 1.5)), tracking=1)
        return img


class Compare(Scene):
    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        img = navy_bg(cv, fx, t)
        s = cv.s
        L, R = p["left"], p["right"]
        for side, (spec, x, col, t0) in enumerate([(L, 180, (200, 200, 200), 0.2), (R, 1010, TEAL, 0.9)]):
            a = ease_out(prog(t, t0, t0 + 0.6))
            dx = lerp(-40 if side == 0 else 40, 0, a)
            panel = np.zeros(img.shape[:2], np.float32)
            cv2.rectangle(panel, (int((x + dx) * s), int(250 * s)), (int((x + 730 + dx) * s), int(830 * s)), 1.0, -1)
            img[:] = img * (1 - panel[..., None] * 0.45 * a) + panel[..., None] * np.array([0.10, 0.07, 0.04]) * a
            cv2.rectangle(img, (int((x + dx) * s), int(250 * s)), (int((x + 8 + dx) * s), int(830 * s)), np.array(col) / 255.0 * a, -1)
            draw_text(cv, img, spec["kicker"], F_BOLD, 26, col, x + 50 + dx, 300, opacity=a, tracking=6)
            yy = 350
            for ln in spec["title"].split("\n"):
                draw_text(cv, img, ln, F_BLACK, 66, WHITE, x + 48 + dx, yy, reveal=prog(t, t0 + 0.1, t0 + 0.7), tracking=1, shadow=6)
                yy += 80
            yy += 20
            for ln in spec["body"].split("\n"):
                draw_text(cv, img, ln, F_MED, 30, (225, 225, 225), x + 50 + dx, yy, opacity=0.9 * ease(prog(t, t0 + 0.3, t0 + 0.8)), tracking=1)
                yy += 44
            draw_text(cv, img, spec["who"], F_BOLD, 32, col, x + 50 + dx, 740, opacity=ease(prog(t, t0 + 0.5, t0 + 1.0)), tracking=3)
        va = ease_out(prog(t, 0.6, 1.0))
        vw = text_width("VS", F_BLACK, 70, 2)
        draw_text(cv, img, "VS", F_BLACK, 70, YELLOW, 960 - vw / 2, 490, opacity=va, tracking=2, shadow=10)
        return img


class MoneyQ(Scene):
    def setup(self):
        a = self.spec.get("visualAssets") or []
        self.bg = blurred_plate(a[0], 16, 0.30, "bw_cool") if a else None

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        u = ease(t / self.d)
        img = cv.place(self.bg, cv.cover(self.bg) * lerp(1.04, 1.1, u), 960, 540) if self.bg is not None else navy_bg(cv, fx, t)
        g = ease_out(prog(t, 0.2, 2.0))
        v = int(p["value"] * g)
        num = "$" + f"{v:,}".replace(",", ".")
        nw = text_width(num, F_BLACK, 150, 2)
        draw_text(cv, img, num, F_BLACK, 150, YELLOW, 960 - nw / 2, 400, opacity=ease_out(prog(t, 0.1, 0.5)), tracking=2, shadow=12)
        lab = p.get("label", "")
        lw_ = text_width(lab, F_MED, 30, 4)
        draw_text(cv, img, lab, F_MED, 30, (230, 230, 230), 960 - lw_ / 2, 600, opacity=0.85 * ease(prog(t, 0.8, 1.3)), tracking=4)
        if p.get("strike"):
            sa = ease(prog(t, p.get("strike_t", 2.2), p.get("strike_t", 2.2) + 0.5))
            x0, x1 = 960 - nw / 2 - 20, 960 - nw / 2 - 20 + (nw + 40) * sa
            cv2.line(img, (int(x0 * cv.s), int(505 * cv.s)), (int(x1 * cv.s), int(470 * cv.s)), (0.25, 0.25, 0.95), max(2, int(9 * cv.s)), cv2.LINE_AA)
            q = p.get("question", "")
            qw = text_width(q, F_BOLD, 44, 2)
            draw_text(cv, img, q, F_BOLD, 44, WHITE, 960 - qw / 2, 680, opacity=ease_out(prog(t, p.get("strike_t", 2.2) + 0.4, p.get("strike_t", 2.2) + 0.9)), tracking=2, shadow=8)
        self.caption(img, t)
        return img


class CoinRain(Scene):
    def setup(self):
        rng = np.random.default_rng(12)
        n = 90
        self.c = [(rng.uniform(980, 1800), rng.uniform(-900, -60), rng.uniform(0, 1.6), rng.uniform(26, 40), rng.uniform(0, 6.28)) for _ in range(n)]

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        img = navy_bg(cv, fx, t, glow=(0.03, 0.06, 0.10), center=(0.7, 0.5))
        s = cv.s
        floor = 900
        for i, (x, y0, d, r, ph) in enumerate(self.c):
            tt = max(t - d, 0)
            y = min(y0 + 0.5 * 1500 * tt * tt, floor - r - (i % 7) * r * 0.35)
            squash = abs(math.cos(ph + tt * 6)) * 0.75 + 0.25 if y < floor - r - (i % 7) * r * 0.35 else 0.35
            ax = (max(2, int(r * s)), max(1, int(r * squash * s)))
            cv2.ellipse(img, (int(x * s), int(y * s)), ax, 0, 0, 360, (0.55, 0.62, 0.68), -1, cv2.LINE_AA)
            cv2.ellipse(img, (int(x * s), int(y * s)), ax, 0, 0, 360, (0.80, 0.86, 0.90), max(1, int(2 * s)), cv2.LINE_AA)
        a = ease_out(prog(t, 0.2, 0.8))
        draw_text(cv, img, p["kicker"], F_BOLD, 28, YELLOW, SAFE_X + 40, 330, opacity=a, tracking=8)
        yy = 380
        for ln in p["title"].split("\n"):
            draw_text(cv, img, ln, F_BLACK, 80, WHITE, SAFE_X + 36, yy, reveal=prog(t, 0.25, 0.85), tracking=1, shadow=8)
            yy += 92
        draw_text(cv, img, p["sub"], F_MED, 30, (220, 220, 220), SAFE_X + 40, yy + 20, opacity=0.85 * ease(prog(t, 0.8, 1.3)), tracking=1)
        return img


class PhotoCard(Scene):
    """Fotograf kart olarak (beyaz cerceve, golge) + bulanik arka plan + yanda opsiyonel metin."""
    def setup(self):
        src = grade(load(self.spec["visualAssets"][0]), self.p.get("grade", "bw_cool"))
        b = 14
        h, w = src.shape[:2]
        fr = np.ones((h + 2 * b, w + 2 * b, 3), np.float32) * np.array([0.92, 0.94, 0.95], np.float32)
        fr[b:b + h, b:b + w] = src
        self.card = fr
        self.bg = cv2.GaussianBlur(src, (0, 0), 24) * 0.28
        pad = 90
        sh = np.zeros((h + 2 * b + 2 * pad, w + 2 * b + 2 * pad), np.float32)
        sh[pad:pad + h + 2 * b, pad:pad + w + 2 * b] = 1
        self.shadow = cv2.GaussianBlur(sh, (0, 0), 30)
        self.alpha = np.ones(fr.shape[:2], np.float32)

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        u = ease(t / self.d)
        img = cv.place(self.bg, cv.cover(self.bg) * lerp(1.15, 1.08, u), lerp(990, 930, u), 540)
        side = p.get("side", "right")
        h, w = self.card.shape[:2]
        sc = min(820 / h, 900 / w) * lerp(p.get("z0", 1.0), p.get("z1", 1.06), u)
        cx = (1290 if side == "right" else 630 if side == "left" else 960) + lerp(10, -10, u)
        cy = 540
        ang = lerp(p.get("a0", 2.5 if side == "right" else -2.5), p.get("a1", 1.2 if side == "right" else -1.2), u)
        sh = cv.place(self.shadow, sc, cx + 20, cy + 28, ang, border=cv2.BORDER_CONSTANT)
        img *= (1 - 0.7 * sh[..., None])
        card = cv.place(self.card, sc, cx, cy, ang, border=cv2.BORDER_CONSTANT)
        am = cv.place(self.alpha, sc, cx, cy, ang, border=cv2.BORDER_CONSTANT)[..., None]
        img = img * (1 - am) + card * am
        if p.get("title"):
            tx = SAFE_X + 40 if side == "right" else 1130
            a = ease_out(prog(t, 0.4, 1.0))
            draw_text(cv, img, p.get("kicker", ""), F_BOLD, 26, YELLOW, tx, 400, opacity=a, tracking=6)
            yy = 445
            for ln in p["title"].split("\n"):
                draw_text(cv, img, ln, F_BLACK, p.get("size", 70), WHITE, tx - 2, yy, reveal=prog(t, 0.45, 1.05), tracking=1, shadow=8)
                yy += p.get("size", 70) * 1.15
            if p.get("sub"):
                draw_text(cv, img, p["sub"], F_MED, 30, (225, 225, 225), tx, yy + 18, opacity=0.85 * ease(prog(t, 0.9, 1.4)), tracking=1)
        self.caption(img, t)
        return img


class KodCard(Scene):
    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        img = navy_bg(cv, fx, t, glow=(0.03, 0.10, 0.16))
        dust(cv, img, t, n=50, seed=8, color=(0.4, 0.8, 1.0), amt=0.2)
        s = cv.s
        ba = ease_out(prog(t, 0.1, 0.6))
        badge = p.get("badge", "BEYİN KODU")
        bw = text_width(badge, F_BLACK, 34, 6) + 60
        x0 = 960 - bw / 2
        cv2.rectangle(img, (int(x0 * s), int(250 * s)), (int((x0 + bw) * s), int(312 * s)), np.array(YELLOW) / 255.0 * ba, -1)
        draw_text(cv, img, badge, F_BLACK, 34, (20, 20, 20), x0 + 30, 260, opacity=ba, tracking=6, shadow=0)
        yy = 380
        for i, ln in enumerate(p["lines"]):
            t0 = 0.7 + i * 0.6
            a = ease_out(prog(t, t0, t0 + 0.5))
            lw_ = text_width(ln, F_BOLD, 58, 0)
            draw_text(cv, img, ln, F_BOLD, 58, WHITE if i != p.get("hl", -1) else YELLOW, 960 - lw_ / 2, yy, reveal=prog(t, t0, t0 + 0.6), shadow=8)
            yy += 78
        q = p.get("question")
        if q:
            qa = ease_out(prog(t, p.get("q_t", 3.5), p.get("q_t", 3.5) + 0.6))
            qw = text_width(q, F_SEMI, 40, 1)
            draw_text(cv, img, q, F_SEMI, 40, YELLOW, 960 - qw / 2, yy + 60, opacity=qa, tracking=1, shadow=6)
        return img


class EndScreen(Scene):
    """YouTube bitis ekrani: logo + oneri ve abone alanlari (YouTube ogeleri bu kutulara yerlestirilir)."""
    def setup(self):
        lg = imread(self.spec["visualAssets"][0]).astype(np.float32) / 255.0
        self.logo = lg
        h, w = lg.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.sqrt((xx - w / 2) ** 2 + (yy - h / 2) ** 2) / (w / 2)
        self.lmask = np.clip((0.985 - r) / 0.02, 0, 1).astype(np.float32)

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        img = navy_bg(cv, fx, t, glow=(0.02, 0.07, 0.14))
        dust(cv, img, t, n=50, seed=5, color=(0.4, 0.7, 1.0), amt=0.2)
        s = cv.s
        a = ease_out(prog(t, 0.0, 0.8))
        sz = 300 / self.logo.shape[1]
        lg = cv.place(self.logo, sz, 960, 250, border=cv2.BORDER_CONSTANT)
        m = cv.place(self.lmask, sz, 960, 250, border=cv2.BORDER_CONSTANT)[..., None] * a
        img = img * (1 - m) + lg * m
        tag = p.get("tag", "")
        tw = text_width(tag, F_BOLD, 30, 8)
        draw_text(cv, img, tag, F_BOLD, 30, YELLOW, 960 - tw / 2, 430, opacity=ease(prog(t, 0.5, 1.0)), tracking=8)
        ba = ease(prog(t, 0.8, 1.4))
        # video kutusu (sol) ve abone dairesi (sag) - YouTube ogeleri icin yer
        for (x0, y0, x1, y1) in [(300, 540, 1060, 968)]:
            cv2.rectangle(img, (int(x0 * s), int(y0 * s)), (int(x1 * s), int(y1 * s)), np.array(YELLOW) / 255.0 * ba * 0.9, max(1, int(3 * s)), cv2.LINE_AA)
        draw_text(cv, img, p.get("next", "SIRADAKİ BELGESEL"), F_BOLD, 26, WHITE, 300, 500, opacity=ba, tracking=6)
        cv2.circle(img, (int(1400 * s), int(754 * s)), int(170 * s), np.array(YELLOW) / 255.0 * ba * 0.9, max(1, int(3 * s)), cv2.LINE_AA)
        aw = text_width("ABONE OL", F_BOLD, 26, 6)
        draw_text(cv, img, "ABONE OL", F_BOLD, 26, WHITE, 1400 - aw / 2, 500, opacity=ba, tracking=6)
        return img


EXT_SCENES = {"chapter": ChapterTitle, "quote": QuoteCard, "timeline_years": TimelineYears, "bar_chart": BarChart,
              "family": FamilyIcons, "dots": DotField, "compare": Compare, "money": MoneyQ, "coins": CoinRain,
              "photo_card": PhotoCard, "kod": KodCard, "end_screen": EndScreen}

# ===================== EK SAHNE TIPLERI (v3): merak ve sururukleyicilik =====================
class HeadlineSlam(Scene):
    """Gazete mansetti: radyal zoom-blur ile carpma + sarsinti, sonra manset uzerinde isik vurgusu."""
    def setup(self):
        src = grade(load(self.spec["visualAssets"][0]), self.p.get("grade", "desat"))
        b = 10
        h, w = src.shape[:2]
        fr = np.ones((h + 2 * b, w + 2 * b, 3), np.float32) * 0.93
        fr[b:b + h, b:b + w] = src
        self.card = fr
        self.alpha = np.ones(fr.shape[:2], np.float32)
        self.bg = cv2.GaussianBlur(src, (0, 0), 26) * 0.25

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        img = cv.place(self.bg, cv.cover(self.bg) * 1.15, 960, 540)
        hit = p.get("hit", 0.35)
        g = ease_out(prog(t, 0.0, hit))
        h, w = self.card.shape[:2]
        base = min(900 / h, 1300 / w) * p.get("scale", 1.0)
        sc = base * lerp(2.6, 1.0, g) * lerp(1.0, 1.05, ease(prog(t, hit, self.d)))
        shake = math.exp(-max(t - hit, 0) * 9) * (12 if t > hit else 0)
        cx = p.get("cx", 960) + shake * math.sin(t * 90)
        cy = 540 + shake * math.cos(t * 77)
        ang = lerp(-14, p.get("angle", -3), g)
        card = cv.place(self.card, sc, cx, cy, ang, border=cv2.BORDER_CONSTANT)
        am = cv.place(self.alpha, sc, cx, cy, ang, border=cv2.BORDER_CONSTANT)[..., None] * min(1, g * 1.5)
        if t < hit:  # hareket bulaniksi (radyal)
            k = max(1, int(25 * (1 - g) * cv.s)) * 2 + 1
            card = cv2.GaussianBlur(card, (k, k), 0)
        img = img * (1 - am) + card * am
        if t > hit and t < hit + 0.12:
            img = img + 0.25 * (1 - (t - hit) / 0.12)
        if p.get("kicker"):
            draw_text(cv, img, p["kicker"], F_BOLD, 30, YELLOW, SAFE_X + 40, 1080 - SAFE_Y - 120, reveal=prog(t, hit + 0.5, hit + 1.1), tracking=8, shadow=8)
        self.caption(img, t)
        return img


class Spotlight(Scene):
    """Fotograf kararir, tek bir detay daire icinde aydinlanir ve yaklasir; cizgiyle aciklama etiketi."""
    def setup(self):
        self.img = grade(load(self.spec["visualAssets"][0]), self.p.get("grade", "bw_cool"))

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        u = ease(t / self.d)
        fxp, fyp = p["focus"]          # odak noktasi (gorselin 0-1 koordinati)
        h, w = self.img.shape[:2]
        base = cv.cover(self.img) * p.get("z0", 1.0)
        zin = lerp(1.0, p.get("zoom", 1.35), ease(prog(t, 0.6, self.d)))
        sc = base * zin
        # odagi ekranda hedef noktaya kaydir
        tx, ty = p.get("target", (760, 520))
        cx = lerp(960, tx + (0.5 - fxp) * w * sc, ease(prog(t, 0.6, self.d)))
        cy = lerp(540, ty + (0.5 - fyp) * h * sc, ease(prog(t, 0.6, self.d)))
        img = cv.place(self.img, sc, cx, cy)
        sx = cx + (fxp - 0.5) * w * sc
        sy = cy + (fyp - 0.5) * h * sc
        r = p.get("radius", 170) * lerp(1.6, 1.0, ease(prog(t, 0.2, 1.0)))
        d = np.sqrt((fx.xx - sx * cv.s) ** 2 + (fx.yy - sy * cv.s) ** 2) / (r * cv.s)
        dim = ease(prog(t, 0.2, 0.9))
        m = np.clip(1.15 - d, 0, 1)[..., None] ** 0.6
        img = img * (1 - dim * 0.72 * (1 - m))
        ring = np.zeros(img.shape[:2], np.float32)
        cv2.circle(ring, (int(sx * cv.s), int(sy * cv.s)), int(r * cv.s), 1.0, max(1, int(3 * cv.s)), cv2.LINE_AA)
        img += ring[..., None] * np.array(YELLOW, np.float32) / 255.0 * dim
        lab = p.get("label")
        if lab:
            la = prog(t, 1.0, 1.5)
            lx, ly = p.get("label_xy", (sx + r + 140, sy - r - 40))
            px, py = sx + r * 0.72, sy - r * 0.72
            ex = lerp(px, lx - 12, ease_out(la)); ey = lerp(py, ly + 30, ease_out(la))
            cv2.line(img, (int(px * cv.s), int(py * cv.s)), (int(ex * cv.s), int(ey * cv.s)), np.array(YELLOW) / 255.0, max(1, int(3 * cv.s)), cv2.LINE_AA)
            draw_text(cv, img, lab, F_BOLD, 40, WHITE, lx, ly, reveal=prog(t, 1.3, 1.9), tracking=1, shadow=8)
            if p.get("sub"):
                draw_text(cv, img, p["sub"], F_MED, 28, (225, 225, 225), lx + 2, ly + 54, opacity=0.85 * ease(prog(t, 1.7, 2.2)), tracking=1)
        self.caption(img, t)
        return img


class QuestionCard(Scene):
    """Merak dongusu (open loop): izleyicinin aklina soru takar; her ~2 dakikada bir kullanilir."""
    def setup(self):
        a = self.spec.get("visualAssets") or []
        self.bg = blurred_plate(a[0], 14, 0.22) if a else None

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        u = ease(t / self.d)
        img = cv.place(self.bg, cv.cover(self.bg) * lerp(1.04, 1.12, u), 960, 540) if self.bg is not None else navy_bg(cv, fx, t)
        k = p.get("kicker", "PEKİ...")
        kw = text_width(k, F_BOLD, 32, 10)
        draw_text(cv, img, k, F_BOLD, 32, YELLOW, 960 - kw / 2, 360, reveal=prog(t, 0.05, 0.5), tracking=10)
        lines = p["question"].split("\n")
        yy = 420
        for i, ln in enumerate(lines):
            lw_ = text_width(ln, F_BLACK, 84, 1)
            draw_text(cv, img, ln, F_BLACK, 84, WHITE, 960 - lw_ / 2, yy, reveal=prog(t, 0.35 + i * 0.35, 0.95 + i * 0.35), tracking=1, shadow=10)
            yy += 100
        # yanip sonen soru isareti nabzi
        pa = 0.55 + 0.45 * math.sin(t * 4.5)
        qw = text_width("?", F_BLACK, 120, 0)
        draw_text(cv, img, "?", F_BLACK, 120, YELLOW, 960 - qw / 2, yy + 10, opacity=pa * ease(prog(t, 1.2, 1.6)), shadow=12)
        return img


EXT2_SCENES = {"headline": HeadlineSlam, "spotlight": Spotlight, "question": QuestionCard}


# ===================== v4: HARITA ve ISTATISTIK =====================
def rrect(img, x0, y0, x1, y1, r, color, alpha=1.0, s=1.0):
    """Yuvarlatilmis dikdortgen (yumusak kenarli), 1920 koordinatinda."""
    x0, y0, x1, y1, r = [int(v * s) for v in (x0, y0, x1, y1, r)]
    h, w = img.shape[:2]
    m = np.zeros((h, w), np.float32)
    r = max(r, 1)
    cv2.rectangle(m, (x0 + r, y0), (x1 - r, y1), 1.0, -1)
    cv2.rectangle(m, (x0, y0 + r), (x1, y1 - r), 1.0, -1)
    for cx, cy in ((x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)):
        cv2.circle(m, (cx, cy), r, 1.0, -1, cv2.LINE_AA)
    a = m[..., None] * alpha
    img[:] = img * (1 - a) + np.array(color, np.float32) * a


MAP_CITIES = {  # eyalet sinir kutusuna gore oran (ABD_harita_CC0.svg koordinati)
    "ny": ("ny", 0.865, 0.93), "pit": ("pa", 0.04, 0.57), "aa": ("mi", 0.80, 0.93),
    "sd": ("ca", 0.75, 0.985), "dc": ("dc", 0.5, 0.5), "ws": ("ga", 0.25, 0.55),
}


class MapScene(Scene):
    """Vox tarzi harita: salgin yayilimi (dalga), eyalet vurgusu, igne dusmesi, rota, kamera yakinlasmasi.
    Harita uzayi: SVG 959x593 birimi; goruntu 2x (1918x1186) cozunurlukte tutulur."""
    MS = 2

    def setup(self):
        p = self.p
        d = p.get("dir", "src/map")
        self.bb = json.load(open(os.path.join(d, "bbox.json"), encoding="utf-8"))
        land = imread(os.path.join(d, "land.png"), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
        bor = imread(os.path.join(d, "borders.png"), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
        self.land, self.bor = land, bor
        H, W = land.shape
        # eyalet etiket haritasi (her piksel hangi eyalete ait)
        self.ids = sorted(self.bb.keys())
        lab = np.zeros((H, W), np.int16)
        for i, sid in enumerate(self.ids):
            m = imread(os.path.join(d, f"m_{sid}.png"), cv2.IMREAD_GRAYSCALE)
            lab[m > 127] = i + 1
        self.lab = lab
        # golge (derinlik)
        self.shadow = cv2.GaussianBlur(land, (0, 0), 14)
        # yayilma sirasi: baslangic noktasina uzaklik + rastgelelik = gercekci dalga
        sp = p.get("spread")
        self.order = {}
        if sp:
            ox, oy = sp.get("origin", [800, 150])
            rng = np.random.default_rng(sp.get("seed", 3))
            ds = {}
            for sid in self.ids:
                x, y, w, h = self.bb[sid]
                ds[sid] = math.hypot(x + w / 2 - ox, y + h / 2 - oy) * (0.75 + 0.5 * rng.random())
            mx = max(ds.values())
            self.order = {k: v / mx for k, v in ds.items()}

    def city_xy(self, key):
        if isinstance(key, (list, tuple)):
            return key
        st, fx_, fy_ = MAP_CITIES[key]
        x, y, w, h = self.bb[st]
        return (x + fx_ * w, y + fy_ * h)

    def camera(self, t):
        keys = self.p.get("cam", [[0, 480, 300, 1.0]])
        if t <= keys[0][0]:
            k = keys[0]; return k[1], k[2], k[3]
        for a, b in zip(keys, keys[1:]):
            if t <= b[0]:
                u = ease((t - a[0]) / max(b[0] - a[0], 1e-6))
                return lerp(a[1], b[1], u), lerp(a[2], b[2], u), lerp(a[3], b[3], u)
        k = keys[-1]; return k[1], k[2], k[3]

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s
        img = navy_bg(cv, fx, t, glow=(0.08, 0.05, 0.02), center=(0.5, 0.5))
        # ince enlem/boylam izgarasi
        grid = np.zeros(img.shape[:2], np.float32)
        step = max(4, int(96 * s))
        grid[:, ::step] = 1; grid[::step, :] = 1
        img += grid[..., None] * 0.018
        n = len(self.ids)
        # eyalet degerleri
        red = np.zeros(n + 1, np.float32); flash = np.zeros(n + 1, np.float32); hl = np.zeros(n + 1, np.float32)
        sp = p.get("spread")
        if sp:
            t0, t1 = sp["t0"], sp["t1"]
            for i, sid in enumerate(self.ids):
                ts = lerp(t0, t1, self.order[sid])
                a = prog(t, ts, ts + 0.45)
                sev = 0.62 + 0.38 * ((hash(sid) % 97) / 96.0)
                red[i + 1] = ease_out(a) * sp.get("max", 0.85) * sev
                flash[i + 1] = math.exp(-((t - ts - 0.12) / 0.16) ** 2) if t > ts else 0
        for h_ in p.get("highlight", []):
            i = self.ids.index(h_["state"]) + 1
            hl[i] = ease_out(prog(t, h_["t"], h_["t"] + 0.6))
        R, F, Hh = red[self.lab], flash[self.lab], hl[self.lab]
        land = self.land
        base = np.array([0.26, 0.21, 0.17], np.float32)      # BGR: soguk koyu gri-mavi kara
        redc = np.array([0.20, 0.22, 0.88], np.float32)      # kirmizi
        yel = np.array(YELLOW, np.float32) / 255.0
        mp = land[..., None] * base
        mp = mp * (1 - R[..., None]) + (R[..., None] * redc) * land[..., None]
        mp = mp * (1 - Hh[..., None] * 0.55) + Hh[..., None] * 0.55 * yel * land[..., None]
        mp += F[..., None] * land[..., None] * 0.35
        mp = mp * (1 - self.bor[..., None] * 0.55) + self.bor[..., None] * 0.55 * np.array([0.62, 0.60, 0.58], np.float32)
        # kirmizi parilti (dusuk cozunurlukte bulanik)
        glow_src = cv2.resize((R * land), (land.shape[1] // 4, land.shape[0] // 4), interpolation=cv2.INTER_AREA)
        glow = cv2.resize(cv2.GaussianBlur(glow_src, (0, 0), 6), (land.shape[1], land.shape[0]))
        alpha = np.clip(land + glow * 0.6, 0, 1)
        mp = mp + glow[..., None] * redc * 0.45
        E = int(p.get("extrude", 0) * self.MS)
        if E > 0 and R.max() > 0:
            Rl = R * land
            wall = np.zeros_like(Rl)
            for k in range(1, E + 1):
                wall = np.maximum(wall, np.roll(Rl, -k, axis=0) * (k / E) ** 0)
            top = np.roll(Rl, -E, axis=0)
            topb = np.roll(self.bor, -E, axis=0)
            wallonly = np.clip(wall - top, 0, 1)
            mp = mp * (1 - wallonly[..., None]) + wallonly[..., None] * redc * 0.45
            mp = mp * (1 - top[..., None]) + top[..., None] * (redc * 1.05 + F[..., None] * 0.0)
            mp = mp * (1 - (topb * top)[..., None] * 0.6) + (topb * top)[..., None] * 0.6 * np.array([0.75, 0.72, 0.95], np.float32)
            alpha = np.clip(np.maximum(alpha, wall), 0, 1)
        # kamera: harita uzayi -> (egim) -> kare  [homografi]
        mx, my, z = self.camera(t)
        tilt = p.get("tilt", 0.0)
        if isinstance(tilt, list):
            tilt = lerp(tilt[0], tilt[1], ease(prog(t, tilt[2], tilt[3])))
        Hm, Wm = land.shape
        k_in = 0.20 * tilt
        src = np.float32([[0, 0], [Wm, 0], [Wm, Hm], [0, Hm]])
        dst = np.float32([[Wm * k_in, Hm * 0.30 * tilt], [Wm * (1 - k_in), Hm * 0.30 * tilt], [Wm, Hm], [0, Hm]])
        Ht = cv2.getPerspectiveTransform(src, dst)
        base_sc = (1560 / (959 * self.MS)) * z * s
        cxf, cyf = 960 * s, (p.get("cy", 560)) * s
        c = Ht @ np.array([mx * self.MS, my * self.MS, 1.0]); c = c[:2] / c[2]
        A = np.array([[base_sc, 0, cxf - c[0] * base_sc], [0, base_sc, cyf - c[1] * base_sc], [0, 0, 1]])
        H = A @ Ht
        W, H_ = cv.W, cv.H
        kd = min(1.0, base_sc / 0.75)
        if kd < 1.0:  # once kucult (aliasing/titreme onlemi)
            mp = cv2.resize(mp, None, fx=kd, fy=kd, interpolation=cv2.INTER_AREA)
            alpha = cv2.resize(alpha, None, fx=kd, fy=kd, interpolation=cv2.INTER_AREA)
            shadow = cv2.resize(self.shadow, None, fx=kd, fy=kd, interpolation=cv2.INTER_AREA)
        else:
            shadow = self.shadow
        Hk = H @ np.diag([1 / kd, 1 / kd, 1.0])
        off = np.array([[1, 0, 10 * s], [0, 1, 18 * s], [0, 0, 1]])
        sh = cv2.warpPerspective(shadow, off @ Hk, (W, H_), flags=cv2.INTER_LINEAR)
        img *= (1 - 0.55 * sh[..., None])
        mw = cv2.warpPerspective(mp, Hk, (W, H_), flags=cv2.INTER_LINEAR)
        aw = cv2.warpPerspective(alpha, Hk, (W, H_), flags=cv2.INTER_LINEAR)[..., None]
        img = img * (1 - aw) + mw

        def to_frame(pt):
            v = H @ np.array([pt[0] * self.MS, pt[1] * self.MS, 1.0])
            return v[0] / v[2] / s, v[1] / v[2] / s

        # rotalar
        for r_ in p.get("routes", []):
            a = to_frame(self.city_xy(r_["from"])); b = to_frame(self.city_xy(r_["to"]))
            g = ease(prog(t, r_["t0"], r_["t1"]))
            if g <= 0:
                continue
            dist = math.hypot(b[0] - a[0], b[1] - a[1])
            c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - dist * 0.28)
            N = 60
            pts = []
            for i in range(int(N * g) + 1):
                u = i / N
                x = (1 - u) ** 2 * a[0] + 2 * (1 - u) * u * c[0] + u * u * b[0]
                y = (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * c[1] + u * u * b[1]
                pts.append((int(x * s), int(y * s)))
            lay = np.zeros(img.shape[:2], np.float32)
            for i in range(len(pts) - 1):
                if (i // 3) % 2 == 0:  # kesikli iz
                    cv2.line(lay, pts[i], pts[i + 1], 1.0, max(1, int(4 * s)), cv2.LINE_AA)
            head = np.zeros_like(lay)
            if g < 1:
                cv2.circle(head, pts[-1], max(2, int(9 * s)), 1.0, -1, cv2.LINE_AA)
            gl = cv2.GaussianBlur(lay + head * 2, (0, 0), 7 * s)
            img += (lay[..., None] * 0.95 + head[..., None] + gl[..., None] * 0.9) * yel
        # igneler
        for pin in p.get("pins", []):
            x, y = to_frame(self.city_xy(pin["city"]))
            pt = pin["t"]
            if t < pt:
                continue
            u = prog(t, pt, pt + 0.55)
            # dusme + yaylanma (easeOutBack)
            c1 = 1.70158; c3 = c1 + 1
            bounce = 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2
            yy = y - (1 - bounce) * 70
            # nabiz halkalari
            for k in range(2):
                ph = ((t - pt - 0.4 - k * 0.75) % 1.5) / 1.5 if t > pt + 0.4 + k * 0.75 else -1
                if ph >= 0:
                    rr = (12 + 48 * ph) * s
                    ring = np.zeros(img.shape[:2], np.float32)
                    cv2.circle(ring, (int(x * s), int(y * s)), int(rr), 1.0, max(1, int(2.5 * s)), cv2.LINE_AA)
                    img += ring[..., None] * yel * (1 - ph) * 0.9
            sh_ = np.zeros(img.shape[:2], np.float32)
            cv2.ellipse(sh_, (int(x * s), int((y + 4) * s)), (max(1, int(10 * s)), max(1, int(4 * s))), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
            img *= (1 - 0.5 * sh_[..., None] * u)
            dot = np.zeros(img.shape[:2], np.float32)
            cv2.circle(dot, (int(x * s), int(yy * s)), max(2, int(11 * s)), 1.0, -1, cv2.LINE_AA)
            img = img * (1 - dot[..., None]) + dot[..., None] * yel
            ring2 = np.zeros(img.shape[:2], np.float32)
            cv2.circle(ring2, (int(x * s), int(yy * s)), max(2, int(11 * s)), 1.0, max(1, int(3 * s)), cv2.LINE_AA)
            img = img * (1 - ring2[..., None]) + ring2[..., None]
            # etiket kutusu
            la = ease_out(prog(t, pt + 0.35, pt + 0.9))
            if la > 0 and pin.get("label"):
                side = pin.get("side", "right")
                tw = max(text_width(pin["label"], F_BOLD, 34, 1), text_width(pin.get("sub", ""), F_MED, 24, 1)) + 52
                bx0 = x + 30 if side == "right" else x - 30 - tw
                by0 = y - 70 + pin.get("dy", 0)
                bx0 += lerp(-14 if side == "right" else 14, 0, la)
                rrect(img, bx0, by0, bx0 + tw, by0 + (98 if pin.get("sub") else 62), 10, (0.06, 0.04, 0.03), 0.78 * la, s)
                rrect(img, bx0, by0, bx0 + 6, by0 + (98 if pin.get("sub") else 62), 3, yel, la, s)
                draw_text(cv, img, pin["label"], F_BOLD, 34, WHITE, bx0 + 26, by0 + 10, opacity=la, tracking=1, shadow=0, check_safe=False)
                if pin.get("sub"):
                    draw_text(cv, img, pin["sub"], F_MED, 24, (215, 215, 215), bx0 + 27, by0 + 56, opacity=la * 0.9, tracking=1, shadow=0, check_safe=False)
        # salgin sayaci
        if sp and sp.get("value"):
            g = ease_out(prog(t, sp["t0"], sp["t1"] + 0.5))
            v = int(sp["value"] * g)
            num = f"{v:,}".replace(",", ".")
            draw_text(cv, img, sp.get("kicker", ""), F_BOLD, 28, YELLOW, SAFE_X + 40, 150, reveal=prog(t, 0.1, 0.6), tracking=8)
            draw_text(cv, img, num, F_BLACK, 110, WHITE, SAFE_X + 36, 190, opacity=ease(prog(t, 0.2, 0.6)), tracking=2, shadow=10)
            draw_text(cv, img, sp.get("label", ""), F_SEMI, 32, (230, 230, 230), SAFE_X + 40, 322, reveal=prog(t, 0.5, 1.0), tracking=2)
        if p.get("title"):
            draw_text(cv, img, p["title"], F_BOLD, 30, YELLOW, SAFE_X + 40, 150, reveal=prog(t, 0.1, 0.6), tracking=8)
        self.caption(img, t)
        return img


class StatRow(Scene):
    """Uclu (veya ikili/dortlu) istatistik: sayaclar sirayla sayar, ince ayiricilar, kaynak satiri."""
    def setup(self):
        a = self.spec.get("visualAssets") or []
        self.bg = blurred_plate(a[0], 18, 0.24) if a else None

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s
        u = ease(t / self.d)
        img = cv.place(self.bg, cv.cover(self.bg) * lerp(1.05, 1.12, u), 960, 540) if self.bg is not None else navy_bg(cv, fx, t)
        k = p.get("kicker", "")
        kw = text_width(k, F_BOLD, 30, 10)
        draw_text(cv, img, k, F_BOLD, 30, YELLOW, 960 - kw / 2, 250, reveal=prog(t, 0.05, 0.55), tracking=10)
        if p.get("title"):
            tw = text_width(p["title"], F_BLACK, 56, 1)
            draw_text(cv, img, p["title"], F_BLACK, 56, WHITE, 960 - tw / 2, 296, reveal=prog(t, 0.2, 0.8), tracking=1, shadow=8)
        items = p["items"]
        n = len(items)
        colw = 1500 / n
        x0 = 960 - 750
        for i, it in enumerate(items):
            val, lab = it[0], it[1]
            col = np.array((0.20, 0.22, 0.90), np.float32) if (len(it) > 2 and it[2] == "red") else np.array(YELLOW, np.float32) / 255.0
            colb = tuple(int(c * 255) for c in col)
            t0 = 0.6 + i * p.get("step", 0.7)
            g = ease_out(prog(t, t0, t0 + 1.2))
            cx = x0 + colw * (i + 0.5)
            v = int(round(val * g))
            num = f"{v:,}".replace(",", ".")
            done = prog(t, t0 + 1.2, t0 + 1.45)
            pop = 1 + 0.07 * math.sin(math.pi * done)
            size = 128 * pop
            nw = text_width(num, F_BLACK, size, 1)
            draw_text(cv, img, num, F_BLACK, size, colb, cx - nw / 2, 420 - (size - 128) * 0.5, opacity=ease(prog(t, t0, t0 + 0.3)), tracking=1, shadow=10)
            lw_ = text_width(lab, F_BOLD, 34, 4)
            draw_text(cv, img, lab, F_BOLD, 34, WHITE, cx - lw_ / 2, 590, reveal=prog(t, t0 + 0.3, t0 + 0.8), tracking=4)
            bl = 120 * ease(prog(t, t0 + 0.6, t0 + 1.2))
            cv2.line(img, (int((cx - bl / 2) * s), int(650 * s)), (int((cx + bl / 2) * s), int(650 * s)), col.tolist(), max(1, int(4 * s)), cv2.LINE_AA)
            if i > 0:
                da = ease(prog(t, 0.4, 1.0))
                xd = x0 + colw * i
                cv2.line(img, (int(xd * s), int(430 * s)), (int(xd * s), int((430 + 210 * da) * s)), (0.4, 0.4, 0.4), max(1, int(2 * s)), cv2.LINE_AA)
        if p.get("note"):
            draw_text(cv, img, p["note"], F_MED, 22, (190, 190, 190), SAFE_X + 42, 1080 - SAFE_Y - 40, opacity=0.7 * ease(prog(t, 1.5, 2.0)), tracking=1)
        self.caption(img, t)
        return img


EXT3_SCENES = {"map": MapScene, "stats": StatRow}


# ===================== v5: 3B CEKIRDEK ve 3B SAHNELER =====================
class Cam3:
    """Basit perspektif kamera. Dunya: X sag, Y asagi, Z ileri. 1920x1080 koordinatina izdusum."""
    def __init__(self, pos, yaw=0.0, pitch=0.0, f=1150.0):
        self.p = np.array(pos, np.float64)
        cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
        cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
        Ry = np.array([[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]])
        Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        self.R = Rx @ Ry
        self.f = f

    def proj(self, P):
        """P: (N,3) -> (N,2) ekran, (N,) derinlik."""
        P = np.atleast_2d(np.asarray(P, np.float64)) - self.p
        C = P @ self.R.T
        z = np.maximum(C[:, 2], 1e-3)
        return np.stack([960 + self.f * C[:, 0] / z, 540 + self.f * C[:, 1] / z], 1), C[:, 2]


def warp_quad(img, src_img, src_alpha, dst, s, opacity=1.0):
    """Gorseli ekrandaki 4 koseye (1920 koordinati) perspektifle yerlestirir; sadece ilgili bolge islenir (hizli)."""
    h, w = src_img.shape[:2]
    d = np.float32(dst) * s
    x0, y0 = np.floor(d.min(0)).astype(int); x1, y1 = np.ceil(d.max(0)).astype(int)
    H, W = img.shape[:2]
    x0c, y0c, x1c, y1c = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1c <= x0c or y1c <= y0c:
        return
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), d - np.float32([x0c, y0c]))
    size = (x1c - x0c, y1c - y0c)
    q = cv2.warpPerspective(src_img, M, size, flags=cv2.INTER_LINEAR)
    a = cv2.warpPerspective(src_alpha, M, size, flags=cv2.INTER_LINEAR)[..., None] * opacity
    roi = img[y0c:y1c, x0c:x1c]
    img[y0c:y1c, x0c:x1c] = roi * (1 - a) + q * a


_SPR = {}
def sphere_sprite(px, color, seed=0, spikes=True):
    """Isiklandirilmis 3B kure (virus): difuz + yansima + yuzey proteinleri + diken halkasi. Premultiplied BGRA."""
    key = (px, tuple(color), seed, spikes)
    if key in _SPR:
        return _SPR[key]
    S = px
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    R = S * 0.40
    nx, ny = (xx - S / 2) / R, (yy - S / 2) / R
    r2 = nx ** 2 + ny ** 2
    inside = np.clip((1 - r2) * R / 1.5, 0, 1)
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    L = np.array([-0.45, -0.55, 0.70]); L /= np.linalg.norm(L)
    diff = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    hx, hy, hz = L[0], L[1], L[2] + 1; hn = math.sqrt(hx * hx + hy * hy + hz * hz)
    spec = np.clip((nx * hx + ny * hy + nz * hz) / hn, 0, 1) ** 40
    col = np.array(color, np.float32)
    rgb = (0.18 + 0.82 * diff)[..., None] * col + spec[..., None] * 0.9
    # yuzey proteinleri (kucuk parlak benekler)
    rng = np.random.default_rng(seed)
    bumps = np.zeros((S, S), np.float32)
    for _ in range(int(S * 0.5)):
        a, b = rng.uniform(-1, 1, 2)
        if a * a + b * b < 0.85:
            cv2.circle(bumps, (int(S / 2 + a * R), int(S / 2 + b * R)), max(1, int(S * 0.018)), 1.0, -1, cv2.LINE_AA)
    rgb += (bumps * diff)[..., None] * col * 0.35
    alpha = inside
    if spikes:
        sp = np.zeros((S, S), np.float32)
        n = 28
        for i in range(n):
            ang = 2 * math.pi * i / n + rng.uniform(-0.05, 0.05)
            x1, y1 = S / 2 + math.cos(ang) * R * 0.98, S / 2 + math.sin(ang) * R * 0.98
            x2, y2 = S / 2 + math.cos(ang) * R * 1.16, S / 2 + math.sin(ang) * R * 1.16
            cv2.line(sp, (int(x1), int(y1)), (int(x2), int(y2)), 1.0, max(1, int(S * 0.012)), cv2.LINE_AA)
            cv2.circle(sp, (int(x2), int(y2)), max(1, int(S * 0.028)), 1.0, -1, cv2.LINE_AA)
        sp *= (1 - inside)
        lit = np.clip(0.35 + 0.65 * ((xx - S / 2) * L[0] + (yy - S / 2) * L[1]) / (-R * 1.2) * -1, 0.25, 1.0)
        rgb = rgb * inside[..., None] + (sp * lit)[..., None] * col * 0.8
        alpha = np.clip(inside + sp, 0, 1)
    else:
        rgb = rgb * inside[..., None]
    out = np.dstack([rgb * 1.0, alpha]).astype(np.float32)
    out[..., :3] = np.clip(out[..., :3], 0, 1.5)
    blurs = [out] + [cv2.GaussianBlur(out, (0, 0), S * k) for k in (0.02, 0.05)]
    _SPR[key] = blurs
    return blurs


def paste_sprite(img, spr, cx, cy, size, s, opacity=1.0):
    """spr: premult BGRA; cx,cy,size 1920 koordinatinda."""
    d = max(2, int(size * s))
    sp = cv2.resize(spr, (d, d), interpolation=cv2.INTER_AREA if d < spr.shape[0] else cv2.INTER_LINEAR)
    over(img, sp, cx * s - d / 2, cy * s - d / 2, opacity, False)


def virus_field(cv, fx, t, n=60, seed=4, dark=1.0, speed=160, color=(0.80, 0.86, 0.25)):
    """3B virus parcacik alani: kamera ileri suzulur, alan derinligi bulaniklik + sis."""
    img = navy_bg(cv, fx, t, glow=(0.12, 0.10, 0.02), center=(0.5, 0.5))
    rng = np.random.default_rng(seed)
    P = np.stack([rng.uniform(-1500, 1500, n), rng.uniform(-900, 900, n), rng.uniform(200, 3600, n)], 1)
    spin = rng.uniform(-0.3, 0.3, n)
    P[:, 2] = (P[:, 2] - t * speed - 200) % 3400 + 200
    P[:, 0] += np.sin(t * 0.4 + spin * 10) * 40
    cam = Cam3((0, 0, 0), yaw=math.sin(t * 0.25) * 4, pitch=math.cos(t * 0.2) * 3)
    xy, z = cam.proj(P)
    order = np.argsort(-z)
    blurs = sphere_sprite(160, color, seed=1)
    focus = 900
    for i in order:
        if z[i] < 120:
            continue
        size = cam.f * 85 / z[i]
        if size < 3:
            continue
        dz = abs(z[i] - focus) / focus
        lvl = 0 if dz < 0.35 else (1 if dz < 0.9 else 2)
        fog = np.clip(1.2 - z[i] / 3600, 0.15, 1.0)
        near = np.clip((z[i] - 120) / 300, 0, 1)
        paste_sprite(img, blurs[lvl], xy[i, 0], xy[i, 1], size * 1.35, cv.s, fog * near * dark)
    return img


# --- 29. sn: soru karti artik 3B virus alaninin icinde ---
_QC_render = QuestionCard.render
def _qc_render(self, t, f):
    if self.p.get("bg3d") == "virus":
        cv, fx, p = self.cv, self.fx, self.p
        img = virus_field(cv, fx, t, dark=0.85)
        img *= 0.62
        k = p.get("kicker", "PEKİ...")
        kw = text_width(k, F_BOLD, 32, 10)
        draw_text(cv, img, k, F_BOLD, 32, YELLOW, 960 - kw / 2, 360, reveal=prog(t, 0.05, 0.5), tracking=10)
        yy = 420
        for i, ln in enumerate(p["question"].split("\n")):
            lw_ = text_width(ln, F_BLACK, 84, 1)
            draw_text(cv, img, ln, F_BLACK, 84, WHITE, 960 - lw_ / 2, yy, reveal=prog(t, 0.35 + i * 0.35, 0.95 + i * 0.35), tracking=1, shadow=14)
            yy += 100
        pa = 0.55 + 0.45 * math.sin(t * 4.5)
        qw = text_width("?", F_BLACK, 120, 0)
        draw_text(cv, img, "?", F_BLACK, 120, YELLOW, 960 - qw / 2, yy + 10, opacity=pa * ease(prog(t, 1.2, 1.6)), shadow=12)
        return img
    return _QC_render(self, t, f)
QuestionCard.render = _qc_render


class Virus3D(Scene):
    """Bilim sahnesi: 3B virus alani + alt bilgi (orn. 'Formaldehitle oldurulmus virus')."""
    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        dead = p.get("dead_t")
        col = (0.80, 0.86, 0.25)
        img = virus_field(cv, fx, t, n=p.get("n", 70), speed=p.get("speed", 160), color=col)
        if dead is not None:  # olum ani: renk soner, gri-mavi olur
            k = ease(prog(t, dead, dead + 1.0))
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)[..., None]
            img = img * (1 - k) + (g * np.array([1.0, 0.85, 0.7], np.float32)) * k
        if p.get("title"):
            la = prog(t, 0.5, 1.1)
            rrect(img, SAFE_X + 20, 640, SAFE_X + 30, 760, 3, np.array(YELLOW) / 255.0, ease_out(la), cv.s)
            draw_text(cv, img, p["title"], F_BLACK, 64, WHITE, SAFE_X + 52, 640, reveal=la, tracking=1, shadow=10)
            if p.get("sub"):
                draw_text(cv, img, p["sub"], F_MED, 30, (225, 225, 225), SAFE_X + 55, 722, opacity=0.85 * ease(prog(t, 1.0, 1.5)), tracking=1)
        if p.get("hud"):
            hw = text_width(p["hud"], F_SEMI, 22, 5)
            draw_text(cv, img, p["hud"], F_SEMI, 22, TEAL, 1920 - SAFE_X - 30 - hw, 130, opacity=0.85 * ease(prog(t, 0.3, 0.9)), tracking=5, shadow=0)
        self.caption(img, t)
        return img


# --- 36. sn: hacimli figurler + isik huzmeleri + zemin yansimasi ---
def person_mask(h, s):
    S = int(h * 1.1 * s) + 4
    m = np.zeros((S, S), np.float32)
    cx = S / 2
    cv2.circle(m, (int(cx), int(S * 0.22)), max(2, int(h * 0.20 * s)), 1.0, -1, cv2.LINE_AA)
    # omuzlu govde: yuvarlatilmis ust + duz alt
    tw, top, bot = h * 0.34 * s, S * 0.47, S * 0.93
    r = max(2, int(tw * 0.55))
    cv2.rectangle(m, (int(cx - tw), int(top + r)), (int(cx + tw), int(bot)), 1.0, -1)
    cv2.rectangle(m, (int(cx - tw + r), int(top)), (int(cx + tw - r), int(bot)), 1.0, -1)
    cv2.circle(m, (int(cx - tw + r), int(top + r)), r, 1.0, -1, cv2.LINE_AA)
    cv2.circle(m, (int(cx + tw - r), int(top + r)), r, 1.0, -1, cv2.LINE_AA)
    cv2.rectangle(m, (int(cx - h * 0.07 * s), int(S * 0.38)), (int(cx + h * 0.07 * s), int(top + 2)), 1.0, -1)
    m[int(bot):] = 0
    return m


def _family_render(self, t, f):
    cv, fx, p = self.cv, self.fx, self.p
    s = cv.s
    img = navy_bg(cv, fx, t)
    floor_y = 760
    # sahne zemini (ufka dogru acilan isik)
    yy = fx.yy / s
    flo = np.clip((yy - floor_y) / 300, 0, 1)
    img += (flo * (1 - flo) * 0.10)[..., None] * np.array([0.9, 0.85, 0.8], np.float32)
    # arkada dev soluk yil
    yr = p.get("bigyear", "1953")
    yw = text_width(yr, F_BLACK, 420, 4)
    draw_text(cv, img, yr, F_BLACK, 420, (255, 255, 255), 960 - yw / 2, 140, opacity=0.05, tracking=4, shadow=0, check_safe=False)
    people = p["people"]
    n = len(people)
    xs = [960 + (i - (n - 1) / 2) * 300 for i in range(n)]
    yel = np.array(YELLOW, np.float32) / 255.0
    for i, (lab, h, ton) in enumerate(people):
        h = h * 1.4
        on = ease_out(prog(t, ton, ton + 0.45))
        # isik huzmesi (hacimli)
        if on > 0:
            cone = np.zeros(img.shape[:2], np.float32)
            pts = np.int32([[(xs[i] - 26) * s, 0], [(xs[i] + 26) * s, 0], [(xs[i] + h * 0.62) * s, floor_y * s], [(xs[i] - h * 0.62) * s, floor_y * s]])
            cv2.fillConvexPoly(cone, pts, 1.0, cv2.LINE_AA)
            cone = cv2.GaussianBlur(cone, (0, 0), 18 * s) * (0.35 + 0.65 * (fx.yy / (floor_y * s)).clip(0, 1))
            img += cone[..., None] * np.array([0.75, 0.88, 1.0], np.float32) * 0.16 * on
            pool = np.zeros(img.shape[:2], np.float32)
            cv2.ellipse(pool, (int(xs[i] * s), int(floor_y * s)), (int(h * 0.62 * s), int(h * 0.10 * s)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
            img += cv2.GaussianBlur(pool, (0, 0), 10 * s)[..., None] * 0.18 * on
        m = person_mask(h, s)
        S = m.shape[0]
        g = np.linspace(1.15, 0.55, S, dtype=np.float32)[:, None]
        rim = np.clip(m - cv2.erode(m, np.ones((max(2, int(4 * s)),) * 2, np.uint8)), 0, 1)
        base = np.array((0.30, 0.28, 0.30), np.float32) * (1 - on) + yel * on
        rgb = (m * g)[..., None] * base + rim[..., None] * (0.25 + 0.5 * on)
        spr = np.dstack([rgb, m]).astype(np.float32)
        x0 = xs[i] * s - S / 2
        y0 = floor_y * s - S * 0.93
        over(img, spr, x0, y0, 1.0, False)
        refl = spr[::-1].copy()
        fade = np.linspace(0.10, 0.0, S, dtype=np.float32)[:, None, None]
        refl[..., :4] *= np.concatenate([np.repeat(fade, 3, 2), fade], 2)
        over(img, refl[int(S * 0.07):], x0, floor_y * s + 2, 1.0, False)
        lw_ = text_width(lab, F_BOLD, 30, 3)
        draw_text(cv, img, lab, F_BOLD, 30, WHITE, xs[i] - lw_ / 2, floor_y + 70, opacity=0.35 + 0.65 * on, tracking=3)
    title = p.get("title")
    if title:
        tw = text_width(title, F_BLACK, 66, 2)
        draw_text(cv, img, title, F_BLACK, 66, WHITE, 960 - tw / 2, 120, reveal=prog(t, 0, 0.6), tracking=2, shadow=8)
    return img
FamilyIcons.render = _family_render


# --- 42. sn: perspektifte ufka uzanan cocuk kalabaligi ---
class Crowd3D(Scene):
    def setup(self):
        rng = np.random.default_rng(9)
        cols, rows = 64, 46
        X, Z = np.meshgrid(np.linspace(-1500, 1500, cols), np.linspace(500, 5200, rows))
        X = X + rng.uniform(-14, 14, X.shape); Z = Z + rng.uniform(-20, 20, Z.shape)
        self.P = np.stack([X.ravel(), np.full(X.size, 320.0), Z.ravel()], 1)
        rowf = (np.repeat(np.arange(rows), cols) / rows)
        self.lit_t = rowf * 0.85 + rng.uniform(0, 0.15, X.size)
        self.hgt = rng.uniform(0.75, 1.15, X.size)

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s
        img = navy_bg(cv, fx, t, glow=(0.10, 0.07, 0.03), center=(0.5, 0.35))
        u = ease(t / self.d)
        cam = Cam3((0, -40 - 60 * u, -200 + 520 * u), yaw=lerp(-6, 4, u), pitch=lerp(14, 18, u))
        xy, z = cam.proj(self.P)
        g = ease(prog(t, 0.5, p.get("fill_dur", 3.4)))
        order = np.argsort(-z)
        yel = np.array(YELLOW, np.float32) / 255.0
        unlit = np.array((0.30, 0.27, 0.27), np.float32)
        glow = np.zeros(img.shape[:2], np.float32)
        lay = img
        for i in order:
            if z[i] < 60:
                continue
            r = cam.f * 10 / z[i]
            if r < 0.6:
                continue
            fog = float(np.clip(1.25 - z[i] / 5600, 0.12, 1.0))
            lit = self.lit_t[i] <= g
            col = (yel if lit else unlit) * fog + np.array([0.07, 0.04, 0.02], np.float32) * (1 - fog)
            x, y = xy[i, 0] * s, xy[i, 1] * s
            hh = r * 2.6 * self.hgt[i]
            if r * s > 3:  # yakin: kucuk insan figuru
                cv2.circle(lay, (int(x), int(y - hh * s * 1.05)), max(1, int(r * 0.85 * s)), col.tolist(), -1, cv2.LINE_AA)
                cv2.ellipse(lay, (int(x), int(y)), (max(1, int(r * 1.1 * s)), max(1, int(hh * 0.62 * s))), 0, 180, 360, col.tolist(), -1, cv2.LINE_AA)
            else:
                cv2.circle(lay, (int(x), int(y - hh * s * 0.5)), max(1, int(r * s)), col.tolist(), -1, cv2.LINE_AA)
            if lit and r * s > 1:
                cv2.circle(glow, (int(x), int(y - hh * s * 0.6)), max(1, int(r * 2.2 * s)), fog, -1)
        img += cv2.GaussianBlur(glow, (0, 0), 6 * s)[..., None] * yel * 0.35
        # ufuk sisi
        hz = np.clip(1 - np.abs(fx.yy / s - 330) / 220, 0, 1) ** 2
        img += hz[..., None] * np.array([0.10, 0.08, 0.05], np.float32)
        v = int(p["value"] * g)
        draw_text(cv, img, f"{v:,}".replace(",", "."), F_BLACK, 110, WHITE, SAFE_X + 40, 120, opacity=ease_out(prog(t, 0.2, 0.7)), tracking=2, shadow=12)
        draw_text(cv, img, p["label"], F_BOLD, 34, YELLOW, SAFE_X + 44, 250, reveal=prog(t, 0.5, 1.1), tracking=6)
        if p.get("note"):
            draw_text(cv, img, p["note"], F_MED, 22, (200, 200, 200), SAFE_X + 44, 1080 - SAFE_Y - 40, opacity=0.75 * ease(prog(t, 1.0, 1.5)), tracking=1)
        return img


# --- 45. sn: derinlige uzanan 3B zaman cizelgesi, her yilda arsiv karti ---
class Timeline3D(Scene):
    def setup(self):
        self.cards = []
        for it in self.p["items"]:
            path = it[2] if len(it) > 2 else None
            if path:
                im = grade(load(path), "bw_cool")
                h, w = im.shape[:2]
                k = 560 / max(h, w)
                im = cv2.resize(im, (int(w * k), int(h * k)), interpolation=cv2.INTER_AREA)
                b = 8
                fr = np.ones((im.shape[0] + 2 * b, im.shape[1] + 2 * b, 3), np.float32) * 0.92
                fr[b:-b, b:-b] = im
                self.cards.append((fr, np.ones(fr.shape[:2], np.float32)))
            else:
                self.cards.append(None)

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s
        img = navy_bg(cv, fx, t)
        items = p["items"]; n = len(items)
        act = p.get("active", n - 1); frm = p.get("from", max(act - 1, 0))
        sp = 760
        X = [i * sp for i in range(n)]
        g = ease(prog(t, 0.3, min(self.d - 0.4, 2.6)))
        camx = lerp(X[frm], X[act], g)
        cam = Cam3((camx - 160, -380, -1350), yaw=-26, pitch=12, f=1050)
        yel = np.array(YELLOW, np.float32) / 255.0
        floorY = 220
        # zemin izgarasi
        for gx in range(-2, n + 2):
            a, _ = cam.proj([[gx * sp - sp / 2, floorY, -600], [gx * sp - sp / 2, floorY, 2600]])
            cv2.line(img, tuple((a[0] * s).astype(int)), tuple((a[1] * s).astype(int)), (0.16, 0.13, 0.11), max(1, int(1.5 * s)), cv2.LINE_AA)
        # ana cizgi
        L, _ = cam.proj([[-sp, floorY, 600], [X[-1] + sp, floorY, 600]])
        cv2.line(img, tuple((L[0] * s).astype(int)), tuple((L[1] * s).astype(int)), (0.35, 0.35, 0.35), max(1, int(3 * s)), cv2.LINE_AA)
        P2, _ = cam.proj([[X[0], floorY, 600], [camx, floorY, 600]])
        cv2.line(img, tuple((P2[0] * s).astype(int)), tuple((P2[1] * s).astype(int)), yel.tolist(), max(1, int(5 * s)), cv2.LINE_AA)
        order = sorted(range(n), key=lambda i: -cam.proj([[X[i], 0, 600]])[1][0])
        for i in order:
            isact = (i == act)
            reached = X[i] <= camx + 1
            yr, lab = items[i][0], items[i][1]
            card = self.cards[i]
            if card is not None:
                ci, ca = card
                h, w = ci.shape[:2]
                cw, chh = 420 * w / max(w, h) * 1.3, 420 * h / max(w, h) * 1.3
                bot = floorY - 90
                quad = [[X[i] - cw / 2, bot - chh, 600], [X[i] + cw / 2, bot - chh, 600], [X[i] + cw / 2, bot, 600], [X[i] - cw / 2, bot, 600]]
                q, _ = cam.proj(quad)
                dim = 1.0 if isact and g > 0.85 else (0.62 if reached else 0.38)
                warp_quad(img, ci * dim, ca, q, s)
                if isact and g > 0.85:
                    fl = np.zeros(img.shape[:2], np.float32)
                    cv2.polylines(fl, [np.int32(q * s)], True, 1.0, max(1, int(4 * s)), cv2.LINE_AA)
                    img += (fl + cv2.GaussianBlur(fl, (0, 0), 8 * s) * 1.5)[..., None] * yel * ease(prog(t, 2.2, 2.8))
            d, _ = cam.proj([[X[i], floorY, 600]])
            r = (15 if isact else 9)
            cv2.circle(img, (int(d[0, 0] * s), int(d[0, 1] * s)), max(2, int(r * s)), (yel if reached else np.array((0.5, 0.5, 0.5))).tolist(), -1, cv2.LINE_AA)
            ys = 64 if isact else 40
            yw = text_width(yr, F_BLACK, ys, 1)
            draw_text(cv, img, yr, F_BLACK, ys, YELLOW if (isact or reached) else (190, 190, 190), d[0, 0] - yw / 2, d[0, 1] + 26, tracking=1, shadow=8, check_safe=False, opacity=0.95)
            lw_ = text_width(lab, F_SEMI, 26, 1)
            draw_text(cv, img, lab, F_SEMI, 26, WHITE, d[0, 0] - lw_ / 2, d[0, 1] + 30 + ys, opacity=0.9 if (isact or reached) else 0.5, tracking=1, check_safe=False)
        if p.get("title"):
            draw_text(cv, img, p["title"], F_BOLD, 30, YELLOW, SAFE_X + 40, 120, reveal=prog(t, 0, 0.5), tracking=8)
        return img


# --- 53-54. sn: 3B sutun grafik ---
def cuboid_faces(cam, cx, cz, w, d, y0, y1):
    """y0 zemin, y1 tepe (y asagi pozitif => y1 < y0)."""
    x0, x1, z0, z1 = cx - w / 2, cx + w / 2, cz - d / 2, cz + d / 2
    V = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
    P, _ = cam.proj(V)
    front = P[[0, 1, 2, 3]]; top = P[[3, 2, 6, 7]]; right = P[[1, 5, 6, 2]]; left = P[[4, 0, 3, 7]]
    return front, top, right, left, P


class Bars3D(Scene):
    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s
        img = navy_bg(cv, fx, t, glow=(0.08, 0.06, 0.03))
        u = ease(t / self.d)
        cam = Cam3((lerp(-620, -380, u), -560, -900), yaw=lerp(13, 8, u), pitch=lerp(15, 12, u), f=1100)
        floorY = 300
        # zemin izgarasi
        for gx in np.linspace(-1100, 1100, 12):
            a, _ = cam.proj([[gx, floorY, 900], [gx, floorY, 2600]])
            cv2.line(img, tuple((a[0] * s).astype(int)), tuple((a[1] * s).astype(int)), (0.15, 0.12, 0.10), max(1, int(1.5 * s)), cv2.LINE_AA)
        for gz in np.linspace(900, 2600, 8):
            a, _ = cam.proj([[-1100, floorY, gz], [1100, floorY, gz]])
            cv2.line(img, tuple((a[0] * s).astype(int)), tuple((a[1] * s).astype(int)), (0.15, 0.12, 0.10), max(1, int(1.5 * s)), cv2.LINE_AA)
        bars = p["bars"]; vmax = max(b[1] for b in bars)
        n = len(bars)
        xs = [(i - (n - 1) / 2) * 560 for i in range(n)]
        cols = [np.array(YELLOW, np.float32) / 255.0] + [np.array(TEAL, np.float32) / 255.0] * (n - 1)
        info = []
        for i in sorted(range(n), key=lambda i: -abs(xs[i] - cam.p[0])):
            lab, val, _ = bars[i]
            t0 = 0.5 + i * p.get("step", 0.9)
            g = ease_out(prog(t, t0, t0 + 1.3))
            hgt = max(760 * (val / vmax) * g, 10 * g)
            if g <= 0:
                info.append((i, None, lab, val, g)); continue
            fr, top, rt, lf, P = cuboid_faces(cam, xs[i], 1600, 340, 340, floorY, floorY - hgt)
            c = cols[i]
            # yuz golgelendirme: on 1.0, ust 1.35, yan 0.6
            side = rt if cam.p[0] < xs[i] else lf
            for poly, k in ((side, 0.55), (fr, 1.0), (top, 1.35)):
                cv2.fillConvexPoly(img, np.int32(poly * s), np.clip(c * k, 0, 1).tolist(), cv2.LINE_AA)
            # on yuzde dikey parlaklik gradyani (cam hissi)
            m = np.zeros(img.shape[:2], np.float32)
            cv2.fillConvexPoly(m, np.int32(fr * s), 1.0, cv2.LINE_AA)
            yy0, yy1 = fr[:, 1].min() * s, fr[:, 1].max() * s
            grad = np.clip(1 - (fx.yy - yy0) / max(yy1 - yy0, 1), 0, 1)
            img += (m * grad * 0.18)[..., None]
            # zemin isik havuzu
            pool = np.zeros(img.shape[:2], np.float32)
            q, _ = cam.proj([[xs[i], floorY, 1600]])
            cv2.ellipse(pool, (int(q[0, 0] * s), int(q[0, 1] * s)), (int(260 * s), int(60 * s)), 0, 0, 360, 1.0, -1)
            img += cv2.GaussianBlur(pool, (0, 0), 24 * s)[..., None] * c * 0.18 * g
            info.append((i, top, lab, val, g))
        for i, top, lab, val, g in info:
            q, _ = cam.proj([[xs[i], floorY, 1450]])
            lw_ = text_width(lab, F_BOLD, 38, 3)
            draw_text(cv, img, lab, F_BOLD, 38, (235, 235, 235), q[0, 0] - lw_ / 2, q[0, 1] + 24, tracking=3, opacity=ease(prog(t, 0.2, 0.7)), check_safe=False)
            if top is None:
                continue
            cur = int(round(val * g))
            txt = f"{cur:,}".replace(",", ".")
            tw = text_width(txt, F_BLACK, 66, 1)
            tc = top.mean(0)
            draw_text(cv, img, txt, F_BLACK, 66, WHITE, tc[0] - tw / 2, tc[1] - 100, tracking=1, shadow=10, check_safe=False, opacity=ease(prog(t, 0.6 + i * p.get("step", 0.9), 0.9 + i * p.get("step", 0.9))))
        draw_text(cv, img, p.get("title", ""), F_BOLD, 40, WHITE, SAFE_X + 40, 80, reveal=prog(t, 0, 0.6), tracking=3)
        if p.get("sub"):
            draw_text(cv, img, p["sub"], F_MED, 26, (200, 200, 200), SAFE_X + 42, 134, opacity=0.8 * ease(prog(t, 0.3, 0.8)), tracking=2)
        if p.get("note"):
            draw_text(cv, img, p["note"], F_MED, 22, (190, 190, 190), SAFE_X + 42, 1080 - SAFE_Y - 40, opacity=0.7 * ease(prog(t, 2.0, 2.5)), tracking=1)
        return img


EXT4_SCENES = {"virus3d": Virus3D, "crowd3d": Crowd3D, "timeline3d": Timeline3D, "bars3d": Bars3D}


SCENES = {"year_card": YearCard, "card_counter": CardCounter, "archival_push": ArchivalPush,
          "microscope": Microscope, "portrait_parallax": PortraitParallax,
          "archival_kinetic": ArchivalKinetic, "logo": Logo}
SCENES.update(EXT_SCENES)
SCENES.update(EXT2_SCENES)
SCENES.update(EXT3_SCENES)
SCENES.update(EXT4_SCENES)


# ---------- zaman cizelgesi ----------
def build_timeline(tl):
    """explicitTiming: sahnelerde start/end hazir (anlatim zaman cizelgesinden). Degilse sureler art arda eklenir."""
    out = []
    if tl.get("explicitTiming"):
        for sp in tl["scenes"]:
            sp.setdefault("transitionIn", {"type": "none", "dur": 0})
            sp["duration"] = round(sp["end"] - sp["start"], 4)
            out.append(sp)
        total = max(sp["end"] for sp in out)
    else:
        t = 0.0
        for i, sp in enumerate(tl["scenes"]):
            ti = sp.get("transitionIn", {"type": "none", "dur": 0})
            start = t - (ti["dur"] if i > 0 else 0)
            sp["start"] = round(start, 4)
            sp["end"] = round(start + sp["duration"], 4)
            t = sp["end"]
            out.append(sp)
        total = t
    if tl.get("subtitles") is not None and out:
        out[0]["_globalSubs"] = [tuple(c) for c in tl["subtitles"]]
    return out, total


def subtitles(scenes):
    if scenes and "_globalSubs" in scenes[0]:
        return scenes[0]["_globalSubs"]
    cues = []
    for sp in scenes:
        for a, b, txt in sp.get("subtitleCues", []):
            cues.append((sp["start"] + a, sp["start"] + b, txt))
    return cues


def draw_subtitle(cv, img, T, cues):
    for a, b, txt in cues:
        if a <= T < b:
            op = min(prog(T, a, a + 0.18), 1 - prog(T, b - 0.18, b))
            lines = txt.split("\n")
            y = 1080 - SAFE_Y - 26 - 56 * len(lines)
            for ln in lines:
                draw_text(cv, img, ln, F_SEMI, 42, WHITE, 960, y, opacity=op, anchor="mt", shadow=7, tag="sub")
                y += 56


def transition(kind, a_img, b_img, p, fx, cv):
    if kind == "crossfade":
        return a_img * (1 - p) + b_img * p
    if kind == "dip":
        return a_img * max(0, 1 - 2 * p) if p < 0.5 else b_img * (2 * p - 1)
    if kind == "iris":
        r = (40 + 1200 * ease(p)) * cv.s
        m = fx.circle_mask(1290 * cv.s, 470 * cv.s, r, 3 * cv.s)
        return a_img * (1 - m) + b_img * m
    if kind == "lightleak":
        q = math.sin(math.pi * p)
        mix = a_img * (1 - ease(p)) + b_img * ease(p)
        sweep = np.clip(1 - np.abs((fx.xx / fx.W) - lerp(-0.3, 1.3, p)) * 1.8, 0, 1)[..., None]
        leak = sweep * np.array([0.25, 0.55, 1.0], np.float32) * 0.9 * q
        return mix + leak + q * 0.08
    return b_img


# ===================== v6: SINEMATIK 3B MANSET (headline3d) — bkz. SAHNE_MANSET_3B.md =====================
def _rot(rx, ry, rz):
    ax, ay, az = (math.radians(v) for v in (rx, ry, rz))
    Rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    Ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    Rz = np.array([[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]])
    return Ry @ Rz @ Rx


def _keys(t, keys):
    """[(t, deger...)] anahtar kareleri arasinda yumusak (ease) gecis."""
    if t <= keys[0][0]:
        return np.array(keys[0][1:], float)
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            u = ease((t - a[0]) / max(b[0] - a[0], 1e-6))
            return np.array(a[1:], float) * (1 - u) + np.array(b[1:], float) * u
    return np.array(keys[-1][1:], float)


class Headline3D(Scene):
    PW, PH, TH = 600.0, 774.0, 7.0          # gazete boyutu ve kalinligi (dunya birimi)
    NX, NZ = 8, 10                           # gazete agi hucreleri
    L = np.array([-0.50, -0.78, -0.36]) / np.linalg.norm([-0.50, -0.78, -0.36])   # anahtar isik yonu (yuzeyden isiga)
    T_FALL, T_HIT = 0.35, 1.15
    T_EDGE = 0.07   # koselerin gecikmeli inisi (iki asamali temas)

    def setup(self):
        p = self.p
        src = grade(load(self.spec["visualAssets"][0]), p.get("grade", "desat"))
        tex = cv2.resize(src, (900, int(900 * self.PH / self.PW)), interpolation=cv2.INTER_AREA)
        paper = np.array([0.93, 0.95, 0.97], np.float32)
        tex = tex * 0.92 + paper * 0.08
        self.cells = []
        th, tw = tex.shape[:2]
        for j in range(self.NZ):
            row = []
            for i in range(self.NX):
                x0, x1 = int(tw * i / self.NX), int(tw * (i + 1) / self.NX)
                y0, y1 = int(th * j / self.NZ), int(th * (j + 1) / self.NZ)
                c = tex[max(y0 - 1, 0):min(y1 + 1, th), max(x0 - 1, 0):min(x1 + 1, tw)].copy()
                row.append((c, np.ones(c.shape[:2], np.float32)))
            self.cells.append(row)
        self.tex = tex
        # kenar dokusu: 6 sayfa katmani
        side = np.zeros((14, 64, 3), np.float32)
        for k in range(14):
            side[k] = (0.80 if k % 2 == 0 else 0.62)
        self.side = (side * np.array([0.95, 0.97, 1.0], np.float32), np.ones((14, 64), np.float32))
        # masa dokusu: koyu ceviz (prosedurel damar), dikissiz tekrar
        rng = np.random.default_rng(21)
        S = 1024
        n1 = cv2.resize(rng.normal(0, 1, (8, 256)).astype(np.float32), (S, S), interpolation=cv2.INTER_CUBIC)
        n2 = cv2.resize(rng.normal(0, 1, (64, 512)).astype(np.float32), (S, S), interpolation=cv2.INTER_CUBIC)
        yy = np.arange(S, dtype=np.float32)[:, None]
        grain = np.sin(yy * 0.09 + n1 * 2.2) * 0.5 + 0.5
        wood = 0.62 + 0.34 * grain + 0.08 * n2
        base = np.array([0.085, 0.120, 0.170], np.float32)
        table = wood[..., None] * base
        fine = rng.normal(0, 0.006, (S, S)).astype(np.float32)[..., None]
        self.table = np.clip(table + fine, 0, 1)
        # toz parcaciklari (temas aninda dogar)
        N = 260
        self.d_edge = rng.uniform(0, 1, N)
        self.d_speed = rng.uniform(300, 900, N)
        self.d_up = rng.uniform(100, 420, N)
        self.d_size = rng.uniform(1.5, 4.5, N)
        self.d_life = rng.uniform(1.2, 2.0, N)
        self.d_jit = rng.uniform(-0.35, 0.35, N)
        # havadaki toz (atmosfer)
        M = 70
        self.m_p = np.stack([rng.uniform(-1300, 1300, M), rng.uniform(-950, -60, M), rng.uniform(-700, 1500, M)], 1)
        self.m_v = rng.normal(0, 1, (M, 3)) * np.array([14, 6, 10])
        self.m_ph = rng.uniform(0, 6.28, M)

    # --- durum ---
    def _tx(self, t):
        """Uzun sahnede (>4.2 sn) kamera ve cikis zamani sahneye yayilir; temas fizigi gercek zamanda kalir."""
        if self.d > 4.2 and t > 2.1:
            return 2.1 + (t - 2.1) * (4.0 - 2.1) / max(self.d - 2.1, 1.9)
        return t

    def cam(self, t):
        # ust-cayrek aci; temastan sonra mansetin okunacagi aciya yerlesir; cikista yukari (karanliga) kalkar
        k = _keys(t, [(0.0, -260, -1150, -1520, 34, 9), (1.15, -170, -1110, -1300, 40, 6), (2.10, -60, -1070, -990, 52, 3),
                      (3.25, -40, -1050, -930, 54, 2), (4.0, -30, -1080, -900, 46, 2)])
        if self.p.get("doc"):
            k[:3] = k[:3] * 0.93
        return Cam3(k[:3], yaw=k[4], pitch=k[3], f=1150)

    def paper_pose(self, t):
        u = prog(t, self.T_FALL, self.T_HIT)
        # hava yastigi: son %15'te yavaslama (dogrusal olmayan dusus)
        uu = u * u if u < 0.85 else 0.7225 + (u - 0.85) * 1.85 * (1 - (u - 0.85) * 1.6)
        y = -950 * (1 - min(uu, 1.0))
        if t > self.T_HIT:
            y = -9 * math.sin(math.pi * prog(t, self.T_HIT, self.T_HIT + 0.11)) * math.exp(-6 * (t - self.T_HIT))
        x = lerp(-80, 0, ease_out(u)); z = lerp(420, 0, ease_out(u))
        rx = 34 * (1 - u) ** 1.6; ry = lerp(-22, -4, ease_out(u)); rz = 9 * (1 - u) ** 2
        if t > self.T_HIT:
            dt = t - self.T_HIT
            if dt < self.T_EDGE:          # orta oturdu, koseler hala havada
                curl = lerp(34, 6, (dt / self.T_EDGE) ** 2)
            else:                          # koseler indi: sonumlenen titresim
                d2 = dt - self.T_EDGE
                curl = 6 + 7 * math.exp(-7 * d2) * math.cos(d2 * 26)
            flut = 0.0
        else:
            curl = lerp(60, 34, u)         # hava kenarlari yukari iter
            flut = 34 * (1 - u) * (0.6 + 0.4 * math.sin(t * 9))
        return np.array([x, y, z]), _rot(rx, ry, rz), curl, flut

    def grid(self, t, extra_y=0.0):
        c, R, curl, flut = self.paper_pose(t)
        hw, hh = self.PW / 2, self.PH / 2
        us = np.linspace(-hw, hw, self.NX + 1); vs = np.linspace(hh, -hh, self.NZ + 1)   # satir 0 = gorselin ustu (uzak)
        U, V = np.meshgrid(us, vs)
        corner = np.clip((np.abs(U) / hw) * (np.abs(V) / hh) - 0.45, 0, None) / 0.55
        lift = -(curl * corner ** 2) - flut * (U / hw) ** 2
        Ploc = np.stack([U, lift + extra_y, V], -1)
        Pw = Ploc @ R.T + c
        return Pw, c

    # --- cizim ---
    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s
        W, H = cv.W, cv.H
        cam = self.cam(self._tx(t))
        # 1) masa (dikissiz doku, perspektif) + sis + alan derinligi
        quad = np.array([[-1600, 0, -1200], [1600, 0, -1200], [1600, 0, 2200], [-1600, 0, 2200]], float)
        q, z = cam.proj(quad)
        Ts = self.table.shape[0]
        Mt = cv2.getPerspectiveTransform(np.float32([[0, 0], [Ts * 3, 0], [Ts * 3, Ts * 3.2], [0, Ts * 3.2]]), np.float32(q * s))
        img = cv2.warpPerspective(self.table, Mt, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        yy = fx.yy / H
        far = np.clip(1 - yy * 1.35, 0, 1) ** 1.6
        bg = navy_bg(cv, fx, t, glow=(0.05, 0.04, 0.03), center=(0.5, 0.0))
        img = img * (1 - far[..., None] * 0.85) + bg * far[..., None] * 0.85
        blur = cv2.GaussianBlur(img, (0, 0), 7 * s)
        dof = np.clip(far * 1.4 + np.clip(yy - 0.92, 0, 1) * 4, 0, 1)[..., None]
        img = img * (1 - dof) + blur * dof
        # isik havuzu ve masa parlamasi (anahtar isik ust soldan)
        hp, _ = cam.proj([[-260, 0, 420]])
        d = np.sqrt((fx.xx - hp[0, 0] * s) ** 2 + ((fx.yy - hp[0, 1] * s) * 1.6) ** 2) / (520 * s)
        img *= (0.70 + 1.05 * np.exp(-d ** 2 * 1.1))[..., None]                      # anahtar isik havuzu + dolgu (0.70)
        img += (np.exp(-d ** 2 * 5) * 0.035)[..., None] * np.array([0.85, 0.92, 1.0], np.float32)   # mat masada hafif parlama
        # 2) havadaki toz (arka katman)
        self._motes(img, cam, t, s, back=True)
        if t >= self.T_FALL - 0.05:
            Pw, c = self.grid(t)
            h_above = max(-c[1], 0)
            # 3) yansima (masaya yakinken)
            ra = np.clip(1 - h_above / 120, 0, 1) * 0.10
            if ra > 0.005:
                Pm = Pw.copy(); Pm[..., 1] = -Pm[..., 1] + 2 * self.TH
                cq, _ = cam.proj(Pm[[0, 0, -1, -1], [0, -1, -1, 0]])
                lay = np.zeros_like(img); al = np.zeros((H, W), np.float32)
                warp_quad(lay, self.tex, np.ones(self.tex.shape[:2], np.float32), cq, s)
                warp_quad(al[..., None].repeat(3, 2), self.tex, np.ones(self.tex.shape[:2], np.float32), cq, s)
                m = np.zeros((H, W), np.float32)
                cv2.fillConvexPoly(m, np.int32(cq * s), 1.0, cv2.LINE_AA)
                lay = cv2.GaussianBlur(lay, (0, 0), 10 * s); m = cv2.GaussianBlur(m, (0, 0), 10 * s)
                img = img * (1 - m[..., None] * ra) + lay * ra
            # 4) golge: kenar noktalari isik yonunde masaya izdusurulur
            ring = np.concatenate([Pw[0, :], Pw[1:, -1], Pw[-1, ::-1][1:], Pw[::-1, 0][1:-1]])
            tt = -ring[:, 1] / self.L[1]
            shadow_pts = ring + tt[:, None] * self.L * -1.0
            shadow_pts[:, 1] = 0
            sq, _ = cam.proj(shadow_pts)
            sm = np.zeros((H, W), np.float32)
            cv2.fillPoly(sm, [np.int32(cv2.convexHull(np.float32(sq * s)))], 1.0, cv2.LINE_AA)
            sig = (6 + 0.05 * h_above) * s
            sop = lerp(0.75, 0.25, min(h_above / 900, 1))
            sm = cv2.GaussianBlur(sm, (0, 0), sig)
            img *= (1 - sm[..., None] * sop)
            if h_above < 40:  # temas golgesi (ortam kapanmasi)
                fp = Pw.copy(); fp[..., 1] = 0
                fq, _ = cam.proj(fp[[0, 0, -1, -1], [0, -1, -1, 0]])
                ao = np.zeros((H, W), np.float32)
                cv2.fillConvexPoly(ao, np.int32(fq * s), 1.0, cv2.LINE_AA)
                ao = cv2.GaussianBlur(cv2.dilate(ao, np.ones((max(1, int(5 * s)),) * 2, np.uint8)), (0, 0), 3 * s)
                img *= (1 - ao[..., None] * 0.55 * (1 - h_above / 40))
            # 5) kagit kenarlari (kalinlik, sayfa katmanlari)
            Pb = Pw.copy(); Pb[..., 1] += self.TH
            edges = [(Pw[-1, i], Pw[-1, i + 1], Pb[-1, i + 1], Pb[-1, i]) for i in range(self.NX)]            # on kenar
            edges += [(Pw[j, -1], Pw[j + 1, -1], Pb[j + 1, -1], Pb[j, -1]) for j in range(self.NZ)]          # sag
            edges += [(Pw[j + 1, 0], Pw[j, 0], Pb[j, 0], Pb[j + 1, 0]) for j in range(self.NZ)]              # sol
            st, sa = self.side
            for e in edges:
                eq, ez = cam.proj(np.array(e))
                if ez.min() < 10:
                    continue
                n = np.cross(e[1] - e[0], e[3] - e[0]); n /= (np.linalg.norm(n) + 1e-9)
                lit = 0.45 + 0.4 * max(0.0, float(-n @ self.L))
                warp_quad(img, st * lit, sa, eq, s)
            # 6) ust yuzey hucreleri: normal x isik = golgelendirme; uzaktan yakina
            order = []
            for j in range(self.NZ):
                for i in range(self.NX):
                    a, b, c2, d2 = Pw[j, i], Pw[j, i + 1], Pw[j + 1, i + 1], Pw[j + 1, i]
                    nrm = np.cross(b - a, d2 - a); nrm /= (np.linalg.norm(nrm) + 1e-9)
                    if nrm[1] > 0:
                        nrm = -nrm
                    shade = 0.46 + 0.58 * max(0.0, float(nrm @ self.L))   # dolgu 0.46 + anahtar
                    qq, zz = cam.proj(np.array([a, b, c2, d2]))
                    order.append((zz.mean(), qq, shade, j, i))
            order.sort(key=lambda o: -o[0])
            sweep = prog(t, 2.35, 3.05)
            for zz, qq, shade, j, i in order:
                ci, ca = self.cells[j][i]
                k = min(shade * 1.08, 1.15)
                if p.get("doc"):
                    k = lerp(1.0, k, 0.35)   # duz kagit: hucre gecisi gorunmesin
                tint = ci * k
                if 0 < sweep < 1 and j <= 2:   # ust satirlar = manset bolgesi
                    band = math.exp(-(((i + 0.5) / self.NX - lerp(-0.2, 1.2, sweep)) / 0.12) ** 2)
                    tint = tint + band * 0.22 * (np.array(YELLOW, np.float32) / 255.0)
                dv = qq - qq.mean(0)
                qq = qq + dv / (np.linalg.norm(dv, axis=1, keepdims=True) + 1e-6) * (1.4 / s)   # komsu hucreler arasi dikis olmasin
                warp_quad(img, tint, ca, qq, s)
            # 7) kenar isigi: isiga bakan sol ve uzak kenar
            rimpts, _ = cam.proj(np.concatenate([Pw[::-1, 0], Pw[0, :]]))
            rim = np.zeros((H, W), np.float32)
            cv2.polylines(rim, [np.int32(rimpts * s)], False, 1.0, max(1, int(2 * s)), cv2.LINE_AA)
            img += (rim * 0.18 + cv2.GaussianBlur(rim, (0, 0), 3 * s) * 0.12)[..., None]
            # 8) toz (temas aninda)
            if t > self.T_HIT - 0.03:
                self._dust(img, cam, t - (self.T_HIT - 0.03), Pw, s)
        self._motes(img, cam, t, s, back=False)
        # 9a) karanliktan dogus (0-0.35): isik yandan acilir
        if t < 0.6:
            reveal = ease(prog(t, 0.0, 0.55))
            sidek = np.clip((fx.xx / W) * 1.6 - (1 - reveal) * 1.4, 0, 1)
            img *= (sidek * reveal)[..., None] * 0.85 + 0.15 * reveal
        # 9b) cikis (3.25-4.0): ust kadraj karanliga ve lacivert tona yaklasir (sonraki sahne: yukaridan dusen paralar)
        tx = self._tx(t)
        if tx > 3.25:
            e = ease(prog(tx, 3.25, 4.0))
            top = np.clip(1 - fx.yy / (H * 0.75), 0, 1)[..., None]
            img = img * (1 - 0.55 * e * top) + navy_bg(cv, fx, t) * 0.55 * e * top
        # 9) hacimli isik huzmesi (ust soldan)
        beam = np.clip(1 - np.abs((fx.xx / W) * 0.9 + (fx.yy / H) * 0.55 - 0.55) * 2.2, 0, 1) ** 2
        img += beam[..., None] * np.array([0.05, 0.055, 0.06], np.float32)
        # 10) darbe: %2 iceri "vurus" + dikey agirlikli sarsinti, ~6 karede soner
        if t > self.T_HIT:
            dt = t - self.T_HIT
            amp = 13 * math.exp(-13 * dt)
            punch = 1.0 + 0.02 * math.exp(-((dt - 0.02) / 0.05) ** 2)
            if amp > 0.2 or punch > 1.001:
                dx = amp * 0.45 * math.sin(2 * math.pi * 31 * dt) * s
                dy = amp * math.cos(2 * math.pi * 24 * dt) * s
                ang = 0.35 * math.exp(-13 * dt) * math.sin(2 * math.pi * 19 * dt)
                M = cv2.getRotationMatrix2D((W / 2, H * 0.55), ang, punch)
                M[0, 2] += dx; M[1, 2] += dy
                img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT101)
        # 11) yazi: goruntu sakinlestikten sonra
        if p.get("kicker"):
            ky = 150 if (p.get("doc") or not self.spec.get("noSubs")) else 1080 - SAFE_Y - 120   # altyazi varsa ust tarafa (cakisma onlemi)
            draw_text(cv, img, p["kicker"], F_BOLD, 30, YELLOW, SAFE_X + 40, ky, reveal=prog(t, 2.2, 2.8), tracking=8, shadow=10)
        self.caption(img, t)
        return img

    def _dust(self, img, cam, dt, Pw, s):
        ring = np.concatenate([Pw[0, :], Pw[1:, -1], Pw[-1, ::-1][1:], Pw[::-1, 0][1:-1]])
        n = len(ring)
        idx = (self.d_edge * (n - 1)).astype(int)
        p0 = ring[idx]; p0[:, 1] = -2
        cen = Pw.reshape(-1, 3).mean(0)
        out = p0 - cen; out[:, 1] = 0
        out /= (np.linalg.norm(out, axis=1, keepdims=True) + 1e-9)
        ca, sa = np.cos(self.d_jit), np.sin(self.d_jit)
        ox = out[:, 0] * ca - out[:, 2] * sa; oz = out[:, 0] * sa + out[:, 2] * ca
        k = 2.6
        fall = (1 - np.exp(-k * dt)) / k
        P = np.stack([p0[:, 0] + ox * self.d_speed * fall,
                      np.minimum(p0[:, 1] - self.d_up * fall + 0.5 * 900 * dt * dt * math.exp(-0.8 * dt), 0),
                      p0[:, 2] + oz * self.d_speed * fall], 1)
        q, z = cam.proj(P)
        age = dt / self.d_life
        vis = np.clip(1 - age, 0, 1) ** 1.5
        H, W = img.shape[:2]
        lay = np.zeros((H, W), np.float32)
        for i in range(len(P)):
            if vis[i] <= 0.01 or z[i] < 50:
                continue
            r = max(1, int(cam.f * self.d_size[i] / z[i] * s))
            cv2.circle(lay, (int(q[i, 0] * s), int(q[i, 1] * s)), r, float(vis[i]), -1, cv2.LINE_AA)
        lay = cv2.GaussianBlur(lay, (0, 0), 2.2 * s) * 0.32
        col = np.array([0.55, 0.62, 0.70], np.float32)
        img[:] = img * (1 - lay[..., None]) + col * lay[..., None]

    def _motes(self, img, cam, t, s, back):
        P = self.m_p + self.m_v * t
        P[:, 1] += np.sin(t * 0.8 + self.m_ph) * 12
        q, z = cam.proj(P)
        sel = (z > 1250) if back else (z <= 1250)
        H, W = img.shape[:2]
        lay = np.zeros((H, W), np.float32)
        for i in np.where(sel & (z > 60))[0]:
            r = max(1, int(cam.f * 3.0 / z[i] * s * (2.5 if not back else 1.0)))
            tw = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 2.1 + self.m_ph[i]))
            cv2.circle(lay, (int(q[i, 0] * s), int(q[i, 1] * s)), r, tw, -1, cv2.LINE_AA)
        lay = cv2.GaussianBlur(lay, (0, 0), (1.2 if back else 3.5) * s) * (0.35 if back else 0.25)
        img += lay[..., None] * np.array([0.80, 0.90, 1.0], np.float32)


EXT5_SCENES = {"headline3d": Headline3D}

SCENES.update(EXT5_SCENES)


# ===================== v7: SINEMATIK KALABALIK (crowd3d_cine) — bkz. SAHNE_KALABALIK_3B.md =====================
class CrowdCine(Scene):
    """Gercekci cocuk kalabaligi: 4 silüet tipi (sprite onbellegi), arkadan safak isigi, kenar isigi, uzun golgeler, sis."""
    COLS, ROWS = 64, 46
    _SPR = None

    def setup(self):
        rng = np.random.default_rng(9)
        X, Z = np.meshgrid(np.linspace(-2300, 2300, self.COLS), np.linspace(420, 7200, self.ROWS))
        X = X + rng.uniform(-30, 30, X.shape); Z = Z + rng.uniform(-45, 45, Z.shape)
        self.X, self.Z = X.ravel(), Z.ravel()
        row = np.repeat(np.arange(self.ROWS), self.COLS) / self.ROWS
        self.t_on = 0.7 + 2.6 * row + rng.uniform(0, 0.25, X.size)
        self.hgt = rng.uniform(0.80, 1.12, X.size)
        self.var = rng.integers(0, 4, X.size)
        self.flip = rng.integers(0, 2, X.size)
        self.motes = np.stack([rng.uniform(-900, 900, 60), rng.uniform(-420, -30, 60), rng.uniform(80, 1400, 60)], 1)
        self.mph = rng.uniform(0, 6.28, 60)
        if CrowdCine._SPR is None:
            d = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "kids_sprites.npz"))
            base = [d[k].astype(np.float32) / 255.0 for k in ("boy", "cap", "girl", "pony")]
            sprs = []
            for m in base:
                sh = np.zeros_like(m); sh[6:, :-5] = m[:-6, 5:]          # isik sag-ustten: kenar = maske - kaydirilmis maske
                rim = np.clip(m - sh, 0, 1)
                rim = cv2.GaussianBlur(rim, (0, 0), 1.5)
                sprs.append((m, rim))
            CrowdCine._SPR = sprs
        self.cache = {}
        # zemin dokusu (ot / toprak)
        n = rng.normal(0, 1, (270, 480)).astype(np.float32)
        self.grass = cv2.resize(cv2.GaussianBlur(n, (0, 0), 0.8), (cv.W, cv.H), interpolation=cv2.INTER_LINEAR) * 0.012 if False else None

    def sprite(self, v, flip, hpx):
        key = (v, flip, hpx)
        c = self.cache.get(key)
        if c is None:
            m, rim = CrowdCine._SPR[v]
            w = max(1, int(round(hpx * m.shape[1] / m.shape[0])))
            ms = cv2.resize(m, (w, hpx), interpolation=cv2.INTER_AREA)
            rs = cv2.resize(rim, (w, hpx), interpolation=cv2.INTER_AREA)
            if flip:
                ms, rs = ms[:, ::-1], rs[:, ::-1]
            c = (np.ascontiguousarray(ms), np.ascontiguousarray(rs))
            if len(self.cache) > 4000:
                self.cache.clear()
            self.cache[key] = c
        return c

    def cam(self, t):
        k = _keys(t, [(0.0, -120, -95, -40, -2, 4), (0.6, -120, -100, -50, -1.5, 3.6), (3.4, -40, -760, -420, 17, -3), (5.0, -30, -790, -360, 17.5, -3)])
        return Cam3(k[:3], yaw=k[4], pitch=k[3], f=1150)

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s; W, H = cv.W, cv.H
        cam = self.cam(t)
        sun = np.array([0.55, 0.80, 1.0], np.float32)
        hz, _ = cam.proj([[0, 0, 1e6]])
        hy = hz[0, 1] * s
        yy = fx.yy
        # safak gokyuzu: lacivert -> mor-gri -> turuncu ufuk
        u = np.clip((hy - yy) / (H * 0.85), 0, 1)[..., None]
        c_top = np.array([0.14, 0.07, 0.035], np.float32); c_mid = np.array([0.30, 0.22, 0.24], np.float32); c_hor = np.array([0.36, 0.56, 0.86], np.float32)
        img = np.where(u > 0.35, c_mid + (c_top - c_mid) * ((u - 0.35) / 0.65), c_hor + (c_mid - c_hor) * (u / 0.35)).astype(np.float32)
        g = np.clip((yy - hy) / (H * 0.9), 0, 1)[..., None]
        ground = np.array([0.030, 0.040, 0.040], np.float32) + c_hor * 0.30 * (1 - g) ** 8
        img = np.where((yy >= hy)[..., None], ground + (fx.grain[3][..., None] * 0.010) * (yy >= hy)[..., None], img).astype(np.float32)
        sx, sy = 1180 * s, hy - 26 * s
        d = np.sqrt((fx.xx - sx) ** 2 + (fx.yy - sy) ** 2) / (W * 0.5)
        img += (np.exp(-d ** 2 * 420) * 1.2 + np.exp(-d ** 2 * 18) * 0.20 + np.exp(-d ** 2 * 2.5) * 0.06)[..., None] * sun
        ang = np.arctan2(fx.yy - sy, fx.xx - sx)
        rays = (0.5 + 0.5 * np.cos(ang * 5 + t * 0.15)) ** 8 * np.exp(-d * 2.4)
        img += (rays * 0.04)[..., None] * sun
        # figurler
        P0 = np.stack([self.X, np.zeros_like(self.X), self.Z], 1)
        base, z = cam.proj(P0)
        Hf = 118 * self.hgt
        top_, _ = cam.proj(np.stack([self.X, -Hf, self.Z], 1))
        order = np.argsort(-z)
        shadow = np.zeros((H, W), np.float32)
        glow = np.zeros((H, W), np.float32)
        fogc = c_hor * 0.85
        warm = np.array((0.20, 0.40, 0.70), np.float32)
        dark = np.array((0.075, 0.07, 0.075), np.float32)
        pitch_k = max(0.12, math.sin(math.radians(cam_pitch(t, self))) + 0.15)
        for i in order:
            zi = z[i]
            if zi < 40:
                continue
            bx, by = base[i] * s
            hp = by - top_[i, 1] * s
            if hp < 1.0 or by < -20 or by - hp > H or bx < -200 or bx > W + 200:
                continue
            fog = float(np.clip((zi - 300) / 6400, 0, 0.94)) ** 0.8
            on = float(np.clip((t - self.t_on[i]) / 0.3, 0, 1))
            body = dark * (1 - on) + warm * on
            body = body * (1 - fog) + fogc * fog
            rimc = sun * (1.15 + 0.35 * on) * (1 - 0.75 * fog)
            sl = hp * 3.6 * pitch_k
            cv2.ellipse(shadow, (int(bx), int(by + sl * 0.45)), (max(1, int(hp * 0.16)), max(1, int(sl * 0.5))), 0, 0, 360, 1.0 - fog, -1)
            if hp >= 7:
                hpx = int(round(hp)) if hp < 80 else int(round(hp / 4) * 4)
                m, rim = self.sprite(int(self.var[i]), int(self.flip[i]), hpx)
                hh, ww = m.shape
                x0 = int(bx - ww / 2); y0 = int(by - hh)
                xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + ww, W), min(y0 + hh, H)
                if xb <= xa or yb <= ya:
                    continue
                ms = m[ya - y0:yb - y0, xa - x0:xb - x0][..., None]
                rs = rim[ya - y0:yb - y0, xa - x0:xb - x0][..., None]
                roi = img[ya:yb, xa:xb]
                img[ya:yb, xa:xb] = roi * (1 - ms) + body * ms + rs * rimc * 0.9
            else:
                cv2.ellipse(img, (int(bx), int(by - hp * 0.5)), (max(1, int(hp * 0.16)), max(1, int(hp * 0.5))), 0, 0, 360, body.tolist(), -1, cv2.LINE_AA)
            if on > 0:
                cv2.circle(glow, (int(bx), int(by - hp * 0.55)), max(1, int(hp * 0.45)), on * (1 - fog * 0.7), -1)
        sh_op = 0.55 * min(1.0, max(0.0, (pitch_k - 0.12) / 0.25))   # goz hizasinda golgeler lekelenmesin
        img *= (1 - cv2.GaussianBlur(shadow, (0, 0), 2.5 * s)[..., None] * sh_op)
        img += cv2.GaussianBlur(glow, (0, 0), 8 * s)[..., None] * warm * 0.18
        Pm = self.motes + np.array([t * 18, 0, 0]) + np.stack([np.zeros(60), np.sin(t + self.mph) * 10, np.zeros(60)], 1)
        mq, mz = cam.proj(Pm)
        lay = np.zeros((H, W), np.float32)
        for i in range(len(Pm)):
            if mz[i] > 30:
                cv2.circle(lay, (int(mq[i, 0] * s), int(mq[i, 1] * s)), max(1, int(cam.f * 1.6 / mz[i] * s)), 0.7, -1, cv2.LINE_AA)
        img += cv2.GaussianBlur(lay, (0, 0), 2 * s)[..., None] * sun * 0.30
        frac = float(np.mean(t > self.t_on))
        v = int(round(p["value"] * frac))
        rrect(img, SAFE_X + 20, 100, SAFE_X + 760, 330, 14, (0.04, 0.03, 0.02), 0.45, s)
        draw_text(cv, img, f"{v:,}".replace(",", "."), F_BLACK, 110, WHITE, SAFE_X + 40, 110, opacity=ease_out(prog(t, 0.2, 0.7)), tracking=2, shadow=12)
        draw_text(cv, img, p["label"], F_BOLD, 34, YELLOW, SAFE_X + 44, 245, reveal=prog(t, 0.5, 1.1), tracking=6)
        if p.get("note"):
            draw_text(cv, img, p["note"], F_MED, 22, (220, 220, 220), SAFE_X + 44, 1080 - SAFE_Y - 40, opacity=0.8 * ease(prog(t, 1.0, 1.5)), tracking=1)
        return img


def cam_pitch(t, sc):
    return _keys(t, [(0.0, -2), (0.6, -1.5), (3.4, 17), (5.0, 17.5)])[0]


EXT6_SCENES = {"crowd3d_cine": CrowdCine}

SCENES.update(EXT6_SCENES)



# ===================== v8: GERCEKCILIK PAKETI =====================
_HERE = os.path.dirname(os.path.abspath(__file__))


def add_rgba(img, rgb, alpha, x0, y0):
    """rgb (premult) + alpha'yi img'ye (piksel koordinati) kirparak bindirir."""
    h, w = alpha.shape[:2]
    H, W = img.shape[:2]
    x0, y0 = int(round(x0)), int(round(y0))
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if xb <= xa or yb <= ya:
        return
    a = alpha[ya - y0:yb - y0, xa - x0:xb - x0]
    if a.ndim == 2:
        a = a[..., None]
    img[ya:yb, xa:xb] = img[ya:yb, xa:xb] * (1 - a) + rgb[ya - y0:yb - y0, xa - x0:xb - x0]


# ---------- figurler: bolge etiketli siluet + hacim golgelendirme ----------
_FIG = {}
FIG_PALS = [  # BGR: ten, sac, ust, alt, ayakkabi, aksesuar
    [(0.55, 0.66, 0.86), (0.10, 0.14, 0.22), (0.22, 0.35, 0.72), (0.40, 0.25, 0.15), (0.08, 0.08, 0.09), (0.18, 0.18, 0.60)],
    [(0.48, 0.60, 0.80), (0.06, 0.08, 0.12), (0.70, 0.55, 0.30), (0.20, 0.20, 0.24), (0.07, 0.07, 0.08), (0.80, 0.80, 0.80)],
    [(0.52, 0.64, 0.84), (0.14, 0.24, 0.40), (0.30, 0.62, 0.40), (0.45, 0.30, 0.18), (0.10, 0.09, 0.08), (0.20, 0.30, 0.65)],
    [(0.42, 0.55, 0.76), (0.05, 0.06, 0.08), (0.85, 0.85, 0.86), (0.35, 0.22, 0.12), (0.08, 0.08, 0.10), (0.25, 0.25, 0.70)],
    [(0.56, 0.68, 0.88), (0.18, 0.32, 0.52), (0.35, 0.40, 0.82), (0.25, 0.25, 0.30), (0.09, 0.09, 0.10), (0.75, 0.75, 0.78)],
    [(0.50, 0.62, 0.82), (0.08, 0.10, 0.16), (0.55, 0.38, 0.22), (0.18, 0.22, 0.32), (0.07, 0.07, 0.07), (0.30, 0.55, 0.75)],
    [(0.46, 0.58, 0.78), (0.10, 0.12, 0.18), (0.25, 0.55, 0.80), (0.42, 0.42, 0.45), (0.08, 0.08, 0.09), (0.70, 0.30, 0.25)],
    [(0.54, 0.66, 0.86), (0.12, 0.20, 0.34), (0.60, 0.30, 0.45), (0.30, 0.20, 0.12), (0.10, 0.10, 0.10), (0.80, 0.80, 0.82)],
]


def fig_base():
    if not _FIG:
        d = np.load(os.path.join(_HERE, "figures.npz"))
        for k in ("boy", "cap", "girl", "pony", "man", "woman"):
            m = d[k + "_m"].astype(np.float32) / 255.0
            l = d[k + "_l"].astype(np.int32)
            dt = cv2.distanceTransform((m > 0.5).astype(np.uint8), cv2.DIST_L2, 5)
            dt = cv2.GaussianBlur(dt, (0, 0), 2.5)
            gx = cv2.Sobel(dt, cv2.CV_32F, 1, 0, ksize=5); gy = cv2.Sobel(dt, cv2.CV_32F, 0, 1, ksize=5)
            n = np.sqrt(gx ** 2 + gy ** 2) + 1e-6
            edge = np.clip(1 - dt / 9.0, 0, 1)            # kenara yakin bant: hacim burada okunur
            _FIG[k] = (m, l, -gx / n * edge, -gy / n * edge, np.clip(dt / 18.0, 0, 1))
    return _FIG


_FIGC = {}
def fig_sprite(kind, hpx, pal_i, flip=False, light=(-0.6, -0.5), amb=0.42, key=0.75, rim=(0.7, -0.3), rimk=0.0, warm=0.0, sat=1.0):
    """Isiklandirilmis figur (premult rgb, alpha). hpx: piksel boyu. rimk: kenar isigi gucu; warm: sicak isik orani; sat: doygunluk."""
    key_ = (kind, hpx, pal_i, flip, round(rimk, 2), round(warm, 2), round(sat, 2), light, amb, key)
    c = _FIGC.get(key_)
    if c is not None:
        return c
    m, l, nx, ny, core = fig_base()[kind]
    w = max(1, int(round(hpx * m.shape[1] / m.shape[0])))
    rs = lambda a, it=cv2.INTER_AREA: cv2.resize(a, (w, hpx), interpolation=it)
    ms = rs(m)
    ls = cv2.resize(l.astype(np.uint8), (w, hpx), interpolation=cv2.INTER_NEAREST).astype(np.int32)
    nxs, nys, cs = rs(nx), rs(ny), rs(core)
    if flip:
        ms, ls, nxs, nys, cs = ms[:, ::-1], ls[:, ::-1], -nxs[:, ::-1], nys[:, ::-1], cs[:, ::-1]
    pal = np.array([(0, 0, 0)] + FIG_PALS[pal_i % len(FIG_PALS)], np.float32)
    alb = pal[ls]
    if sat < 1:
        g = alb.mean(2, keepdims=True)
        alb = alb * sat + g * (1 - sat)
    lam = np.clip(nxs * light[0] + nys * light[1], -1, 1)
    shade = amb + key * (0.55 + 0.45 * lam) * (0.75 + 0.25 * cs)
    vert = np.linspace(1.08, 0.78, hpx, dtype=np.float32)[:, None]     # ust isik: bas parlak, ayaklar golgede
    rgb = alb * (shade * vert)[..., None]
    if warm > 0:
        rgb = rgb * (1 - 0.35 * warm) + rgb * np.array([0.55, 0.95, 1.55], np.float32) * 0.35 * warm
    if rimk > 0:
        rr = np.clip(nxs * rim[0] + nys * rim[1], 0, 1) ** 1.5
        rgb = rgb + (rr * rimk)[..., None] * np.array([0.70, 0.88, 1.0], np.float32)
    out = (np.ascontiguousarray(rgb * ms[..., None]), np.ascontiguousarray(ms))
    if len(_FIGC) > 6000:
        _FIGC.clear()
    _FIGC[key_] = out
    return out


# ---------- gercekci poliovirus kapsidi (ikozahedral yuzey) ----------
_ICO = {}
def _ico():
    if not _ICO:
        from itertools import combinations
        phi = (1 + 5 ** 0.5) / 2
        V = np.array([[-1, phi, 0], [1, phi, 0], [-1, -phi, 0], [1, -phi, 0], [0, -1, phi], [0, 1, phi], [0, -1, -phi], [0, 1, -phi],
                      [phi, 0, -1], [phi, 0, 1], [-phi, 0, -1], [-phi, 0, 1]], float)
        V /= np.linalg.norm(V, axis=1, keepdims=True)
        D = np.linalg.norm(V[:, None] - V[None], axis=2); e = D[D > 0].min()
        F = [f for f in combinations(range(12), 3) if all(abs(D[a, b] - e) < 1e-6 for a, b in combinations(f, 2))]
        C = np.array([V[list(f)].mean(0) for f in F]); C /= np.linalg.norm(C, axis=1, keepdims=True)
        P = []
        for f in F:
            a, b, c = V[list(f)]
            for x, y, z in ((a, b, c), (b, c, a), (c, a, b)):
                q = 0.60 * x + 0.20 * y + 0.20 * z; P.append(q / np.linalg.norm(q))
        rng = np.random.default_rng(3)
        Q = rng.normal(0, 1, (260, 3)); Q /= np.linalg.norm(Q, axis=1, keepdims=True)
        _ICO.update(V=V, C=C, P=np.array(P), Q=Q)
    return _ICO


def _rot_axis(ax, ang):
    ax = np.asarray(ax, float); ax /= np.linalg.norm(ax)
    K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


_CAP = {}
def capsid_maps(px, ang, axis=(0.35, 1.0, 0.15)):
    """Kapsid isik haritalari: difuz, parlama, kenar isigi, ortam kapanmasi, alfa. ang: derece."""
    key = (px, round(ang, 1), tuple(axis))
    c = _CAP.get(key)
    if c is not None:
        return c
    G = _ico()
    S = px
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    R = S * 0.42
    x, y = (xx - S / 2) / R, (yy - S / 2) / R
    rho = np.sqrt(x * x + y * y)
    inside0 = rho < 1.12
    nz = np.sqrt(np.clip(1 - rho * rho, 0, 1))
    rr = np.maximum(rho, 1e-6)
    N = np.stack([np.where(rho < 1, x, x / rr), np.where(rho < 1, y, y / rr), np.where(rho < 1, nz, 0)], -1)
    Rm = _rot_axis(axis, math.radians(ang))
    No = N[inside0] @ Rm          # nesne uzayi
    def bump(Pts, w):
        return np.exp(-(1 - np.clip(No @ Pts.T, -1, 1)) / w).sum(1)
    dv = No @ G["V"].T
    angv = np.arccos(np.clip(dv, -1, 1))
    h = (0.80 * np.exp(-(1 - dv) / 0.010).sum(1)          # 5-katli tepe (mesa)
         - 0.22 * np.exp(-((angv - 0.27) / 0.045) ** 2).sum(1)   # sig kanyon
         + 0.95 * bump(G["P"], 0.0050)                     # VP1 alt birimleri (belirgin yumrular)
         + 0.60 * bump(G["C"], 0.0055)                     # 3-katli pervane
         + 0.38 * bump(G["Q"], 0.0018))                    # ince protein dokusu
    H = np.zeros((S, S), np.float32); H[inside0] = h
    hn = (H - 0.0) / 1.6
    alpha = np.clip((1 + 0.075 * np.clip(hn, -1, 1.2) - rho) * R / 1.2, 0, 1).astype(np.float32)
    # yuzey normali: kure normali + yukseklik egimi
    gx = cv2.Sobel(H, cv2.CV_32F, 1, 0, ksize=3) / (R * 0.09)
    gy = cv2.Sobel(H, cv2.CV_32F, 0, 1, ksize=3) / (R * 0.09)
    nxp, nyp, nzp = N[..., 0] - gx * 0.9, N[..., 1] - gy * 0.9, N[..., 2] + 0.05
    nn = np.sqrt(nxp ** 2 + nyp ** 2 + nzp ** 2) + 1e-6
    nxp, nyp, nzp = nxp / nn, nyp / nn, nzp / nn
    L = np.array([-0.50, -0.62, 0.60]); L /= np.linalg.norm(L)
    ndl = nxp * L[0] + nyp * L[1] + nzp * L[2]
    diff = np.clip((ndl + 0.25) / 1.25, 0, 1)
    Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
    spec = np.clip(nxp * Hh[0] + nyp * Hh[1] + nzp * Hh[2], 0, 1) ** 28
    Lr = np.array([0.75, 0.15, -0.55]); Lr /= np.linalg.norm(Lr)
    rim = np.clip(nxp * Lr[0] + nyp * Lr[1] + nzp * Lr[2], 0, 1) ** 1.6 * (1 - nz) ** 0.5
    ao = np.clip(0.42 + 0.40 * hn, 0.22, 1.0)
    out = tuple(a.astype(np.float32) for a in (diff, spec, rim, ao, alpha))
    if len(_CAP) > 400:
        _CAP.clear()
    _CAP[key] = out
    return out


def capsid_rgba(px, ang, col, rimcol=(1.0, 0.85, 0.55), axis=(0.35, 1.0, 0.15), spec_k=0.55):
    diff, spec, rim, ao, a = capsid_maps(px, ang, axis)
    col = np.array(col, np.float32)
    rgb = col * (0.07 + 0.95 * diff * ao)[..., None] + (spec * spec_k * ao)[..., None] + rim[..., None] * np.array(rimcol, np.float32) * 0.55
    return (rgb * a[..., None]).astype(np.float32), a


_VF = {}
def virus_field(cv, fx, t, n=60, seed=4, dark=1.0, speed=160, color=(0.80, 0.86, 0.25)):
    """3B virus alani (gercekci kapsidler): kamera ileri suzulur, alan derinligi + sis."""
    img = navy_bg(cv, fx, t, glow=(0.12, 0.10, 0.02), center=(0.5, 0.5))
    rng = np.random.default_rng(seed)
    P = np.stack([rng.uniform(-1500, 1500, n), rng.uniform(-900, 900, n), rng.uniform(200, 3600, n)], 1)
    spin = rng.uniform(-0.3, 0.3, n)
    var = rng.integers(0, 6, n)
    P[:, 2] = (P[:, 2] - t * speed - 200) % 3400 + 200
    P[:, 0] += np.sin(t * 0.4 + spin * 10) * 40
    cam = Cam3((0, 0, 0), yaw=math.sin(t * 0.25) * 4, pitch=math.cos(t * 0.2) * 3)
    xy, z = cam.proj(P)
    order = np.argsort(-z)
    focus = 900
    S = 192
    for i in order:
        if z[i] < 120:
            continue
        size = cam.f * 85 / z[i] * 1.25
        if size < 3:
            continue
        dz = abs(z[i] - focus) / focus
        lvl = 0 if dz < 0.35 else (1 if dz < 0.9 else 2)
        k = (int(var[i]), tuple(np.round(color, 3)), lvl)
        spr = _VF.get(k)
        if spr is None:
            rgb, a = capsid_rgba(S, 37.0 * var[i] + 11, color, rimcol=(0.95, 0.85, 0.6))
            spr = np.dstack([rgb, a]).astype(np.float32)
            if lvl:
                spr = cv2.GaussianBlur(spr, (0, 0), S * (0.02 if lvl == 1 else 0.05))
            _VF[k] = spr
        fog = np.clip(1.2 - z[i] / 3600, 0.15, 1.0)
        near = np.clip((z[i] - 120) / 300, 0, 1)
        paste_sprite(img, spr, xy[i, 0], xy[i, 1], size, cv.s, fog * near * dark)
    return img


class Virus3DReal(Scene):
    """Kahraman kapsid (yavas doner) + arka planda virus alani. dead_t: formaldehit ani -> renk soner, donus durur."""
    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s
        dead = p.get("dead_t")
        live = np.array((0.30, 0.72, 0.95), np.float32)      # BGR: sicak altin-turuncu
        grey = np.array((0.62, 0.58, 0.55), np.float32)
        k = ease(prog(t, dead, dead + 1.2)) if dead is not None else 0.0
        img = virus_field(cv, fx, t, n=p.get("n", 55), speed=p.get("speed", 120), color=tuple(np.round(live * (1 - k) + grey * k, 2)), dark=0.75)
        img = cv2.GaussianBlur(img, (0, 0), 1.2 * s) * (1 - 0.25 * k)
        # kahraman
        w0 = 9.0
        td = dead if dead is not None else 1e9
        ang = w0 * min(t, td) + (w0 * (1 - math.exp(-(t - td) * 1.6)) / 1.6 if t > td else 0)
        px = max(64, int(600 * s) // 4 * 4)
        col = live * (1 - k) + grey * k
        rgb, a = capsid_rgba(px, round(ang * 2) / 2, col, rimcol=(1.0, 0.85, 0.55) if k < 0.5 else (0.95, 0.9, 0.85), spec_k=0.55 - 0.25 * k)
        cx, cy = 1180 + 14 * math.sin(t * 0.5), 480 + 10 * math.cos(t * 0.4)
        sc = lerp(0.92, 1.0, ease_out(prog(t, 0, 1.2)))
        if sc != 1.0:
            nps = max(8, int(px * sc))
            rgb = cv2.resize(rgb, (nps, nps), interpolation=cv2.INTER_AREA); a = cv2.resize(a, (nps, nps), interpolation=cv2.INTER_AREA)
        # arka isik halesi
        hal = np.zeros(img.shape[:2], np.float32)
        cv2.circle(hal, (int(cx * s), int(cy * s)), int(250 * s), 1.0, -1)
        img += cv2.GaussianBlur(hal, (0, 0), 90 * s)[..., None] * (live * 0.10 * (1 - k) + 0.03)
        add_rgba(img, rgb, a * ease_out(prog(t, 0, 0.8)), cx * s - rgb.shape[1] / 2, cy * s - rgb.shape[0] / 2)
        # formaldehit sisi (olum aninda kapsidi saran soguk buhar)
        if dead is not None and t > dead - 0.4:
            rng = np.random.default_rng(31)
            n = 140
            th = rng.uniform(0, 6.28, n); rr = rng.uniform(260, 520, n); ph = rng.uniform(0, 1, n)
            u = prog(t, dead - 0.4, dead + 2.0)
            lay = np.zeros(img.shape[:2], np.float32)
            for i in range(n):
                q = (u * 1.4 + ph[i]) % 1.0
                r_ = rr[i] * (1 - 0.55 * q)
                x_ = cx + math.cos(th[i] + q * 0.8) * r_; y_ = cy + math.sin(th[i] + q * 0.8) * r_ * 0.8
                cv2.circle(lay, (int(x_ * s), int(y_ * s)), max(1, int(rng.uniform(2, 5) * s)), (1 - q) * 0.8, -1, cv2.LINE_AA)
            img += cv2.GaussianBlur(lay, (0, 0), 3 * s)[..., None] * np.array((0.9, 0.85, 0.75), np.float32) * 0.35 * (1 - prog(t, dead + 1.6, dead + 2.6))
        # olcek isareti (bilimsel)
        la = ease(prog(t, 0.8, 1.4))
        r = 285
        arc = np.zeros(img.shape[:2], np.float32)
        cv2.ellipse(arc, (int(cx * s), int(cy * s)), (int(r * s), int(r * s)), 0, 200, 250, 1.0, max(1, int(2 * s)), cv2.LINE_AA)
        cv2.ellipse(arc, (int(cx * s), int(cy * s)), (int(r * s), int(r * s)), 0, 20, 70, 1.0, max(1, int(2 * s)), cv2.LINE_AA)
        img += arc[..., None] * (np.array(TEAL, np.float32) / 255.0) * 0.8 * la
        draw_text(cv, img, "≈ 30 nm", F_SEMI, 24, TEAL, cx + 150, cy - 300, opacity=0.9 * la, tracking=3, shadow=0, check_safe=False)
        if k > 0.02:
            draw_text(cv, img, "ETKİSİZ · ÇOĞALAMAZ", F_BOLD, 24, (230, 230, 230), cx + 120, cy + 290, opacity=k, tracking=4, shadow=4, check_safe=False)
        if p.get("title"):
            la2 = prog(t, 0.5, 1.1)
            rrect(img, SAFE_X + 20, 640, SAFE_X + 30, 760, 3, np.array(YELLOW) / 255.0, ease_out(la2), s)
            draw_text(cv, img, p["title"], F_BLACK, 64, WHITE, SAFE_X + 52, 640, reveal=la2, tracking=1, shadow=10)
            if p.get("sub"):
                draw_text(cv, img, p["sub"], F_MED, 30, (225, 225, 225), SAFE_X + 55, 722, opacity=0.85 * ease(prog(t, 1.0, 1.5)), tracking=1)
        if p.get("hud"):
            hw = text_width(p["hud"], F_SEMI, 22, 5)
            draw_text(cv, img, p["hud"], F_SEMI, 22, TEAL, 1920 - SAFE_X - 30 - hw, 130, opacity=0.85 * ease(prog(t, 0.3, 0.9)), tracking=5, shadow=0)
        self.caption(img, t)
        return img


# --- karsilastirma karti + iki gercekci virus (canli / olu) ---
_CMP_render = Compare.render
def _compare_render(self, t, f):
    img = _CMP_render(self, t, f)
    p = self.p
    if p.get("viz") != "virus":
        return img
    cv = self.cv; s = cv.s
    px = max(48, int(250 * s) // 2 * 2)
    for side, (x, t0) in enumerate([(180, 0.2), (1010, 0.9)]):
        a = ease_out(prog(t, t0 + 0.2, t0 + 0.9))
        if a <= 0:
            continue
        cx, cy = x + 590, 380
        if side == 0:   # canli: doner, nabiz atar, cevresinde kopyalari belirir
            ang = t * 24
            col = (0.25, 0.62, 0.95)
            rgb, al = capsid_rgba(px, round(ang * 2) / 2, col)
            pulse = 1 + 0.03 * math.sin(t * 5)
            hal = np.zeros(img.shape[:2], np.float32)
            cv2.circle(hal, (int(cx * s), int(cy * s)), int(110 * pulse * s), 1.0, -1)
            img += cv2.GaussianBlur(hal, (0, 0), 30 * s)[..., None] * np.array(col, np.float32) * 0.28 * a
            for j in range(3):   # cogalma: kucuk kopyalar disari suzulur
                q = ((t - t0 - 1.0) * 0.45 + j / 3) % 1.0 if t > t0 + 1.0 else -1
                if q >= 0:
                    r2, a2 = capsid_rgba(max(16, px // 3 // 2 * 2), round(ang * 1.5) % 360, col)
                    ox = cx + math.cos(j * 2.1 + 0.6) * (70 + 110 * q); oy = cy + math.sin(j * 2.1 + 0.6) * (60 + 90 * q)
                    add_rgba(img, r2 * (a * (1 - q)), a2 * a * (1 - q), ox * s - r2.shape[1] / 2, oy * s - r2.shape[0] / 2)
            add_rgba(img, rgb * a, al * a, cx * s - px / 2, cy * s - px / 2)
            chip, cc = "ÇOĞALABİLİR", (90, 150, 245)
        else:           # olu: hareketsiz, gri, uzerinde capraz isaret
            col = (0.55, 0.53, 0.50)
            rgb, al = capsid_rgba(px, 40.0, col, rimcol=(0.8, 0.8, 0.8), spec_k=0.3)
            add_rgba(img, rgb * a, al * a, cx * s - px / 2, cy * s - px / 2)
            xk = ease(prog(t, t0 + 1.1, t0 + 1.5))
            if xk > 0:
                lay = np.zeros(img.shape[:2], np.float32)
                r = 92 * xk
                cv2.line(lay, (int((cx - r) * s), int((cy - r) * s)), (int((cx + r) * s), int((cy + r) * s)), 1.0, max(1, int(6 * s)), cv2.LINE_AA)
                cv2.line(lay, (int((cx + r) * s), int((cy - r) * s)), (int((cx - r) * s), int((cy + r) * s)), 1.0, max(1, int(6 * s)), cv2.LINE_AA)
                img[:] = img * (1 - lay[..., None] * 0.9) + lay[..., None] * (np.array(TEAL, np.float32) / 255.0) * 0.9
            chip, cc = "ÇOĞALAMAZ", TEAL
        ca = ease(prog(t, t0 + 1.2, t0 + 1.7))
        cw = text_width(chip, F_BOLD, 20, 4) + 30
        rrect(img, cx - cw / 2, 492, cx + cw / 2, 526, 8, (0.06, 0.05, 0.04), 0.85 * ca, s)
        draw_text(cv, img, chip, F_BOLD, 20, cc, cx - cw / 2 + 15, 497, opacity=ca, tracking=4, shadow=0, check_safe=False)
    return img
Compare.render = _compare_render


# ---------- gunes (NASA SDO gorseli, toplamali isik + parlama) ----------
_SUNT = {}
def sun_add(img, cv, t, cx, cy, diam, k=1.0, path="src/17_gunes_nasa.jpg", rot=0.5, bloom=0.7):
    if path not in _SUNT:
        im = imread(path).astype(np.float32) / 255.0
        _SUNT[path] = im
    tex = _SUNT[path]
    sc = diam / (tex.shape[1] * 0.83)
    lay = cv.place(tex, sc, cx, cy, angle=t * rot, border=cv2.BORDER_CONSTANT)
    img += lay * k
    if bloom > 0:
        sm = cv2.resize(lay, (max(8, lay.shape[1] // 8), max(8, lay.shape[0] // 8)), interpolation=cv2.INTER_AREA)
        b1 = cv2.GaussianBlur(sm, (0, 0), 3); b2 = cv2.GaussianBlur(sm, (0, 0), 14)
        b = cv2.resize(b1 * 0.6 + b2 * 1.4, (lay.shape[1], lay.shape[0]), interpolation=cv2.INTER_LINEAR)
        img += b * bloom * k * np.array([0.55, 0.85, 1.15], np.float32)


# ---------- 3B asi sisesi (cam, sivi, donen etiket, aluminyum kapak) ----------
_VLAB = {}
def _vial_label(Tw, Th):
    key = (Tw, Th)
    if key in _VLAB:
        return _VLAB[key]
    sc = 4
    im = Image.new("RGB", (Tw * sc, Th * sc), (236, 230, 214))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, Tw * sc, int(Th * sc * 0.16)], fill=(150, 34, 30))
    d.rectangle([0, int(Th * sc * 0.90), Tw * sc, Th * sc], fill=(150, 34, 30))
    fb = ImageFont.truetype(F_BOLD, int(Th * sc * 0.15)); fm = ImageFont.truetype(F_MED, int(Th * sc * 0.085)); fs = ImageFont.truetype(F_SEMI, int(Th * sc * 0.11))
    x0 = int(Tw * sc * 0.06)
    for k in range(2):  # etiket iki kez (silindir etrafinda)
        xo = x0 + k * Tw * sc // 2
        d.text((xo, int(Th * sc * 0.22)), "POLIOMYELITIS", font=fb, fill=(30, 28, 26))
        d.text((xo, int(Th * sc * 0.40)), "VACCINE", font=fb, fill=(30, 28, 26))
        d.text((xo, int(Th * sc * 0.60)), "Inactivated · Types 1, 2, 3", font=fm, fill=(60, 55, 50))
        d.text((xo, int(Th * sc * 0.73)), "1 cc · EXPERIMENTAL", font=fs, fill=(150, 34, 30))
    im = im.resize((Tw, Th), Image.LANCZOS)
    a = np.asarray(im, np.float32)[..., ::-1] / 255.0
    _VLAB[key] = a
    return a


_VIAL = {}
def vial_rgba(Hpx, phase, liquid=(0.55, 0.38, 0.92)):
    """Cam sise: on-arka cam, sivi (menisküs), silindirik etiket, aluminyum kapak, yansimalar. premult rgb + alfa."""
    key = (Hpx, round(phase % 1.0, 3))
    if key in _VIAL:
        return _VIAL[key]
    H = Hpx; W = int(H * 0.46) // 2 * 2 + 2
    R = W / 2 * 0.96
    f = (np.arange(H, dtype=np.float32) + 0.5) / H
    prof = np.where(f < 0.13, 0.80, np.where(f < 0.19, 0.58, np.where(f < 0.27, 0.58 + 0.42 * np.sin((f - 0.19) / 0.08 * math.pi / 2), 1.0)))
    prof = prof * np.where(f > 0.97, np.sqrt(np.clip(1 - ((f - 0.97) / 0.03) ** 2, 0.05, 1)), 1.0)
    prof = prof * np.where(f < 0.01, 0.0, 1.0)
    hw = (R * prof)[:, None]
    xx = np.arange(W, dtype=np.float32)[None, :] - W / 2 + 0.5
    u = xx / np.maximum(hw, 1e-3)
    edge_a = np.clip((1 - np.abs(u)) * hw / 1.2, 0, 1)
    nz = np.sqrt(np.clip(1 - u * u, 0, 1))
    F = np.repeat(f[:, None], W, 1)
    rgb = np.zeros((H, W, 3), np.float32); A = np.zeros((H, W), np.float32)

    def over_(col, al):
        nonlocal rgb, A
        al = np.clip(al, 0, 1)
        rgb = rgb * (1 - al[..., None]) + col * al[..., None]
        A = A * (1 - al) + al
    glass_zone = (F >= 0.13) * edge_a
    # arka cam duvari (soluk)
    over_(np.array([0.80, 0.86, 0.88], np.float32) * (0.5 + 0.3 * nz)[..., None], glass_zone * (0.06 + 0.25 * np.abs(u) ** 6))
    # sivi
    fill = 0.36
    ul = np.clip(u / 0.90, -1, 1)
    top = fill - 0.012 * ul ** 2 * 0 + 0.010 * (ul ** 2)
    liq = ((F > top) & (F < 0.972) & (np.abs(u) < 0.90)).astype(np.float32) * edge_a
    nzl = np.sqrt(np.clip(1 - ul * ul, 0, 1))
    lc = np.array(liquid, np.float32)
    liq_col = lc * (0.35 + 0.65 * nzl)[..., None] + lc * 0.25 * np.clip((F - 0.80) / 0.17, 0, 1)[..., None]
    over_(liq_col, liq * 0.80)
    men = np.exp(-((F - top) * H / 1.6) ** 2) * (np.abs(u) < 0.9) * edge_a
    rgb += men[..., None] * np.array([0.85, 0.85, 0.95], np.float32) * 0.6
    # etiket (silindir uzerinde doner)
    l0, l1 = 0.47, 0.86
    Tw, Th = int(2 * math.pi * R), max(8, int((l1 - l0) * H))
    lab = _vial_label(Tw, Th)
    theta = np.arcsin(np.clip(u, -1, 1))
    tx = ((phase + theta / (2 * math.pi)) % 1.0) * (Tw - 1)
    ty = np.clip((F - l0) / (l1 - l0), 0, 0.999) * (Th - 1)
    lab_s = cv2.remap(lab, tx.astype(np.float32), ty.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    lam = np.clip(0.50 + 0.55 * (-0.55 * u + 0.83 * nz), 0.15, 1.1)
    lmask = ((F > l0) & (F < l1) & (np.abs(u) < 0.985)).astype(np.float32) * edge_a
    over_(lab_s * lam[..., None], lmask)
    # on cam (fresnel kenarlar)
    over_(np.array([0.85, 0.90, 0.92], np.float32) * (0.6 + 0.4 * nz)[..., None], glass_zone * (0.05 + 0.55 * np.abs(u) ** 8))
    # kapak: aluminyum + lastik tipa
    capm = ((F < 0.13) & (F > 0.012)).astype(np.float32) * edge_a
    met = 0.30 + 0.45 * np.clip(-0.6 * u + 0.8 * nz, 0, 1) + 0.25 * np.exp(-((u + 0.45) / 0.10) ** 2)
    met = met * (1 - 0.35 * np.exp(-((F - 0.105) * H / 2.0) ** 2))   # kivrim cizgisi
    over_(np.array([0.78, 0.76, 0.74], np.float32) * met[..., None], capm)
    # parlama seritleri (on yuzey)
    gl = (F >= 0.15) * edge_a
    hi = 0.55 * np.exp(-((u + 0.60) / 0.09) ** 2) + 0.85 * np.exp(-((u - 0.78) / 0.025) ** 2)
    rgb += (hi * gl)[..., None] * np.array([1.0, 1.0, 1.0], np.float32)
    A = np.clip(A + hi * gl * 0.5, 0, 1)
    out = (rgb.astype(np.float32), A.astype(np.float32))
    if len(_VIAL) > 300:
        _VIAL.clear()
    _VIAL[key] = out
    return out


def lab_stage(cv, fx, t, warm=0.0):
    """Karanlik laboratuvar sahnesi: arka planda bokeh isiklar, parlak masa ufku."""
    s = cv.s
    img = navy_bg(cv, fx, t, glow=(0.10, 0.08, 0.05), center=(0.62, 0.40))
    rng = np.random.default_rng(17)
    lay = np.zeros(img.shape[:2], np.float32)
    for i in range(16):
        x = rng.uniform(100, 1820) + 10 * math.sin(t * 0.3 + i); y = rng.uniform(120, 560)
        cv2.circle(lay, (int(x * s), int(y * s)), int(rng.uniform(18, 46) * s), rng.uniform(0.3, 1.0), -1, cv2.LINE_AA)
    lay = cv2.GaussianBlur(lay, (0, 0), 9 * s)
    img += lay[..., None] * (np.array([0.55, 0.70, 0.85], np.float32) * (1 - warm) + np.array([0.35, 0.65, 1.0], np.float32) * warm) * 0.10
    yy = fx.yy / s
    tab = np.clip((yy - 760) / 320, 0, 1)
    img = img * (1 - (yy > 760)[..., None] * 0.35) + (tab * (1 - tab) * 0.10)[..., None] * np.array([0.8, 0.85, 0.9], np.float32)
    line = np.exp(-((yy - 760) / 2.5) ** 2) * 0.06
    img += line[..., None]
    return img


def put_vial(img, cv, cx, base_y, Hh, phase, blur=0.0, dim=1.0, refl=0.12, liquid=(0.55, 0.38, 0.92)):
    s = cv.s
    hp = max(16, int(Hh * s))
    rgb, a = vial_rgba(hp, phase, liquid)
    if blur > 0:
        rgb = cv2.GaussianBlur(rgb, (0, 0), blur * s); a = cv2.GaussianBlur(a, (0, 0), blur * s)
    x0 = cx * s - rgb.shape[1] / 2; y0 = base_y * s - rgb.shape[0]
    # temas golgesi + isik havuzu
    sh = np.zeros(img.shape[:2], np.float32)
    cv2.ellipse(sh, (int(cx * s), int(base_y * s)), (int(rgb.shape[1] * 0.62), max(1, int(rgb.shape[1] * 0.10))), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
    img *= (1 - cv2.GaussianBlur(sh, (0, 0), 6 * s)[..., None] * 0.6 * dim)
    if refl > 0:
        add_rgba(img, rgb[::-1] * refl * dim * np.linspace(1, 0, rgb.shape[0], dtype=np.float32)[:, None, None],
                 a[::-1] * refl * dim * np.linspace(1, 0, rgb.shape[0], dtype=np.float32)[:, None], x0, base_y * s)
    add_rgba(img, rgb * dim, a * dim, x0, y0)


def vial_scene(cv, fx, t, hero_x=1290, hero_h=640, second=True, push=True):
    img = lab_stage(cv, fx, t)
    s = cv.s
    if second:
        put_vial(img, cv, hero_x - 420, 735, hero_h * 0.62, 0.15 + t * 0.02, blur=5, dim=0.55, refl=0.10)
    put_vial(img, cv, hero_x + (10 * math.sin(t * 0.3) if push else 0), 790, hero_h * (lerp(0.96, 1.02, ease(min(t / 6, 1))) if push else 1), 0.62 + t * 0.035)
    # anahtar isik huzmesi
    beam = np.clip(1 - np.abs((fx.xx / cv.W) * 0.9 - (fx.yy / cv.H) * 0.35 - 0.42) * 2.6, 0, 1) ** 2
    img += beam[..., None] * np.array([0.05, 0.055, 0.06], np.float32)
    return img


# --- soru karti: bg3d = "vial" (gercekci asi sisesi, metin solda) ---
_QC2 = QuestionCard.render
def _qc_render2(self, t, f):
    p = self.p
    if p.get("bg3d") != "vial":
        return _QC2(self, t, f)
    cv, fx = self.cv, self.fx
    img = vial_scene(cv, fx, t, hero_x=1400, hero_h=700)
    img *= fx.left_dark * 0.5 + 0.5
    k = p.get("kicker", "PEKİ...")
    draw_text(cv, img, k, F_BOLD, 32, YELLOW, SAFE_X + 40, 330, reveal=prog(t, 0.05, 0.5), tracking=10)
    yy = 390
    for i, ln in enumerate(p["question"].split("\n")):
        draw_text(cv, img, ln, F_BLACK, 66, WHITE, SAFE_X + 36, yy, reveal=prog(t, 0.35 + i * 0.35, 0.95 + i * 0.35), tracking=1, shadow=14)
        yy += 84
    pa = 0.55 + 0.45 * math.sin(t * 4.5)
    draw_text(cv, img, "?", F_BLACK, 120, YELLOW, SAFE_X + 36, yy + 10, opacity=pa * ease(prog(t, 1.2, 1.6)), shadow=12)
    return img
QuestionCard.render = _qc_render2


# ---------- metal bozuk paralar (kabartma doku, fizik, yigin) ----------
_COIN = {}
def _coin_maps(face, S=192):
    key = (face, S)
    if key in _COIN:
        return _COIN[key]
    sc = 3
    big = S * sc
    im = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(im)
    c = big / 2; R = big * 0.48
    d.ellipse([c - R, c - R, c + R, c + R], fill=60)
    d.ellipse([c - R * 0.90, c - R * 0.90, c + R * 0.90, c + R * 0.90], fill=0)
    d.ellipse([c - R * 0.86, c - R * 0.86, c + R * 0.86, c + R * 0.86], fill=18)

    def arc_text(txt, rad, a0, a1, size, top=True):
        fnt = ImageFont.truetype(F_BOLD, int(size))
        n = len(txt)
        for i, ch in enumerate(txt):
            a = math.radians(lerp(a0, a1, (i + 0.5) / n))
            g = Image.new("L", (int(size * 1.6), int(size * 1.6)), 0)
            ImageDraw.Draw(g).text((int(size * 0.3), int(size * 0.1)), ch, font=fnt, fill=55)
            rot = -math.degrees(a) - 90 if top else -math.degrees(a) + 90
            g = g.rotate(rot, resample=Image.BICUBIC)
            x = c + math.cos(a) * rad - g.width / 2; y = c + math.sin(a) * rad - g.height / 2
            im.paste(Image.eval(g, lambda v: v), (int(x), int(y)), g)
    if face == 0:   # arka yuz: mesale + dallar
        arc_text("UNITED STATES OF AMERICA", R * 0.74, 200, 340, big * 0.065)
        arc_text("ONE DIME", R * 0.74, 120, 60, big * 0.075, top=False)
        d.rectangle([c - big * 0.022, c - big * 0.16, c + big * 0.022, c + big * 0.20], fill=55)
        d.polygon([(c - big * 0.05, c - big * 0.16), (c + big * 0.05, c - big * 0.16), (c, c - big * 0.30)], fill=60)
        d.ellipse([c - big * 0.05, c - big * 0.26, c + big * 0.05, c - big * 0.14], fill=60)
        for sg in (-1, 1):
            for k in range(6):
                yy = c + big * (0.15 - k * 0.06); xx = c + sg * big * (0.09 + k * 0.012)
                d.ellipse([xx - big * 0.035, yy - big * 0.015, xx + big * 0.035, yy + big * 0.015], fill=48)
    else:           # on yuz: genel profil + yazilar
        arc_text("LIBERTY", R * 0.74, 205, 285, big * 0.085)
        arc_text("1946", R * 0.74, 60, 20, big * 0.075, top=False)
        d.ellipse([c - big * 0.17, c - big * 0.20, c + big * 0.13, c + big * 0.12], fill=58)       # bas
        d.polygon([(c - big * 0.10, c + big * 0.05), (c + big * 0.08, c + big * 0.05), (c + big * 0.12, c + big * 0.27), (c - big * 0.16, c + big * 0.27)], fill=58)   # boyun/omuz
        d.ellipse([c + big * 0.10, c - big * 0.06, c + big * 0.17, c + big * 0.01], fill=58)      # burun
    h = np.asarray(im.resize((S, S), Image.LANCZOS), np.float32) / 60.0
    h = cv2.GaussianBlur(h, (0, 0), 0.8)
    gx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3) * 1.4; gy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3) * 1.4
    n = np.sqrt(gx * gx + gy * gy + 1)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    r = np.sqrt((xx - S / 2) ** 2 + (yy - S / 2) ** 2)
    a = np.clip((S * 0.48 - r) / 1.2, 0, 1).astype(np.float32)
    out = (-gx / n, -gy / n, 1 / n, h, a)
    _COIN[key] = out
    return out


def coin_face(face, Ll, Vl, S=128, tint=(0.70, 0.72, 0.74)):
    nx, ny, nz, h, a = _coin_maps(face, S)
    L = Ll / (np.linalg.norm(Ll) + 1e-9); V = Vl / (np.linalg.norm(Vl) + 1e-9)
    Hh = L + V; Hh /= (np.linalg.norm(Hh) + 1e-9)
    ndl = np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    ndh = np.clip(nx * Hh[0] + ny * Hh[1] + nz * Hh[2], 0, 1)
    col = np.array(tint, np.float32)
    shade = 0.10 + 0.55 * ndl + 0.20 * (0.6 + 0.4 * h.clip(0, 1))
    rgb = col * shade[..., None] + (ndh ** 14 * 0.55 + ndh ** 90 * 1.4)[..., None]
    return np.clip(rgb, 0, 2), a


_TABLE = {}
def wood_table():
    if "w" not in _TABLE:
        rng = np.random.default_rng(21)
        S = 1024
        n1 = cv2.resize(rng.normal(0, 1, (8, 256)).astype(np.float32), (S, S), interpolation=cv2.INTER_CUBIC)
        n2 = cv2.resize(rng.normal(0, 1, (64, 512)).astype(np.float32), (S, S), interpolation=cv2.INTER_CUBIC)
        yy = np.arange(S, dtype=np.float32)[:, None]
        grain = np.sin(yy * 0.09 + n1 * 2.2) * 0.5 + 0.5
        wood = 0.62 + 0.34 * grain + 0.08 * n2
        _TABLE["w"] = np.clip(wood[..., None] * np.array([0.085, 0.120, 0.170], np.float32), 0, 1)
    return _TABLE["w"]


class CoinStack:
    """Masaya dusen, donen, sekip yiginda duran metal paralar. t_land[i] kelime bagimsiz, kapali formul."""
    def __init__(self, n=130, center=(260, 700), seed=12, t0=0.6, t1=6.4, spread=(150, 95)):
        rng = np.random.default_rng(seed)
        self.n = n
        self.tl = t0 + (t1 - t0) * (np.arange(n) / n) ** 1.2 + rng.uniform(-0.04, 0.04, n)
        self.xl = center[0] + rng.normal(0, spread[0], n) * np.linspace(0.6, 1.0, n)
        self.zl = center[1] + rng.normal(0, spread[1], n) * np.linspace(0.6, 1.0, n)
        self.r, self.th = 30.0, 3.4
        hgt = np.zeros(n)
        for i in range(n):
            dd = np.hypot(self.xl[:i] - self.xl[i], self.zl[:i] - self.zl[i])
            hgt[i] = (dd < self.r * 1.5).sum() * self.th * 0.75
        self.yl = -hgt - self.th / 2
        self.ax = rng.normal(0, 1, (n, 3)); self.ax /= np.linalg.norm(self.ax, axis=1, keepdims=True)
        self.w = rng.uniform(9, 16, n)
        self.yaw = rng.uniform(0, 6.28, n)
        self.face = rng.integers(0, 2, n)
        self.x0 = self.xl + rng.normal(0, 60, n); self.z0 = self.zl + rng.normal(0, 60, n)
        self.y0 = -rng.uniform(800, 1100, n)
        self.tint = rng.choice(3, n)

    def state(self, i, t):
        tl = self.tl[i]; tf = 0.55
        if t < tl - tf:
            return None
        if t < tl:
            u = (t - (tl - tf)) / tf
            P = np.array([lerp(self.x0[i], self.xl[i], u), lerp(self.y0[i], self.yl[i], u * u), lerp(self.z0[i], self.zl[i], u)])
            R = _rot_axis(self.ax[i], self.w[i] * (t - tl))
            Rf = _rot_axis((1, 0, 0), -math.pi / 2) @ _rot_axis((0, 0, 1), self.yaw[i])
            return P, R @ Rf
        dt = t - tl
        P = np.array([self.xl[i], self.yl[i] - 16 * abs(math.sin(math.pi * dt / 0.13)) * math.exp(-dt * 11), self.zl[i]])
        wob = math.radians(22) * math.exp(-dt * 7) * math.cos(dt * 34)
        R = _rot_axis((1, 0, 0), -math.pi / 2 + wob) @ _rot_axis((0, 0, 1), self.yaw[i])
        R = _rot_axis((0, 1, 0), self.yaw[i] * 0.3) @ R
        return P, R

    def landed(self, t):
        return int((self.tl <= t).sum())

    def render(self, img, cam, t, s, Lw=np.array([-0.35, -1.0, -0.45]), size=128):
        Lw = Lw / np.linalg.norm(Lw)
        H, W = img.shape[:2]
        items = []
        for i in range(self.n):
            st = self.state(i, t)
            if st is None:
                continue
            P, R = st
            _, zc = cam.proj(P[None])
            items.append((zc[0], i, P, R))
        # golgeler: merkez isik yonunde masaya izdusurulur
        sh = np.zeros((H, W), np.float32)
        for _, i, P, R in items:
            hy = max(-P[1], 0.0)
            tt = P[1] / Lw[1]
            G = P - tt * Lw
            qq, _ = cam.proj(np.array([[G[0], 0, G[2]], [G[0] - self.r, 0, G[2]], [G[0] + self.r, 0, G[2]], [G[0], 0, G[2] - self.r], [G[0], 0, G[2] + self.r]]))
            rx = max(1.0, abs(qq[2, 0] - qq[1, 0]) * s / 2) * (1 + hy / 700); ry = max(1.0, abs(qq[4, 1] - qq[3, 1]) * s / 2) * (1 + hy / 700)
            op = 0.8 * math.exp(-hy / 420)
            cv2.ellipse(sh, (int(qq[0, 0] * s), int(qq[0, 1] * s)), (int(rx), int(ry)), 0, 0, 360, op, -1, cv2.LINE_AA)
        img *= (1 - cv2.GaussianBlur(sh, (0, 0), 3 * s)[..., None] * 0.65)
        items.sort(key=lambda o: -o[0])
        tints = [(0.70, 0.72, 0.74), (0.62, 0.66, 0.70), (0.74, 0.74, 0.72)]
        ang = np.linspace(0, 2 * math.pi, 28, endpoint=False)
        for zc, i, P, R in items:
            if zc < 30:
                continue
            nW = R @ np.array([0, 0, 1.0])
            V = cam.p - P
            front = float(nW @ V) > 0
            zf = self.th / 2 if front else -self.th / 2
            # kenar (kalinlik)
            ring = np.stack([np.cos(ang) * self.r, np.sin(ang) * self.r], 1)
            A3 = np.concatenate([np.c_[ring, np.full(28, zf)], np.c_[ring, np.full(28, -zf)]]) @ R.T + P
            q, _ = cam.proj(A3)
            hull = cv2.convexHull(np.float32(q * s))
            ec = np.array(tints[self.tint[i]], np.float32) * (0.35 + 0.25 * max(0.0, float((R @ np.array([1.0, 0, 0])) @ Lw)))
            cv2.fillConvexPoly(img, np.int32(hull), ec.tolist(), cv2.LINE_AA)
            # yuz
            Ll = R.T @ Lw; Vl = R.T @ (V / np.linalg.norm(V))
            face = int(self.face[i]) if front else 1 - int(self.face[i])
            if not front:
                Ll = Ll * np.array([1, 1, -1]); Vl = Vl * np.array([1, 1, -1])
            rgb, a = coin_face(face, Ll, Vl, size, tints[self.tint[i]])
            sx = 1 if front else -1
            C = np.array([[-self.r * sx, -self.r, zf], [self.r * sx, -self.r, zf], [self.r * sx, self.r, zf], [-self.r * sx, self.r, zf]]) @ R.T + P
            qc, _ = cam.proj(C)
            warp_quad(img, rgb, a, qc, s)


class CoinsReal(Scene):
    """1:22 - Milyonlarca bozuk para: masaya dusen gercekci metal onluklar, yigin buyur; metin solda."""
    def setup(self):
        self.stack = CoinStack(n=self.p.get("n", 130), center=(300, 760), t0=0.5, t1=min(self.d - 1.5, 8.5))

    def cam(self, t):
        u = ease(t / max(self.d, 1))
        return Cam3((lerp(-20, 50, u), lerp(-330, -300, u), lerp(150, 230, u)), yaw=lerp(-4, 0, u), pitch=lerp(30, 27, u), f=1250)

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s; W, H = cv.W, cv.H
        cam = self.cam(t)
        tab = wood_table()
        Ts = tab.shape[0]
        quad = np.array([[-1800, 0, -200], [1800, 0, -200], [1800, 0, 3200], [-1800, 0, 3200]], float)
        q, _ = cam.proj(quad)
        Mt = cv2.getPerspectiveTransform(np.float32([[0, 0], [Ts * 3, 0], [Ts * 3, Ts * 3.2], [0, Ts * 3.2]]), np.float32(q * s))
        img = cv2.warpPerspective(tab, Mt, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        yy = fx.yy / H
        far = np.clip(1 - yy * 1.6, 0, 1) ** 1.4
        img = img * (1 - far[..., None] * 0.9) + navy_bg(cv, fx, t, glow=(0.05, 0.04, 0.03), center=(0.6, 0.0)) * far[..., None] * 0.9
        hp, _ = cam.proj([[300, 0, 760]])
        d = np.sqrt((fx.xx - hp[0, 0] * s) ** 2 + ((fx.yy - hp[0, 1] * s) * 1.7) ** 2) / (560 * s)
        img *= (0.55 + 1.15 * np.exp(-d ** 2 * 1.2))[..., None]
        self.stack.render(img, cam, t, s, size=max(48, int(150 * s)))
        blur = cv2.GaussianBlur(img, (0, 0), 5 * s)
        dof = np.clip(far * 1.6, 0, 1)[..., None]
        img = img * (1 - dof) + blur * dof
        img *= fx.left_dark * 0.6 + 0.4
        a = ease_out(prog(t, 0.2, 0.8))
        draw_text(cv, img, p["kicker"], F_BOLD, 28, YELLOW, SAFE_X + 40, 330, opacity=a, tracking=8)
        yy_ = 380
        for ln in p["title"].split("\n"):
            draw_text(cv, img, ln, F_BLACK, 80, WHITE, SAFE_X + 36, yy_, reveal=prog(t, 0.25, 0.85), tracking=1, shadow=8)
            yy_ += 92
        draw_text(cv, img, p["sub"], F_MED, 30, (220, 220, 220), SAFE_X + 40, yy_ + 20, opacity=0.85 * ease(prog(t, 0.8, 1.3)), tracking=1)
        return img


# ---------- harita: gercekci arazi (yukseklik golgesi, iklim renkleri, okyanus, bulut) ----------
def _fbm(H, W, octaves, seed, base=64):
    rng = np.random.default_rng(seed)
    acc = np.zeros((H, W), np.float32)
    for o in range(octaves):
        cell = base / (2 ** o)
        n = rng.normal(0, 1, (int(H / cell) + 3, int(W / cell) + 3)).astype(np.float32)
        acc += cv2.resize(n, (W, H), interpolation=cv2.INTER_CUBIC) * (0.55 ** o)
    return acc


_TERR = {}
def map_terrain(land, key):
    if key in _TERR:
        return _TERR[key]
    H, W = land.shape
    xn = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    e = _fbm(H, W, 5, 5, 128)
    rock = np.exp(-((xn - 0.27) / 0.09) ** 2) * 1.5 + np.exp(-((xn - 0.09) / 0.035) ** 2) * 0.9
    appal = np.exp(-((xn - 0.80) / 0.035) ** 2) * 0.55
    elev = np.clip(0.20 + 0.16 * e + rock * (0.55 + 0.35 * e) + appal * (0.6 + 0.3 * e), 0, None)
    dry = np.clip(1.25 - xn * 1.9 + 0.18 * _fbm(H, W, 4, 9), 0, 1)
    green = np.array([0.20, 0.34, 0.24], np.float32); brown = np.array([0.30, 0.43, 0.55], np.float32)
    col = green * (1 - dry[..., None]) + brown * dry[..., None]
    col *= (0.82 + 0.22 * np.clip(elev, 0, 1.4))[..., None]
    snow = np.clip((elev - 1.15) / 0.25, 0, 1)
    col = col * (1 - snow[..., None]) + np.array([0.86, 0.88, 0.90], np.float32) * snow[..., None]
    gx = cv2.Sobel(elev, cv2.CV_32F, 1, 0, ksize=5); gy = cv2.Sobel(elev, cv2.CV_32F, 0, 1, ksize=5)
    shade = np.clip(0.86 + (gx * 0.55 + gy * 0.75) * 0.9, 0.45, 1.25)     # isik kuzeybatidan
    col *= shade[..., None]
    col *= (0.95 + 0.05 * _fbm(H, W, 3, 2, 32))[..., None]
    # okyanus + kiyi sigligi
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    ocean = np.array([0.30, 0.16, 0.05], np.float32) * (0.85 + 0.15 * (1 - yy))[..., None] * np.ones((H, W, 1), np.float32)
    coast = cv2.GaussianBlur(land, (0, 0), 14) - land * 0.6
    ocean += np.clip(coast, 0, 1)[..., None] * np.array([0.30, 0.25, 0.05], np.float32)
    bx = np.minimum(np.minimum(np.arange(W), W - 1 - np.arange(W))[None, :] / (W * 0.06), np.minimum(np.arange(H), H - 1 - np.arange(H))[:, None] / (H * 0.08))
    oa = np.clip(bx, 0, 1).astype(np.float32) ** 1.5
    clouds = cv2.GaussianBlur(np.clip((_fbm(H, W + 600, 4, 13, 160) - 1.05) * 1.1, 0, 1), (0, 0), 6).astype(np.float32)
    out = (col.astype(np.float32), ocean.astype(np.float32), oa, clouds)
    _TERR[key] = out
    return out


_MAP_render = MapScene.render
def _map_render(self, t, f):
    p = self.p
    if not p.get("terrain"):
        return _MAP_render(self, t, f)
    cv, fx = self.cv, self.fx
    s = cv.s
    land = self.land
    col, ocean, oa, clouds = map_terrain(land, id(self.land))
    Hm, Wm = land.shape
    n = len(self.ids)
    hl = np.zeros(n + 1, np.float32)
    for h_ in p.get("highlight", []):
        i = self.ids.index(h_["state"]) + 1
        hl[i] = ease_out(prog(t, h_["t"], h_["t"] + 0.7))
    Hh = hl[self.lab] * land
    yel = np.array(YELLOW, np.float32) / 255.0
    # bulut ve golgesi (yavas suzulur)
    off = int(t * 14 * self.MS) % 600
    cl = clouds[:, off:off + Wm]
    cls = clouds[:, (off + 18) % 600:(off + 18) % 600 + Wm] if (off + 18) % 600 + Wm <= clouds.shape[1] else cl
    mp = ocean * (1 - land[..., None]) + col * land[..., None]
    mp *= (1 - 0.25 * cls[..., None] * land[..., None])
    mp = mp * (1 - Hh[..., None] * 0.42) + Hh[..., None] * 0.42 * yel * 1.1
    mp = mp * (1 - self.bor[..., None] * 0.45) + self.bor[..., None] * 0.45 * np.array([0.78, 0.80, 0.82], np.float32)
    alpha = np.maximum(oa * 0.95, land)
    # vurgulanan eyalet: kalkan (yukselme) - yan duvar + ust yuz
    E = int(10 * self.MS * hl.max())
    if E > 0:
        wall = np.zeros_like(Hh)
        for k in range(1, E + 1):
            wall = np.maximum(wall, np.roll(Hh, -k, axis=0))
        top = np.roll(Hh, -E, axis=0); topc = np.roll(mp, -E, axis=0)
        wo = np.clip(wall - top, 0, 1)
        mp = mp * (1 - wo[..., None]) + wo[..., None] * yel * 0.40
        mp = mp * (1 - top[..., None]) + top[..., None] * topc * 1.12
        sh_ = cv2.GaussianBlur(np.roll(Hh, E // 2, axis=1), (0, 0), 6)
        mp *= (1 - 0.35 * np.clip(sh_ - top, 0, 1)[..., None])
    mp = mp * (1 - cl[..., None] * 0.55) + cl[..., None] * 0.55 * np.array([0.92, 0.92, 0.94], np.float32)
    # kamera (homografi; daha guclu perspektif)
    mx, my, z = self.camera(t)
    tilt = p.get("tilt", 1.0)
    if isinstance(tilt, list):
        tilt = lerp(tilt[0], tilt[1], ease(prog(t, tilt[2], tilt[3])))
    k_in = 0.26 * tilt
    src = np.float32([[0, 0], [Wm, 0], [Wm, Hm], [0, Hm]])
    dst = np.float32([[Wm * k_in, Hm * 0.40 * tilt], [Wm * (1 - k_in), Hm * 0.40 * tilt], [Wm, Hm], [0, Hm]])
    Ht = cv2.getPerspectiveTransform(src, dst)
    base_sc = (1560 / (959 * self.MS)) * z * s
    cxf, cyf = 960 * s, p.get("cy", 600) * s
    c = Ht @ np.array([mx * self.MS, my * self.MS, 1.0]); c = c[:2] / c[2]
    A = np.array([[base_sc, 0, cxf - c[0] * base_sc], [0, base_sc, cyf - c[1] * base_sc], [0, 0, 1]])
    Hfull = A @ Ht
    W, H_ = cv.W, cv.H
    kd = min(1.0, base_sc / 0.75)
    if kd < 1.0:
        mp_ = cv2.resize(mp, None, fx=kd, fy=kd, interpolation=cv2.INTER_AREA)
        al_ = cv2.resize(alpha, None, fx=kd, fy=kd, interpolation=cv2.INTER_AREA)
    else:
        mp_, al_ = mp, alpha
    Hk = Hfull @ np.diag([1 / kd, 1 / kd, 1.0])
    img = navy_bg(cv, fx, t, glow=(0.10, 0.06, 0.03), center=(0.5, 0.2))
    mw = cv2.warpPerspective(mp_, Hk, (W, H_), flags=cv2.INTER_LINEAR)
    aw = cv2.warpPerspective(al_, Hk, (W, H_), flags=cv2.INTER_LINEAR)[..., None]
    img = img * (1 - aw) + mw * aw
    # atmosfer: uzak kisim pus + hafif alan derinligi
    yy = fx.yy / H_
    haze = np.clip(1 - yy / 0.55, 0, 1) ** 1.5 * 0.55 * tilt
    img = img * (1 - haze[..., None]) + haze[..., None] * np.array([0.30, 0.22, 0.16], np.float32)
    bl = cv2.GaussianBlur(img, (0, 0), 3 * s)
    dk = np.clip(1 - yy / 0.40, 0, 1)[..., None]
    img = img * (1 - dk) + bl * dk

    def to_frame(pt):
        v = Hfull @ np.array([pt[0] * self.MS, pt[1] * self.MS, 1.0])
        return v[0] / v[2] / s, v[1] / v[2] / s
    # rotalar: yukselen yay + iz + parlayan bas
    for r_ in p.get("routes", []):
        a = to_frame(self.city_xy(r_["from"])); b = to_frame(self.city_xy(r_["to"]))
        g = ease(prog(t, r_["t0"], r_["t1"]))
        if g <= 0:
            continue
        dist = math.hypot(b[0] - a[0], b[1] - a[1])
        cc = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - dist * 0.45)
        N = 80; pts = []
        for i in range(int(N * g) + 1):
            u = i / N
            pts.append(((1 - u) ** 2 * a[0] + 2 * (1 - u) * u * cc[0] + u * u * b[0], (1 - u) ** 2 * a[1] + 2 * (1 - u) * u * cc[1] + u * u * b[1]))
        lay = np.zeros(img.shape[:2], np.float32); shd = np.zeros_like(lay)
        for i in range(len(pts) - 1):
            p0 = (int(pts[i][0] * s), int(pts[i][1] * s)); p1 = (int(pts[i + 1][0] * s), int(pts[i + 1][1] * s))
            cv2.line(lay, p0, p1, 1.0, max(1, int(4 * s)), cv2.LINE_AA)
            u = i / N
            gy = lerp(a[1], b[1], u)
            cv2.line(shd, (p0[0], int(gy * s)), (p1[0], int(lerp(a[1], b[1], (i + 1) / N) * s)), 1.0, max(1, int(5 * s)), cv2.LINE_AA)
        img *= (1 - cv2.GaussianBlur(shd, (0, 0), 4 * s)[..., None] * 0.35)
        head = np.zeros_like(lay)
        if g < 1:
            cv2.circle(head, (int(pts[-1][0] * s), int(pts[-1][1] * s)), max(2, int(10 * s)), 1.0, -1, cv2.LINE_AA)
        gl = cv2.GaussianBlur(lay + head * 2, (0, 0), 8 * s)
        img += (lay[..., None] * 0.9 + head[..., None] + gl[..., None] * 1.0) * yel
    # igneler: dikey isik sutunu + taban halkasi + etiket
    for pin in p.get("pins", []):
        x, y = to_frame(self.city_xy(pin["city"]))
        pt = pin["t"]
        if t < pt:
            continue
        u = ease_out(prog(t, pt, pt + 0.6))
        beam_h = 150 * u
        lay = np.zeros(img.shape[:2], np.float32)
        cv2.line(lay, (int(x * s), int(y * s)), (int(x * s), int((y - beam_h) * s)), 1.0, max(1, int(5 * s)), cv2.LINE_AA)
        grad = np.clip((fx.yy - (y - beam_h) * s) / max(beam_h * s, 1), 0, 1)
        img += (lay * grad)[..., None] * yel * 0.9 + cv2.GaussianBlur(lay * grad, (0, 0), 10 * s)[..., None] * yel * 0.9
        for k in range(2):
            ph = ((t - pt - 0.3 - k * 0.75) % 1.5) / 1.5 if t > pt + 0.3 + k * 0.75 else -1
            if ph >= 0:
                ring = np.zeros(img.shape[:2], np.float32)
                cv2.ellipse(ring, (int(x * s), int(y * s)), (int((14 + 60 * ph) * s), int((14 + 60 * ph) * 0.45 * s)), 0, 0, 360, 1.0, max(1, int(2.5 * s)), cv2.LINE_AA)
                img += ring[..., None] * yel * (1 - ph) * 0.9
        dot = np.zeros(img.shape[:2], np.float32)
        cv2.circle(dot, (int(x * s), int((y - beam_h) * s)), max(2, int(10 * s)), 1.0, -1, cv2.LINE_AA)
        img = img * (1 - dot[..., None]) + dot[..., None] * np.array([0.9, 0.95, 1.0], np.float32)
        img += cv2.GaussianBlur(dot, (0, 0), 12 * s)[..., None] * yel * 0.8
        la = ease_out(prog(t, pt + 0.35, pt + 0.9))
        if la > 0 and pin.get("label"):
            side = pin.get("side", "right")
            tw = max(text_width(pin["label"], F_BOLD, 34, 1), text_width(pin.get("sub", ""), F_MED, 24, 1)) + 52
            yb = y - beam_h - 50 + pin.get("dy", 0)
            bx0 = x + 30 if side == "right" else x - 30 - tw
            bx0 += lerp(-14 if side == "right" else 14, 0, la)
            hh = 98 if pin.get("sub") else 62
            rrect(img, bx0, yb, bx0 + tw, yb + hh, 10, (0.05, 0.035, 0.025), 0.82 * la, s)
            rrect(img, bx0, yb, bx0 + 6, yb + hh, 3, yel, la, s)
            draw_text(cv, img, pin["label"], F_BOLD, 34, WHITE, bx0 + 26, yb + 10, opacity=la, tracking=1, shadow=0, check_safe=False)
            if pin.get("sub"):
                draw_text(cv, img, pin["sub"], F_MED, 24, (215, 215, 215), bx0 + 27, yb + 56, opacity=la * 0.9, tracking=1, shadow=0, check_safe=False)
    if p.get("title"):
        draw_text(cv, img, p["title"], F_BOLD, 30, YELLOW, SAFE_X + 40, 150, reveal=prog(t, 0.1, 0.6), tracking=8)
    self.caption(img, t)
    return img
MapScene.render = _map_render


# ---------- alinti + gunes (3:48) ----------
_QT_render = QuoteCard.render
def _quote_render(self, t, f):
    p = self.p
    if not p.get("sun"):
        return _QT_render(self, t, f)
    cv, fx = self.cv, self.fx
    u = ease(t / self.d)
    img = cv.place(self.bg, cv.cover(self.bg) * lerp(1.05, 1.12, u), lerp(980, 940, u), 540) if self.bg is not None else navy_bg(cv, fx, t)
    st = p.get("sun_t", 2.5)
    k = ease_out(prog(t, st - 0.4, st + 1.4))
    if k > 0:
        img *= (1 - 0.35 * k)
        sun_add(img, cv, t, 1430, lerp(1300, 560, k), 760, k=0.95 * k, bloom=0.8)
    img *= fx.left_dark * 0.45 + 0.55
    lines = p["quote"].split("\n")
    size = p.get("size", 64); lh = size * 1.32
    y0 = 540 - lh * len(lines) / 2 - 20
    draw_text(cv, img, "“", F_BLACK, 220, YELLOW, 150, y0 - 120, opacity=ease_out(prog(t, 0.0, 0.5)), shadow=0)
    for i, ln in enumerate(lines):
        t0 = p.get("t0", 0.25) + i * p.get("step", 0.55)
        if p.get("line_ts"):
            t0 = p["line_ts"][i]
        col = YELLOW if i in p.get("highlight", []) else WHITE
        draw_text(cv, img, ln, F_SEMI if col == WHITE else F_BLACK, size, col, 270, y0 + i * lh, reveal=prog(t, t0, t0 + 0.6), shadow=10)
    who = p.get("who")
    if who:
        ta = p.get("who_t", 0.6 + len(lines) * 0.55)
        draw_text(cv, img, "— " + who, F_MED, 32, (225, 225, 225), 274, y0 + len(lines) * lh + 30, opacity=0.85 * ease(prog(t, ta, ta + 0.5)), tracking=2)
    self.caption(img, t)
    return img
QuoteCard.render = _quote_render


# ---------- kinetik metin: renksiz/derecelendirme yok + 'donus' ani ----------
_AK_render = ArchivalKinetic.render
def _ak_render(self, t, f):
    p = self.p
    cv, fx = self.cv, self.fx
    if not p.get("turn_t") and p.get("grade") != "none":
        return _AK_render(self, t, f)
    u = ease(t / self.d)
    img = cv.place(self.img, cv.cover(self.img) * lerp(1.16, 1.04, u), lerp(1000, 980, u), 540)
    if p.get("turn_t"):
        k = ease(prog(t, p["turn_t"], p["turn_t"] + 0.9))
        img = img * (1 - k) + grade(img, "bw_cool") * 0.55 * k
    img *= fx.left_dark
    y = 360
    for text, kind, t0 in p["lines"]:
        a = ease_out(prog(t, t0, t0 + 0.5))
        if kind == "big":
            sc = lerp(1.08, 1.0, a)
            draw_text(cv, img, text, F_BLACK, 96 * sc, YELLOW, SAFE_X + 40, y + lerp(20, 0, a), opacity=a, tracking=1, shadow=12)
            y += 124
        else:
            draw_text(cv, img, text, F_SEMI, 52, WHITE, SAFE_X + 44, y, reveal=prog(t, t0, t0 + 0.55), shadow=8)
            y += 80
    self.caption(img, t)
    return img
ArchivalKinetic.render = _ak_render


# ---------- kapanis: dogan gunes + ilke ----------
_KOD_render = KodCard.render
def _kod_render(self, t, f):
    p = self.p
    if not p.get("sun"):
        return _KOD_render(self, t, f)
    cv, fx = self.cv, self.fx
    s = cv.s
    img = navy_bg(cv, fx, t, glow=(0.05, 0.06, 0.10), center=(0.5, 0.9))
    rise = ease(prog(t, 0.0, self.d * 0.85))
    cy = lerp(1720, 1330, rise)
    # ufuk cizgisi ve sicak isik
    hz = np.exp(-((fx.yy / s - 1000) / 180) ** 2)
    img += hz[..., None] * np.array([0.10, 0.22, 0.40], np.float32) * (0.3 + 0.7 * rise)
    sun_add(img, cv, t, 960, cy, 1300, k=0.75 + 0.35 * rise, rot=0.3, bloom=0.9)
    ang = np.arctan2(fx.yy - cy * s, fx.xx - 960 * s)
    d = np.sqrt((fx.xx - 960 * s) ** 2 + (fx.yy - cy * s) ** 2) / (cv.W * 0.6)
    rays = (0.5 + 0.5 * np.cos(ang * 9 + t * 0.12)) ** 10 * np.exp(-d * 1.4)
    img += (rays * 0.10 * (0.4 + 0.6 * rise))[..., None] * np.array([0.55, 0.85, 1.1], np.float32)
    top = np.clip(1 - fx.yy / (cv.H * 0.7), 0, 1)[..., None]
    img *= (1 - 0.35 * top)
    dust(cv, img, t, n=40, seed=8, color=(0.5, 0.8, 1.0), amt=0.16)
    ba = ease_out(prog(t, 0.1, 0.6))
    badge = p.get("badge", "BEYİN KODU")
    bw = text_width(badge, F_BLACK, 34, 6) + 60
    x0 = 960 - bw / 2
    cv2.rectangle(img, (int(x0 * s), int(190 * s)), (int((x0 + bw) * s), int(252 * s)), np.array(YELLOW) / 255.0 * ba, -1)
    draw_text(cv, img, badge, F_BLACK, 34, (20, 20, 20), x0 + 30, 200, opacity=ba, tracking=6, shadow=0)
    yy = 310
    for i, ln in enumerate(p["lines"]):
        t0 = 0.7 + i * 0.9
        lw_ = text_width(ln, F_BOLD, 58, 0)
        draw_text(cv, img, ln, F_BOLD, 58, WHITE if i != p.get("hl", -1) else YELLOW, 960 - lw_ / 2, yy, reveal=prog(t, t0, t0 + 0.6), shadow=14)
        yy += 78
    q = p.get("question")
    if q:
        qa = ease_out(prog(t, p.get("q_t", 3.5), p.get("q_t", 3.5) + 0.6))
        qw = text_width(q, F_SEMI, 44, 1)
        draw_text(cv, img, q, F_SEMI, 44, YELLOW, 960 - qw / 2, yy + 50, opacity=qa, tracking=1, shadow=12)
        cta = "Yorumlara yaz."
        cw = text_width(cta, F_MED, 30, 2)
        draw_text(cv, img, cta, F_MED, 30, (230, 230, 230), 960 - cw / 2, yy + 120, opacity=0.85 * ease(prog(t, p.get("q_t", 3.5) + 1.2, p.get("q_t", 3.5) + 1.8)), tracking=2, shadow=8)
    return img
KodCard.render = _kod_render


# ---------- 3B belge (headline3d ile): prosedurel 'patent basvurusu' formu + uzun sahnede zaman esnetme ----------
def make_doc_tex(spec):
    Wp, Hp = 900, int(900 * 774 / 600)
    sc = 2
    im = Image.new("RGB", (Wp * sc, Hp * sc), (226, 232, 236))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(4)
    F = lambda fn, sz: ImageFont.truetype(fn, int(sz * sc))
    d.rectangle([40 * sc, 40 * sc, (Wp - 40) * sc, (Hp - 40) * sc], outline=(70, 70, 70), width=3 * sc)
    d.text((70 * sc, 64 * sc), spec.get("head", "PATENT BAŞVURUSU"), font=F(F_BLACK, 74), fill=(25, 25, 25))
    d.line([70 * sc, 160 * sc, (Wp - 70) * sc, 160 * sc], fill=(40, 40, 40), width=3 * sc)
    y = 200
    for lab, val in spec.get("fields", []):
        d.text((70 * sc, y * sc), lab, font=F(F_SEMI, 38), fill=(70, 70, 70))
        d.line([340 * sc, (y + 50) * sc, (Wp - 70) * sc, (y + 50) * sc], fill=(120, 120, 120), width=2 * sc)
        if val:
            d.text((350 * sc, (y - 2) * sc), val, font=F(F_BOLD, 38), fill=(20, 30, 70))
        y += 110
    for k in range(9):   # silik satirlar (form govdesi)
        yk = y + 30 + k * 46
        if yk > Hp - 120:
            break
        d.line([70 * sc, yk * sc, (Wp - 70 - rng.integers(0, 260)) * sc, yk * sc], fill=(180, 180, 180), width=2 * sc)
    im = im.resize((Wp, Hp), Image.LANCZOS)
    a = np.asarray(im, np.float32)[..., ::-1] / 255.0
    n = cv2.GaussianBlur(rng.normal(0, 1, (Hp, Wp)).astype(np.float32), (0, 0), 6)
    a = a * (0.94 + 0.05 * n[..., None]) * np.array([0.90, 0.97, 1.0], np.float32)   # eskimis kagit tonu
    return np.clip(a, 0, 1)


_HL_setup = Headline3D.setup
def _hl_setup(self):
    if self.p.get("doc"):
        tex = make_doc_tex(self.p["doc"])
        path = os.path.join(_HERE, "_doc_tmp_%d.png" % id(self))
        imwrite(path, (tex * 255).astype(np.uint8))
        self.spec = dict(self.spec); self.spec["visualAssets"] = [path]
        self.p = dict(self.p); self.p["grade"] = "none"
        _HL_setup(self)
        try:
            os.remove(path)
        except Exception:
            pass
        return
    _HL_setup(self)
Headline3D.setup = _hl_setup



# ---------- 3B (kabartma) rakam ----------
def text3d(cv, img, txt, font, size, x, y, color, depth=16, opacity=1.0, sweep=None, tracking=2):
    col = np.array(color, np.float32)
    for k in range(depth, 0, -1):
        sh = 0.22 + 0.25 * (1 - k / depth)
        c = tuple(int(v * sh) for v in color)
        draw_text(cv, img, txt, font, size, c, x + k * 0.9, y + k * 1.3, opacity=opacity, tracking=tracking, shadow=0, check_safe=False)
    draw_text(cv, img, txt, font, size, color, x, y, opacity=opacity, tracking=tracking, shadow=14)
    if sweep is not None and 0 < sweep < 1:
        rgba, pad = text_rgba(txt, font, size, (255, 255, 255), tracking, cv.s, 0)
        h, w = rgba.shape[:2]
        xs = np.arange(w, dtype=np.float32)[None, :] + np.arange(h, dtype=np.float32)[:, None] * 0.4
        band = np.exp(-((xs / w - lerp(-0.3, 1.3, sweep)) / 0.06) ** 2)
        lay = rgba.copy(); lay[..., :3] *= band[..., None] * 0.6; lay[..., 3] *= band * 0.6
        over(img, lay, x * cv.s - pad, y * cv.s - pad, opacity, False)


_MQ_setup = MoneyQ.setup
def _mq_setup(self):
    _MQ_setup(self)
    if self.p.get("coins_bg"):
        self.stack = CoinStack(n=110, center=(0, 900), t0=0.0, t1=max(self.d - 0.8, 2.0), seed=33, spread=(190, 70))
MoneyQ.setup = _mq_setup

_MQ_render = MoneyQ.render
def _mq_render(self, t, f):
    p = self.p
    if not (p.get("num3d") or p.get("coins_bg")):
        return _MQ_render(self, t, f)
    cv, fx = self.cv, self.fx
    s = cv.s
    u = ease(t / self.d)
    if p.get("coins_bg"):
        W, H = cv.W, cv.H
        cam = Cam3((lerp(-30, 30, u), -380, lerp(60, 120, u)), yaw=0, pitch=lerp(14, 13, u), f=1250)
        tab = wood_table(); Ts = tab.shape[0]
        q, _ = cam.proj(np.array([[-1800, 0, -200], [1800, 0, -200], [1800, 0, 3200], [-1800, 0, 3200]], float))
        Mt = cv2.getPerspectiveTransform(np.float32([[0, 0], [Ts * 3, 0], [Ts * 3, Ts * 3.2], [0, Ts * 3.2]]), np.float32(q * s))
        img = cv2.warpPerspective(tab, Mt, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        far = np.clip(1 - (fx.yy / H) * 1.6, 0, 1) ** 1.4
        img = img * (1 - far[..., None] * 0.9) + navy_bg(cv, fx, t) * far[..., None] * 0.9
        hp, _ = cam.proj([[0, 0, 900]])
        d = np.sqrt((fx.xx - hp[0, 0] * s) ** 2 + ((fx.yy - hp[0, 1] * s) * 1.7) ** 2) / (560 * s)
        img *= (0.55 + 1.15 * np.exp(-d ** 2 * 1.2))[..., None]
        self.stack.render(img, cam, t, s, size=max(48, int(150 * s)))
        img = cv2.GaussianBlur(img, (0, 0), 1.2 * s) * 0.80
    else:
        img = cv.place(self.bg, cv.cover(self.bg) * lerp(1.04, 1.1, u), 960, 540) if self.bg is not None else navy_bg(cv, fx, t)
    g = 1.0 if p.get("nocount") else ease_out(prog(t, 0.2, 2.0))
    v = int(p["value"] * g)
    num = "$" + f"{v:,}".replace(",", ".")
    nw = text_width(num, F_BLACK, 150, 2)
    text3d(cv, img, num, F_BLACK, 150, 960 - nw / 2, 380, YELLOW, depth=18, opacity=ease_out(prog(t, 0.1, 0.5)), sweep=prog(t, 2.0, 3.0))
    lab = p.get("label", "")
    lw_ = text_width(lab, F_MED, 30, 4)
    draw_text(cv, img, lab, F_MED, 30, (230, 230, 230), 960 - lw_ / 2, 600, opacity=0.85 * ease(prog(t, 0.8, 1.3)), tracking=4)
    if p.get("strike"):
        st = p.get("strike_t", 2.2)
        sa = ease(prog(t, st, st + 0.5))
        x0, x1 = 960 - nw / 2 - 20, 960 - nw / 2 - 20 + (nw + 40) * sa
        lay = np.zeros(img.shape[:2], np.float32)
        if sa > 0.01:
            cv2.line(lay, (int(x0 * s), int(490 * s)), (int(x1 * s), int(455 * s)), 1.0, max(2, int(11 * s)), cv2.LINE_AA)
        img[:] = img * (1 - lay[..., None]) + lay[..., None] * np.array((0.22, 0.22, 0.92), np.float32)
        img += cv2.GaussianBlur(lay, (0, 0), 8 * s)[..., None] * np.array((0.1, 0.1, 0.6), np.float32)
        q = p.get("question", "")
        qw = text_width(q, F_BOLD, 44, 2)
        draw_text(cv, img, q, F_BOLD, 44, WHITE, 960 - qw / 2, 680, opacity=ease_out(prog(t, st + 0.4, st + 0.9)), tracking=2, shadow=8)
    self.caption(img, t)
    return img
MoneyQ.render = _mq_render


# ---------- Cutter faciasi: 40.000 -> 200 -> 10 oran yakinlasmasi ----------
class CutterScale(Scene):
    def setup(self):
        rng = np.random.default_rng(55)
        n = 200
        gx, gz = np.meshgrid(np.arange(n), np.arange(n))
        self.X = (gx.ravel() - n / 2) * 11.0 + rng.uniform(-2, 2, n * n)
        self.Z = gz.ravel() * 11.0 + rng.uniform(-2, 2, n * n) + 300
        c = np.argmin((self.X - 260) ** 2 + (self.Z - 1300) ** 2)
        d = (self.X - self.X[c]) ** 2 + (self.Z - self.Z[c]) ** 2
        self.red = np.argsort(d)[:200]
        self.dead = self.red[np.argsort(rng.uniform(0, 1, 200))[:10]]
        self.cx, self.cz = self.X[c], self.Z[c]

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s; W, H = cv.W, cv.H
        t1, t2, t3 = p.get("w1_t", 0.8), p.get("w2_t", 3.0), p.get("w3_t", 5.0)
        z2 = ease(prog(t, t2 - 0.2, t2 + 1.6)); z3 = ease(prog(t, t3 - 0.2, t3 + 1.4))
        far = np.array([0, -1500, -700.0]); mid = np.array([self.cx - 60, -520, self.cz - 760]); near = np.array([self.cx - 20, -260, self.cz - 380])
        pos = far * (1 - z2) + mid * z2
        pos = pos * (1 - z3) + near * z3
        pitch = lerp(lerp(52, 34, z2), 30, z3)
        cam = Cam3(pos, yaw=lerp(0, 4, z2), pitch=pitch, f=1150)
        img = navy_bg(cv, fx, t, glow=(0.04, 0.05, 0.10), center=(0.55, 0.5))
        P = np.stack([self.X, np.zeros_like(self.X), self.Z], 1)
        q, z = cam.proj(P)
        g1 = ease(prog(t, 0.2, t1 + 0.8))
        vis = (z > 30) & (q[:, 0] > -20) & (q[:, 0] < 1940) & (q[:, 1] > -20) & (q[:, 1] < 1100)
        order = np.random.default_rng(8).permutation(len(self.X))
        appear = np.zeros(len(self.X), bool); appear[order[:int(len(order) * g1)]] = True
        sel = vis & appear
        xi = np.clip((q[sel, 0] * s).astype(int), 0, W - 1); yi = np.clip((q[sel, 1] * s).astype(int), 0, H - 1)
        sz = np.clip(cam.f * 3.2 / z[sel] * s, 0.6, 6)
        buf = np.zeros((H, W), np.float32)
        np.add.at(buf, (yi, xi), np.clip(sz, 0, 1.6) * np.clip(1.6 - z[sel] / 5000, 0.25, 1.0))
        k = max(1, int(round(float(np.median(sz)) if len(sz) else 1)))
        buf = cv2.dilate(buf, np.ones((k, k), np.uint8)) if k > 1 else buf
        buf = cv2.GaussianBlur(buf, (0, 0), 0.7 * s + 0.3)
        yel = np.array(YELLOW, np.float32) / 255.0
        img += np.clip(buf, 0, 1.0)[..., None] * yel * 0.75
        img += cv2.GaussianBlur(buf, (0, 0), 6 * s)[..., None] * yel * 0.25
        # 200 felc: kirmizi sutunlar yukselir
        red = np.array((0.20, 0.22, 0.92), np.float32)
        g2 = ease_out(prog(t, t2, t2 + 1.0))
        if g2 > 0:
            items = []
            for i in self.red:
                _, zz = cam.proj([[self.X[i], 0, self.Z[i]]])
                items.append((zz[0], i))
            items.sort(key=lambda o: -o[0])
            for zz, i in items:
                if zz < 30:
                    continue
                hgt = 26 * g2 + (70 * ease_out(prog(t, t3, t3 + 1.0)) if i in self.dead else 0)
                fr, top, rt, lf, _ = cuboid_faces(cam, self.X[i], self.Z[i], 8, 8, 0, -hgt)
                c = red * (1.25 if i in self.dead and t > t3 else 1.0)
                for poly, kk in ((rt, 0.55), (fr, 0.95), (top, 1.4)):
                    cv2.fillConvexPoly(img, np.int32(poly * s), np.clip(c * kk, 0, 1.2).tolist(), cv2.LINE_AA)
            # kume halesi
            hq, _ = cam.proj([[self.cx, 0, self.cz]])
            hal = np.zeros(img.shape[:2], np.float32)
            cv2.circle(hal, (int(hq[0, 0] * s), int(hq[0, 1] * s)), int(cam.f * 110 / max(cam.proj([[self.cx, 0, self.cz]])[1][0], 1) * s), 1.0, -1)
            img += cv2.GaussianBlur(hal, (0, 0), 30 * s)[..., None] * red * 0.25 * g2
        # olumler: beyaz-kirmizi parlayan isaret
        g3 = ease_out(prog(t, t3, t3 + 0.8))
        if g3 > 0:
            lay = np.zeros(img.shape[:2], np.float32)
            for i in self.dead:
                qq, zz = cam.proj([[self.X[i], -96 * g3, self.Z[i]]])
                if zz[0] > 30:
                    cv2.circle(lay, (int(qq[0, 0] * s), int(qq[0, 1] * s)), max(2, int(cam.f * 7 / zz[0] * s)), 1.0, -1, cv2.LINE_AA)
            img += (lay[..., None] * np.array((0.8, 0.85, 1.0), np.float32) + cv2.GaussianBlur(lay, (0, 0), 10 * s)[..., None] * red) * g3
        # sayaclar (sol ust): sirayla
        k_ = p.get("kicker", "")
        draw_text(cv, img, k_, F_BOLD, 28, YELLOW, SAFE_X + 40, 120, reveal=prog(t, 0.05, 0.6), tracking=8)
        rows = [(40000, "VAKA", YELLOW, t1), (200, "FELÇ", (60, 60, 235), t2), (10, "ÖLÜM", (60, 60, 235), t3)]
        yy = 170
        for val, lab, colr, tt0 in rows:
            a = ease_out(prog(t, tt0, tt0 + 0.5))
            if a <= 0:
                yy += 118; continue
            vv = int(round(val * ease_out(prog(t, tt0, tt0 + 1.0))))
            num = f"{vv:,}".replace(",", ".")
            text3d(cv, img, num, F_BLACK, 92, SAFE_X + 40, yy, colr, depth=10, opacity=a)
            nw = text_width(num, F_BLACK, 92, 2)
            draw_text(cv, img, lab, F_BOLD, 34, WHITE, SAFE_X + 70 + nw, yy + 42, opacity=a, tracking=5)
            yy += 118
        frac = p.get("note")
        if frac:
            draw_text(cv, img, frac, F_MED, 22, (190, 190, 190), SAFE_X + 42, 1080 - SAFE_Y - 40, opacity=0.7 * ease(prog(t, 1.5, 2.0)), tracking=1)
        return img


# ---------- gercekci 3B sutun grafik: cam/akrilik sutunlar, parlak zemin yansimasi, dusus etiketleri ----------
class Bars3DReal(Scene):
    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s; W, H = cv.W, cv.H
        img = navy_bg(cv, fx, t, glow=(0.08, 0.06, 0.03))
        u = ease(t / self.d)
        cam = Cam3((lerp(-620, -380, u), -560, -900), yaw=lerp(13, 8, u), pitch=lerp(15, 12, u), f=1100)
        floorY = 300
        # parlak zemin: isik havuzu + uzaklasan izgara
        fq, _ = cam.proj(np.array([[-1600, floorY, 700], [1600, floorY, 700], [1600, floorY, 3400], [-1600, floorY, 3400]], float))
        fm = np.zeros((H, W), np.float32)
        cv2.fillConvexPoly(fm, np.int32(fq * s), 1.0, cv2.LINE_AA)
        img = img * (1 - fm[..., None] * 0.35) + fm[..., None] * np.array([0.035, 0.03, 0.03], np.float32)
        for gx in np.linspace(-1500, 1500, 16):
            a, _ = cam.proj([[gx, floorY, 700], [gx, floorY, 3400]])
            cv2.line(img, tuple((a[0] * s).astype(int)), tuple((a[1] * s).astype(int)), (0.13, 0.11, 0.10), max(1, int(1.2 * s)), cv2.LINE_AA)
        for gz in np.linspace(700, 3400, 12):
            a, _ = cam.proj([[-1600, floorY, gz], [1600, floorY, gz]])
            cv2.line(img, tuple((a[0] * s).astype(int)), tuple((a[1] * s).astype(int)), (0.13, 0.11, 0.10), max(1, int(1.2 * s)), cv2.LINE_AA)
        bars = p["bars"]; vmax = max(b[1] for b in bars)
        n = len(bars)
        xs = [(i - (n - 1) / 2) * 560 for i in range(n)]
        cols = [np.array(YELLOW, np.float32) / 255.0] + [np.array(TEAL, np.float32) / 255.0] * (n - 1)
        info = []; refl = np.zeros_like(img); rmask = np.zeros((H, W), np.float32)
        for i in sorted(range(n), key=lambda i: -abs(xs[i] - cam.p[0])):
            lab, val, _ = bars[i]
            t0 = 0.5 + i * p.get("step", 0.9)
            g = ease_out(prog(t, t0, t0 + 1.3))
            hgt = max(760 * (val / vmax) * g, 10 * g)
            if g <= 0:
                info.append((i, None, lab, val, g)); continue
            c = cols[i]
            for mirror in (True, False):
                y0, y1 = (floorY, floorY + hgt) if mirror else (floorY, floorY - hgt)
                fr, top, rt, lf, P = cuboid_faces(cam, xs[i], 1600, 340, 340, y0, y1)
                side = rt if cam.p[0] < xs[i] else lf
                tgt = refl if mirror else img
                for poly, k in ((side, 0.50), (fr, 0.92), (top, 1.30)):
                    cv2.fillConvexPoly(tgt, np.int32(poly * s), np.clip(c * k, 0, 1.3).tolist(), cv2.LINE_AA)
                if mirror:
                    for poly in (side, fr):
                        cv2.fillConvexPoly(rmask, np.int32(poly * s), 1.0, cv2.LINE_AA)
                    continue
                # cam hissi: dikey parlama, kenar isiklari, ic parilti
                m = np.zeros((H, W), np.float32)
                cv2.fillConvexPoly(m, np.int32(fr * s), 1.0, cv2.LINE_AA)
                yy0, yy1 = fr[:, 1].min() * s, fr[:, 1].max() * s
                grad = np.clip(1 - (fx.yy - yy0) / max(yy1 - yy0, 1), 0, 1)
                xx0, xx1 = fr[:, 0].min() * s, fr[:, 0].max() * s
                streak = np.exp(-(((fx.xx - xx0) / max(xx1 - xx0, 1) - 0.22) / 0.06) ** 2)
                img += (m * (grad * 0.22 + streak * 0.25))[..., None]
                el = np.zeros((H, W), np.float32)
                cv2.polylines(el, [np.int32(fr * s), np.int32(top * s)], True, 1.0, max(1, int(2 * s)), cv2.LINE_AA)
                img += (el * 0.35 + cv2.GaussianBlur(el, (0, 0), 4 * s) * 0.4)[..., None] * c
                pool = np.zeros((H, W), np.float32)
                q, _ = cam.proj([[xs[i], floorY, 1600]])
                cv2.ellipse(pool, (int(q[0, 0] * s), int(q[0, 1] * s)), (int(300 * s), int(70 * s)), 0, 0, 360, 1.0, -1)
                img += cv2.GaussianBlur(pool, (0, 0), 26 * s)[..., None] * c * 0.20 * g
                info.append((i, top, lab, val, g))
        rk = cv2.GaussianBlur(rmask, (0, 0), 3 * s) * fm
        fade = np.clip(1 - (fx.yy - fq[:, 1].min() * s) / (H * 0.6), 0, 1) * 0.0 + 1.0
        img = img * (1 - rk[..., None] * 0.20) + cv2.GaussianBlur(refl, (0, 0), 3 * s) * 0.20 * fm[..., None] * fade[..., None]
        # degerler + dusus etiketleri
        tops = {}
        for i, top, lab, val, g in info:
            q, _ = cam.proj([[xs[i], floorY, 1450]])
            lw_ = text_width(lab, F_BOLD, 38, 3)
            draw_text(cv, img, lab, F_BOLD, 38, (235, 235, 235), q[0, 0] - lw_ / 2, q[0, 1] + 24, tracking=3, opacity=ease(prog(t, 0.2, 0.7)), check_safe=False)
            if top is None:
                continue
            tops[i] = top.mean(0)
            cur = int(round(val * g))
            txt = f"{cur:,}".replace(",", ".")
            tw = text_width(txt, F_BLACK, 66, 1)
            tc = top.mean(0)
            draw_text(cv, img, txt, F_BLACK, 66, WHITE, tc[0] - tw / 2, tc[1] - 100, tracking=1, shadow=10, check_safe=False, opacity=ease(prog(t, 0.6 + i * p.get("step", 0.9), 0.9 + i * p.get("step", 0.9))))
        for i in range(1, n):
            if i in tops and (i - 1) in tops:
                g = ease_out(prog(t, 0.5 + i * p.get("step", 0.9) + 1.1, 0.5 + i * p.get("step", 0.9) + 1.7))
                if g <= 0:
                    continue
                v0, v1 = bars[i - 1][1], bars[i][1]
                pct = f"−%{round(100 * (1 - v1 / v0))}"
                a_, b_ = tops[i - 1], tops[i]
                mx_, my_ = b_[0], b_[1] - 118
                lay = np.zeros((H, W), np.float32)
                pts = [(int(lerp(a_[0] + 70, b_[0] - 90, k) * s), int((lerp(a_[1] - 40, b_[1] - 150, k) - 60 * math.sin(math.pi * k)) * s)) for k in np.linspace(0, g, 30)]
                for j in range(len(pts) - 1):
                    cv2.line(lay, pts[j], pts[j + 1], 1.0, max(1, int(3 * s)), cv2.LINE_AA)
                img += lay[..., None] * np.array((0.45, 0.45, 0.95), np.float32)
                pw = text_width(pct, F_BLACK, 48, 1)
                rrect(img, mx_ - pw / 2 - 18, my_ - 66, mx_ + pw / 2 + 18, my_ - 4, 10, (0.08, 0.06, 0.20), 0.85 * g, s)
                draw_text(cv, img, pct, F_BLACK, 48, (120, 120, 255), mx_ - pw / 2, my_ - 62, opacity=g, tracking=1, shadow=0, check_safe=False)
        draw_text(cv, img, p.get("title", ""), F_BOLD, 40, WHITE, SAFE_X + 40, 80, reveal=prog(t, 0, 0.6), tracking=3)
        if p.get("sub"):
            draw_text(cv, img, p["sub"], F_MED, 26, (200, 200, 200), SAFE_X + 42, 134, opacity=0.8 * ease(prog(t, 0.3, 0.8)), tracking=2)
        if p.get("note"):
            draw_text(cv, img, p["note"], F_MED, 22, (190, 190, 190), SAFE_X + 42, 1080 - SAFE_Y - 40, opacity=0.7 * ease(prog(t, 2.0, 2.5)), tracking=1)
        return img


# ---------- gercekci 3B zaman cizelgesi: baski fotograflar, golge, yansima, alan derinligi ----------
class Timeline3DReal(Timeline3D):
    def setup(self):
        super().setup()
        self.blur = [None if c is None else (cv2.GaussianBlur(c[0], (0, 0), 5), cv2.GaussianBlur(c[1], (0, 0), 5)) for c in self.cards]

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s; W, H = cv.W, cv.H
        img = navy_bg(cv, fx, t, glow=(0.08, 0.06, 0.04), center=(0.5, 0.3))
        items = p["items"]; n = len(items)
        act = p.get("active", n - 1); frm = p.get("from", max(act - 1, 0))
        sp = 760
        X = [i * sp for i in range(n)]
        g = ease(prog(t, 0.3, min(self.d - 0.4, 2.6)))
        camx = lerp(X[frm], X[act], g)
        cam = Cam3((camx - 160, -380, -1350), yaw=-26, pitch=12, f=1050)
        yel = np.array(YELLOW, np.float32) / 255.0
        floorY = 220
        fq, _ = cam.proj(np.array([[X[0] - 2000, floorY, -400], [X[-1] + 2000, floorY, -400], [X[-1] + 2000, floorY, 3000], [X[0] - 2000, floorY, 3000]], float))
        fm = np.zeros((H, W), np.float32)
        cv2.fillConvexPoly(fm, np.int32(fq * s), 1.0, cv2.LINE_AA)
        img = img * (1 - fm[..., None] * 0.4) + fm[..., None] * np.array([0.03, 0.028, 0.026], np.float32)
        ap, _ = cam.proj([[X[act], floorY, 600]])
        d = np.sqrt((fx.xx - ap[0, 0] * s) ** 2 + ((fx.yy - ap[0, 1] * s) * 2.2) ** 2) / (600 * s)
        img += (np.exp(-d ** 2 * 2) * fm * 0.10 * g)[..., None] * np.array([0.6, 0.8, 1.0], np.float32)
        L, _ = cam.proj([[-sp, floorY, 600], [X[-1] + sp, floorY, 600]])
        cv2.line(img, tuple((L[0] * s).astype(int)), tuple((L[1] * s).astype(int)), (0.30, 0.30, 0.30), max(1, int(3 * s)), cv2.LINE_AA)
        P2, _ = cam.proj([[X[0], floorY, 600], [camx, floorY, 600]])
        lay = np.zeros((H, W), np.float32)
        cv2.line(lay, tuple((P2[0] * s).astype(int)), tuple((P2[1] * s).astype(int)), 1.0, max(1, int(5 * s)), cv2.LINE_AA)
        img += (lay[..., None] + cv2.GaussianBlur(lay, (0, 0), 6 * s)[..., None] * 0.8) * yel
        order = sorted(range(n), key=lambda i: -cam.proj([[X[i], 0, 600]])[1][0])
        for i in order:
            isact = (i == act)
            reached = X[i] <= camx + 1
            yr, lab = items[i][0], items[i][1]
            card = self.cards[i]
            sharp = abs(X[i] - camx) < sp * 0.6
            if card is not None:
                ci, ca = card if sharp else self.blur[i]
                h, w = ci.shape[:2]
                cw, chh = 420 * w / max(w, h) * 1.3, 420 * h / max(w, h) * 1.3
                bot = floorY - 90
                quad = [[X[i] - cw / 2, bot - chh, 600], [X[i] + cw / 2, bot - chh, 600], [X[i] + cw / 2, bot, 600], [X[i] - cw / 2, bot, 600]]
                # golge (masa uzerine egik izdusum)
                sq = [[X[i] - cw / 2 + 60, floorY, 640], [X[i] + cw / 2 + 60, floorY, 640], [X[i] + cw / 2 + 140, floorY, 900], [X[i] - cw / 2 + 140, floorY, 900]]
                qs, _ = cam.proj(sq)
                sh = np.zeros((H, W), np.float32)
                cv2.fillConvexPoly(sh, np.int32(qs * s), 1.0, cv2.LINE_AA)
                img *= (1 - cv2.GaussianBlur(sh, (0, 0), 16 * s)[..., None] * 0.45)
                # yansima
                rq = [[x_, 2 * floorY - y_, z_] for x_, y_, z_ in quad]
                qr, _ = cam.proj(rq)
                dim = 1.0 if isact and g > 0.85 else (0.62 if reached else 0.38)
                rl = np.zeros_like(img)
                warp_quad(rl, ci * dim, ca, qr, s)
                img += cv2.GaussianBlur(rl, (0, 0), 3 * s) * 0.14 * fm[..., None]
                q, _ = cam.proj(quad)
                warp_quad(img, ci * dim, ca, q, s)
                if isact and g > 0.85:
                    fl = np.zeros((H, W), np.float32)
                    cv2.polylines(fl, [np.int32(q * s)], True, 1.0, max(1, int(4 * s)), cv2.LINE_AA)
                    img += (fl + cv2.GaussianBlur(fl, (0, 0), 10 * s) * 1.6)[..., None] * yel * ease(prog(t, 2.2, 2.8))
            dd, _ = cam.proj([[X[i], floorY, 600]])
            r = (15 if isact else 9)
            dot = np.zeros((H, W), np.float32)
            cv2.circle(dot, (int(dd[0, 0] * s), int(dd[0, 1] * s)), max(2, int(r * s)), 1.0, -1, cv2.LINE_AA)
            cc = yel if reached else np.array((0.5, 0.5, 0.5), np.float32)
            img = img * (1 - dot[..., None]) + dot[..., None] * cc
            if reached:
                img += cv2.GaussianBlur(dot, (0, 0), 10 * s)[..., None] * yel * 0.8
            ys = 64 if isact else 40
            yw = text_width(yr, F_BLACK, ys, 1)
            draw_text(cv, img, yr, F_BLACK, ys, YELLOW if (isact or reached) else (190, 190, 190), dd[0, 0] - yw / 2, dd[0, 1] + 26, tracking=1, shadow=8, check_safe=False, opacity=0.95)
            lw_ = text_width(lab, F_SEMI, 26, 1)
            draw_text(cv, img, lab, F_SEMI, 26, WHITE, dd[0, 0] - lw_ / 2, dd[0, 1] + 30 + ys, opacity=0.9 if (isact or reached) else 0.5, tracking=1, check_safe=False)
        dust(cv, img, t, n=40, seed=12, amt=0.12)
        if p.get("title"):
            draw_text(cv, img, p["title"], F_BOLD, 30, YELLOW, SAFE_X + 40, 120, reveal=prog(t, 0, 0.5), tracking=8)
        return img


# ---------- dunya kuresi (NASA Blue Marble) + isaretler ----------
class GlobeScene(Scene):
    def setup(self):
        self.tex = imread(self.spec["visualAssets"][0]).astype(np.float32) / 255.0
        self.ocean = (self.tex[..., 0] > self.tex[..., 2] * 1.05).astype(np.float32)
        self.ocean = cv2.GaussianBlur(self.ocean, (0, 0), 2)

    def render(self, t, f):
        cv, fx, p = self.cv, self.fx, self.p
        s = cv.s; W, H = cv.W, cv.H
        img = navy_bg(cv, fx, t, glow=(0.10, 0.05, 0.02), center=(0.66, 0.5))
        rng = np.random.default_rng(2)
        stars = np.zeros((H, W), np.float32)
        for _ in range(220):
            stars[int(rng.uniform(0, H)), int(rng.uniform(0, W))] = rng.uniform(0.2, 1.0)
        img += cv2.GaussianBlur(stars, (0, 0), 0.6)[..., None] * 0.5
        cx, cy, Rr = p.get("cx", 1290), p.get("cy", 560), p.get("r", 420) * lerp(0.96, 1.0, ease(t / self.d))
        lon0 = math.radians(p.get("lon0", 40) + p.get("spin", 6) * t); lat0 = math.radians(p.get("lat0", 18))
        Rp = int(Rr * s)
        x0, y0 = int(cx * s) - Rp, int(cy * s) - Rp
        yy, xx = np.mgrid[0:2 * Rp, 0:2 * Rp].astype(np.float32)
        X = (xx - Rp + 0.5) / Rp; Y = -(yy - Rp + 0.5) / Rp
        rho = np.sqrt(X * X + Y * Y)
        inside = rho < 1
        c = np.arcsin(np.clip(rho, 0, 1))
        sc_, cc_ = np.sin(c), np.cos(c)
        lat = np.arcsin(np.clip(cc_ * math.sin(lat0) + np.where(rho > 0, Y * sc_ * math.cos(lat0) / np.maximum(rho, 1e-6), 0), -1, 1))
        lon = lon0 + np.arctan2(X * sc_, rho * math.cos(lat0) * cc_ - Y * math.sin(lat0) * sc_)
        th, tw = self.tex.shape[:2]
        mx = ((lon / (2 * math.pi) + 0.5) % 1.0) * (tw - 1)
        my = (0.5 - lat / math.pi) * (th - 1)
        col = cv2.remap(self.tex, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        oc = cv2.remap(self.ocean, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        Z = np.sqrt(np.clip(1 - rho * rho, 0, 1))
        L = np.array([-0.55, 0.45, 0.70]); L /= np.linalg.norm(L)
        ndl = X * L[0] + Y * L[1] + Z * L[2]
        day = np.clip(ndl * 2.2 + 0.25, 0, 1)
        col = col * (0.10 + 1.05 * day)[..., None]
        Hh = L + np.array([0, 0, 1.0]); Hh /= np.linalg.norm(Hh)
        spec = np.clip(X * Hh[0] + Y * Hh[1] + Z * Hh[2], 0, 1) ** 40 * oc * 0.6
        col += spec[..., None]
        limb = (1 - Z) ** 3
        col = col * (1 - limb[..., None] * 0.35) + limb[..., None] * np.array([0.95, 0.65, 0.35], np.float32) * 0.35 * day[..., None]
        a = np.clip((1 - rho) * Rp / 1.5, 0, 1)
        add_rgba(img, col * a[..., None], a, x0, y0)
        # atmosfer halesi
        hal = np.zeros((H, W), np.float32)
        cv2.circle(hal, (int(cx * s), int(cy * s)), Rp, 1.0, max(2, int(10 * s)), cv2.LINE_AA)
        img += cv2.GaussianBlur(hal, (0, 0), 18 * s)[..., None] * np.array([0.95, 0.60, 0.30], np.float32) * 0.55
        # isaretler (Pakistan, Afganistan)
        red = np.array((0.25, 0.25, 0.95), np.float32)
        mt = p.get("mark_t", 2.2)
        ma = ease_out(prog(t, mt, mt + 0.6))
        pts = []
        for la_, lo_ in p.get("marks", []):
            la, lo = math.radians(la_), math.radians(lo_)
            cosc = math.sin(lat0) * math.sin(la) + math.cos(lat0) * math.cos(la) * math.cos(lo - lon0)
            if cosc <= 0.05:
                continue
            px_ = math.cos(la) * math.sin(lo - lon0); py_ = math.cos(lat0) * math.sin(la) - math.sin(lat0) * math.cos(la) * math.cos(lo - lon0)
            sx_, sy_ = cx + px_ * Rr, cy - py_ * Rr
            pts.append((sx_, sy_))
            if ma > 0:
                lay = np.zeros((H, W), np.float32)
                cv2.circle(lay, (int(sx_ * s), int(sy_ * s)), max(2, int(10 * s)), 1.0, -1, cv2.LINE_AA)
                ph = ((t - mt) % 1.2) / 1.2
                cv2.circle(lay, (int(sx_ * s), int(sy_ * s)), int((10 + 34 * ph) * s), (1 - ph), max(1, int(2 * s)), cv2.LINE_AA)
                img += cv2.GaussianBlur(lay, (0, 0), 9 * s)[..., None] * red * ma
                lm = (lay * ma)[..., None]
                img[:] = img * (1 - lm) + lm * np.array((0.30, 0.30, 1.0), np.float32)
        if pts and ma > 0 and p.get("mark_label"):
            mx_ = max(q[0] for q in pts) + 70; my_ = min(q[1] for q in pts) - 150
            lab, sub = p["mark_label"]
            tw = max(text_width(lab, F_BOLD, 28, 2), text_width(sub, F_MED, 22, 1)) + 44
            mx_ = min(mx_, 1920 - SAFE_X - tw - 10)
            rrect(img, mx_, my_, mx_ + tw, my_ + 86, 10, (0.05, 0.035, 0.03), 0.85 * ma, s)
            rrect(img, mx_, my_, mx_ + 6, my_ + 86, 3, red, ma, s)
            draw_text(cv, img, lab, F_BOLD, 28, WHITE, mx_ + 22, my_ + 10, opacity=ma, tracking=2, shadow=0, check_safe=False)
            draw_text(cv, img, sub, F_MED, 22, (210, 210, 210), mx_ + 22, my_ + 50, opacity=ma * 0.9, tracking=1, shadow=0, check_safe=False)
        img *= fx.left_dark * 0.55 + 0.45
        y = 360
        for text, kind, t0 in p["lines"]:
            a = ease_out(prog(t, t0, t0 + 0.5))
            if kind == "big":
                sc = lerp(1.08, 1.0, a)
                draw_text(cv, img, text, F_BLACK, 96 * sc, YELLOW, SAFE_X + 40, y + lerp(20, 0, a), opacity=a, tracking=1, shadow=12)
                y += 124
            else:
                draw_text(cv, img, text, F_SEMI, 46, WHITE, SAFE_X + 44, y, reveal=prog(t, t0, t0 + 0.55), shadow=8)
                y += 72
        if p.get("note"):
            draw_text(cv, img, p["note"], F_MED, 22, (190, 190, 190), SAFE_X + 42, 1080 - SAFE_Y - 40, opacity=0.7 * ease(prog(t, 1.5, 2.0)), tracking=1)
        self.caption(img, t)
        return img


# ---------- yil karti: gercek mekan fotografi ile (Rackham, Ann Arbor) ----------
_YC_render = YearCard.render
def _yc_render(self, t, f):
    a = self.spec.get("visualAssets")
    if not a:
        return _YC_render(self, t, f)
    cv, fx = self.cv, self.fx
    if not hasattr(self, "_photo"):
        self._photo = grade(load(a[0]), self.p.get("grade", "desat"))
    u = ease(t / self.d)
    img = cv.place(self._photo, cv.cover(self._photo) * lerp(1.10, 1.02, u), lerp(990, 930, u), lerp(560, 540, u))
    img *= 0.42
    img += navy_bg(cv, fx, t) * 0.35
    zoom = lerp(1.0, 1.04, u)
    year = self.p["year"]; size = 300 * zoom
    aa = ease_out(prog(t, 0.15, 1.1)); sc = lerp(1.10, 1.0, ease_out(prog(t, 0.15, 1.3))); sz = size * sc
    w = text_width(year, F_BLACK, sz, 6 * sc)
    text3d(cv, img, year, F_BLACK, sz, 960 - w / 2, 540 - sz * 0.62, YELLOW, depth=14, opacity=aa, tracking=6 * sc, sweep=prog(t, 1.2, 2.2))
    lw = 560 * ease(prog(t, 0.8, 1.7)) * zoom
    y = int((540 + 140 * zoom) * cv.s)
    cv2.line(img, (int((960 - lw / 2) * cv.s), y), (int((960 + lw / 2) * cv.s), y), np.array(YELLOW) / 255.0, max(1, int(4 * cv.s)), cv2.LINE_AA)
    k = self.p["kicker"]; ka = ease(prog(t, 1.1, 1.8)); kw = text_width(k, F_SEMI, 30, 10)
    draw_text(cv, img, k, F_SEMI, 30, (235, 235, 235), 960 - kw / 2, 540 - 245 * zoom, opacity=0.85 * ka, tracking=10)
    self.caption(img, t)
    return img
YearCard.render = _yc_render


# ---------- aile: once gercek asi fotografi + 3B sise, sonra gercekci figurler ----------
_FAM_render = FamilyIcons.render
def _family_real(self, t, f):
    p = self.p
    cv, fx = self.cv, self.fx
    s = cv.s; W, H = cv.W, cv.H
    people = p["people"]
    t_cut = min(pp[2] for pp in people) - 0.6
    intro = p.get("intro_photo")
    if intro and not hasattr(self, "_ph"):
        im = grade(load(intro), "bw_cool")
        b = 18
        fr = np.ones((im.shape[0] + 2 * b, im.shape[1] + 2 * b, 3), np.float32) * np.array([0.90, 0.93, 0.94], np.float32)
        fr[b:-b, b:-b] = im
        self._ph = (fr, np.ones(fr.shape[:2], np.float32))

    def intro_frame(tt):
        img = vial_scene(cv, fx, tt, hero_x=1420, hero_h=640, second=False)
        ci, ca = self._ph
        h, w = ci.shape[:2]
        cam = Cam3((0, -260, -1300), yaw=lerp(-4, 2, ease(tt / 4)), pitch=6, f=1150)
        ww, hh = 760 * w / max(w, h), 760 * h / max(w, h)
        x0_ = -560
        quad = [[x0_ - ww / 2, -hh + 40, 300], [x0_ + ww / 2, -hh + 40, 140], [x0_ + ww / 2, 40, 140], [x0_ - ww / 2, 40, 300]]
        q, _ = cam.proj(quad)
        sh = np.zeros((H, W), np.float32)
        cv2.fillConvexPoly(sh, np.int32((q + np.array([30, 40])) * s), 1.0, cv2.LINE_AA)
        img *= (1 - cv2.GaussianBlur(sh, (0, 0), 22 * s)[..., None] * 0.55)
        warp_quad(img, ci * 0.95, ca, q, s)
        cap = p.get("intro_caption")
        if cap:
            draw_text(cv, img, cap, F_MED, 19, (225, 225, 225), SAFE_X, SAFE_Y, opacity=0.72 * ease(prog(tt, 0.3, 0.9)), tracking=1.2, shadow=4)
        return img

    def people_frame(tt):
        img = navy_bg(cv, fx, tt)
        floor_y = 780
        yy = fx.yy / s
        flo = np.clip((yy - floor_y) / 300, 0, 1)
        img += (flo * (1 - flo) * 0.10)[..., None] * np.array([0.9, 0.85, 0.8], np.float32)
        yr = p.get("bigyear", "1953")
        yw = text_width(yr, F_BLACK, 420, 4)
        draw_text(cv, img, yr, F_BLACK, 420, (255, 255, 255), 960 - yw / 2, 140, opacity=0.05, tracking=4, shadow=0, check_safe=False)
        n = len(people)
        xs = [960 + (i - (n - 1) / 2) * 300 for i in range(n)]
        kinds = ["man", "woman", "boy", "cap", "boy"]
        pals = [5, 7, 0, 2, 4]
        for i, (lab, h, ton) in enumerate(people):
            on = ease_out(prog(tt, ton, ton + 0.45))
            hp = int(h * 1.85 * s)
            if on > 0:
                cone = np.zeros((H, W), np.float32)
                pts = np.int32([[(xs[i] - 26) * s, 0], [(xs[i] + 26) * s, 0], [(xs[i] + h * 0.62) * s, floor_y * s], [(xs[i] - h * 0.62) * s, floor_y * s]])
                cv2.fillConvexPoly(cone, pts, 1.0, cv2.LINE_AA)
                cone = cv2.GaussianBlur(cone, (0, 0), 18 * s) * (0.35 + 0.65 * (fx.yy / (floor_y * s)).clip(0, 1))
                img += cone[..., None] * np.array([0.75, 0.88, 1.0], np.float32) * 0.16 * on
                pool = np.zeros((H, W), np.float32)
                cv2.ellipse(pool, (int(xs[i] * s), int(floor_y * s)), (int(h * 0.62 * s), int(h * 0.10 * s)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
                img += cv2.GaussianBlur(pool, (0, 0), 10 * s)[..., None] * 0.18 * on
            q = round(on * 4) / 4
            rgb, a = fig_sprite(kinds[i % 5], hp, pals[i % 5], flip=(i % 2 == 1), amb=0.18 + 0.30 * q, key=0.30 + 0.55 * q, rimk=0.25 + 0.55 * q, rim=(0.0, -1.0), sat=0.15 + 0.85 * q, warm=0.35 * q)
            x0 = xs[i] * s - a.shape[1] / 2; y0 = floor_y * s - a.shape[0] * 0.96
            sh = np.zeros((H, W), np.float32)
            cv2.ellipse(sh, (int(xs[i] * s), int(floor_y * s)), (int(a.shape[1] * 0.45), max(1, int(a.shape[1] * 0.08))), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
            img *= (1 - cv2.GaussianBlur(sh, (0, 0), 5 * s)[..., None] * 0.6)
            fade = np.linspace(0.12, 0.0, a.shape[0], dtype=np.float32)[:, None]
            add_rgba(img, rgb[::-1] * fade[..., None], a[::-1] * fade, x0, floor_y * s + 2)
            add_rgba(img, rgb, a, x0, y0)
            lw_ = text_width(lab, F_BOLD, 30, 3)
            draw_text(cv, img, lab, F_BOLD, 30, WHITE, xs[i] - lw_ / 2, floor_y + 60, opacity=0.35 + 0.65 * on, tracking=3)
        title = p.get("title")
        if title:
            tw = text_width(title, F_BLACK, 66, 2)
            draw_text(cv, img, title, F_BLACK, 66, WHITE, 960 - tw / 2, 120, reveal=prog(tt, max(t_cut, 0) + 0.1, max(t_cut, 0) + 0.7), tracking=2, shadow=8)
        return img

    if intro and t < t_cut - 0.25:
        return intro_frame(t)
    if intro and t < t_cut + 0.25:
        k = ease(prog(t, t_cut - 0.25, t_cut + 0.25))
        return intro_frame(t) * (1 - k) + people_frame(t) * k
    return people_frame(t)
FamilyIcons.render = _family_real


# ---------- kalabalik: renkli, hacimli, net figurler ----------
def _crowd_render(self, t, f):
    cv, fx, p = self.cv, self.fx, self.p
    s = cv.s; W, H = cv.W, cv.H
    cam = self.cam(t)
    sun = np.array([0.55, 0.80, 1.0], np.float32)
    hz, _ = cam.proj([[0, 0, 1e6]])
    hy = hz[0, 1] * s
    yy = fx.yy
    u = np.clip((hy - yy) / (H * 0.85), 0, 1)[..., None]
    c_top = np.array([0.20, 0.10, 0.05], np.float32); c_mid = np.array([0.42, 0.34, 0.36], np.float32); c_hor = np.array([0.45, 0.66, 0.92], np.float32)
    img = np.where(u > 0.35, c_mid + (c_top - c_mid) * ((u - 0.35) / 0.65), c_hor + (c_mid - c_hor) * (u / 0.35)).astype(np.float32)
    g = np.clip((yy - hy) / (H * 0.9), 0, 1)[..., None]
    ground = np.array([0.10, 0.17, 0.14], np.float32) * (0.7 + 0.3 * g) + c_hor * 0.35 * (1 - g) ** 8
    img = np.where((yy >= hy)[..., None], ground + (fx.grain[3][..., None] * 0.012) * (yy >= hy)[..., None], img).astype(np.float32)
    sx, sy = 1180 * s, hy - 26 * s
    d = np.sqrt((fx.xx - sx) ** 2 + (fx.yy - sy) ** 2) / (W * 0.5)
    img += (np.exp(-d ** 2 * 420) * 1.2 + np.exp(-d ** 2 * 18) * 0.22 + np.exp(-d ** 2 * 2.5) * 0.07)[..., None] * sun
    ang = np.arctan2(fx.yy - sy, fx.xx - sx)
    img += ((0.5 + 0.5 * np.cos(ang * 5 + t * 0.15)) ** 8 * np.exp(-d * 2.4) * 0.04)[..., None] * sun
    P0 = np.stack([self.X, np.zeros_like(self.X), self.Z], 1)
    base, z = cam.proj(P0)
    Hf = 118 * self.hgt
    top_, _ = cam.proj(np.stack([self.X, -Hf, self.Z], 1))
    order = np.argsort(-z)
    shadow = np.zeros((H, W), np.float32)
    glow = np.zeros((H, W), np.float32)
    fogc = c_hor * 0.80
    warm = np.array((0.20, 0.40, 0.70), np.float32)
    kinds = ("boy", "cap", "girl", "pony")
    pitch_k = max(0.12, math.sin(math.radians(cam_pitch(t, self))) + 0.15)
    for i in order:
        zi = z[i]
        if zi < 40:
            continue
        bx, by = base[i] * s
        hp = by - top_[i, 1] * s
        if hp < 1.0 or by < -20 or by - hp > H or bx < -200 or bx > W + 200:
            continue
        fog = float(np.clip((zi - 600) / 6400, 0, 0.92)) ** 0.9
        on = float(np.clip((t - self.t_on[i]) / 0.3, 0, 1))
        sl = hp * 3.6 * pitch_k
        cv2.ellipse(shadow, (int(bx), int(by + sl * 0.45)), (max(1, int(hp * 0.16)), max(1, int(sl * 0.5))), 0, 0, 360, 1.0 - fog, -1)
        if hp >= 9:
            hpx = int(round(hp)) if hp < 40 else (int(round(hp / 2) * 2) if hp < 100 else int(round(hp / 4) * 4))
            q = round(on * 2) / 2
            rgb, a = fig_sprite(kinds[int(self.var[i])], hpx, int(i * 7 % len(FIG_PALS)), flip=bool(self.flip[i]),
                                light=(-0.55, -0.6), amb=0.30 + 0.18 * q, key=0.40 + 0.40 * q, rim=(0.85, -0.35), rimk=0.55 + 0.35 * q, sat=0.30 + 0.70 * q, warm=0.45 * q)
            hh, ww = a.shape
            x0 = int(bx - ww / 2); y0 = int(by - hh)
            if fog > 0.01:
                rgb = rgb * (1 - fog) + a[..., None] * fogc * fog
            add_rgba(img, rgb, a, x0, y0)
        else:
            colr = (np.array((0.30, 0.32, 0.36), np.float32) * (1 - on) + warm * on) * (1 - fog) + fogc * fog
            cv2.ellipse(img, (int(bx), int(by - hp * 0.5)), (max(1, int(hp * 0.16)), max(1, int(hp * 0.5))), 0, 0, 360, colr.tolist(), -1, cv2.LINE_AA)
        if on > 0:
            cv2.circle(glow, (int(bx), int(by - hp * 0.55)), max(1, int(hp * 0.45)), on * (1 - fog * 0.7), -1)
    sh_op = 0.55 * min(1.0, max(0.0, (pitch_k - 0.12) / 0.25))
    img *= (1 - cv2.GaussianBlur(shadow, (0, 0), 2.5 * s)[..., None] * sh_op)
    img += cv2.GaussianBlur(glow, (0, 0), 8 * s)[..., None] * warm * 0.14
    Pm = self.motes + np.array([t * 18, 0, 0]) + np.stack([np.zeros(60), np.sin(t + self.mph) * 10, np.zeros(60)], 1)
    mq, mz = cam.proj(Pm)
    lay = np.zeros((H, W), np.float32)
    for i in range(len(Pm)):
        if mz[i] > 30:
            cv2.circle(lay, (int(mq[i, 0] * s), int(mq[i, 1] * s)), max(1, int(cam.f * 1.6 / mz[i] * s)), 0.7, -1, cv2.LINE_AA)
    img += cv2.GaussianBlur(lay, (0, 0), 2 * s)[..., None] * sun * 0.30
    frac = float(np.mean(t > self.t_on))
    v = int(round(p["value"] * frac))
    rrect(img, SAFE_X + 20, 100, SAFE_X + 760, 330, 14, (0.04, 0.03, 0.02), 0.50, s)
    draw_text(cv, img, f"{v:,}".replace(",", "."), F_BLACK, 110, WHITE, SAFE_X + 40, 110, opacity=ease_out(prog(t, 0.2, 0.7)), tracking=2, shadow=12)
    draw_text(cv, img, p["label"], F_BOLD, 34, YELLOW, SAFE_X + 44, 245, reveal=prog(t, 0.5, 1.1), tracking=6)
    if p.get("note"):
        draw_text(cv, img, p["note"], F_MED, 22, (220, 220, 220), SAFE_X + 44, 1080 - SAFE_Y - 40, opacity=0.8 * ease(prog(t, 1.0, 1.5)), tracking=1)
    return img
CrowdCine.render = _crowd_render


EXT7_SCENES = {"coins": CoinsReal, "virus3d": Virus3DReal, "cutter3d": CutterScale, "bars3d": Bars3DReal,
               "timeline3d": Timeline3DReal, "globe": GlobeScene}
SCENES.update(EXT7_SCENES)


# Brifteki sahne aileleri -> motor tipleri (belgelenmis takma adlar)
SCENE_ALIASES = {
    "CinematicOpening": "year_card", "HistoricalArchiveScene": "archival_push", "ThreeDParticleScene": "virus3d",
    "CrowdVisualization": "crowd3d", "Timeline3DScene": "timeline3d", "StatisticalChartScene": "bars3d",
    "KineticTypographyScene": "quote", "CinematicEnding": "end_screen",
}
for _k, _v in SCENE_ALIASES.items():
    SCENES.setdefault(_k, SCENES[_v])


def peak_mem_mb():
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e3
        except Exception:
            return None


def validate(tl):
    """Render oncesi kontrol: sahne tipi, eksik/bozuk dosya, zamanlama. Anlasilir Turkce hata listesi dondurur."""
    errs, warns = [], []
    for sp in tl["scenes"]:
        sid = sp.get("id", "?")
        if sp.get("type") not in SCENES:
            errs.append(f"[{sid}] bilinmeyen sahne tipi: {sp.get('type')}")
        for a in sp.get("visualAssets") or []:
            if not os.path.isfile(a):
                errs.append(f"[{sid}] dosya bulunamadi: {a}")
            else:
                try:
                    if a.lower().endswith((".jpg", ".jpeg", ".png")):
                        imread(a)
                except Exception:
                    errs.append(f"[{sid}] dosya bozuk/okunamiyor: {a}")
        if "start" not in sp and "duration" not in sp:
            errs.append(f"[{sid}] sure tanimsiz")
        if not sp.get("purpose"):
            warns.append(f"[{sid}] anlati amaci (purpose) yazilmamis")
    if tl.get("map_dir") and not os.path.isfile(os.path.join(tl["map_dir"], "bbox.json")):
        errs.append("harita dosyalari eksik: " + tl["map_dir"])
    return errs, warns


def badge(cv, img, text):
    """Arsiv ile temsili canlandirmayi ayirt eden kucuk etiket."""
    w = text_width(text, F_BOLD, 18, 3) + 28
    x0, y0 = SAFE_X, SAFE_Y + 34
    rrect(img, x0, y0, x0 + w, y0 + 32, 6, (0.10, 0.07, 0.05), 0.75, cv.s)
    draw_text(cv, img, text, F_BOLD, 18, TEAL, x0 + 14, y0 + 6, tracking=3, shadow=0)


def main():
    import time, traceback
    ap = argparse.ArgumentParser()
    ap.add_argument("timeline"); ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--stills", default="")
    ap.add_argument("--crf", type=int, default=17)
    ap.add_argument("--hq", action="store_true", help="final kalite: kubik ornekleme + yavas kodlama")
    a = ap.parse_args()
    tl = json.load(open(a.timeline, encoding="utf-8"))
    HQ["on"] = a.hq
    errs, warns = validate(tl)
    if errs:
        print("RENDER BASLATILMADI - duzeltilmesi gerekenler:")
        for e in errs:
            print("  -", e)
        sys.exit(2)
    fps = tl["fps"]; s = a.scale
    W, H = int(1920 * s) // 2 * 2, int(1080 * s) // 2 * 2
    cv = Canvas(W, H, s); fx = FX(W, H)
    scenes, total = build_timeline(tl)
    objs = [None] * len(scenes)     # sahneler yalnizca ekrandayken bellekte tutulur (tembel kurulum)

    def get_obj(i):
        if objs[i] is None:
            sp = scenes[i]
            try:
                objs[i] = SCENES[sp["type"]](sp, cv, fx)
            except Exception as ex:
                print(f"HATA: [{sp['id']}] sahnesi hazirlanamadi ({sp['type']}): {ex}")
                traceback.print_exc(); sys.exit(3)
        return objs[i]
    cues = subtitles(scenes)
    logo_small = imread("src/logo.png").astype(np.float32) / 255.0
    stats = {sp["id"]: [0.0, 0] for sp in scenes}

    def frame_at(fi):
        T = fi / fps
        idx = [i for i, sp in enumerate(scenes) if sp["start"] <= T < sp["end"]] or [len(scenes) - 1]
        for i, sp in enumerate(scenes):
            if objs[i] is not None and i not in idx and (T > sp["end"] or T < sp["start"] - 1):
                objs[i] = None
        act = [(scenes[i], get_obj(i)) for i in idx]
        cur_id = act[-1][0]["id"]
        if frame_at.__dict__.get("last") != cur_id:     # sahne degisti: buyuk onbellekleri bosalt (bellek tasmasi onlemi)
            frame_at.last = cur_id
            for c in ("_CAP", "_VF", "_FIGC", "_VIAL", "_SPR", "_TERR"):
                d = globals().get(c)
                if isinstance(d, dict):
                    d.clear()
            cv.__dict__.pop("_mip", None)
            import gc; gc.collect()
        imgs = []
        for sp, o in act:
            t0 = time.perf_counter()
            try:
                im = o.render(T - sp["start"], fi)
            except Exception as ex:
                raise RuntimeError(f"[{sp['id']}] sahnesi {T:.2f}. saniyede cizilemedi ({sp['type']}): {ex}")
            if sp.get("visualType") in ("dataGraphic", "illustration") and sp["type"] not in ("end_screen",):
                u = (T - sp["start"]) / max(sp["end"] - sp["start"], 1e-6)
                z = 1.0 + 0.035 * ease(u)
                M = np.float32([[z, 0, (1 - z) * W / 2], [0, z, (1 - z) * H / 2]])
                im = cv2.warpAffine(im, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT101)
            if sp.get("visualType") == "reconstruction":
                badge(cv, im, sp.get("badge", "TEMSİLİ CANLANDIRMA"))
            st = stats[sp["id"]]; st[0] += time.perf_counter() - t0; st[1] += 1
            imgs.append(im)
        if len(act) == 2:
            sp2 = act[1][0]; ti = sp2["transitionIn"]
            p = (T - sp2["start"]) / max(ti["dur"], 1e-6)
            img = transition(ti["type"], imgs[0], imgs[1], p, fx, cv)
        else:
            img = imgs[0]
        img = img * fx.vig
        if not act[-1][0].get("noSubs") and not (len(act) == 2 and act[0][0].get("noSubs") and T - act[1][0]["start"] < 0.3):
            draw_subtitle(cv, img, T, cues)
        cur = act[-1][0]
        if cur["type"] not in ("logo", "end_screen", "chapter", "kod"):
            sz = 64 / logo_small.shape[1]
            lg = cv.place(logo_small, sz, 1920 - SAFE_X - 32, SAFE_Y + 32, border=cv2.BORDER_CONSTANT)
            m = cv.place(np.ones(logo_small.shape[:2], np.float32), sz, 1920 - SAFE_X - 32, SAFE_Y + 32, border=cv2.BORDER_CONSTANT)[..., None] * 0.55
            img = img * (1 - m) + lg * m
        img = fx.apply_grain(img, fi // 2, 0.02)
        img *= min(1.0, T / 0.35, (total - T) / 0.5)
        out = np.clip(img, 0, 1)
        if not np.isfinite(out).all():
            raise RuntimeError(f"{T:.2f}. saniyede gecersiz piksel (NaN) olustu")
        return (out * 255).astype(np.uint8)

    if a.stills:
        for ts in a.stills.split(","):
            fi = int(float(ts) * fps)
            imwrite(f"{a.out}_{float(ts):05.1f}.jpg", frame_at(fi))
        print("safe violations:", sorted(set(QC["safe_violations"])))
        return

    n = int(round(total * fps))
    gop = max(1, fps // 2)
    tmp = a.out + ".yaziliyor.mp4"   # once gecici dosya; basarili olursa yeniden adlandirilir (yarim dosya kalmaz)
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", "slow" if a.hq else "medium", "-crf", str(a.crf), "-tune", "film",
           "-profile:v", "high", "-bf", "2", "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0", "-flags", "+cgop",
           "-coder", "1", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-movflags", "+faststart", tmp]
    t_start = time.time()
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    log = {"ok": False, "error": None}
    try:
        for fi in range(n):
            pr.stdin.write(frame_at(fi).tobytes())
            if fi % 48 == 0:
                el = time.time() - t_start
                eta = el / max(fi, 1) * (n - fi)
                print(f"kare {fi}/{n}  (%{100 * fi / n:.0f}, kalan ~{eta / 60:.1f} dk)", flush=True)
        pr.stdin.close(); rc = pr.wait()
        if rc != 0:
            raise RuntimeError(f"FFmpeg kodlama hatasi (kod {rc})")
        # kare sayisi dogrulamasi
        fdir, fbase = os.path.split(FFMPEG)
        probe = os.path.join(fdir, fbase.replace("ffmpeg", "ffprobe")) if fdir else "ffprobe"
        q = subprocess.run([probe,
                            "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames", "-of", "csv=p=0", tmp],
                           capture_output=True, text=True)
        got = int(q.stdout.strip() or 0)
        if got != n:
            raise RuntimeError(f"kare sayisi tutmuyor: beklenen {n}, yazilan {got}")
        os.replace(tmp, a.out)
        log["ok"] = True
    except Exception as ex:
        log["error"] = str(ex)
        try:
            pr.kill()
        except Exception:
            pass
        print("RENDER HATASI:", ex)
    sec = time.time() - t_start
    log.update({"total_s": total, "frames": n, "render_dk": round(sec / 60, 2), "kare_basina_ms": round(1000 * sec / max(n, 1), 1),
                "bellek_tepe_mb": peak_mem_mb(), "uyarilar": warns,
                "sahneler": [{"id": sp["id"], "tip": sp["type"], "amac": sp.get("purpose", ""), "baslangic": sp["start"], "bitis": sp["end"],
                              "ms_kare": round(1000 * stats[sp["id"]][0] / max(stats[sp["id"]][1], 1), 1)} for sp in scenes]})
    json.dump(log, open(a.out + ".render_log.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"total": total, "frames": n, "scenes": [{k: sp[k] for k in ("id", "start", "end")} for sp in scenes],
               "subtitles": cues, "safe_violations": sorted(set(QC["safe_violations"]))},
              open(a.out + ".qc.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not log["ok"]:
        sys.exit(4)
    print("done", total, "s", n, "frames; safe violations:", sorted(set(QC["safe_violations"])))


if __name__ == "__main__":
    main()
