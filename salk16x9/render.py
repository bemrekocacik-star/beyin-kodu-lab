"""Beyin Kodu Lab 16:9 - tek komutla uretim hatti.
Kullanim (proje klasorunde):
  python <motor>/render.py [--onizleme | --4k] [--anlatim ses.wav] [--zorla]
Adimlar:
  1 render oncesi kalite kapisi (eksik medya, lisans, altyazi)  -> KALDI varsa durur (--zorla ile gecilir)
  2 muzik -> ses normalize (anlatim varsa: anlatim one, muzik ducking ile alta)
  3 goruntu (engine.py)
  4 YouTube teslim kodlamasi (H.264 High, Rec.709, AAC 384k 48 kHz, -14 LUFS / -1.5 dBTP, faststart, <= 400 MB hedefi)
  5 render sonrasi otomatik kalite kontrolu (qc.py) -> <video>.kalite.json / .kalite.md
"""
import os, sys, json, subprocess, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from engine import FFMPEG
import qc


def run(args):
    print(">", " ".join(str(a) for a in args[:6]), "...", flush=True)
    subprocess.run(args, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", default="timeline.json")
    ap.add_argument("--assets", default="assets.json")
    ap.add_argument("--onizleme", action="store_true", help="960x540 hizli onizleme")
    ap.add_argument("--4k", dest="k4", action="store_true", help="3840x2160 final")
    ap.add_argument("--anlatim", default="", help="anlatici sesi (wav/mp3); verilirse muzik altina ducking ile girer")
    ap.add_argument("--zorla", action="store_true", help="render oncesi KALDI sonucunu yok say")
    a = ap.parse_args()
    os.makedirs("renders", exist_ok=True)
    tl = json.load(open(a.timeline, encoding="utf-8"))
    name = tl.get("project", "video").replace(" ", "_").replace(":", "")
    tag = "540p_onizleme" if a.onizleme else ("2160p_4K" if a.k4 else "1080p")
    py = sys.executable

    # 1 render oncesi kapi
    R0 = qc.kontrol_once(a.timeline, a.assets if os.path.isfile(a.assets) else None)
    o0 = R0.yaz("renders/_render_oncesi")
    for x in R0.k:
        if x["durum"] != "GECTI":
            print(f"  [{x['durum']}] {x['kontrol']}: {x['ayrinti']}")
    if o0["KALDI"] and not a.zorla:
        print("RENDER DURDURULDU: render oncesi kalite kapisi KALDI (ayrinti renders/_render_oncesi.kalite.md)")
        sys.exit(1)

    # 2 ses
    run([py, os.path.join(HERE, "music.py"), a.timeline, "renders/_muzik_ham.wav"])
    if a.anlatim:
        # anlatim -16 LUFS'a, muzik -26 LUFS taban, anlatim konusurken ek ~8 dB alcalir (anlatimin ~18 dB altinda) (sidechain ducking), sonra toplam -14 LUFS
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", "renders/_muzik_ham.wav", "-i", a.anlatim,
             "-filter_complex",
             "[1:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-16:TP=-2:LRA=7,asplit[n][sc];"
             "[0:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-26:TP=-6:LRA=11[m];"
             "[m][sc]sidechaincompress=threshold=0.03:ratio=6:attack=80:release=450[md];"
             "[n][md]amix=inputs=2:normalize=0:duration=first[mix]",
             "-map", "[mix]", "-ar", "48000", "renders/_muzik.wav"])
    else:
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", "renders/_muzik_ham.wav",
             "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "48000", "renders/_muzik.wav"])

    # 3 goruntu
    run([py, os.path.join(HERE, "engine.py"), a.timeline, "renders/_goruntu.mp4",
         "--scale", "0.5" if a.onizleme else ("2.0" if a.k4 else "1.0"),
         "--crf", "22" if a.onizleme else "16"] + ([] if a.onizleme else ["--hq"]))

    # 4 teslim kodlamasi
    out = f"renders/{name}_{tag}.mp4"
    if a.onizleme:
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", "renders/_goruntu.mp4", "-i", "renders/_muzik.wav",
             "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out])
    else:
        fps = tl["fps"]; g = max(1, fps // 2)
        rate = ["-maxrate", "40M", "-bufsize", "80M"] if a.k4 else ["-maxrate", "8.6M", "-bufsize", "17M"]
        run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", "renders/_goruntu.mp4", "-i", "renders/_muzik.wav",
             "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", "18", *rate,
             "-profile:v", "high", "-pix_fmt", "yuv420p", "-bf", "2", "-g", str(g), "-keyint_min", str(g),
             "-sc_threshold", "0", "-flags", "+cgop",
             "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
             "-af", "loudnorm=I=-14:TP=-2:LRA=11", "-c:a", "aac", "-b:a", "384k", "-ar", "48000", "-ac", "2",
             "-shortest", "-movflags", "+faststart", out])

    # 5 render sonrasi kalite kontrolu
    R = qc.kontrol_sonra(out, a.timeline, a.assets if os.path.isfile(a.assets) else None)
    eq = "renders/_goruntu.mp4.qc.json"
    if os.path.isfile(eq):
        sv = json.load(open(eq, encoding="utf-8")).get("safe_violations", [])
        R.ekle("Güvenli alan (başlık/altyazı kenarda)", "UYARI" if sv else "GECTI", ", ".join(map(str, sv[:8])) or "taşma yok")
    o = R.yaz(out)
    print("\nBITTI:", out)
    for x in R.k:
        print(f"  [{x['durum']:5}] {x['kontrol']}: {x['ayrinti']}")
    print("OZET:", o, "| rapor:", out + ".kalite.md")
    sys.exit(1 if o["KALDI"] else 0)


if __name__ == "__main__":
    main()
