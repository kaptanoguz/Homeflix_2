# Homeflix 2

Ev ağı için kişisel film ve dizi platformu.

```bash
./run.sh              # uygulama penceresi
./run.sh --browser    # varsayılan tarayıcıda
./run.sh --headless   # yalnızca sunucu
```

Diğer cihazlardan: `http://<bilgisayarın-ip-adresi>:5000` (adres Ayarlar ekranında yazar).
Farklı port için: `HOMEFLIX_PORT=5001 ./run.sh`.

## Neler var

- **Ana sayfa:** Dönen öne çıkan alan, İzlemeye Devam Et, Listem, Yeni Eklenenler, Koleksiyonlar, Diziler, En Yüksek Puanlılar, türe göre satırlar
- **Koleksiyonlar:** Devam filmleri (Matrix 1-2-3, Felekten Bir Gece 1-2-3, Harry Potter…) TMDb'den otomatik gruplanır. TMDb'de olmayanlar isimdeki numaraya göre gruplanır.
- **Detay sayfası:** Arka plan görseli, süre, türler, koleksiyon şeridi, benzer içerikler. Aynı filmin birden fazla dosyası "Sürümler" altında toplanır.
- **Diziler:** TMDb'den bölüm adları, açıklamaları ve görselleri. Bölüm başına ilerleme çubuğu ve "İzlendi" işareti. Aynı dizinin farklı klasörlerdeki bölümleri birleştirilir.
- **Oynatıcı:**
  - Tarayıcının açamadığı dosyalar (mkv, avi, ts, VOB) anında canlı dönüştürülerek oynatılır.
  - Ses parçası seçilebilir (dublaj / orijinal).
  - Altyazı kaynakları: yerel `.srt/.vtt/.ass`, mkv içine gömülü altyazılar, OpenSubtitles araması, dosyadan yükleme ya da sürükle-bırak.
  - Altyazı boyutu, arka planı ve senkronu (±0,5 sn) ayarlanabilir.
  - Kaldığın yerden devam edilir, sıradaki bölüm geri sayımla otomatik açılır.
  - Hız ayarı, klavye kısayolları ve tam ekran var.
- **Listem ve izleme ilerlemesi** sunucuda tutulur. Telefonda yarım bırakılan film bilgisayarda kaldığı yerden açılır.
- **Arama:** Anlık arama. `/` tuşu ile açılır. Türkçe karakterlere duyarsızdır ("sirin" → "Şirin").

## Yapı

```
app.py                 giriş noktası (sunucu + pencere)
homeflix/
  config.py            yollar, API anahtarları
  db.py                SQLite şeması ve göçler
  names.py             dosya adından başlık / sezon / bölüm çıkarımı
  library.py           disk taraması, Emby/Jellyfin .nfo ve afişleri
  metadata.py          TMDb/OMDb zenginleştirme, koleksiyonlar, bölüm bilgileri
  media.py             ffprobe analizi, canlı akış, görsel önbelleği
  subtitles.py         yerel, gömülü ve çevrimiçi altyazılar
  api.py               HTTP uçları
templates/index.html   sayfa iskeleti ve simgeler
static/app.css         tasarım sistemi
static/app.js          arayüz ve oynatıcı
data/                  veritabanı, afişler, önbellek (v1'den kopyalandı)
```

v1 (`../Homeflix_Linux`) olduğu gibi duruyor, v2 ondan bağımsız çalışır.
