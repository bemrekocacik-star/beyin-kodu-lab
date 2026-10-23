"""Gercekci figur sprite'lari: maske + bolge etiketi (1 ten, 2 sac, 3 ust giysi, 4 alt giysi, 5 ayakkabi, 6 sapka/kravat).
Cikti: figures.npz (her tur icin <tur>_m ve <tur>_l). Bir kez calistirilir; motor bu dosyayi okur."""
import cv2, numpy as np, os

SKIN, HAIR, TOP, BOT, SHOE, ACC = 1, 2, 3, 4, 5, 6


def make(kind, S=640):
    W = S // 2
    lab = np.zeros((S, W), np.uint8)
    cx = W / 2

    def poly(pts, v):
        cv2.fillPoly(lab, [np.int32(np.round(pts))], v, cv2.LINE_AA)

    def ell(c, ax, ang, v, a0=0, a1=360):
        cv2.ellipse(lab, (int(c[0]), int(c[1])), (max(1, int(ax[0])), max(1, int(ax[1]))), ang, a0, a1, v, -1, cv2.LINE_AA)

    adult = kind in ("man", "woman")
    head_r = S * (0.062 if adult else 0.092)
    hy = S * (0.085 if adult else 0.125)
    sh = S * (0.185 if adult else 0.245)
    # boyun
    poly([(cx - S * .022, hy + head_r * 0.6), (cx + S * .022, hy + head_r * 0.6), (cx + S * .024, sh + 6), (cx - S * .024, sh + 6)], SKIN)
    if kind == "man":
        # takim elbise ceket
        poly([(cx - S * .115, sh), (cx + S * .115, sh), (cx + S * .108, S * .50), (cx - S * .108, S * .50)], TOP)
        for sg in (-1, 1):
            poly([(cx + sg * S * .105, sh + 4), (cx + sg * S * .14, sh + S * .03), (cx + sg * S * .150, S * .47), (cx + sg * S * .118, S * .48)], TOP)   # kol
            ell((cx + sg * S * .134, S * .49), (S * .018, S * .024), 0, SKIN)                                                               # el
            poly([(cx + sg * S * .006, S * .49), (cx + sg * S * .095, S * .49), (cx + sg * S * .078, S * .945), (cx + sg * S * .030, S * .945)], BOT)  # pantolon
            ell((cx + sg * S * .058, S * .958), (S * .042, S * .016), 0, SHOE)
        poly([(cx - S * .026, sh), (cx + S * .026, sh), (cx, sh + S * .07)], SKIN)          # gomlek yakasi (acik ton)
        poly([(cx - S * .010, sh + S * .012), (cx + S * .010, sh + S * .012), (cx + S * .014, sh + S * .14), (cx, sh + S * .16), (cx - S * .014, sh + S * .14)], ACC)  # kravat
        ell((cx, hy), (head_r * 0.92, head_r * 1.08), 0, SKIN)
        ell((cx, hy - head_r * 0.42), (head_r * 0.98, head_r * 0.62), 0, HAIR, 180, 360)   # kisa sac
    elif kind == "woman":
        poly([(cx - S * .085, sh), (cx + S * .085, sh), (cx + S * .062, S * .40), (cx - S * .062, S * .40)], TOP)      # bluz/elbise ust
        poly([(cx - S * .066, S * .39), (cx + S * .066, S * .39), (cx + S * .15, S * .74), (cx - S * .15, S * .74)], TOP)  # 1950'ler etek (genis)
        for sg in (-1, 1):
            poly([(cx + sg * S * .08, sh + 4), (cx + sg * S * .115, sh + S * .03), (cx + sg * S * .125, S * .43), (cx + sg * S * .096, S * .44)], TOP)
            ell((cx + sg * S * .110, S * .45), (S * .016, S * .022), 0, SKIN)
            poly([(cx + sg * S * .018, S * .73), (cx + sg * S * .052, S * .73), (cx + sg * S * .046, S * .945), (cx + sg * S * .028, S * .945)], SKIN)
            ell((cx + sg * S * .040, S * .956), (S * .028, S * .013), 0, SHOE)
        ell((cx, hy + head_r * 0.25), (head_r * 1.25, head_r * 1.18), 0, HAIR)   # dalgali sac
        ell((cx, hy + head_r * 0.12), (head_r * 0.86, head_r * 1.0), 0, SKIN)
        ell((cx, hy - head_r * 0.48), (head_r * 1.05, head_r * 0.55), 0, HAIR, 180, 360)
    elif kind in ("boy", "cap"):
        poly([(cx - S * .11, sh), (cx + S * .11, sh), (cx + S * .10, S * .57), (cx - S * .10, S * .57)], TOP)
        poly([(cx - S * .10, S * .55), (cx + S * .10, S * .55), (cx + S * .095, S * .67), (cx - S * .095, S * .67)], BOT)   # sort
        for sg in (-1, 1):
            poly([(cx + sg * S * .014, S * .66), (cx + sg * S * .088, S * .66), (cx + sg * S * .07, S * .945), (cx + sg * S * .036, S * .945)], SKIN)
            poly([(cx + sg * S * .032, S * .86), (cx + sg * S * .072, S * .86), (cx + sg * S * .07, S * .945), (cx + sg * S * .036, S * .945)], ACC)   # corap
            poly([(cx + sg * S * .10, sh + 4), (cx + sg * S * .145, sh + S * .03), (cx + sg * S * .155, S * .38), (cx + sg * S * .118, S * .385)], TOP)  # kisa kol
            poly([(cx + sg * S * .118, S * .38), (cx + sg * S * .155, S * .38), (cx + sg * S * .175, S * .53), (cx + sg * S * .14, S * .545)], SKIN)   # kol (ten)
            ell((cx + sg * S * .06, S * .958), (S * .042, S * .018), 0, SHOE)
        ell((cx, hy), (head_r * 0.95, head_r), 0, SKIN)
        if kind == "cap":
            ell((cx, hy - head_r * .3), (head_r * 1.05, head_r * .78), 0, ACC, 180, 360)
            poly([(cx, hy - head_r * .36), (cx + head_r * 1.7, hy - head_r * .26), (cx + head_r * 1.6, hy - head_r * .05), (cx, hy - head_r * .1)], ACC)
        else:
            ell((cx, hy - head_r * .35), (head_r * 1.0, head_r * .70), 0, HAIR, 180, 360)
    else:  # girl / pony
        poly([(cx - S * .09, sh), (cx + S * .09, sh), (cx + S * .17, S * .67), (cx - S * .17, S * .67)], TOP)   # elbise
        for sg in (-1, 1):
            poly([(cx + sg * S * .03, S * .66), (cx + sg * S * .075, S * .66), (cx + sg * S * .07, S * .945), (cx + sg * S * .036, S * .945)], SKIN)
            poly([(cx + sg * S * .085, sh + 4), (cx + sg * S * .13, sh + S * .03), (cx + sg * S * .16, S * .51), (cx + sg * S * .125, S * .525)], SKIN)
            ell((cx + sg * S * .055, S * .958), (S * .036, S * .016), 0, SHOE)
        if kind == "pony":
            ell((cx + head_r * 1.15, hy + head_r * .35), (head_r * .45, head_r * 1.05), 20, HAIR)
            ell((cx, hy), (head_r * 0.95, head_r), 0, SKIN)
            ell((cx, hy - head_r * .35), (head_r * 1.02, head_r * .72), 0, HAIR, 180, 360)
        else:
            ell((cx, hy + head_r * .25), (head_r * 1.18, head_r * 1.08), 0, HAIR)
            ell((cx, hy + head_r * 0.1), (head_r * 0.82, head_r * 0.95), 0, SKIN)
            ell((cx, hy - head_r * .4), (head_r * 1.0, head_r * .6), 0, HAIR, 180, 360)
    # yumusak, organik siluet: maske = tum bolgeler; hafif bulaniklik + esik
    m = (lab > 0).astype(np.uint8) * 255
    m = cv2.GaussianBlur(m, (0, 0), S * 0.008)
    m = cv2.threshold(m, 110, 255, cv2.THRESH_BINARY)[1]
    m = cv2.GaussianBlur(m, (0, 0), 1.0)
    # etiketleri maskenin icine yay (bosluklar en yakin etiketle dolar)
    filled = lab.copy()
    holes = (m > 0) & (lab == 0)
    if holes.any():
        dil = lab.copy()
        for _ in range(12):
            dil = np.maximum(dil, cv2.dilate(dil, np.ones((3, 3), np.uint8)))
        filled[holes] = dil[holes]
    return m, filled


if __name__ == "__main__":
    out = {}
    for k in ("boy", "cap", "girl", "pony", "man", "woman"):
        m, l = make(k)
        out[k + "_m"], out[k + "_l"] = m, l
    here = os.path.dirname(os.path.abspath(__file__))
    np.savez_compressed(os.path.join(here, "figures.npz"), **out)
    pal = np.array([[0, 0, 0], [140, 170, 215], [40, 50, 70], [60, 110, 170], [120, 70, 50], [30, 30, 30], [40, 40, 140]], np.uint8)
    sheet = np.hstack([np.where(out[k + "_m"][..., None] > 0, pal[out[k + "_l"]], 255) for k in ("boy", "cap", "girl", "pony", "man", "woman")])
    cv2.imwrite(os.path.join(here, "figures_preview.png"), sheet)
