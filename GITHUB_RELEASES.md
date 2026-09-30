# GitHub Releases ile Dağıtım

## Nasıl Çalışır?

Bu proje, GitHub Actions kullanarak otomatik olarak Windows executable'ını derleyip GitHub Releases'e yükler. Böylece kullanıcılar:

✅ **Python yüklemeye gerek YOK**
✅ **Başka hiçbir şey indirmeye gerek YOK**  
✅ **Sadece `.exe` dosyasını indir ve çalıştır**

## Kurulum

### 1. GitHub'a Push Edin

Projeyi ilk kez GitHub'a göndermeniz gerekir:

```bash
cd /home/oguz/Antigravity_Projects/Homeflix_v2

# Git konfigürasyonu (ilk seferse)
git config user.email "kaptanoguz@gmail.com"
git config user.name "Oguz Kaptan"

# Tüm dosyaları ekleyin
git add .

# Commit yapın
git commit -m "Initial commit: Homeflix v2 Windows executable build setup"

# GitHub'a bağlayın (kendi repo URL'inizi kullanın)
git remote add origin https://github.com/YOUR_USERNAME/Homeflix_v2.git
git branch -M main
git push -u origin main
```

### 2. Release Oluşturun (Uygulamayı Yayınlarken)

Yeni bir sürüm yayınlamak istediğinizde, bir tag oluşturun:

```bash
# Tag oluşturun
git tag -a v2.0.0 -m "Release version 2.0.0"

# GitHub'a push edin
git push origin v2.0.0
```

**Tag formatı:** `v` ile başlamalı (örn: `v1.0.0`, `v2.1.5`)

### 3. Otomatik Build Olur 🤖

Tag'ı push ettikten sonra:

1. ✅ GitHub Actions otomatik olarak başlar
2. ✅ Windows'ta build yapılır
3. ✅ `Homeflix.exe` derlenir
4. ✅ GitHub Releases'e yüklenir
5. ✅ Kullanıcılar indirebilir

## Kullanıcılar İçin

Projeniz GitHub'da yayında olduğunda, kullanıcılar:

1. Releases sayfasına gidecek
2. `.exe` dosyasını indirecek
3. Çalıştıracak - HEPSİ!

**Hiç Python yüklemeye gerek yok!**

## Release Oluşturma Takvimi

Yeni sürüm yayınlamak istediğinizde:

```bash
# Kod değişikliklerini yapın
# ...

# Staging area'ya ekleyin
git add .

# Commit yapın
git commit -m "Your changes here"

# Main branch'e push edin
git push origin main

# Version bump yapın (SemVer: major.minor.patch)
git tag -a v2.1.0 -m "Release version 2.1.0"
git push origin v2.1.0
```

## Troubleshooting

### Build başarısız mı?

GitHub'da Actions sekmesini kontrol edin:
- Workflow logs'unda hatayı görebilirsiniz
- Genellikle eksik dependencies'dir

### Build başarılı ama executable çalışmıyor?

1. `build_windows.py` dosyasında `hiddenimports` kontrol edin
2. Yeni bir Python package eklediyseniz, orada listeyin:

```python
hiddenimports=[
    'flask',
    'waitress',
    'pywebview',
    'requests',
    'pillow',
    # Yeni package'ınız buraya
]
```

### Release dosyaları yok?

Workflow logs'u kontrol edin:
- Tag formatı doğru mu? (`v*` olmalı)
- Requirements.txt eksik mi?
- build_windows.py hata verdi mi?

## İleri Bilgiler

### Workflow Nedir?

`.github/workflows/build-windows.yml` dosyası:
- Tag push'u dinler
- Windows machine'de Python'u yükler
- PyInstaller ile build yapılır
- Release oluşturulur
- Executable'ı yükler

### Nasıl Çalışır?

```
You git tag -a v1.0 
    ↓
GitHub Actions tetiklenir
    ↓
Windows Runner başlar
    ↓
Python yüklenir + dependencies
    ↓
build_windows.py çalışır
    ↓
Homeflix.exe oluşur
    ↓
GitHub Release'e yüklenir
    ↓
Kullanıcılar indirebilir ✅
```

## Checklist: First Time Setup

- [ ] Projeyi GitHub'a push ettiniz
- [ ] `.github/workflows/build-windows.yml` mevcut
- [ ] Tag oluşturdunuz (`git tag -a v1.0.0 ...`)
- [ ] Tag'ı push ettiniz (`git push origin v1.0.0`)
- [ ] GitHub Actions çalışıyor (Actions sekmesi)
- [ ] Release sayfasında dosyalar görülüyor

Hepsi tamam! 🎉 Kullanıcılar artık .exe'yi direkt indirebilir!
