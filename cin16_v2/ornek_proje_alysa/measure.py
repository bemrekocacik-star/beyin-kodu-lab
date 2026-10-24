import json,numpy as np,wave,subprocess,re,sys
def rd(f):
    w=wave.open(f); x=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(float)/32768; return x.reshape(-1,w.getnchannels()).mean(1),w.getframerate()
v,sr=rd("v_norm.wav"); b,_=rd("bg_only.wav"); m=min(len(v),len(b)); v=v[:m]; b=b[:m]
W=json.load(open('kelimeler_final.json'))
sp=np.zeros(len(v),bool)
for w in W: sp[int(w['s']*sr):int(w['e']*sr)]=True
def db(x): return 20*np.log10(np.sqrt(np.mean(x**2))+1e-12)
r=sorted((db(v[int(w['s']*sr):int(w['e']*sr)])-db(b[int(w['s']*sr):int(w['e']*sr)]),w['w'],w['s']) for w in W if w['e']-w['s']>0.15)
end=W[-1]['e']; gap=~sp; gap[:int(0.3*sr)]=False; gap[int(end*sr):]=False
print(f"konuşma-arka plan: ort {db(v[sp])-db(b[sp]):.1f} dB, en kötü {r[0][0]:.1f} dB ({r[0][1]} {r[0][2]:.1f} sn)")
print(f"cümle arası arka plan: {db(b[gap]):.1f} dBFS")
