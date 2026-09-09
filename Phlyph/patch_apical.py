#!/usr/bin/env python3
"""
Phylph / Phlyph: retire Retroflex as a place of articulation; add APICAL radical.

Retroflex consonants are re-analysed as apical post-alveolars:
    old:  place=retroflex  -> stroke 12  (the /\ chevron)
    new:  place=post-alveolar -> stroke 6, PLUS articulator=apical -> stroke 25

Stroke 25 is a full-height vertical rail at the right edge of the glyph box,
matching the supplied 8x8 bitmap (rightmost column, all eight rows).

Run from inside the Phlyph/ directory.
"""

import re, json, math, sys, pathlib

DATA_FILES = ["consonants.html", "lab.html", "slate.html", "mouthmap.html", "vowels.html"]

# ---------------------------------------------------------------- geometry --
# The house style: a stroke is a stadium (rounded-rect) outline around a
# centreline, sampled at 33 points per semicircular cap.  Verified to
# reproduce every existing stroke byte-for-byte.

def _f(v):
    return f"{v:.2f}"

def vbar(cx, y0, y1, w, N=32):
    r = w / 2.0
    P = []
    for k in range(N + 1):                       # bottom cap, left -> right
        a = k * math.pi / N
        P.append((cx - r * math.cos(a), y1 + r * math.sin(a)))
    for k in range(N + 1):                       # top cap, right -> left
        a = k * math.pi / N
        P.append((cx + r * math.cos(a), y0 - r * math.sin(a)))
    P.append(P[0])
    return "M" + " ".join(f"{_f(x)},{_f(y)}" for x, y in P) + "Z"

# Existing verticals sit at x = 13.125 / 50 / 86.875 with w = 15.625.
# The apical rail is half-width and pushed to x = 100 so it clears the
# post-alveolar bar (which ends at 94.69) instead of merging with it.
# The glyph viewBox is already "-6 -6 112 112", so it stays inside the canvas.
APICAL_ID = "25"
APICAL_CX = 102.0
APICAL_W  = 6.25
APICAL_Y0, APICAL_Y1 = 8.75, 91.25

APICAL_STROKE = vbar(APICAL_CX, APICAL_Y0, APICAL_Y1, APICAL_W)
APICAL_CENTER = {"d": f"M{_f(APICAL_CX)},{_f(APICAL_Y0)} {_f(APICAL_CX)},{_f(APICAL_Y1)}",
                 "w": round(APICAL_W, 2)}

# ------------------------------------------------------------------- data ---

RETRO = 12   # the stroke being retired
POSTALV = 6  # post-alveolar vertical
APICAL = 25

# old desc -> new desc
def redesc(d):
    return d.replace("retroflex", "apical post-alveolar")

def transform_data(D):
    changed = []

    # 1. new stroke ------------------------------------------------------
    D["strokes"][APICAL_ID] = APICAL_STROKE
    D["center"][APICAL_ID]  = APICAL_CENTER

    # 2. rewire every symbol that used the retroflex chevron -------------
    for ch, s in D["symbols"].items():
        if RETRO not in s["ids"]:
            continue
        s["ids"] = [POSTALV, APICAL] + [i for i in s["ids"] if i != RETRO]
        s["desc"] = redesc(s["desc"])
        comp = []
        for c in s["comp"]:
            if c["cat"] == "place" and c["val"] == "retroflex":
                comp.append({"cat": "place", "val": "post-alveolar", "ids": [POSTALV]})
                comp.append({"cat": "articulator", "val": "apical", "ids": [APICAL]})
            else:
                comp.append(c)
        s["comp"] = comp
        changed.append(ch)

    # 3. retroflex is no longer a place ----------------------------------
    D["place"].pop("Retroflex", None)

    # 4. apical becomes its own feature axis, like `lateral` -------------
    D["articulator"] = {"Apical": [APICAL]}

    # 5. surface it in the class filters ---------------------------------
    if not any(c[1] == "articulator" for c in D["classes"]):
        D["classes"].append(["Apical", "articulator", "apical"])

    return changed


def rewrite_data_blob(text):
    m = re.search(r"const DATA = (\{.*?\});\n", text, re.S)
    if not m:
        return text, []
    D = json.loads(m.group(1))
    changed = transform_data(D)
    new = "const DATA = " + json.dumps(D, ensure_ascii=False) + ";\n"
    return text[:m.start()] + new + text[m.end():], changed


# ------------------------------------------------------- acoustic tables ----
# Place lookup now returns post-alveolar for these sounds, which would make
# them sound identical to /ʃ ʒ/.  Re-apply the old retroflex targets as an
# apical override so the ʃ -> ʂ demo still contrasts audibly.

ACOUSTIC_OLD = """            locus:LOCUS[place]??1500, noiseHz:NOISE[place]??2500, lateral:has('lateral','lateral')};"""
ACOUSTIC_NEW = """            locus:(has('articulator','apical')?APICAL_LOCUS:LOCUS[place])??1500,
            noiseHz:(has('articulator','apical')?APICAL_NOISE:NOISE[place])??2500,
            lateral:has('lateral','lateral')};"""

NOISE_ANCHOR = """                 retroflex:2400,palatal:3200,velar:1900,uvular:1300,pharyngeal:1150,epiglottal:1000,glottal:1000};"""
NOISE_REPLACEMENT = """                 palatal:3200,velar:1900,uvular:1300,pharyngeal:1150,epiglottal:1000,glottal:1000};
  // apicality lowers F3 and the noise centroid regardless of place
  const APICAL_LOCUS = 1500, APICAL_NOISE = 2400;"""

LOCUS_ANCHOR = """                 retroflex:1500,palatal:2400,velar:1900,uvular:1250,pharyngeal:1100,epiglottal:1050,glottal:1500};"""
LOCUS_REPLACEMENT = """                 palatal:2400,velar:1900,uvular:1250,pharyngeal:1100,epiglottal:1050,glottal:1500};"""


def patch_acoustics(text):
    n = 0
    if LOCUS_ANCHOR in text:
        text = text.replace(LOCUS_ANCHOR, LOCUS_REPLACEMENT); n += 1
    if NOISE_ANCHOR in text:
        text = text.replace(NOISE_ANCHOR, NOISE_REPLACEMENT); n += 1
    if ACOUSTIC_OLD in text:
        text = text.replace(ACOUSTIC_OLD, ACOUSTIC_NEW); n += 1
    return text, n


# ------------------------------------------------------------ per-file -----

def patch_slate(text):
    # chart cells: fold the old retroflex column into post-alveolar
    text = text.replace(
        '"Plosive":{Bilabial:"b",Labiodental:"",Dental:"",Alveolar:"d",Retroflex:"ɖ",Palatal:"ɟ",Velar:"g",Uvular:"ɢ","Post-alveolar":"",Pharyngeal:"",Epiglottal:"",Glottal:"ʔ"},',
        '"Plosive":{Bilabial:"b",Labiodental:"",Dental:"",Alveolar:"d",Palatal:"ɟ",Velar:"g",Uvular:"ɢ","Post-alveolar":"ɖ",Pharyngeal:"",Epiglottal:"",Glottal:"ʔ"},')
    text = text.replace(
        '"Nasal":{Bilabial:"m",Labiodental:"ɱ",Alveolar:"n",Retroflex:"ɳ",Palatal:"ɲ",Velar:"ŋ",Uvular:"ɴ"},',
        '"Nasal":{Bilabial:"m",Labiodental:"ɱ",Alveolar:"n","Post-alveolar":"ɳ",Palatal:"ɲ",Velar:"ŋ",Uvular:"ɴ"},')
    text = text.replace(
        '"Flap":{Alveolar:"ɾ",Retroflex:"ɽ"},',
        '"Flap":{Alveolar:"ɾ","Post-alveolar":"ɽ"},')
    text = text.replace(
        '"Fricative":{Bilabial:"β",Labiodental:"v",Dental:"ð",Alveolar:"z","Post-alveolar":"ʒ",Retroflex:"ʐ",Palatal:"ʝ",Velar:"ɣ",Uvular:"ʁ",Pharyngeal:"ʕ",Glottal:"ɦ"},',
        '"Fricative":{Bilabial:"β",Labiodental:"v",Dental:"ð",Alveolar:"z","Post-alveolar":"ʒ",Palatal:"ʝ",Velar:"ɣ",Uvular:"ʁ",Pharyngeal:"ʕ",Glottal:"ɦ"},')
    text = text.replace(
        '"Approximant":{Labiodental:"ʋ",Alveolar:"ɹ",Retroflex:"ɻ",Palatal:"j",Velar:"ɰ"},',
        '"Approximant":{Labiodental:"ʋ",Alveolar:"ɹ","Post-alveolar":"ɻ",Palatal:"j",Velar:"ɰ"},')
    text = text.replace(
        '"Lateral":{Alveolar:"l",Retroflex:"ɭ",Palatal:"ʎ",Velar:"ʟ"},',
        '"Lateral":{Alveolar:"l","Post-alveolar":"ɭ",Palatal:"ʎ",Velar:"ʟ"},')

    # stroke key
    text = text.replace('11:"Fricative",12:"Retroflex",13:"Uvular",',
                        '11:"Fricative",13:"Uvular",')
    text = text.replace('23:"Lateral",24:"Syllable break (.)"};',
                        '23:"Lateral",24:"Syllable break (.)",25:"Apical"};')
    return text


def patch_lab(text):
    return text.replace(
        "const cats=['place','manner','voicing','backness','height','rounding','lateral','airstream'];",
        "const cats=['place','manner','articulator','voicing','backness','height','rounding','lateral','airstream'];")


def patch_mandarin(text):
    return text.replace(
        "t:'Retroflex / postalveolar — zh / ch / sh / r'",
        "t:'Apical post-alveolar — zh / ch / sh / r'")


# ----------------------------------------------------------------- main ----

def main():
    root = pathlib.Path(".")
    report = {}

    for name in DATA_FILES:
        p = root / name
        text = p.read_text(encoding="utf-8")
        text, changed = rewrite_data_blob(text)
        text, nac = patch_acoustics(text)
        if name == "slate.html":
            text = patch_slate(text)
        if name == "lab.html":
            text = patch_lab(text)
        p.write_text(text, encoding="utf-8")
        report[name] = (len(changed), nac)

    mp = root / "mandarin-sounds.html"
    if mp.exists():
        mp.write_text(patch_mandarin(mp.read_text(encoding="utf-8")), encoding="utf-8")

    print("stroke 25 (apical) added; retroflex place removed\n")
    for k, (nsym, nac) in report.items():
        print(f"  {k:<20} symbols rewired: {nsym}   acoustic edits: {nac}")


if __name__ == "__main__":
    main()
