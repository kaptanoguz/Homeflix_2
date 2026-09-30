import hashlib
import json
import os
import re
import subprocess
import threading

from flask import Response

from .config import IMAGES_DIR, THUMBS_DIR, TMDB_IMG
from .metadata import download
from .names import vob_parts

HAS_VAAPI = os.path.exists('/dev/dri/renderD128')
BROWSER_VIDEO = ('h264', 'vp8', 'vp9', 'av1')
BROWSER_AUDIO = ('aac', 'mp3', 'opus', 'vorbis')
TEXT_SUBS = ('subrip', 'ass', 'ssa', 'mov_text', 'webvtt', 'text')

LANG_NAMES = {'tur': 'Türkçe', 'tr': 'Türkçe', 'eng': 'İngilizce', 'en': 'İngilizce', 'ger': 'Almanca', 'deu': 'Almanca',
              'fre': 'Fransızca', 'fra': 'Fransızca', 'spa': 'İspanyolca', 'ita': 'İtalyanca', 'rus': 'Rusça',
              'jpn': 'Japonca', 'kor': 'Korece', 'ara': 'Arapça', 'und': ''}

_probe_cache = {}
_probe_lock = threading.Lock()


def probe(path):
    with _probe_lock:
        if path in _probe_cache:
            return _probe_cache[path]
    parts = vob_parts(path) or [path]
    info = {'duration': 0.0, 'video': None, 'audio': [], 'subs': [], 'container': os.path.splitext(path)[1].lower()}
    for i, part in enumerate(parts):
        try:
            out = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', part],
                                 capture_output=True, text=True, timeout=15).stdout
            d = json.loads(out or '{}')
        except Exception:
            continue
        info['duration'] += float((d.get('format') or {}).get('duration') or 0)
        if i:
            continue
        for st in d.get('streams', []):
            tags = st.get('tags') or {}
            lang = (tags.get('language') or 'und').lower()
            t = st.get('codec_type')
            if t == 'video' and not info['video'] and (st.get('disposition') or {}).get('attached_pic') != 1:
                info['video'] = {'codec': (st.get('codec_name') or '').lower(), 'width': st.get('width'),
                                 'height': st.get('height')}
            elif t == 'audio':
                info['audio'].append({'index': len(info['audio']), 'codec': (st.get('codec_name') or '').lower(),
                                      'lang': lang, 'channels': st.get('channels') or 2,
                                      'title': tags.get('title') or '',
                                      'label': _track_label(lang, tags.get('title'), st.get('channels'))})
            elif t == 'subtitle':
                codec = (st.get('codec_name') or '').lower()
                info['subs'].append({'index': len(info['subs']), 'codec': codec, 'lang': lang,
                                     'title': tags.get('title') or '', 'text': codec in TEXT_SUBS,
                                     'label': _track_label(lang, tags.get('title'))})
    v = (info['video'] or {}).get('codec')
    a = info['audio'][0]['codec'] if info['audio'] else 'aac'
    info['direct'] = (info['container'] in ('.mp4', '.m4v', '.webm') and v in BROWSER_VIDEO and a in BROWSER_AUDIO
                      and not vob_parts(path))
    with _probe_lock:
        _probe_cache[path] = info
    return info


def _track_label(lang, title=None, channels=None):
    name = LANG_NAMES.get(lang, lang.upper() if lang else '')
    title = (title or '').strip()
    if len(title) > 32 or re.search(r'encoded|www\.|\.com|\.org|x26[45]|S\d{2}E\d{2}|\d{3,4}p|\w\.\w+\.', title, re.I):
        title = ''
    bits = [b for b in (name, title) if b]
    label = ' · '.join(dict.fromkeys(bits)) or 'Varsayılan'
    if channels and channels > 2:
        label += ' (5.1)' if channels == 6 else f' ({channels}ch)'
    return label


def stream(path, start=0.0, audio=0):
    info = probe(path)
    v = (info['video'] or {}).get('codec', 'h264')
    tracks = info['audio']
    audio = audio if 0 <= audio < len(tracks) else 0
    a = tracks[audio]['codec'] if tracks else 'aac'
    parts = vob_parts(path)
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-loglevel', 'error']
    if v != 'h264' and HAS_VAAPI:
        cmd += ['-vaapi_device', '/dev/dri/renderD128']
    if start > 0:
        cmd += ['-ss', f"{start:.2f}"]
    cmd += ['-i', ('concat:' + '|'.join(parts)) if parts else path, '-map', '0:v:0', '-map', f'0:a:{audio}?']
    if v == 'h264':
        cmd += ['-c:v', 'copy']
    elif HAS_VAAPI:
        cmd += ['-vf', 'format=nv12,hwupload', '-c:v', 'h264_vaapi']
    else:
        cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p']
    if a == 'aac':
        cmd += ['-c:a', 'copy', '-bsf:a', 'aac_adtstoasc']
    elif a == 'mp3':
        cmd += ['-c:a', 'copy']
    else:
        cmd += ['-c:a', 'aac', '-b:a', '192k', '-ac', '2']
    cmd += ['-sn', '-movflags', 'frag_keyframe+empty_moov+default_base_moof', '-f', 'mp4', 'pipe:1']

    def generate():
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        try:
            while True:
                chunk = p.stdout.read(262144)
                if not chunk:
                    break
                yield chunk
        finally:
            p.kill()
            p.wait()

    r = Response(generate(), mimetype='video/mp4')
    r.headers['Cache-Control'] = 'no-store'
    return r


# ---------------------------------------------------------------- images

def thumbnail(src, width):
    """Resized JPEG copy of a local image, cached by source path + mtime."""
    try:
        st = os.stat(src)
    except OSError:
        return None
    key = hashlib.sha1(f"{src}|{st.st_mtime}|{st.st_size}|{width}".encode()).hexdigest()
    dest = os.path.join(THUMBS_DIR, f"{key}.jpg")
    if os.path.exists(dest):
        return dest
    try:
        from PIL import Image
        with Image.open(src) as im:
            im = im.convert('RGB')
            if im.width > width:
                im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            tmp = dest + '.part'
            im.save(tmp, 'JPEG', quality=84, optimize=True, progressive=True)
            os.replace(tmp, dest)
        return dest
    except Exception:
        return src


def remote_image(tmdb_path, size='w1280'):
    if not tmdb_path:
        return None
    name = hashlib.sha1(f"{size}{tmdb_path}".encode()).hexdigest() + '.jpg'
    dest = os.path.join(IMAGES_DIR, name)
    if os.path.exists(dest) or download(f"{TMDB_IMG}{size}{tmdb_path}", dest):
        return dest
    return None
