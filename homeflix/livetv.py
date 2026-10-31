"""Live TV tab: free channels that broadcasters stream on their own sites, played by each device directly.

Only streams served from the broadcaster's own servers (or the CDN its own website uses) are listed; restreams of
paid channels are left out on purpose. The server never carries video. It keeps the channel logos (so the list looks
right without internet), and every few hours it downloads each channel's small playlist file to see whether the
channel is on air, so dead channels drop out of the list by themselves."""
import os
import re
import threading
import time

import requests

from .config import IMAGES_DIR, USER_AGENT

# Category ids and the names shown on the chips, in chip order.
CATEGORIES = [('ulusal', 'Ulusal'), ('haber', 'Haber'), ('spor', 'Spor'), ('belgesel', 'Belgesel'),
              ('cocuk', 'Çocuk'), ('muzik', 'Müzik'), ('dunya', 'Dünya')]

# id (iptv-org channel id, used for the logo), name, category, quality label, stream URLs (first that works wins),
# extra flags. 'tr' marks channels that only open from inside Turkey. 'yt' streams are YouTube channel ids played
# in YouTube's own embed (the channel's official 24/7 live stream).
CHANNELS = [
    ('TRT1.tr', 'TRT 1', 'ulusal', '1440p', ['https://tv-trt1.medya.trt.com.tr/master.m3u8']),
    ('KanalD.tr', 'Kanal D', 'ulusal', '1080p', ['https://demiroren.daioncdn.net/kanald/kanald.m3u8?app=kanald_web&ce=3']),
    ('ATV.tr', 'ATV', 'ulusal', '1080p', ['https://rnttwmjcin.turknet.ercdn.net/lcpmvefbyo/atv/atv_1080p.m3u8']),
    ('StarTV.tr', 'Star TV', 'ulusal', '720p', ['https://dogus.daioncdn.net/startv/startv_720p.m3u8?app=a20ac41e-bdc3-4aa1-934d-26b484480ac9&ce=3']),
    ('TV8.tr', 'TV8', 'ulusal', '1080p', ['https://tv8.daioncdn.net/tv8/tv8.m3u8?app=7ddc255a-ef47-4e81-ab14-c0e5f2949788&ce=3',
                                         'https://tv8-live.daioncdn.net/tv8/tv8.m3u8']),
    ('NOWTV.tr', 'NOW', 'ulusal', '720p', ['https://uycyyuuzyh.turknet.ercdn.net/nphindgytw/nowtv/nowtv.m3u8']),
    ('Kanal7.tr', 'Kanal 7', 'ulusal', '1080p', ['https://kanal7-live.daioncdn.net/kanal7/kanal7.m3u8']),
    ('A2TV.tr', 'a2', 'ulusal', '1080p', ['https://rnttwmjcin.turknet.ercdn.net/lcpmvefbyo/a2tv/a2tv.m3u8']),
    ('TRTTurk.tr', 'TRT Türk', 'ulusal', '720p', ['https://tv-trtturk.medya.trt.com.tr/master.m3u8']),
    ('TRT2.tr', 'TRT 2', 'ulusal', '1440p', ['https://tv-trt2.medya.trt.com.tr/master.m3u8'], 'tr'),

    ('TRTHaber.tr', 'TRT Haber', 'haber', '720p', ['https://tv-trthaber.medya.trt.com.tr/master.m3u8']),
    ('NTV.tr', 'NTV', 'haber', 'HD', ['https://dogus.daioncdn.net/ntv/ntv.m3u8?app=ntv_web']),
    ('AHaber.tr', 'A Haber', 'haber', '1080p', ['https://rnttwmjcin.turknet.ercdn.net/lcpmvefbyo/ahaber/ahaber.m3u8']),
    ('HalkTV.tr', 'Halk TV', 'haber', '1080p', ['https://halktv-live.daioncdn.net/halktv/halktv.m3u8']),
    ('Tele1.tr', 'Tele 1', 'haber', '1080p', ['https://tele1-live.ercdn.net/tele1/tele1.m3u8']),
    ('TVNET.tr', 'TVNET', 'haber', '1080p', ['https://tvnet-live.lg.mncdn.com/tvnet/tvnet/playlist.m3u8']),
    ('BloombergHT.tr', 'Bloomberg HT', 'haber', '720p', ['https://ciner-live.daioncdn.net/bloomberght/bloomberght.m3u8']),
    ('CNBCe.tr', 'CNBC-e', 'haber', 'HD', ['https://hnpsechtsc.turknet.ercdn.net/xpnvudnlsv/cnbc-e/cnbc-e.m3u8']),
    ('TBMMTV.tr', 'TBMM TV', 'haber', '720p', ['https://meclistv-live.ercdn.net/meclistv/meclistv.m3u8']),

    ('TRTSporYildiz.tr', 'TRT Spor Yıldız', 'spor', '1440p', ['https://trt.daioncdn.net/trtspor-yildiz/master.m3u8?app=web&platform=trtspor'], 'tr'),
    ('ASpor.tr', 'A Spor', 'spor', '1080p', ['https://rnttwmjcin.turknet.ercdn.net/lcpmvefbyo/aspor/aspor.m3u8']),
    ('HTSporTV.tr', 'HT Spor', 'spor', '1080p', ['https://ciner.daioncdn.net/ht-spor/ht-spor.m3u8?app=web']),

    ('TRTBelgesel.tr', 'TRT Belgesel', 'belgesel', '720p', ['https://tv-trtbelgesel.medya.trt.com.tr/master.m3u8']),
    ('NHKWorldJapan.jp', 'NHK World', 'belgesel', '1080p', ['https://masterpl.hls.nhkworld.jp/hls/w/live/smarttv.m3u8',
                                                             'https://media-tyo.hls.nhkworld.jp/hls/w/live/master.m3u8']),

    ('TRTCocuk.tr', 'TRT Çocuk', 'cocuk', '1440p', ['https://tv-trtcocuk.medya.trt.com.tr/master.m3u8']),
    ('MinikaCocuk.tr', 'Minika Çocuk', 'cocuk', '720p', ['https://rnttwmjcin.turknet.ercdn.net/lcpmvefbyo/minikago_cocuk/minikago_cocuk.m3u8']),
    ('MinikaGo.tr', 'Minika Go', 'cocuk', '720p', ['https://rnttwmjcin.turknet.ercdn.net/lcpmvefbyo/minikago/minikago.m3u8']),

    ('TRTMuzik.tr', 'TRT Müzik', 'muzik', '720p', ['https://tv-trtmuzik.medya.trt.com.tr/master.m3u8']),
    ('KralPopTV.tr', 'Kral Pop', 'muzik', '720p', ['https://dogus-live.daioncdn.net/kralpoptv/playlist.m3u8']),
    ('PowerTurkTV.tr', 'Power Türk', 'muzik', '1080p', ['https://livetv.powerapp.com.tr/powerturkTV/powerturkhd.smil/playlist.m3u8']),
    ('DreamTurk.tr', 'Dream Türk', 'muzik', '720p', ['https://live.duhnet.tv/S2/HLS_LIVE/dreamturknp/playlist.m3u8']),

    ('SkyNews.uk', 'Sky News', 'dunya', 'HD', ['yt:UCoMdktPbSTixAyNGwb-UYkQ']),
    ('TRTWorld.tr', 'TRT World', 'dunya', '1080p', ['https://tv-trtworld.medya.trt.com.tr/master.m3u8']),
    ('DW.de', 'DW English', 'dunya', '1080p', ['https://dwamdstream102.akamaized.net/hls/live/2015525/dwstream102/master.m3u8']),
    ('France24.fr', 'France 24', 'dunya', '1080p', ['https://live.france24.com/hls/live/2037218-b/F24_EN_HI_HLS/master_5000.m3u8',
                                                    'https://live.france24.com/hls/live/2037218/F24_EN_HI_HLS/master_5000.m3u8']),
    ('AlJazeera.qa', 'Al Jazeera English', 'dunya', '1080p', ['https://live-hls-apps-aje-fa.getaj.net/AJE/index.m3u8']),
    ('EuronewsEnglish.fr', 'Euronews', 'dunya', '720p', ['https://cdn-euronews.akamaized.net/live/eds/euronews-en/25002/index.m3u8']),
    ('BloombergTV.us', 'Bloomberg', 'dunya', '720p', ['https://bloomberg.com/media-manifest/streams/eu.m3u8']),
    ('DasErste.de', 'Das Erste', 'dunya', '1080p', ['https://daserste-live.ard-mcdn.de/daserste/live/hls/int/master.m3u8']),
]

CHECK_EVERY = 6 * 3600
CHECK_TIMEOUT = 12
# A channel is hidden only after this many failed checks in a row, so one hiccup doesn't make it disappear.
DEAD_AFTER = 2
LOGO_LIST = 'https://iptv-org.github.io/api/logos.json'
LOGO_DIR = os.path.join(IMAGES_DIR, 'live')
LOGO_MAX_AGE = 7 * 86400
LOGO_EXT = ('png', 'svg', 'jpg', 'webp')
os.makedirs(LOGO_DIR, exist_ok=True)

_http = requests.Session()
_http.headers['User-Agent'] = USER_AGENT
_lock = threading.Lock()
# id -> {'ok': True/False/None, 'fails': n, 'url': working URL, 'cors': True/False/None, 'at': time}
_status = {}


def _channel(row):
    cid, name, cat, quality, urls = row[:5]
    flags = row[5] if len(row) > 5 else ''
    return {'id': cid, 'name': name, 'cat': cat, 'q': quality, 'urls': urls, 'tr': 'tr' in flags}


def channels():
    """The channel list for the web app, dead channels left out. A channel not checked yet is listed."""
    out = []
    with _lock:
        status = dict(_status)
    for i, row in enumerate(CHANNELS):
        ch = _channel(row)
        st = status.get(ch['id'], {})
        if st.get('ok') is False and st.get('fails', 0) >= DEAD_AFTER:
            continue
        url = st.get('url') or ch['urls'][0]
        item = {'id': ch['id'], 'n': ch['name'], 'cat': ch['cat'], 'q': ch['q'], 'no': i + 1,
                'logo': f"/img/live/{ch['id']}" if logo_file(ch['id']) else '', 'ok': st.get('ok')}
        if url.startswith('yt:'):
            item['yt'] = url[3:]
        else:
            item['url'] = url
            item['alt'] = [u for u in ch['urls'] if u != url and not u.startswith('yt:')]
            # False: the broadcaster doesn't let other sites read the stream, so the browser plays it natively.
            item['cors'] = st.get('cors')
        if ch['tr']:
            item['tr'] = 1
        out.append(item)
    return {'channels': out, 'cats': [{'id': k, 'n': n} for k, n in CATEGORIES]}


def find(cid):
    return next((_channel(r) for r in CHANNELS if r[0] == cid), None)


# ---------------------------------------------------------------- on-air check

def _check_url(url):
    """(on air, CORS allowed) for one stream. Downloads only the playlist text (a few KB), never video."""
    if url.startswith('yt:'):
        return True, None
    try:
        r = _http.get(url, timeout=CHECK_TIMEOUT, headers={'Origin': 'http://homeflix.local'}, stream=True)
        try:
            body = r.raw.read(65536, decode_content=True).decode('utf-8', 'replace')
        finally:
            r.close()
    except (requests.RequestException, OSError):
        return False, None
    ok = r.status_code == 200 and '#EXTM3U' in body[:1024]
    cors = r.headers.get('Access-Control-Allow-Origin') in ('*', 'http://homeflix.local')
    return ok, cors


def check_channel(cid):
    ch = find(cid)
    if not ch:
        return None
    result = {'ok': False, 'url': None, 'cors': None}
    for url in ch['urls']:
        ok, cors = _check_url(url)
        if ok:
            result = {'ok': True, 'url': url, 'cors': cors}
            break
    with _lock:
        prev = _status.get(cid, {})
        fails = 0 if result['ok'] else prev.get('fails', 0) + 1
        _status[cid] = {**result, 'fails': fails, 'at': time.time()}
    return _status[cid]


def check_all():
    alive = 0
    for row in CHANNELS:
        st = check_channel(row[0])
        alive += bool(st and st['ok'])
        time.sleep(0.3)
    dead = [r[1] for r in CHANNELS if not _status.get(r[0], {}).get('ok')]
    print(f"Canlı TV: {alive}/{len(CHANNELS)} kanal yayında" + (f" (açılmayan: {', '.join(dead)})" if dead else ''))
    return alive


def report_failure(cid, code, agent):
    """A device couldn't play a channel: logged, and the channel is checked again right away."""
    ch = find(cid)
    if not ch:
        return
    print(f"Canlı TV: {ch['name']} cihazda açılmadı ({code}) · {agent[:80]}")
    threading.Thread(target=check_channel, args=(cid,), daemon=True).start()


# ---------------------------------------------------------------- logos

def logo_file(cid):
    for ext in LOGO_EXT:
        p = os.path.join(LOGO_DIR, f'{cid}.{ext}')
        if os.path.exists(p):
            return p
    return None


def _pick_logo(entries):
    """The best logo for one channel from iptv-org's list: the main feed's, wide and large."""
    def score(e):
        tags = e.get('tags') or []
        return (e.get('feed') is None, 'horizontal' in tags or (e.get('width') or 0) >= (e.get('height') or 0),
                e.get('format') in ('PNG', 'SVG'), (e.get('width') or 0))
    return max(entries, key=score) if entries else None


def fetch_logos(force=False):
    """Saves every channel's logo on the server (once; refreshed weekly) so devices without internet see them."""
    missing = [r[0] for r in CHANNELS if force or not logo_file(r[0]) or
               time.time() - os.path.getmtime(logo_file(r[0])) > LOGO_MAX_AGE]
    if not missing:
        return 0
    try:
        listing = _http.get(LOGO_LIST, timeout=60).json()
    except (requests.RequestException, ValueError):
        return 0
    by_channel = {}
    for e in listing:
        if e.get('channel') in missing:
            by_channel.setdefault(e['channel'], []).append(e)
    saved = 0
    for cid in missing:
        best = _pick_logo(by_channel.get(cid, []))
        if not best or not best.get('url'):
            continue
        ext = (best.get('format') or '').lower()
        if ext not in LOGO_EXT:
            m = re.search(r'\.(png|svg|jpg|webp)(\?|$)', best['url'], re.I)
            ext = m.group(1).lower() if m else 'png'
        try:
            r = _http.get(best['url'], timeout=20)
            if r.status_code != 200 or len(r.content) < 100:
                continue
        except requests.RequestException:
            continue
        old = logo_file(cid)
        if old:
            os.remove(old)
        with open(os.path.join(LOGO_DIR, f'{cid}.{ext}'), 'wb') as f:
            f.write(r.content)
        saved += 1
        time.sleep(0.5)
    return saved


def warm_loop():
    """Logos once, then an on-air check of every channel every CHECK_EVERY (a few KB per channel)."""
    time.sleep(40)
    while True:
        try:
            n = fetch_logos()
            if n:
                print(f"Canlı TV: {n} kanal logosu indirildi")
            check_all()
        except Exception as e:
            print(f"Canlı TV kontrol hatası: {e}")
        time.sleep(CHECK_EVERY)


def status_report():
    with _lock:
        status = dict(_status)
    return [{'id': r[0], 'n': r[1], **{k: status.get(r[0], {}).get(k) for k in ('ok', 'cors', 'url', 'fails', 'at')}}
            for r in CHANNELS]


if __name__ == '__main__':
    # python -m homeflix.livetv : checks every channel from this computer and prints the result.
    fetch_logos()
    check_all()
    for s in status_report():
        print(f"{'OK ' if s['ok'] else 'YOK'} cors={s['cors']!s:5} {s['n']}")
