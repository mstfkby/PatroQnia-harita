"""
PatroQnia bolum haritalari. Her bolum Konya'nin gercek bir semti.

origin: haritanin (0,0) noktasi (enlem, boylam)
rect:   (x_min, x_max, z_min, z_max) metre; x = dogu, z = kuzey
sanctuaries: savas olmayan, duvarla cevrili kutsal alanlar (OSM ad eslesmesi)
"""

MAPS = {
    # Bolum 1: Alaaddin Tepesi -> Mevlana Caddesi -> Mevlana Muzesi (tarihi merkez)
    "merkez": {
        "folder": "Merkez",
        "title": "Bölüm 1 - Alaaddin'den Mevlana'ya",
        "origin": (37.87259, 32.49218),   # Alaaddin Tepesi
        "rect": (-270.0, 1280.0, -420.0, 280.0),
        "sanctuaries": ["Mevlana", "Mevlâna"],
    },
    # Ilk prototip (yalnizca Alaaddin Tepesi cevresi)
    "alaaddin": {
        "folder": "Alaaddin",
        "title": "Alaaddin Tepesi (prototip)",
        "origin": (37.87259, 32.49218),
        "rect": (-250.0, 250.0, -250.0, 250.0),
        "sanctuaries": [],
    },
}

DEM_STEP = 25.0  # yukseklik orneklem araligi (m); EU-DEM cozunurlugu 25 m
