"""
Bir bolumun ham verisini indirir: OpenStreetMap (Overpass API) + yukseklik (OpenTopoData, EU-DEM 25 m).

Kullanim:  python fetch_data.py merkez
Cikti:     data/<bolum>/osm.json, data/<bolum>/dem.json

Not: OpenTopoData genel sunucusu: istek basina en fazla 100 nokta, saniyede 1 istek, gunde 1000 istek.
"""
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request

from maps_config import DEM_STEP, MAPS

UA = {"User-Agent": "PatroQnia-mapgen/1.0 (indie game dev)"}
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HERE = os.path.dirname(os.path.abspath(__file__))


def bbox(cfg, pad=30.0):
    lat0, lon0 = cfg["origin"]
    x0, x1, z0, z1 = cfg["rect"]
    mlat, mlon = 111320.0, 111320.0 * math.cos(math.radians(lat0))
    return (lat0 + (z0 - pad) / mlat, lon0 + (x0 - pad) / mlon, lat0 + (z1 + pad) / mlat, lon0 + (x1 + pad) / mlon)


def fetch_osm(cfg, path):
    s, w, n, e = bbox(cfg)
    bb = f"{s:.6f},{w:.6f},{n:.6f},{e:.6f}"
    keys = ["building", "highway", "railway", "landuse", "leisure", "natural", "amenity",
            "historic", "man_made", "barrier", "tourism"]
    parts = "".join(f'way["{k}"]({bb});' for k in keys)
    parts += "".join(f'relation["{k}"]({bb});' for k in ("building", "landuse", "leisure", "tourism"))
    query = f"[out:json][timeout:180];({parts});(._;>;);out body;"
    body = urllib.parse.urlencode({"data": query}).encode()
    data = None
    # Ana sunucu yogunsa yedek Overpass sunuculari denenir.
    for attempt, server in enumerate(OVERPASS_SERVERS * 2):
        try:
            req = urllib.request.Request(server, data=body, headers=UA)
            with urllib.request.urlopen(req, timeout=240) as r:
                data = r.read()
            break
        except Exception as ex:
            print(f"   {server} -> {ex}; {5 * (attempt + 1)} sn sonra tekrar")
            time.sleep(5 * (attempt + 1))
    if data is None:
        raise RuntimeError("Overpass sunucularina ulasilamadi")
    with open(path, "wb") as f:
        f.write(data)
    d = json.loads(data)
    print(f"  OSM: {len(d['elements'])} oge, {len(data) / 1e6:.1f} MB")


def fetch_dem(cfg, path):
    lat0, lon0 = cfg["origin"]
    x0, x1, z0, z1 = cfg["rect"]
    mlat, mlon = 111320.0, 111320.0 * math.cos(math.radians(lat0))
    nx = int(math.ceil((x1 - x0) / DEM_STEP)) + 1
    nz = int(math.ceil((z1 - z0) / DEM_STEP)) + 1
    pts = [(lat0 + (z0 + j * DEM_STEP) / mlat, lon0 + (x0 + i * DEM_STEP) / mlon) for j in range(nz) for i in range(nx)]
    heights = []
    for k in range(0, len(pts), 100):
        loc = "|".join(f"{a:.6f},{b:.6f}" for a, b in pts[k:k + 100])
        url = "https://api.opentopodata.org/v1/eudem25m?locations=" + urllib.parse.quote(loc, safe=",|.")
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                    res = json.load(r)
                if res.get("status") != "OK":
                    raise RuntimeError(res)
                break
            except Exception as ex:  # gecici sunucu hatasi: bekle ve tekrar dene
                if attempt == 2:
                    raise
                print("   tekrar deneniyor:", ex)
                time.sleep(3)
        heights += [r["elevation"] for r in res["results"]]
        print(f"  DEM: {min(k + 100, len(pts))}/{len(pts)}", end="\r")
        time.sleep(1.1)
    if any(h is None for h in heights):
        raise RuntimeError("Yukseklik verisinde bosluk var")
    with open(path, "w") as f:
        json.dump({"dataset": "eudem25m", "nx": nx, "nz": nz, "step": DEM_STEP,
                   "x0": x0, "z0": z0, "heights": heights}, f)
    print(f"\n  DEM: {nx}x{nz} nokta, {min(heights):.1f}-{max(heights):.1f} m")


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else "merkez"
    cfg = MAPS[key]
    out = os.path.join(HERE, "data", key)
    os.makedirs(out, exist_ok=True)
    print(f"{cfg['title']} verisi indiriliyor...")
    fetch_osm(cfg, os.path.join(out, "osm.json"))
    fetch_dem(cfg, os.path.join(out, "dem.json"))
    print("Tamam:", out)
