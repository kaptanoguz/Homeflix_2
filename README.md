# Homeflix

A personal movie and TV platform for your home network: watch the movies and series on your own computer from your phone, TV or browser, in a Netflix-style interface.

Self-hosted home media server and player for your own library (a lightweight Plex / Jellyfin alternative): TMDb posters and metadata, collections, resume playback, live transcoding of MKV/AVI, subtitles from OpenSubtitles. Python + Flask, runs on Linux and Windows. The interface is in Turkish.

![Homeflix home page: featured series and the Continue Watching row](docs/screenshots/home.jpg)

```bash
./run.sh              # app window
./run.sh --browser    # in the default browser
./run.sh --headless   # server only
```

From other devices: `http://<computer-ip-address>:5000` (the address is shown on the Settings screen).
For a different port: `HOMEFLIX_PORT=5001 ./run.sh`.

## Getting your API keys

**OMDb API key** (for posters & metadata)
1. Go to https://www.omdbapi.com/apikey.aspx
2. Select the FREE tier (1,000 daily requests)
3. Enter your email and submit
4. Check your email for the API key
5. Paste it into Home Theater settings

**OpenSubtitles API key** (for subtitles, optional)
1. Create an account at https://www.opensubtitles.com
2. Go to https://www.opensubtitles.com/consumers
3. Register a new consumer/app to get your API key
4. Paste it into Home Theater settings

## Features

- **Home page:** rotating featured banner, Continue Watching, My List, Recently Added, Collections, Series, Top Rated, and rows by genre.
- **Collections:** sequels (Matrix 1-2-3, Felekten Bir Gece 1-2-3, Harry Potter…) are grouped automatically from TMDb. Those not on TMDb are grouped by the number in their name.
- **Detail page:** backdrop image, runtime, genres, collection strip, similar titles. Several files of the same movie are grouped under "Versions".
- **Series:** episode titles, descriptions and images from TMDb. A progress bar and a "Watched" mark per episode. Episodes of the same series in different folders are merged.
- **Player:**
  - Files the browser can't open (mkv, avi, ts, VOB) are transcoded live and played straight away.
  - Audio track selection (dubbed / original).
  - Subtitle sources: local `.srt/.vtt/.ass`, subtitles embedded in mkv, OpenSubtitles search, loading from a file, or drag and drop.
  - Subtitle size, background and sync (±0.5 s) are adjustable.
  - Playback resumes where you left off, and the next episode starts automatically after a countdown.
  - Playback speed, keyboard shortcuts and full screen.
- **Online:** movies and series that aren't in your library. The list and search come from TMDb, and playback streams from the internet through frameXTV's player (nothing is downloaded). Resume, Continue Watching and My List work for online titles too. Titles you already have are marked "KÜTÜPHANEDE" (in library). The catalog and posters are stored on the server, so devices without internet still see the list, posters and ratings (video needs internet). When the server can reach the internet it refreshes the catalog every 6 hours; without internet it retries every 10 minutes. The player address can be changed with `online_embed` in `secrets.json` or `HOMEFLIX_ONLINE_EMBED`.
- **My List and watch progress** are kept on the server. A movie you stop on your phone resumes where you left off on the computer.
- **Search:** instant search, opened with the `/` key. It ignores Turkish accents ("sirin" → "Şirin").

## Screenshots

![Recently Added and Collections rows](docs/screenshots/rows.jpg)

![Collections: sequels are grouped automatically](docs/screenshots/collections.jpg)

## Structure

```
app.py                 entry point (server + window)
homeflix/
  config.py            paths, API keys
  db.py                SQLite schema and migrations
  names.py             title / season / episode parsing from file names
  library.py           disk scan, Emby/Jellyfin .nfo files and posters
  metadata.py          TMDb/OMDb enrichment, collections, episode details
  media.py             ffprobe analysis, live streaming, image cache
  subtitles.py         local, embedded and online subtitles
  api.py               HTTP endpoints
templates/index.html   page skeleton and icons
static/app.css         design system
static/app.js          interface and player
data/                  database, posters, cache (copied from v1)
```

v1 (`../Homeflix_Linux`) is left as it is; v2 runs independently of it.

## License

Homeflix is free software, released under the [GNU General Public License v3.0](LICENSE). You may use, change and share it. If you distribute a changed version, you must share its source code under the same license.
