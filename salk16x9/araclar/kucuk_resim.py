"""Beyin Kodu Lab kucuk resim (1920x1080): sol portre kesimi + sag buyuk yazi + gunes arka plan.
Kullanim: python kucuk_resim.py portre.jpg maske.png arkaplan.jpg cikti.jpg"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import F_BLACK
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
POR, MASK, BG, OUT = sys.argv[1:5]
W, H = 1920, 1080
sun = cv2.imread(BG)[:, :, ::-1]
h, w = sun.shape[:2]; s = max(W / w, H / h) * 1.15
sun = cv2.resize(sun, (int(w * s), int(h * s)), interpolation=cv2.INTER_CUBIC)
y0 = (sun.shape[0] - H) // 2; x0 = max(0, min(int(sun.shape[1] * 0.55) - W // 2, sun.shape[1] - W))
bg = cv2.GaussianBlur(sun[y0:y0 + H, x0:x0 + W].astype(np.float32) / 255, (0, 0), 2.2)
yy, xx = np.mgrid[0:H, 0:W]; xx = xx / W; yy = yy / H
lum = 0.10 + 0.95 * np.clip((xx - 0.30) / 0.55, 0, 1) ** 1.2
vig = 1 - 0.55 * (((xx - 0.62) / 0.75) ** 2 + ((yy - 0.5) / 0.7) ** 2)
bg = np.clip(bg * (lum * np.clip(vig, 0.25, 1))[..., None] * np.array([1.10, 0.78, 0.42]) * 1.15, 0, 1)
img = Image.fromarray((bg * 255).astype(np.uint8)).convert('RGBA')
por = cv2.imread(POR, 0); m = cv2.imread(MASK, 0)
ph = 1220; pw = int(por.shape[1] * ph / por.shape[0])
por = cv2.resize(por, (pw, ph), interpolation=cv2.INTER_CUBIC); m = cv2.resize(m, (pw, ph))
por = cv2.createCLAHE(2.2, (8, 8)).apply(por)
por = cv2.addWeighted(por, 1.6, cv2.GaussianBlur(por, (0, 0), 2), -0.6, 0)
p = (np.stack([por] * 3, -1).astype(np.float32) / 255) ** 1.05 * np.array([1.0, 0.96, 0.88])
ma = cv2.GaussianBlur(cv2.erode(m, np.ones((3, 3), np.uint8)).astype(np.float32) / 255, (0, 0), 1.4)
edge = np.clip(ma - cv2.GaussianBlur(np.roll(ma, -14, axis=1), (0, 0), 6), 0, 1)
p = np.clip(p + edge[..., None] * np.array([1.0, 0.62, 0.22]) * 0.9, 0, 1)
P = Image.fromarray((np.dstack([p, ma[..., None]]) * 255).astype(np.uint8), 'RGBA')
px, py = -90, H - ph + 110
glow = Image.new('RGBA', (pw, ph), (255, 150, 40, 0)); glow.putalpha(Image.fromarray((cv2.GaussianBlur(ma, (0, 0), 40) * 150).astype(np.uint8)))
img.alpha_composite(glow, (px + 30, py)); img.alpha_composite(P, (px, py))


def text(t, f, x, y, top, bot, stroke=0):
    tw, th = int(f.getlength(t)) + 40, f.size + 60
    mask = Image.new('L', (tw, th), 0); ImageDraw.Draw(mask).text((20, 10), t, font=f, fill=255)
    sh = Image.new('RGBA', (tw, th), (0, 0, 0, 0)); sh.putalpha(mask.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.9)))
    img.alpha_composite(sh, (x + 8, y + 12))
    if stroke:
        st = Image.new('RGBA', (tw, th), (10, 8, 6, 255)); st.putalpha(mask.filter(ImageFilter.MaxFilter(stroke * 2 + 1))); img.alpha_composite(st, (x, y))
    g = np.linspace(0, 1, th)[:, None, None]
    G = Image.fromarray((np.array(top) * (1 - g) + np.array(bot) * g * np.ones((th, tw, 3))).astype(np.uint8)).convert('RGBA'); G.putalpha(mask)
    img.alpha_composite(G, (x, y))


fA = ImageFont.truetype(F_BLACK, 230); fB = ImageFont.truetype(F_BLACK, 112)
tx = 860
text("PATENT", fA, tx, 90, (255, 226, 90), (255, 160, 10), 5)
text("YOK!", fA, tx + 30, 330, (255, 255, 255), (225, 225, 230), 5)
t = "$7.000.000.000"; y = 640; text(t, fB, tx + 10, y, (255, 255, 255), (215, 215, 215), 4)
d = ImageDraw.Draw(img); bw = fB.getlength(t)
for col, wd in (((10, 8, 6, 255), 26), ((235, 35, 35, 255), 16)):
    d.line([(tx + 20, y + 102), (tx + 40 + bw, y + 66)], fill=col, width=wd)
img.convert('RGB').save(OUT, quality=95, subsampling=0)
