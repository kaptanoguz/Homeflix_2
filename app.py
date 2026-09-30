import os
import sys
import threading
import webbrowser

from homeflix.db import init_db

init_db()

from homeflix import library, metadata, state  # noqa: E402
from homeflix.api import app, lan_ips, settings  # noqa: E402
from homeflix.config import PORT  # noqa: E402


def startup_jobs():
    try:
        library.fill_file_info()
        library.cleanup_titles()
        library.sync_emby(settings)
    except Exception as e:
        print(f"Başlangıç işi hatası: {e}")
    state.bump()
    state.wake_enricher()


def serve():
    from waitress import serve as waitress_serve
    print("\n=======================================================")
    print("🍿 Homeflix 2 başlatıldı")
    print(f"📌 Bu bilgisayardan: http://127.0.0.1:{PORT}")
    for ip in lan_ips():
        print(f"🌐 Ev ağından:      http://{ip}:{PORT}")
    print("=======================================================\n")
    waitress_serve(app, host='0.0.0.0', port=PORT, threads=16, connection_limit=100, channel_timeout=60, backlog=256)


class WindowApi:
    def __init__(self):
        self.window = None

    def toggle_fullscreen(self):
        if self.window:
            self.window.toggle_fullscreen()


def server_running():
    import socket
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(('127.0.0.1', PORT)) == 0


def open_window(url):
    try:
        import webview
        api = WindowApi()
        api.window = webview.create_window('Homeflix', url, width=1440, height=900, min_size=(960, 600),
                                           background_color='#0b0b0f', js_api=api)
        webview.start()
        return True
    except Exception as e:
        print(f"Uygulama penceresi açılamadı ({e}), tarayıcıda açılıyor.")
        return False


def main():
    headless = '--headless' in sys.argv or not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
    url = f'http://127.0.0.1:{PORT}'
    if not headless and server_running():
        # The background service already serves the library: only open the window.
        if '--browser' in sys.argv or not open_window(url):
            webbrowser.open(url)
        return
    metadata.start()
    threading.Thread(target=startup_jobs, daemon=True).start()
    if headless:
        serve()
        return
    threading.Thread(target=serve, daemon=True).start()
    if '--browser' in sys.argv or not open_window(url):
        webbrowser.open(url)
        threading.Event().wait()


if __name__ == '__main__':
    main()
