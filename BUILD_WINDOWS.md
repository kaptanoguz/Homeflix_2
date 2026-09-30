# Windows Executable Derleme Kılavuzu

## Gereksinimler

- Python 3.8+
- pip (Python paket yöneticisi)
- NSIS (installer oluşturmak için, isteğe bağlı)
- cairosvg (SVG → ICO dönüştürmesi için, isteğe bağlı)

## Kurulum Adımları

### 1. Bağımlılıkları Yükleyin

```bash
pip install -r requirements-build.txt
```

### 2. İcon Dönüştürme (İsteğe Bağlı)

SVG ikonunuzu Windows ICO formatına çevirmek için:

```bash
pip install cairosvg
python -c "from cairosvg import svg2png; svg2png(url='static/icon.svg', write_to='static/icon.png'); print('PNG oluşturuldu')"
```

Sonra çevrimiçi bir dönüştürücü kullanarak PNG → ICO dönüştürün
([CloudConvert](https://cloudconvert.com/) gibi).

### 3. Executable Oluşturun

```bash
python build_windows.py
```

Veya manuel olarak:

```bash
python -m PyInstaller homeflix.spec
```

### 4. Kurulum Paketi Oluşturun (İsteğe Bağlı)

NSIS yüklü ise:

```bash
makensis windows_installer.nsi
```

## Çıktılar

- `dist/Homeflix/` - Portable executable dizini
- `dist/Homeflix/Homeflix.exe` - Ana uygulama dosyası
- `dist/HomeflixInstaller.exe` - Kurulum paketi (NSIS ile oluşturulmuş)

## Dağıtım

### Portable Sürüm

1. `dist/Homeflix/` klasörünün tamamını kopyalayın
2. Zip dosyasına sıkıştırın: `Homeflix-v2.zip`
3. Kullanıcılar çıkarıp `Homeflix.exe`'yi çalıştırabilir

### Kurulum Paketi ile Dağıtım

1. `HomeflixInstaller.exe`'yi dağıtın
2. Kullanıcılar bunu çalıştırıp kurabilir
3. Start Menu'den "Homeflix" ile başlatabilir

## Sorun Çözme

### "ModuleNotFoundError" hatası

Spec dosyasında `hiddenimports` listeyi kontrol edin:

```python
hiddenimports=[
    'flask',
    'waitress',
    'webview',
    # Diğer modüller...
]
```

### Executable çalışmıyor

1. Konsol penceresinde hata görmek için `homeflix.spec`'te `console=True` yapın
2. `python app.py` ile doğrudan çalıştırmayı deneyin
3. Tüm bağımlılıkların yüklü olduğunu kontrol edin

### Executable çok büyük

- `hiddenimports`'tan kullanılmayan modülleri kaldırın
- `excludedimports` listeyi artırın
- `upx=True` kullanın (sıkıştırma için)

## İleri Ayarlar

### Spec Dosyasını Özelleştirme

`homeflix.spec` dosyasını düzenleyerek:

- **Console window**: `console=False` → `console=True`
- **İcon**: `icon='static/icon.ico'` yolunu değiştirin
- **Gizli imports**: `hiddenimports` listesine ekleyin
- **Dışlanan modüller**: `excludedimports` listesini değiştirin

### Imzalama (Code Signing)

Windows Defender uyarılarını azaltmak için:

```bash
# Spec dosyasında güncelleyin:
codesign_identity='Your Certificate Name'
```

## Kaynaklar

- [PyInstaller Dokümantasyonu](https://pyinstaller.org/)
- [NSIS Dokümantasyonu](https://nsis.sourceforge.io/)
- [Electron alternatifi düşünüyor musunuz?](https://www.electronjs.org/)
