@echo off
REM Homeflix Windows Build Script
REM Bu script Homeflix'i Windows executable'ına derler

echo.
echo ======================================================
echo  Homeflix Windows Derleme Aracı
echo ======================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python bulunamadi!
    echo Lutfen Python'u https://www.python.org adresinden yukleyin
    echo ve PATH'e ekleyin.
    pause
    exit /b 1
)

echo [OK] Python bulundu
echo.

REM Check if we're in the right directory
if not exist "app.py" (
    echo [HATA] app.py bulunamadi!
    echo Lutfen Homeflix proje dizininde olmaktan emin olun.
    pause
    exit /b 1
)

echo [OK] Proje dizini dogrulandi
echo.

REM Run the build script
echo Homeflix derleme baslatiliyor...
echo.
python build_windows.py

if errorlevel 1 (
    echo.
    echo [HATA] Derleme basarisiz oldu!
    pause
    exit /b 1
)

echo.
echo ======================================================
echo  Derleme Basarili!
echo ======================================================
echo.
echo Executable buradadir: dist\Homeflix\Homeflix.exe
echo.
pause
