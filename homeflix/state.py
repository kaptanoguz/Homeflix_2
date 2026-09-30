import threading

_lock = threading.Lock()
_tasks = {}
enrich = {'done': 0, 'total': 0}
enrich_wake = threading.Event()
library_version = [0]


def set_task(key, label):
    with _lock:
        _tasks[key] = label


def clear_task(key):
    with _lock:
        _tasks.pop(key, None)
        library_version[0] += 1


def bump():
    with _lock:
        library_version[0] += 1


def wake_enricher():
    enrich_wake.set()


def snapshot():
    with _lock:
        tasks = list(_tasks.values())
    busy_enrich = enrich['total'] > 0 and enrich['done'] < enrich['total']
    if busy_enrich:
        tasks.append(f"Bilgiler zenginleştiriliyor {enrich['done']}/{enrich['total']}")
    return {
        'busy': bool(tasks),
        'tasks': tasks,
        'scanning': 'Kütüphane taranıyor' in tasks,
        'queue': max(0, enrich['total'] - enrich['done']),
        'version': library_version[0],
    }
