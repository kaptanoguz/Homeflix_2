#!/bin/sh
# Homeflix'i uygulama menüsüne ekler. Arşivi açtığınız klasörde çalıştırın: ./install.sh
# Kaldırmak için: ./install.sh --uninstall
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"

if [ "$1" = "--uninstall" ]; then
    rm -f "$APPS/homeflix.desktop" "$ICONS/homeflix.png"
    echo "Homeflix menüden kaldırıldı. Kütüphane verisi: ${XDG_DATA_HOME:-$HOME/.local/share}/homeflix"
    exit 0
fi

mkdir -p "$APPS" "$ICONS"
cp "$HERE/homeflix.png" "$ICONS/homeflix.png"
cat > "$APPS/homeflix.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Homeflix
Comment=Ev sineması
Exec="$HERE/Homeflix/Homeflix" --browser
Icon=homeflix
Terminal=false
Categories=AudioVideo;Video;Player;
DESKTOP
chmod +x "$APPS/homeflix.desktop"
echo "Homeflix uygulama menüsüne eklendi."
