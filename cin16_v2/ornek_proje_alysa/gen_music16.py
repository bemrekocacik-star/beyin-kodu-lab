"""Alysa Liu 16:9 — bölüm ruh haline göre sentez müzik + az efekt (numpy, telifsiz)."""
import json, numpy as np, wave
TL = json.load(open('tl.json')); D = TL['total']; SR = 48000; n = int(SR * D); t = np.arange(n) / SR
I = {i['name']: i for i in TL['inserts']}
CH = lambda k: I[k]['start']
m = np.zeros(n, np.float32); fx = np.zeros(n, np.float32)
def env(a, b, fi=1.0, fo=1.0): return (np.clip((t - a) / fi, 0, 1) * np.clip((b - t) / fo, 0, 1)).astype(np.float32)
def note(at, f, dur=1.6, a=0.2, dec=2.5, harm=(1, .5, .25, .12)):
    i = int(at * SR); L = min(int(dur * SR), n - i)
    if L <= 0: return
    k = np.arange(L) / SR; w = sum(h * np.sin(2 * np.pi * f * (j + 1) * k) for j, h in enumerate(harm))
    m[i:i + L] += (a * w * np.exp(-k * dec) * np.clip(k / 0.01, 0, 1)).astype(np.float32)
def pad(a, b, freqs, g=0.05, lfo=0.15):
    e = env(a, b, 2.0, 2.0)
    for j, f in enumerate(freqs):
        m[:] += (g * e * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.003 * t)) * (1 + 0.25 * np.sin(2 * np.pi * lfo * t + j))).astype(np.float32)
def pulse(a, b, bpm, f=50, g=0.35):
    for bt in np.arange(a, b, 60 / bpm):
        i = int(bt * SR); L = int(0.14 * SR); k = np.arange(L) / SR
        if i + L < n: m[i:i + L] += (g * np.sin(2 * np.pi * f * k) * np.exp(-k * 26)).astype(np.float32)
def arp(a, b, chords, step, octv=2, g=0.07, dec=5):
    st = a; j = 0; span = (b - a) / max(1, len(chords))
    while st < b - 0.2:
        c = chords[min(int((st - a) / span), len(chords) - 1)]; note(st, c[j % len(c)] * octv, 1.0, g, dec); st += step; j += 1
Am = [220.0, 261.6, 329.6]; F = [174.6, 220.0, 261.6]; C = [261.6, 329.6, 392.0]; G = [196.0, 246.9, 293.7]; Em = [164.8, 196.0, 246.9]; Dm = [146.8, 174.6, 220.0]
# KANCA: karanlık + gerilim
pad(0, CH('baslik') + 0.5, [55, 82.4, 110], 0.05); pulse(0.5, I['birak']['start'] - 0.3, 64, 48, 0.28); pulse(I['birak']['start'] + 1.6, CH('baslik'), 76, 48, 0.25)
for k, at in enumerate([20.3, 26.0, 31.0, 36.5]): note(at, [220, 196, 174.6, 164.8][k], 3.0, 0.08, 1.0)
# BAŞLIK: açılış vuruşu + umut akoru
note(CH('baslik'), 55, 3.5, 0.5, 1.4, (1, .3)); pad(CH('baslik'), CH('1') + 4, [130.8, 164.8, 196.0], 0.05)
# B1 merak: piyano arpeji
arp(CH('1') + 4.5, CH('2') - 0.5, [Am, F, C, G, Am, F, C, G] * 3, 0.36, 2, 0.06, 4.5); pad(CH('1') + 4, CH('2'), [110, 164.8], 0.025)
# B2 gerilim: kalp atışı + koyu pad
pad(CH('2'), CH('3'), [55, 65.4, 82.4], 0.05); pulse(CH('2') + 5.5, CH('3') - 2.0, 70, 46, 0.3)
arp(CH('2') + 6, CH('3') - 1.5, [Dm, Am, Em, Am], 0.9, 2, 0.04, 2.5)
# B3 sakin: yumuşak pad + seyrek notalar
pad(CH('3'), CH('4'), [196.0, 246.9, 293.7], 0.035, 0.08)
for at in np.arange(CH('3') + 6, CH('4') - 2, 2.4): note(at, [392, 440, 493.9, 587.3][int(at) % 4], 2.2, 0.05, 1.6)
# B4 umut: yükselen arpej + hafif ritim
arp(CH('4') + 5.5, CH('5') - 0.5, [C, G, Am, F, C, G, F, G], 0.28, 2, 0.06, 5); pulse(I['kendim']['start'] + 1.5, CH('5') - 1.0, 92, 55, 0.22)
pad(CH('4') + 5, CH('5'), [130.8, 196.0, 261.6], 0.03)
# B5 Milano: inşa + zirve
pad(CH('5'), I['sampiyon']['start'] + 5, [110, 164.8, 220], 0.045); pulse(CH('5') + 6, I['sampiyon']['start'] - 13, 84, 52, 0.25)
arp(CH('5') + 6, I['sampiyon']['start'], [Am, F, C, G], 0.24, 2, 0.05, 5)
x = np.clip((t - (I['sampiyon']['start'] - 14)) / 13.5, 0, 1); m += (0.06 * env(I['sampiyon']['start'] - 14, I['sampiyon']['start'] - 0.5, 1, 0.1) * np.sin(2 * np.pi * (180 + 500 * x ** 2) * t) * x).astype(np.float32)
note(I['sampiyon']['start'] - 13.6, 55, 3.0, 0.45, 1.5, (1, .3))  # puan açıklanma
for j, f in enumerate([261.6, 329.6, 392.0, 523.3]): note(I['sampiyon']['start'] + 0.15 * j, f, 5.0, 0.10, 0.5)  # zafer akoru
pad(I['sampiyon']['start'], CH('6'), [130.8, 164.8, 196.0, 261.6], 0.05)
# B6 dersler + kod: düşünceli
pad(CH('6'), TL['total'], [110, 164.8, 220], 0.035, 0.07)
arp(CH('6') + 6, TL['voice_end_final'] - 12, [Am, F, C, Em], 0.72, 2, 0.04, 2.0)
note(TL['voice_end_final'] - 12.6, 82.4, 3.0, 0.3, 1.2, (1, .3))  # Kod vuruşu
for at in np.arange(TL['voice_end_final'] + 0.6, TL['total'] - 3, 0.5): note(at, [261.6, 329.6, 392.0, 329.6][int(at * 2) % 4] * 2, 1.0, 0.045, 3)
# susma: Kod'dan 0.6 sn önce
kod = TL['voice_end_final'] - 12.6; m *= np.where((t > kod - 0.8) & (t < kod), 0.15, 1.0).astype(np.float32)
# V2: BIRAKMAK sahnesinde kontrollü müzik düşüşü
SN = TL['sent']; b0 = SN[64]['s'] - 0.6
m *= (1 - 0.7 * env(b0, SN[65]['s'] + 0.3, 0.5, 0.8)).astype(np.float32)
m *= env(0, D, 0.3, 3.0)
# EFEKT: bölüm kartlarında yumuşak whoosh + 2 vuruş
def whoosh(at, dur=0.9, a=0.10):
    i = int(at * SR); L = int(dur * SR); k = np.arange(L) / L; no = np.random.default_rng(int(at * 10)).normal(0, 1, L)
    no = np.convolve(no, np.ones(60) / 60, 'same'); fx[i:i + L] += (a * no * np.sin(np.pi * k) ** 2).astype(np.float32)
for k in ('1', '2', '3', '4', '5', '6'): whoosh(CH(k) - 0.3)
def thud(at, a=0.4, f=60):
    i = int(at * SR); L = int(0.6 * SR); k = np.arange(L) / SR; fx[i:i + L] += (a * np.sin(2 * np.pi * f * k) * np.exp(-k * 10)).astype(np.float32)
thud(I['birak']['start'] - 0.55, 0.45)
# V2: HIZ / ADRENALİN / KONTROL vurguları
whoosh(SN[91]['s'] - 0.4, 0.5, 0.07); thud(SN[92]['s'] + 0.1, 0.3, 70); whoosh(SN[93]['s'] - 0.2, 0.4, 0.05)
# lowpass ~9 kHz (basit)
from scipy.signal import butter, sosfilt
sos = butter(4, 9000, 'low', fs=SR, output='sos'); m = sosfilt(sos, m).astype(np.float32)
def wr(f, x):
    w = wave.open(f, 'w'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
wr('music.wav', m * 0.9); wr('fx.wav', fx)
print('ok', round(D, 2))
