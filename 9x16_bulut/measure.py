import json, numpy as np, subprocess
def rd(p):
    b=subprocess.run(["ffmpeg","-v","error","-i",p,"-ac","1","-ar","16000","-f","s16le","-"],capture_output=True).stdout
    return np.frombuffer(b,np.int16).astype(np.float32)/32768
v=rd("v_proc.wav"); m=rd("bg_stem.wav"); n=min(len(v),len(m)); v,m=v[:n],m[:n]
W=json.load(open("kelimeler.json")); db=lambda x:10*np.log10(np.mean(x**2)+1e-12)
d=[db(v[int(w['s']*16000):int(w['e']*16000)])-db(m[int(w['s']*16000):int(w['e']*16000)]) for w in W]
print(f"konuşmada arka plan ortalama {np.mean(d):.1f} dB aşağıda, en kötü kelime {min(d):.1f} dB ('{W[int(np.argmin(d))]['w']}')")
r=subprocess.run(["ffmpeg","-hide_banner","-i","final_audio.wav","-af","ebur128=peak=true","-f","null","-"],capture_output=True,text=True).stderr
print([l.strip() for l in r.splitlines() if l.strip().startswith(("I:","Peak:"))][-2:])
