import math
import os
import re
import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from . import state
from .config import OMDB_KEYS, POSTERS_DIR, TMDB_IMG, TMDB_KEY, USER_AGENT
from .db import session
from . import library
from .library import poster_file
from .names import fold, search_candidates

http = requests.Session()
http.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
http.mount("http://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=1)))
http.headers.update({'User-Agent': USER_AGENT})

GENRE_TR = {
    'action': 'Aksiyon', 'adventure': 'Macera', 'animation': 'Animasyon', 'comedy': 'Komedi', 'crime': 'Suç',
    'documentary': 'Belgesel', 'drama': 'Dram', 'family': 'Aile', 'fantasy': 'Fantastik', 'history': 'Tarih',
    'horror': 'Korku', 'music': 'Müzik', 'musical': 'Müzikal', 'mystery': 'Gizem', 'romance': 'Romantik',
    'sci-fi': 'Bilim-Kurgu', 'science fiction': 'Bilim-Kurgu', 'thriller': 'Gerilim', 'war': 'Savaş',
    'western': 'Vahşi Batı', 'biography': 'Biyografi', 'sport': 'Spor', 'short': 'Kısa',
}


class NetworkError(Exception):
    pass


def tmdb(path, **params):
    params = {'api_key': TMDB_KEY, 'language': 'tr-TR', **params}
    try:
        r = http.get(f"https://api.themoviedb.org/3{path}", params=params, timeout=10)
    except requests.RequestException as e:
        raise NetworkError(str(e))
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise NetworkError(f"TMDb {r.status_code}")
    return r.json()


def download(url, dest):
    try:
        r = http.get(url, timeout=15)
        if r.status_code == 200 and len(r.content) > 1000:
            tmp = dest + '.part'
            with open(tmp, 'wb') as f:
                f.write(r.content)
            os.replace(tmp, dest)
            return True
    except (requests.RequestException, OSError):
        pass
    return False


def movie_cert(d):
    """'US:PG' / 'TR:7+' from a /movie response with release_dates appended; '' when TMDb has no rating."""
    by_country = {r.get('iso_3166_1'): [x.get('certification') for x in r.get('release_dates') or [] if x.get('certification')]
                  for r in (d.get('release_dates') or {}).get('results') or []}
    for country in ('US', 'TR'):
        if by_country.get(country):
            return f"{country}:{by_country[country][0]}"
    return ''


def tv_cert(d):
    by_country = {r.get('iso_3166_1'): r.get('rating') for r in (d.get('content_ratings') or {}).get('results') or [] if r.get('rating')}
    for country in ('US', 'TR'):
        if by_country.get(country):
            return f"{country}:{by_country[country]}"
    return ''


def translate_genres(genre):
    if not genre:
        return genre
    out = []
    for g in [x.strip() for x in genre.split(',') if x.strip()]:
        t = GENRE_TR.get(g.lower(), g)
        if t not in out:
            out.append(t)
    return ', '.join(out)


def clean_collection_name(name):
    name = re.sub(r'\s*\[(Seri|Koleksiyon)\]\s*', '', name or '', flags=re.I)
    name = re.sub(r'\s+(Serisi|Koleksiyonu|Collection)$', '', name, flags=re.I)
    return name.strip()


def _year_of(item, key):
    d = item.get(key) or ''
    return d[:4] if len(d) >= 4 else ''


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', fold(s))


def _score(r, query, year, date_key):
    title = r.get('title') or r.get('name') or ''
    orig = r.get('original_title') or r.get('original_name') or ''
    nq = _norm(query)
    s = 0.0
    if nq and nq in (_norm(title), _norm(orig)):
        s += 10
    elif nq and (_norm(title).startswith(nq) or _norm(orig).startswith(nq) or nq.startswith(_norm(title) or '#')):
        s += 4
    qw = set(re.sub(r'[^\w\s]', ' ', fold(query)).split())
    tw = set(re.sub(r'[^\w\s]', ' ', fold(title + ' ' + orig)).split())
    s += 4 * len(qw & tw) / max(1, len(qw))
    ry = _year_of(r, date_key)
    if year and str(year).isdigit() and ry.isdigit():
        s += 5 if abs(int(ry) - int(year)) <= 1 else -4
    s += min(3.5, math.log10(1 + (r.get('vote_count') or 0)))
    return s


def _pick(results, year, date_key, query=''):
    if not results:
        return None
    return max(results[:10], key=lambda r: _score(r, query, year, date_key))


def search_tmdb(kind, title, year='', original_title=''):
    path = '/search/movie' if kind == 'movie' else '/search/tv'
    date_key = 'release_date' if kind == 'movie' else 'first_air_date'
    year_param = 'year' if kind == 'movie' else 'first_air_date_year'
    queries = ([original_title] if original_title else []) + search_candidates(title)
    for q in dict.fromkeys(queries):
        params = {'query': q}
        if year and str(year).isdigit():
            params[year_param] = year
        res = tmdb(path, **params) or {}
        hit = _pick(res.get('results'), year, date_key, q)
        if not hit and year_param in params:
            res = tmdb(path, query=q) or {}
            hit = _pick(res.get('results'), year, date_key, q)
        if hit:
            return hit
    return None


def omdb_lookup(title, year='', imdb_id=''):
    for key in OMDB_KEYS[:2]:
        params = {'apikey': key}
        if imdb_id:
            params['i'] = imdb_id
        else:
            params['t'] = title
            if year:
                params['y'] = year
        try:
            d = http.get("http://www.omdbapi.com/", params=params, timeout=8).json()
        except (requests.RequestException, ValueError):
            continue
        if d.get('Response') == 'True':
            return d
    return None


def _ensure_poster(c, table, kind, row, tmdb_poster):
    current = poster_file(row['poster'])
    if (current and not library.is_tiny(current)) or not tmdb_poster:
        return
    dest = os.path.join(POSTERS_DIR, f"poster_{kind}_{row['id']}.jpg")
    if download(f"{TMDB_IMG}w780{tmdb_poster}", dest):
        c.execute(f"UPDATE {table} SET poster = ? WHERE id = ?", (f"/get_poster/{kind}_{row['id']}", row['id']))


def ensure_collection(c, col):
    cid = col['id']
    if c.execute("SELECT fetched FROM collections WHERE id = ?", (cid,)).fetchone():
        return
    c.execute("INSERT OR IGNORE INTO collections (id, name, poster, backdrop) VALUES (?, ?, ?, ?)",
              (cid, clean_collection_name(col.get('name')), col.get('poster_path'), col.get('backdrop_path')))


def fetch_collection_details(cid):
    d = tmdb(f"/collection/{cid}")
    if not d:
        return
    with session() as c:
        c.execute("UPDATE collections SET name = ?, overview = ?, poster = COALESCE(?, poster), "
                  "backdrop = COALESCE(?, backdrop), parts = ?, fetched = 1 WHERE id = ?",
                  (clean_collection_name(d.get('name')), d.get('overview') or '', d.get('poster_path'),
                   d.get('backdrop_path'), len(d.get('parts') or []), cid))


def enrich_movie(row):
    with session() as c:
        tmdb_id = row['tmdb_id']
        if not tmdb_id:
            hit = search_tmdb('movie', row['title'], row['year'], row['original_title'])
            tmdb_id = hit['id'] if hit else None
        if not tmdb_id:
            fields = {}
            if not row['rating'] or not poster_file(row['poster']):
                o = omdb_lookup(row['title'], row['year'])
                if o:
                    if not row['rating'] and o.get('imdbRating') not in (None, 'N/A'):
                        fields['rating'] = o['imdbRating']
                    if not row['plot'] and o.get('Plot') not in (None, 'N/A'):
                        fields['plot'] = o['Plot']
                    if not row['genre'] and o.get('Genre') not in (None, 'N/A'):
                        fields['genre'] = translate_genres(o['Genre'])
                    if o.get('imdbID'):
                        fields['imdb_id'] = o['imdbID']
                    poster = o.get('Poster')
                    if poster and poster != 'N/A' and not poster_file(row['poster']):
                        if download(poster, os.path.join(POSTERS_DIR, f"poster_movie_{row['id']}.jpg")):
                            fields['poster'] = f"/get_poster/movie_{row['id']}"
            tries = (row['meta_tries'] or 0) + 1
            fields['meta_tries'] = tries
            fields['enriched'] = 2 if tries >= 3 else 0
            c.execute(f"UPDATE movies SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?",
                      list(fields.values()) + [row['id']])
            return
        d = tmdb(f"/movie/{tmdb_id}", append_to_response='release_dates') or {}
        fields = {'tmdb_id': tmdb_id, 'enriched': 1, 'cert': movie_cert(d)}
        if d.get('runtime'):
            fields['runtime'] = d['runtime']
        if d.get('imdb_id') and not row['imdb_id']:
            fields['imdb_id'] = d['imdb_id']
        if d.get('original_title'):
            fields['original_title'] = d['original_title']
        fields['backdrop'] = d.get('backdrop_path')
        genres = ', '.join(g['name'] for g in d.get('genres') or [])
        if genres and not row['genre']:
            fields['genre'] = genres
        elif row['genre'] and translate_genres(row['genre']) != row['genre']:
            fields['genre'] = translate_genres(row['genre'])
        if not row['plot'] and d.get('overview'):
            fields['plot'] = d['overview']
        if not row['rating'] or row['rating'] == 'N/A':
            va = d.get('vote_average') or 0
            if va:
                fields['rating'] = f"{va:.1f}"
        if not row['year'] and d.get('release_date'):
            fields['year'] = d['release_date'][:4]
        tmdb_title = (d.get('title') or '').strip()
        if tmdb_title and fold(tmdb_title) != fold(row['title']) and len(tmdb_title) < len(row['title']):
            cur = re.sub(r'\W+', ' ', fold(row['title'])).strip()
            short = re.sub(r'\W+', ' ', fold(tmdb_title)).strip()
            if short and cur.startswith(short + ' '):
                fields['title'] = tmdb_title
        col = d.get('belongs_to_collection')
        fields['collection_id'] = col['id'] if col else None
        if col:
            ensure_collection(c, col)
        c.execute(f"UPDATE movies SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?",
                  list(fields.values()) + [row['id']])
        folder, base, generic_ok = library.movie_folder_info(library.settings_ref, row['path'])
        if d.get('poster_path') and not library.find_poster(folder, [base], generic_ok):
            dest = os.path.join(POSTERS_DIR, f"poster_movie_{row['id']}.jpg")
            if download(f"{TMDB_IMG}w780{d['poster_path']}", dest):
                c.execute("UPDATE movies SET poster = ? WHERE id = ?", (f"/get_poster/movie_{row['id']}", row['id']))


def enrich_series(row):
    with session() as c:
        tmdb_id = row['tmdb_id']
        if not tmdb_id:
            hit = search_tmdb('tv', row['title'], row['year'], row['original_title'])
            tmdb_id = hit['id'] if hit else None
        if not tmdb_id:
            tries = (row['meta_tries'] or 0) + 1
            c.execute("UPDATE series SET meta_tries = ?, enriched = ? WHERE id = ?", (tries, 2 if tries >= 3 else 0, row['id']))
            return
        d = tmdb(f"/tv/{tmdb_id}", append_to_response='content_ratings') or {}
        fields = {'tmdb_id': tmdb_id, 'enriched': 1, 'cert': tv_cert(d)}
        if d.get('backdrop_path'):
            fields['backdrop'] = d['backdrop_path']
        if d.get('original_name'):
            fields['original_title'] = d['original_name']
        if d.get('name'):
            fields['display_title'] = d['name']
        genres = ', '.join(g['name'] for g in d.get('genres') or [])
        if genres and not row['genre']:
            fields['genre'] = genres
        if not row['plot'] and d.get('overview'):
            fields['plot'] = d['overview']
        if not row['rating'] and d.get('vote_average'):
            fields['rating'] = f"{d['vote_average']:.1f}"
        if not row['year'] and d.get('first_air_date'):
            fields['year'] = d['first_air_date'][:4]
        c.execute(f"UPDATE series SET {', '.join(k + ' = ?' for k in fields)} WHERE id = ?",
                  list(fields.values()) + [row['id']])
        _ensure_poster(c, 'series', 'series', row, d.get('poster_path'))


def enricher_loop():
    while True:
        state.enrich_wake.wait()
        state.enrich_wake.clear()
        with session() as c:
            movies = c.execute("SELECT * FROM movies WHERE COALESCE(enriched, 0) = 0 AND (COALESCE(meta_tries, 0) < 3 OR tmdb_id IS NOT NULL) "
                               "ORDER BY added_at DESC").fetchall()
            shows = c.execute("SELECT * FROM series WHERE COALESCE(enriched, 0) = 0 AND (COALESCE(meta_tries, 0) < 3 OR tmdb_id IS NOT NULL)").fetchall()
        jobs = [(enrich_series, r) for r in shows] + [(enrich_movie, r) for r in movies]
        state.enrich.update(done=0, total=len(jobs))
        failures = 0
        for i, (fn, row) in enumerate(jobs):
            try:
                fn(row)
                failures = 0
            except NetworkError as e:
                failures += 1
                if failures >= 5:
                    print(f"Metadata: ağ hatası, sonra tekrar denenecek ({e})")
                    break
            except Exception as e:
                print(f"Metadata hatası ({row['title']}): {e}")
            state.enrich['done'] = i + 1
            if (i + 1) % 40 == 0:
                state.bump()
            time.sleep(0.05)
        try:
            with session() as c:
                pending = [r['id'] for r in c.execute("SELECT id FROM collections WHERE fetched = 0")]
            for cid in pending:
                fetch_collection_details(cid)
                time.sleep(0.05)
        except Exception as e:
            print(f"Koleksiyon hatası: {e}")
        state.enrich.update(done=0, total=0)
        state.bump()


_season_jobs = set()
_season_lock = threading.Lock()


def fetch_season(series_id, tmdb_id, season, ids=None):
    key = (series_id, season)
    with _season_lock:
        if key in _season_jobs:
            return
        _season_jobs.add(key)
    try:
        d = tmdb(f"/tv/{tmdb_id}/season/{season}")
        with session() as c:
            for ep in (d or {}).get('episodes') or []:
                for sid in ids or [series_id]:
                    c.execute("UPDATE episodes SET ep_name = ?, ep_overview = ?, still = ?, runtime = ? "
                              "WHERE series_id = ? AND season = ? AND episode = ?",
                              (ep.get('name'), ep.get('overview'), ep.get('still_path'), ep.get('runtime'),
                               sid, season, ep.get('episode_number')))
            c.execute("INSERT OR REPLACE INTO season_fetch (series_id, season, fetched_at) VALUES (?, ?, ?)",
                      (series_id, season, time.time()))
    except Exception as e:
        print(f"Sezon bilgisi alınamadı: {e}")
    finally:
        with _season_lock:
            _season_jobs.discard(key)


def start():
    threading.Thread(target=enricher_loop, daemon=True, name="enricher").start()
