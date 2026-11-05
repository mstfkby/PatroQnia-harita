"""Uretilen harita JSON'undan kusbakisi onizleme PNG'si cizer (hata ayiklama icin).

Kullanim: python preview_map.py <bolum> [piksel/metre]
"""
import json
import os
import sys

from PIL import Image, ImageDraw

from maps_config import MAPS

key = sys.argv[1] if len(sys.argv) > 1 else "merkez"
S = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
here = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(here, "..", "..", "Assets", "_Game", "Art", "Maps", MAPS[key]["folder"], f"{key}_map.json")
d = json.load(open(src, encoding="utf-8"))
x0, x1, z0, z1 = d["rect"]
img = Image.new("RGB", (int((x1 - x0) * S), int((z1 - z0) * S)), (0, 0, 0))
dr = ImageDraw.Draw(img)


def px(x, z):
    return ((x - x0) * S, (z1 - z) * S)


def col(c, k=1.0):
    return tuple(int(max(0, min(1, v * k)) * 255) for v in c)


def collect(mesh, out, shade):
    v = mesh["v"]
    for s in mesh["subs"]:
        t = s["t"]
        base = {"pavement": 0.75, "asphalt": 0.3, "grass": 0.45, "gravel": 0.5, "stone": 0.78,
                "roof_tile": 0.6, "roof_flat": 0.68, "brick": 0.55, "shopfront": 0.5}.get(s["tex"], 1.0)
        c = s["c"] if s["tex"] in ("", "grass") else [ch * base for ch in s["c"]]
        if s["tex"] == "roof_tile":
            c = [0.71, 0.33, 0.2]
        if s["tex"] == "grass":
            c = [c[0] * 0.36, c[1] * 0.5, c[2] * 0.25]
        for i in range(0, len(t), 3):
            a, b, cc = (v[t[i] * 3:t[i] * 3 + 3], v[t[i + 1] * 3:t[i + 1] * 3 + 3], v[t[i + 2] * 3:t[i + 2] * 3 + 3])
            out.append((max(a[1], b[1], cc[1]) + shade, a, b, cc, c))


tris = []
for tile in d["tiles"]:
    for layer, shade in (("ground", 0), ("roads", 0.01), ("buildings", 0), ("trees", 0)):
        collect(tile[layer], tris, shade)
tris.sort(key=lambda r: r[0])
for h, a, b, c, cc in tris:
    dr.polygon([px(a[0], a[2]), px(b[0], b[2]), px(c[0], c[2])], fill=col(cc, 0.8 + 0.008 * h))
x, y, z = d["spawn"]
p = px(x, z)
dr.ellipse([p[0] - 5, p[1] - 5, p[0] + 5, p[1] + 5], fill=(255, 220, 60), outline=(0, 0, 0))
out = os.path.join(here, f"preview_{key}.png")
img.save(out)
print(out)
