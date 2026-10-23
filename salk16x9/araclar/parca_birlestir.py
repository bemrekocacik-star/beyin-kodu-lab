"""Tarayicidan base64 parcalar halinde alinan gorselleri birlestirir.
Kullanim: python parca_birlestir.py ANAHTAR=cikti.jpg [ANAHTAR2=cikti2.jpg ...]
Parca bicimi: PIMG_<anahtar>_<sira>:<base64>:END (arac sonuclari + oturum kaydinda aranir)."""
import json, re, base64, glob, sys, os
ROOT = "/root/.claude/projects/-home-claude"
pat = re.compile(r'PIMG_(\w+?)_(\d+):([A-Za-z0-9+/=]+):END')
parts = {}
for f in glob.glob(ROOT + "/*/tool-results/*.txt"):
    try:
        t = json.load(open(f))[0]["text"]
    except Exception:
        continue
    for m in pat.finditer(t):
        parts[(m.group(1), int(m.group(2)))] = m.group(3)
for f in glob.glob(ROOT + "/*.jsonl"):
    for line in open(f, errors="ignore"):
        if "PIMG_" in line:
            for m in pat.finditer(line.replace("\\n", "")):
                parts.setdefault((m.group(1), int(m.group(2))), m.group(3))
for arg in sys.argv[1:]:
    k, out = arg.split("=", 1)
    idx = sorted(i for (kk, i) in parts if kk == k)
    if not idx or idx != list(range(len(idx))):
        print("EKSIK", k, idx); continue
    open(out, "wb").write(base64.b64decode("".join(parts[(k, i)] for i in idx)))
    print("tamam", k, len(idx), "parca ->", out, os.path.getsize(out))
