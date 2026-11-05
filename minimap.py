"""
Mini harita gorseli: uretilmis harita verisinden stilize kusbakisi doku cizer (oyunda calisma aninda
ekstra kamera/render yok; UI bu gorseli kaydirip dondurur).

Kullanim: python minimap.py <bolum> [piksel/metre]
Cikti:    Assets/_Game/Resources/Minimap/<bolum>.png  ve  <bolum>_meta.json (harita siniri)
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

from maps_config import MAPS

key = sys.argv[1] if len(sys.argv) > 1 else "merkez"
PPM = float(sys.argv[2]) if len(sys.argv) > 2 else 1.3
here = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(here, "..", "..", "Assets", "_Game", "Art", "Maps", MAPS[key]["folder"], f"{key}_map.json")
out_dir = os.path.join(here, "..", "..", "Assets", "_Game", "Resources", "Minimap")
os.makedirs(out_dir, exist_ok=True)

d = json.load(open(src, encoding="utf-8"))
x0, x1, z0, z1 = d["rect"]
W, H = int((x1 - x0) * PPM), int((z1 - z0) * PPM)

# Okunur, sade palet: koyu zemin, acik yollar, park yesili, tarihi yapilar kum rengi
PALETTE = {
    "Ground_Paved": (58, 62, 70), "Ground_Plaza": (78, 82, 90), "Ground_Parking": (66, 70, 78),
    "Ground_Grass": (62, 104, 66), "Ground_Forest": (52, 92, 58), "Ground_Water": (52, 120, 170),
    "Road": (196, 200, 208), "Sidewalk": (120, 124, 132), "Path": (150, 140, 118), "RailBed": (120, 124, 132),
    "Rail": (120, 124, 132), "Marking": (196, 200, 208),
    "Stone": (214, 186, 132), "Ruin": (170, 148, 112), "Dome": (214, 186, 132), "Brick": (214, 186, 132),
    "Turquoise": (70, 210, 210),
}
BUILDING = (34, 37, 44)

img = Image.new("RGB", (W, H), (58, 62, 70))
dr = ImageDraw.Draw(img)


def px(x, z):
    return ((x - x0) * PPM, (z1 - z) * PPM)


def draw_mesh(mesh, color_for, only_up=False):
    v = mesh["v"]
    for s in mesh["subs"]:
        col = color_for(s["mat"])
        if col is None:
            continue
        t = s["t"]
        for i in range(0, len(t), 3):
            a, b, c = (v[t[i] * 3:t[i] * 3 + 3], v[t[i + 1] * 3:t[i + 1] * 3 + 3], v[t[i + 2] * 3:t[i + 2] * 3 + 3])
            dr.polygon([px(a[0], a[2]), px(b[0], b[2]), px(c[0], c[2])], fill=col)


for tile in d["tiles"]:
    draw_mesh(tile["ground"], lambda m: PALETTE.get(m))
for tile in d["tiles"]:
    draw_mesh(tile["roads"], lambda m: PALETTE.get(m))
for tile in d["tiles"]:
    # tarihi yapilar renkli, digerleri koyu blok (camiler/turbeler haritada hemen secilsin)
    draw_mesh(tile["buildings"], lambda m: PALETTE.get(m, BUILDING) if m in ("Stone", "Ruin", "Dome", "Brick", "Turquoise") else BUILDING)

img = img.filter(ImageFilter.SMOOTH)
out_png = os.path.join(out_dir, f"{key}.png")
img.save(out_png, optimize=True)
with open(os.path.join(out_dir, f"{key}_meta.json"), "w", encoding="utf-8") as f:
    json.dump({"rect": [x0, x1, z0, z1], "pixelsPerMeter": PPM, "width": W, "height": H}, f)
# Simge yapilar: sahnede MapLandmarks yoksa oyun bunu calisma aninda yukler (gorev hedefleri, Konya Rehberi)
with open(os.path.join(out_dir, f"{key}_landmarks.json"), "w", encoding="utf-8") as f:
    json.dump({"landmarks": [l for l in d["landmarks"] if l.get("name")]}, f, ensure_ascii=False)
print(f"Mini harita: {W}x{H} px ({PPM} px/m) -> {os.path.normpath(out_png)} ({os.path.getsize(out_png) / 1e6:.2f} MB)")
