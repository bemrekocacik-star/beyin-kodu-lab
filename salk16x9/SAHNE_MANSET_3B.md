# Sahne: Manşet Çarpması 3B (`headline3d`)

**Anlatı amacı:** 12 Nisan 1955'te bütün ülkenin aynı haberi okuduğu anı fiziksel bir olay gibi hissettirmek. İzleyicinin gözü önce masaya, sonra düşen gazeteye, çarpışmaya ve sonunda okunabilir manşete yönlendirilir.

**Süre:** 5,5 sn (24 fps = 132 kare). Bütün değerler sahne içi zamandır (t = 0 sahnenin ilk karesi).

## 1. Dünya ve birimler
- Koordinat: X sağ, Y aşağı (masa yüzeyi Y = 0, yukarısı negatif), Z ileri. Birim yaklaşık 1 mm.
- Kamera: `Cam3` perspektif, odak uzaklığı f = 1150 (1920 px genişlikte yaklaşık 40° yatay görüş).

## 2. Nesneler
| Nesne | Tanım |
|---|---|
| Masa | 3200 × 3400 düzlem, koyu ceviz dokusu (prosedürel damar + ince gürültü), uzak kısım alan derinliğiyle bulanık |
| Gazete | 600 × 774 kâğıt, 8 × 10 hücreli ağ (mesh), yerel kıvrılma: köşeler yukarı, düşerken hava direnciyle kenarlar bükülür |
| Kâğıt kalınlığı | 7 birim; ön ve yan kenarlarda katman çizgileri (6 sayfa) görünür |
| Toz | 260 parçacık, temas anında kenarlardan doğar |
| Havadaki toz | 70 parçacık, ışık huzmesinde yavaş süzülür (atmosfer) |

## 3. Kare kare zaman çizelgesi
| t (sn) | Kare | Kamera | Gazete | Işık / parçacık | Ses |
|---|---|---|---|---|---|
| 0.00–0.50 | 0–12 | Konum (0, −1080, −1450), eğim 36°, yavaş ileri kayma | Kadraj dışında, yukarıda | Havadaki toz süzülür; anahtar ışık soldan masaya düşer | Oda tonu, düşük uğultu |
| 0.50–1.25 | 12–30 | İleri kaymaya devam, eğim 36°→40° | Y: −950→0, yerçekimi eğrisi (u²); dönme X 38°→0°, Z −20°→−4°; kıvrılma 70→18 | Gölge yükseklikle büyür ve yumuşar: σ = 6 + 0,05·h, yoğunluk 0,25→0,75 | Hava sesi (whoosh) yükselir |
| **1.25** | **30** | **Sarsıntı başlar:** 14 px genlik, 34 Hz, sönüm e^(−11·Δt); 0,5° dönme | **Temas.** 0,12 sn içinde 10 birim zıplama ve yerleşme | 260 toz parçacığı kenarlardan çıkar | **Kâğıt çarpması** (yüksek frekanslı kısa gürültü, 60 ms) + **tok vuruş** (55 Hz, 0,25 sn) + **bas vuruş** (40 Hz, 0,6 sn) |
| 1.25–1.70 | 30–41 | Sarsıntı söner | Temas gölgesi keskinleşir (σ = 3) | Toz: hız 300–900, yukarı 100–420, yerçekimi 900, sürtünme k = 2,6 | Vuruşun yankısı |
| 1.70–4.60 | 41–110 | Yerleşme: konum → (0, −1180, −560), eğim → 58°; manşet okunacak açı | Hareketsiz | Toz 1,2–2,0 sn içinde söner; alan derinliği odağı manşette | Sakin müzik, efekt yok |
| 2.10 | 50 | — | — | Alt yazı maskeli yükselişle girer | — |
| 4.60–5.50 | 110–132 | Çok yavaş ileri itme (%2) | — | Havadaki toz devam eder | Sonraki sahneye geçiş |

## 4. Işık değerleri
- **Anahtar ışık:** yön L = normalize(−0,50, −0,78, −0,36) (üst sol, kameraya doğru hafif).
- **Kâğıt gölgelendirme:** parlaklık = 0,34 + 0,66 · max(0, n·L); hafif sıcak ton (kâğıt rengi 0,93 / 0,95 / 0,97 BGR).
- **Kenar ışığı:** ışığa bakan kenarlarda +%18 parlaklık şeridi.
- **Masa yansıması:** ışığın yansıdığı noktada yumuşak bir parlama (genişlik 520 px); gazetenin aynalanmış görüntüsü %10 opaklık ve σ = 10 bulanıklıkla, sadece gazete masaya 120 birimden yakınken.
- **Gölge:** kâğıt köşeleri ışık yönünde masaya izdüşürülür; yumuşaklık ve yoğunluk yüksekliğe bağlıdır. Temas anında ek bir dar ortam gölgesi (AO) eklenir.

## 5. Parçacık fiziği (her karede kapalı formülle hesaplanır, render tekrarlanabilir)
- Doğum noktası: gazetenin kenarı üzerinde rastgele bir nokta.
- Başlangıç hızı: kenar normali yönünde 300–900 + yukarı 100–420.
- Konum: x(t) = x₀ + v₀·(1 − e^(−k·t))/k; y(t) = y₀ + vy₀·(1 − e^(−k·t))/k + ½·g·t² · e^(−0,8·t); y ≤ 0 (masaya oturur).
- Boyut 2–7 birim; görünürlük (1 − yaş/ömür)^1,5; ışığa göre sıcak gri renk.

## 6. Ses senkronu
Ses olayları sahne zamanına bağlıdır. Sahne zaman çizelgesinde kayarsa sesler de onunla birlikte kayar.
- `whoosh` @ 0,95 (0,6 sn)
- `paper` @ 1,25 (kâğıt çarpması + tok vuruş)
- `impact` @ 1,25 (bas, 40 Hz)

## 7. Performans hedefi
- 540p önizleme: kare başına ≤ 250 ms (bulut CPU).
- 1080p final: kare başına ≤ 700 ms. Ölçüm render raporuna yazılır.
