"""Hikaye ve gorsel plan denetimi (editoryal yardimci; son karar insanda).
Kullanim: python hikaye_gorsel_denetim.py timeline.json [cikti.md]
Uretir: sahne sahne gorsel plan tablosu + uyarilar:
  - ayni gorsel turu art arda 3+ sahne (monotonluk)
  - tek arsiv fotografinda 7 sn'den uzun kalis
  - ayni gorselin 45 sn icinde tekrar kullanimi
  - bolum basina merak unsuru (soru / ucurum / acik dongu) sayisi
  - gorsel degisim araligi (ortalama ve en uzun)"""
import json, sys, collections

KAT = {
    "archival_push": "arşiv foto", "archival_kinetic": "arşiv+metin", "spotlight": "arşiv vurgu", "photo_card": "arşiv kart",
    "portrait_parallax": "arşiv 2.5B", "microscope": "arşiv bilim", "headline3d": "3B belge", "year_card": "tipografi",
    "chapter": "bölüm kartı", "quote": "alıntı", "question": "soru (3B)", "kod": "kapanış", "end_screen": "bitiş",
    "map": "harita 3B", "stats": "veri", "money": "veri 3B", "coins": "3B nesne", "compare": "karşılaştırma",
    "virus3d": "3B bilim", "family": "3B figür", "crowd3d_cine": "3B kalabalık", "timeline3d": "3B zaman", "bars3d": "veri 3B",
    "cutter3d": "veri 3B", "globe": "3B küre",
}
KAMERA = {"archival_push": "yavaş itme/kaydırma", "spotlight": "odak yakınlaşma", "portrait_parallax": "derinlik paralaks",
          "headline3d": "düşüş + yerleşme", "map": "eğik uçuş", "crowd3d_cine": "vinç yükselişi", "timeline3d": "yanal kaydırma",
          "bars3d": "yörünge", "cutter3d": "uzaktan yakına dalış", "globe": "dönüş", "coins": "yavaş itme", "virus3d": "yörünge + dönüş"}
MERAK = ("?", "merak", "uçurum", "kanca", "döngü", "soru", "beklenti", "gerilim")


def main(path, out=None):
    tl = json.load(open(path, encoding="utf-8"))
    sc = [s for s in tl["scenes"] if s["type"] != "end_screen"]
    rows, warn = [], []
    last_img = {}
    run = []
    chapter = "Kanca"; merak = collections.Counter(); ch_order = ["Kanca"]
    for s in sc:
        d = s["end"] - s["start"]
        typ = s["type"]; kat = KAT.get(typ, typ)
        if typ == "chapter" and s["params"].get("num", "").startswith("BÖLÜM"):
            chapter = s["params"]["title"]; ch_order.append(chapter)
        purpose = s.get("purpose", "")
        txt = s.get("narrationText", "")
        if any(k in purpose.lower() for k in MERAK) or "?" in txt or typ == "question":
            merak[chapter] += 1
        img = (s.get("visualAssets") or [""])[0].split("/")[-1]
        rows.append((s["start"], d, typ, kat, KAMERA.get(typ, "sabit/hafif"), img, purpose))
        # monotonluk
        fam = kat.split(" ")[0]
        run = run + [fam] if run and run[-1] == fam else [fam]
        if len(run) == 3:
            warn.append(f"{s['start']:6.1f} sn: '{fam}' türü art arda 3 sahne — çeşitlendirmeyi düşünün")
        if typ == "archival_push" and d > 7.0:
            warn.append(f"{s['start']:6.1f} sn: tek fotoğrafta {d:.1f} sn kalınıyor — ikinci bir kare veya vurgu ekleyin")
        if img and img in last_img and s["start"] - last_img[img] < 45 and not img.endswith(".png"):
            warn.append(f"{s['start']:6.1f} sn: '{img}' {s['start'] - last_img[img]:.0f} sn önce de kullanıldı")
        if img:
            last_img[img] = s["start"]
    durs = [r[1] for r in rows]
    lines = ["# Görsel plan ve hikâye denetimi", "",
             f"Sahne: {len(rows)} · ortalama görsel değişimi {sum(durs) / len(durs):.1f} sn · en uzun {max(durs):.1f} sn", "",
             "| Zaman | Süre | Görsel türü | Kamera | Görsel | Sahnenin amacı |", "|---|---|---|---|---|---|"]
    for t0, d, typ, kat, cam, img, pur in rows:
        lines.append(f"| {int(t0 // 60)}:{t0 % 60:04.1f} | {d:.1f} | {kat} | {cam} | {img or '—'} | {pur} |")
    lines += ["", "## Bölüm başına merak unsuru", ""]
    for c in ch_order:
        n = merak.get(c, 0)
        lines.append(f"- {c}: {n}" + ("  ⚠ merak unsuru yok" if n == 0 else ""))
    lines += ["", "## Uyarılar", ""] + ([f"- {w}" for w in warn] or ["- Yok"])
    md = "\n".join(lines)
    if out:
        open(out, "w", encoding="utf-8").write(md)
    return md, warn


if __name__ == "__main__":
    md, w = main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(md[-2500:])
