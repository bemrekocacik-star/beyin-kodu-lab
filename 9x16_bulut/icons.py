#!/usr/bin/env python3
"""Beyin Kodu Lab v6.3 SVG ikon seti (Fleming eklemeleri). Palet: lacivert, beyaz, altın, turkuaz, kırmızı, yeşil.
python3 icons.py -> ic/*.png (600 px, şeffaf)"""
import os
from playwright.sync_api import sync_playwright

DEFS = """
<defs>
 <linearGradient id="gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFE866"/><stop offset=".55" stop-color="#FFD400"/><stop offset="1" stop-color="#C9A200"/></linearGradient>
 <linearGradient id="red" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FF6B66"/><stop offset="1" stop-color="#B71C1C"/></linearGradient>
 <linearGradient id="green" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6FF0A4"/><stop offset="1" stop-color="#1E9E56"/></linearGradient>
 <linearGradient id="turq" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8BEFF4"/><stop offset="1" stop-color="#1F8F96"/></linearGradient>
 <linearGradient id="steel" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#AEB8CC"/></linearGradient>
 <linearGradient id="navy" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2A3B66"/><stop offset="1" stop-color="#0B1530"/></linearGradient>
 <radialGradient id="glass" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#FFFFFF" stop-opacity=".85"/><stop offset=".5" stop-color="#DDEFF5" stop-opacity=".35"/><stop offset="1" stop-color="#9FC9D6" stop-opacity=".25"/></radialGradient>
 <radialGradient id="melon" cx=".4" cy=".35" r=".75"><stop offset="0" stop-color="#FFE98A"/><stop offset=".6" stop-color="#E8BE2A"/><stop offset="1" stop-color="#9C7A08"/></radialGradient>
 <filter id="sh" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#000" flood-opacity=".45"/></filter>
</defs>"""

I = {}
I["trash"] = """<g filter="url(#sh)">
<rect x="150" y="190" width="300" height="330" rx="26" fill="url(#steel)"/>
<rect x="125" y="140" width="350" height="56" rx="18" fill="url(#steel)" stroke="#8C97AE" stroke-width="4"/>
<rect x="250" y="105" width="100" height="40" rx="12" fill="none" stroke="#AEB8CC" stroke-width="14"/>
<g stroke="#8C97AE" stroke-width="16" stroke-linecap="round"><line x1="220" y1="240" x2="220" y2="470"/><line x1="300" y1="240" x2="300" y2="470"/><line x1="380" y1="240" x2="380" y2="470"/></g>
<path d="M165 205 L190 205 L190 505 L170 505 Z" fill="#fff" opacity=".5"/></g>"""
I["magnifier"] = """<g filter="url(#sh)">
<line x1="370" y1="370" x2="500" y2="500" stroke="url(#gold)" stroke-width="58" stroke-linecap="round"/>
<circle cx="260" cy="260" r="160" fill="url(#glass)" stroke="url(#gold)" stroke-width="34"/>
<path d="M170 210 A110 110 0 0 1 260 140" stroke="#fff" stroke-width="18" fill="none" stroke-linecap="round" opacity=".9"/></g>"""
I["suitcase"] = """<g filter="url(#sh)">
<rect x="225" y="120" width="150" height="70" rx="22" fill="none" stroke="#C9A200" stroke-width="24"/>
<rect x="100" y="180" width="400" height="300" rx="40" fill="url(#gold)"/>
<rect x="100" y="180" width="400" height="60" rx="30" fill="#FFE866" opacity=".5"/>
<rect x="175" y="180" width="34" height="300" fill="#0B1530" opacity=".55"/><rect x="391" y="180" width="34" height="300" fill="#0B1530" opacity=".55"/>
<rect x="150" y="480" width="40" height="30" rx="8" fill="#0B1530"/><rect x="410" y="480" width="40" height="30" rx="8" fill="#0B1530"/></g>"""
I["vial"] = """<g filter="url(#sh)">
<rect x="225" y="70" width="150" height="70" rx="14" fill="url(#red)"/>
<rect x="245" y="135" width="110" height="40" fill="#AEB8CC"/>
<path d="M200 175 H400 V500 Q400 540 360 540 H240 Q200 540 200 500 Z" fill="url(#glass)" stroke="#fff" stroke-width="10"/>
<path d="M210 330 H390 V500 Q390 530 360 530 H240 Q210 530 210 500 Z" fill="url(#gold)" opacity=".92"/>
<rect x="215" y="250" width="170" height="70" rx="8" fill="#fff"/>
<text x="300" y="298" font-family="Inter" font-weight="900" font-size="34" text-anchor="middle" fill="#0B1530">PENİSİLİN</text>
<rect x="225" y="190" width="22" height="300" rx="10" fill="#fff" opacity=".55"/></g>"""
I["helmet"] = """<g filter="url(#sh)">
<path d="M90 380 Q90 140 300 130 Q510 140 510 380 Z" fill="url(#navy)" stroke="#5B6C94" stroke-width="10"/>
<path d="M40 380 H560 Q560 420 520 425 H80 Q40 420 40 380 Z" fill="#2A3B66" stroke="#5B6C94" stroke-width="8"/>
<path d="M150 300 Q170 190 280 170" stroke="#fff" stroke-width="20" fill="none" opacity=".35" stroke-linecap="round"/>
<path d="M210 425 Q300 520 390 425" stroke="#AEB8CC" stroke-width="12" fill="none"/></g>"""
I["melon"] = """<g filter="url(#sh)">
<ellipse cx="300" cy="320" rx="230" ry="200" fill="url(#melon)"/>
<g stroke="#FFF5C4" stroke-width="7" fill="none" opacity=".75">
<path d="M120 250 Q200 280 160 360 Q240 330 260 420"/><path d="M220 160 Q240 240 320 230 Q330 300 420 300"/><path d="M360 160 Q390 220 460 230"/><path d="M300 470 Q340 420 420 430"/><path d="M110 320 Q150 300 190 320"/></g>
<rect x="285" y="105" width="30" height="40" rx="8" fill="#1E9E56"/></g>"""
I["mold"] = """<g filter="url(#sh)">
<path d="M300 560 V330" stroke="#8BEFF4" stroke-width="18"/>
<path d="M300 380 L220 300 M300 380 L380 300 M300 360 V280" stroke="#8BEFF4" stroke-width="14"/>
<g fill="url(#turq)">
<circle cx="220" cy="290" r="24"/><circle cx="200" cy="245" r="20"/><circle cx="185" cy="205" r="17"/><circle cx="173" cy="170" r="14"/>
<circle cx="380" cy="290" r="24"/><circle cx="400" cy="245" r="20"/><circle cx="415" cy="205" r="17"/><circle cx="427" cy="170" r="14"/>
<circle cx="300" cy="265" r="25"/><circle cx="300" cy="217" r="21"/><circle cx="300" cy="175" r="18"/><circle cx="300" cy="138" r="15"/><circle cx="300" cy="106" r="12"/>
</g><g fill="#fff" opacity=".6"><circle cx="292" cy="258" r="7"/><circle cx="212" cy="283" r="6"/><circle cx="372" cy="283" r="6"/></g></g>"""
I["chart"] = """<g filter="url(#sh)">
<rect x="90" y="400" width="80" height="120" rx="12" fill="url(#green)" opacity=".55"/>
<rect x="200" y="330" width="80" height="190" rx="12" fill="url(#green)" opacity=".7"/>
<rect x="310" y="240" width="80" height="280" rx="12" fill="url(#green)" opacity=".85"/>
<rect x="420" y="130" width="80" height="390" rx="12" fill="url(#green)"/>
<path d="M90 360 L230 270 L330 300 L470 120" stroke="url(#gold)" stroke-width="30" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M420 100 L500 90 L490 170 Z" fill="url(#gold)"/></g>"""
I["medal"] = """<g filter="url(#sh)">
<path d="M210 60 L260 250 L300 230 L250 60 Z" fill="url(#red)"/><path d="M390 60 L340 250 L300 230 L350 60 Z" fill="#B71C1C"/>
<circle cx="300" cy="370" r="170" fill="url(#gold)" stroke="#C9A200" stroke-width="12"/>
<circle cx="300" cy="370" r="128" fill="none" stroke="#FFF5C4" stroke-width="6" opacity=".8"/>
<text x="300" y="400" font-family="Inter" font-weight="900" font-size="78" text-anchor="middle" fill="#8A6E00">1945</text>
<path d="M190 300 A125 125 0 0 1 260 245" stroke="#fff" stroke-width="16" fill="none" opacity=".7" stroke-linecap="round"/></g>"""
I["xmark"] = """<g filter="url(#sh)"><circle cx="300" cy="300" r="230" fill="url(#red)"/>
<path d="M200 200 L400 400 M400 200 L200 400" stroke="#fff" stroke-width="56" stroke-linecap="round"/></g>"""
I["check"] = """<g filter="url(#sh)"><circle cx="300" cy="300" r="230" fill="url(#green)"/>
<path d="M185 310 L270 395 L425 215" stroke="#fff" stroke-width="56" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>"""
I["arrow"] = """<g filter="url(#sh)"><path d="M230 80 H370 V330 H470 L300 520 L130 330 H230 Z" fill="url(#gold)"/></g>"""
I["syringe"] = """<g filter="url(#sh)" transform="rotate(-35 300 300)">
<rect x="270" y="40" width="60" height="30" rx="8" fill="#AEB8CC"/><rect x="292" y="70" width="16" height="80" fill="#AEB8CC"/>
<rect x="215" y="140" width="170" height="24" rx="8" fill="#AEB8CC"/>
<rect x="240" y="160" width="120" height="280" rx="16" fill="url(#glass)" stroke="#fff" stroke-width="8"/>
<rect x="248" y="270" width="104" height="162" rx="10" fill="url(#gold)" opacity=".9"/>
<path d="M290 440 H310 V540 L300 575 L290 540 Z" fill="#DDE3EE"/></g>"""
I["shield"] = """<g filter="url(#sh)"><path d="M300 60 L500 130 V300 Q500 460 300 545 Q100 460 100 300 V130 Z" fill="url(#green)"/>
<path d="M300 100 L465 158 V300 Q465 430 300 505 Z" fill="#fff" opacity=".15"/>
<path d="M210 300 L280 370 L400 230" stroke="#fff" stroke-width="44" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g>"""

def main():
    os.makedirs("ic", exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 600, "height": 600})
        for k, v in I.items():
            pg.set_content(f'<html><body style="margin:0;background:transparent"><svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 600 600">{DEFS}{v}</svg></body></html>')
            pg.screenshot(path=f"ic/{k}.png", omit_background=True)
        b.close()
    print("ikon:", len(I))

if __name__ == "__main__":
    main()
