# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the release packages: Windows (single .exe), macOS (Homeflix.app) and Linux (folder).
# Build from the repository root after `python packaging/make_icon.py`:
#   pyinstaller --noconfirm packaging/homeflix-desktop.spec
# The personal data/ folder is not bundled: packaged builds keep their library in the user's data folder.
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
ICONS = os.path.join(ROOT, 'build', 'icons')
VERSION = os.environ.get('HOMEFLIX_VERSION', '2.0.0').lstrip('v')

a = Analysis(
    [os.path.join(ROOT, 'app.py')],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, 'templates'), 'templates'), (os.path.join(ROOT, 'static'), 'static')],
    hiddenimports=['waitress', 'webview'],
    excludes=['matplotlib', 'numpy', 'pandas', 'tkinter'],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == 'win32':
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='Homeflix', console=True, upx=False,
              icon=os.path.join(ICONS, 'homeflix.ico'))
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Homeflix', console=sys.platform != 'darwin',
              upx=False, icon=os.path.join(ICONS, 'homeflix.png'))
    coll = COLLECT(exe, a.binaries, a.datas, upx=False, name='Homeflix')
    if sys.platform == 'darwin':
        app = BUNDLE(
            coll,
            name='Homeflix.app',
            icon=os.path.join(ICONS, 'homeflix.png'),
            bundle_identifier='com.kaptanoguz.homeflix',
            version=VERSION,
            info_plist={
                'CFBundleDisplayName': 'Homeflix',
                'CFBundleShortVersionString': VERSION,
                'NSHighResolutionCapable': True,
                'LSApplicationCategoryType': 'public.app-category.entertainment',
                # The player loads posters and video over the home network (plain http).
                'NSAppTransportSecurity': {'NSAllowsArbitraryLoads': True},
                'NSLocalNetworkUsageDescription': 'Homeflix ev ağındaki cihazlara film ve dizi sunar.',
            },
        )
