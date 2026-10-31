"""Downloads of local library files to a device: one file at a time per device, and all downloads together share a
speed limit so they never take the bandwidth people need to watch.

A device is the viewer cookie (the same id that keeps its watch history). While a device's download is moving, a
second one from that device is refused; a download that has sent nothing for STALE seconds (the connection died
without the server noticing) no longer counts, so a dropped download never leaves the device locked out.
"""
import threading
import time

CHUNK = 64 * 1024
DEFAULT_MBPS = 40          # all downloads together, in megabits per second
MIN_MBPS, MAX_MBPS = 5, 1000
STALE = 30

_lock = threading.Lock()
_active = {}               # viewer -> {'token', 'name', 'size', 'sent', 'last'}
_bucket = {'tokens': 0.0, 'at': time.monotonic()}
_rate = {'bps': DEFAULT_MBPS * 125_000}


def set_limit(mbps):
    try:
        mbps = int(float(mbps))
    except (TypeError, ValueError):
        mbps = DEFAULT_MBPS
    mbps = max(MIN_MBPS, min(MAX_MBPS, mbps))
    _rate['bps'] = mbps * 125_000
    return mbps


def limit_mbps():
    return _rate['bps'] // 125_000


def status(viewer):
    """What this device is downloading now (or None), and how many devices are downloading in total."""
    with _lock:
        a = _active.get(viewer)
        mine = {'name': a['name'], 'size': a['size'], 'sent': a['sent']} if _alive(a) else None
        return {'mine': mine, 'count': sum(1 for x in _active.values() if _alive(x)), 'limit_mbps': limit_mbps()}


def _take(n):
    """Wait until n bytes fit under the shared limit (a token bucket holding at most a quarter second of data)."""
    while True:
        with _lock:
            now = time.monotonic()
            rate = _rate['bps']
            _bucket['tokens'] = min(rate / 4, _bucket['tokens'] + (now - _bucket['at']) * rate)
            _bucket['at'] = now
            if _bucket['tokens'] >= n:
                _bucket['tokens'] -= n
                return
            wait = (n - _bucket['tokens']) / rate
        time.sleep(min(wait, 0.25))


def _alive(a):
    return a is not None and time.monotonic() - a['last'] < STALE


def claim(viewer, name, size):
    """Make this the device's one download, or return None while another download on this device is still moving.
    A stalled earlier download is replaced and stops at its next chunk."""
    token = object()
    with _lock:
        if _alive(_active.get(viewer)):
            return None
        _active[viewer] = {'token': token, 'name': name, 'size': size, 'sent': 0, 'last': time.monotonic()}
    return token


def _release(viewer, token):
    with _lock:
        if _active.get(viewer, {}).get('token') is token:
            del _active[viewer]


def reader(path, viewer, token, start, length):
    """Yield the byte range of the file, throttled; ends early if the device starts another download."""
    try:
        with open(path, 'rb') as f:
            f.seek(start)
            left = length
            while left > 0:
                with _lock:
                    a = _active.get(viewer)
                    if not a or a['token'] is not token:
                        return
                n = min(CHUNK, left)
                _take(n)
                data = f.read(n)
                if not data:
                    return
                left -= len(data)
                with _lock:
                    a = _active.get(viewer)
                    if a and a['token'] is token:
                        a['sent'] += len(data)
                        a['last'] = time.monotonic()
                yield data
    finally:
        _release(viewer, token)
