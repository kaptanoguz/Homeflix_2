"""Online tab: a TMDb catalog of movies and series that play through frameXTV's iframe player (by TMDb id).

Nothing here downloads video; the browser plays the embed directly. This module only lists what exists on TMDb,
remembers the titles someone opened (for Continue Watching and My List), and works out the next episode."""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import metadata
from .config import TMDB_KEY
from .db import session

# TMDb's genre ids (stable), named as TMDb's tr-TR genre list names them.
GENRES = {
    28: 'Aksiyon', 12: 'Macera', 16: 'Animasyon', 35: 'Komedi', 80: 'Suç', 99: 'Belgesel', 18: 'Dram', 10751: 'Aile',
    14: 'Fantastik', 36: 'Tarih', 27: 'Korku', 10402: 'Müzik', 9648: 'Gizem', 10749: 'Romantik', 878: 'Bilim-Kurgu',
    10770: 'TV Filmi', 53: 'Gerilim', 10752: 'Savaş', 37: 'Vahşi Batı', 10759: 'Aksiyon & Macera', 10762: 'Çocuk',
    10763: 'Haber', 10764: 'Gerçeklik', 10765: 'Bilim Kurgu & Fantazi', 10766: 'Pembe Dizi', 10767: 'Talk Show',
    10768: 'Savaş & Politik',
}

# (row title, TMDb path, extra params, 'm' / 's'); 'm' rows hold movies, 's' rows series.
HOME_ROWS = [
    ('Trend Filmler', '/trending/movie/week', {}, 'm'),
    ('Trend Diziler', '/trending/tv/week', {}, 's'),
    ('Vizyondakiler', '/movie/now_playing', {'region': 'TR'}, 'm'),
    ('Popüler Filmler', '/movie/popular', {}, 'm'),
    # /tv/popular is full of talk shows and untranslated imports; asking for well-voted series cleans it up.
    ('Popüler Diziler', '/discover/tv', {'sort_by': 'popularity.desc', 'vote_count.gte': 200}, 's'),
    ('Türk Filmleri', '/discover/movie', {'with_original_language': 'tr', 'sort_by': 'popularity.desc'}, 'm'),
    ('Türk Dizileri', '/discover/tv', {'with_original_language': 'tr', 'sort_by': 'popularity.desc'}, 's'),
    ('En Yüksek Puanlı Filmler', '/movie/top_rated', {}, 'm'),
    ('En Yüksek Puanlı Diziler', '/tv/top_rated', {}, 's'),
    ('Aksiyon', '/discover/movie', {'with_genres': 28, 'sort_by': 'popularity.desc'}, 'm'),
    ('Komedi', '/discover/movie', {'with_genres': 35, 'sort_by': 'popularity.desc'}, 'm'),
    ('Bilim-Kurgu', '/discover/movie', {'with_genres': 878, 'sort_by': 'popularity.desc'}, 'm'),
    ('Korku', '/discover/movie', {'with_genres': 27, 'sort_by': 'popularity.desc'}, 'm'),
    ('Animasyon', '/discover/movie', {'with_genres': 16, 'sort_by': 'popularity.desc'}, 'm'),
    ('Belgesel', '/discover/movie', {'with_genres': 99, 'sort_by': 'popularity.desc'}, 'm'),
]

# News, reality and talk shows aren't what the tab is for; adult titles never show.
SKIP_GENRES = {10763, 10764, 10767}

HOME_MAX_AGE = 6 * 3600
TITLE_MAX_AGE = 24 * 3600
SEARCH_MAX_AGE = 3600

_cache = {}
_cache_lock = threading.Lock()


class Unavailable(Exception):
    """TMDb can't be reached (or no TMDb key is set) and nothing is cached."""


def _cached(key, max_age, fetch):
    """fetch() at most once per max_age; when TMDb is down, the last good answer is served however old it is."""
    with _cache_lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[0] < max_age:
        return hit[1]
    if not TMDB_KEY:
        raise Unavailable('TMDb anahtarı yok')
    try:
        value = fetch()
    except metadata.NetworkError as e:
        if hit:
            return hit[1]
        raise Unavailable(str(e))
    with _cache_lock:
        _cache[key] = (time.time(), value)
        if len(_cache) > 600:
            for k in sorted(_cache, key=lambda k: _cache[k][0])[:200]:
                del _cache[k]
    return value


def _year(d):
    return (d.get('release_date') or d.get('first_air_date') or '')[:4]


def _rating(d):
    v = d.get('vote_average') or 0
    return f"{v:.1f}" if v and (d.get('vote_count') or 0) >= 20 else ''


def item(d, kind):
    """A TMDb list / search result in the shape the web app's cards use."""
    names = [GENRES[g] for g in d.get('genre_ids') or [] if g in GENRES]
    names = names or [g.get('name') for g in d.get('genres') or [] if g.get('name')]
    return {'kind': kind, 'tm': d['id'], 't': d.get('title') or d.get('name') or '',
            'ot': d.get('original_title') or d.get('original_name') or '', 'y': _year(d), 'r': _rating(d),
            'g': ', '.join(names), 'p': d.get('overview') or '', 'op': d.get('poster_path') or '',
            'ob': d.get('backdrop_path') or ''}


def wanted(r):
    return bool(r.get('poster_path')) and not r.get('adult') and not SKIP_GENRES & set(r.get('genre_ids') or [])


def _results(path, kind, **params):
    if path.startswith('/discover/'):
        params = {'include_adult': 'false', **params}
        if kind == 's' and 'with_genres' not in params:
            params['without_genres'] = ','.join(map(str, sorted(SKIP_GENRES)))
    d = metadata.tmdb(path, quick=True, **params) or {}
    return [item(r, kind) for r in d.get('results') or [] if wanted(r)]


def home():
    def fetch():
        with ThreadPoolExecutor(6) as pool:
            jobs = [(title, pool.submit(_results, path, kind, **params)) for title, path, params, kind in HOME_ROWS]
            rows, failed = [], 0
            for title, job in jobs:
                try:
                    items = job.result()
                except metadata.NetworkError:
                    failed += 1
                    continue
                if items:
                    rows.append({'title': title, 'items': items})
        if failed == len(HOME_ROWS):
            raise metadata.NetworkError('TMDb')
        return rows
    return _cached('home', HOME_MAX_AGE, fetch)


def search(q):
    q = ' '.join(q.split())[:80]
    if len(q) < 2:
        return []

    def fetch():
        d = metadata.tmdb('/search/multi', quick=True, query=q, include_adult='false') or {}
        out = []
        for r in d.get('results') or []:
            kind = {'movie': 'm', 'tv': 's'}.get(r.get('media_type'))
            if kind and wanted(r):
                out.append(item(r, kind))
        return out
    return _cached(('search', q.lower()), SEARCH_MAX_AGE, fetch)


def title(kind, tmdb_id):
    """Details for the online detail page: TMDb info, seasons for series and recommendations."""
    path = f"/{'movie' if kind == 'm' else 'tv'}/{tmdb_id}"

    def fetch():
        d = metadata.tmdb(path, quick=True, append_to_response='recommendations')
        if not d:
            return None
        out = item(d, kind)
        out['tagline'] = d.get('tagline') or ''
        if kind == 'm':
            out['rt'] = d.get('runtime') or 0
            out['date'] = d.get('release_date') or ''
        else:
            out['date'] = d.get('first_air_date') or ''
            out['seasons'] = [[s['season_number'], s.get('episode_count') or 0] for s in d.get('seasons') or []
                              if s.get('season_number') and s.get('episode_count')]
        out['rec'] = [item(r, kind) for r in (d.get('recommendations') or {}).get('results') or []
                      if wanted(r)][:18]
        return out
    data = _cached(('title', kind, tmdb_id), TITLE_MAX_AGE, fetch)
    if data:
        remember(kind, tmdb_id, data)
    return data


def season(tmdb_id, n):
    def fetch():
        d = metadata.tmdb(f"/tv/{tmdb_id}/season/{n}", quick=True) or {}
        return [{'n': e.get('episode_number'), 'name': e.get('name') or '', 'ov': e.get('overview') or '',
                 'still': e.get('still_path') or '', 'rt': e.get('runtime') or 0, 'air': e.get('air_date') or ''}
                for e in d.get('episodes') or [] if e.get('episode_number')]
    return _cached(('season', tmdb_id, n), TITLE_MAX_AGE, fetch)


# ---------------------------------------------------------------- remembered titles

KEEP = ('kind', 'tm', 't', 'ot', 'y', 'r', 'g', 'p', 'op', 'ob', 'rt', 'seasons')


def remember(kind, tmdb_id, data):
    keep = {k: data[k] for k in KEEP if k in data}
    with session() as c:
        c.execute("INSERT OR REPLACE INTO online_titles (kind, tmdb_id, data, updated_at) VALUES (?, ?, ?, ?)",
                  (kind, tmdb_id, json.dumps(keep, ensure_ascii=False), time.time()))


def known(c, kind, tmdb_id):
    r = c.execute("SELECT data FROM online_titles WHERE kind = ? AND tmdb_id = ?", (kind, tmdb_id)).fetchone()
    return json.loads(r['data']) if r else None


def next_episode(info, s, e):
    """(season, episode) after s:e from the season sizes TMDb gave, or None after the last one."""
    sizes = dict((n, count) for n, count in (info or {}).get('seasons') or [])
    if e < sizes.get(s, 0):
        return s, e + 1
    later = sorted(n for n in sizes if n > s and sizes[n])
    return (later[0], 1) if later else None


def parse_key(key):
    """'om:<tmdb>' -> ('m', tm, 0, 0); 'oe:<tmdb>:<s>:<e>' -> ('s', tm, s, e); None for anything else."""
    kind, _, rest = key.partition(':')
    parts = rest.split(':')
    if not all(p.isdigit() for p in parts):
        return None
    if kind == 'om' and len(parts) == 1:
        return 'm', int(parts[0]), 0, 0
    if kind == 'oe' and len(parts) == 3:
        return 's', int(parts[0]), int(parts[1]), int(parts[2])
    if kind == 'os' and len(parts) == 1:
        return 's', int(parts[0]), 0, 0
    return None
