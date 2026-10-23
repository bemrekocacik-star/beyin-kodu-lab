"""Beyin Kodu Lab - otomatik kalite kontrol (render oncesi ve sonrasi).

Kullanim:
  python qc.py once  timeline.json [assets.json]          -> render oncesi: medya + lisans + altyazi kurallari
  python qc.py sonra video.mp4 [timeline.json] [assets.json] -> render sonrasi: teknik + ses + goruntu + tempo

Cikti: <video>.kalite.json ve .kalite.md. Her kontrol: GECTI / UYARI / KALDI.
KALDI varsa cikis kodu 1 (yayin oncesi duzeltilmeli). Editoryal karar (hikaye, tempo hissi) insana aittir;
bu modul yalnizca olculebilen seyleri olcer.

Esikler (kaynak):
- YouTube yukleme onerisi: H.264 High, 4:2:0, AAC-LC 48 kHz stereo (support.google.com/youtube/answer/1722171)
- Ses: YouTube oynatma normallestirmesi ~-14 LUFS; gercek tepe <= -1 dBTP (EBU R128 / ITU-R BS.1770)
- Video seviyeleri: 8 bit sinirli aralik Y 16-235 (ITU-R BT.709)
- Altyazi: en fazla 2 satir, satir <= 42 karakter, okuma hizi <= 17 karakter/sn, 5/6 sn - 7 sn sure
  (Netflix Timed Text Style Guide, Turkce: 17 kps)
"""
import os, sys, re, json, subprocess, shutil

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from engine import FFMPEG as _F
    FFMPEG = _F
    d, b = os.path.split(_F)
    FFPROBE = os.path.join(d, b.replace("ffmpeg", "ffprobe")) if d else "ffprobe"
except Exception:
    pass

ESIK = {"lufs_hedef": -14.0, "lufs_tolerans": 1.5, "tepe_dbtp": -1.0, "av_fark_sn": 0.10,
        "siyah_min_sn": 0.25, "donma_sn": 2.0, "sessizlik_sn": 1.5, "en_uzun_cekim_sn": 15.0,
        "kps": 17.0, "satir_karakter": 42, "alt_min_sn": 0.83, "alt_max_sn": 7.0,
        "y_alt": 16, "y_ust": 235, "seviye_tasma_orani": 0.02}


class Rapor:
    def __init__(self):
        self.k = []

    def ekle(self, ad, durum, ayrinti=""):
        self.k.append({"kontrol": ad, "durum": durum, "ayrinti": ayrinti})

    def ozet(self):
        c = {s: sum(1 for x in self.k if x["durum"] == s) for s in ("GECTI", "UYARI", "KALDI")}
        return c

    def yaz(self, yol):
        o = self.ozet()
        json.dump({"ozet": o, "kontroller": self.k, "esikler": ESIK}, open(yol + ".kalite.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        ik = {"GECTI": "✅", "UYARI": "⚠️", "KALDI": "❌"}
        md = [f"# Kalite raporu — {os.path.basename(yol)}", "", f"Geçti {o['GECTI']} · Uyarı {o['UYARI']} · Kaldı {o['KALDI']}", "",
              "| | Kontrol | Ayrıntı |", "|---|---|---|"]
        md += [f"| {ik[x['durum']]} | {x['kontrol']} | {x['ayrinti']} |" for x in self.k]
        open(yol + ".kalite.md", "w", encoding="utf-8").write("\n".join(md))
        return o


def _ff(args):
    r = subprocess.run([FFMPEG, "-hide_banner", "-nostats"] + args, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return r.stderr


# ---------------- render oncesi ----------------
def kontrol_once(tl_yol, assets_yol=None, R=None):
    R = R or Rapor()
    tl = json.load(open(tl_yol, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(tl_yol))
    eksik, kullanilan = [], set()
    for s in tl["scenes"]:
        for a in s.get("visualAssets") or []:
            kullanilan.add(a)
            if not os.path.isfile(os.path.join(base, a)):
                eksik.append(f"{s['id']}: {a}")
    R.ekle("Eksik medya dosyası", "KALDI" if eksik else "GECTI", "; ".join(eksik[:6]) or f"{len(kullanilan)} görsel bulundu")
    # lisans kapisi
    if assets_yol and os.path.isfile(assets_yol):
        reg = json.load(open(assets_yol, encoding="utf-8"))
        izin = set(reg.get("izinli_lisanslar", []))
        V = reg["varliklar"]
        kayitsiz = [a for a in kullanilan if a not in V]
        uygunsuz = [f"{a} ({V[a]['lisans']})" for a in kullanilan if a in V and V[a]["lisans"] not in izin]
        atif = sorted({V[a]["atif"] for a in kullanilan if a in V and V[a].get("atif")})
        dogrulanmamis = [a for a in kullanilan if a in V and not V[a].get("adres_dogrulandi", True)]
        R.ekle("Lisans kaydı (her görsel assets.json'da)", "KALDI" if kayitsiz else "GECTI", "; ".join(kayitsiz) or "tümü kayıtlı")
        R.ekle("Lisans uygunluğu (ticari kullanım)", "KALDI" if uygunsuz else "GECTI", "; ".join(uygunsuz) or "tümü izinli")
        R.ekle("Atıf gereken görseller", "UYARI" if atif else "GECTI", (" | ".join(atif) + " → açıklamaya yaz") if atif else "yok")
        R.ekle("Kaynak adresi doğrulanmamış", "UYARI" if dogrulanmamis else "GECTI", ", ".join(x.split('/')[-1] for x in dogrulanmamis) or "yok")
    else:
        R.ekle("Lisans kaydı", "UYARI", "assets.json bulunamadı")
    # altyazi kurallari
    subs = tl.get("subtitles", [])
    sorun = []
    for i, (a, b, t) in enumerate(subs):
        ln = t.split("\n"); d = b - a
        chars = len(t.replace("\n", ""))
        if len(ln) > 2: sorun.append(f"#{i + 1} {len(ln)} satır")
        if max(len(x) for x in ln) > ESIK["satir_karakter"]: sorun.append(f"#{i + 1} satır {max(len(x) for x in ln)} karakter")
        if d < ESIK["alt_min_sn"]: sorun.append(f"#{i + 1} {d:.2f} sn (kısa)")
        if d > ESIK["alt_max_sn"]: sorun.append(f"#{i + 1} {d:.1f} sn (uzun)")
        if d > 0 and chars / d > ESIK["kps"]: sorun.append(f"#{i + 1} okuma hızı {chars / d:.1f} kps")
    R.ekle("Altyazı kuralları (2 satır, 42 kar., 17 kps, 0.83-7 sn)", "UYARI" if sorun else "GECTI",
           f"{len(sorun)} sorun: " + "; ".join(sorun[:8]) if sorun else f"{len(subs)} altyazı uygun")
    zam = tl.get("timingSource", "")
    R.ekle("Zamanlama kaynağı", "UYARI" if "TAHMİN" in zam else "GECTI", zam)
    return R


# ---------------- render sonrasi ----------------
def kontrol_sonra(video, tl_yol=None, assets_yol=None):
    R = Rapor()
    if not os.path.isfile(video) or os.path.getsize(video) < 1000:
        R.ekle("Dosya var", "KALDI", video); return R
    pr = subprocess.run([FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", video], capture_output=True, text=True)
    try:
        info = json.loads(pr.stdout)
    except Exception:
        R.ekle("Dosya bütünlüğü (ffprobe)", "KALDI", pr.stderr[:200]); return R
    vs = [s for s in info["streams"] if s["codec_type"] == "video"]; as_ = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if not vs or not as_:
        R.ekle("Görüntü + ses akışı", "KALDI", f"video {len(vs)}, ses {len(as_)}"); return R
    v, a = vs[0], as_[0]
    R.ekle("Dosya bütünlüğü (ffprobe)", "GECTI", f"{os.path.getsize(video) / 1e6:.0f} MB, {float(info['format']['duration']):.2f} sn")
    fps = eval(v["r_frame_rate"])
    ok = v["codec_name"] == "h264" and v.get("profile") in ("High", "Main") and v.get("pix_fmt") == "yuv420p"
    R.ekle("Video kodek (H.264 High, 4:2:0)", "GECTI" if ok else "UYARI", f"{v['codec_name']} {v.get('profile')} {v.get('pix_fmt')}")
    R.ekle("Çözünürlük / kare hızı", "GECTI" if (int(v["height"]) >= 1080 and fps in (24, 25, 30)) else "UYARI", f"{v['width']}x{v['height']} @ {fps:g} fps")
    R.ekle("Renk alanı (Rec.709)", "GECTI" if v.get("color_space", "bt709") in ("bt709",) else "UYARI", v.get("color_space", "belirtilmemiş"))
    aok = a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000 and int(a["channels"]) == 2
    R.ekle("Ses kodek (AAC 48 kHz stereo)", "GECTI" if aok else "UYARI", f"{a['codec_name']} {a['sample_rate']} Hz {a['channels']} kanal")
    vd, ad = float(v.get("duration", 0)), float(a.get("duration", 0))
    R.ekle("Ses-görüntü süre farkı (senkron)", "GECTI" if abs(vd - ad) <= ESIK["av_fark_sn"] else "KALDI", f"{abs(vd - ad):.3f} sn")
    if tl_yol and os.path.isfile(tl_yol):
        tl = json.load(open(tl_yol, encoding="utf-8"))
        tot = tl["scenes"][-1]["end"]
        R.ekle("Süre zaman çizelgesiyle uyumlu", "GECTI" if abs(vd - tot) < 0.2 else "KALDI", f"video {vd:.2f} / plan {tot:.2f} sn")
    # tam kod cozumu: bozuk paket / kare hatasi
    err = subprocess.run([FFMPEG, "-v", "error", "-i", video, "-f", "null", "-"], capture_output=True, text=True).stderr.strip()
    R.ekle("Baştan sona kod çözme hatası", "KALDI" if err else "GECTI", err[:160] or "hatasız")
    # goruntu: siyah, donma, seviye, tempo (tek gecis)
    s = _ff(["-i", video, "-an", "-vf",
             f"blackdetect=d={ESIK['siyah_min_sn']}:pix_th=0.06,freezedetect=n=0.001:d={ESIK['donma_sn']},"
             "select='not(mod(n\\,12))',signalstats=stat=brng,metadata=mode=print:key=lavfi.signalstats.BRNG",
             "-f", "null", "-"])
    blacks = [(float(x), float(y)) for x, y in re.findall(r"black_start:(\S+) black_end:(\S+)", s)]
    blacks = [b for b in blacks if b[0] > 0.5 and b[1] < vd - 0.8]   # bastaki/sondaki bilincli kararmalar haric
    R.ekle("Gereksiz siyah ekran", "KALDI" if blacks else "GECTI", ", ".join(f"{x:.1f}-{y:.1f} sn" for x, y in blacks) or "yok")
    fr = re.findall(r"freeze_start: (\S+)", s)
    R.ekle(f"Donmuş görüntü (>{ESIK['donma_sn']:g} sn)", "UYARI" if fr else "GECTI", ", ".join(f"{float(x):.1f} sn" for x in fr[:8]) or "yok")
    br = [float(x) for x in re.findall(r"BRNG=(\d+\.?\d*)", s)]
    if br:
        # BRNG: karede yayin araligi (Y 16-235 / C 16-240) disina tasan piksel orani; x264 kenar sapmalari ~%1-3 normaldir
        ort, mx = sum(br) / len(br), max(br)
        R.ekle("Video seviyeleri (yayın aralığı dışı piksel)", "UYARI" if (ort > 0.01 or mx > 0.05) else "GECTI",
               f"ortalama %{100 * ort:.2f}, en kötü kare %{100 * mx:.1f} ({len(br)} örnek kare)")
    sc = _ff(["-i", video, "-an", "-vf", "scdet=threshold=8,metadata=mode=print:key=lavfi.scd.time", "-f", "null", "-"])
    cuts = [0.0] + [float(x) for x in re.findall(r"lavfi\.scd\.time=(\S+)", sc)] + [vd]
    shots = [b - a for a, b in zip(cuts, cuts[1:]) if b > a]
    if shots:
        en = max(shots); i = shots.index(en)
        R.ekle("Tempo: görsel değişim aralığı", "UYARI" if en > ESIK["en_uzun_cekim_sn"] else "GECTI",
               f"ortalama {sum(shots) / len(shots):.1f} sn · en uzun {en:.1f} sn ({cuts[i]:.0f}. saniyede) · {len(shots)} kesme")
    if tl_yol and os.path.isfile(tl_yol):
        sc_ = [x for x in json.load(open(tl_yol, encoding="utf-8"))["scenes"] if x["type"] != "end_screen"]
        uz = max(sc_, key=lambda x: x["end"] - x["start"])
        R.ekle("Tempo: planlı sahne süresi", "UYARI" if uz["end"] - uz["start"] > 12 else "GECTI",
               f"ortalama {sum(x['end'] - x['start'] for x in sc_) / len(sc_):.1f} sn · en uzun {uz['end'] - uz['start']:.1f} sn ({uz['id']})")
    # ses: loudness, gercek tepe, kirpilma, faz, sessizlik
    e = _ff(["-i", video, "-vn", "-af", "ebur128=peak=true,aphasemeter=video=0,ametadata=mode=print:key=lavfi.aphasemeter.phase", "-f", "null", "-"])
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", e); LRA = re.findall(r"LRA:\s+([\d.]+) LU", e); TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)
    if I:
        i_ = float(I[-1])
        R.ekle("Entegre ses yüksekliği (YouTube ~-14 LUFS)", "GECTI" if abs(i_ - ESIK["lufs_hedef"]) <= ESIK["lufs_tolerans"] else "UYARI", f"{i_:.1f} LUFS, LRA {LRA[-1] if LRA else '?'} LU")
    if TP:
        tp = float(TP[-1])
        R.ekle("Gerçek tepe (≤ -1 dBTP)", "GECTI" if tp <= ESIK["tepe_dbtp"] + 0.05 else "UYARI", f"{tp:.1f} dBTP")
    ph = [float(x) for x in re.findall(r"lavfi\.aphasemeter\.phase=(-?[\d.]+)", e)]
    if ph:
        mph = sum(ph) / len(ph)
        R.ekle("Faz uyumu (mono uyumluluk)", "GECTI" if mph > 0.2 else "UYARI", f"ortalama faz {mph:+.2f} (+1 tam uyum, -1 ters faz)")
    sl = _ff(["-i", video, "-vn", "-af", f"silencedetect=n=-50dB:d={ESIK['sessizlik_sn']}", "-f", "null", "-"])
    sil = [float(x) for x in re.findall(r"silence_start: (\S+)", sl)]
    sil = [x for x in sil if x > 0.5 and x < vd - 1.0]
    R.ekle(f"Beklenmeyen sessizlik (>{ESIK['sessizlik_sn']:g} sn)", "UYARI" if sil else "GECTI", ", ".join(f"{x:.1f} sn" for x in sil[:8]) or "yok")
    if tl_yol:
        kontrol_once(tl_yol, assets_yol, R)
    return R


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("once", "sonra"):
        print(__doc__); sys.exit(2)
    if sys.argv[1] == "once":
        R = kontrol_once(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        hedef = os.path.splitext(sys.argv[2])[0]
    else:
        R = kontrol_sonra(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None, sys.argv[4] if len(sys.argv) > 4 else None)
        hedef = sys.argv[2]
    o = R.yaz(hedef)
    for x in R.k:
        print(f"[{x['durum']:5}] {x['kontrol']}: {x['ayrinti']}")
    print("OZET:", o)
    sys.exit(1 if o["KALDI"] else 0)
