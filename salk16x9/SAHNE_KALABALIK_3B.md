# Sahne: Kalabalık 3B (`crowd3d_cine`)

**Anlatı amacı:** 1954 saha deneyine katılan 1.829.916 çocuğun büyüklüğünü sayı olarak değil, manzara olarak hissettirmek. İzleyici önce bir çocuğun göz hizasından tek tek figürleri görür, sonra kamera yükseldikçe kalabalığın ufka kadar uzandığını fark eder.

**Süre:** 5,0 sn (24 fps = 120 kare). Bütün zamanlar sahne içi zamandır.

## 1. Dünya
- Zemin Y = 0, yukarısı negatif. Figürler 64 sütun × 46 sıra (2.944 adet), X ∈ [−1500, 1500], Z ∈ [350, 5200], hafif rastgele kayma ve boy farkı (0,75–1,15).
- Güneş: ufukta, ekranda yaklaşık (1180, 300) noktası. Işık yönü kameraya doğru, yani figürler arkadan aydınlanıyor.

## 2. Kare kare zaman çizelgesi
| t (sn) | Kare | Kamera | Figürler / ışık | Ses |
|---|---|---|---|---|
| 0.00–0.60 | 0–14 | Göz hizası: konum (−120, −95, −40), eğim −2° (hafif yukarı), sapma 4° | Ön sıralar silüet, kenar ışığı belirgin; ufukta güneş parlaması | Uzak kalabalık mırıltısı açılır |
| 0.60–3.40 | 14–82 | Vinç yükselişi: Y −95 → −760, Z −40 → −420, eğim −2° → 17°, sapma 4° → −3° | Aşı dalgası önden arkaya ilerler: figürler griden sarıya döner, sarı parıltı | Dalga ilerledikçe 4 ince çan (0.9 / 1.6 / 2.3 / 3.0); 1,0'dan 3,4'e yükselen müzik dalgası |
| 3.40–5.00 | 82–120 | Çok yavaş ileri itme (Z −420 → −360) | Dalga ufka ulaşır; sayaç 1.829.916'da durur; uzun gölgeler sabit | Akor açılır, mırıltı alçalır |

## 3. Işık
- **Arka ışık (güneş):** sıcak (BGR 0,55 / 0,78 / 1,0). Figürün üst ve yan kenarında 1–2 piksellik parlak hat (kenar ışığı).
- **Dolgu:** figür gövdesi koyu ama tamamen siyah değil (0,22–0,30).
- **Gölge:** her figürün kameraya doğru uzanan, 3,2 kat uzunluğunda yumuşak elips gölgesi.
- **Hava perspektifi (sis):** derinlikle artar; renk ufuk ışığına karışır: sis = clip(z / 5600).
- **Işık huzmeleri:** güneşten yayılan 5 hafif ışın; yoğunluk ≤ 0,05.

## 4. Aşı dalgası
- Her figürün yanma zamanı: t_yan = 0,7 + 2,6 · (sıra / 46) + rastgele(0 – 0,25).
- Yanma geçişi 0,25 sn: gri → sıcak sarı; kısa parlama tepe noktası (×1,35).
- Sayaç: yanmış figür oranı × 1.829.916. Sayaç bu sayede dalgayla birebir eşleşir.

## 5. Ses senkronu
- `crowd` @ 0 (5 sn, uzak mırıltı: bant geçiren gürültü + yavaş genlik dalgalanması)
- `bell` @ 0,9 / 1,6 / 2,3 / 3,0 (çok hafif)
- `riser` biter @ 3,4 (müzik dalgası)

## 6. Performans hedefi
1080p'de kare başına ≤ 500 ms (bulut CPU).
