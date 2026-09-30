import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_FILE = os.path.join(DATA_DIR, "homeflix.db")
POSTERS_DIR = os.path.join(DATA_DIR, "posters")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
THUMBS_DIR = os.path.join(CACHE_DIR, "thumbs")
IMAGES_DIR = os.path.join(CACHE_DIR, "images")
SUBS_DIR = os.path.join(CACHE_DIR, "subs")

for _d in (DATA_DIR, POSTERS_DIR, CACHE_DIR, THUMBS_DIR, IMAGES_DIR, SUBS_DIR):
    os.makedirs(_d, exist_ok=True)

PORT = int(os.environ.get("HOMEFLIX_PORT", "5000"))

TMDB_KEY = "3aec63790d50f3b9fc2efb4c15a8cf99"
TMDB_IMG = "https://image.tmdb.org/t/p/"
OMDB_KEYS = ["4255837a", "d0f27f55", "b9bd48a6"]
OPENSUBTITLES_API_KEY = "DeTeFvcW0oZNdErwGeYlpjWNOsZozwDz"
USER_AGENT = "Homeflix/2.0"

VIDEO_EXTS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.vob',
              '.divx', '.mpg', '.mpeg', '.m2ts', '.3gp', '.ogv')
IMG_EXTS = ('.jpg', '.jpeg', '.png', '.webp')

DEFAULT_MOVIE_DIRS = ["/media/oguz/BackupPlus/Film", "/media/oguz/BackupPlus/Movies",
                      os.path.expanduser("~/Videos/Film"), os.path.expanduser("~/Videos/Movies")]
DEFAULT_SERIES_DIRS = ["/media/oguz/BackupPlus/dizi", "/media/oguz/BackupPlus/Diziler",
                       os.path.expanduser("~/Videos/dizi"), os.path.expanduser("~/Videos/Diziler")]
