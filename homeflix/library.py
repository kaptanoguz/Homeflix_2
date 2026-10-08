import json
import os
import re
import shutil
import threading
import time
import xml.etree.ElementTree as ET
from collections import defaultdict

from . import state
from .config import IMG_EXTS, POSTERS_DIR, VIDEO_EXTS
from .db import session
from .names import (VTS_RE, clean_display_title, clean_series_name, parse_season_episode, smart_title)

NON_POSTER_WORDS = ('backdrop', 'fanart', 'landscape', 'banner', 'thumb', 'logo', 'clearart', 'disc', 'background')
scan_lock = threading.Lock()
settings_ref = {}
emby_lock = threading.Lock()


def poster_file(poster_value):
    """'/get_poster/movie_12' -> absolute path of the cached poster, or None."""
    if not poster_value or not poster_value.startswith('/get_poster/'):
        return None
    p = os.path.join(POSTERS_DIR, f"poster_{poster_value[len('/get_poster/'):]}.jpg")
    return p if os.path.exists(p) else None


def is_movie_file(name):
    if name.startswith('._') or not name.lower().endswith(VIDEO_EXTS):
        return False
    if re.search(r'[Ss]\d+[Ee]\d+', name):
        return False
    if name.upper() == 'VIDEO_TS.VOB':
        return False
    vm = VTS_RE.match(name)
    return not (vm and vm.group(2) != '1')


# ---------------------------------------------------------------- scanning

def scan_library(settings):
    if not scan_lock.acquire(blocking=False):
        return
    state.set_task('scan', 'Kütüphane taranıyor')
    try:
        _scan(settings)
    except Exception as e:
        print(f"Tarama hatası: {e}")
    finally:
        state.clear_task('scan')
        scan_lock.release()
    sync_emby(settings)
    state.wake_enricher()


def _file_info(path):
    try:
        st = os.stat(path)
        return st.st_mtime, st.st_size
    except OSError:
        return time.time(), 0


def _scan(settings):
    movie_dir, series_dir = settings['movie_dir'], settings['series_dir']
    with session() as c:
        found = set()
        if os.path.isdir(movie_dir):
            existing = {r['path']: r for r in c.execute("SELECT id, path, added_at FROM movies")}
            for root, _, files in os.walk(movie_dir):
                for f in files:
                    if not is_movie_file(f):
                        continue
                    path = os.path.join(root, f)
                    found.add(path)
                    mtime, size = _file_info(path)
                    row = existing.get(path)
                    if row:
                        if not row['added_at']:
                            c.execute("UPDATE movies SET added_at = ?, size = ? WHERE id = ?", (mtime, size, row['id']))
                        continue
                    title, year = smart_title(path)
                    c.execute("INSERT INTO movies (title, year, path, poster, rating, plot, genre, candidates, added_at, size) "
                              "VALUES (?, ?, ?, '', '', '', '', ?, ?, ?)",
                              (title, year, path, json.dumps([title]), mtime, size))
            if found:
                for r in c.execute("SELECT id, path FROM movies").fetchall():
                    if r['path'] not in found:
                        c.execute("DELETE FROM movies WHERE id = ?", (r['id'],))

        shows = defaultdict(list)
        if os.path.isdir(series_dir):
            for root, _, files in os.walk(series_dir):
                for f in files:
                    if f.startswith('._') or not f.lower().endswith(VIDEO_EXTS):
                        continue
                    path = os.path.join(root, f)
                    rel = os.path.relpath(path, series_dir)
                    season, episode = parse_season_episode(rel)
                    shows[clean_series_name(rel.split(os.sep)[0])].append((season, episode, path, f))
        if shows:
            ep_paths = set()
            for name, eps in shows.items():
                row = c.execute("SELECT id FROM series WHERE title = ?", (name,)).fetchone()
                if not row:
                    added = min(_file_info(p)[0] for _, _, p, _ in eps)
                    c.execute("INSERT INTO series (title, year, poster, rating, plot, genre, candidates, added_at) "
                              "VALUES (?, '', '', '', '', '', ?, ?)", (name, json.dumps([name]), added))
                    row = c.execute("SELECT id FROM series WHERE title = ?", (name,)).fetchone()
                sid = row['id']
                for season, episode, path, fname in eps:
                    ep_paths.add(path)
                    c.execute("INSERT INTO episodes (series_id, series_name, season, episode, title, path, filename) "
                              "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(path) DO UPDATE SET series_id = excluded.series_id, "
                              "series_name = excluded.series_name, season = excluded.season, episode = excluded.episode, "
                              "title = excluded.title, filename = excluded.filename",
                              (sid, name, season, episode, fname, path, fname))
            for r in c.execute("SELECT id, title FROM series").fetchall():
                if r['title'] not in shows:
                    c.execute("DELETE FROM series WHERE id = ?", (r['id'],))
            for r in c.execute("SELECT id, path FROM episodes").fetchall():
                if r['path'] not in ep_paths:
                    c.execute("DELETE FROM episodes WHERE id = ?", (r['id'],))


def fill_file_info():
    with session() as c:
        for r in c.execute("SELECT id, path FROM movies WHERE added_at IS NULL").fetchall():
            mtime, size = _file_info(r['path'])
            c.execute("UPDATE movies SET added_at = ?, size = ? WHERE id = ?", (mtime, size, r['id']))
        for r in c.execute("SELECT id FROM series WHERE added_at IS NULL").fetchall():
            e = c.execute("SELECT path FROM episodes WHERE series_id = ? LIMIT 1", (r['id'],)).fetchone()
            c.execute("UPDATE series SET added_at = ? WHERE id = ?", (_file_info(e['path'])[0] if e else time.time(), r['id']))


def tr_title_case(text):
    def word(w):
        if any(ch.isdigit() for ch in w) or len(w) <= 1:
            return w
        low = w.replace('I', 'ı').replace('İ', 'i').lower()
        first = {'i': 'İ', 'ı': 'I'}.get(low[0], low[0].upper())
        return first + low[1:]
    return ' '.join(word(w) for w in text.split(' '))


def cleanup_titles():
    with session() as c:
        for r in c.execute("SELECT id, title FROM movies").fetchall():
            new = clean_display_title(r['title'])
            if new.isupper() and len(new.replace(' ', '')) > 4 and ' ' in new:
                new = tr_title_case(new)
            if new and new != r['title']:
                c.execute("UPDATE movies SET title = ? WHERE id = ?", (new, r['id']))


# ---------------------------------------------------------------- Emby / Jellyfin .nfo

def read_nfo(path, root_tag):
    try:
        with open(path, 'rb') as fh:
            data = fh.read()
        if data.startswith(b'\xef\xbb\xbf'):
            data = data[3:]
        root = ET.fromstring(data)
    except Exception:
        return None
    if root.tag != root_tag:
        return None

    def txt(tag):
        e = root.find(tag)
        return (e.text or '').strip() if e is not None and e.text else ''

    rating = ''
    try:
        rv = float(txt('rating').replace(',', '.'))
        if rv > 0:
            rating = f"{rv:.1f}"
    except ValueError:
        pass
    tmdb = txt('tmdbid')
    set_el = root.find('set')
    set_name = ''
    if set_el is not None:
        set_name = (set_el.findtext('name') or set_el.text or '').strip()
    return {
        'title': txt('title'), 'original_title': txt('originaltitle'), 'rating': rating, 'plot': txt('plot'),
        'year': txt('year'), 'genre': ', '.join(g.text.strip() for g in root.findall('genre') if g.text and g.text.strip()),
        'tmdb_id': int(tmdb) if tmdb.isdigit() else None,
        'imdb_id': txt('imdbid') or txt('imdb_id'), 'set': set_name,
        'runtime': int(txt('runtime')) if txt('runtime').isdigit() else None,
    }


_tiny_cache = {}


def is_tiny(path, limit=200):
    """True for placeholder images (some downloaders drop a 50x50 poster.jpg) so TMDb artwork is used instead."""
    try:
        st = os.stat(path)
    except OSError:
        return False
    key = (path, st.st_mtime, st.st_size)
    if key not in _tiny_cache:
        try:
            from PIL import Image
            with Image.open(path) as im:
                _tiny_cache[key] = max(im.size) < limit
        except Exception:
            _tiny_cache[key] = False
    return _tiny_cache[key]


def _images(folder):
    try:
        return [f for f in os.listdir(folder) if f.lower().endswith(IMG_EXTS) and not f.startswith('._')
                and not is_tiny(os.path.join(folder, f))]
    except OSError:
        return []


def find_poster(folder, base_names, generic_ok):
    files = _images(folder)
    low = {f.lower(): f for f in files}
    names = []
    for b in base_names:
        for ext in IMG_EXTS:
            names += [f"{b}-poster{ext}", f"{b}{ext}"]
    if generic_ok:
        for g in ('poster', 'folder', 'cover', 'movie'):
            names += [g + ext for ext in IMG_EXTS]
    for n in names:
        if n.lower() in low:
            return os.path.join(folder, low[n.lower()])
    if generic_ok:
        imgs = [f for f in files if not any(w in f.lower() for w in NON_POSTER_WORDS)]
        if len(imgs) == 1:
            return os.path.join(folder, imgs[0])
    return None


def find_backdrop(folder, base_names=(), generic_ok=True):
    low = {f.lower(): f for f in _images(folder)}
    names = []
    for b in base_names:
        names += [f"{b}-fanart{ext}" for ext in IMG_EXTS] + [f"{b}-backdrop{ext}" for ext in IMG_EXTS]
    if generic_ok:
        for g in ('backdrop', 'fanart', 'background', 'landscape'):
            names += [g + ext for ext in IMG_EXTS]
    for n in names:
        if n.lower() in low:
            return os.path.join(folder, low[n.lower()])
    return None


def find_movie_nfo(folder, base, generic_ok):
    cands = [os.path.join(folder, base + '.nfo')]
    if generic_ok:
        cands.append(os.path.join(folder, 'movie.nfo'))
        try:
            entries = os.listdir(folder)
            if len([f for f in entries if f.lower().endswith(VIDEO_EXTS)]) <= 1:
                cands += [os.path.join(folder, f) for f in entries if f.lower().endswith('.nfo') and not f.startswith('._')]
        except OSError:
            pass
    for p in cands:
        if os.path.exists(p):
            m = read_nfo(p, 'movie')
            if m:
                return m
    return None


def series_folder(settings, title):
    root = settings['series_dir']
    try:
        for d in os.listdir(root):
            if os.path.isdir(os.path.join(root, d)) and clean_series_name(d).lower() == title.lower():
                return os.path.join(root, d)
    except OSError:
        pass
    return None


def movie_folder_info(settings, path):
    folder, fname = os.path.split(path)
    base = os.path.splitext(fname)[0]
    generic_ok = os.path.normpath(folder) != os.path.normpath(settings['movie_dir'])
    return folder, base, generic_ok


def _copy_poster(src, kind, item_id):
    dst = os.path.join(POSTERS_DIR, f"poster_{kind}_{item_id}.jpg")
    try:
        if not (os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src)
                and os.path.getmtime(dst) >= os.path.getmtime(src)):
            shutil.copyfile(src, dst)
        return f"/get_poster/{kind}_{item_id}"
    except OSError:
        return None


def sync_emby(settings):
    if not emby_lock.acquire(blocking=False):
        return 0, 0
    state.set_task('emby', 'Emby bilgileri okunuyor')
    try:
        return _sync_emby(settings)
    finally:
        state.clear_task('emby')
        emby_lock.release()


def _sync_emby(settings):
    n_movies = n_series = 0
    with session() as c:
        for row in c.execute("SELECT id, path FROM movies").fetchall():
            folder, base, generic_ok = movie_folder_info(settings, row['path'])
            meta = find_movie_nfo(folder, base, generic_ok)
            poster_src = find_poster(folder, [base], generic_ok)
            fields = {}
            if poster_src:
                p = _copy_poster(poster_src, 'movie', row['id'])
                if p:
                    fields['poster'] = p
            if meta:
                for k in ('title', 'original_title', 'rating', 'plot', 'genre', 'year', 'tmdb_id', 'imdb_id', 'runtime'):
                    if meta.get(k):
                        fields[k] = meta[k]
            if fields:
                c.execute(f"UPDATE movies SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?",
                          list(fields.values()) + [row['id']])
                n_movies += 1
        for row in c.execute("SELECT id, title FROM series").fetchall():
            folder = series_folder(settings, row['title'])
            if not folder:
                continue
            nfo = os.path.join(folder, 'tvshow.nfo')
            meta = read_nfo(nfo, 'tvshow') if os.path.exists(nfo) else None
            poster_src = find_poster(folder, [], True)
            fields = {}
            if poster_src:
                p = _copy_poster(poster_src, 'series', row['id'])
                if p:
                    fields['poster'] = p
            if meta:
                for k in ('rating', 'plot', 'genre', 'year', 'tmdb_id', 'original_title'):
                    if meta.get(k):
                        fields[k] = meta[k]
            if fields:
                c.execute(f"UPDATE series SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?",
                          list(fields.values()) + [row['id']])
                n_series += 1
    print(f"Emby metadata: {n_movies} film, {n_series} dizi güncellendi.")
    return n_movies, n_series
