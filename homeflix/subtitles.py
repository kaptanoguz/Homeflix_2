import hashlib
import os
import re
import struct
import subprocess

import requests

from .config import OPENSUBTITLES_API_KEY, SUBS_DIR, USER_AGENT
from .names import vob_parts

SUB_EXTS = ('.srt', '.vtt', '.sub', '.ass', '.ssa')
OS_HEADERS = {'Api-Key': OPENSUBTITLES_API_KEY, 'Content-Type': 'application/json', 'User-Agent': USER_AGENT}


def local_subtitles(video_path):
    folder, fname = os.path.split(video_path)
    base = os.path.splitext(fname)[0].lower()
    try:
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith(SUB_EXTS) and not f.startswith('._'))
    except OSError:
        return []
    videos = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in
              ('.mp4', '.mkv', '.avi', '.ts', '.mov', '.m4v', '.wmv', '.webm', '.mpg', '.mpeg', '.vob')]
    matches = [f for f in files if f.lower().startswith(base)]
    if not matches and len(videos) <= 1 or (not matches and vob_parts(video_path)):
        matches = files
    out = []
    for i, f in enumerate(matches):
        rest = os.path.splitext(f)[0][len(base):].strip('._- ').lower() if f.lower().startswith(base) else ''
        label = {'tr': 'Türkçe', 'tur': 'Türkçe', 'turkish': 'Türkçe', 'en': 'İngilizce', 'eng': 'İngilizce',
                 'english': 'İngilizce'}.get(rest, rest.upper() if rest else ('Yerel altyazı' if len(matches) == 1 else f))
        out.append({'index': i, 'path': os.path.join(folder, f), 'label': label,
                    'lang': 'tr' if label == 'Türkçe' else ('en' if label == 'İngilizce' else '')})
    out.sort(key=lambda s: (s['lang'] != 'tr', s['index']))
    for i, s in enumerate(out):
        s['index'] = i
    return out


def decode_text(data):
    for enc in ('utf-8-sig', 'cp1254', 'latin-1'):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode('latin-1', errors='ignore')


def to_vtt(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if text.lstrip().startswith('WEBVTT'):
        return text
    if re.search(r'^\[Script Info\]', text, re.M):
        return ass_to_vtt(text)
    return "WEBVTT\n\n" + re.sub(r'(\d{1,2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', text)


def ass_to_vtt(text):
    out = ["WEBVTT", ""]
    fmt = None
    for line in text.split('\n'):
        if line.startswith('Format:') and fmt is None and 'Start' in line:
            fmt = [x.strip().lower() for x in line[7:].split(',')]
        elif line.startswith('Dialogue:') and fmt:
            vals = line[9:].split(',', len(fmt) - 1)
            row = dict(zip(fmt, vals))

            def ts(v):
                h, m, s = v.strip().split(':')
                return f"{int(h):02d}:{int(m):02d}:{float(s):06.3f}"
            body = re.sub(r'\{[^}]*\}', '', row.get('text', '')).replace('\\N', '\n').replace('\\n', '\n')
            out += [f"{ts(row['start'])} --> {ts(row['end'])}", body.strip(), ""]
    return '\n'.join(out)


def read_subtitle(path):
    with open(path, 'rb') as f:
        return to_vtt(decode_text(f.read()))


def extract_embedded(path, index):
    st = os.stat(path)
    key = hashlib.sha1(f"{path}|{st.st_mtime}|{index}".encode()).hexdigest()
    dest = os.path.join(SUBS_DIR, key + '.vtt')
    if os.path.exists(dest):
        with open(dest, encoding='utf-8') as f:
            return f.read()
    out = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', path, '-map', f'0:s:{index}', '-f', 'webvtt', 'pipe:1'],
                         capture_output=True, timeout=180).stdout
    if not out:
        return None
    text = decode_text(out)
    with open(dest, 'w', encoding='utf-8') as f:
        f.write(text)
    return text


def opensubtitles_hash(path):
    size = os.path.getsize(path)
    if size < 131072:
        return None
    h = size
    with open(path, 'rb') as f:
        for off in (0, size - 65536):
            f.seek(off)
            h = (h + sum(struct.unpack('<8192Q', f.read(65536)))) & 0xFFFFFFFFFFFFFFFF
    return f"{h:016x}"


def search_online(path, query):
    results, seen = [], set()

    def collect(params, tag):
        try:
            r = requests.get("https://api.opensubtitles.com/api/v1/subtitles", params=params, headers=OS_HEADERS, timeout=10)
            if r.status_code != 200:
                return
            for item in r.json().get('data', []):
                attr = item['attributes']
                if attr.get('language') not in ('tr', 'en') or not attr.get('files'):
                    continue
                fid = attr['files'][0]['file_id']
                if fid in seen:
                    continue
                seen.add(fid)
                results.append({'file_id': fid, 'lang': attr['language'], 'release': attr.get('release') or '',
                                'downloads': attr.get('download_count') or 0, 'match': tag,
                                'title': f"[{tag}] {attr['language']} - {attr.get('release') or ''}"})
        except (requests.RequestException, ValueError, KeyError):
            pass

    try:
        mh = opensubtitles_hash(path)
    except OSError:
        mh = None
    if mh:
        collect({'moviehash': mh, 'languages': 'tr,en'}, 'HASH')
    if len(results) < 5 and query:
        collect({'query': query, 'languages': 'tr,en'}, 'ISIM')
    results.sort(key=lambda x: (x['match'] != 'HASH', x['lang'] != 'tr', -x['downloads']))
    return results


def download_online(file_id):
    r = requests.post("https://api.opensubtitles.com/api/v1/download", headers=OS_HEADERS,
                      json={'file_id': file_id}, timeout=10)
    if r.status_code != 200:
        return None
    link = r.json().get('link')
    if not link:
        return None
    return to_vtt(decode_text(requests.get(link, timeout=15).content))
