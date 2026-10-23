# Beyin Kodu Lab — 16:9 sinematik belgesel motoru

Haftalık YouTube belgeselleri (5–6 dk, 1920×1080, 24 fps) için Python + OpenCV + FFmpeg üretim hattı.

| Klasör | İçerik |
|---|---|
| `salk16x9/` | Motor: `engine.py` (41+ sahne türü), `render.py` (tek komut hattı), `qc.py` (otomatik kalite kontrol), `music.py`, `figures.npz`, `tests/`, `araclar/` |
| `salk55/` | Proje: *Güneşin Patenti — Jonas Salk*. `plan_salk.py` → `timeline.json`, `senaryo_v2.txt`, `assets.json` (lisans kaydı), `sources.md`, `gorsel_plan.md`, `src/` |

## Kullanım

```bash
cd salk55
python plan_salk.py                          # senaryo -> timeline.json (ses yoksa tahmini zamanlama)
python ../salk16x9/araclar/hikaye_gorsel_denetim.py timeline.json gorsel_plan.md   # editoryal denetim
python ../salk16x9/qc.py once timeline.json assets.json                               # render öncesi kapı
python ../salk16x9/render.py --onizleme                     # 540p hızlı önizleme
python ../salk16x9/render.py --anlatim anlatim.wav          # 1080p final + YouTube kodlaması + render sonrası QC
```

## Kalite kapıları

1. **Render öncesi** (`qc.py once`): eksik medya, her görselin `assets.json` kaydı, ticari kullanıma uygun lisans, atıf gereği, doğrulanmamış kaynak adresi, altyazı kuralları (2 satır, 42 karakter, 17 kar./sn, 0.83–7 sn). KALDI → render başlamaz.
2. **Render sonrası** (`qc.py sonra`): ffprobe bütünlüğü, H.264 High/4:2:0/Rec.709, AAC 48 kHz stereo, ses-görüntü süre farkı ≤ 0.1 sn, baştan sona kod çözme, siyah ekran, donma, yayın aralığı dışı piksel (BRNG), tempo (sahne kesmeleri + planlı süreler), entegre ses -14 LUFS ±1.5, gerçek tepe ≤ -1 dBTP, faz uyumu, beklenmeyen sessizlik, güvenli alan.
3. **Editoryal** (insan + `hikaye_gorsel_denetim.py`): kanca, merak döngüleri, monotonluk, görsel tekrar, uzun kalışlar.

Otomatik kontrol ile editoryal kontrol birbirinin yerini tutmaz.

## Testler

```bash
cd salk16x9 && python -m unittest discover -s tests -v      # HIZLI=1 ile sahne duman testi atlanır
```

## Görsel lisans kuralı

Yalnızca Public domain, CC0, "No known restrictions", CC BY (atıflı) ve kanala ait üretimler. Her görsel `assets.json`'a kaynak adresi, lisans, atıf ve indirme tarihiyle girilir; kayıtsız görsel render'ı durdurur.
