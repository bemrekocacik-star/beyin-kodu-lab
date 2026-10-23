"""Beyin Kodu Lab motor testleri (unittest; pytest gerekmez).
Calistir: cd salk16x9 && python -m unittest discover -s tests -v
PROJE ortam degiskeni proje klasorunu verir (varsayilan ../salk55)."""
import os, sys, json, subprocess, tempfile, unittest, shutil
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJE = os.environ.get("PROJE", os.path.join(os.path.dirname(KOK), "salk55"))
sys.path.insert(0, KOK)
import qc  # noqa: E402

TL = os.path.join(PROJE, "timeline.json")


class AltyaziBolme(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, PROJE)
        import plan_salk
        self.split = plan_salk.split_cues

    def kelimeler(self, metin, hiz=0.32):
        return [[i, i * hiz, i * hiz + hiz * 0.9, w] for i, w in enumerate(metin.split())]

    def test_kelime_kaybolmaz_ve_kurallar(self):
        m = ("Bu cok uzun bir cumle ve altyazi bolucu hicbir kelimeyi kaybetmemeli, iki satiri asmamali, "
             "her satir kirk iki karakteri gecmemeli ve en sonda kisa bir yetim kelime birakmamali. Bitti.")
        c = self.split(self.kelimeler(m))
        self.assertEqual(" ".join(x[2].replace("\n", " ") for x in c).split(), m.split())
        for a, b, t in c:
            self.assertLessEqual(len(t.split("\n")), 2)
            self.assertTrue(all(len(l) <= 42 for l in t.split("\n")))
            self.assertGreaterEqual(round(b - a, 3), 0.5)
        for x, y in zip(c, c[1:]):
            self.assertLessEqual(x[1], y[0])


@unittest.skipUnless(os.path.isfile(TL), "timeline.json yok")
class ZamanCizelgesi(unittest.TestCase):
    def test_dogrulama_hatasiz(self):
        import engine
        tl = json.load(open(TL, encoding="utf-8"))
        cwd = os.getcwd(); os.chdir(PROJE)
        try:
            errs, _ = engine.validate(tl)
        finally:
            os.chdir(cwd)
        self.assertEqual(errs, [])

    def test_sahne_tipleri_tanimli_ve_sureler_artan(self):
        import engine
        tl = json.load(open(TL, encoding="utf-8"))
        for s in tl["scenes"]:
            t = engine.SCENE_ALIASES.get(s["type"], s["type"])
            self.assertIn(t, engine.SCENES, s["id"])
            self.assertGreater(s["end"], s["start"], s["id"])

    def test_render_oncesi_qc_kalmaz(self):
        R = qc.kontrol_once(TL, os.path.join(PROJE, "assets.json"))
        kal = [x for x in R.k if x["durum"] == "KALDI"]
        self.assertEqual(kal, [], kal)


@unittest.skipUnless(os.path.isfile(TL) and os.environ.get("HIZLI") != "1", "duman testi atlandi")
class SahneDumanTesti(unittest.TestCase):
    """Her sahne turunden bir kareyi 0.25 olcekte cizer: cokme, NaN ve bos kare yakalar."""
    def test_her_sahne_turu_cizilir(self):
        tl = json.load(open(TL, encoding="utf-8"))
        ilk = {}
        for s in tl["scenes"]:
            ilk.setdefault(s["type"], s)
        ts = ",".join(f"{(s['start'] + s['end']) / 2:.2f}" for s in ilk.values())
        d = tempfile.mkdtemp()
        r = subprocess.run([sys.executable, os.path.join(KOK, "engine.py"), "timeline.json", os.path.join(d, "k"),
                            "--scale", "0.25", "--stills", ts], cwd=PROJE, capture_output=True, text=True, timeout=1800)
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-800:])
        import cv2, numpy as np
        kareler = sorted(os.listdir(d))
        self.assertEqual(len(kareler), len(ilk))
        for f in kareler:
            im = cv2.imread(os.path.join(d, f))
            self.assertIsNotNone(im, f)
            self.assertGreater(float(im.std()), 3.0, f"{f}: kare neredeyse duz renk")
        shutil.rmtree(d)


class KaliteKontrolSentetik(unittest.TestCase):
    """qc.py'nin hatayi gercekten yakaladigini sentetik kliplerle dogrular."""
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp()
        ff = qc.FFMPEG
        def mk(ad, vf, af, extra=()):
            yol = os.path.join(cls.d, ad)
            subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", vf, "-f", "lavfi", "-i", af, *extra,
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-colorspace", "bt709",
                            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", yol], check=True)
            return yol
        cls.iyi = mk("iyi.mp4", "testsrc2=s=1920x1080:r=24:d=6", "sine=f=440:d=6,volume=-17dB,aformat=channel_layouts=stereo")
        cls.siyah = mk("siyah.mp4", "testsrc2=s=1920x1080:r=24:d=6,drawbox=c=black:t=fill:enable='between(t,2,3)'",
                       "sine=f=440:d=6,aformat=channel_layouts=stereo")
        cls.kayik2 = os.path.join(cls.d, "kayik2.mp4")
        subprocess.run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=24:d=6",
                        "-f", "lavfi", "-i", "sine=f=440:d=4", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        "-ar", "48000", "-ac", "2", cls.kayik2], check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d)

    def durum(self, R, ad):
        return next(x["durum"] for x in R.k if x["kontrol"].startswith(ad))

    def test_temiz_klip(self):
        R = qc.kontrol_sonra(self.iyi)
        self.assertEqual(self.durum(R, "Gereksiz siyah"), "GECTI")
        self.assertEqual(self.durum(R, "Ses-görüntü"), "GECTI")
        self.assertEqual(self.durum(R, "Baştan sona"), "GECTI")

    def test_siyah_ekran_yakalanir(self):
        self.assertEqual(self.durum(qc.kontrol_sonra(self.siyah), "Gereksiz siyah"), "KALDI")

    def test_senkron_kaymasi_yakalanir(self):
        self.assertEqual(self.durum(qc.kontrol_sonra(self.kayik2), "Ses-görüntü"), "KALDI")

    def test_yuksek_ses_uyarir(self):
        self.assertEqual(self.durum(qc.kontrol_sonra(self.siyah), "Entegre"), "UYARI")


if __name__ == "__main__":
    unittest.main(verbosity=2)
