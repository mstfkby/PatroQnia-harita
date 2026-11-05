# PatroQnia — harita üretim betikleri

Bu depo, **PatroQnia** oyunundaki Konya haritasının OpenStreetMap verisinden nasıl üretildiğini gösterir.
Open Database License (ODbL) 1.0 madde 4.6 gereği, oyunda kullanılan türetilmiş harita verisinin üretim
yöntemi burada herkese açık olarak sunulmaktadır.

## Veri ve atıflar

- **Harita verisi © OpenStreetMap katkıcıları**, Open Database License (ODbL) 1.0 ile lisanslıdır:
  https://www.openstreetmap.org/copyright
  `data/<bölüm>/osm.json` dosyaları OpenStreetMap'ten (Overpass API) alınmış ham verilerdir ve ODbL kapsamındadır.
  Bu verilerden üretilen ve oyunda kullanılan harita verisi de ODbL kapsamındadır.
- **Yükseklik verisi:** Copernicus EU-DEM; değiştirilmiştir; with funding by the European Union.
  (`data/<bölüm>/dem.json`)

## Dosyalar

| Dosya | Ne yapar |
|---|---|
| `maps_config.py` | Bölümlerin sınırları ve başlangıç noktası (enlem/boylam) |
| `fetch_data.py` | Bir bölümün OSM ve yükseklik verisini indirir → `data/<bölüm>/` |
| `build_map.py` | OSM + yükseklik verisinden oyun haritasını üretir: zemin, yollar, kaldırımlar, binalar, ağaçlar, parklar, yer adları, trafik ağı, dükkânlar (JSON çıktı) |
| `minimap.py` | OSM verisinden mini harita görseli üretir |
| `preview_map.py` | Üretilen haritanın kuşbakışı önizlemesi |

## Kullanım

```
python fetch_data.py merkez      # ham veriyi indir (isteğe bağlı; data/ içinde hazır)
python build_map.py merkez       # haritayı üret
python minimap.py merkez         # mini harita
```

Gereksinim: Python 3.10+, Pillow (`minimap.py`, `preview_map.py` için).

Not: `build_map.py` çıktısını oyun projesindeki klasörlere yazar (`../../Assets/...`); bu depoda yalnız
yöntem paylaşıldığından o klasörler yoktur, betik gerekirse oluşturur.

## Telif

Betikler © 2026 Patrox. ODbL madde 4.6 kapsamında, yöntemin incelenebilmesi ve yeniden üretilebilmesi amacıyla
paylaşılmıştır. OpenStreetMap verisi ve ondan türetilen veritabanı ODbL 1.0 ile lisanslıdır.

---

*English:* Map generation scripts for the game PatroQnia (Konya, Türkiye), published to satisfy ODbL 1.0 §4.6.
Map data © OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright). Elevation: Copernicus
EU-DEM, modified, with funding by the European Union.
