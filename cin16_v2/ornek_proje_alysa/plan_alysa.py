"""Alysa Liu 16:9 — sahne planı (her cümle bir görsele bağlı)."""
import json
TL = json.load(open('tl.json')); SENT = TL['sent']; INS = {i['name']: i for i in TL['inserts']}
CR = {c['dosya']: c for c in json.load(open('foto/kaynaklar.json'))}
def S(k, off=-0.15): return SENT[k]['s'] + off
def F(n): return f'foto/al_{n:03d}.jpg'
def credit(n):
    c = CR[f'al_{n:03d}.jpg']; return f"Foto: {c['yazar']} · {c['lisans']} · Wikimedia Commons"
def ph(n, mode=None, **kw):
    b = {'k': 'photo', 'photo': F(n), 'credit': credit(n)}; b.update(kw)
    if mode: b['mode'] = mode
    return b
BG = {'k': 'bg'}
LCR = {c['dosya']: c for c in json.load(open('loc/loc_kaynaklar.json'))}
def LP(name, temsili=False, **kw):
    c = LCR[f'loc_{name}.jpg']; b = {'k': 'photo', 'photo': f'loc/loc_{name}.jpg', 'mode': 'cover', 'z0': 1.12, 'z1': 1.0, 'grad': 0.42,
         'credit': ('Temsili görüntü · ' if temsili else '') + f"Foto: {c['yazar']} · {c['lisans']} · Wikimedia Commons"}; b.update(kw); return b
def L2(city, date, at=0.2, size=104): return {'k': 'loc2', 'city': city, 'date': date, 'at': at, 'size': size}
def tx(t, y=540, size=72, col='w', at=0, **kw):
    d = {'k': 'text', 't': t, 'y': y, 'size': size, 'col': col, 'at': at}; d.update(kw)
    if d.get('x', 960) != 960 and 'maxw' not in d: d['maxw'] = 820
    return d
def low(title, sub=None, at=0.2): return {'k': 'lower', 'title': title, 'sub': sub, 'at': at}
def W_(k, word, off=0.0):
    """k. cümlede 'word' kelimesinin final zamanı (sahne başına göre değil, mutlak)."""
    words = json.load(open('kelimeler_final.json'))
    acc = 0; s = SENT[k]['s']
    for w in words:
        if w['s'] >= s - 0.01 and w['w'].lower().startswith(word.lower()): return w['s'] + off
    return s
Q = []  # (başlangıç, sahne)
def add(t, base, els=(), **kw): d = {'start': round(t, 3), 'base': base, 'els': list(els)}; d.update(kw); Q.append(d)
def rel(abs_t, start): return round(abs_t - start, 3)

# ---------------- KANCA ----------------
add(0.0, ph(98, z0=1.06, z1=1.0, focus=[0.45, 0.5], tone='cold', grad=0.55), [tx('2022 · DÜNYA ŞAMPİYONASI', 150, 40, 'y', 0.0, x=960), tx('16 YAŞINDA', 940, 64, 'w', 2.6)])
t = S(2); add(t, ph(36, z0=1.0, z1=1.12, tone='dim', dark=0.85), [tx('BIRAKIYORUM.', 540, 170, 'w', rel(W_(3, 'Bırakıyorum'), t), stroke=0)])
t = S(4); add(t, ph(89, z0=1.0, z1=1.07, px=0.32), [tx('TARİHİN EN GENÇ', 400, 64, 'w', 0.2, x=1400), tx('ABD ŞAMPİYONU', 490, 90, 'y', 0.5, x=1400)])
t = S(5); add(t, ph(97, z0=1.08, z1=1.0, px=0.68), [tx('OLİMPİYATLAR', 470, 90, 'w', 0.2, x=620)])
t = S(7); add(t, ph(100, tone='bw', z0=1.0, z1=1.1, px=0.5, dark=0.75), [tx('…VE KAPIYI KAPATTI', 960, 64, 'w', 0.8)])
t = S(8); add(t, ph(115, mode='cover', z0=1.0, z1=1.1, focus=[0.45, 0.4]), [tx('4 YIL SONRA', 140, 54, 'y', 0.1), tx('2 OLİMPİYAT ALTINI', 950, 96, 'w', rel(W_(8, 'iki'), t))])
t = S(9); add(t, BG, [{'k': 'counter', 'to': 24, 'suffix': ' YIL', 'size': 260, 'col': 'y', 'y': 470, 'at': 0.2, 'dur': 1.8}, tx('ABD\'li bir kadının beklediği altın', 690, 54, 'w', 0.8)])
t = S(10); add(t, ph(27, z0=1.0, z1=1.12, focus=[0.5, 0.35], px=0.7), [tx('Neden bıraktı?', 400, 80, 'w', 0.1, x=620), tx('Neden geri döndü?', 520, 80, 'y', rel(S(12, 0), t), x=620)])
t = S(13); add(t, ph(21, mode='fit', px=0.7, z0=1.0, z1=1.06), [low('ALYSA LIU', 'Artistik patinajcı · ABD', 0.2), tx('Asıl kazandığı şey', 520, 64, 'w', rel(S(14, 0), t) + 0.6, x=600), tx('madalya değildi.', 610, 76, 'y', rel(S(14, 0), t) + 1.8, x=600)])
# başlık + bölüm 1
i = INS['baslik']; add(i['start'], ph(24, mode='cover', z0=1.12, z1=1.02, focus=[0.5, 0.4], dark=0.6), [tx('ALYSA LIU', 430, 150, 'w', 0.3), tx('16 Yaşında Bıraktı… Sonra 2. Olimpiyat Altını', 560, 54, 'y', 0.9), {'k': 'bar', 'x': 960, 'y': 490, 'w': 700, 'at': 0.6}])
i = INS['1']; add(i['start'], {'k': 'chapter', 'n': 1, 'title': 'DAHİ ÇOCUK'})
# ---------------- BÖLÜM 1 ----------------
t = S(15); add(t, LP('clovis'), [L2('CLOVIS, KALİFORNİYA', '2005 · HİKÂYENİN BAŞLADIĞI YER')])
t = S(16); add(t, ph(0, px=0.65, z0=1.0, z1=1.08), [tx('5 YAŞINDA', 470, 110, 'y', rel(W_(16, 'beş'), t), x=560), tx('ilk kez buzda', 580, 56, 'w', rel(W_(16, 'beş'), t) + 0.4, x=560)])
t = S(18); add(t, BG, [tx('ÇOK KÜÇÜK YAŞTA', 220, 60, 'y', 0.1), {'k': 'checklist', 'items': ['SABAH · BUZ', 'ÖĞLEN · DERS', 'AKŞAM · BUZ'], 'mark': '•', 'mcol': 'y', 'x': 720, 'y': 380, 'at': rel(S(19, 0), t), 'gap': 0.75}])
t = S(20); add(t, ph(2, px=0.35, z0=1.06, z1=1.0), [tx('OKUL YOK', 430, 96, 'w', 0.2, x=1380), tx('eğitim hep evde', 530, 56, 'y', 0.6, x=1380)])
t = S(22); add(t, BG, [{'k': 'rot2', 'turns': 3.5, 'label': '3,5', 'sub': 'TUR · ÜÇLÜ AKSEL', 'at': rel(W_(23, 'üç'), t) - 0.6, 'dur': 2.4}])
t = S(24); add(t, ph(90, mode='fit', px=0.68, z0=1.0, z1=1.08), [tx('yetişkin şampiyonların', 440, 56, 'w', 0.2, x=600), tx('çoğu yapamaz', 530, 76, 'y', 0.6, x=600)])
t = S(25); add(t, ph(1, px=0.68, z0=1.0, z1=1.08), [tx('13 YAŞINDA', 420, 100, 'y', rel(W_(25, 'on'), t), x=600), tx('ÜÇLÜ AKSEL', 520, 74, 'w', rel(W_(25, 'üçlü'), t), x=600), {'k': 'pill', 't': 'EN GENÇ PATENCİ', 'x': 600, 'y': 640, 'at': rel(S(26, 0), t) + 1.4}])
t = S(27); add(t, LP('detroit'), [L2('DETROIT', 'OCAK 2019 · ABD ŞAMPİYONASI', 0.3)])
t = S(30); add(t, ph(89, mode='fit', px=0.33, z0=1.04, z1=1.0, dx=0.3), [{'k': 'stamp', 't': 'ŞAMPİYON', 'kind': 'ok', 'x': 1300, 'y': 470, 'at': rel(W_(31, 'kazandı'), t)}, tx('TARİHİN EN GENÇ ABD ŞAMPİYONU', 640, 48, 'w', rel(S(32, 0), t), x=1380)])
t = S(33); add(t, ph(30, mode='cover', tone='dim', dark=0.5, z0=1.18, z1=1.06, focus=[0.5, 0.4]), [{'k': 'rot2', 'turns': 4.0, 'label': '4', 'sub': 'TUR · DÖRTLÜ ATLAYIŞ', 'at': rel(W_(34, 'dört'), t) - 0.4, 'dur': 2.0}])
t = S(35); add(t, ph(30, mode='fit', px=0.68, z0=1.0, z1=1.07), [low('LAKE PLACID · 2019', 'Junior Grand Prix', 0.2), tx('DÖRTLÜ + ÜÇLÜ AKSEL', 470, 66, 'y', 0.6, x=600), tx('aynı programda ilk kadın', 560, 50, 'w', 1.0, x=600)])
t = S(36); add(t, ph(4, mode='cover', z0=1.12, z1=1.0, focus=[0.5, 0.5]), [tx('14 YAŞINDA · UNVANINI KORUDU', 150, 52, 'w', rel(W_(36, 'on'), t), box=True)])
t = S(37); add(t, ph(89, mode='cover', tone='dim', dark=0.4, z0=1.15, z1=1.05), [{'k': 'news2', 't': 'GELECEĞİN YILDIZI', 'sub': '13 yaşında Amerika şampiyonu', 'photo': F(89), 'date': 'OCAK 2019', 'cap': 'Alysa Liu', 'at': 0.0, 'rot': -2}])
t = S(38); add(t, ph(3, px=0.68, z0=1.0, z1=1.06), [tx('PROGRAM', 380, 74, 'w', rel(W_(39, 'Program'), t), x=620), tx('MÜZİK', 480, 74, 'w', rel(W_(39, 'müzik'), t), x=620), tx('KOSTÜM', 580, 74, 'w', rel(W_(39, 'kostüm'), t), x=620), tx('başkaları seçiyordu', 690, 48, 'y', rel(W_(39, 'başkaları'), t), x=620)])
t = S(40); add(t, ph(90, mode='fit', px=0.75, tone='dim', dark=0.7), [{'k': 'quote', 'lines': ['Programlarımı bile', 'ben seçmiyordum.'], 'x': 700, 'y': 500, 'qx': 460, 'size': 82, 'at': rel(S(41, 0), t), 'gap': 0.5, 'who': 'Alysa Liu'}], nosub=True)
t = S(42); add(t, ph(97, mode='fit', px=0.5, tone='bw', z0=1.0, z1=1.1), [tx('Bu hayat gerçekten benim mi?', 960, 64, 'w', rel(S(44, 0), t), box=True)])
i = INS['2']; add(i['start'], {'k': 'chapter', 'n': 2, 'title': 'ZİRVEDE KAPIYI KAPATMAK'})
# ---------------- BÖLÜM 2 ----------------
t = S(45); add(t, LP('pekin'), [L2('PEKİN', 'ŞUBAT 2022 · KIŞ OLİMPİYATLARI')])
t = S(47); add(t, ph(98, px=0.3, z0=1.0, z1=1.07, focus=[0.5, 0.45]), [{'k': 'counter', 'to': 6, 'suffix': '.', 'size': 240, 'col': 'w', 'x': 1320, 'y': 470, 'at': rel(S(48, 0), t) - 0.3, 'dur': 0.6}, tx('16 yaşında, ilk olimpiyatı', 650, 46, 'y', 0.4, x=1400)])
t = S(49); add(t, ph(36, mode='fit', px=0.68), [low('MONTPELLIER · FRANSA', 'Mart 2022 · Dünya Şampiyonası', 0.2), {'k': 'pill', 't': 'BRONZ MADALYA', 'bg': (205, 127, 50), 'fg': 'w', 'size': 52, 'x': 600, 'y': 540, 'at': rel(S(51, 0), t)}])
t = S(52); add(t, ph(100, mode='cover', z0=1.0, z1=1.1, dark=0.6), [{'k': 'cards', 'items': [('💰', 'SPONSORLAR', rel(W_(53, 'Sponsor'), t)), ('🎥', 'KAMERALAR', rel(W_(53, 'kamera'), t)), ('👀', 'BEKLENTİLER', rel(W_(53, 'beklenti'), t))], 'y': 600}])
t = S(55); add(t, BG, [{'k': 'phone', 'lines': ['Patenden emekli', 'oluyorum.'], 'at': 0.2}, tx('9 NİSAN 2022', 470, 64, 'y', 0.5, x=1580)])
t = S(57); add(t, ph(36, mode='cover', tone='dim', dark=0.4, z0=1.15, z1=1.05), [{'k': 'news2', 't': '16 YAŞINDA EMEKLİLİK?', 'sub': 'Zirvenin tam ortasında şok karar', 'photo': F(36), 'date': 'NİSAN 2022', 'cap': 'Alysa Liu', 'at': 0.0, 'rot': 1.5}])
t = S(60); add(t, BG, [{'k': 'timeline', 'pts': [('başladı', '5'), ('ABD şampiyonu', '13'), ('olimpiyat', '16'), ('bıraktı', '16')], 'at': 0.4, 'dur': 2.8, 'y': 560}, tx('11 YIL · HİÇ DURMADAN', 300, 64, 'y', rel(S(61, 0), t) + 0.8)])
t = S(63); add(t, ph(98, mode='fit', px=0.5, tone='cold', dark=0.8, z0=1.12, z1=1.0), [tx('kendi hayatını yaşamak istiyordu', 950, 56, 'w', 0.3, box=True)])
t = S(64); add(t, BG, [{'k': 'layered', 'big': 'BIRAKMAK', 'l1': 'BIRAKMAK', 'l2': '= YENİLMEK?', 'l3': 'İLK KENDİ KARARI', 'at': 0.6, 't2': rel(S(65, 0), t) + 0.2}])
t = S(66); add(t, ph(3, mode='fit', px=0.5, tone='bw', dark=0.55, z0=1.0, z1=1.12), [tx('Buzun dışında kim olacaktı?', 540, 76, 'w', rel(S(67, 0), t))])
i = INS['3']; add(i['start'], {'k': 'chapter', 'n': 3, 'title': 'NORMAL BİR HAYAT'})
# ---------------- BÖLÜM 3 ----------------
t = S(68); add(t, LP('colorado'), [L2('COLORADO', 'OLİMPİYAT ANTRENMAN MERKEZİNDEN AYRILDI')])
t = S(69); add(t, BG, [{'k': 'counter', 'to': 7, 'suffix': ' GÜN', 'size': 230, 'col': 'y', 'y': 450, 'at': 0.4, 'dur': 1.4}, tx('antrenmansız · beş yaşından beri ilk kez', 650, 52, 'w', 1.2)])
t = S(71); add(t, LP('meksika', True, grad=0.5), [tx('İLK TATİL · MEKSİKA', 150, 64, 'w', 0.2, box=True), {'k': 'cards', 'items': [('🏖️', 'İLK TATİL', 0.5), ('🐚', 'DENİZ KABUĞU', rel(W_(72, 'deniz'), t)), ('🚡', 'ZİPLİNE', rel(W_(72, 'zipline'), t))], 'y': 760, 'cw': 380, 'ch': 250, 'size': 40}])
t = S(73); add(t, BG, [{'k': 'checks2', 'items': [('🚗', 'Ehliyet aldı'), ('🎒', 'Kardeşlerini okula götürdü'), ('🎂', 'Doğum günü partileri')], 'y': 380, 'dy': 160, 'at': 0.1, 'gap': 1.15}])
t = S(76); add(t, BG, [{'k': 'quote2', 'lines': ['sıradan bir genç kızın,', 'sıradan bir abla hayatı'], 'x': 960, 'y': 500, 'size': 76, 'at': 0.5, 'gap': 0.9, 'who': 'kendi deyişiyle', 'hi': ('sıradan',)}], nosub=True)
t = S(77); add(t, LP('ucla'), [L2('UCLA · LOS ANGELES', 'SONBAHAR 2023 · PSİKOLOJİ')])
t = S(80); add(t, LP('ucla', tone='cold', dark=0.32, grad=None, z0=1.0, z1=1.08), [{'k': 'neuro', 'x': 960, 'y': 340, 'at': 0.0}, tx('İnsan zihnini anlamak', 640, 70, 'w', 0.3), tx('belki de önce kendi zihnini', 740, 56, 'y', rel(S(81, 0), t))])
t = S(82); add(t, ph(3, mode='cover', tone='bw', dark=0.42, z0=1.0, z1=1.1), [tx('KİMLİK = PATENCİ ?', 420, 96, 'gr', 0.3), tx('SEÇME ÖZGÜRLÜĞÜ', 600, 112, 'y', rel(S(84, 0), t))])
t = S(85); add(t, BG, [{'k': 'counter', 'to': 2, 'suffix': ' YIL', 'size': 230, 'col': 'w', 'y': 470, 'at': 0.3, 'dur': 1.0}, tx('buzdan uzak', 650, 60, 'y', 0.8), {'k': 'emoji', 'ch': '⛷️', 'x': 960, 'y': 850, 'size': 130, 'at': rel(S(86, 0), t)}])
i = INS['4']; add(i['start'], {'k': 'chapter', 'n': 4, 'title': 'GERİ DÖNÜŞÜN KODU'})
# ---------------- BÖLÜM 4 ----------------
t = S(87); add(t, LP('tahoe'), [L2('LAKE TAHOE', 'OCAK 2024 · BİR KAYAK GEZİSİ')])
t = S(90); add(t, BG, [{'k': 'kin', 'words': [('HIZ', rel(S(91, 0), t) - 0.15, 'speed', 330, 'w'), ('ADRENALİN', rel(S(92, 0), t) + 0.1, 'punch', 530, 'w'), ('KONTROL', rel(S(93, 0), t), 'lock', 730, 'y')], 'size': 130}], nosub=True)
t = S(94); add(t, BG, [{'k': 'phone', 'lines': ['Buza geri', 'dönüyorum.'], 'at': 0.2}, tx('MART 2024', 470, 64, 'y', 0.5, x=1580)])
t = S(96); add(t, ph(7, mode='fit', px=0.7, z0=1.0, z1=1.08), [low('SKATE CANADA · 2024', 'İlk sezonu', 0.2), tx('Bu kez kurallar farklı', 480, 64, 'y', 0.4, x=600)])
t = S(97); add(t, ph(9, mode='fit', px=0.3), [{'k': 'checklist', 'items': ['MÜZİK', 'KOSTÜM', 'PROGRAM'], 'x': 1180, 'y': 360, 'at': 0.2, 'gap': 99, 'size': 70}])
t = S(98); add(t, ph(10, mode='fit', px=0.3, z0=1.0, z1=1.07), [{'k': 'counter', 'to': 15, 'suffix': ' KEZ', 'size': 200, 'col': 'y', 'x': 1320, 'y': 470, 'at': rel(W_(98, 'on'), t), 'dur': 1.2}, tx('müziğini değiştirdi', 640, 52, 'w', rel(W_(98, 'değiştirdi'), t), x=1400)])
t = S(99); add(t, ph(112, mode='fit', px=0.68, z0=1.0, z1=1.08), [tx('KOSTÜM', 420, 90, 'w', 0.2, x=620), tx('defalarca terziye geri', 520, 50, 'y', 0.6, x=620), low('2024 DÜNYA ŞAMPİYONASI', 'Kostüm sergisi', 0.3)])
t = S(100); add(t, ph(11, mode='fit', px=0.32), [tx('ANTRENMAN PROGRAMI', 450, 62, 'w', 0.2, x=1380), tx('kendi kararı', 540, 56, 'y', 0.6, x=1380)])
t = S(101); add(t, ph(5, mode='fit', px=0.7, z0=1.06, z1=1.0), [tx('“ALYSA 2.0”', 470, 110, 'w', rel(W_(101, 'Alysa'), t), x=600), {'k': 'stamp', 't': 'SEVMEDİ', 'kind': 'no', 'x': 600, 'y': 620, 'at': rel(S(102, 0), t) + 0.6}])
t = S(103); add(t, BG, [tx('DEĞİŞEN KİŞİ DEĞİL', 420, 90, 'gr', 0.2), tx('KARARI VEREN', 580, 120, 'y', rel(S(104, 0), t))])
t = S(105); add(t, ph(7, mode='fit', px=0.75, tone='dim', dark=0.7), [{'k': 'quote', 'lines': ['Bu sefer tamamen', 'kendim için.'], 'x': 700, 'y': 500, 'qx': 450, 'size': 88, 'at': rel(S(106, 0), t), 'gap': 0.6, 'who': 'Alysa Liu'}], nosub=True)
t = S(107); add(t, LP('boston'), [L2('BOSTON', 'MART 2025 · DÜNYA ŞAMPİYONASI')])
t = S(111); add(t, ph(54, mode='fit', px=0.32, z0=1.0, z1=1.08), [{'k': 'pill', 't': 'DÜNYA ŞAMPİYONU', 'size': 52, 'x': 1300, 'y': 470, 'at': 0.2}])
t = S(112); add(t, ph(58, mode='fit', px=0.7), [tx('2006 → 2025', 400, 90, 'w', 0.2, x=620), {'k': 'counter', 'to': 19, 'suffix': ' YIL', 'size': 160, 'col': 'y', 'x': 620, 'y': 560, 'at': 0.6, 'dur': 1.5}, tx('Kimmie Meissner\'dan beri ilk', 700, 40, 'w', 1.0, x=620)])
t = S(114); add(t, ph(93, mode='cover', z0=1.0, z1=1.1, focus=[0.4, 0.5]), [tx('+ TAKIM ALTINI', 950, 70, 'y', 0.3, box=True)])
t = S(115); add(t, LP('nagoya'), [L2('NAGOYA, JAPONYA', 'ARALIK 2025 · GRAND PRIX FİNALİ')])
t = S(115) + 2.7; add(t, ph(39, mode='fit', px=0.7, z0=1.0, z1=1.06), [low('GRAND PRIX FİNALİ', 'Nagoya · altın', 0.2)])
t = S(116); add(t, ph(104, mode='fit', px=0.5, z0=1.1, z1=1.0), [tx('Peki ya olimpiyatlar?', 940, 76, 'w', rel(S(117, 0), t), box=True)])
i = INS['5']; add(i['start'], {'k': 'chapter', 'n': 5, 'title': 'MİLANO'})
# ---------------- BÖLÜM 5 ----------------
t = S(118); add(t, LP('milano'), [L2('MİLANO-CORTINA', 'ŞUBAT 2026 · KIŞ OLİMPİYATLARI')])
t = S(120); add(t, ph(99, mode='cover', z0=1.0, z1=1.12, focus=[0.55, 0.5]), [low('TAKIM YARIŞMASI', '6 Şubat 2026', 0.2), tx('KISA PROGRAMDA 2.', 940, 64, 'w', rel(W_(121, 'ikinci'), t), box=True)])
t = S(122); add(t, ph(113, mode='cover', z0=1.12, z1=1.0, focus=[0.5, 0.5]), [{'k': 'pill', 't': 'TAKIM ALTINI · ABD', 'size': 54, 'x': 960, 'y': 900, 'at': 0.3}, tx('İLK OLİMPİYAT ALTINI', 160, 56, 'y', rel(S(123, 0), t), box=True)])
t = S(124); add(t, BG, [tx('BİREYSEL YARIŞMA', 420, 100, 'y', 0.1), tx('2 program · tek puan', 560, 60, 'w', rel(S(125, 0), t))])
t = S(126); add(t, LP('milano', tone='cold', dark=0.35, grad=None, z0=1.0, z1=1.1), [tx('PUAN NASIL HESAPLANIR?', 230, 56, 'y', 0.1), {'k': 'formula', 'cards': [('⏱️', 'KISA PROGRAM', 'ilk gün', rel(W_(126, 'kısa'), t)), ('🎼', 'SERBEST PROGRAM', 'daha uzun · daha zor', rel(W_(126, 'serbest'), t)), ('🏅', 'TOPLAM PUAN', 'iki puan toplanır', rel(S(127, 0), t))], 'ops': [('+', rel(W_(126, 'serbest'), t) - 0.25), ('=', rel(S(127, 0), t) - 0.15)], 'y': 580}])
t = S(128); add(t, ph(96, mode='fit', px=0.7), [{'k': 'pill', 't': 'KISA PROGRAM SONRASI', 'size': 34, 'x': 600, 'y': 360, 'at': 0.2}, {'k': 'counter', 'to': 3, 'suffix': '.', 'size': 230, 'col': 'w', 'x': 600, 'y': 520, 'at': rel(W_(128, 'üçüncü'), t) - 0.3, 'dur': 0.6}, tx('altın için kusursuz olmalı', 690, 46, 'y', rel(S(130, 0), t), x=600)])
t = S(131); add(t, ph(22, mode='cover', z0=1.15, z1=1.0, focus=[0.45, 0.6]), [low('19 ŞUBAT 2026', 'Serbest program', 0.2)])
t = S(134); add(t, ph(21, mode='fit', px=0.5, z0=1.0, z1=1.1), [tx('Gülümsüyordu.', 950, 64, 'w', rel(S(135, 0), t), box=True)])
t = S(136); add(t, ph(19, mode='cover', z0=1.0, z1=1.12, focus=[0.5, 0.55]))
t = S(137, 1.5); add(t, ph(20, mode='cover', z0=1.12, z1=1.0, focus=[0.5, 0.55]))
t = S(138); add(t, ph(23, mode='cover', z0=1.12, z1=1.0, focus=[0.5, 0.55]), [{'k': 'pill', 't': 'SERBEST PROGRAMDA 1.', 'size': 52, 'x': 960, 'y': 900, 'at': rel(S(139, 0), t)}])
t = S(140); add(t, ph(23, mode='cover', tone='cold', dark=0.3, z0=1.12, z1=1.0, focus=[0.5, 0.5]), [tx('KADINLAR · BİREYSEL SONUÇ', 190, 54, 'y', 0.1), {'k': 'score2', 'rows': [('ALYSA LIU', 226.79, 'USA'), ('KAORI SAKAMOTO', 224.90, 'JPN'), ('AMI NAKAI', 219.16, 'JPN')], 'y': 320, 'min': 200, 'at': 0.0}])
t = S(143); add(t, ph(24, mode='cover', z0=1.0, z1=1.1, focus=[0.5, 0.35]), [tx('OLİMPİYAT ŞAMPİYONU', 940, 92, 'y', 0.3, box=True)])
i = INS['sampiyon']; add(i['start'], ph(25, mode='fit', px=0.5, z0=1.0, z1=1.12, snow=True), [])
t = S(144); add(t, BG, [{'k': 'tl2', 'pts': [('Sarah Hughes', '2002'), ('Alysa Liu', '2026')], 'at': 0.3, 'dur': 2.0, 'y': 590}, tx('24 YIL SONRA', 150, 56, 'y', 2.6)])
t = S(145); add(t, ph(114, mode='fit', px=0.5, z0=1.0, z1=1.15), [tx('2. ALTIN', 540, 130, 'y', 0.2, x=1450)])
t = S(146); add(t, {'k': 'split', 'photos': [F(89), F(29)], 'focus': [[0.5, 0.3], [0.5, 0.3]]}, [tx('16 YAŞINDA BIRAKTI', 1020, 52, 'w', 0.1, x=530), tx('20 YAŞINDA TARİH YAZDI', 1020, 52, 'y', rel(W_(146, 'yirmi'), t), x=1390)])
i = INS['6']; add(i['start'], {'k': 'chapter', 'n': '★', 'title': 'HİKÂYEDEN 3 DERS'})
# ---------------- DERSLER + KOD ----------------
t = S(147); add(t, ph(96, mode='fit', px=0.5, dark=0.55), [tx('3 DERS', 540, 140, 'y', rel(S(148, 0), t))])
t = S(149); add(t, BG, [tx('1', 300, 160, 'y', 0.1), tx('DURMAK, BİTMEK DEĞİLDİR', 520, 82, 'w', rel(S(150, 0), t)), tx('kariyer bitmedi · sahibi değişti', 640, 50, 'gr', rel(S(151, 0), t) + 0.5)])
t = S(153); add(t, {'k': 'split', 'photos': [F(0), F(28)], 'focus': [[0.5, 0.3], [0.5, 0.3]]}, [tx('2', 90, 70, 'y', 0.1, x=960), tx('13 YAŞ · YETENEK', 1020, 50, 'w', rel(S(155, 0), t), x=530), tx('20 YAŞ · YETENEK + İSTEK', 1020, 50, 'y', rel(S(156, 0), t), x=1390)])
t = S(157); add(t, BG, [tx('3', 300, 160, 'y', 0.1), tx('KONTROL, MOTİVASYONUN YAKITIDIR', 520, 74, 'w', rel(S(158, 0), t))])
t = S(159); add(t, ph(62, mode='fit', px=0.7, z0=1.0, z1=1.08), [{'k': 'checklist', 'items': ['MÜZİĞİ', 'KOSTÜMÜ', 'PROGRAMI'], 'x': 330, 'y': 400, 'at': 0.3, 'gap': 0.7, 'size': 64}])
t = S(160); add(t, ph(68, mode='fit', px=0.5, tone='dim', dark=0.8), [tx('AYNI BUZ', 300, 100, 'w', 0.0), tx('AYNI ATLAYIŞLAR', 450, 100, 'w', rel(S(161, 0), t)), tx('AYNI ANTRENÖR', 600, 100, 'w', rel(S(162, 0), t)), tx('DEĞİŞEN: KARARIN SAHİBİ', 800, 78, 'y', rel(S(163, 0), t) + 0.3)], nosub=True)
t = S(164); add(t, ph(27, mode='fit', px=0.78, dark=0.8), [tx('BEYİN KODU #2', 330, 100, 'y', 0.1, x=640), {'k': 'bar', 'x': 640, 'y': 400, 'w': 600, 'at': 0.4}, tx('Başkasının hayalini yaşarken', 480, 50, 'w', rel(S(166, 0), t), x=640), tx('zirve bile ağır gelir.', 545, 50, 'w', rel(S(166, 0), t) + 0.3, x=640), tx('Kendi seçtiğin yolda ise', 640, 50, 'y', rel(S(167, 0), t), x=640), tx('zorluk bile hafifler.', 705, 50, 'y', rel(S(167, 0), t) + 0.3, x=640), tx('Sen kimin hayalini yaşıyorsun? 👇', 850, 46, 'w', rel(S(168, 0), t), x=640)], nosub=True)
add(TL['voice_end_final'] + 0.6, {'k': 'end', 'kod': 'BEYİN KODU #2', 'lines': ['Başkasının hayalini yaşarken', 'zirve bile ağır gelir.', 'Kendi seçtiğin yolda ise', 'zorluk bile hafifler.']})

# ---------------- B-ROLL (Pexels, temsili) ----------------
import os
def V(id_): 
    f = [x for x in os.listdir('video') if x.startswith(f'px_{id_}_')] if os.path.isdir('video') else []
    return 'video/' + f[0] if f else None
BROLL = [(18, '6539145', dict(vdark=0.55, off=1.0)), (22, '6015598', dict(vdark=0.45, off=2.0)), (64, '6015598', dict(vdark=0.5, off=8.0, tone='bw')),
         (69, '6539119', dict(vdark=0.5, off=0.5)), (85, '6539119', dict(vdark=0.5, off=6.0, tone='bw')), (90, '6539137', dict(vdark=0.5, off=0.5)),
         (103, '6539116', dict(vdark=0.5, off=1.0)), (124, '6539134', dict(vdark=0.5, off=1.0)), (149, '6539132', dict(vdark=0.5, off=1.0)),
         (157, '6015591', dict(vdark=0.5, off=1.0))]
for k, vid, kw in BROLL:
    path = V(vid)
    if not path: continue
    st = round(S(k), 3)
    for sc in Q:
        if abs(sc['start'] - st) < 0.002:
            b = {'k': 'video', 'video': path, 'credit': 'Temsili görüntü · Pexels'}; b.update(kw); sc['base'] = b; sc['broll'] = True

Q.sort(key=lambda s: s['start'])
for a, b in zip(Q, Q[1:]): a['end'] = b['start']
Q[-1]['end'] = TL['total']
for s in Q:
    if s['base'].get('k') in ('chapter',): s['cut'] = False
json.dump({'fps': 24, 'total': TL['total'], 'xfade': 0.35, 'scenes': Q}, open('plan.json', 'w'), ensure_ascii=False, indent=1)
durs = [s['end'] - s['start'] for s in Q]
print('sahne', len(Q), 'ort', round(sum(durs) / len(durs), 2), 'max', round(max(durs), 2), 'min', round(min(durs), 2))
for s in Q:
    d = s['end'] - s['start']
    if d > 9 or d < 1.2: print('  uyarı', round(s['start'], 1), round(d, 1), s['base'].get('k'), s['base'].get('photo', ''))
