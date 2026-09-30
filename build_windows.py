#!/usr/bin/env python3
"""
Windows build script for Homeflix
Generates standalone executable and optional installer
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def run_command(cmd, description=""):
    """Run a shell command and handle errors"""
    if description:
        print(f"▶ {description}")
    print(f"  {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Hata: {description or cmd[0]} başarısız oldu (kod: {e.returncode})")
        return False
    except FileNotFoundError:
        print(f"\n❌ Hata: {cmd[0]} bulunamadı. Lütfen yükleyin.")
        return False


def convert_svg_to_ico():
    """Convert SVG icon to ICO format"""
    print_header("İcon Dönüştürme")

    svg_path = Path("static/icon.svg")
    ico_path = Path("static/icon.ico")

    if not svg_path.exists():
        print(f"⚠️  Icon.svg bulunamadı: {svg_path}")
        print("   Varsayılan Windows ikonunu kullanacağım...")
        return False

    try:
        from PIL import Image
        import io

        # SVG'yi PNG'ye çevirmek için cairosvg kullanmalısınız
        # Alternatif: PIL ile doğrudan işleyemez, bu yüzden adım atlanacak
        print("📌 SVG → ICO dönüştürmesi için cairosvg gerekli")
        print("   Komut: pip install cairosvg")
        print("   Ya da: Çevrimiçi bir SVG to ICO dönüştürücü kullanın")
        return False
    except ImportError:
        print("⚠️  PIL (Pillow) yüklü değil, ICO dosyası oluşturulamıyor")
        return False


def install_build_dependencies():
    """Install PyInstaller and other build tools"""
    print_header("Derleme Bağımlılıkları Yükleniyor")

    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "-r", "requirements-build.txt"]
    return run_command(cmd, "Build tools yükleniyor...")


def build_executable():
    """Build the Windows executable using PyInstaller"""
    print_header("Homeflix Executable Derleniyor")

    if not Path("homeflix.spec").exists():
        print("❌ homeflix.spec bulunamadı!")
        return False

    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "homeflix.spec"]
    success = run_command(cmd, "PyInstaller çalıştırılıyor...")

    if success:
        print("\n✅ Executable başarıyla oluşturuldu!")
        print(f"   📁 Konum: ./dist/Homeflix/")
        print(f"   🎯 Executable: ./dist/Homeflix/Homeflix.exe")

    return success


def create_installer():
    """Create NSIS installer"""
    print_header("Windows Kurulum Paketi Oluşturuluyor")

    nsi_file = Path("windows_installer.nsi")
    if not nsi_file.exists():
        print("⚠️  windows_installer.nsi bulunamadı")
        return False

    # Check if NSIS is installed
    try:
        cmd = ["makensis", str(nsi_file)]
        success = run_command(cmd, "NSIS installer oluşturuluyor...")

        if success:
            print("\n✅ Windows installer başarıyla oluşturuldu!")
            print(f"   📁 Konum: ./dist/HomeflixInstaller.exe")

        return success
    except FileNotFoundError:
        print("⚠️  NSIS bulunamadı. Sadece executable oluşturuldu.")
        print("   Installer için: https://nsis.sourceforge.io/Main_Page adresinden yükleyin")
        return False


def cleanup_build_artifacts():
    """Remove build artifacts"""
    print_header("Geçici Dosyalar Temizleniyor")

    paths_to_remove = [
        Path("build"),
    ]

    for path in paths_to_remove:
        if path.exists():
            print(f"🗑️  Siliniyor: {path}")
            shutil.rmtree(path, ignore_errors=True)

    print("✅ Temizlik tamamlandı")


def create_readme():
    """Create build instructions file"""
    print_header("BUILD_WINDOWS.md Oluşturuluyor")

    readme_content = """# Windows Executable Derleme Kılavuzu

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
"""

    Path("BUILD_WINDOWS.md").write_text(readme_content, encoding='utf-8')
    print("✅ BUILD_WINDOWS.md oluşturuldu")


def main():
    """Main build process"""
    print_header("🍿 Homeflix Windows Derleme Başlangıç")

    # Check if we're in the right directory
    if not Path("app.py").exists():
        print("❌ app.py bulunamadı!")
        print("   Lütfen Homeflix proje dizininde olduğunuzdan emin olun")
        sys.exit(1)

    print("✅ Proje dizini doğrulandı\n")

    # Step 1: Create documentation
    create_readme()

    # Step 2: Install dependencies
    if not install_build_dependencies():
        print("\n⚠️  Bağımlılık kurulumu başarısız, devam etmeyi deniyor...")

    # Step 3: Convert icon (optional)
    convert_svg_to_ico()

    # Step 4: Build executable
    if not build_executable():
        print("\n❌ Derleme başarısız oldu!")
        sys.exit(1)

    # Step 5: Create installer (optional)
    create_installer()

    # Step 6: Cleanup
    cleanup_build_artifacts()

    # Final summary
    print_header("🎉 Derleme Tamamlandı!")
    print("""
✅ Homeflix Windows executable'ı başarıyla oluşturuldu!

📦 Dağıtım seçenekleri:
  1. Portable sürüm: dist/Homeflix/ klasörünü zip'leyin
  2. Installer: dist/HomeflixInstaller.exe (NSIS kuruluysa)

🚀 Çalıştırmak için:
  - dist/Homeflix/Homeflix.exe 'yi açın

📖 Detaylı bilgi için BUILD_WINDOWS.md okuyun
""")


if __name__ == "__main__":
    main()
