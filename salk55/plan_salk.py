"""Jonas Salk 5:30 belgesel - sahne plani uretici.
Senaryonun her cumlesi bir sahneye baglanir. Ses yokken zamanlama okuma hizindan TAHMIN edilir;
ses gelince align adimi (kelime zamanlari) bu dosyadaki 'words' tahminlerini gercekleriyle degistirir.
Kullanim: python plan_salk.py [kelime_zamanlari.json]
"""
import json, re, sys

WPS = 2.3            # tahmini okuma hizi (kelime/sn) - ElevenLabs Turkce
SENT_PAUSE = 0.30
PARA_PAUSE = 0.65
CH_DUR = 2.4         # bolum basligi: sessiz nefes ani
X = lambda t, d=0.45: {"type": t, "dur": d}

ARCH = {
    "01": "ARŞİV · Çocuk felci karantina kartı · Public domain",
    "02": "ARŞİV · Poliovirüs, elektron mikroskobu · CDC, Public domain",
    "03": "ARŞİV · Fizik tedavi gören çocuklar · CDC, Public domain",
    "04": "ARŞİV · Demir akciğerde tedavi gören hasta · NMHM, CC BY 2.0",
    "05": "ARŞİV · Demir akciğer · CDC, Public domain",
    "06": "ARŞİV · Jonas Salk, 1959 · SAS, Public domain",
    "07": "ARŞİV · Jonas Salk, 1959 · SAS, Public domain",
    "08": "ARŞİV · Çocuk felci aşısı, 1956 · Mississippi Dept. of Archives and History",
    "09": "ARŞİV · Çocuk felci aşısı, 1956 · Mississippi Dept. of Archives and History",
    "10": "ARŞİV · Çocuk felci aşısı, İsrail 1958 · Public domain",
    "11": "ARŞİV · Salk aşısı manşetleri, 1955 · March of Dimes, Public domain",
    "12": "ARŞİV · Edward R. Murrow, 1953 · Public domain",
    "13": "ARŞİV · Jonas Salk, 1959 · SAS, Public domain",
    "14": "ARŞİV · Jonas Salk, 1988 · CDC, Public domain",
    "15": "ARŞİV · Albert Sabin · CDC (EID Journal), Public domain",
    "16": "Rackham Binası, Michigan Üniversitesi (günümüz) · CC0",
    "17": "Güneş · NASA/SDO, Public domain",
    "18": "Dünya · NASA Blue Marble, Public domain",
    "19": "ARŞİV · Roosevelt tekerlekli sandalyede, 1941 · FDR Kütüphanesi, Public domain",
    "20": "ARŞİV · Çocuk Felci Onur Galerisi açılışı, 1958 (Salk ve Sabin) · NARA, Public domain",
    "21": "ARŞİV · Demir akciğer koğuşu · FDA, Public domain",
    "22": "ARŞİV · March of Dimes bağış kampanyası, Washington 1948 · NARA, Public domain",
    "24": "ARŞİV · Roosevelt ve üç çocuk felci hastası, Warm Springs 1925 · NARA, Public domain",
    "25": "ARŞİV · Aşı dağıtımı ve güvenliği raporu taslağı, Temmuz 1955 · HEW/DPLA, Public domain",
}
IMG = {k: f"src/{v}" for k, v in {
    "01": "01_karantina_karti.jpg", "02": "02_virus_mikroskop.jpg", "03": "03_cocuklar_fizik_tedavi.jpg",
    "04": "04_demir_ciger_hasta.jpg", "05": "05_demir_ciger_makine.jpg", "06": "06_salk_portre_1959.jpg",
    "07": "07_salk_candid.jpg", "08": "08_asi_1956_a.jpg", "09": "09_asi_1956_b.jpg", "10": "10_asi_cocuk_1958.jpg",
    "11": "11_gazete_manset_1955.jpg", "12": "12_muhabir_murrow_1953.jpg", "13": "13_salk_havalimani_1959.jpg",
    "14": "14_salk_1988.jpg", "15": "15_sabin_portre.jpg", "16": "16_rackham_annarbor.jpg",
    "17": "17_gunes_nasa.jpg", "18": "18_dunya_nasa.jpg",
    "19": "19_fdr_tekerlekli_1941.jpg", "20": "20_salk_sabin_1958.jpg", "21": "21_demir_ciger_kogus.jpg", "22": "22_march_of_dimes_1948.jpg",
    "24": "24_fdr_warm_springs_1925.jpg", "25": "25_hew_rapor_1955.jpg"}.items()}


def arch(k, typ="archival_push", **params):
    return {"type": typ, "visualType": "archival", "visualAssets": [IMG[k]], "caption": ARCH[k], "params": params}


def chapter(n, title, sub, bg):
    return {"type": "chapter", "visualType": "dataGraphic", "visualAssets": [IMG[bg]],
            "params": {"num": f"BÖLÜM {n}", "title": title, "sub": sub, "total": 6, "index": n - 1},
            "noSubs": True, "transitionIn": X("dip", 0.5), "purpose": f"Bölüm {n} geçişi: nefes anı",
            "soundEffects": [{"type": "impact", "t": 0.15, "gain": 0.35, "f0": 46}, {"type": "whoosh", "t": 0.1, "gain": 0.06}]}


def namecard(kicker, title, sub, bg=None):
    sc = {"type": "chapter", "visualType": "dataGraphic", "params": {"num": kicker, "title": title, "sub": sub, "size": 112}}
    if bg:
        sc["visualAssets"] = [IMG[bg]]
    return sc


TL_ITEMS = [["1947", "Pittsburgh", IMG["02"]], ["1952", "Salgın", IMG["04"]], ["1953", "Kendine aşı", IMG["06"]],
            ["1954", "Saha deneyi", IMG["09"]], ["1955", "Sonuç", IMG["11"]], ["1963", "Enstitü", IMG["14"]]]
SFX_MANSET = [{"type": "room", "t": 0.0, "dur": 4.0}, {"type": "air", "t": 1.13, "dur": 0.75}, {"type": "body", "t": 1.15},
              {"type": "bass", "t": 1.15, "gain": 0.8}, {"type": "resonance", "t": 1.16}, {"type": "dust", "t": 1.14},
              {"type": "slap", "t": 1.22}, {"type": "tick", "t": 1.23}, {"type": "tick", "t": 1.25, "gain": 0.7},
              {"type": "scrape", "t": 1.50, "dur": 0.3}, {"type": "silence", "t": 1.30, "dur": 0.40},
              {"type": "bell", "t": 2.2, "gain": 0.05}]

# (anlati metni, sahne, paragraf sonu?, amac)
SEG = [
    # --- KANCA ---
    ("On iki Nisan, bin dokuz yüz elli beş.", {"type": "year_card", "visualType": "dataGraphic", "params": {"year": "1955", "kicker": "12 NİSAN"}}, False, "Kanca: tarih"),
    ("Amerika'da milyonlarca insan televizyonun başında.", arch("12", grade="bw_cool", z0=1.05, z1=1.16, x0=0.02, x1=-0.03), False, "Atmosfer: canlı yayın"),
    ("Ünlü gazeteci Edward Murrow, kırk yaşındaki bir doktora basit bir soru soruyor:", arch("12", "spotlight", grade="bw_cool", focus=[0.40, 0.30], zoom=1.4, target=[760, 470], radius=150, label="Edward R. Murrow", sub="Gazeteci · CBS", label_xy=[1060, 300]), False, "Kişi tanıtımı"),
    ("\"Bu aşının patenti kime ait?\"", dict(arch("12", "quote", quote="Bu aşının patenti\nkime ait?", highlight=[1], who="Edward R. Murrow, 12 Nisan 1955", size=78), noSubs=True), False, "Merak sorusu"),
    ("Doktorun vereceği cevap, tarihe geçecekti.", arch("07", z0=1.04, z1=1.20, x0=0.0, x1=-0.02, y0=0.02, y1=0.0), False, "Gerilim: sessiz an"),
    ("Ve verdiği cevapla, bazı tahminlere göre yedi milyar dolarlık bir serveti masada bıraktığı söyleniyor.", {"type": "money", "visualType": "dataGraphic", "visualAssets": [IMG["13"]], "params": {"value": 7000000000, "label": "BAZI TAHMİNLERE GÖRE (FORBES)"}, "caption": ARCH["13"]}, False, "Çarpıcı iddia (sonra sorgulanacak)"),
    ("Bu, o cevabın hikâyesi. Sonunda bu ünlü cevabın pek bilinmeyen bir yüzünü de göreceğiz. Ama önce, o cevabı bu kadar değerli yapan korkuyu anlamamız gerekiyor.", dict(namecard("BEYİN KODU LAB · BELGESEL", "GÜNEŞİN PATENTİ", "Jonas Salk ve çocuk felci aşısı", "06"), noSubs=False), True, "Başlık ve vaat"),
    # --- BOLUM 1: KORKU ---
    ("", chapter(1, "KORKU", "Amerika, 1952", "04"), False, ""),
    ("Bin dokuz yüz elli iki. Amerika, tarihinin en büyük çocuk felci salgınını yaşıyor. Tek bir yılda yaklaşık elli sekiz bin vaka.", {"type": "map", "visualType": "dataGraphic", "params": {"spread": {"t0": 1.0, "t1": 5.0, "origin": [820, 140], "value": 57628, "kicker": "1952 SALGINI", "label": "çocuk felci vakası · ABD"}, "extrude": 7, "tilt": [0, 1, 0.3, 2.8], "cy": 610, "cam": [[0, 500, 300, 0.95], [8, 470, 320, 1.05]]}, "soundEffects": [{"type": "riser", "t": 5.0, "dur": 3.5, "gain": 0.06}]}, False, "İlk veri: salgının yayılımı"),
    ("Üç binden fazla ölüm. Yirmi bir binden fazla insan, ömrünün geri kalanını felçle geçirecek.", {"type": "stats", "visualType": "dataGraphic", "visualAssets": [IMG["05"]], "params": {"kicker": "1952 · ABD", "items": [[3145, "ÖLÜM", "red"], [21269, "FELÇ", "red"]], "note": "Kaynak: History of polio"}}, False, "Bedel"),
    ("Hastalığın en korkutucu yanı, kimi seçeceğinin bilinmemesiydi.", arch("03", "spotlight", focus=[0.33, 0.62], zoom=1.35, target=[760, 560], radius=170, label="Kim olacağı bilinmiyordu", label_xy=[1060, 360]), False, "Belirsizlik korkusu"),
    ("Sabah koşarak okula giden bir çocuk, akşam yürüyemez hâle gelebiliyordu.", {"type": "compare", "visualType": "dataGraphic", "params": {"left": {"kicker": "SABAH", "title": "Okula\nkoşuyor", "body": "Her şey normal.", "who": ""}, "right": {"kicker": "AKŞAM", "title": "Yürüyemiyor", "body": "Bacaklar tutmuyor.", "who": ""}}}, False, "Ani dönüşüm"),
    ("Bazı hastalar nefes bile alamıyordu. Onlar için tek çare, demir akciğer denen dev metal makinelerdi.", arch("05", "spotlight", focus=[0.30, 0.45], zoom=1.25, target=[720, 520], radius=190, label="DEMİR AKCİĞER", sub="Nefes almayı makine sağlıyordu", label_xy=[1040, 300]), False, "Somut korku nesnesi"),
    ("Hastane koridorları bu makinelerle doluydu.", arch("21", z0=1.04, z1=1.16, x0=0.03, x1=-0.03), False, "Yaygınlık"),
    ("Yazlar korku mevsimine dönüştü. Yüzme havuzları kapandı, sinemalar boşaldı.", dict(arch("01", "archival_kinetic", grade="bw_cool", lines=[["Yazlar korku mevsimine dönüştü.", "small", 0.3], ["HAVUZLAR KAPANDI", "big", 1.6], ["Sinemalar boşaldı.", "small", 2.6]]), noSubs=True), False, "Günlük hayatın çöküşü"),
    ("Anneler çocuklarını sokağa çıkarmaya korkuyordu.", arch("04", z0=1.30, z1=1.42, x0=0.10, x1=0.06, y0=0.02, y1=0.0), False, "Duygu: anne"),
    ("Bu hastalık güçlüleri bile ayırt etmiyordu.", arch("24", z0=1.12, z1=1.02, x0=0.04, x1=0.0), False, "Güçlüler bile (arşiv)"),
    ("Franklin Roosevelt, otuz dokuz yaşında çocuk felcine yakalanmış ve bir daha yardımsız yürüyememişti.", arch("19", "photo_card", side="right", kicker="32. ABD BAŞKANI", title="Franklin D.\nRoosevelt", sub="1921: 39 yaşında çocuk felci", grade="bw_cool", z0=0.86, z1=0.92), False, "Güçlüler bile"),
    ("Kurduğu vakıf, halktan küçük bağışlar topluyordu.", arch("22", z0=1.05, z1=1.17, x0=-0.02, x1=0.02), False, "Halkın seferberliği (arşiv)"),
    ("İnsanlar zarflara birer onluk koyup gönderiyordu. Milyonlarca bozuk para, tek bir umut için birikiyordu.", {"type": "coins", "visualType": "dataGraphic", "params": {"kicker": "FRANKLIN D. ROOSEVELT · 1938", "title": "Milyonlarca\nbozuk para", "sub": "Halk, zarflara birer onluk koyup gönderdi."}}, False, "Toplumsal umut"),
    ("Ama bu umudu gerçeğe dönüştürecek kişi, o yıllarda henüz kimsenin tanımadığı genç bir doktordu.", arch("06", grade="bw_cool", z0=1.45, z1=1.15, x0=0.06, x1=0.02, y0=0.05, y1=0.02), True, "Köprü: kahramanın gölgesi (merak)"),
    # --- BOLUM 2: AYKIRI FIKIR ---
    ("", chapter(2, "AYKIRI FİKİR", "Pittsburgh, 1947", "02"), False, ""),
    ("Bu umudun adresi, Pittsburgh'daki bir laboratuvardı.", {"type": "microscope", "visualType": "archival", "visualAssets": [IMG["02"]], "caption": ARCH["02"], "params": {"title": "PITTSBURGH ÜNİVERSİTESİ", "sub": "Virüs Araştırma Laboratuvarı", "hud": "POLİOVİRÜS · ELEKTRON MİKROSKOBU"}}, False, "Mekân"),
    ("Jonas Salk, New York'ta yoksul bir ailenin çocuğuydu.", {"type": "portrait_parallax", "visualType": "archival", "visualAssets": [IMG["06"], "mask06.png"], "caption": ARCH["06"], "params": {"name": "JONAS SALK", "sub": "Virolog · 1914, New York"}, "noSubs": True}, False, "Kahraman tanıtımı"),
    ("Tıp fakültesini bitirdiğinde önünde rahat bir hekimlik kariyeri vardı.", arch("13", z0=1.05, z1=1.14, x0=0.03, x1=-0.01), False, "Rahat yol"),
    ("Ama o, hastaları tek tek tedavi etmek yerine, hastalığı kökünden durdurmayı seçti.", dict(arch("07", "archival_kinetic", grade="bw_cool", lines=[["Hastaları tek tek değil,", "small", 0.3], ["HASTALIĞI KÖKÜNDEN", "big", 1.6], ["durdurmayı seçti.", "small", 2.6]]), noSubs=True), False, "Karakter seçimi"),
    ("Bin dokuz yüz kırk yedide Pittsburgh Üniversitesi'nde kendi virüs laboratuvarının başına geçti.", {"type": "map", "visualType": "dataGraphic", "params": {"title": "JONAS SALK'IN YOLU", "terrain": True, "tilt": 1.0, "cy": 620, "highlight": [{"state": "pa", "t": 1.6}], "pins": [{"city": "ny", "label": "New York", "sub": "Doğum · 1914", "t": 0.4, "side": "right"}, {"city": "pit", "label": "Pittsburgh", "sub": "Virüs laboratuvarı · 1947", "t": 2.4, "side": "left"}], "routes": [{"from": "ny", "to": "pit", "t0": 1.2, "t1": 2.4}], "cam": [[0, 700, 200, 1.6], [8, 760, 190, 2.4]]}}, False, "Yolculuk"),
    ("Ve dönemin pek çok bilim insanının yanlış bulduğu bir fikre inandı.", {"type": "question", "visualType": "reconstruction", "params": {"bg3d": "virus", "kicker": "AYKIRI BİR FİKİR", "question": "Ölü bir virüs\nkoruyabilir mi?"}, "noSubs": True}, False, "Merak (yeniden kanca)"),
    ("O yıllardaki yaygın görüş şuydu: Kalıcı bağışıklık için vücuda canlı ama zayıflatılmış virüs verilmeliydi. Salk ise farklı düşünüyordu.", {"type": "compare", "visualType": "dataGraphic", "params": {"left": {"kicker": "YAYGIN GÖRÜŞ", "title": "Canlı ama\nzayıf virüs", "body": "Kalıcı bağışıklık için\nvirüs canlı olmalı.", "who": "ALBERT SABIN"}, "right": {"kicker": "AYKIRI FİKİR", "title": "Tamamen\nölü virüs", "body": "Formaldehitle öldürülmüş virüs\nkimseyi hasta edemez.", "who": "JONAS SALK"}, "viz": "virus"}}, False, "Çatışma"),
    ("Virüsü formaldehitle tamamen öldürürse, vücut yine de onu tanımayı öğrenebilirdi. Üstelik ölü bir virüs, kimseyi hasta edemezdi.", {"type": "virus3d", "visualType": "reconstruction", "params": {"title": "Ölü virüs", "sub": "Formaldehitle etkisiz hâle getirildi", "dead_word": "öldürürse", "hud": "POLİOVİRÜS"}}, False, "Bilimsel fikir (temsili)"),
    ("En güçlü rakibi Albert Sabin, ölü virüsle kalıcı koruma sağlanamayacağını savunuyordu. Salk geri adım atmadı.", arch("15", "photo_card", side="right", kicker="EN GÜÇLÜ RAKİP", title="Albert\nSabin", sub="Canlı (zayıflatılmış) virüs aşısını savundu", grade="bw_cool", z0=0.86, z1=0.92), False, "Karşı güç"),
    ("Laboratuvarında yıllar süren deneylerin sonunda, işe yarayacağına inandığı bir aşı vardı.", arch("02", z0=1.08, z1=1.20, x0=0.02, x1=-0.02), False, "Sonuç: aşı hazır"),
    ("Ama bunu kanıtlamanın tek bir yolu vardı: Aşıyı bir insana yapmak.", dict(arch("10", "archival_kinetic", grade="bw_cool", lines=[["Kanıtlamanın tek yolu:", "small", 0.3], ["BİR İNSANA YAPMAK", "big", "insana"]]), noSubs=True), True, "Uçurum: risk (merak)"),
    # --- BOLUM 3: EN BUYUK RISK ---
    ("", chapter(3, "EN BÜYÜK RİSK", "1953", "21"), False, ""),
    ("Peki bir aşının güvenli olduğundan nasıl emin olursunuz?", {"type": "question", "visualType": "reconstruction", "params": {"bg3d": "vial", "kicker": "PEKİ...", "question": "Bir aşının güvenli\nolduğundan nasıl\nemin olursunuz?"}, "noSubs": True}, False, "Merak"),
    ("Salk'ın cevabı, beklenmeyecek kadar kişiseldi. Bin dokuz yüz elli üçte aşıyı önce kendisine yaptı. Sonra eşine. Sonra da üç oğluna.", {"type": "family", "visualType": "dataGraphic", "visualAssets": [IMG["08"]], "params": {"intro_photo": IMG["08"], "intro_caption": ARCH["08"], "title": "1953: İLK DENEKLER", "bigyear": "1953", "people_words": [["SALK", 230, "kendisine"], ["EŞİ", 205, "eşine"], ["OĞLU", 150, "oğluna"], ["OĞLU", 135, "oğluna+0.25"], ["OĞLU", 120, "oğluna+0.5"]]}}, False, "Kişisel risk"),
    ("Bir babanın, kendi geliştirdiği aşıyı kendi çocuklarına yapması...", arch("06", z0=1.05, z1=1.22, x0=0.0, x1=0.0, y0=0.04, y1=0.0), False, "Duygu"),
    ("Bu, laboratuvardaki her sayıdan daha güçlü bir mesajdı: \"Ben buna inanıyorum.\"", dict(arch("13", "quote", quote="Ben buna\ninanıyorum.", highlight=[1], who="kararının verdiği mesaj", size=84), noSubs=True), True, "Anlam"),
    # --- BOLUM 4: DEV DENEY ---
    ("", chapter(4, "DEV DENEY", "1954", "09"), False, ""),
    ("Ama inanç yetmezdi. Kanıt gerekiyordu.", {"type": "timeline3d", "visualType": "dataGraphic", "params": {"title": "JONAS SALK", "items": TL_ITEMS, "active": 3, "from": 2}}, False, "Neden-sonuç"),
    ("Bin dokuz yüz elli dörtte tarihin en büyük tıbbi deneylerinden biri başladı. Bir milyon sekiz yüz binden fazla çocuk katıldı. Onlara \"Çocuk Felci Öncüleri\" dendi.", {"type": "crowd3d_cine", "visualType": "dataGraphic", "params": {"value": 1829916, "label": "ÇOCUK FELCİ ÖNCÜSÜ", "note": "1954 saha deneyi · Kaynak: Michigan Üniversitesi"}, "soundEffects": [{"type": "crowd", "t": 0, "dur": 7.0}, {"type": "bell", "t": 1.6, "gain": 0.035}, {"type": "bell", "t": 2.6, "gain": 0.04}, {"type": "bell", "t": 3.6, "gain": 0.045}]}, False, "Ölçek"),
    ("Deneyi tarafsız kalması için Salk değil, eski hocası Thomas Francis yönetti.", {"type": "map", "visualType": "dataGraphic", "params": {"title": "DEĞERLENDİRME MERKEZİ", "terrain": True, "tilt": 0.85, "cy": 600, "highlight": [{"state": "mi", "t": 0.8}], "pins": [{"city": "pit", "label": "Pittsburgh", "sub": "Salk · aşı", "t": 0.3, "side": "right"}, {"city": "aa", "label": "Ann Arbor, Michigan", "sub": "Thomas Francis · bağımsız değerlendirme", "t": 1.6, "side": "left"}], "routes": [{"from": "pit", "to": "aa", "t0": 0.8, "t1": 1.7}], "cam": [[0, 680, 200, 2.4], [8, 650, 190, 3.0]]}}, False, "Tarafsızlık"),
    ("Masrafların büyük kısmı, halkın gönderdiği o küçük bağışlarla karşılandı.", {"type": "money", "visualType": "dataGraphic", "params": {"value": 7500000, "label": "MARCH OF DIMES FONLARI · 1954 SAHA DENEYİ", "coins_bg": True, "num3d": True}, "caption": "Kaynak: Michigan Üniversitesi, 1955 basın bülteni"}, False, "Halkın payı"),
    ("Bir yıl boyunca bütün ülke sonucu bekledi.", {"type": "timeline3d", "visualType": "dataGraphic", "params": {"title": "BEKLEYİŞ", "items": TL_ITEMS, "active": 4, "from": 3}, "soundEffects": [{"type": "tick", "t": 0.3}, {"type": "tick", "t": 1.1}, {"type": "tick", "t": 1.9}]}, True, "Gerilim"),
    # --- BOLUM 5: CEVAP ---
    ("", chapter(5, "CEVAP", "12 Nisan 1955", "11"), False, ""),
    ("On iki Nisan, bin dokuz yüz elli beş. Michigan Üniversitesi'nde salon tıklım tıklım.", {"type": "year_card", "visualType": "archival", "visualAssets": [IMG["16"]], "caption": ARCH["16"], "params": {"year": "1955", "kicker": "12 NİSAN · ANN ARBOR, MICHIGAN"}}, False, "Döngü: kanca tarihine dönüş"),
    ("Thomas Francis kürsüye çıkıyor ve sonucu açıklıyor: Aşı güvenli, etkili ve güçlü.", dict(arch("11", "quote", quote="Güvenli.\nEtkili.\nGüçlü.", highlight=[0, 1, 2], who="Thomas Francis, 12 Nisan 1955", size=96, step_words=["güvenli", "etkili", "güçlü"]), noSubs=False), False, "Kanıt"),
    ("Kiliselerin çanları çaldı. İnsanlar sokaklarda birbirine sarıldı.", {"type": "headline3d", "visualType": "archival", "visualAssets": [IMG["11"]], "caption": ARCH["11"], "params": {"kicker": "12 NİSAN 1955 · BÜTÜN ÜLKE AYNI MANŞETİ OKUDU"}, "soundEffects": SFX_MANSET, "min_dur": 4.0}, False, "Toplumsal patlama"),
    ("Salk, bir gecede ülkenin kahramanı oldu.", arch("13", "photo_card", side="right", kicker="BİR GECEDE", title="Ulusal\nkahraman"), False, "Şöhret"),
    ("Ve o akşam, Edward Murrow o soruyu sordu: \"Patent kimin?\"", dict(arch("12", z0=1.10, z1=1.24, x0=0.02, x1=-0.02), soundEffects=[{"type": "riser", "t": 99, "dur": 1.6, "gain": 0.08}]), False, "Döngü: kanca sorusu"),
    ("Salk sakin bir sesle cevap verdi: \"Halkın, diyebilirim. Patent yok. Güneşin patentini alabilir misiniz?\"", dict(arch("06", "quote", grade="bw_cool", quote="Halkın, diyebilirim.\nPatent yok.\nGüneşin patentini\nalabilir misiniz?", highlight=[2, 3], who="Jonas Salk, 12 Nisan 1955", size=66, sun=True, sun_word="Güneşin"), noSubs=True, soundEffects=[{"type": "silence", "t": 0.0, "dur": 0.6}, {"type": "impact", "t": 0.05, "gain": 0.35, "f0": 50}]), True, "Doruk"),
    # --- BOLUM 6: YANLIS BILINEN ---
    ("", chapter(6, "YANLIŞ BİLİNEN", "Hikâyenin az bilinen tarafı", "12"), False, ""),
    ("Bu cümle bugün hâlâ cömertliğin sembolü olarak anlatılıyor. Ama hikâyenin az bilinen bir tarafı da var.", dict(arch("17", "archival_kinetic", grade="none", turn_word="Ama", lines=[["Bu cümle bugün hâlâ", "small", 0.3], ["CÖMERTLİĞİN SEMBOLÜ", "big", "cömertliğin"], ["Ama hikâyenin az bilinen bir tarafı var.", "small", "Ama"]]), noSubs=True), False, "Beklentiyi kırma"),
    ("Bazı hukukçulara göre aşının yöntemi daha önceki çalışmalara dayandığı için patent almak zaten kolay olmayacaktı.", {"type": "headline3d", "visualType": "reconstruction", "params": {"doc": {"head": "PATENT BAŞVURUSU", "fields": [["Buluş:", "İnaktive çocuk felci aşısı"], ["Mucit:", "Jonas E. Salk"], ["Başvuru tarihi:", ""], ["Patent no:", ""]]}, "kicker": "HUKUKÇULARA GÖRE: PATENT ALMAK KOLAY DEĞİLDİ"}, "soundEffects": SFX_MANSET, "min_dur": 4.0}, False, "Yeni bilgi: hukuki engel"),
    ("Yani Salk büyük ihtimalle bir patenti reddetmedi; patent almaya hiç uğraşmadı.", {"type": "money", "visualType": "dataGraphic", "visualAssets": [IMG["13"]], "caption": ARCH["13"], "params": {"value": 7000000000, "label": "BAZI TAHMİNLERE GÖRE (FORBES)", "strike": True, "strike_word": "reddetmedi", "question": "Patent başvurusu hiç yapılmadı.", "num3d": True, "nocount": True}}, False, "Yeni bilgi: iddia düzeltilir"),
    ("Peki bu, kararını küçültür mü? Bizce hayır.", {"type": "question", "visualType": "reconstruction", "params": {"bg3d": "virus", "kicker": "PEKİ...", "question": "Bu, kararını\nküçültür mü?"}, "noSubs": True}, False, "Yorum"),
    ("Çünkü asıl seçim patentle ilgili değildi. Aşı, birçok üreticinin kullanımına açık kaldı. Bu yüzden hızla ve ucuza çoğaltılabildi.", arch("09", "spotlight", focus=[0.45, 0.45], zoom=1.35, target=[760, 540], radius=170, label="Hızla çoğaltıldı", sub="Toplu aşılama · 1956", label_xy=[1080, 330]), False, "Asıl seçim"),
    ("Kabul edilmesi gereken bir gerçek daha var. İlk aylarda bir firmanın hatalı üretimi, kırk bin kadar vakaya, iki yüz çocuğun felç kalmasına ve on çocuğun ölümüne yol açtı.", {"type": "cutter3d", "visualType": "dataGraphic", "params": {"kicker": "1955 · CUTTER LABORATUVARLARI", "w1_word": "kırk", "w2_word": "iki", "w3_word": "on", "note": "Her nokta bir vaka · Kaynak: USC Scalar, The Cutter Incident"}}, False, "Dürüstlük"),
    ("Bu trajedi, aşı üretimindeki güvenlik kurallarının baştan yazılmasını sağladı.", {"type": "headline3d", "visualType": "archival", "visualAssets": [IMG["25"]], "caption": ARCH["25"], "params": {"grade": "none", "kicker": "TEMMUZ 1955 · AŞI GÜVENLİĞİ RAPORU"}, "soundEffects": SFX_MANSET, "min_dur": 4.0}, True, "Ders: kurallar değişti"),
    # --- SONUC ---
    ("Ve sonra rakamlar konuştu. Bin dokuz yüz elli ikide yaklaşık elli sekiz bin olan vaka sayısı, sadece beş yıl sonra beş bin altı yüze indi. On yıl dolmadan, yüz altmış bire düştü.", {"type": "bars3d", "visualType": "dataGraphic", "params": {"title": "ABD'DE ÇOCUK FELCİ VAKALARI", "sub": "Aşıdan önce ve sonra", "bars": [["1952", 57628, None], ["1957", 5600, None], ["1961", 161, None]], "step_words": ["iki", "altı yüze", "bire"], "note": "Kaynak: History of polio"}}, False, "Sonuç verisi"),
    ("Salk, Nobel Ödülü'nü hiç almadı.", arch("20", z0=1.04, z1=1.14, x0=0.02, x1=-0.02), False, "Ödülsüz kalan kahraman (arşiv)"),
    ("Ama bin dokuz yüz altmış üçte kendi adını taşıyan araştırma enstitüsünü kurdu ve hayatının sonuna kadar çalışmayı sürdürdü.", {"type": "timeline3d", "visualType": "dataGraphic", "params": {"title": "JONAS SALK", "items": TL_ITEMS, "active": 5, "from": 4}}, False, "Miras"),
    ("Bugün çocuk felci, dünyanın neredeyse tamamından silinmiş durumda.", {"type": "globe", "visualType": "dataGraphic", "visualAssets": [IMG["18"]], "caption": ARCH["18"], "noSubs": True, "params": {"lines": [["Bugün çocuk felci", "small", 0.2], ["NEREDEYSE YOK", "big", 1.2], ["Yabani virüs yalnızca", "small", 2.2], ["iki ülkede kaldı.", "small", 2.6]], "marks": [[30.4, 69.3], [33.9, 67.7]], "mark_t": 2.3, "mark_label": ["YABANİ VİRÜS · 2026", "Pakistan · Afganistan"], "lon0": 20, "spin": 5, "note": "Kaynak: GPEI / DSÖ, 2026"}}, True, "Kalıcı fikir"),
    ("Beyin Kodu Lab'da bu hikâyeden çıkardığımız karar ilkesi şu: Bir fikrin gerçek değeri, ona ne kadar sıkı sahip olduğunla değil, kaç hayata dokunduğuyla ölçülür. Sen olsaydın, o soruya ne cevap verirdin? Yorumlara yaz.", {"type": "kod", "visualType": "dataGraphic", "params": {"badge": "BEYİN KODU · KOD #2", "lines": ["Bir fikrin gerçek değeri,", "ona ne kadar sıkı sahip olduğunla değil,", "kaç hayata dokunduğuyla ölçülür."], "hl": 2, "question": "Sen olsaydın, ne cevap verirdin?", "q_word": "Sen", "sun": True}, "noSubs": True}, False, "İlke + soru"),
]


def words_of(text):
    return re.findall(r"[\w'’çğıöşüÇĞİÖŞÜâîû\-]+", text)


def est_times(text, t0):
    """Kelime bazli tahmini zamanlar: [(kelime, baslangic, bitis)]."""
    out = []; t = t0
    for tok in re.findall(r"[^\s]+", text):
        w = re.sub(r"[^\wçğıöşüÇĞİÖŞÜâîû'’]", "", tok)
        dur = max(0.18, 0.13 + 0.045 * len(w)) * (2.3 / WPS)
        out.append((w, t, t + dur)); t += dur
        if tok.endswith((".", "?", "!", "...", ":")):
            t += SENT_PAUSE
        elif tok.endswith((",", ";")):
            t += 0.12
    return out, t


def _wrap(txt, max_chars=42):
    lines = []; line = ""
    for w in txt.split(" "):
        if len(line) + len(w) + 1 > max_chars and line:
            lines.append(line); line = w
        else:
            line = (line + " " + w).strip()
    return lines + [line]


def split_cues(words, max_chars=42):
    """Kelimeleri en fazla 2 satir x 42 karakterlik altyazilara boler.
    Kurallar: cumle sonunda kes; 3. satira tasacaksa once kes; cumlenin sonunda <=12 karakterlik
    yetim kelime kalacaksa onceki parcayi erken kesip dengele; kelime asla kaybolmaz."""
    cues = []; cur = []
    def flush(c):
        if c:
            cues.append([round(c[0][1], 3), round(c[-1][2] + 0.15, 3), "\n".join(_wrap(" ".join(w[3] for w in c), max_chars))])
    for k, w in enumerate(words):
        if cur and len(_wrap(" ".join(x[3] for x in cur + [w]), max_chars)) > 2:
            # cumlenin geri kalani kisa mi? yetim birakmamak icin bolme noktasini one cek
            rest = []
            for x in words[k:]:
                rest.append(x[3])
                if x[3].endswith((".", "?", "!")):
                    break
            if len(" ".join(rest)) <= 12 and len(cur) > 3:
                flush(cur[:-2]); cur = cur[-2:]
            else:
                flush(cur); cur = []
        cur.append(w)
        if w[3].endswith((".", "?", "!")) and len(" ".join(x[3] for x in cur)) > 20:
            flush(cur); cur = []
    flush(cur)
    # minimum 0.83 sn ve cakismasizlik
    for a, b in zip(cues, cues[1:] + [None]):
        lim = b[0] - 0.05 if b else a[1] + 1
        if a[1] - a[0] < 0.83:
            a[1] = round(min(a[0] + 0.83, max(lim, a[1])), 3)
        if b and a[1] > b[0] - 0.05:
            a[1] = round(b[0] - 0.05, 3)
    return cues


def build(real_words=None):
    t = 0.6
    segs = []
    for text, sc, para, purpose in SEG:
        sc = json.loads(json.dumps(sc))
        if not text:  # bolum basligi: sessiz nefes ani
            segs.append({"t0": t, "t1": t + CH_DUR, "sc": sc, "words": []}); t += CH_DUR; continue
        w, t_end = est_times(text, t)
        raw = re.findall(r"[^\s]+", text)
        words = [(w[i][0], w[i][1], w[i][2], raw[i]) for i in range(len(w))]
        sc.setdefault("purpose", purpose)
        sc["narrationText"] = text
        segs.append({"t0": t, "t1": t_end, "sc": sc, "words": words})
        t = t_end + (PARA_PAUSE if para else 0.05)
    # sahne zamanlari: sahne konusmadan 0.2 sn once baslar; bir sonrakinin gecisi kadar uzar
    scenes = []; subs = []
    for i, sg in enumerate(segs):
        sc = sg["sc"]
        sc["id"] = f"s{i + 1:02d}_{sc['type']}"
        sc.setdefault("transitionIn", X("crossfade", 0.45) if i else X("none", 0))
        start = max(0.0, sg["t0"] - 0.2) if i else 0.0
        nxt = segs[i + 1] if i + 1 < len(segs) else None
        if nxt:
            ntr = nxt["sc"].get("transitionIn", X("crossfade", 0.45))["dur"]
            end = max(nxt["t0"] - 0.2, start + 1.0) + ntr
        else:
            end = sg["t1"] + 0.8
        end = max(end, start + sc.pop("min_dur", 0))
        sc["start"], sc["end"] = round(start, 3), round(end, 3)
        rel = lambda word, extra=0.0: next((round(w[1] - start + extra, 3) for w in sg["words"] if w[0].lower().startswith(word.lower())), None)
        p = sc.get("params", {})
        # kelimeye bagli animasyon zamanlari
        if "people_words" in p:
            ppl = []
            for lab, h, key in p.pop("people_words"):
                k, _, ex = key.partition("+")
                tt = rel(k, float(ex or 0)); ppl.append([lab, h, tt if tt is not None else 1.0])
            p["people"] = ppl
        if "dead_word" in p:
            p["dead_t"] = rel(p.pop("dead_word")) or 1.5
        if "strike_word" in p:
            p["strike_t"] = rel(p.pop("strike_word")) or 2.5
        if "q_word" in p:
            p["q_t"] = rel(p.pop("q_word")) or 3.5
        if "step_words" in p and sc["type"] == "quote":
            ts = [rel(w) for w in p.pop("step_words")]
            p["t0"] = ts[0] or 0.3; p["step"] = (ts[-1] - ts[0]) / max(len(ts) - 1, 1) if all(ts) else 0.55
        if "step_words" in p and sc["type"] == "bars3d":
            ts = [rel(w) for w in p.pop("step_words")]
            p["step"] = max(0.6, ((ts[-1] or 6) - (ts[0] or 1)) / 2)
        for key in [k for k in list(p) if k.endswith("_word")]:
            tt = rel(p.pop(key))
            if tt is not None:
                p[key[:-5] + "_t"] = tt
        if "lines" in p and sc["type"] in ("archival_kinetic", "globe"):
            p["lines"] = [[a, b, (rel(c) if isinstance(c, str) else c) or 0.3] for a, b, c in p["lines"]]
        if sc["type"] == "coins":
            d = end - start; t1 = min(d - 1.5, 8.5); n = 130
            sc["soundEffects"] = [{"type": "tick", "t": round(0.5 + (t1 - 0.5) * (i / n) ** 1.2, 3), "gain": 0.45} for i in (0, 2, 5, 9, 14, 20, 28, 37, 48, 60, 74, 90, 108)]
        for ev in sc.get("soundEffects", []):
            if ev.get("t") == 99:   # 'sahne sonunda' = sonraki dorugun hemen oncesi
                ev["t"] = round(end - start - 0.4, 3)
        scenes.append(sc)
        if not sc.get("noSubs"):
            subs += split_cues(sg["words"])
    total = scenes[-1]["end"]
    # bitis ekrani
    scenes.append({"id": "s99_end", "type": "end_screen", "visualType": "illustration", "visualAssets": ["src/logo.png"],
                   "params": {"tag": "HER PAZAR YENİ BELGESEL"}, "noSubs": True, "transitionIn": X("dip", 0.6),
                   "start": round(total - 0.6, 3), "end": round(total + 7.4, 3), "purpose": "Bitiş ekranı (YouTube öğeleri)"})
    total = scenes[-1]["end"]
    # muzik: bolum ruh halleri
    ch_starts = [sc["start"] for sc in scenes if sc["type"] == "chapter" and sc["params"].get("num", "").startswith("BÖLÜM")]
    moods = [[0, "dark"]] + [[s0, m] for s0, m in zip(ch_starts, ["tension", "curious", "dark", "curious", "hope", "dark"])]
    kod = next(sc for sc in scenes if sc["type"] == "kod")
    bars = next(sc for sc in scenes if sc["type"] == "bars3d")
    moods += [[bars["start"], "hope"], [kod["start"], "resolve"]]
    tl = {"project": "Jonas Salk Gunesin Patenti", "fps": 24, "width": 1920, "height": 1080, "explicitTiming": True,
          "timingSource": "kelime zamanlari" if real_words else "TAHMİN (ses yok)", "map_dir": "src/map",
          "scenes": scenes, "subtitles": subs,
          "music": {"moods": moods, "hits": [], "risers": [], "drops": []}}
    return tl, total


if __name__ == "__main__":
    tl, total = build()
    json.dump(tl, open("timeline.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(tl['scenes'])} sahne, toplam {total:.1f} sn ({int(total // 60)}:{int(total % 60):02d}), {len(tl['subtitles'])} altyazi")
