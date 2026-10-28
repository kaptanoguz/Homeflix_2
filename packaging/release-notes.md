Kişisel film ve dizi platformunuz: bilgisayarınızdaki filmleri ve dizileri ev ağındaki telefon, TV ve tarayıcılardan Netflix tarzı bir arayüzle izleyin.

![Homeflix ana sayfa](https://raw.githubusercontent.com/kaptanoguz/Homeflix_2/__VERSION__/docs/screenshots/home.jpg)

## İndir

| Sistem | Dosya | Not |
|---|---|---|
| 🪟 **Windows** 10/11 (64-bit) | [`Homeflix-__VERSION__-windows-x64.exe`](https://github.com/kaptanoguz/Homeflix_2/releases/download/__VERSION__/Homeflix-__VERSION__-windows-x64.exe) | Kurulum gerekmez, çift tıklayıp açın |
| 🍎 **macOS** Apple Silicon (M1–M4) | [`Homeflix-__VERSION__-macos-arm64.dmg`](https://github.com/kaptanoguz/Homeflix_2/releases/download/__VERSION__/Homeflix-__VERSION__-macos-arm64.dmg) | macOS 12 ve üzeri |
| 🍎 **macOS** Intel | [`Homeflix-__VERSION__-macos-x64.dmg`](https://github.com/kaptanoguz/Homeflix_2/releases/download/__VERSION__/Homeflix-__VERSION__-macos-x64.dmg) | macOS 12 ve üzeri |
| 🐧 **Linux** (64-bit) | [`Homeflix-__VERSION__-linux-x64.tar.gz`](https://github.com/kaptanoguz/Homeflix_2/releases/download/__VERSION__/Homeflix-__VERSION__-linux-x64.tar.gz) | Ubuntu 22.04+, Debian 12+, Fedora 38+ |
| 📺 **Android TV / telefon** | [Homeflix TV](https://github.com/kaptanoguz/Homeflix_2/releases/tag/android-tv-v1.1) | Sunucuya bağlanan uygulama |

Python ya da başka bir şey kurmanız gerekmez.

## Kurulum

**Windows:** `.exe` dosyasını indirip açın. SmartScreen uyarısı çıkarsa *Ek bilgi → Yine de çalıştır*'a tıklayın.

**macOS:** `.dmg` dosyasını açın ve **Homeflix**'i *Uygulamalar* klasörüne sürükleyin. Uygulama imzasız olduğu için ilk açılışta macOS engeller: *Sistem Ayarları → Gizlilik ve Güvenlik → Yine de Aç*'a tıklayın (ya da Terminal'de `xattr -dr com.apple.quarantine /Applications/Homeflix.app`).

**Linux:**
```bash
tar xzf Homeflix-__VERSION__-linux-x64.tar.gz
cd Homeflix-__VERSION__-linux-x64
./install.sh            # uygulama menüsüne ekler (isteğe bağlı)
./Homeflix/Homeflix     # ya da doğrudan çalıştırın
```
Linux'ta arayüz varsayılan tarayıcıda açılır. Sadece sunucu olarak çalıştırmak için: `./Homeflix/Homeflix --headless`

## İlk açılış

1. Homeflix açılınca **Ayarlar**'dan film ve dizi klasörlerinizi seçin.
2. Diğer cihazlardan `http://<bilgisayarın-ip-adresi>:5000` adresine girin (adres Ayarlar ekranında yazar).
3. MKV/AVI gibi dosyaları canlı dönüştürmek ve gömülü altyazılar için **ffmpeg** gerekir:
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg` (Fedora: `sudo dnf install ffmpeg`)
   - Windows: `winget install ffmpeg`

Kütüphane verisi (veritabanı, posterler, `secrets.json`) şurada tutulur:
- Windows: `%APPDATA%\Homeflix`
- macOS: `~/Library/Application Support/Homeflix`
- Linux: `~/.local/share/homeflix`

TMDb anahtarınızı `secrets.json` dosyasına bu klasörde ekleyebilirsiniz (örnek: [`secrets.example.json`](https://github.com/kaptanoguz/Homeflix_2/blob/main/secrets.example.json)).

## Özellikler

- 🏠 Netflix tarzı ana sayfa: öne çıkanlar, İzlemeye Devam Et, Listem, Son Eklenenler, türlere göre satırlar
- 🎞️ TMDb'den poster, açıklama ve puanlar; seri filmler otomatik **Koleksiyon** olur
- 📺 Diziler: bölüm adları, görselleri, izlendi işareti, sonraki bölüme otomatik geçiş
- ▶️ Tarayıcının açamadığı dosyalar (mkv, avi, ts) canlı dönüştürülür; ses dili seçimi
- 💬 Altyazı: yerel dosyalar, mkv içindeki altyazılar ve otomatik Türkçe altyazı
- 🌐 **Online** sekmesi: kütüphanenizde olmayan filmleri ve dizileri izleyin
- 📱 Kaldığınız yer sunucuda saklanır, telefonda durdurduğunuz filme bilgisayarda devam edersiniz
