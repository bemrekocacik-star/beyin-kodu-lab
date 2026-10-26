# Beyin Kodu Lab 9:16 bulut motoru v7 (Fleming, Kod #9 — 26 Ekim 2026)

Kullanıcı: "izlediğim en harika içeriklerden biri". Bu klasör o videonun tam hattıdır.

| Dosya | Görev |
|---|---|
| `align3.py` | Hizalama + SENKRON KAPISI (sessizlik parçaları + hece çekirdeği + noktalama DP). Çıkış 1 = render yok |
| `engine9.py` | Çekirdek: kart, rozet, yazı, ikon, damga, cam panel, arka plan (cv2 + PIL) |
| `icons.py` | 14 SVG ikon → `ic/*.png` (Playwright) |
| `caption_styles.py` | ASS altyazı; düşürülen kelime (`i`) ve sahne (`sc`) sınırında böler |
| `gen_audio.py` | Telifsiz müzik/efekt + ileri bakışlı kısma (olay zamanlarını projeye göre düzenle) |
| `mix.sh` + `measure.py` | Miks (müzik ~0.02) ve konuşma/arka plan ölçümü |
| `render.py` / `snap.py` | Parça render (2 süreç) / sahne son kare kontrol sayfası |
| `ornek_proje_fleming/` | plan_fleming.py (14 sahne şablonu), metin, kelimeler, kaynaklar, görseller |

## Sıra
```bash
python3 align3.py ses.mp3 metin.txt kelimeler.json --spoken '{"Fleming":"fleming"}' --debug   # GEÇTİ ✓ şart
python3 icons.py
python3 snap.py qc_sahne.jpg          # her sahnenin son karesi
python3 render.py 0 930 p1.mp4 & python3 render.py 930 N p2.mp4 & wait
python3 gen_audio.py && bash mix.sh ses.mp3 muzik.wav 0.02 && python3 measure.py
ffmpeg -f concat -i l.txt -i final_audio.wav -vf ass=alt.ass -crf 22 -preset slow ... final.mp4
```
