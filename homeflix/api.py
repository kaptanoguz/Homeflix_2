import gzip
import os
import subprocess
import threading
import time
from collections import defaultdict

from flask import Flask, abort, jsonify, render_template, request, send_file

from . import library, media, metadata, state, subtitles
from .config import BASE_DIR, POSTERS_DIR
from .db import load_settings, save_settings, session
from .names import fold, sequel_key

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
settings = load_settings()
library.settings_ref = settings


@app.after_request
def finish(response):
    p = request.path
    if p == '/' or p.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    elif p.startswith('/img/') and response.status_code == 200:
        response.headers['Cache-Control'] = 'public, max-age=86400'
    elif p.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-cache'
    if (response.mimetype in ('application/json', 'text/vtt', 'text/html', 'text/css', 'application/javascript',
                              'text/javascript')
            and not response.direct_passthrough and 'gzip' in request.headers.get('Accept-Encoding', '')
            and response.status_code == 200 and 'Content-Encoding' not in response.headers):
        data = response.get_data()
        if len(data) > 1400:
            response.set_data(gzip.compress(data, 5))
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Vary'] = 'Accept-Encoding'
    return response


def _pv(poster):
    p = library.poster_file(poster)
    return int(os.path.getmtime(p)) if p else 0


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------- library

KIDS_GENRES = ('Animasyon', 'Aile', 'Çocuk')
NOT_KIDS_GENRES = ('Korku', 'Suç', 'Savaş', 'Gerilim')
KIDS_RATINGS = {'US': {'G', 'PG', 'TV-Y', 'TV-Y7', 'TV-G', 'TV-PG'},
                'TR': {'G', '0+', '6+', '7+', '6A', '7A'}}


def is_kids(genre, cert):
    """Kids Zone: animation/family titles with a G/PG-level age rating (or, without a rating, tagged Family)."""
    genre = genre or ''
    if not any(g in genre for g in KIDS_GENRES) or any(g in genre for g in NOT_KIDS_GENRES):
        return False
    if cert:
        country, _, rating = cert.partition(':')
        return rating in KIDS_RATINGS.get(country, ()) or (country == 'TR' and rating.lower().startswith('genel'))
    return 'Aile' in genre


def build_library():
    with session() as c:
        movies = c.execute("SELECT id, title, original_title, year, rating, genre, plot, runtime, added_at, size, "
                           "tmdb_id, collection_id, poster, backdrop, cert FROM movies").fetchall()
        shows = c.execute("SELECT s.*, COUNT(e.id) AS eps FROM series s LEFT JOIN episodes e ON e.series_id = s.id "
                          "GROUP BY s.id").fetchall()
        ep_keys = defaultdict(set)
        for e in c.execute("SELECT series_id, season, episode FROM episodes"):
            ep_keys[e['series_id']].add((e['season'], e['episode']))
        cols = {r['id']: r for r in c.execute("SELECT * FROM collections")}

    out_movies = []
    by_col = defaultdict(list)
    loose = []
    for m in movies:
        item = {'id': m['id'], 't': m['title'], 'ot': m['original_title'] or '', 'y': m['year'] or '',
                'r': m['rating'] if m['rating'] not in (None, '', 'N/A') else '', 'g': m['genre'] or '',
                'p': m['plot'] or '', 'rt': m['runtime'] or 0, 'add': m['added_at'] or 0, 'sz': m['size'] or 0,
                'tm': m['tmdb_id'] or 0, 'ph': _pv(m['poster']), 'bd': bool(m['backdrop']), 'c': None,
                'k': is_kids(m['genre'], m['cert'])}
        out_movies.append(item)
        if m['collection_id'] and m['collection_id'] in cols:
            by_col[m['collection_id']].append(item)
        else:
            loose.append(item)

    collections = []

    def add_collection(cid, name, items, overview='', parts=0, poster=False, backdrop=False):
        distinct = {i['tm'] or f"id{i['id']}" for i in items}
        if len(distinct) < 2:
            return
        items.sort(key=lambda i: (i['y'] or '9999', i['t']))
        for i in items:
            i['c'] = cid
        collections.append({'id': cid, 'name': name, 'ov': overview, 'parts': parts, 'poster': poster,
                            'backdrop': backdrop, 'items': [i['id'] for i in items], 'owned': len(distinct)})

    for cid, items in by_col.items():
        col = cols[cid]
        add_collection(cid, col['name'] or items[0]['t'], items, col['overview'] or '', col['parts'] or 0,
                       bool(col['poster']), bool(col['backdrop']))

    groups = defaultdict(list)
    exact = {}
    for i in loose:
        key = sequel_key(i['t'])
        if key:
            groups[key[0]].append(i)
        exact.setdefault(fold(i['t']).strip(), []).append(i)
    for base, items in groups.items():
        items = items + [i for i in exact.get(base, []) if i not in items]
        if len({fold(i['t']) for i in items}) < 2:
            continue
        first = min(items, key=lambda i: (i['y'] or '9999'))
        name = next((i['t'] for i in items if fold(i['t']).strip() == base), None) or \
            ' '.join(first['t'].split()[:len(base.split())])
        add_collection(f"h-{base.replace(' ', '-')}", name, items)
    collections.sort(key=lambda c: fold(c['name']))

    show_groups = defaultdict(list)
    for s in shows:
        show_groups[f"t{s['tmdb_id']}" if s['tmdb_id'] else f"i{s['id']}"].append(s)
    out_series = []
    for group in show_groups.values():
        group.sort(key=lambda s: -s['eps'])
        s = group[0]
        keys = set().union(*(ep_keys[g['id']] for g in group))
        out_series.append({
            'id': s['id'], 'ids': [g['id'] for g in group], 't': s['display_title'] or s['title'],
            'ot': s['original_title'] or '', 'y': s['year'] or '',
            'r': s['rating'] if s['rating'] not in (None, '', 'N/A') else '', 'g': s['genre'] or '', 'p': s['plot'] or '',
            'add': max(g['added_at'] or 0 for g in group), 'tm': s['tmdb_id'] or 0,
            'ph': _pv(s['poster']), 'bd': bool(s['backdrop']),
            'eps': len(keys), 'seasons': len({k[0] for k in keys}), 'k': is_kids(s['genre'], s['cert'])})
    return {'movies': out_movies, 'series': out_series, 'collections': collections,
            'version': state.snapshot()['version']}


@app.route('/')
def index():
    return render_template('index.html', v=int(os.path.getmtime(os.path.join(BASE_DIR, 'static', 'app.js'))))


@app.route('/api/library')
def api_library():
    return jsonify(build_library())


@app.route('/api/status')
def api_status():
    return jsonify(state.snapshot())


@app.route('/api/series/<int:sid>')
def api_series(sid):
    with session() as c:
        s = c.execute("SELECT * FROM series WHERE id = ?", (sid,)).fetchone()
        if not s:
            abort(404)
        ids = [sid]
        if s['tmdb_id']:
            ids += [r['id'] for r in c.execute("SELECT id FROM series WHERE tmdb_id = ? AND id != ?", (s['tmdb_id'], sid))]
        order = {v: i for i, v in enumerate(ids)}
        rows = c.execute(f"SELECT id, series_id, season, episode, filename, ep_name, ep_overview, still, runtime FROM episodes "
                         f"WHERE series_id IN ({','.join('?' * len(ids))})", ids).fetchall()
        rows = sorted(rows, key=lambda e: (e['season'], e['episode'], order[e['series_id']], e['filename']))
        seen, eps = set(), []
        for e in rows:
            if (e['season'], e['episode'], e['filename']) in seen:
                continue
            seen.add((e['season'], e['episode'], e['filename']))
            eps.append(e)
        fetched = {r['season'] for r in c.execute("SELECT season FROM season_fetch WHERE series_id = ?", (sid,))}
        prog = {r['key']: r for r in c.execute("SELECT * FROM progress WHERE key LIKE 'e:%'")}
    seasons = defaultdict(list)
    for e in eps:
        p = prog.get(f"e:{e['id']}")
        seasons[e['season']].append({
            'id': e['id'], 'n': e['episode'], 'name': e['ep_name'] or '', 'file': e['filename'],
            'ov': e['ep_overview'] or '', 'still': bool(e['still']), 'rt': e['runtime'] or 0,
            'pos': p['position'] if p else 0, 'dur': p['duration'] if p else 0, 'fin': bool(p and p['finished']),
            'at': p['updated_at'] if p else 0})
    pending = []
    if s['tmdb_id']:
        pending = [n for n in seasons if n not in fetched]
        for n in pending:
            threading.Thread(target=metadata.fetch_season, args=(sid, s['tmdb_id'], n, ids), daemon=True).start()
    return jsonify({'id': sid, 'seasons': [{'n': n, 'eps': seasons[n]} for n in sorted(seasons)], 'pending': bool(pending)})


# ---------------------------------------------------------------- user state

def sibling_ids(c, series_id):
    r = c.execute("SELECT tmdb_id FROM series WHERE id = ?", (series_id,)).fetchone()
    if not r or not r['tmdb_id']:
        return [series_id]
    return [x['id'] for x in c.execute("SELECT id FROM series WHERE tmdb_id = ?", (r['tmdb_id'],))]


def next_episode(c, e):
    ids = sibling_ids(c, e['series_id'])
    q = ','.join('?' * len(ids))
    return c.execute(f"SELECT * FROM episodes WHERE series_id IN ({q}) AND (season > ? OR (season = ? AND episode > ?)) "
                     f"ORDER BY season, episode, id LIMIT 1", (*ids, e['season'], e['season'], e['episode'])).fetchone()


def _progress_map():
    with session() as c:
        return {r['key']: r for r in c.execute("SELECT * FROM progress")}


@app.route('/api/user')
def api_user():
    with session() as c:
        prog = {r['key']: [round(r['position'] or 0), round(r['duration'] or 0), r['finished'] or 0, r['updated_at'] or 0]
                for r in c.execute("SELECT * FROM progress WHERE key LIKE 'm:%'")}
        mylist = [r['key'] for r in c.execute("SELECT key FROM mylist ORDER BY added_at DESC")]
    return jsonify({'progress': prog, 'mylist': mylist, 'continue': continue_watching()})


def continue_watching():
    out = []
    with session() as c:
        rows = c.execute("SELECT * FROM progress ORDER BY updated_at DESC LIMIT 60").fetchall()
        seen_series = set()
        for r in rows:
            kind, _, sid = r['key'].partition(':')
            if not sid.isdigit():
                continue
            iid = int(sid)
            if kind == 'm':
                if r['finished'] or (r['position'] or 0) < 60:
                    continue
                m = c.execute("SELECT id, title FROM movies WHERE id = ?", (iid,)).fetchone()
                if m:
                    out.append({'kind': 'm', 'id': iid, 'mid': iid, 'title': m['title'], 'sub': '',
                                'pos': r['position'], 'dur': r['duration'], 'at': r['updated_at']})
            elif kind == 'e':
                e = c.execute("SELECT e.*, COALESCE(s.display_title, s.title) AS stitle FROM episodes e "
                              "JOIN series s ON s.id = e.series_id WHERE e.id = ?", (iid,)).fetchone()
                if not e:
                    continue
                group = tuple(sibling_ids(c, e['series_id']))
                if group in seen_series:
                    continue
                seen_series.add(group)
                target, pos, dur = e, r['position'], r['duration']
                if r['finished'] or (r['position'] or 0) < 60:
                    if not r['finished']:
                        continue
                    target = next_episode(c, e)
                    if not target:
                        continue
                    pos, dur = 0, 0
                label = f"S{target['season']}:B{target['episode']}"
                if target['ep_name']:
                    label += f" · {target['ep_name']}"
                out.append({'kind': 'e', 'id': target['id'], 'sid': e['series_id'], 'title': e['stitle'], 'sub': label,
                            'pos': pos, 'dur': dur, 'at': r['updated_at'], 'up_next': target['id'] != e['id']})
            if len(out) >= 20:
                break
    return out


@app.route('/api/progress', methods=['POST'])
def api_progress():
    d = request.get_json(force=True, silent=True) or {}
    key, pos, dur = d.get('key', ''), _num(d.get('position')), _num(d.get('duration'))
    if not key or key[0] not in 'me' or ':' not in key:
        abort(400)
    finished = 1 if dur > 0 and (pos >= dur * 0.93 or dur - pos < 90) else 0
    with session() as c:
        c.execute("INSERT OR REPLACE INTO progress (key, position, duration, finished, updated_at) VALUES (?, ?, ?, ?, ?)",
                  (key, 0 if finished else pos, dur, finished, time.time()))
    return jsonify({'ok': True, 'finished': bool(finished)})


@app.route('/api/progress/<key>', methods=['DELETE'])
def api_progress_delete(key):
    with session() as c:
        c.execute("DELETE FROM progress WHERE key = ?", (key,))
    return jsonify({'ok': True})


@app.route('/api/mylist', methods=['POST'])
def api_mylist():
    d = request.get_json(force=True, silent=True) or {}
    key = d.get('key', '')
    if not key or key[0] not in 'ms':
        abort(400)
    with session() as c:
        if d.get('on'):
            c.execute("INSERT OR IGNORE INTO mylist (key, added_at) VALUES (?, ?)", (key, time.time()))
        else:
            c.execute("DELETE FROM mylist WHERE key = ?", (key,))
    return jsonify({'ok': True})


@app.route('/api/migrate', methods=['POST'])
def api_migrate():
    """Imports v1 favourites/resume positions that lived in the browser's localStorage."""
    d = request.get_json(force=True, silent=True) or {}
    now = time.time()
    with session() as c:
        for fav in d.get('favorites') or []:
            fav = str(fav)
            if fav.startswith('m_') and fav[2:].isdigit():
                c.execute("INSERT OR IGNORE INTO mylist (key, added_at) VALUES (?, ?)", (f"m:{fav[2:]}", now))
            elif fav.startswith('s_'):
                r = c.execute("SELECT id FROM series WHERE title = ? OR CAST(id AS TEXT) = ?", (fav[2:], fav[2:])).fetchone()
                if r:
                    c.execute("INSERT OR IGNORE INTO mylist (key, added_at) VALUES (?, ?)", (f"s:{r['id']}", now))
        for vid, pos in (d.get('positions') or {}).items():
            if not str(vid).isdigit() or _num(pos) < 30:
                continue
            kind = 'm' if c.execute("SELECT 1 FROM movies WHERE id = ?", (int(vid),)).fetchone() else 'e'
            c.execute("INSERT OR IGNORE INTO progress (key, position, duration, finished, updated_at) VALUES (?, ?, 0, 0, ?)",
                      (f"{kind}:{vid}", _num(pos), now))
    return jsonify({'ok': True})


# ---------------------------------------------------------------- playback

def media_path(kind, iid):
    table = {'m': 'movies', 'e': 'episodes'}.get(kind)
    if not table:
        abort(404)
    with session() as c:
        r = c.execute(f"SELECT path FROM {table} WHERE id = ?", (iid,)).fetchone()
    if not r or not os.path.exists(r['path']):
        abort(404)
    return r['path']


@app.route('/api/media/<kind>/<int:iid>')
def api_media(kind, iid):
    path = media_path(kind, iid)
    info = media.probe(path)
    out = {'kind': kind, 'id': iid, 'direct': info['direct'], 'duration': info['duration'], 'audio': info['audio'],
           'subs': [s for s in info['subs'] if s['text']],
           'local_subs': [{'index': s['index'], 'label': s['label'], 'lang': s['lang']} for s in subtitles.local_subtitles(path)],
           'video': info['video'], 'file': os.path.basename(path), 'size': os.path.getsize(path)}
    with session() as c:
        p = c.execute("SELECT * FROM progress WHERE key = ?", (f"{kind}:{iid}",)).fetchone()
        out['resume'] = p['position'] if p and not p['finished'] else 0
        if kind == 'm':
            m = c.execute("SELECT title, year FROM movies WHERE id = ?", (iid,)).fetchone()
            out.update(title=m['title'], sub=m['year'] or '')
        else:
            e = c.execute("SELECT e.*, COALESCE(s.display_title, s.title) AS stitle FROM episodes e "
                          "JOIN series s ON s.id = e.series_id WHERE e.id = ?", (iid,)).fetchone()
            out.update(title=e['stitle'], sid=e['series_id'],
                       sub=f"S{e['season']}:B{e['episode']}" + (f" · {e['ep_name']}" if e['ep_name'] else ''))
            nxt = next_episode(c, e)
            if nxt:
                out['next'] = {'id': nxt['id'], 'label': f"S{nxt['season']}:B{nxt['episode']}",
                               'name': nxt['ep_name'] or '', 'still': bool(nxt['still'])}
    return jsonify(out)


@app.route('/play/<kind>/<int:iid>')
def play(kind, iid):
    path = media_path(kind, iid)
    audio = request.args.get('a', 0, type=int)
    if request.args.get('mode') != 'stream' and audio == 0 and media.probe(path)['direct']:
        mime = 'video/webm' if path.lower().endswith('.webm') else 'video/mp4'
        return send_file(path, mimetype=mime, conditional=True)
    return media.stream(path, request.args.get('t', 0, type=float), audio)


@app.route('/api/hls/<kind>/<int:iid>')
def api_hls(kind, iid):
    path = media_path(kind, iid)
    sid = media.hls_start(path, max(0.0, request.args.get('t', 0, type=float)), request.args.get('a', 0, type=int),
                          request.args.get('c', '')[:64])
    if not sid:
        abort(503)
    return jsonify({'url': f'/hls/{sid}/index.m3u8'})


@app.route('/api/hls/stop', methods=['POST'])
def api_hls_stop():
    client = request.args.get('c', '')[:64]
    if client:
        media.hls_stop(client, request.args.get('s', ''))
    return jsonify({'ok': True})


@app.route('/hls/<sid>/<name>')
def hls_file(sid, name):
    p = media.hls_file(sid, name)
    if not p:
        abort(404)
    playlist = name.endswith('.m3u8')
    r = send_file(p, mimetype='application/vnd.apple.mpegurl' if playlist else 'video/mp2t', conditional=not playlist)
    r.headers['Cache-Control'] = 'no-cache' if playlist else 'max-age=3600'
    return r


@app.route('/api/client_error', methods=['POST'])
def api_client_error():
    d = request.get_json(force=True, silent=True) or {}
    print(f"Oynatma hatası [{request.remote_addr}] {str(d.get('item', ''))[:20]} mod={str(d.get('mode', ''))[:10]} "
          f"kod={str(d.get('code', ''))[:10]} t={_num(d.get('t')):.0f} deneme={_num(d.get('retry')):.0f} "
          f"{str(d.get('msg', ''))[:120]} | {request.headers.get('User-Agent', '')[:160]}")
    return jsonify({'ok': True})


@app.route('/sub/<kind>/<int:iid>/local/<int:n>')
def sub_local(kind, iid, n):
    subs = subtitles.local_subtitles(media_path(kind, iid))
    if n >= len(subs):
        abort(404)
    return app.response_class(subtitles.read_subtitle(subs[n]['path']), mimetype='text/vtt')


@app.route('/sub/<kind>/<int:iid>/embedded/<int:n>')
def sub_embedded(kind, iid, n):
    try:
        text = subtitles.extract_embedded(media_path(kind, iid), n)
    except subprocess.TimeoutExpired:
        text = None
    if not text:
        abort(404)
    return app.response_class(text, mimetype='text/vtt')


@app.route('/api/subs/search/<kind>/<int:iid>')
def subs_search(kind, iid):
    path = media_path(kind, iid)
    with session() as c:
        if kind == 'm':
            r = c.execute("SELECT title, year, original_title FROM movies WHERE id = ?", (iid,)).fetchone()
            query = f"{r['original_title'] or r['title']} {r['year'] or ''}".strip()
        else:
            r = c.execute("SELECT e.season, e.episode, s.title, s.original_title FROM episodes e JOIN series s "
                          "ON s.id = e.series_id WHERE e.id = ?", (iid,)).fetchone()
            query = f"{r['original_title'] or r['title']} S{r['season']:02d}E{r['episode']:02d}"
    return jsonify(subtitles.search_online(path, query))


@app.route('/api/subs/download', methods=['POST'])
def subs_download():
    fid = (request.get_json(force=True, silent=True) or {}).get('file_id')
    if not fid:
        abort(400)
    try:
        vtt = subtitles.download_online(fid)
    except Exception:
        vtt = None
    if not vtt:
        abort(502)
    return app.response_class(vtt, mimetype='text/vtt')


# ---------------------------------------------------------------- images

def _send_image(path, width=None):
    if not path:
        abort(404)
    if width:
        path = media.thumbnail(path, width) or path
    return send_file(path, mimetype='image/jpeg', conditional=True)


@app.route('/img/poster/<kind>/<iid>')
def img_poster(kind, iid):
    w = min(max(request.args.get('w', 0, type=int), 0), 1000) or None
    with session() as c:
        if kind in ('m', 's') and iid.isdigit():
            r = c.execute(f"SELECT poster FROM {'movies' if kind == 'm' else 'series'} WHERE id = ?", (int(iid),)).fetchone()
            return _send_image(library.poster_file(r['poster']) if r else None, w)
        if kind == 'c' and iid.isdigit():
            r = c.execute("SELECT poster FROM collections WHERE id = ?", (int(iid),)).fetchone()
            return _send_image(media.remote_image(r['poster'] if r else None, 'w780'), w)
    abort(404)


@app.route('/img/backdrop/<kind>/<iid>')
def img_backdrop(kind, iid):
    w = min(max(request.args.get('w', 1280, type=int), 300), 1920)
    if not iid.isdigit():
        abort(404)
    iid = int(iid)
    with session() as c:
        if kind == 'm':
            r = c.execute("SELECT path, backdrop FROM movies WHERE id = ?", (iid,)).fetchone()
            if not r:
                abort(404)
            folder, base, generic_ok = library.movie_folder_info(settings, r['path'])
            local = library.find_backdrop(folder, [base], generic_ok)
            return _send_image(local or media.remote_image(r['backdrop'], 'w1280'), w)
        if kind == 's':
            r = c.execute("SELECT title, backdrop FROM series WHERE id = ?", (iid,)).fetchone()
            if not r:
                abort(404)
            folder = library.series_folder(settings, r['title'])
            local = library.find_backdrop(folder) if folder else None
            return _send_image(local or media.remote_image(r['backdrop'], 'w1280'), w)
        if kind == 'c':
            r = c.execute("SELECT backdrop FROM collections WHERE id = ?", (iid,)).fetchone()
            return _send_image(media.remote_image(r['backdrop'] if r else None, 'w1280'), w)
    abort(404)


@app.route('/img/still/<int:eid>')
def img_still(eid):
    with session() as c:
        r = c.execute("SELECT still FROM episodes WHERE id = ?", (eid,)).fetchone()
    return _send_image(media.remote_image(r['still'] if r else None, 'w300'))


@app.route('/get_poster/<path:vid>')
def legacy_poster(vid):
    p = os.path.join(POSTERS_DIR, f"poster_{vid.replace('/', '_')}.jpg")
    return send_file(p) if os.path.exists(p) else ('', 404)


# ---------------------------------------------------------------- admin

def lan_ips():
    skip = ('docker', 'br-', 'virbr', 'lxc', 'veth', 'tun', 'tap', 'wg', 'proton', 'lo')
    try:
        out = subprocess.run(['ip', '-4', '-o', 'addr', 'show', 'scope', 'global'], capture_output=True, text=True,
                             timeout=3).stdout
        return [ln.split()[3].split('/')[0] for ln in out.splitlines() if len(ln.split()) > 3 and not ln.split()[1].startswith(skip)]
    except Exception:
        return []


def is_local_request():
    """True only for requests from this computer (app window, 127.0.0.1 or its own LAN address)."""
    addr = request.remote_addr or ''
    return addr in ('127.0.0.1', '::1') or addr.startswith('127.') or addr in lan_ips()


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    local = is_local_request()
    if request.method == 'POST':
        if not local:
            abort(403)
        d = request.get_json(force=True, silent=True) or {}
        values = {k: str(v).strip() for k, v in d.items() if k in ('movie_dir', 'series_dir', 'omdb_api_key') and str(v).strip()}
        settings.update(values)
        save_settings(values)
    with session() as c:
        stats = {'movies': c.execute("SELECT COUNT(*) FROM movies").fetchone()[0],
                 'series': c.execute("SELECT COUNT(*) FROM series").fetchone()[0],
                 'episodes': c.execute("SELECT COUNT(*) FROM episodes").fetchone()[0],
                 'collections': c.execute("SELECT COUNT(*) FROM collections").fetchone()[0]}
    from .config import PORT
    # Folder paths and the API key are only shown to (and editable from) this computer, not other devices on the LAN.
    private = {k: settings.get(k, '') if local else '' for k in ('movie_dir', 'series_dir', 'omdb_api_key')}
    return jsonify({**private, 'local': local, 'stats': stats, 'urls': [f"http://{ip}:{PORT}" for ip in lan_ips()]})


@app.route('/api/scan', methods=['POST'])
@app.route('/api/rescan', methods=['POST'])
def api_scan():
    threading.Thread(target=library.scan_library, args=(settings,), daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/sync_emby', methods=['POST'])
def api_sync_emby():
    m, s = library.sync_emby(settings)
    state.bump()
    return jsonify({'status': 'ok', 'movies': m, 'series': s})


@app.route('/api/enrich', methods=['POST'])
def api_enrich():
    with session() as c:
        c.execute("UPDATE movies SET meta_tries = 0, enriched = 0 WHERE COALESCE(enriched, 0) != 1")
        c.execute("UPDATE series SET meta_tries = 0, enriched = 0 WHERE COALESCE(enriched, 0) != 1")
    state.wake_enricher()
    return jsonify({'status': 'started'})
