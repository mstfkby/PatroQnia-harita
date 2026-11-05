"""
PatroQnia harita uretici: OpenStreetMap + yukseklik verisinden Unity icin hazir, parcali (tile) mesh verisi uretir.

Kullanim:  python fetch_data.py <bolum>    (ham veri, bir kez)
           python gen_textures.py          (dokular, bir kez)
           python build_map.py <bolum>     (varsayilan: merkez)
Bolumler:  maps_config.py
Cikti:     Assets/_Game/Art/Maps/<Klasor>/<bolum>_map.json

Koordinatlar: x = dogu, z = kuzey, y = yukari (metre), (0,0) = bolumun origin noktasi.
Veri kaynaklari: (c) OpenStreetMap katkicilari (ODbL), Copernicus EU-DEM.
"""
import hashlib
import json
import math
import os
import random
import sys

from maps_config import MAPS

CELL = 2.0          # zemin izgarasi cozunurlugu (m)
TILE = 128.0        # parca boyutu (m); CELL'in tam kati olmali
HEIGHT_SCALE = 1.0  # gercek yukseklik

# ---------------------------------------------------------------- malzemeler: ad -> (renk carpani, doku)
MAT = {
    # zemin
    "Ground_Paved":   ((0.80, 0.78, 0.74), "pavement"),
    "Ground_Grass":   ((1.00, 1.00, 1.00), "grass"),
    "Ground_Forest":  ((0.70, 0.78, 0.66), "grass"),
    "Ground_Water":   ((0.26, 0.46, 0.56), ""),
    "Ground_Plaza":   ((0.90, 0.88, 0.85), "pavement"),
    "Ground_Parking": ((1.00, 1.00, 1.00), "asphalt"),
    # yollar
    "Road":           ((1.00, 1.00, 1.00), "asphalt"),
    "Sidewalk":       ((0.80, 0.80, 0.80), "pavement"),
    "Curb":           ((0.74, 0.74, 0.72), ""),
    "Cornice":        ((0.93, 0.92, 0.89), ""),          # saçak, silme, denizlik, parapet: açık beton/sıva
    "AcUnit":         ((0.88, 0.89, 0.88), ""),          # klima dış ünitesi
    "AcGrille":       ((0.30, 0.31, 0.33), ""),          # klima pervane ızgarası
    # 7f bitki ortusu: cim obekleri ve cicek tarhlari (Konya parklarinin baharda lale tarhlari)
    "GrassTuft":      ((0.46, 0.68, 0.28), "leaves"),
    "GrassTuftDry":   ((0.56, 0.68, 0.30), "leaves"),
    "Soil":           ((0.40, 0.30, 0.22), "gravel"),
    "BedStone":       ((0.80, 0.79, 0.76), "stone"),
    "FlowerLeaf":     ((0.30, 0.52, 0.24), "leaves"),
    "FlowerRed":      ((0.86, 0.10, 0.10), ""),
    "FlowerYellow":   ((0.98, 0.80, 0.14), ""),
    "FlowerPink":     ((0.95, 0.42, 0.60), ""),
    "FlowerWhite":    ((0.96, 0.95, 0.92), ""),
    "FlowerPurple":   ((0.50, 0.22, 0.64), ""),          # bordur tasi: duz acik gri beton (Konya: gri bordur)
    "Path":           ((0.96, 0.90, 0.80), "pavement"),
    "RailBed":        ((1.00, 1.00, 1.00), "gravel"),
    "Rail":           ((0.58, 0.58, 0.62), ""),
    "Marking":        ((0.95, 0.95, 0.90), ""),
    # binalar
    "Facade_Window_Cream":  ((0.99, 0.93, 0.82), "facade_window"),
    "Facade_Window_White":  ((0.97, 0.97, 0.95), "facade_window"),
    "Facade_Window_Peach":  ((0.98, 0.85, 0.75), "facade_window"),
    "Facade_Window_Sand":   ((0.96, 0.89, 0.70), "facade_window"),
    "Facade_Balcony_Cream": ((0.99, 0.93, 0.82), "facade_balcony"),
    "Facade_Balcony_White": ((0.97, 0.97, 0.95), "facade_balcony"),
    "Facade_Balcony_Peach": ((0.98, 0.85, 0.75), "facade_balcony"),
    "Facade_Balcony_Sand":  ((0.96, 0.89, 0.70), "facade_balcony"),
    "Facade_Window_Grey":   ((0.84, 0.85, 0.86), "facade_window"),
    "Facade_Window_Salmon": ((0.97, 0.80, 0.68), "facade_window"),
    "Facade_Balcony_Grey":  ((0.84, 0.85, 0.86), "facade_balcony"),
    "Facade_Balcony_Salmon": ((0.97, 0.80, 0.68), "facade_balcony"),
    # Cam balkonlu apartman (Turkiye'de cok yaygin) ve modern is merkezi cepheleri
    "Facade_GlassBalcony_Cream":  ((0.99, 0.93, 0.82), "facade_glassbalcony"),
    "Facade_GlassBalcony_White":  ((0.97, 0.97, 0.95), "facade_glassbalcony"),
    "Facade_GlassBalcony_Peach":  ((0.98, 0.85, 0.75), "facade_glassbalcony"),
    "Facade_GlassBalcony_Sand":   ((0.96, 0.89, 0.70), "facade_glassbalcony"),
    "Facade_GlassBalcony_Grey":   ((0.84, 0.85, 0.86), "facade_glassbalcony"),
    "Facade_GlassBalcony_Salmon": ((0.97, 0.80, 0.68), "facade_glassbalcony"),
    "Facade_Modern_White":  ((0.95, 0.95, 0.94), "facade_modern"),
    "Facade_Modern_Grey":   ((0.78, 0.80, 0.82), "facade_modern"),
    "Shop":           ((1.00, 1.00, 1.00), "shopfront"),
    "ShopSign":       ((1.00, 1.00, 1.00), "shop_signs"),   # markasiz Turkce dukkan tabelalari (atlas)
    "RoofTile":       ((1.00, 1.00, 1.00), "roof_tile"),
    "RoofFlat":       ((1.00, 1.00, 1.00), "roof_flat"),
    "Stone":          ((1.00, 1.00, 1.00), "stone"),
    "Ruin":           ((0.80, 0.76, 0.70), "stone"),
    "Dome":           ((0.56, 0.59, 0.62), ""),
    "Brick":          ((1.00, 1.00, 1.00), "brick"),
    "Marble":         ((0.95, 0.94, 0.91), ""),           # Karatay tac kapisi: beyaz mermer
    "MarbleBlue":     ((0.52, 0.60, 0.70), ""),           #                     mavi-gri mermer bantlar
    "Turquoise":      ((0.10, 0.62, 0.62), ""),
    "Solar":          ((0.12, 0.17, 0.30), ""),
    "Tank":           ((0.92, 0.92, 0.92), ""),
    "RoofBox":        ((0.74, 0.73, 0.70), ""),
    "Metal":          ((0.42, 0.44, 0.47), ""),
    "Mast":           ((0.07, 0.29, 0.24), ""),       # Konya katener direkleri: koyu yesil
    "Wire":           ((0.05, 0.05, 0.05), ""),
    "Platform":       ((0.88, 0.87, 0.85), "pavement"),
    "ShelterRoof":    ((0.80, 0.82, 0.84), ""),
    "ShelterGlass":   ((0.30, 0.42, 0.46), ""),
    # agaclar
    # Yaprak/kabuk dokulari gri tonlu: renk tur basina malzemeden gelir (doku x renk)
    "Trunk":          ((0.62, 0.50, 0.40), "bark"),
    "Trunk_Pine":     ((0.72, 0.52, 0.40), "bark"),       # karacam: kizilimsi kabuk
    "Trunk_Poplar":   ((0.86, 0.86, 0.80), "bark"),       # kavak: acik gri-beyaz kabuk
    "Leaves_A":       ((0.36, 0.58, 0.27), "leaves"),     # cinar / ihlamur
    "Leaves_B":       ((0.45, 0.66, 0.30), "leaves"),     # acik, gunes alan
    "Leaves_C":       ((0.29, 0.49, 0.24), "leaves"),     # koyu
    "Leaves_D":       ((0.50, 0.62, 0.28), "leaves"),     # sarimsi yesil (akasya, dut)
    "Leaves_Pine":    ((0.20, 0.36, 0.26), "needles"),    # karacam: koyu mavimsi yesil
    "Leaves_Poplar":  ((0.47, 0.63, 0.33), "leaves"),     # kavak: gumussu acik yesil
    "Shrub":          ((0.33, 0.50, 0.26), "leaves"),
    # sokak donatisi
    "LampPole":       ((0.24, 0.26, 0.28), ""),
    "LampGlass":      ((1.00, 0.97, 0.88), ""),
    "BenchWood":      ((0.58, 0.38, 0.22), ""),
    "TrashBin":       ((0.24, 0.33, 0.28), ""),          # koyu yesil belediye cop kutusu
    "BusSign":        ((1.00, 1.00, 1.00), "bus_sign"),
    "StopGlass":      ((0.62, 0.74, 0.80), ""),          # durak cami: vitrin camindan acik, ayirt edilsin
    "StopRoof":       ((0.93, 0.94, 0.95), ""),
    "Facade_Stone":   ((1.00, 1.00, 1.00), "facade_stone"),   # Hukumet Konagi: kesme tas, sivri kemerli pencere
    "Column":         ((0.93, 0.90, 0.84), ""),
    "PoolWater":      ((0.30, 0.55, 0.66), ""),
    "Bronze":         ((0.62, 0.45, 0.24), ""),
    "FlagTR":         ((1.00, 1.00, 1.00), "flag_tr"),
}
WALL_COLORS = ("Cream", "White", "Peach", "Sand", "Grey", "Salmon")

ROAD_WIDTH = {
    "primary": 14, "primary_link": 9, "secondary": 11, "tertiary": 9, "residential": 7,
    "living_street": 6, "unclassified": 7, "service": 5, "pedestrian": 6,
    "footway": 2.5, "path": 2.5, "steps": 2.5, "cycleway": 2.5, "track": 3,
}
VEHICLE = {"primary", "primary_link", "secondary", "tertiary", "residential",
           "living_street", "unclassified", "service"}

# zemin ustu katmanlarin yuksekligi (z-fighting olmasin)
Y_SIDEWALK, Y_PATH, Y_ROAD, Y_RAILBED, Y_MARKING, Y_RAIL = 0.05, 0.08, 0.12, 0.16, 0.18, 0.20
Y_KERB = Y_ROAD + 0.15   # yukseltilmis kaldirim ust yuzu (yoldan 15 cm yukarida, 7b)
KERB_W = 2.5             # yolun iki yanindaki kaldirim genisligi (m)
CURB_W = 0.22            # bordur tasinin ust genisligi (m)

SHOP_H = 4.2   # zemin kat (dukkan) yuksekligi
FLOOR_H = 3.1  # ust kat yuksekligi


# ---------------------------------------------------------------- yardimcilar
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def qibla_dir(lat=37.8726, lon=32.4922):
    """Konya'dan Kabe'ye buyuk daire yonu, yerel (x=dogu, z=kuzey) birim vektor.
    Cami plani buna gore: mihrap duvari kibleye, giris (son cemaat yeri) karsi tarafa bakar."""
    p1, p2 = math.radians(lat), math.radians(21.4225)
    dl = math.radians(39.8262 - lon)
    b = math.atan2(math.sin(dl) * math.cos(p2), math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))
    return math.sin(b), math.cos(b)


QIBLA = qibla_dir()
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def stable_hash(x):
    return int(hashlib.md5(str(x).encode()).hexdigest()[:8], 16)


class MeshBuilder:
    """Duz golgelendirmeli mesh: her ucgen kendi vertexlerine sahip. uv=False ise UV yazilmaz."""

    def __init__(self, uv=True):
        self.v, self.uv, self.subs, self.with_uv = [], [], {}, uv
        self.ao_fn = None   # 7d: kose kararmasi (ambient occlusion) fonksiyonu (x, y, z) -> 0..1, ciktida hesaplanir

    def tri(self, mat, a, b, c, outward, uvs=None):
        if uvs is None:
            uvs = [(p[0] / 4.0, p[2] / 4.0) for p in (a, b, c)]
        ua, ub, uc = uvs
        # Unity on yuzu = cross(b-a, c-a) yonu. Disari bakmiyorsa sirayi cevir.
        if dot(cross(sub(b, a), sub(c, a)), outward) < 0:
            b, c, ub, uc = c, b, uc, ub
        base = len(self.v)
        self.v += [a, b, c]
        if self.with_uv:
            self.uv += [ua, ub, uc]
        self.subs.setdefault(mat, []).extend((base, base + 1, base + 2))

    def quad(self, mat, p0, p1, p2, p3, outward, uvs=None):
        if uvs is None:
            self.tri(mat, p0, p1, p2, outward)
            self.tri(mat, p0, p2, p3, outward)
        else:
            self.tri(mat, p0, p1, p2, outward, (uvs[0], uvs[1], uvs[2]))
            self.tri(mat, p0, p2, p3, outward, (uvs[0], uvs[2], uvs[3]))

    def add_strip(self, mat, left, right):
        """Seritte kesitler arasi vertexler paylasilir (yol/kaldirim icin ~3 kat az vertex)."""
        base = len(self.v)
        for lp, rp in zip(left, right):
            self.v += [lp, rp]
            if self.with_uv:
                self.uv += [(lp[0] / 4.0, lp[2] / 4.0), (rp[0] / 4.0, rp[2] / 4.0)]
        tris = self.subs.setdefault(mat, [])
        for i in range(len(left) - 1):
            a, b, c, d = base + 2 * i, base + 2 * i + 1, base + 2 * i + 2, base + 2 * i + 3
            pa, pb, pd = self.v[a], self.v[b], self.v[d]
            if cross(sub(pb, pa), sub(pd, pa))[1] >= 0:
                tris.extend((a, b, d, a, d, c))
            else:
                tris.extend((a, d, b, a, c, d))

    def add_rows(self, mat, row_a, row_b, uv_a, uv_b, normal):
        """Iki paralel kose dizisi arasinda paylasimli serit (kaldirim, bordur yuzu). Her dortgen 'normal' yonune bakar."""
        base = len(self.v)
        n = len(row_a)
        self.v += list(row_a) + list(row_b)
        if self.with_uv:
            self.uv += list(uv_a) + list(uv_b)
        tris = self.subs.setdefault(mat, [])
        for i in range(n - 1):
            a, b, c, d = base + i, base + i + 1, base + n + i, base + n + i + 1
            if dot(cross(sub(self.v[b], self.v[a]), sub(self.v[c], self.v[a])), normal) >= 0:
                tris.extend((a, b, c, b, d, c))
            else:
                tris.extend((a, c, b, b, c, d))

    def add_indexed(self, mat, verts, tris, uvs=None):
        """Paylasilan vertexli parca (yumusak golgelenir: agac tepeleri icin). uvs verilmezse ustten izdusum."""
        base = len(self.v)
        self.v += verts
        if self.with_uv:
            self.uv += uvs if uvs is not None else [(p[0] / 4.0, p[2] / 4.0) for p in verts]
        self.subs.setdefault(mat, []).extend(base + i for t in tris for i in t)

    def to_json(self):
        ao = [round(self.ao_fn(*p), 2) for p in self.v] if self.ao_fn else []
        if ao and min(ao) > 0.985:
            ao = []
        return {
            "ao": ao,
            "v": [round(c, 2) for p in self.v for c in p],
            "uv": [round(c, 3) for p in self.uv for c in p] if self.with_uv else [],
            "subs": [sub_json(m, t) for m, t in self.subs.items()],
        }


def sub_json(mat, tris):
    col, tex = MAT[mat]
    return {"mat": mat, "c": col, "tex": tex, "t": tris}


# ---------------------------------------------------------------- 2D geometri
def signed_area(poly):
    n = len(poly)
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))


def clean_poly(pts):
    out = []
    for p in pts:
        if not out or (abs(p[0] - out[-1][0]) > 0.05 or abs(p[1] - out[-1][1]) > 0.05):
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 0.05 and abs(out[0][1] - out[-1][1]) < 0.05:
        out.pop()
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 0.02:
                out.pop(i)
                changed = True
                break
    if len(out) >= 3 and signed_area(out) < 0:
        out.reverse()  # CCW
    return out


def point_in_tri(p, a, b, c):
    d1 = (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
    d2 = (p[0] - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (p[1] - c[1])
    d3 = (p[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (p[1] - a[1])
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def ear_clip(poly):
    idx = list(range(len(poly)))
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 5000:
        guard += 1
        found = False
        n = len(idx)
        for k in range(n):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % n]
            a, b, c = poly[i0], poly[i1], poly[i2]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 1e-9:
                continue
            if any(point_in_tri(poly[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            found = True
            break
        if not found:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    elif len(idx) > 3:
        tris += [(idx[0], idx[k], idx[k + 1]) for k in range(1, len(idx) - 1)]
    return tris


def point_in_poly(x, z, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, zi = poly[i]
        xj, zj = poly[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def seg_dist(px, pz, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dz * dz
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - a[0]) * dx + (pz - a[1]) * dz) / l2))
    return math.hypot(px - (a[0] + t * dx), pz - (a[1] + t * dz))


def poly_edge_dist(x, z, poly):
    return min(seg_dist(x, z, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def convex_hull(pts):
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts

    def half(points):
        h = []
        for p in points:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(p)
        return h

    lower, upper = half(pts), half(list(reversed(pts)))
    return lower[:-1] + upper[:-1]


def min_area_rect(pts):
    """En kucuk alanli dondurulmus dikdortgen: (merkez, uzun eksen, kisa eksen, yari uzunluk, yari genislik, alan)."""
    hull = convex_hull(pts)
    best = None
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1e-6:
            continue
        ux = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        uz = (-ux[1], ux[0])
        pu = [p[0] * ux[0] + p[1] * ux[1] for p in hull]
        pv = [p[0] * uz[0] + p[1] * uz[1] for p in hull]
        area = (max(pu) - min(pu)) * (max(pv) - min(pv))
        if best is None or area < best[0]:
            cu, cv = (max(pu) + min(pu)) / 2, (max(pv) + min(pv)) / 2
            center = (cu * ux[0] + cv * uz[0], cu * ux[1] + cv * uz[1])
            best = (area, center, ux, uz, (max(pu) - min(pu)) / 2, (max(pv) - min(pv)) / 2)
    area, center, ux, uz, hx, hz = best
    if hz > hx:  # ux hep uzun kenar boyunca
        ux, uz, hx, hz = uz, (-uz[0], -uz[1]), hz, hx
    return center, ux, uz, hx, hz, area


def resample(pts, step):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(math.ceil(L / step)))
        for k in range(1, n + 1):
            out.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    return out


def normalize_dem(dem):
    """Eski (kare, merkezli) ve yeni (dikdortgen) DEM bicimlerini ayni yapiya getirir."""
    if "n" in dem:
        n, size = dem["n"], dem["size"]
        return {"nx": n, "nz": n, "step": size / (n - 1), "x0": -size / 2, "z0": -size / 2, "heights": dem["heights"]}
    return dem


# ---------------------------------------------------------------- ana surec
def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "merkez"
    cfg = MAPS[key]
    here = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(here, "data", key)
    out_dir = os.path.join(here, "..", "..", "Assets", "_Game", "Art", "Maps", cfg["folder"])
    os.makedirs(out_dir, exist_ok=True)

    X0, X1, Z0, Z1 = cfg["rect"]
    lat0, lon0 = cfg["origin"]
    mlat = 111320.0
    mlon = 111320.0 * math.cos(math.radians(lat0))
    sanct_names = cfg.get("sanctuaries", [])

    osm = json.load(open(os.path.join(data_dir, "osm.json"), encoding="utf-8"))
    dem = normalize_dem(json.load(open(os.path.join(data_dir, "dem.json"), encoding="utf-8")))

    nodes = {e["id"]: ((e["lon"] - lon0) * mlon, (e["lat"] - lat0) * mlat)
             for e in osm["elements"] if e["type"] == "node"}
    ways = {e["id"]: e for e in osm["elements"] if e["type"] == "way"}
    relations = [e for e in osm["elements"] if e["type"] == "relation"]

    def osm_nodes_named(name):
        """Adi verilen OSM noktalarinin yerel koordinatlari (or. tramvay duragi)."""
        return [nodes[e["id"]] for e in osm["elements"] if e["type"] == "node" and e.get("tags", {}).get("name") == name and e["id"] in nodes]

    def way_pts(w):
        return [nodes[n] for n in w.get("nodes", []) if n in nodes]

    def is_closed(w):
        n = w.get("nodes", [])
        return len(n) > 3 and n[0] == n[-1]

    def inside_rect(x, z, margin=0.0):
        return X0 + margin <= x <= X1 - margin and Z0 + margin <= z <= Z1 - margin

    # ---------- yukseklik: DEM'den Catmull-Rom ile yumusak zemin
    NX, NZ, STEP, DX0, DZ0 = dem["nx"], dem["nz"], dem["step"], dem["x0"], dem["z0"]
    dmin = min(dem["heights"])
    D = [[(dem["heights"][j * NX + i] - dmin) * HEIGHT_SCALE for i in range(NX)] for j in range(NZ)]

    def cr(p0, p1, p2, p3, t):
        return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                      + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t)

    def dem_h(x, z):
        u, v = (x - DX0) / STEP, (z - DZ0) / STEP
        i, j = int(math.floor(u)), int(math.floor(v))
        tu, tv = u - i, v - j

        def g(ii, jj):
            return D[max(0, min(NZ - 1, jj))][max(0, min(NX - 1, ii))]

        rows = [cr(g(i - 1, jj), g(i, jj), g(i + 1, jj), g(i + 2, jj), tu) for jj in (j - 1, j, j + 1, j + 2)]
        return cr(rows[0], rows[1], rows[2], rows[3], tv)

    CW = int(round((X1 - X0) / CELL))   # hucre sayisi (x)
    CH = int(round((Z1 - Z0) / CELL))   # hucre sayisi (z)
    H = [[dem_h(X0 + i * CELL, Z0 + j * CELL) for i in range(CW + 1)] for j in range(CH + 1)]

    def ground_h(x, z):
        u = max(0.0, min(CW - 1e-6, (x - X0) / CELL))
        v = max(0.0, min(CH - 1e-6, (z - Z0) / CELL))
        i, j = int(u), int(v)
        tu, tv = u - i, v - j
        h0 = H[j][i] * (1 - tu) + H[j][i + 1] * tu
        h1 = H[j + 1][i] * (1 - tu) + H[j + 1][i + 1] * tu
        return h0 * (1 - tv) + h1 * tv

    # ---------- parcalar (tile): her parca kendi mesh'lerini tutar, kamera disindakiler cizilmez
    TC = int(TILE / CELL)
    TX, TZ = (CW + TC - 1) // TC, (CH + TC - 1) // TC
    tiles = {}

    def tile_key(x, z):
        return (max(0, min(TX - 1, int((x - X0) // TILE))), max(0, min(TZ - 1, int((z - Z0) // TILE))))

    def tile_mb(x, z, layer):
        t = tiles.setdefault(tile_key(x, z), {})
        if layer not in t:
            t[layer] = MeshBuilder(uv=(layer in ("buildings", "trees", "sidewalks", "details", "plants")))  # agaclar: yaprak/kabuk dokusu; kaldirim: bordur yuzleri
        return t[layer]

    # ---------- hucre maskeleri
    G_PAVED, G_GRASS, G_FOREST, G_WATER, G_PLAZA, G_PARKING = range(6)
    GROUND_MATS = ["Ground_Paved", "Ground_Grass", "Ground_Forest", "Ground_Water", "Ground_Plaza", "Ground_Parking"]
    cat = [[G_PAVED] * CW for _ in range(CH)]
    blocked = [[False] * CW for _ in range(CH)]   # bina altinda
    no_tree = [[False] * CW for _ in range(CH)]   # yol, patika, su, kutsal alan

    def cells_in_bbox(pts, pad):
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        i0 = max(0, int((min(xs) - pad - X0) / CELL))
        i1 = min(CW - 1, int((max(xs) + pad - X0) / CELL))
        j0 = max(0, int((min(zs) - pad - Z0) / CELL))
        j1 = min(CH - 1, int((max(zs) + pad - Z0) / CELL))
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                yield i, j, X0 + (i + 0.5) * CELL, Z0 + (j + 0.5) * CELL

    def fill_poly(pts, value, grid):
        if len(pts) >= 3:
            for i, j, x, z in cells_in_bbox(pts, 0):
                if point_in_poly(x, z, pts):
                    grid[j][i] = value

    def fill_line(pts, width, value, grid):
        r = width / 2.0
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            for i, j, x, z in cells_in_bbox([a, b], r):
                if seg_dist(x, z, a, b) <= r:
                    grid[j][i] = value

    def cell_of(x, z):
        i, j = int((x - X0) / CELL), int((z - Z0) / CELL)
        return (i, j) if 0 <= i < CW and 0 <= j < CH else None

    # 1) alanlar (buyukten kucuge)
    areas = []
    for w in ways.values():
        t = w.get("tags", {})
        if not is_closed(w):
            continue
        val = None
        if t.get("landuse") == "forest" or t.get("natural") == "wood":
            val = G_FOREST
        elif t.get("landuse") in ("grass", "meadow", "village_green") or t.get("leisure") in ("park", "garden"):
            val = G_GRASS
        elif t.get("natural") == "water" or t.get("amenity") == "fountain":
            val = G_WATER
        elif t.get("amenity") == "parking" and "building" not in t:
            val = G_PARKING
        elif t.get("highway") == "pedestrian" or t.get("area:highway") or t.get("place") == "square":
            val = G_PLAZA
        if val is not None:
            pts = clean_poly(way_pts(w))
            if len(pts) >= 3:
                areas.append((abs(signed_area(pts)), pts, val))
    for _, pts, val in sorted(areas, key=lambda a: -a[0]):
        fill_poly(pts, val, cat)
        if val == G_WATER:
            fill_poly(pts, True, no_tree)

    # 2) yol seritleri (parcalara bolunur) + altlarindaki zemin kaldirim olsun
    def strip(mat, pts, width, yoff, center_off=0.0, step=3.0):
        pts = resample(pts, step)
        if len(pts) < 2:
            return
        left, right = [], []
        for i, p in enumerate(pts):
            a = pts[max(0, i - 1)]
            b = pts[min(len(pts) - 1, i + 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dz) or 1.0
            nx, nz = -dz / L, dx / L  # sol normal
            cx, cz = p[0] + nx * center_off, p[1] + nz * center_off
            hw = width / 2
            lp = (cx + nx * hw, cz + nz * hw)
            rp = (cx - nx * hw, cz - nz * hw)
            left.append((lp[0], ground_h(*lp) + yoff, lp[1]))
            right.append((rp[0], ground_h(*rp) + yoff, rp[1]))
        # ardisik ayni parcadaki bolumleri tek seritte topla
        start = 0
        for k in range(len(pts) - 1):
            mid = ((pts[k][0] + pts[k + 1][0]) / 2, (pts[k][1] + pts[k + 1][1]) / 2)
            nxt = None
            if k + 1 < len(pts) - 1:
                nxt = ((pts[k + 1][0] + pts[k + 2][0]) / 2, (pts[k + 1][1] + pts[k + 2][1]) / 2)
            if nxt is None or tile_key(*nxt) != tile_key(*mid):
                if inside_rect(mid[0], mid[1]):
                    tile_mb(mid[0], mid[1], "roads").add_strip(mat, left[start:k + 2], right[start:k + 2])
                start = k + 1

    def dashes(pts, width, yoff, on=3.0, off=4.0):
        """Kesik serit cizgisi: her cizgi tek dortgen."""
        pts = resample(pts, 0.5)
        dist, start = 0.0, None
        for a, b in zip(pts, pts[1:]):
            drawing = (dist % (on + off)) < on
            if drawing and start is None:
                start = a
            elif not drawing and start is not None:
                strip("Marking", [start, a], width, yoff, step=99.0)
                start = None
            dist += math.hypot(b[0] - a[0], b[1] - a[1])
        if start is not None:
            strip("Marking", [start, pts[-1]], width, yoff, step=99.0)

    lines = []
    for w in ways.values():
        t = w.get("tags", {})
        hw = t.get("highway")
        pts = way_pts(w)
        if len(pts) < 2:
            continue
        if hw in ROAD_WIDTH and not (t.get("area") == "yes" and is_closed(w)):
            lines.append((hw, pts, ROAD_WIDTH[hw]))
        elif t.get("railway") == "tram":
            lines.append(("tram", pts, 3.2))

    for hw, pts, width in lines:
        if hw in VEHICLE:
            strip("Sidewalk", pts, width + 5.0, Y_SIDEWALK)
            fill_line(pts, width + 5.0, G_PAVED, cat)
            fill_line(pts, width + 5.0, True, no_tree)
        elif hw == "pedestrian":
            strip("Sidewalk", pts, width, Y_PATH)
            fill_line(pts, width, True, no_tree)
        elif hw != "tram":
            strip("Path", pts, width, Y_PATH, step=2.0)  # tepe patikalari egimli: daha sik ornekle
            fill_line(pts, width + 1.0, True, no_tree)
    for hw, pts, width in lines:
        if hw in VEHICLE:
            strip("Road", pts, width, Y_ROAD)
            if width >= 9:
                dashes(pts, 0.2, Y_MARKING)
    # 7b: YUKSELTILMIS KALDIRIM ve BORDUR. Arac yollarinin iki yaninda 2.5 m'lik bant, yoldan 15 cm yukarida;
    # yola bakan kenarda bordur tasi (ust serit + dikey yuz), dis kenarda zemine inen yuz. Baska bir yolun arac
    # seridine (kavsak) ya da tramvay yatagina dusen parcalar kesilir (orada yol duz devam eder), kesilen
    # yerde uc yuzu kapatilir. Carpisma: ayri "sidewalks" katmani (oyuncu ve yayalar kaldirimin ustunde yurur;
    # gezinme agi da kaldirimin ustunden gecer). Esyalar (lamba, durak, agac...) surface_h ile bandin ustune oturur.
    carriage_exact = [[False] * CW for _ in range(CH)]
    for hw, pts, width in lines:
        if hw in VEHICLE or hw == "tram":
            fill_line(pts, width, True, carriage_exact)
    kerb_quads = {}   # 4 m'lik izgara -> bant dortgenleri (xz koseleri): surface_h icin

    def kerb_add_lookup(quad):
        xs, zs = [q[0] for q in quad], [q[1] for q in quad]
        for gi in range(int(min(xs) // 4), int(max(xs) // 4) + 1):
            for gj in range(int(min(zs) // 4), int(max(zs) // 4) + 1):
                kerb_quads.setdefault((gi, gj), []).append(quad)

    def in_quad(x, z, quad):
        sign = 0
        for k in range(4):
            ax, az = quad[k]
            bx, bz = quad[(k + 1) % 4]
            c = (bx - ax) * (z - az) - (bz - az) * (x - ax)
            if abs(c) < 1e-9:
                continue
            sgn = 1 if c > 0 else -1
            if sign == 0:
                sign = sgn
            elif sgn != sign:
                return False
        return True

    def on_kerb(x, z):
        for quad in kerb_quads.get((int(x // 4), int(z // 4)), ()):
            if in_quad(x, z, quad):
                return True
        return False

    def surface_h(x, z):
        """Yurunen yuzeyin yuksekligi: kaldirim bandinin ustunde Y_KERB kadar yukarida, degilse zemin."""
        return ground_h(x, z) + (Y_KERB if on_kerb(x, z) else 0.0)

    def kerb_cut(x, z):
        c = cell_of(x, z)
        return c is None or carriage_exact[c[1]][c[0]]

    kerb_segments = 0

    def kerb_band(pts, width):
        pts = resample(pts, 3.0)
        if len(pts) < 2:
            return 0
        hw = width / 2.0
        frames = []
        for i, p in enumerate(pts):
            a = pts[max(0, i - 1)]
            b = pts[min(len(pts) - 1, i + 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dz) or 1.0
            frames.append((p, -dz / L, dx / L))
        made = 0
        for side in (1.0, -1.0):
            def edge(i, off):
                p, nx, nz = frames[i]
                return (p[0] + nx * off * side, p[1] + nz * off * side)

            def seg_ok(k):
                m0, m1 = edge(k, hw + KERB_W / 2), edge(k + 1, hw + KERB_W / 2)
                mx, mz = (m0[0] + m1[0]) / 2, (m0[1] + m1[1]) / 2
                return inside_rect(mx, mz) and not kerb_cut(mx, mz) and \
                    not kerb_cut(*edge(k, hw + KERB_W - 0.3)) and not kerb_cut(*edge(k + 1, hw + KERB_W - 0.3))

            k = 0
            while k < len(pts) - 1:
                if not seg_ok(k):
                    k += 1
                    continue
                k0 = k
                while k < len(pts) - 1 and seg_ok(k):
                    kerb_add_lookup([edge(k, hw), edge(k + 1, hw), edge(k + 1, hw + KERB_W), edge(k, hw + KERB_W)])
                    k += 1
                emit_run([edge(i, hw) for i in range(k0, k + 1)], [edge(i, hw + CURB_W) for i in range(k0, k + 1)],
                         [edge(i, hw + KERB_W) for i in range(k0, k + 1)])
                made += k - k0
        return made

    def emit_run(inner, curb, outer):
        """Kesintisiz kaldirim parcasi: bordur ust seridi, kaldirim, bordurun dikey yuzu, dis yuz, iki uc yuzu."""
        mid = inner[len(inner) // 2]
        mb = tile_mb(mid[0], mid[1], "sidewalks")
        along = [0.0]
        for a, b in zip(inner, inner[1:]):
            along.append(along[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))

        def row(q, y):
            return [(p[0], ground_h(p[0], p[1]) + y, p[1]) for p in q]

        up = (0.0, 1.0, 0.0)
        o = (outer[0][0] - inner[0][0], 0.0, outer[0][1] - inner[0][1])    # yoldan disari
        wuv = lambda q: [(p[0] / 4, p[1] / 4) for p in q]                 # dunya koordinatli: desen kesintisiz
        mb.add_rows("Curb", row(inner, Y_KERB), row(curb, Y_KERB), wuv(inner), wuv(curb), up)
        mb.add_rows("Sidewalk", row(curb, Y_KERB), row(outer, Y_KERB), wuv(curb), wuv(outer), up)
        luv0 = [(u / 2, 0.0) for u in along]
        luv1 = [(u / 2, 0.15) for u in along]
        mb.add_rows("Curb", row(inner, Y_ROAD - 0.03), row(inner, Y_KERB), luv0, luv1, (-o[0], 0.0, -o[2]))
        mb.add_rows("Sidewalk", row(outer, 0.0), row(outer, Y_KERB), luv0, luv1, o)
        end_cap(inner[0], outer[0])
        end_cap(inner[-1], outer[-1])

    def end_cap(a, b):
        """Kesilen kaldirim ucunu kapatan dikey yuz (iki yone bakan iki dortgen: hangi yandan bakilirsa gorunur)."""
        mb = tile_mb(a[0], a[1], "sidewalks")
        dx, dz = b[0] - a[0], b[1] - a[1]
        n1 = (-dz, 0.0, dx)
        pa0 = (a[0], ground_h(*a) + Y_ROAD - 0.03, a[1])
        pb0 = (b[0], ground_h(*b) + Y_ROAD - 0.03, b[1])
        pa1 = (a[0], ground_h(*a) + Y_KERB, a[1])
        pb1 = (b[0], ground_h(*b) + Y_KERB, b[1])
        uvs = [(0.0, 0.0), (1.25, 0.0), (1.25, 0.07), (0.0, 0.07)]
        mb.quad("Curb", pa0, pb0, pb1, pa1, n1, uvs)
        mb.quad("Curb", pa0, pb0, pb1, pa1, (-n1[0], 0.0, -n1[2]), uvs)

    for hw, pts, width in lines:
        if hw in VEHICLE:
            kerb_segments += kerb_band(pts, width)

    for hw, pts, width in lines:
        if hw == "tram":
            strip("RailBed", pts, width, Y_RAILBED)
            strip("Rail", pts, 0.12, Y_RAIL, center_off=0.72)
            strip("Rail", pts, 0.12, Y_RAIL, center_off=-0.72)
            fill_line(pts, width, True, no_tree)

    # ---------- binalar (yazim hedefi: binanin bulundugu parca)
    target = {"mb": None}
    landmarks = []

    def mb():
        return target["mb"]

    def wall(mat, a, b, y_bot, y_top, u0, u_per_m, v_base, v_per_m):
        dx, dz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dz)
        out = (dz, 0.0, -dx)  # CCW poligonda disari = sag taraf
        u1 = u0 + L * u_per_m
        # 7d: zemine degen uzun duvar dipten 2.6 m'de bolunur: dip kararmasi (AO) o seritte yogunlassin
        ys = [y_bot, y_top]
        gz = min(ground_h(*a), ground_h(*b))
        if y_bot < gz + 0.8 and y_top - y_bot > 3.4:
            ys = [y_bot, gz + 2.6, y_top]
        for y0_, y1_ in zip(ys, ys[1:]):
            vb, vt = (y0_ - v_base) * v_per_m, (y1_ - v_base) * v_per_m
            mb().quad(mat, (a[0], y0_, a[1]), (b[0], y0_, b[1]), (b[0], y1_, b[1]), (a[0], y1_, a[1]), out,
                      [(u0, vb), (u1, vb), (u1, vt), (u0, vt)])

    def walls_around(pts, mat, y_bot, y_top, u_per_m=1 / 4.0, v_per_m=1 / 4.0, v_base=0.0):
        u = 0.0
        for k in range(len(pts)):
            a, c = pts[k], pts[(k + 1) % len(pts)]
            wall(mat, a, c, y_bot, y_top, u, u_per_m, v_base, v_per_m)
            u += math.hypot(c[0] - a[0], c[1] - a[1]) * u_per_m

    def flat_roof(pts, y, mat, uv_scale=4.0):
        for i0, i1, i2 in ear_clip(pts):
            ps = [(pts[k][0], y, pts[k][1]) for k in (i0, i1, i2)]
            mb().tri(mat, ps[0], ps[1], ps[2], (0, 1, 0), [(p[0] / uv_scale, p[2] / uv_scale) for p in ps])

    def hip_roof(rect, y):
        center, ux, uz, hx, hz, _ = rect
        o = 0.35  # sacak tasmasi
        hx, hz = hx + o, hz + o
        rise = min(hz * 0.6, 3.2)

        def P(a, b, h):
            return (center[0] + ux[0] * a + uz[0] * b, y + h, center[1] + ux[1] * a + uz[1] * b)

        c_pp, c_mp, c_mm, c_pm = P(hx, hz, 0), P(-hx, hz, 0), P(-hx, -hz, 0), P(hx, -hz, 0)
        ridge = max(0.0, hx - hz)
        r1, r2 = P(ridge, 0, rise), P(-ridge, 0, rise)

        def uvs_for(points, eave_dir, slope_dir):
            return [((p[0] * eave_dir[0] + p[2] * eave_dir[1]) / 1.6,
                     -(p[0] * slope_dir[0] + p[2] * slope_dir[1]) / 1.1) for p in points]

        up = 0.8
        for side, (e0, e1) in ((1, (c_pp, c_mp)), (-1, (c_mm, c_pm))):
            out = (uz[0] * side, up, uz[1] * side)
            pts = [e0, e1, r2, r1] if side == 1 else [e0, e1, r1, r2]
            mb().quad("RoofTile", *pts, out, uvs_for(pts, ux, (uz[0] * side, uz[1] * side)))
        for side, (e0, e1, r) in ((1, (c_pm, c_pp, r1)), (-1, (c_mp, c_mm, r2))):
            out = (ux[0] * side, up, ux[1] * side)
            pts = [e0, e1, r]
            mb().tri("RoofTile", *pts, out, uvs_for(pts, uz, (ux[0] * side, ux[1] * side)))

    def box(mat, cx, cz, y0, sx, sy, sz, yaw=0.0):
        cs, sn = math.cos(yaw), math.sin(yaw)

        def P(a, h, b):
            return (cx + a * cs - b * sn, y0 + h, cz + a * sn + b * cs)

        hx, hz = sx / 2, sz / 2
        c = [P(-hx, 0, -hz), P(hx, 0, -hz), P(hx, 0, hz), P(-hx, 0, hz)]
        t = [P(-hx, sy, -hz), P(hx, sy, -hz), P(hx, sy, hz), P(-hx, sy, hz)]
        u = 0.0
        for k in range(4):
            a, b = c[k], c[(k + 1) % 4]
            mid = ((a[0] + b[0]) / 2 - cx, 0, (a[2] + b[2]) / 2 - cz)
            L = math.hypot(b[0] - a[0], b[2] - a[2])
            # Yan yuz UV'si: cevre boyunca ve yukseklik yonunde (4 m'de bir tekrar): doku dikey cizgilere gerilmesin
            mb().quad(mat, a, b, t[(k + 1) % 4], t[k], mid,
                      [(u / 4.0, y0 / 4.0), ((u + L) / 4.0, y0 / 4.0), ((u + L) / 4.0, (y0 + sy) / 4.0), (u / 4.0, (y0 + sy) / 4.0)])
            u += L
        mb().quad(mat, t[0], t[1], t[2], t[3], (0, 1, 0))

    def solar_heater(cx, cz, y):
        """Turk catilarinin vazgecilmezi: gunes enerjili sofben (panel + depo), panel guneye bakar."""
        tilt = math.radians(35)
        depth, width = 1.3, 2.0
        zf = cz - depth * math.cos(tilt) / 2
        zb = cz + depth * math.cos(tilt) / 2
        y_low, y_high = y + 0.35, y + 0.35 + depth * math.sin(tilt)
        mb().quad("Solar", (cx - width / 2, y_low, zf), (cx + width / 2, y_low, zf),
                  (cx + width / 2, y_high, zb), (cx - width / 2, y_high, zb), (0, math.cos(tilt), -math.sin(tilt)))
        box("Tank", cx, zb + 0.35, y_high - 0.1, width * 0.95, 0.5, 0.5)
        box("RoofBox", cx, zf + 0.2, y, width * 0.9, 0.35, 0.25)

    def satellite_dish(cx, cz, y, r):
        """Canak anten: gune-guneydoguya (uydu kusagina) ~35 derece yukari bakan sig koni + kisa direk."""
        box("Metal", cx, cz, y, 0.08, 0.7, 0.08)
        az, el = math.radians(160.0), math.radians(35.0)          # kuzeyden saat yonu: guney-guneydogu
        nrm = (math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))
        up = (0.0, 1.0, 0.0)
        e1 = cross(up, nrm)
        L1 = math.sqrt(dot(e1, e1)) or 1.0
        e1 = (e1[0] / L1, e1[1] / L1, e1[2] / L1)
        e2 = cross(nrm, e1)
        c = (cx, y + 0.85, cz)
        segs = 10
        rim = [(c[0] + r * (math.cos(2 * math.pi * k / segs) * e1[0] + math.sin(2 * math.pi * k / segs) * e2[0]),
                c[1] + r * (math.cos(2 * math.pi * k / segs) * e1[1] + math.sin(2 * math.pi * k / segs) * e2[1]),
                c[2] + r * (math.cos(2 * math.pi * k / segs) * e1[2] + math.sin(2 * math.pi * k / segs) * e2[2])) for k in range(segs)]
        back = (c[0] - nrm[0] * r * 0.35, c[1] - nrm[1] * r * 0.35, c[2] - nrm[2] * r * 0.35)
        for k in range(segs):
            a, b = rim[k], rim[(k + 1) % segs]
            mb().tri("Tank", a, b, back, nrm)                    # on yuz (canak ici)
            mb().tri("Tank", a, b, back, (-nrm[0], -nrm[1], -nrm[2]))  # arka yuz

    def tv_antenna(cx, cz, y, rnd):
        """Eski tip TV anteni: ince direk + kisa yatay cubuklar."""
        h = 2.2 + rnd.random() * 1.2
        box("Metal", cx, cz, y, 0.05, h, 0.05)
        yaw = rnd.random() * math.pi
        for k in range(3):
            box("Metal", cx, cz, y + h - 0.25 - k * 0.3, 1.1 - k * 0.25, 0.03, 0.03, yaw)

    def random_point_inside(pts, margin, rnd):
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        for _ in range(20):
            x = rnd.uniform(min(xs), max(xs))
            z = rnd.uniform(min(zs), max(zs))
            if point_in_poly(x, z, pts) and poly_edge_dist(x, z, pts) > margin:
                return x, z
        return None

    def ring(cx, cz, y, r, segs, phase=0.0):
        return [(cx + r * math.cos(phase + 2 * math.pi * s / segs), y, cz + r * math.sin(phase + 2 * math.pi * s / segs))
                for s in range(segs)]

    def cylinder(cx, cz, y0, y1, r, segs, mat, radii=None, uv_scale=3.0):
        rs = radii or [r] * segs
        bottom = [(cx + rs[s] * math.cos(2 * math.pi * s / segs), y0, cz + rs[s] * math.sin(2 * math.pi * s / segs)) for s in range(segs)]
        top = [(p[0], y1, p[2]) for p in bottom]
        for s in range(segs):
            a, b = bottom[s], bottom[(s + 1) % segs]
            out = ((a[0] + b[0]) / 2 - cx, 0, (a[2] + b[2]) / 2 - cz)
            mb().quad(mat, a, b, top[(s + 1) % segs], top[s], out,
                      [(s * 0.4, y0 / uv_scale), ((s + 1) * 0.4, y0 / uv_scale), ((s + 1) * 0.4, y1 / uv_scale), (s * 0.4, y1 / uv_scale)])
        return top

    def cone(base, tip, mat):
        n = len(base)
        cx = sum(p[0] for p in base) / n
        cz = sum(p[2] for p in base) / n
        for s in range(n):
            a, b = base[s], base[(s + 1) % n]
            out = ((a[0] + b[0]) / 2 - cx, 0.6, (a[2] + b[2]) / 2 - cz)
            mb().tri(mat, a, b, tip, out)

    def cap(top, mat):
        n = len(top)
        c = (sum(p[0] for p in top) / n, top[0][1], sum(p[2] for p in top) / n)
        for s in range(n):
            mb().tri(mat, c, top[s], top[(s + 1) % n], (0, 1, 0))

    def alem(cx, cz, y):
        cylinder(cx, cz, y, y + 1.2, 0.07, 4, "Turquoise")

    def dome(cx, cz, base_y, r, mat="Dome", segs=14, rings=5):
        cylinder(cx, cz, base_y - r * 0.35, base_y, r, segs, "Stone")  # kasnak
        rows = [ring(cx, cz, base_y + r * math.sin((math.pi / 2) * k / rings) * 0.95,
                     r * math.cos((math.pi / 2) * k / rings), segs) for k in range(rings + 1)]
        center = (cx, base_y, cz)
        for k in range(rings):
            for s in range(segs):
                p0, p1 = rows[k][s], rows[k][(s + 1) % segs]
                p2, p3 = rows[k + 1][(s + 1) % segs], rows[k + 1][s]
                mid = ((p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2, (p0[2] + p2[2]) / 2)
                mb().quad(mat, p0, p1, p2, p3, sub(mid, center))
        alem(cx, cz, base_y + r * 0.95)

    def minaret(cx, cz, y0, height, body_mat, r=1.3, segs=10, cap_mat="Turquoise", cap_h=4.5):
        y_bal = y0 + height - 4.0   # serefe
        y_top = y0 + height
        cylinder(cx, cz, y0, y_bal, r, segs, body_mat)
        cap(cylinder(cx, cz, y_bal, y_bal + 0.6, r * 1.45, segs, "Stone"), "Stone")
        top = cylinder(cx, cz, y_bal + 0.6, y_top, r * 0.9, segs, body_mat)
        cone(top, (cx, y_top + cap_h, cz), cap_mat)
        alem(cx, cz, y_top + cap_h)

    def kumbet(pts, y0, y1, roof_mat):
        """Selcuklu kumbeti (turbe): cokgen tas govde + konik cati."""
        walls_around(pts, "Stone", y0, y1)
        cx = sum(p[0] for p in pts) / len(pts)
        cz = sum(p[1] for p in pts) / len(pts)
        r = max(math.hypot(p[0] - cx, p[1] - cz) for p in pts)
        base = ring(cx, cz, y1, r * 1.05, 8, math.pi / 8)
        cone(base, (cx, y1 + r * 1.3, cz), roof_mat)

    def yesil_kubbe(cx, cz, y_roof):
        """Mevlana Turbesi'nin Kubbe-i Hadra'si: oluklu turkuaz govde + sivri konik kulah."""
        segs = 16
        radii = [4.2 if s % 2 == 0 else 3.75 for s in range(segs)]  # oluklar
        top = cylinder(cx, cz, y_roof, y_roof + 8.0, 4.2, segs, "Turquoise", radii=radii)
        ring_top = [(cx + radii[s] * 1.08 * math.cos(2 * math.pi * s / segs), y_roof + 8.0,
                     cz + radii[s] * 1.08 * math.sin(2 * math.pi * s / segs)) for s in range(segs)]
        cone(ring_top, (cx, y_roof + 16.0, cz), "Turquoise")
        alem(cx, cz, y_roof + 16.0)
        _ = top

    # ---------- ozel simge yapilar (kaynak: tr.wikipedia, TDV Islam Ansiklopedisi; yalnizca dogrulanan ozellikler)
    def edge_facing(pts, d, len_cap=12.0):
        """Dis normali d yonune en cok bakan kenar: (a, b, birim normal, uzunluk). Cok kisa kenarlar elenir;
        len_cap buyutulurse uzun cepheler (or. avlu tarafindaki ana duvar) koselerdeki kisa pahlara yeglenir."""
        best = None
        for k in range(len(pts)):
            a, b = pts[k], pts[(k + 1) % len(pts)]
            dx, dz = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dz)
            if L < 1.0:
                continue
            n = (dz / L, -dx / L)  # CCW poligonda disari = sag taraf
            score = (n[0] * d[0] + n[1] * d[1]) * min(L, len_cap)
            if best is None or score > best[0]:
                best = (score, a, b, n, L)
        return best[1:]

    def toward(p, cx, cz, m):
        dx, dz = cx - p[0], cz - p[1]
        L = math.hypot(dx, dz) or 1.0
        return p[0] + dx / L * m, p[1] + dz / L * m

    def pyramid(cx, cz, y, r, h, sides, mat):
        cone(ring(cx, cz, y, r, sides, math.pi / sides), (cx, y + h, cz), mat)

    def ince_minareli_medrese(pts, cx, cz, y0, gmax, area):
        """Kapali avlulu Selcuklu medresesi (1264): tek buyuk kubbe, dogu cephesinde anitsal tas tac kapi,
        kare kaideden silindire gecen tugla minare; 1901'de yildirimla birinci serefeden yukarisi yikildi: kesik."""
        y1 = gmax + 8.0
        walls_around(pts, "Stone", y0, y1)
        flat_roof(pts, y1, "Stone")
        r = max(3.0, min(6.5, math.sqrt(area) / 3.2))
        dome(cx, cz, y1 + r * 0.35, r)
        # Tac kapi: dogu cephesinden tasan, duvarlardan yuksek tas blok + koyu kapi nisi
        a, b, n, L = edge_facing(pts, (1.0, 0.0))
        mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        yaw = math.atan2(b[1] - a[1], b[0] - a[0])
        w = min(L * 0.5, 10.0)
        box("Stone", mx + n[0] * 0.8, mz + n[1] * 0.8, y0, w, y1 + 4.5 - y0, 1.6, yaw)
        box("Ruin", mx + n[0] * 0.9, mz + n[1] * 0.9, y0, w * 0.32, (y1 - y0) * 0.75, 1.62, yaw)
        # Kesik minare: kaideden uzak kosede
        far = max(pts, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cz) ** 2)
        tx, tz = toward(far, cx, cz, 2.0)
        base_top = y1 + 1.0
        box("Brick", tx, tz, y0, 3.6, base_top - y0, 3.6, yaw)
        cap(cylinder(tx, tz, base_top, base_top + 1.2, 2.0, 8, "Brick"), "Brick")      # kareden silindire gecis
        y_cut = y0 + 22.0
        cylinder(tx, tz, base_top + 1.2, y_cut, 1.45, 12, "Brick")
        for yb in (base_top + 4.0, base_top + 7.5, y_cut - 2.2):                        # firuze sirli tugla bantlari
            cylinder(tx, tz, yb, yb + 0.7, 1.5, 12, "Turquoise")
        cap(cylinder(tx, tz, y_cut, y_cut + 0.5, 1.75, 12, "Stone"), "Stone")           # yikilan serefenin kaidesi

    def aziziye_camii(pts, cx, cz, y0, gmax, area):
        """Gec Osmanli (1867, Pertevniyal Sultan): kesme tas, tek buyuk kubbe, iki tek serefeli minare,
        son cemaat yerinde uc kucuk kubbe. Minareler giris (kibleye karsi) cephesinin iki kosesinde."""
        y1 = gmax + 11.0
        walls_around(pts, "Stone", y0, y1)
        flat_roof(pts, y1, "Dome")
        rect = min_area_rect(pts)
        half = min(rect[3], rect[4])
        r = max(4.0, min(10.0, half * 0.75))
        shift = min(2.5, half * 0.2)
        dome(cx + QIBLA[0] * shift, cz + QIBLA[1] * shift, y1 + r * 0.35, r)
        a, b, n, L = edge_facing(pts, (-QIBLA[0], -QIBLA[1]))
        ex, ez = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        mx, mz = (a[0] + b[0]) / 2 - n[0] * 2.6, (a[1] + b[1]) / 2 - n[1] * 2.6
        rs = max(1.4, min(2.4, L / 8.0))
        for k in (-1, 0, 1):
            dome(mx + ex * k * L * 0.27, mz + ez * k * L * 0.27, y1 + rs * 0.35, rs)
        for p in (a, b):
            px, pz = toward(p, cx, cz, 1.2)
            minaret(px, pz, y0, max(28.0, (y1 - y0) + 17.0), "Stone", r=1.05, segs=12, cap_mat="Dome", cap_h=6.5)

    def alaeddin_camii(pts, cx, cz, y0, gmax, area):
        """Selcuklu ulu camii: duz damli uzun govde; maksure kubbesi on cepheli piramit kulahla gizli;
        tek minare dogu kanadinin kuzeydogu kosesinde; kuzeydeki avluda iki Selcuklu kumbeti
        (II. Kilicarslan kumbeti on cepheli, iki katli, piramit catili; digeri tamamlanmamis)."""
        y1 = gmax + 8.0
        walls_around(pts, "Stone", y0, y1)
        flat_roof(pts, y1, "Dome")
        a, b, n, L = edge_facing(pts, QIBLA)
        mx, mz = (a[0] + b[0]) / 2 - n[0] * 6.5, (a[1] + b[1]) / 2 - n[1] * 6.5
        cylinder(mx, mz, y1, y1 + 2.2, 5.2, 10, "Stone")
        pyramid(mx, mz, y1 + 2.2, 5.6, 4.5, 10, "Dome")
        ne = max(pts, key=lambda p: p[0] + p[1])
        px, pz = toward(ne, cx, cz, 1.5)
        minaret(px, pz, y0, (y1 - y0) + 12.0, "Stone", r=1.25, cap_mat="Dome", cap_h=3.0)
        # Avlu (kuzey) kumbetleri: kuzey cephesinin onunde
        a2, b2, n2, L2 = edge_facing(pts, (0.0, 1.0), len_cap=1e9)
        ex2, ez2 = (b2[0] - a2[0]) / L2, (b2[1] - a2[1]) / L2
        m2x, m2z = (a2[0] + b2[0]) / 2 + n2[0] * 9.0, (a2[1] + b2[1]) / 2 + n2[1] * 9.0
        spread = max(12.0, min(L2 * 0.6, 22.0))  # iki kumbet birbirine degmesin (yaricaplar + 4 m)
        for k, (kr, finished) in enumerate(((4.2, True), (3.6, False))):
            kx, kz = m2x + ex2 * (k - 0.5) * spread, m2z + ez2 * (k - 0.5) * spread
            gy = ground_h(kx, kz) - 0.6
            cylinder(kx, kz, gy, gy + 3.4, kr * 1.06, 10, "Stone")                   # alt kat
            top = cylinder(kx, kz, gy + 3.4, gy + 10.0, kr, 10, "Stone")             # ust kat (on cepheli govde)
            if finished:
                pyramid(kx, kz, gy + 10.0, kr * 1.04, kr * 1.15, 10, "Dome")
            else:
                cap(top, "Stone")
            fill_poly([(q[0], q[2]) for q in ring(kx, kz, 0.0, kr + 1.0, 10)], True, blocked)  # agac dusmesin

    def karatay_medresesi(pts, cx, cz, y0, gmax, area):
        """Karatay Medresesi (1251): kapali, tek katli tas medrese; ana salonu ortasi fenerli kubbe orter;
        dogu cephesinde mavi-beyaz mermer bantli anitsal tac kapi; minaresiz; Celaleddin Karatay'in turbesi
        kucuk bir kubbe altinda (kaynak: tr.wikipedia)."""
        y1 = gmax + 7.0
        walls_around(pts, "Stone", y0, y1)
        flat_roof(pts, y1, "Stone")
        r = max(3.0, min(6.0, math.sqrt(area) / 3.4))
        dome(cx, cz, y1 + r * 0.35, r)
        top = y1 + r * 0.35 + r * 0.95
        cap(cylinder(cx, cz, top - 0.4, top + 0.8, max(0.6, r * 0.18), 8, "Stone"), "Ruin")  # kubbe feneri
        a, b, n, L = edge_facing(pts, (1.0, 0.0))
        mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        yaw = math.atan2(b[1] - a[1], b[0] - a[0])
        w = min(L * 0.45, 9.0)
        H = y1 + 3.5 - y0
        bands = 9
        for k in range(bands):  # alternatif mermer bantlar (ablak)
            box("Marble" if k % 2 == 0 else "MarbleBlue", mx + n[0] * 0.8, mz + n[1] * 0.8,
                y0 + k * H / bands, w, H / bands + 0.01, 1.6, yaw)
        box("Ruin", mx + n[0] * 0.9, mz + n[1] * 0.9, y0, w * 0.3, (y1 - y0) * 0.75, 1.62, yaw)  # kapi nisi
        corner = max(pts, key=lambda p: -p[0] + p[1])   # turbe: kuzeybati kose
        tx, tz = toward(corner, cx, cz, 4.0)
        dome(tx, tz, y1 + 2.0 * 0.35, 2.0)

    def serafettin_camii(pts, cx, cz, y0, gmax, area):
        """Serafettin Camii (1636'da yeniden): kesme tas govde, buyuk tek kubbe + kible (guney) tarafinda yarim
        kubbe; kuzeyde yedi kucuk kubbeli son cemaat yeri; tek serefeli minare (yan giris tarafinda, guneye yakin;
        kaynakta dogu/bati belirtilmedigi icin yan cephelerden biri). Kaynak: konya.gov.tr, Konyapedia."""
        y1 = gmax + 10.0
        walls_around(pts, "Stone", y0, y1)
        flat_roof(pts, y1, "Dome")
        rect = min_area_rect(pts)
        half = min(rect[3], rect[4])
        r = max(4.0, min(9.5, half * 0.8))
        dome(cx, cz, y1 + r * 0.35, r)
        rh = r * 0.6  # yarim kubbe: kible yonunde ana kubbeye yaslanir
        dome(cx + QIBLA[0] * r * 0.85, cz + QIBLA[1] * r * 0.85, y1 + rh * 0.2, rh)
        a, b, n, L = edge_facing(pts, (-QIBLA[0], -QIBLA[1]))   # son cemaat yeri: kibleye karsi (kuzey)
        ex, ez = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        rs = max(1.0, min(1.6, L / 16.0))
        for k in range(7):
            f = (k + 0.5) / 7.0
            px = a[0] + ex * L * f - n[0] * 1.9
            pz = a[1] + ez * L * f - n[1] * 1.9
            dome(px, pz, y1 + rs * 0.35, rs)
        side = (QIBLA[1], -QIBLA[0])
        sa, sb, sn, sL = edge_facing(pts, side)
        q_end = max((sa, sb), key=lambda p: p[0] * QIBLA[0] + p[1] * QIBLA[1])  # yan cephenin guney (kible) ucu
        mx, mz = toward(q_end, cx, cz, 1.3)
        minaret(mx, mz, y0, max(26.0, (y1 - y0) + 15.0), "Stone", r=1.05, segs=12, cap_mat="Dome", cap_h=6.0)

    def sultan_selim_camii(pts, cx, cz, y0, gmax, area):
        """Selimiye (Sultan Selim) Camii (1558-1570): klasik Osmanli; buyuk tek kubbe, iki minare, son cemaat
        yerinde yedi kucuk kubbe (kaynak: tr.wikipedia). Minareler giris (kibleye karsi) cephesinin iki kosesinde."""
        y1 = gmax + 12.0
        walls_around(pts, "Stone", y0, y1)
        flat_roof(pts, y1, "Dome")
        rect = min_area_rect(pts)
        half = min(rect[3], rect[4])
        r = max(5.0, min(11.0, half * 0.8))
        shift = min(2.5, half * 0.15)
        dome(cx + QIBLA[0] * shift, cz + QIBLA[1] * shift, y1 + r * 0.35, r)
        a, b, n, L = edge_facing(pts, (-QIBLA[0], -QIBLA[1]))
        ex, ez = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        rs = max(1.1, min(1.9, L / 16.0))
        for k in range(7):
            f = (k + 0.5) / 7.0
            dome(a[0] + ex * L * f - n[0] * 2.2, a[1] + ez * L * f - n[1] * 2.2, y1 + rs * 0.35, rs)
        for p_ in (a, b):
            px, pz = toward(p_, cx, cz, 1.3)
            minaret(px, pz, y0, max(32.0, (y1 - y0) + 20.0), "Stone", r=1.1, segs=12, cap_mat="Dome", cap_h=7.0)

    def sircali_medrese(pts, cx, cz, y0, gmax, area):
        """Sircali Medrese (1242): acik avlulu, iki katli; dort kanat avluyu cevreler, ana eyvan kuzeyde ve
        firuze-kobalt sirli cinilerle kapli; giriste suslu tas tac kapi (eyvanin karsisinda, tipik plan);
        minare ve kubbe yok (kaynak: tr.wikipedia). Avlu gokyuzune acik."""
        y1 = gmax + 8.5
        center, ux, uz, hx, hz, _ = min_area_rect(pts)
        depth = max(4.0, min(7.0, min(hx, hz) * 0.42))   # kanat derinligi (ogrenci odalari)
        wings = []  # (merkez, uzunluk ekseni, yaricap uzunluk, dis normal)
        for sgn in (1, -1):
            nz_ = (uz[0] * sgn, uz[1] * sgn)
            wings.append(((center[0] + uz[0] * sgn * (hz - depth / 2), center[1] + uz[1] * sgn * (hz - depth / 2)), ux, hx, nz_))
            nx_ = (ux[0] * sgn, ux[1] * sgn)
            wings.append(((center[0] + ux[0] * sgn * (hx - depth / 2), center[1] + ux[1] * sgn * (hx - depth / 2)), uz, hz - depth, nx_))
        for (wc, axis, half_len, out) in wings:
            yaw = math.atan2(axis[1], axis[0])
            box("Stone", wc[0], wc[1], y0, half_len * 2, y1 - y0, depth, yaw)
        # Ana eyvan: kuzeye bakan kanadin avlu tarafinda firuze cinili kemer cercevesi + derin nis
        north = max(wings, key=lambda w: w[3][1])
        wc, axis, half_len, out = north
        yaw = math.atan2(axis[1], axis[0])
        ix, iz = wc[0] - out[0] * (depth / 2 + 0.15), wc[1] - out[1] * (depth / 2 + 0.15)
        ew = min(half_len * 0.6, 7.0)
        box("Turquoise", ix, iz, y0, ew, (y1 - y0) + 1.5, 0.5, yaw)
        box("Ruin", ix - out[0] * 0.05, iz - out[1] * 0.05, y0, ew * 0.62, (y1 - y0) * 0.82, 0.56, yaw)
        # Tac kapi: eyvanin karsisindaki (guney) kanadin dis cephesi
        south = min(wings, key=lambda w: w[3][1])
        wc, axis, half_len, out = south
        yaw = math.atan2(axis[1], axis[0])
        px, pz = wc[0] + out[0] * (depth / 2 + 0.7), wc[1] + out[1] * (depth / 2 + 0.7)
        box("Stone", px, pz, y0, min(half_len, 9.0), (y1 - y0) + 3.0, 1.4, yaw)
        box("Ruin", px + out[0] * 0.1, pz + out[1] * 0.1, y0, min(half_len, 9.0) * 0.32, (y1 - y0) * 0.75, 1.45, yaw)

    def iplikci_camii(pts, cx, cz, y0, gmax, area):
        """Iplikci Camii (13. yy. Selcuklu): duvarlari tamamen tugla; kibleye dik yedi nefli, orta eksende uc kubbe;
        1976'da yapilan iki serefeli tugla minare (kaynak: tr.wikipedia; minarenin kosesi kaynakta belirtilmemis)."""
        y1 = gmax + 9.0
        walls_around(pts, "Brick", y0, y1)
        flat_roof(pts, y1, "Dome")
        rect = min_area_rect(pts)
        rd = max(2.5, min(4.5, min(rect[3], rect[4]) * 0.28))
        for k in (-1, 0, 1):  # kible ekseni boyunca uc kubbe
            dome(cx + QIBLA[0] * k * rd * 2.3, cz + QIBLA[1] * k * rd * 2.3, y1 + rd * 0.35, rd)
        corner = max(pts, key=lambda p: -(p[0] - cx) * QIBLA[0] - (p[1] - cz) * QIBLA[1])
        mx, mz = toward(corner, cx, cz, 1.6)
        top = y0 + max(24.0, (y1 - y0) + 15.0)
        b1, b2 = top - 9.0, top - 4.0
        cylinder(mx, mz, y0, b1, 1.25, 12, "Brick")
        cap(cylinder(mx, mz, b1, b1 + 0.6, 1.8, 12, "Stone"), "Stone")      # 1. serefe
        cylinder(mx, mz, b1 + 0.6, b2, 1.1, 12, "Brick")
        cap(cylinder(mx, mz, b2, b2 + 0.6, 1.65, 12, "Stone"), "Stone")     # 2. serefe
        t2 = cylinder(mx, mz, b2 + 0.6, top, 1.0, 12, "Brick")
        cone(t2, (mx, top + 4.5, mz), "Dome")
        alem(mx, mz, top + 4.5)

    def named_area_center(name):
        for w in ways.values():
            if w.get("tags", {}).get("name") == name:
                pts_ = way_pts(w)
                if pts_:
                    return (sum(p[0] for p in pts_) / len(pts_), sum(p[1] for p in pts_) / len(pts_))
        return None

    def hukumet_konagi(pts, cx, cz, y0, gmax, area):
        """Konya Hukumet Konagi / Valilik (1885-86, Said Pasa; I. Ulusal Mimarlik): dikdortgen, ortasi acik avlulu,
        3 katli; Konya dis kale surlarinin duzgun taslari; dort cepheden giris, ana giris Hukumet Meydani'na bakar:
        dort serbest ve dort duvara bitisik sutun, ust kati cikmali (kaynak: konya.gov.tr, Konyapedia)."""
        ground = gmax + 0.0
        y1 = ground + 12.6                                     # 3 kat x 4.2 m
        center, ux, uz, hx, hz, _ = min_area_rect(pts)
        depth = max(6.0, min(10.0, min(hx, hz) * 0.38))

        def wing(c, axis, half_len, d):
            ax, az = axis
            nx, nz = -az, ax
            corners = [(c[0] - ax * half_len - nx * d / 2, c[1] - az * half_len - nz * d / 2),
                       (c[0] + ax * half_len - nx * d / 2, c[1] + az * half_len - nz * d / 2),
                       (c[0] + ax * half_len + nx * d / 2, c[1] + az * half_len + nz * d / 2),
                       (c[0] - ax * half_len + nx * d / 2, c[1] - az * half_len + nz * d / 2)]
            if signed_area(corners) < 0:
                corners.reverse()
            walls_around(corners, "Facade_Stone", y0, y1, 1 / 4.0, 1 / 4.2, ground)
            flat_roof(corners, y1, "RoofFlat")

        for sgn in (1, -1):
            wing((center[0] + uz[0] * sgn * (hz - depth / 2), center[1] + uz[1] * sgn * (hz - depth / 2)), ux, hx, depth)
            wing((center[0] + ux[0] * sgn * (hx - depth / 2), center[1] + ux[1] * sgn * (hx - depth / 2)), uz, hz - depth, depth)

        # Ana giris: Hukumet Meydani'na bakan cephe (meydan bulunamazsa kuzey)
        mc = named_area_center("Hükümet Meydanı")
        face = (mc[0] - cx, mc[1] - cz) if mc else (0.0, 1.0)
        a, b, n, L = edge_facing(pts, face)
        mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        ex, ez = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        yaw = math.atan2(ez, ex)
        pw, pd = min(L * 0.35, 12.0), 3.2                      # cikma genisligi / derinligi
        px, pz = mx + n[0] * pd / 2, mz + n[1] * pd / 2
        top_y = ground + 4.2
        # ust katlar cikmasi (2 kat): sutunlarin uzerinde
        proj = [(px - ex * pw / 2 - n[0] * pd / 2, pz - ez * pw / 2 - n[1] * pd / 2),
                (px + ex * pw / 2 - n[0] * pd / 2, pz + ez * pw / 2 - n[1] * pd / 2),
                (px + ex * pw / 2 + n[0] * pd / 2, pz + ez * pw / 2 + n[1] * pd / 2),
                (px - ex * pw / 2 + n[0] * pd / 2, pz - ez * pw / 2 + n[1] * pd / 2)]
        if signed_area(proj) < 0:
            proj.reverse()
        walls_around(proj, "Facade_Stone", top_y, y1 + 0.8, 1 / 4.0, 1 / 4.2, ground)
        flat_roof(proj, y1 + 0.8, "RoofFlat")
        box("Column", px, pz, top_y - 0.35, pw + 0.2, 0.35, pd + 0.2, yaw)           # cikma alt dosemesi
        # dort serbest sutun (onde) + dort duvara bitisik sutun (cephe hizasinda)
        for k in range(4):
            t = (k - 1.5) / 1.5 * (pw / 2 - 0.6)
            for depth_off in (pd - 0.4, 0.15):
                sx, sz = mx + ex * t + n[0] * depth_off, mz + ez * t + n[1] * depth_off
                cylinder(sx, sz, y0, top_y - 0.35, 0.32, 10, "Column")
        box("Ruin", mx + n[0] * 0.05, mz + n[1] * 0.05, y0, 2.6, 3.4, 0.2, yaw)        # ana kapi

    SPECIAL_LANDMARKS = (("İnce Minare", ince_minareli_medrese), ("Aziziye Camii", aziziye_camii),
                         ("Valilik", hukumet_konagi),
                         ("Sultan Selim Camii", sultan_selim_camii), ("Sırçalı Medrese", sircali_medrese),
                         ("İplikçi Cami", iplikci_camii),
                         ("Alaeddin Keykubad Camii", alaeddin_camii), ("Karatay Müzesi", karatay_medresesi),
                         ("Şerafeddin Camii", serafettin_camii))

    # Tabela atlasi sirasi (gen_textures.shop_signs) -> islevli dukkan turu (madde 11)
    SHOP_KINDS = {0: "firin", 6: "firin", 7: "bufe", 10: "bufe", 9: "terzi", 15: "galeri"}
    shops = []

    def shop_sign(a, b, L, yb, rnd):
        """Caddeye/kaldirima bakan dukkan cephesine tabela (atlastan rastgele markasiz Turkce isim).
        Cephenin 3.5 m onu yol/kaldirim seridindeyse (no_tree) cadde cephesidir."""
        dx, dz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        out = (dz, -dx)
        mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        c = cell_of(mx + out[0] * 3.5, mz + out[1] * 3.5)
        if c is None or not no_tree[c[1]][c[0]] or blocked[c[1]][c[0]] or rnd.random() > 0.8:
            return
        w = min(L * 0.7, 7.5)
        off = 0.07
        p0 = (mx - dx * w / 2 + out[0] * off, mz - dz * w / 2 + out[1] * off)
        p1 = (mx + dx * w / 2 + out[0] * off, mz + dz * w / 2 + out[1] * off)
        yb0, yt = yb - 1.15, yb - 0.25
        k = rnd.randrange(16)
        u0, v0 = (k % 2) * 0.5, 1.0 - (k // 2 + 1) / 8.0
        if k in SHOP_KINDS:
            # Madde 11 islevli dukkan: kapinin onu (kaldirimda, cepheden 1.6 m disari), cephe yonu ve tur
            fx, fz = mx + out[0] * 1.6, mz + out[1] * 1.6
            shops.append({"kind": SHOP_KINDS[k], "x": round(fx, 2), "y": round(surface_h(fx, fz), 2), "z": round(fz, 2),
                          "fx": round(out[0], 3), "fz": round(out[1], 3)})
        mb().quad("ShopSign", (p0[0], yb0, p0[1]), (p1[0], yb0, p1[1]), (p1[0], yt, p1[1]), (p0[0], yt, p0[1]),
                  (out[0], 0.0, out[1]), [(u0, v0), (u0 + 0.5, v0), (u0 + 0.5, v0 + 0.125), (u0, v0 + 0.125)])

    # ---------- 7c bina ayrintilari: duz kutu goruntusunu kiran, ucuz (az ucgenli) parcalar
    def in_details(fn, *args, **kw):
        """Ayrintiyi binanin parcasinin 'details' katmanina yazar (uzakta gizlenir; carpismasi yok)."""
        prev = target["mb"]
        target["mb"] = tile_mb(target["cx"], target["cz"], "details")
        try:
            fn(*args, **kw)
        finally:
            target["mb"] = prev

    def street_side(a, b, L):
        """Cephenin 3.5 m onu yol/kaldirim seridindeyse cadde cephesidir (dukkan tabelasiyla ayni kural)."""
        dx, dz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        c = cell_of(mx + dz * 3.5, mz - dx * 3.5)
        return c is not None and no_tree[c[1]][c[0]] and not blocked[c[1]][c[0]]

    def ledge(a, b, y, h, depth, mat="Cornice", inner=False, extend=True, bottom=True):
        """Cephe boyunca yatay cikinti (sacak/silme/parapet): on, ust ve alt yuz. Koselerde bosluk kalmasin diye
        uclar 'depth' kadar uzar. inner: parapet icin cati tarafindaki ic yuz."""
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 0.5:
            return
        dx, dz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        ox, oz = dz, -dx                                    # disari (CCW poligonda sag taraf)
        e = depth if extend else 0.0
        a0 = (a[0] - dx * e, a[1] - dz * e)
        b0 = (b[0] + dx * e, b[1] + dz * e)
        a1 = (a0[0] + ox * depth, a0[1] + oz * depth)
        b1 = (b0[0] + ox * depth, b0[1] + oz * depth)
        out = (ox, 0.0, oz)
        u1 = (L + 2 * e) / 2.0
        mb().quad(mat, (a1[0], y, a1[1]), (b1[0], y, b1[1]), (b1[0], y + h, b1[1]), (a1[0], y + h, a1[1]), out,
                  [(0, 0), (u1, 0), (u1, h / 2), (0, h / 2)])
        mb().quad(mat, (a0[0], y + h, a0[1]), (a1[0], y + h, a1[1]), (b1[0], y + h, b1[1]), (b0[0], y + h, b0[1]), (0, 1, 0),
                  [(0, 0), (0, depth / 2), (u1, depth / 2), (u1, 0)])
        if bottom:                                          # alt yuz: sokaktan bakinca gorunen
            mb().quad(mat, (a0[0], y, a0[1]), (b0[0], y, b0[1]), (b1[0], y, b1[1]), (a1[0], y, a1[1]), (0, -1, 0),
                      [(0, 0), (u1, 0), (u1, depth / 2), (0, depth / 2)])
        if inner:
            mb().quad(mat, (a0[0], y, a0[1]), (b0[0], y, b0[1]), (b0[0], y + h, b0[1]), (a0[0], y + h, a0[1]), (-ox, 0.0, -oz),
                      [(0, 0), (u1, 0), (u1, h / 2), (0, h / 2)])

    def window_sills(a, b, L, u_start, y_floor0, floors_up):
        """Pencereli cephe: her pencerenin altinda cikintili denizlik (dokudaki denizlik cizgisiyle ayni hizada:
        3 m'lik doku karesinde pencere 0.72-2.28 m arasi, denizlik kat tabanindan 0.53-0.65 m)."""
        dx, dz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        ox, oz = dz, -dx
        tile = 3.0
        # u (doku koordinati, 1 = 3 m) cephe basinda u_start: pencere k. karede [k+0.24, k+0.76]
        k = math.floor(u_start)
        while True:
            s0 = (k + 0.22 - u_start) * tile
            s1 = (k + 0.78 - u_start) * tile
            if s0 >= L - 0.2:
                break
            if s0 > 0.15 and s1 < L - 0.15:
                for f in range(floors_up):
                    y = y_floor0 + f * FLOOR_H + 0.53
                    pa = (a[0] + dx * s0, a[1] + dz * s0)
                    pb = (a[0] + dx * s1, a[1] + dz * s1)
                    ledge(pa, pb, y, 0.08, 0.1, extend=False, bottom=False)
            k += 1

    def ac_unit(a, b, L, s_along, y, rnd):
        """Klima dis unitesi: cepheye asili kutu + on yuzde pervane izgarasi."""
        dx, dz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        ox, oz = dz, -dx
        cx = a[0] + dx * s_along + ox * 0.22
        cz = a[1] + dz * s_along + oz * 0.22
        yaw = math.atan2(dz, dx)
        box("AcUnit", cx, cz, y, 0.8, 0.55, 0.3, yaw)
        fx, fz = cx + ox * 0.152, cz + oz * 0.152
        r = 0.18
        mb().quad("AcGrille", (fx - dx * r, y + 0.1, fz - dz * r), (fx + dx * r, y + 0.1, fz + dz * r),
                  (fx + dx * r, y + 0.46, fz + dz * r), (fx - dx * r, y + 0.46, fz - dz * r), (ox, 0.0, oz))

    def bay(a, b, L, facade, y_bot, y_top, u_start, depth=0.8):
        """Cikma (cumba): ust katlarda cephenin ortasi disari tasar (Turk apartmanlarinin tipik gorunusu).
        On yuz ayni cephe dokusu (cam balkonlu/balkonlu), yanlar ve alt/ust yuzler. Doner: (s0, s1) aralik."""
        dx, dz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        ox, oz = dz, -dx
        w = min(L * 0.6, 9.0)
        s0 = (L - w) / 2
        s1 = s0 + w
        pa = (a[0] + dx * s0, a[1] + dz * s0)
        pb = (a[0] + dx * s1, a[1] + dz * s1)
        fa = (pa[0] + ox * depth, pa[1] + oz * depth)
        fb = (pb[0] + ox * depth, pb[1] + oz * depth)
        u0 = u_start + s0 / 3.0
        wall(facade, fa, fb, y_bot, y_top, u0, 1 / 3.0, y_bot, 1 / FLOOR_H)          # on yuz
        wall(facade, pa, fa, y_bot, y_top, u0 - depth / 3.0, 1 / 3.0, y_bot, 1 / FLOOR_H)   # yan
        wall(facade, fb, pb, y_bot, y_top, u0 + w / 3.0, 1 / 3.0, y_bot, 1 / FLOOR_H)       # yan
        mb().quad("Cornice", (pa[0], y_bot, pa[1]), (pb[0], y_bot, pb[1]), (fb[0], y_bot, fb[1]), (fa[0], y_bot, fa[1]),
                  (0, -1, 0))                                                         # alt (sokaktan gorunen tavan)
        mb().quad("Cornice", (pa[0], y_top, pa[1]), (fa[0], y_top, fa[1]), (fb[0], y_top, fb[1]), (pb[0], y_top, pb[1]),
                  (0, 1, 0))                                                          # ust
        return s0, s1

    def add_building(pts, t, wid):
        pts = clean_poly(pts)
        if len(pts) < 3 or abs(signed_area(pts)) < 4:
            return
        cx = sum(p[0] for p in pts) / len(pts)
        cz = sum(p[1] for p in pts) / len(pts)
        if not inside_rect(cx, cz, 2.0):
            return
        target["mb"] = tile_mb(cx, cz, "buildings")
        target["cx"], target["cz"] = cx, cz
        gh = [ground_h(p[0], p[1]) for p in pts]
        gmin, gmax = min(gh), max(gh)
        y0 = gmin - 0.6
        h = stable_hash(wid)
        rnd = random.Random(h)
        name = t.get("name", "")
        b = t.get("building", "yes")
        area = abs(signed_area(pts))
        is_mosque = b == "mosque" or (t.get("amenity") == "place_of_worship" and t.get("religion") == "muslim")
        is_minaret = "Minare" in name
        is_tomb = t.get("historic") == "tomb" or b == "mausoleum"
        is_mevlana = any(s in name for s in sanct_names) and is_tomb
        is_historic = bool(t.get("historic")) or is_minaret or is_mosque or is_tomb or t.get("tourism") == "museum"
        fill_poly(pts, True, blocked)

        special = next((fn for key, fn in SPECIAL_LANDMARKS if key in name), None)
        if special:
            special(pts, cx, cz, y0, gmax, area)
        elif is_mevlana:
            y1 = gmax + 9.0
            walls_around(pts, "Stone", y0, y1)
            flat_roof(pts, y1, "Dome")
            yesil_kubbe(cx, cz, y1)
        elif is_tomb:
            kumbet(pts, y0, gmax + 5.5, "Dome")
        elif is_historic:
            y1 = gmax + (9.0 if is_mosque else 7.0)
            walls_around(pts, "Stone", y0, y1)
            flat_roof(pts, y1, "Dome" if is_mosque else "Stone")  # Selcuklu camilerinde cati kursun kapli
            big = area >= 120
            if is_mosque or is_minaret:
                r = max(2.0, min(9.0, math.sqrt(area) / 2.6))
                dome(cx, cz, y1 + r * 0.35, r)
                if big or is_minaret:
                    far = max(pts, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cz) ** 2)
                    mx, mz = cx + (far[0] - cx) * 0.75, cz + (far[1] - cz) * 0.75
                    minaret(mx, mz, y0, 26.0 if is_minaret else (20.0 if area > 400 else 16.0), "Brick" if is_minaret else "Stone")
        else:
            floors = None
            try:
                if "building:levels" in t:
                    floors = max(1, int(float(t["building:levels"])))
            except ValueError:
                pass
            if floors is None:
                # Konya merkezi: cogunlukla 5-7 katli apartmanlar; ticari bloklar biraz daha yuksek
                floors = (5 + (h >> 3) % 4) if b in ("commercial", "office", "retail") else (4 + ((h >> 3) % 7 + (h >> 7) % 3) // 2)
            if b in ("roof", "canopy", "kiosk") or area < 25:
                floors = 1
            c = cell_of(cx, cz)
            if c and cat[c[1]][c[0]] in (G_FOREST, G_GRASS) and "building:levels" not in t:
                floors = 1  # park/koru icindeki yapilar: tek katli kosk / cay bahcesi

            yb = gmin + SHOP_H
            y1 = yb + (floors - 1) * FLOOR_H + 0.4 + (gmax - gmin)
            # Cephe tipi: pencereli / acik balkonlu / cam balkonlu apartman; ticari ve yuksek bloklarda modern serit pencere
            roll = (h >> 11) % 100
            modern = b in ("commercial", "office", "retail") or floors >= 8
            if modern and roll < 55:
                facade = f"Facade_Modern_{'White' if (h >> 4) % 2 else 'Grey'}"
            else:
                style = "Window" if roll < 35 else "Balcony" if roll < 60 else "GlassBalcony"
                facade = f"Facade_{style}_{WALL_COLORS[(h >> 4) % len(WALL_COLORS)]}"
            u_shop, u_up = 0.0, 0.0
            style_key = facade.split("_")[1]                   # Window / Balcony / GlassBalcony / Modern
            for k in range(len(pts)):
                a, c2 = pts[k], pts[(k + 1) % len(pts)]
                L = math.hypot(c2[0] - a[0], c2[1] - a[1])
                wall("Shop", a, c2, y0, yb, u_shop, 1 / 4.0, gmin, 1 / SHOP_H)
                if L >= 4.5 and floors > 1:
                    shop_sign(a, c2, L, yb, rnd)
                if y1 > yb + 0.1:
                    wall(facade, a, c2, yb, y1, u_up, 1 / 3.0, yb, 1 / FLOOR_H)
                # --- 7c ayrintilar
                street = floors > 2 and L >= 4.0 and street_side(a, c2, L)
                if street:
                    in_details(ledge, a, c2, yb - 0.05, 0.32, 0.28)        # dukkan sacagi (yalniz cadde cephesi)
                if street:
                    ups = floors - 1                                       # dukkan ustundeki katlar
                    bay_span = None
                    if style_key in ("GlassBalcony", "Balcony") and L >= 7.0 and floors >= 4 and (h >> 9) % 100 < 75:
                        bay_span = bay(a, c2, L, facade, yb, yb + ups * FLOOR_H, u_up)
                    if style_key == "Window":
                        in_details(window_sills, a, c2, L, u_up, yb, ups)
                    for f in range(1, ups):                                # kat silmeleri / balkon dosemeleri
                        yf = yb + f * FLOOR_H
                        if style_key == "Balcony":
                            depth_f = 0.32
                            yy, hh = yf + 0.2, 0.16
                        else:
                            depth_f = 0.12 if style_key != "Modern" else 0.18
                            yy, hh = yf - 0.02, 0.14 if style_key != "Modern" else 0.22
                        if bay_span is None:
                            in_details(ledge, a, c2, yy, hh, depth_f)
                        else:                                              # cikmanin iki yaninda
                            dx_, dz_ = (c2[0] - a[0]) / L, (c2[1] - a[1]) / L
                            m0 = (a[0] + dx_ * bay_span[0], a[1] + dz_ * bay_span[0])
                            m1 = (a[0] + dx_ * bay_span[1], a[1] + dz_ * bay_span[1])
                            in_details(ledge, a, m0, yy, hh, depth_f, extend=False)
                            in_details(ledge, m1, c2, yy, hh, depth_f, extend=False)
                    # klima dis uniteleri: cikmanin disinda, rastgele katlarda (1-2 adet)
                    for _ in range(1 + int(L > 10.0)):
                        if rnd.random() < 0.7:
                            s_al = rnd.uniform(0.8, L - 0.8)
                            if bay_span is not None and bay_span[0] - 0.6 < s_al < bay_span[1] + 0.6:
                                continue
                            f = rnd.randrange(1, max(2, ups))
                            in_details(ac_unit, a, c2, L, s_al, yb + f * FLOOR_H + 0.25, rnd)
                u_shop += L / 4.0
                u_up += L / 3.0

            rect = min_area_rect(pts)
            rect_like = area / max(rect[5], 1e-6) > 0.82
            if rect_like and area < 900 and h % 100 < 55:
                hip_roof(rect, y1)
            else:
                flat_roof(pts, y1, "RoofFlat")
                if floors > 1:                                             # 7c: parapet + harpusta
                    for k in range(len(pts)):
                        in_details(ledge, pts[k], pts[(k + 1) % len(pts)], y1, 0.55, 0.14, inner=True, bottom=False)
                if area > 60 and rnd.random() < 0.65:
                    p = random_point_inside(pts, 1.8, rnd)
                    if p:
                        solar_heater(p[0], p[1], y1)
                if area > 150 and rnd.random() < 0.5:
                    p = random_point_inside(pts, 2.0, rnd)
                    if p:
                        box("RoofBox", p[0], p[1], y1, 2.4, 2.2, 2.6, yaw=rnd.random() * math.pi)
                for _ in range(1 + int(area > 250)):      # canak anten: Turk catilarinin vazgecilmezi
                    if area > 50 and rnd.random() < 0.55:
                        p = random_point_inside(pts, 1.2, rnd)
                        if p:
                            satellite_dish(p[0], p[1], y1, 0.45 + rnd.random() * 0.25)
                if area > 40 and rnd.random() < 0.35:
                    p = random_point_inside(pts, 1.0, rnd)
                    if p:
                        tv_antenna(p[0], p[1], y1, rnd)
        if name:
            landmarks.append({"name": name, "x": round(cx, 1), "y": round(gmax, 1), "z": round(cz, 1)})

    for w in ways.values():
        t = w.get("tags", {})
        if "building" in t and is_closed(w):
            add_building(way_pts(w), t, w["id"])
    for rel in relations:
        t = rel.get("tags", {})
        if "building" not in t:
            continue
        for m in rel.get("members", []):
            if m["type"] == "way" and m.get("role") == "outer" and m["ref"] in ways and is_closed(ways[m["ref"]]):
                add_building(way_pts(ways[m["ref"]]), t, m["ref"])

    # ---------- kalintilar, duvarlar ve kutsal alan duvarlari
    def wall_segment(a, b, thick, y_bot, y_top, mat):
        dx, dz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dz)
        if L < 0.1:
            return
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if not inside_rect(mid[0], mid[1]):
            return
        target["mb"] = tile_mb(mid[0], mid[1], "buildings")
        nx, nz = -dz / L * thick / 2, dx / L * thick / 2
        q = clean_poly([(a[0] + nx, a[1] + nz), (b[0] + nx, b[1] + nz), (b[0] - nx, b[1] - nz), (a[0] - nx, a[1] - nz)])
        walls_around(q, mat, y_bot, y_top)
        flat_roof(q, y_top, mat)

    def sanctuary_wall(pts):
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            g = min(ground_h(*a), ground_h(*b))
            wall_segment(a, b, 0.8, g - 0.5, g + 3.2, "Stone")
            fill_line([a, b], 1.5, True, no_tree)

    sanctuary_count = 0
    for w in ways.values():
        t = w.get("tags", {})
        pts = way_pts(w)
        if len(pts) < 2:
            continue
        if t.get("historic") == "ruins" and "building" not in t:
            for k in range(len(pts) - 1):
                if stable_hash((w["id"], k)) % 5 == 0:
                    continue  # yikik bosluk
                a, b = pts[k], pts[k + 1]
                hy = 1.8 + (stable_hash((w["id"], k, 1)) % 30) / 10.0
                g = min(ground_h(*a), ground_h(*b))
                wall_segment(a, b, 1.0, g - 0.5, g + hy, "Ruin")
            if t.get("name"):
                landmarks.append({"name": t["name"], "x": round(pts[0][0], 1), "y": round(ground_h(*pts[0]), 1), "z": round(pts[0][1], 1)})
        elif t.get("barrier") == "wall":
            for k in range(len(pts) - 1):
                a, b = pts[k], pts[k + 1]
                g = min(ground_h(*a), ground_h(*b))
                wall_segment(a, b, 0.6, g - 0.5, g + 2.2, "Stone")

    # Kutsal alanlar (Mevlana Muzesi kulliyesi): duvarla cevrili, ici tas avlu, savas disi
    for rel in relations:
        t = rel.get("tags", {})
        if t.get("tourism") != "museum" or not any(s in t.get("name", "") for s in sanct_names):
            continue
        for m in rel.get("members", []):
            if m["type"] == "way" and m.get("role") == "outer" and m["ref"] in ways:
                pts = way_pts(ways[m["ref"]])
                sanctuary_wall(pts)
                if is_closed(ways[m["ref"]]):
                    poly = clean_poly(pts)
                    fill_poly(poly, G_PLAZA, cat)
                    fill_poly(poly, True, no_tree)
        sanctuary_count += 1

    # ---------- dolgu binalar: OSM'de eksik kalan adalari sokaga hizali binalarla doldur
    # (gercek OSM binalarina dokunulmaz; yalnizca yol, park, bina olmayan bos kaldirim hucrelerine)
    seg_grid = {}
    BUCKET = 32.0
    for hw, pts, width in lines:
        if hw not in VEHICLE and hw != "pedestrian":
            continue
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 0.5:
                continue
            for p in resample([a, b], BUCKET / 2):
                seg_grid.setdefault((int(p[0] // BUCKET), int(p[1] // BUCKET)), set()).add((a, b, width))

    def nearest_road(x, z):
        bx, bz = int(x // BUCKET), int(z // BUCKET)
        best = None
        for r in range(0, 3):
            for gx in range(bx - r, bx + r + 1):
                for gz in range(bz - r, bz + r + 1):
                    for a, b, width in seg_grid.get((gx, gz), ()):
                        d = seg_dist(x, z, a, b) - width / 2
                        if best is None or d < best[0]:
                            best = (d, a, b)
            if best is not None:
                break
        return best

    def cell_free(x, z):
        c = cell_of(x, z)
        return c is not None and cat[c[1]][c[0]] == G_PAVED and not blocked[c[1]][c[0]] and not no_tree[c[1]][c[0]]

    def cell_free_or_road(x, z):
        """Bina disi her yer (yol ve kaldirim dahil): direk gibi ince nesneler icin."""
        c = cell_of(x, z)
        return c is not None and not blocked[c[1]][c[0]]

    infill_rng = random.Random(1243)
    candidates = []
    for j in range(2, CH - 2, 4):
        for i in range(2, CW - 2, 4):
            x = X0 + (i + 0.5 + infill_rng.uniform(-1, 1)) * CELL
            z = Z0 + (j + 0.5 + infill_rng.uniform(-1, 1)) * CELL
            if not cell_free(x, z) or not inside_rect(x, z, 8.0):
                continue
            nr = nearest_road(x, z)
            if nr is None or nr[0] > 70:
                continue
            candidates.append((nr[0], x, z, nr[1], nr[2]))
    candidates.sort(key=lambda c: c[0])  # once sokak cephesi dolsun

    infill_count = 0
    for d_road, x, z, a, b in candidates:
        if not cell_free(x, z):
            continue
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        ux, uz = (b[0] - a[0]) / L, (b[1] - a[1]) / L      # sokak yonu
        vx, vz = -uz, ux                                   # sokaga dik
        placed = False
        for _ in range(3):
            w = infill_rng.uniform(9.0, 16.0)   # cephe genisligi
            dpt = infill_rng.uniform(10.0, 15.0)  # derinlik
            hw_, hd = w / 2, dpt / 2
            corners = [(x + ux * sa * hw_ + vx * sb * hd, z + uz * sa * hw_ + vz * sb * hd)
                       for sa, sb in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            ok = all(cell_free(x + ux * su * (hw_ + 0.3) + vx * sv * (hd + 0.3), z + uz * su * (hw_ + 0.3) + vz * sv * (hd + 0.3))
                     for su in (-1, -0.5, 0, 0.5, 1) for sv in (-1, -0.5, 0, 0.5, 1))
            if ok:
                add_building(corners, {"building": "yes"}, ("infill", round(x), round(z)))
                infill_count += 1
                placed = True
                break
        _ = placed

    # ---------- agaclar: yumusak yaprak kumeleri
    rng = random.Random(1071)
    phi = (1 + 5 ** 0.5) / 2
    ico_v = [(-1, phi, 0), (1, phi, 0), (-1, -phi, 0), (1, -phi, 0), (0, -1, phi), (0, 1, phi),
             (0, -1, -phi), (0, 1, -phi), (phi, 0, -1), (phi, 0, 1), (-phi, 0, -1), (-phi, 0, 1)]
    sph_v = [tuple(c / math.sqrt(1 + phi * phi) for c in v) for v in ico_v]
    sph0_v = list(sph_v)   # kaba ikosfer (12 vertex): kucuk yan kumeler ve calilar icin (mobil vertex butcesi)
    ico_f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
             (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
             (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    mid_cache = {}

    def midpoint(a, b):
        k = (min(a, b), max(a, b))
        if k not in mid_cache:
            p = [(sph_v[a][i] + sph_v[b][i]) / 2 for i in range(3)]
            L = math.sqrt(sum(c * c for c in p))
            sph_v.append(tuple(c / L for c in p))
            mid_cache[k] = len(sph_v) - 1
        return mid_cache[k]

    sph0_f = list(ico_f)
    sph_f = []
    for (a, b, c) in ico_f:   # bir kez bolunmus ikosfer: 42 vertex, 80 yuz
        ab, bc, ca = midpoint(a, b), midpoint(b, c), midpoint(c, a)
        sph_f += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]

    def blob(target_mb, mat, cx, cy, cz, R, squash, jitter=0.22, flat_bottom=-0.55, coarse=False):
        """Yaprak kumesi: puruzlu kure (paylasilan vertex, yumusak golge). UV: tepe merkezli Lambert esit alan
        izdusumu: dikissiz, gorunen tepe ve yanlarda doku esit yogunlukta; tek kutup kumenin (yassi, golgede) altinda."""
        yaw = rng.random() * math.pi * 2
        cs, sn = math.cos(yaw), math.sin(yaw)
        verts, uvs = [], []
        sv, sf = (sph0_v, sph0_f) if coarse else (sph_v, sph_f)
        for (vx, vy, vz) in sv:
            j = 1.0 - jitter * 0.6 + rng.random() * jitter
            rx, rz = vx * cs - vz * sn, vx * sn + vz * cs
            verts.append((cx + rx * R * j, cy + max(vy, flat_bottom) * R * squash * j, cz + rz * R * j))
            k = math.sqrt(2.0 / max(1e-3, 1.0 + vy)) * 0.9 * R  # ~1 doku tekrari / 1.1 m
            uvs.append((vx * k + cx * 0.37, vz * k + cz * 0.37))  # konum kaymasi: kumeler ayni deseni tekrarlamasin
        tris = []
        for (a, b, c) in sf:
            pa, pb, pc = verts[a], verts[b], verts[c]
            m = ((pa[0] + pb[0] + pc[0]) / 3 - cx, (pa[1] + pb[1] + pc[1]) / 3 - cy, (pa[2] + pb[2] + pc[2]) / 3 - cz)
            tris.append((a, b, c) if dot(cross(sub(pb, pa), sub(pc, pa)), m) >= 0 else (a, c, b))
        target_mb.add_indexed(mat, verts, tris, uvs)

    def trunk(t_mb, mat, x, z, y0, y1, r0, r1, sides=6, lean=(0.0, 0.0)):
        """Konik govde/dal (alt yaricap r0, ust r1), kabuk dokusu dikey akar. lean: tepenin yatay kaymasi."""
        for k in range(sides):
            a0, a1 = 2 * math.pi * k / sides, 2 * math.pi * (k + 1) / sides
            b0 = (x + r0 * math.cos(a0), y0, z + r0 * math.sin(a0))
            b1 = (x + r0 * math.cos(a1), y0, z + r0 * math.sin(a1))
            t1 = (x + lean[0] + r1 * math.cos(a1), y1, z + lean[1] + r1 * math.sin(a1))
            t0 = (x + lean[0] + r1 * math.cos(a0), y1, z + lean[1] + r1 * math.sin(a0))
            out = (math.cos((a0 + a1) / 2), 0, math.sin((a0 + a1) / 2))
            u0, u1 = k / sides * 1.5, (k + 1) / sides * 1.5
            t_mb.quad(mat, b0, b1, t1, t0, out, [(u0, y0 / 2.2), (u1, y0 / 2.2), (u1, y1 / 2.2), (u0, y1 / 2.2)])

    def cone_layer(t_mb, mat, x, z, y0, y1, r, sides=7):
        """Igne yaprakli katman: hafif sarkik etekli koni (alt yuz kapali; kopuk gorunmesin)."""
        ph = rng.random() * math.pi
        rim = [(x + r * (0.85 + 0.3 * rng.random()) * math.cos(ph + 2 * math.pi * k / sides),
                y0 - 0.25 * r * rng.random(),
                z + r * (0.85 + 0.3 * rng.random()) * math.sin(ph + 2 * math.pi * k / sides)) for k in range(sides)]
        tip = (x + (rng.random() - 0.5) * 0.3, y1, z + (rng.random() - 0.5) * 0.3)
        under = (x, y0 + 0.15 * (y1 - y0), z)
        for k in range(sides):
            a, b = rim[k], rim[(k + 1) % sides]
            out = ((a[0] + b[0]) / 2 - x, 0.5, (a[2] + b[2]) / 2 - z)
            t_mb.tri(mat, a, b, tip, out, [(k * 0.6, 0.0), ((k + 1) * 0.6, 0.0), (k * 0.6 + 0.3, 1.6)])
            t_mb.tri(mat, a, b, under, (0, -1, 0), [(k * 0.6, 0.0), ((k + 1) * 0.6, 0.0), (k * 0.6 + 0.3, 0.6)])

    def broadleaf(x, z, s, mat=None):
        """Genis yaprakli (cinar / ihlamur / dut tipi): egik govde, iki ana dal, 4-6 kumeden puruzlu tac."""
        t_mb = tile_mb(x, z, "trees")
        g = surface_h(x, z) - 0.2
        th = (2.0 + rng.random() * 0.9) * s
        lean = ((rng.random() - 0.5) * 0.5 * s, (rng.random() - 0.5) * 0.5 * s)
        trunk(t_mb, "Trunk", x, z, g, g + th, 0.24 * s, 0.17 * s, 5, lean)
        top = (x + lean[0], g + th, z + lean[1])
        R = (1.9 + rng.random() * 0.7) * s
        leaves = mat or rng.choice(("Leaves_A", "Leaves_A", "Leaves_B", "Leaves_C", "Leaves_D"))
        # iki ana dal tacin icine uzanir
        for k in range(2):
            a = rng.random() * math.pi * 2
            trunk(t_mb, "Trunk", top[0], top[2], top[1] - 0.2, top[1] + R * 0.9,
                  0.13 * s, 0.06 * s, 3, (math.cos(a) * R * 0.45, math.sin(a) * R * 0.45))
        cy = top[1] + R * 0.75
        blob(t_mb, leaves, top[0], cy, top[2], R, 0.78, 0.30)                    # cekirdek
        n = 3 + int(rng.random() * 2)
        for k in range(n):                                                        # cevre kumeleri: girintili siluet
            a = rng.random() * math.pi * 2 + k * 2 * math.pi / n
            d = R * (0.55 + rng.random() * 0.3)
            r = R * (0.48 + rng.random() * 0.22)
            dy = R * (rng.random() * 0.55 - 0.15)
            shade = "Leaves_C" if dy < 0 and rng.random() < 0.5 else leaves     # alttaki kumeler golgede, koyu
            blob(t_mb, shade, top[0] + math.cos(a) * d, cy + dy, top[2] + math.sin(a) * d, r, 0.85, 0.32, coarse=True)

    def pine(x, z, s):
        """Karacam: duz, uzun govde; ust uclukte kat kat igne yaprakli koniler (yasli olanlarin tepesi yayvan)."""
        t_mb = tile_mb(x, z, "trees")
        g = surface_h(x, z) - 0.2
        H = (9.0 + rng.random() * 5.0) * s
        trunk(t_mb, "Trunk_Pine", x, z, g, g + H * 0.92, 0.22 * s, 0.09 * s, 5)
        layers = 3 + int(rng.random() * 2)
        crown_base = g + H * (0.38 + rng.random() * 0.12)
        for k in range(layers):
            f = k / layers
            y0 = crown_base + (H - (crown_base - g)) * f * 0.85
            r = (2.6 - 1.6 * f) * s * (0.85 + rng.random() * 0.3)
            cone_layer(t_mb, "Leaves_Pine", x, z, y0, y0 + r * 1.25 + 0.6, r)

    def poplar(x, z, s):
        """Kavak (Konya ovasinin simgesi): ince uzun, sutun gibi dar tac."""
        t_mb = tile_mb(x, z, "trees")
        g = surface_h(x, z) - 0.2
        H = (12.0 + rng.random() * 5.0) * s
        trunk(t_mb, "Trunk_Poplar", x, z, g, g + H * 0.55, 0.2 * s, 0.1 * s, 4)
        R = (1.25 + rng.random() * 0.35) * s
        mid = g + H * 0.55
        blob(t_mb, "Leaves_Poplar", x, mid, z, R, (H * 0.55) / R * 0.62, 0.2, -0.9)
        blob(t_mb, "Leaves_Poplar", x + (rng.random() - 0.5) * 0.5, g + H * 0.42, z + (rng.random() - 0.5) * 0.5,
             R * 1.1, 2.0, 0.25, -0.9)

    def shrub(x, z, s):
        """Park cali kumesi: yere yakin 2-3 kume."""
        t_mb = tile_mb(x, z, "trees")
        g = surface_h(x, z) - 0.15
        for k in range(2 + int(rng.random() * 2)):
            a = rng.random() * math.pi * 2
            r = (0.55 + rng.random() * 0.35) * s
            blob(t_mb, "Shrub", x + math.cos(a) * r * 0.8, g + r * 0.55, z + math.sin(a) * r * 0.8, r, 0.75, 0.3, coarse=True)

    def tree(x, z, s, park):
        r = rng.random()
        if park:   # koru (Alaaddin Tepesi gibi): genis yaprakli agirlikli, karacam ve kavakla karisik
            if r < 0.30:
                pine(x, z, s)
            elif r < 0.40:
                poplar(x, z, s)
            else:
                broadleaf(x, z, s)
        else:      # cimenlik / bahce
            if r < 0.12:
                pine(x, z, s)
            elif r < 0.30:
                poplar(x, z, s)
            else:
                broadleaf(x, z, s)

    tree_count = shrub_count = street_tree_count = 0
    park_trees = []
    street_spots = []   # cadde agaci / lamba konumlari: otobus duraklari bunlarla cakismasin
    for j in range(CH):
        for i in range(CW):
            c = cat[j][i]
            p = 0.042 if c == G_FOREST else (0.012 if c == G_GRASS else 0.0)
            if not p or blocked[j][i] or no_tree[j][i]:
                continue
            roll = rng.random()
            if roll >= p + 0.008:
                continue
            if any(blocked[jj][ii] for jj in range(max(0, j - 1), min(CH, j + 2)) for ii in range(max(0, i - 1), min(CW, i + 2))):
                continue
            x, z = X0 + (i + rng.random()) * CELL, Z0 + (j + rng.random()) * CELL
            if roll >= p:
                shrub(x, z, 0.9 + rng.random() * 0.5)
                shrub_count += 1
                continue
            tree(x, z, 0.85 + rng.random() * 0.55, c == G_FOREST)
            tree_count += 1
            park_trees.append((x, z))

    # ---------- 7f BITKI ORTUSU: agac diplerinde cim obekleri, park kenarlarinda ot ve yer yer cali, patika
    # kenarlarinda tasli cicek tarhlari (lale ve mevsim cicekleri). Ayri rng: mevcut agac yerlesimi degismez.
    # "plants" katmani: carpismasiz, uzakta cizilmez (Unity: VegetationCuller).
    plant_rng = random.Random(2026)

    def tuft(x, z, s, mat):
        """Cim obegi: basik, yumusak golgeli yuvarlak tumsek (ince yaprak piramitleri gunes altinda kararip diken
        gibi gorunuyordu). Kume ortak rng'yi kullanir: durumu saklanir, obege ozel tohumla calisir, geri yuklenir."""
        mb_ = tile_mb(x, z, "plants")
        g = surface_h(x, z) - 0.04
        R = (0.40 + plant_rng.random() * 0.22) * s
        state = rng.getstate()
        rng.seed(plant_rng.random())
        blob(mb_, mat, x, g + R * 0.12, z, R, 0.55, jitter=0.35, flat_bottom=-0.2, coarse=True)
        rng.setstate(state)

    def flower(mb_, x, y, z, r, mat):
        """Tek cicek kumesi: ust yarim sekizyuzlu (ustten bakinca dolgun renk lekesi)."""
        top = (x, y + r * 0.9, z)
        ring = [(x + math.cos(k * math.pi / 2) * r, y, z + math.sin(k * math.pi / 2) * r) for k in range(4)]
        for k in range(4):
            a, b = ring[k], ring[(k + 1) % 4]
            mb_.tri(mat, a, b, top, ((a[0] + b[0]) / 2 - x, 0.5, (a[2] + b[2]) / 2 - z))

    def flower_bed(x, z, yaw, w, d):
        """Tasli cicek tarhi: alcak bordur, toprak, sira sira lale/mevsim cicegi (bir ya da iki renk)."""
        mb_ = tile_mb(x, z, "plants")
        prev, target["mb"] = target["mb"], mb_
        g = surface_h(x, z) - 0.05
        cs, sn = math.cos(yaw), math.sin(yaw)
        box("Soil", x, z, g, w, 0.22, d, yaw)
        for (ox, oz, sx, sz) in ((0, d / 2, w + 0.3, 0.15), (0, -d / 2, w + 0.3, 0.15), (w / 2, 0, 0.15, d), (-w / 2, 0, 0.15, d)):
            box("BedStone", x + ox * cs - oz * sn, z + ox * sn + oz * cs, g, sx, 0.3, sz, yaw)
        target["mb"] = prev
        palette = ["FlowerRed", "FlowerYellow", "FlowerPink", "FlowerWhite", "FlowerPurple"]
        c1 = plant_rng.choice(palette)
        c2 = plant_rng.choice(palette)
        rows = max(2, int(d / 0.45))
        cols = max(2, int(w / 0.45))
        for ri in range(rows):
            for ci in range(cols):
                lx = (ci + 0.5) / cols * (w - 0.3) - (w - 0.3) / 2 + (plant_rng.random() - 0.5) * 0.12
                lz = (ri + 0.5) / rows * (d - 0.3) - (d - 0.3) / 2 + (plant_rng.random() - 0.5) * 0.12
                fx, fz = x + lx * cs - lz * sn, z + lx * sn + lz * cs
                flower(mb_, fx, g + 0.28, fz, 0.1, "FlowerLeaf")
                flower(mb_, fx, g + 0.38 + plant_rng.random() * 0.08, fz, 0.16, c1 if (ri + (ci // 2)) % 2 == 0 else c2)

    tuft_count = bed_count = 0
    # agac diplerine 2-3 obek
    for (tx_, tz_) in park_trees:
        for _ in range(3 + int(plant_rng.random() * 3)):
            a = plant_rng.random() * math.pi * 2
            rr = 0.5 + plant_rng.random() * 0.9
            tuft(tx_ + math.cos(a) * rr, tz_ + math.sin(a) * rr, 0.9 + plant_rng.random() * 0.5,
                 "GrassTuft" if plant_rng.random() < 0.7 else "GrassTuftDry")
            tuft_count += 1
    # park kenarlari: cim/koru ile kaldirim/meydan arasindaki sinir boyunca, cim tarafinda (yaklasik her 3 m)
    green = (G_GRASS, G_FOREST)
    for j in range(1, CH - 1):
        for i in range(1, CW - 1):
            if cat[j][i] not in green or blocked[j][i] or no_tree[j][i]:
                continue
            for (di, dj) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c2_ = cat[j + dj][i + di]
                if c2_ in green or blocked[j + dj][i + di] or c2_ == G_WATER:
                    continue
                if plant_rng.random() > 0.45:
                    continue
                # sinira 0.3-0.8 m icerde
                bx = X0 + (i + 0.5 + di * 0.5) * CELL - di * plant_rng.uniform(0.3, 0.8) + (plant_rng.random() - 0.5) * CELL * abs(dj)
                bz = Z0 + (j + 0.5 + dj * 0.5) * CELL - dj * plant_rng.uniform(0.3, 0.8) + (plant_rng.random() - 0.5) * CELL * abs(di)
                if plant_rng.random() < 0.12:
                    shrub_rng_state = rng.getstate()   # mevcut rng akisi bozulmasin
                    shrub(bx, bz, 0.55 + plant_rng.random() * 0.25)
                    rng.setstate(shrub_rng_state)
                else:
                    tuft(bx, bz, 0.8 + plant_rng.random() * 0.4, "GrassTuft" if plant_rng.random() < 0.6 else "GrassTuftDry")
                tuft_count += 1
                break
    # cicek tarhlari: park patikalarinin kenarinda, 45-75 m arayla, cimenlik icinde
    for hw, pts, width in lines:
        if hw not in ("footway", "path", "pedestrian"):
            continue
        carry = 15.0 + plant_rng.random() * 25.0
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 1e-3:
                continue
            ux, uz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            t = carry
            while t < L:
                px, pz = a[0] + ux * t, a[1] + uz * t
                side = 1.0 if plant_rng.random() < 0.5 else -1.0
                nx, nz = uz * side, -ux * side
                w_, d_ = plant_rng.uniform(2.2, 4.0), plant_rng.uniform(1.0, 1.6)
                off = width / 2.0 + 0.9 + d_ / 2
                bx, bz = px + nx * off, pz + nz * off
                ok = inside_rect(bx, bz, 4.0)
                for (qx, qz) in ((bx, bz), (bx + ux * w_ / 2, bz + uz * w_ / 2), (bx - ux * w_ / 2, bz - uz * w_ / 2),
                                 (bx + nx * d_ / 2, bz + nz * d_ / 2)):
                    c = cell_of(qx, qz)
                    if c is None or cat[c[1]][c[0]] not in green or blocked[c[1]][c[0]] or no_tree[c[1]][c[0]]:
                        ok = False
                if ok:
                    flower_bed(bx, bz, math.atan2(uz, ux), w_, d_)
                    bed_count += 1
                t += 45.0 + plant_rng.random() * 30.0
            carry = t - L
    print(f"   bitki ortusu: cim obegi/cali {tuft_count}, cicek tarhi {bed_count}")

    # ---------- cadde agaclari: ana yollarin kaldiriminda, bordura yakin, duzenli aralikla (ayni tur, benzer boy)
    carriage = [[False] * CW for _ in range(CH)]   # arac yolu ve tramvay: agac asla buraya dusmesin
    for hw, pts, width in lines:
        if hw in VEHICLE or hw == "tram":
            fill_line(pts, width + 0.8, True, carriage)

    def free_for_street_tree(x, z):
        c = cell_of(x, z)
        if c is None:
            return False
        i, j = c
        if carriage[j][i]:   # agacin kendi hucresi yolda olmasin (bordur ~0.7 m otede: komsu hucre yol olabilir)
            return False
        for jj in range(max(0, j - 1), min(CH, j + 2)):
            for ii in range(max(0, i - 1), min(CW, i + 2)):
                if blocked[jj][ii]:
                    return False
        return True

    for hw, pts, width in lines:
        if hw not in ("primary", "secondary", "tertiary") or width < 9:
            continue
        street_mat = rng.choice(("Leaves_A", "Leaves_B", "Leaves_D"))  # bir cadde boyunca ayni tur
        street_size = 0.8 + rng.random() * 0.25
        offset = width / 2.0 + 1.1
        carry = 6.0 + rng.random() * 4.0
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 1e-3:
                continue
            ux, uz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            t = carry
            while t < L:
                px, pz = a[0] + ux * t, a[1] + uz * t
                for side in (1.0, -1.0):
                    tx, tz = px + uz * offset * side, pz - ux * offset * side
                    if inside_rect(tx, tz, 3.0) and free_for_street_tree(tx, tz):
                        broadleaf(tx, tz, street_size * (0.95 + rng.random() * 0.1), street_mat)
                        street_tree_count += 1
                        street_spots.append((tx, tz))
                t += 11.0 + rng.random() * 2.0
            carry = t - L

    # ---------- sokak donatisi: cadde lambalari (kaldirimda, zikzak) ve park banklari (patika kenarinda, yola donuk)
    def street_lamp(x, z, toward):
        """Celik direk + yola uzanan kol + lamba basligi. toward: yola dogru birim yon (x, z)."""
        t_mb = tile_mb(x, z, "trees")
        g = surface_h(x, z) - 0.1
        H = 8.5
        trunk(t_mb, "LampPole", x, z, g, g + H, 0.11, 0.07, 6)
        ax, az = x + toward[0] * 1.7, z + toward[1] * 1.7
        trunk(t_mb, "LampPole", x, z, g + H - 0.3, g + H + 0.25, 0.05, 0.05, 4, (toward[0] * 1.7, toward[1] * 1.7))
        yaw = math.atan2(toward[1], toward[0])
        prev, target["mb"] = target["mb"], t_mb  # box() hedef parcaya yazar
        box("LampPole", ax, az, g + H + 0.05, 0.9, 0.22, 0.4, yaw)      # basligin govdesi
        box("LampGlass", ax, az, g + H - 0.03, 0.75, 0.09, 0.32, yaw)   # alt cam
        target["mb"] = prev

    def trash_bin(x, z, g):
        """Belediye cop kutusu: koyu yesil govde, gri kapak (cagiran target['mb']'yi ayarlar)."""
        box("TrashBin", x, z, g, 0.5, 0.85, 0.5)
        box("Metal", x, z, g + 0.85, 0.56, 0.06, 0.56)

    def bench(x, z, yaw):
        """Park banki: ahsap oturak + sirtlik, iki metal ayak. yaw: oturanin baktigi yonun dik ekseni."""
        t_mb = tile_mb(x, z, "trees")
        g = surface_h(x, z) - 0.05
        cs, sn = math.cos(yaw), math.sin(yaw)
        prev, target["mb"] = target["mb"], t_mb  # box() hedef parcaya yazar
        for side in (-0.75, 0.75):
            box("LampPole", x + cs * side, z + sn * side, g, 0.08, 0.45, 0.45, yaw)
        box("BenchWood", x, z, g + 0.42, 1.8, 0.07, 0.45, yaw)
        bx, bz = x - (-sn) * 0.22, z - cs * 0.22  # sirtlik oturagin arka kenarinda
        box("BenchWood", bx, bz, g + 0.55, 1.8, 0.45, 0.06, yaw)
        if rng.random() < 0.55:  # yaninda cop kutusu
            trash_bin(x + cs * 1.35, z + sn * 1.35, g)
        target["mb"] = prev

    lamp_count = bench_count = 0
    for hw, pts, width in lines:
        if hw not in ("primary", "secondary", "tertiary") or width < 9:
            continue
        offset = width / 2.0 + 0.5
        carry, side = 14.0, 1.0
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 1e-3:
                continue
            ux, uz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            t = carry
            while t < L:
                px, pz = a[0] + ux * t, a[1] + uz * t
                nx, nz = uz * side, -ux * side          # yolun bu yanina dik
                lx, lz = px + nx * offset, pz + nz * offset
                if inside_rect(lx, lz, 3.0) and free_for_street_tree(lx, lz):
                    street_lamp(lx, lz, (-nx, -nz))
                    lamp_count += 1
                    street_spots.append((lx, lz))
                side = -side                             # zikzak: bir sag, bir sol
                t += 30.0
            carry = t - L

    def in_park(x, z):
        c = cell_of(x, z)
        return c is not None and cat[c[1]][c[0]] in (G_FOREST, G_GRASS) and not blocked[c[1]][c[0]]

    for hw, pts, width in lines:
        if hw not in ("footway", "path"):
            continue
        carry = 8.0 + rng.random() * 10.0
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 1e-3:
                continue
            ux, uz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            t = carry
            while t < L:
                px, pz = a[0] + ux * t, a[1] + uz * t
                side = 1.0 if rng.random() < 0.5 else -1.0
                nx, nz = uz * side, -ux * side
                bx, bz = px + nx * (width / 2.0 + 0.8), pz + nz * (width / 2.0 + 0.8)
                if inside_rect(bx, bz, 3.0) and in_park(bx, bz) and in_park(px, pz):
                    # oturak yola donuk: arkalik yoldan uzakta
                    bench(bx, bz, math.atan2(-nz, -nx) - math.pi / 2)
                    bench_count += 1
                t += 26.0 + rng.random() * 14.0
            carry = t - L

    # ---------- Zafer Meydani (Alaaddin Bulvari, Zafer tramvay duragi yakini): sig havuz, bayrakli sutunlar,
    # Zafer Cesmesi (1924, Istiklal Harbi sehitleri anisina) ve ozgun bir anit sutunu (Selcuklu yildizi tepelikli).
    # Meydandaki modern heykel kopyalanmadi (telif); OSM'de meydan alani olmadigindan duraga en yakin bos alan secilir.
    def zafer_meydani():
        stop = None
        for n_ in osm_nodes_named("Zafer"):
            stop = n_
            break
        if stop is None:
            return None
        R = 10.0
        best = None
        for dz_ in range(-45, 46):
            for dx_ in range(-45, 46):
                cx_, cz_ = stop[0] + dx_ * 2.0, stop[1] + dz_ * 2.0
                d2 = (cx_ - stop[0]) ** 2 + (cz_ - stop[1]) ** 2
                if best is not None and d2 >= best[0]:
                    continue
                ok = True
                for k in range(16):
                    for rr in (0.0, R * 0.5, R):
                        c = cell_of(cx_ + math.cos(k * math.pi / 8) * rr, cz_ + math.sin(k * math.pi / 8) * rr)
                        if c is None or blocked[c[1]][c[0]] or carriage[c[1]][c[0]] or cat[c[1]][c[0]] == G_WATER:
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    best = (d2, cx_, cz_)
        if best is None:
            return None
        _, cx_, cz_ = best
        t_mb = tile_mb(cx_, cz_, "trees")
        prev, target["mb"] = target["mb"], t_mb
        g = ground_h(cx_, cz_) - 0.05
        cylinder(cx_, cz_, g, g + 0.5, 6.4, 24, "Stone")                  # havuz kenari
        cap(cylinder(cx_, cz_, g, g + 0.38, 6.0, 24, "PoolWater"), "PoolWater")  # su
        cylinder(cx_, cz_, g, g + 1.2, 1.3, 8, "Stone")                   # anit kaidesi
        top = cylinder(cx_, cz_, g + 1.2, g + 9.0, 0.55, 8, "Stone")      # anit govdesi
        cap(top, "Stone")
        for rot in (0.0, math.pi / 4):                                     # sekiz koseli Selcuklu yildizi (iki kare)
            box("Bronze", cx_, cz_, g + 9.0, 1.4, 1.4, 0.22, rot)
            box("Bronze", cx_, cz_, g + 9.0, 1.4, 1.4, 0.22, rot + math.pi / 2)
        for k in range(8):                                                 # bayrakli sutunlar
            a = k * math.pi / 4 + math.pi / 8
            fx, fz = cx_ + math.cos(a) * 9.0, cz_ + math.sin(a) * 9.0
            fg = ground_h(fx, fz) - 0.05
            cylinder(fx, fz, fg, fg + 7.0, 0.12, 8, "Column")
            tx_, tz_ = -math.sin(a), math.cos(a)                           # bayrak cembere teget dalgalanir
            p0 = (fx, fz)
            p1 = (fx + tx_ * 1.6, fz + tz_ * 1.6)
            for sgn in (1, -1):
                o = (math.cos(a) * 0.02 * sgn, math.sin(a) * 0.02 * sgn)
                a0, a1 = (p0[0] + o[0], p0[1] + o[1]), (p1[0] + o[0], p1[1] + o[1])
                if sgn < 0:
                    a0, a1 = a1, a0
                t_mb.quad("FlagTR", (a0[0], fg + 5.9, a0[1]), (a1[0], fg + 5.9, a1[1]), (a1[0], fg + 6.95, a1[1]),
                          (a0[0], fg + 6.95, a0[1]), (math.cos(a) * sgn, 0.0, math.sin(a) * sgn),
                          [(0, 0), (1, 0), (1, 1), (0, 1)] if sgn > 0 else [(1, 0), (0, 0), (0, 1), (1, 1)])
        # Zafer Cesmesi: havuzun guneyinde tas cesme (nis + kemer tepeligi)
        ex_, ez_ = cx_, cz_ - 12.0
        eg = ground_h(ex_, ez_) - 0.05
        box("Stone", ex_, ez_, eg, 3.2, 2.6, 1.1)
        box("Ruin", ex_, ez_ + 0.5, eg + 0.5, 1.3, 1.6, 0.2)
        cone(ring(ex_, ez_, eg + 2.6, 1.0, 4, math.pi / 4), (ex_, eg + 3.4, ez_), "Stone")
        for k in range(4):                                                 # banklar
            a = k * math.pi / 2
            bench(cx_ + math.cos(a) * 12.5, cz_ + math.sin(a) * 12.5, a + math.pi / 2)
        target["mb"] = prev
        landmarks.append({"name": "Zafer Meydanı", "x": round(cx_, 1), "y": round(g, 1), "z": round(cz_, 1)})
        return (cx_, cz_)

    zafer_pos = zafer_meydani()

    # ---------- ortam sesi haritasi (AmbienceMixer): 10 m bloklarda yesil alan ve arac yolu yogunlugu (0-9).
    # Parkta kus sesi, caddede trafik ugultusu; ses yayildigi icin bloklar komsulariyla yumusatilir.
    B = 5  # 5 hucre x 2 m = 10 m
    BW, BH = (CW + B - 1) // B, (CH + B - 1) // B
    green = [[0.0] * BW for _ in range(BH)]
    road = [[0.0] * BW for _ in range(BH)]
    for j in range(CH):
        for i in range(CW):
            if cat[j][i] in (G_FOREST, G_GRASS) and not blocked[j][i]:
                green[j // B][i // B] += 1.0 / (B * B)
            if carriage[j][i]:
                road[j // B][i // B] += 1.6 / (B * B)

    def blur(grid, passes):
        for _ in range(passes):
            out = [[0.0] * BW for _ in range(BH)]
            for j in range(BH):
                for i in range(BW):
                    tot = cnt = 0.0
                    for jj in range(max(0, j - 1), min(BH, j + 2)):
                        for ii in range(max(0, i - 1), min(BW, i + 2)):
                            tot += grid[jj][ii]
                            cnt += 1
                    out[j][i] = tot / cnt
            grid = out
        return grid

    green, road = blur(green, 1), blur(road, 2)

    def encode(grid):
        return "".join(str(min(9, int(v * 9 + 0.5))) for row in grid for v in row)

    amb_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Assets", "_Game", "Resources", "Minimap")
    os.makedirs(amb_dir, exist_ok=True)
    with open(os.path.join(amb_dir, f"{key}_ambience.json"), "w", encoding="utf-8") as f:
        json.dump({"x0": X0, "z0": Z0, "cell": CELL * B, "w": BW, "h": BH,
                   "green": encode(green), "road": encode(road)}, f, separators=(",", ":"))

    # ---------- zemin: her parca kendi agi (paylasilan vertex, yumusak). Dortlu agac (quadtree) sadelestirme:
    # ayni zemin turundeki 4x4 ve ustu bloklar, KENARDAKI TUM izgara noktalari korunarak merkezden yelpaze
    # ucgenlenir -> komsu blok hangi boyutta olursa olsun ortak kenar noktalari ayni: catlak (T-kavsagi) olusmaz.
    # Karisik bolgeler 2 m'lik hucreye kadar bolunur. (Duz cimenlik/kaldirimda ~4-8 kat az ucgen.)
    # ---------- 7d: KOSE / DIP KARARMASI (ambient occlusion), harita uretilirken bir kez hesaplanir (telefonda
    # calisma ani maliyeti yok). Kose rengi alfa kanalina yazilir; PatroQnia/MapArray ortam isigini ve rengi karartir.
    #  - zemin ve kaldirim: bina dibine yaklastikca kararir (bina maskesinden uzaklik alani)
    #  - bina ve ayrintilar: duvarin zemine yakin kismi kararir
    #  - agaclar: govde dibi ve tacin alt kismi kararir
    INF = 10 ** 9
    wall_cells = [[0 if blocked[j][i] else INF for i in range(CW)] for j in range(CH)]
    from collections import deque
    dq = deque((i, j) for j in range(CH) for i in range(CW) if blocked[j][i])
    while dq:
        i, j = dq.popleft()
        d = wall_cells[j][i] + 1
        for ii, jj in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= ii < CW and 0 <= jj < CH and wall_cells[jj][ii] > d:
                wall_cells[jj][ii] = d
                dq.append((ii, jj))

    def wall_dist(x, z):
        """Bina duvarina yaklasik uzaklik (m): hucre merkezleri arasinda dogrusal karisim (yumusak gecis)."""
        u = (x - X0) / CELL - 0.5
        v = (z - Z0) / CELL - 0.5
        i, j = int(math.floor(u)), int(math.floor(v))
        tu, tv = u - i, v - j

        def g(ii, jj):
            ii = max(0, min(CW - 1, ii))
            jj = max(0, min(CH - 1, jj))
            return min(wall_cells[jj][ii], 8) * CELL
        a = g(i, j) * (1 - tu) + g(i + 1, j) * tu
        b = g(i, j + 1) * (1 - tu) + g(i + 1, j + 1) * tu
        return max(0.0, a * (1 - tv) + b * tv - CELL * 0.5)

    def smooth01(e0, e1, x):
        t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
        return t * t * (3 - 2 * t)

    def ao_ground(x, y, z):
        return 0.5 + 0.5 * smooth01(0.0, 3.2, wall_dist(x, z))

    def ao_building(x, y, z):
        return 0.45 + 0.55 * smooth01(0.0, 2.6, y - ground_h(x, z))

    def ao_tree(x, y, z):
        return 0.62 + 0.38 * smooth01(0.5, 7.0, y - ground_h(x, z))

    def ao_plant(x, y, z):
        return 0.72 + 0.28 * smooth01(0.0, 0.5, y - surface_h(x, z))

    AO_FN = {"roads": ao_ground, "sidewalks": ao_ground, "buildings": ao_building, "details": ao_building, "trees": ao_tree,
             "plants": ao_plant}

    # ---------- zemin sinirlarini yumusat (7a): turler arasi sinir 2 m'lik hucre kenarlarini izledigi icin merdiven
    # gibi tirtikliydi. Sinirdaki izgara noktalari sinir cizgisi boyunca komsularinin ortasina dogru kaydirilir
    # (birkac tur): 45 derecelik basamak duz cizgi, sig basamak yumusak egri olur. Kesisim (3+ tur) ve harita kenari
    # noktalari sabit; kayma hucre yarisini asmaz (ucgen ters donmez). Kayma (i, j) basina tektir: komsu parcalarda
    # ayni nokta ayni yere gider (catlak yok). Ek ucgen yok: performans maliyeti sifir.
    nbr = {}

    def link(a, b):
        nbr.setdefault(a, []).append(b)
        nbr.setdefault(b, []).append(a)

    for j in range(CH):
        row = cat[j]
        for i in range(1, CW):
            if row[i - 1] != row[i]:
                link((i, j), (i, j + 1))          # dikey kenar x = i
    for j in range(1, CH):
        prev, row = cat[j - 1], cat[j]
        for i in range(CW):
            if prev[i] != row[i]:
                link((i, j), (i + 1, j))          # yatay kenar z = j
    edge_pts = [k for k, n in nbr.items() if len(n) == 2 and 0 < k[0] < CW and 0 < k[1] < CH]
    disp = {k: (0.0, 0.0) for k in nbr}
    MAX_SHIFT = 0.42 * CELL
    for _ in range(5):
        new = {}
        for k in edge_pts:
            (ax, az), (bx, bz) = nbr[k][0], nbr[k][1]
            da, db = disp[nbr[k][0]], disp[nbr[k][1]]
            tx = ((ax + bx) * CELL + da[0] + db[0]) * 0.5 - k[0] * CELL   # komsularin ortasi (kaymali)
            tz = ((az + bz) * CELL + da[1] + db[1]) * 0.5 - k[1] * CELL
            dx, dz = disp[k]
            dx += (tx - dx) * 0.6
            dz += (tz - dz) * 0.6
            new[k] = (max(-MAX_SHIFT, min(MAX_SHIFT, dx)), max(-MAX_SHIFT, min(MAX_SHIFT, dz)))
        disp.update(new)
    moved = sum(1 for k in edge_pts if disp[k] != (0.0, 0.0))
    print(f"   zemin sinirlari yumusatildi: {moved} nokta (sinir noktasi {len(nbr)})")

    ground_verts = ground_tris = 0
    for tz in range(TZ):
        for tx in range(TX):
            i0, i1 = tx * TC, min((tx + 1) * TC, CW)
            j0, j1 = tz * TC, min((tz + 1) * TC, CH)
            verts, vidx = [], {}
            subs = {m: [] for m in GROUND_MATS}

            def gv(i, j):
                k = (i, j)
                if k not in vidx:
                    vidx[k] = len(verts)
                    d = disp.get(k)
                    if d is None or d == (0.0, 0.0):
                        verts.append((X0 + i * CELL, H[j][i], Z0 + j * CELL))
                    else:
                        x, z = X0 + i * CELL + d[0], Z0 + j * CELL + d[1]
                        verts.append((x, ground_h(x, z), z))
                return vidx[k]

            def uniform(bi, bj, n):
                if bi + n > i1 or bj + n > j1:
                    return None
                c0 = cat[bj][bi]
                for jj in range(bj, bj + n):
                    row = cat[jj]
                    for ii in range(bi, bi + n):
                        if row[ii] != c0:
                            return None
                return c0

            def emit(bi, bj, n):
                if bi >= i1 or bj >= j1:
                    return
                if n == 1:
                    a, b = gv(bi, bj), gv(bi + 1, bj)
                    c, d = gv(bi, bj + 1), gv(bi + 1, bj + 1)
                    subs[GROUND_MATS[cat[bj][bi]]].extend((a, c, d, a, d, b))  # yukaridan saat yonu
                    return
                c0 = uniform(bi, bj, n) if n >= 4 else None
                if c0 is None:
                    h = n // 2
                    for (di, dj) in ((0, 0), (h, 0), (0, h), (h, h)):
                        emit(bi + di, bj + dj, h)
                    return
                # Kenar halkasi (yukaridan saat yonunun tersi): alt kenar sola->saga, sag kenar yukari,
                # ust kenar saga->sola, sol kenar asagi. Ucgen (merkez, sonraki, onceki) = yukaridan saat yonu.
                ring = [gv(bi + k, bj) for k in range(n)] + [gv(bi + n, bj + k) for k in range(n)] + \
                       [gv(bi + n - k, bj + n) for k in range(n)] + [gv(bi, bj + n - k) for k in range(n)]
                cx, cz = X0 + (bi + n / 2) * CELL, Z0 + (bj + n / 2) * CELL
                verts.append((cx, ground_h(cx, cz), cz))
                ci = len(verts) - 1
                out = subs[GROUND_MATS[c0]]
                for k in range(len(ring)):
                    out.extend((ci, ring[(k + 1) % len(ring)], ring[k]))

            emit(i0, j0, TC)
            tiles.setdefault((tx, tz), {})["ground"] = {
                "ao": [round(ao_ground(*p), 2) for p in verts],
                "v": [round(cc, 2) for p in verts for cc in p], "uv": [],
                "subs": [sub_json(m, t) for m, t in subs.items() if t]}
            ground_verts += len(verts)
            ground_tris += sum(len(t) for t in subs.values()) // 3

    # ---------- araclar: ara sokaklarda kenara park etmis. Ana caddeler (primary/secondary) bos: oradan trafik akar
    veh_rng = random.Random(1923)
    MODELS = [("NormalCar1", 3), ("NormalCar2", 3), ("Taxi", 2), ("SUV", 2), ("SportsCar", 1), ("SportsCar2", 1), ("Cop", 1)]
    model_pool = [m for m, w in MODELS for _ in range(w)]
    vehicles = []

    def vehicle_ok(x, z, min_gap):
        if not inside_rect(x, z, 15.0):
            return False
        c = cell_of(x, z)
        if c is None or blocked[c[1]][c[0]]:
            return False
        return all(math.hypot(x - v["x"], z - v["z"]) >= min_gap for v in vehicles)

    def add_vehicle(x, z, yaw, model):
        vehicles.append({"model": model, "x": round(x, 2), "y": round(ground_h(x, z) + Y_ROAD, 2),
                         "z": round(z, 2), "yaw": round(yaw % 360, 1)})

    for hw, pts, width in lines:
        if hw not in ("residential", "tertiary", "living_street", "unclassified"):
            continue
        rs = resample(pts, 1.0)
        if len(rs) < 30:
            continue
        k = 12 + veh_rng.randint(0, 10)
        while k < len(rs) - 12:  # kavsaklara (yol uclarina) arac koyma
            a, b = rs[k - 1], rs[k + 1]
            dx, dz = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dz) or 1.0
            ux, uz = dx / L, dz / L
            side = veh_rng.choice((-1, 1))
            road_yaw = math.degrees(math.atan2(ux, uz))
            if veh_rng.random() < 0.3:  # sokak kenarina, yola paralel park
                off = (width / 2 - 1.2) * side
                x, z = rs[k][0] - uz * off, rs[k][1] + ux * off
                if vehicle_ok(x, z, 6.5):
                    add_vehicle(x, z, road_yaw + (0 if side > 0 else 180) + veh_rng.uniform(-4, 4), veh_rng.choice(model_pool))
            k += veh_rng.randint(16, 34)

    # ---------- trafik yol agi (TrafficManager): ana caddeler, kavsak dugumlerinde bolunmus kenarlar.
    # Her kenar: a -> b dugumleri, 4 m araliklarla nokta (x, yol yuksekligi, z), genislik, tek yon bilgisi.
    TRAFFIC = {"primary", "primary_link", "secondary", "secondary_link"}
    tways = []
    for w in ways.values():
        t = w.get("tags", {})
        if t.get("highway") not in TRAFFIC or t.get("area") == "yes":
            continue
        ids = [n for n in w.get("nodes", []) if n in nodes]
        ow = t.get("oneway")
        if ow == "-1":
            ids = ids[::-1]
        if len(ids) >= 2:
            tways.append((ids, ROAD_WIDTH.get(t["highway"], 9), ow in ("yes", "1", "true", "-1")))
    node_use = {}
    for ids, _, _ in tways:
        for n in set(ids):
            node_use[n] = node_use.get(n, 0) + 1
    node_index = {}

    def nid(n):
        if n not in node_index:
            node_index[n] = len(node_index)
        return node_index[n]

    traffic_edges = []
    for ids, width, oneway in tways:
        runs, cur = [], []
        for n in ids:  # bolum icinde kalan ardisik parcalar (disari tasan yol: cikmaz, araba orada yenilenir)
            if inside_rect(nodes[n][0], nodes[n][1], 12.0):
                cur.append(n)
            else:
                if len(cur) >= 2:
                    runs.append(cur)
                cur = []
        if len(cur) >= 2:
            runs.append(cur)
        for run in runs:
            start = 0
            for k in range(1, len(run)):
                if k == len(run) - 1 or node_use.get(run[k], 0) >= 2:
                    seg = run[start:k + 1]
                    rpts = resample([nodes[n] for n in seg], 4.0)
                    flat = []
                    for (x, z) in rpts:
                        flat += [round(x, 2), round(ground_h(x, z) + Y_ROAD, 2), round(z, 2)]
                    if len(rpts) >= 2:
                        traffic_edges.append({"a": nid(seg[0]), "b": nid(seg[-1]), "w": width, "o": 1 if oneway else 0, "p": flat})
                    start = k
    # Otobus duraklari: her tek yonlu kenarin sag kaldiriminda ~230 m'de bir (kavsaga 30 m'den yakin degil)
    bus_stops = []

    def bus_stop(x, z, along, toward):
        """Cam arkalikli, catili durak: bank, cop kutusu, 'DURAK' tabelali direk. toward: yola dogru birim yon."""
        t_mb = tile_mb(x, z, "trees")
        prev, target["mb"] = target["mb"], t_mb
        g = surface_h(x, z) - 0.05
        yaw = math.atan2(along[1], along[0])
        bx, bz = x - toward[0] * 0.75, z - toward[1] * 0.75
        box("StopGlass", bx, bz, g + 0.25, 3.8, 2.0, 0.06, yaw)                  # arka cam (yerden biraz yukarida)
        for sgn in (-1, 1):                                                     # yan camlar
            box("StopGlass", x + along[0] * 1.9 * sgn - toward[0] * 0.3, z + along[1] * 1.9 * sgn - toward[1] * 0.3,
                g + 0.25, 0.06, 2.0, 0.9, yaw)
            for fwd in (-0.75, 0.15):                                           # metal kose dikmeleri
                box("Metal", x + along[0] * 1.95 * sgn + toward[0] * fwd, z + along[1] * 1.95 * sgn + toward[1] * fwd,
                    g, 0.1, 2.45, 0.1, yaw)
        box("StopRoof", x - toward[0] * 0.3, z - toward[1] * 0.3, g + 2.45, 4.3, 0.18, 1.7, yaw)
        box("BenchWood", bx + toward[0] * 0.3, bz + toward[1] * 0.3, g + 0.45, 2.6, 0.08, 0.42, yaw)
        trash_bin(x + along[0] * 2.6, z + along[1] * 2.6, g)
        px, pz = x - along[0] * 2.6 + toward[0] * 0.2, z - along[1] * 2.6 + toward[1] * 0.2
        box("Metal", px, pz, g, 0.07, 2.9, 0.07)
        # tabela: yola paralel (iki yuzu), soforler ve yolcular gorsun
        y0, y1 = g + 2.2, g + 2.9
        for sgn in (1, -1):
            o = (toward[0] * 0.05 * sgn, toward[1] * 0.05 * sgn)
            a = (px - along[0] * 0.35 + o[0], pz - along[1] * 0.35 + o[1])
            b = (px + along[0] * 0.35 + o[0], pz + along[1] * 0.35 + o[1])
            if sgn > 0:  # yoldan bakan icin sag = -along: yazi aynali gorunmesin
                a, b = b, a
            t_mb.quad("BusSign", (a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y1, b[1]), (a[0], y1, a[1]),
                      (toward[0] * sgn, 0.0, toward[1] * sgn), [(0, 0), (1, 0), (1, 1), (0, 1)])
        target["mb"] = prev
        bus_stops.extend([round(x, 2), round(g, 2), round(z, 2), round(math.degrees(math.atan2(toward[0], toward[1])), 1)])

    for e in traffic_edges:
        if e["o"] != 1:
            continue
        P = [(e["p"][i], e["p"][i + 2]) for i in range(0, len(e["p"]), 3)]
        seg = [math.hypot(P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1]) for i in range(len(P) - 1)]
        total = sum(seg)
        t, acc = 60.0, 0.0
        for i in range(len(P) - 1):
            while t <= acc + seg[i] and t < total - 30.0:
                f = (t - acc) / max(seg[i], 1e-6)
                x = P[i][0] + (P[i + 1][0] - P[i][0]) * f
                z = P[i][1] + (P[i + 1][1] - P[i][1]) * f
                dx, dz = (P[i + 1][0] - P[i][0]) / max(seg[i], 1e-6), (P[i + 1][1] - P[i][1]) / max(seg[i], 1e-6)
                right = (dz, -dx)
                sx, sz = x + right[0] * (e["w"] / 2 + 1.5), z + right[1] * (e["w"] / 2 + 1.5)
                c = cell_of(sx, sz)
                behind = cell_of(sx + right[0] * 2.5, sz + right[1] * 2.5)   # duragin arkasi: bina olmasin (genis kaldirim)
                clear = c is not None and not blocked[c[1]][c[0]] and not carriage[c[1]][c[0]] and \
                    behind is not None and not blocked[behind[1]][behind[0]] and \
                    all((sx - q[0]) ** 2 + (sz - q[1]) ** 2 > 3.2 ** 2 for q in street_spots)
                if clear and inside_rect(sx, sz, 5.0):
                    bus_stop(sx, sz, (dx, dz), (-right[0], -right[1]))
                    t += 230.0
                else:
                    t += 15.0   # uygun yer yoksa biraz ileride dene
            acc += seg[i]

    # Yaya gecitleri: kavsak dugumlerinde (3+ kenar) her yol agzina, kavsaktan 7 m geride zebra cizgileri
    degree = {}
    for e in traffic_edges:
        degree[e["a"]] = degree.get(e["a"], 0) + 1
        degree[e["b"]] = degree.get(e["b"], 0) + 1
    crosswalks = 0
    for e in traffic_edges:
        P = [(e["p"][i], e["p"][i + 2]) for i in range(0, len(e["p"]), 3)]
        L_total = sum(math.hypot(P[i + 1][0] - P[i][0], P[i + 1][1] - P[i][1]) for i in range(len(P) - 1))
        if L_total < 24.0:
            continue
        for end, node in ((0, e["a"]), (1, e["b"])):
            if degree.get(node, 0) < 3:
                continue
            q0, q1 = (P[0], P[min(2, len(P) - 1)]) if end == 0 else (P[-1], P[max(0, len(P) - 3)])
            dx, dz = q1[0] - q0[0], q1[1] - q0[1]
            dl = math.hypot(dx, dz) or 1.0
            dx, dz = dx / dl, dz / dl
            cx, cz = q0[0] + dx * 7.0, q0[1] + dz * 7.0
            nx, nz = dz, -dx
            half = e["w"] / 2.0 - 0.6
            t = -half
            while t <= half:
                sx, sz = cx + nx * t, cz + nz * t
                y = ground_h(sx, sz) + Y_MARKING + 0.01
                corners = [(sx - dx * 1.4 - nx * 0.25, sz - dz * 1.4 - nz * 0.25), (sx + dx * 1.4 - nx * 0.25, sz + dz * 1.4 - nz * 0.25),
                           (sx + dx * 1.4 + nx * 0.25, sz + dz * 1.4 + nz * 0.25), (sx - dx * 1.4 + nx * 0.25, sz - dz * 1.4 + nz * 0.25)]
                tile_mb(sx, sz, "roads").quad("Marking", *[(p_[0], y, p_[1]) for p_ in corners], (0, 1, 0))
                t += 1.0
            crosswalks += 1

    res_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Assets", "_Game", "Resources", "Minimap")
    os.makedirs(res_dir, exist_ok=True)
    with open(os.path.join(res_dir, f"{key}_traffic.json"), "w", encoding="utf-8") as f:
        json.dump({"edges": traffic_edges}, f, separators=(",", ":"))

    # ---------- tramvay: bolum icindeki raylardan surekli guzergahlar + gercek duraklar
    import heapq
    from collections import defaultdict

    tram_adj = defaultdict(dict)
    for w in ways.values():
        if w.get("tags", {}).get("railway") != "tram":
            continue
        ns = w.get("nodes", [])
        for a, b in zip(ns, ns[1:]):
            if a in nodes and b in nodes and inside_rect(*nodes[a], 5.0) and inside_rect(*nodes[b], 5.0):
                d = math.dist(nodes[a], nodes[b])
                tram_adj[a][b] = d
                tram_adj[b][a] = d

    def farthest(src, adj):
        dist, prev, pq = {src: 0.0}, {}, [(0.0, src)]
        while pq:
            d, n = heapq.heappop(pq)
            if d > dist[n]:
                continue
            for m, w_ in adj[n].items():
                nd = d + w_
                if nd < dist.get(m, 1e18):
                    dist[m], prev[m] = nd, n
                    heapq.heappush(pq, (nd, m))
        far = max(dist, key=dist.get)
        return far, dist[far], prev

    def longest_path(adj):
        """Agin 'capi': rastgele dugumden en uzaga, oradan en uzaga (cift hat agi icin yeterli)."""
        best = None
        seen = set()
        for start in list(adj):
            if start in seen:
                continue
            u, _, _ = farthest(start, adj)
            v, length, prev = farthest(u, adj)
            path = [v]
            while path[-1] != u:
                path.append(prev[path[-1]])
            seen.update(path)
            seen.update(n for n in adj if n in prev or n == u)
            if best is None or length > best[0]:
                best = (length, path[::-1])
        return best

    stop_nodes = {e["id"]: e["tags"].get("name", "") for e in osm["elements"] if e["type"] == "node"
                  and (e.get("tags", {}).get("railway") == "tram_stop"
                       or (e.get("tags", {}).get("public_transport") == "stop_position" and e["tags"].get("tram") == "yes"))}

    trams = []
    tram_segments = [(nodes[a], nodes[b]) for a in tram_adj for b in tram_adj[a] if a < b]
    for _ in range(2):  # her yon icin bir guzergah
        if not tram_adj:
            break
        res = longest_path(tram_adj)
        if res is None or res[0] < 150:
            break
        length, path_nodes = res
        pts = [nodes[n] for n in path_nodes]
        cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            cum.append(cum[-1] + math.dist(a, b))
        stops = sorted({round(cum[i], 1) for i, n in enumerate(path_nodes) if n in stop_nodes})
        stop_names = [stop_nodes[n] for n in path_nodes if n in stop_nodes]
        dense = resample(pts, 2.0)
        trams.append({"points": [round(c, 2) for p in dense for c in (p[0], ground_h(*p) + Y_RAIL, p[1])],
                      "stops": stops})
        print(f"Tramvay guzergahi: {length:.0f} m, duraklar: {', '.join(stop_names) or '-'}")
        for a, b in zip(path_nodes, path_nodes[1:]):  # bu hatti cikar, ikinci yon kalsin
            tram_adj[a].pop(b, None)
            tram_adj[b].pop(a, None)
        for n in [n for n in tram_adj if not tram_adj[n]]:
            del tram_adj[n]

    # Tramvay altyapisi: katener direkleri, havai tel, durak peronlari (fotograftaki Konya hattina gore)
    catenary = MeshBuilder(uv=True)
    target["mb"] = catenary

    def free_side(x, z, nx, nz, off):
        """Rayin, diger raya ve binaya denk gelmeyen tarafi (+1/-1) ya da None."""
        for side in (1, -1):
            px_, pz_ = x + nx * side * off, z + nz * side * off
            if all(seg_dist(px_, pz_, s0, s1) > 1.6 for s0, s1 in tram_segments) and cell_free_or_road(px_, pz_):
                return side
        return None

    def line_frame(line, k):
        a, b = line[max(0, k - 1)], line[min(len(line) - 1, k + 1)]
        L = math.dist(a, b) or 1.0
        tx, tz = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        return tx, tz, -tz, tx  # teget, sol normal

    for tram in trams:
        p3 = tram["points"]
        line = [(p3[i], p3[i + 2]) for i in range(0, len(p3), 3)]
        rail_y = [p3[i + 1] for i in range(0, len(p3), 3)]

        # Katener direkleri (~36 m arayla): koyu yesil kare kesitli direk + ray ustune uzanan kol
        for k in range(8, len(line) - 8, 18):
            tx, tz, nx, nz = line_frame(line, k)
            side = free_side(line[k][0], line[k][1], nx, nz, 2.8)
            if side is None:
                continue
            px_, pz_ = line[k][0] + nx * side * 2.8, line[k][1] + nz * side * 2.8
            g = surface_h(px_, pz_)
            yaw = math.atan2(nz * side, nx * side)
            box("Mast", px_, pz_, g - 0.3, 0.34, 7.8, 0.34, yaw=yaw)
            arm = 3.3
            box("Mast", px_ - nx * side * arm / 2, pz_ - nz * side * arm / 2, g + 6.5, arm, 0.16, 0.16, yaw=yaw)
            box("Mast", px_ - nx * side * arm / 2, pz_ - nz * side * arm / 2, g + 7.2, arm * 0.9, 0.08, 0.08, yaw=yaw)

        # Havai tel: rayin tam ustunde, iki yuzlu ince serit (her yonden gorunsun)
        for k in range(0, len(line) - 3, 3):
            a, b = line[k], line[k + 3]
            ya, yb = rail_y[k] + 5.7, rail_y[k + 3] + 5.7
            quad_pts = [(a[0], ya, a[1]), (b[0], yb, b[1]), (b[0], yb + 0.05, b[1]), (a[0], ya + 0.05, a[1])]
            tx, tz, nx, nz = line_frame(line, k)
            catenary.quad("Wire", *quad_pts, (nx, 0, nz))
            catenary.quad("Wire", *quad_pts, (-nx, 0, -nz))

        # Durak peronlari: 30 m peron + sundurma (oturma alani, cam arka duvar)
        dense_cum = [0.0]
        for a, b in zip(line, line[1:]):
            dense_cum.append(dense_cum[-1] + math.dist(a, b))
        for st in tram["stops"]:
            k = min(range(len(dense_cum)), key=lambda i: abs(dense_cum[i] - st))
            if k < 3 or k > len(line) - 4:
                continue  # hat ucundaki duraklar bolum sinirinda kalabiliyor
            tx, tz, nx, nz = line_frame(line, k)
            side = free_side(line[k][0], line[k][1], nx, nz, 3.0)
            if side is None:
                continue
            cx, cz = line[k][0] + nx * side * 3.0, line[k][1] + nz * side * 3.0
            g = rail_y[k] - Y_RAIL
            yaw = math.atan2(tz, tx)  # kutunun x ekseni ray boyunca
            box("Platform", cx, cz, g - 0.4, 30.0, 0.7, 3.0, yaw=yaw)
            sx, sz = cx + nx * side * 0.6, cz + nz * side * 0.6
            for along in (-3.6, 3.6):
                for across in (-0.9, 0.9):
                    box("Metal", sx + tx * along + nx * across, sz + tz * along + nz * across, g + 0.3, 0.1, 2.5, 0.1)
            box("ShelterRoof", sx, sz, g + 2.8, 8.2, 0.12, 2.4, yaw=yaw)
            box("ShelterGlass", sx + nx * side * 0.95, sz + nz * side * 0.95, g + 0.5, 7.4, 2.1, 0.06, yaw=yaw)

    # ---------- baslangic: origin'e en yakin, bina ve sudan uzak acik nokta
    spawn = None
    ci, cj = int((0 - X0) / CELL), int((0 - Z0) / CELL)
    for rad in range(0, max(CW, CH)):
        best = None
        for j in range(cj - rad, cj + rad + 1):
            for i in range(ci - rad, ci + rad + 1):
                if max(abs(i - ci), abs(j - cj)) != rad or not (3 <= i < CW - 3 and 3 <= j < CH - 3):
                    continue
                if cat[j][i] == G_WATER:
                    continue
                if any(blocked[jj][ii] for jj in range(j - 3, j + 4) for ii in range(i - 3, i + 4)):
                    continue
                best = (i, j)
                break
            if best:
                break
        if best:
            x, z = X0 + (best[0] + 0.5) * CELL, Z0 + (best[1] + 0.5) * CELL
            spawn = [round(x, 2), round(surface_h(x, z) + 1.2, 2), round(z, 2)]
            break

    # ---------- baslangic aracı: oyuncunun hemen binebilecegi, en yakin arac yolunda bir taksi
    if spawn:
        best = None
        for hw, pts, width in lines:
            if hw not in VEHICLE:
                continue
            rs = resample(pts, 2.0)
            for k in range(1, len(rs) - 1):
                d = math.hypot(rs[k][0] - spawn[0], rs[k][1] - spawn[2])
                if (best is None or d < best[0]) and vehicle_ok(rs[k][0], rs[k][1], 6.0):
                    best = (d, rs[k - 1], rs[k], rs[k + 1])
        if best:
            _, a, p, b = best
            add_vehicle(p[0], p[1], math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])), "Taxi")
            print(f"Baslangic taksisi: {best[0]:.0f} m uzakta")

    # ---------- cikti
    empty = {"v": [], "uv": [], "subs": []}
    tile_list = []
    counts = {"ground": ground_verts, "roads": 0, "sidewalks": 0, "buildings": 0, "details": 0, "trees": 0, "plants": 0}
    for (tx, tz), layers in sorted(tiles.items()):
        entry = {"name": f"{tx:02d}_{tz:02d}"}
        for layer in ("ground", "roads", "sidewalks", "buildings", "details", "trees", "plants"):
            val = layers.get(layer)
            if isinstance(val, MeshBuilder):
                counts[layer] += len(val.v)
                val.ao_fn = AO_FN.get(layer)
                val = val.to_json()
            entry[layer] = val or empty
        tile_list.append(entry)

    out = {
        "name": key,
        "title": cfg["title"],
        "rect": [X0, X1, Z0, Z1],
        "spawn": spawn,
        "tiles": tile_list,
        "vehicles": vehicles,
        "trams": trams,
        "catenary": catenary.to_json(),
        "landmarks": landmarks,
        "busStops": bus_stops,
        "attribution": "Harita verisi (c) OpenStreetMap katkicilari, ODbL. Yukseklik: Copernicus EU-DEM.",
    }
    # Oyunun calisma aninda okudugu simge yapi listesi: harita ile ayni anda yazilir (tek kaynak, eskimez)
    res_lm = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Assets", "_Game", "Resources", "Minimap")
    os.makedirs(res_lm, exist_ok=True)
    with open(os.path.join(res_lm, f"{key}_landmarks.json"), "w", encoding="utf-8") as f:
        json.dump({"landmarks": [l for l in landmarks if l.get("name")]}, f, ensure_ascii=False)
    # Madde 11: islevli dukkanlar (firin, bufe/cay ocagi, terzi, oto galeri) - ShopSystem okur
    with open(os.path.join(res_lm, f"{key}_shops.json"), "w", encoding="utf-8") as f:
        json.dump({"shops": shops}, f, ensure_ascii=False)
    print("Islevli dukkan: " + ", ".join(f"{k} {sum(1 for s in shops if s['kind'] == k)}" for k in ("firin", "bufe", "terzi", "galeri")))
    path = os.path.join(out_dir, f"{key}_map.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    print(f"{cfg['title']}: {X1 - X0:.0f} x {Z1 - Z0:.0f} m, {len(tile_list)} parca, yukseklik farki {max(max(r) for r in H):.1f} m")
    print("Vertex: " + ", ".join(f"{k} {v:,}" for k, v in counts.items()) + f" | toplam {sum(counts.values()):,}")
    print(f"Agac {tree_count} + cadde agaci {street_tree_count} + cali {shrub_count} | lamba {lamp_count}, bank {bench_count} | dolgu bina {infill_count} | arac {len(vehicles)}, trafik kenari {len(traffic_edges)}, yaya gecidi {crosswalks}, durak {len(bus_stops) // 4} | kutsal alan {sanctuary_count} | Zafer Meydani {zafer_pos} | simge yapi {len([l for l in landmarks if l['name']])}")
    print(f"Zemin ucgeni: {ground_tris:,} (tam izgara {CW * CH * 2:,})")
    print(f"Baslangic: {spawn}")
    print(f"Cikti: {os.path.normpath(path)}  ({os.path.getsize(path) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
