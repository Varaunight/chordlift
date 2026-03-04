# ChordLift — Project Specification
> Hand this document to Claude Code and execute top to bottom.

---

## Overview

A web application for musicians that accepts an MP3 file and returns a formatted chord sheet with timestamps, detected key, and both standard and Nashville Number System (NNS) notation. Includes transposition, PDF/TXT export, and session-based history.

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python 3.11 + Flask | Natural fit for audio ML libraries |
| Chord detection | `basic-pitch` (Spotify) | Best free accuracy for MP3 → chords |
| Audio analysis | `librosa` | Key detection, BPM, timestamps |
| Song fingerprinting | `pyacoustid` + MusicBrainz | Identify known songs for metadata |
| PDF generation | `WeasyPrint` | Style with CSS, cleaner than ReportLab |
| Frontend | Single HTML file (vanilla JS) | No build step, drag-and-drop UI |
| Auth / sessions | Flask-Login + Flask-Session | Lightweight, no need for full auth service |
| Database | SQLite (via SQLAlchemy) | Simple, file-based, no infra needed |
| Vocal separation | `demucs` (Meta) | Optional pre-processing to isolate instrumentals |
| Hosting | Render.com or Railway | Docker-based deploy, ~$5-10/mo |
| Containerisation | Docker + docker-compose | Consistent local and prod environment |

---

## Project Structure

```
chordlift/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── routes.py            # All route handlers
│   ├── audio.py             # Audio processing pipeline
│   ├── chords.py            # Chord extraction + NNS conversion
│   ├── export.py            # PDF and TXT generation
│   ├── models.py            # SQLAlchemy models
│   ├── static/
│   │   └── main.js          # Frontend JS (drag-drop, transpose, download)
│   └── templates/
│       └── index.html       # Single page UI
├── tests/
│   ├── test_audio.py
│   └── test_chords.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Feature Specification

### 1. File Upload
- Drag-and-drop zone OR click-to-browse on the main page
- Accept `.mp3` only
- Max file size: **10MB** — reject with a clear error message if exceeded
- Show file name and size after selection, before processing begins
- Upload triggers processing immediately on confirmation

### 2. Audio Processing Pipeline (`audio.py`)

Execute in this order:

**Step 0 — Vocal separation (optional, user-toggled)**
- If the user has checked "Separate instruments before analysis" in the UI, run `demucs` on the MP3 first
- Use the `htdemucs` model (best quality, ships with `demucs`)
- Extract the `no_vocals` stem and use that audio for all subsequent steps instead of the original
- If demucs fails for any reason, log the error and fall back to the original audio silently — do not block processing
- Add ~60–120s to expected processing time when enabled; reflect this in the UI progress messaging

**Step 1 — Song identification (optional, best-effort)**
- Use `pyacoustid` to fingerprint the audio
- Query MusicBrainz for title + artist
- If no match found, label as "Unknown Track" — do not block processing

**Step 2 — Key and BPM detection**
- Use `librosa.load()` to load the audio
- Use `librosa.feature.chroma_cqt()` + key estimation for detected key
- Use `librosa.beat.beat_track()` for BPM
- Return: `{ key: "Em", bpm: 100 }`

**Step 3 — Chord detection**
- Run `basic-pitch` on the MP3 to produce a MIDI representation
- Extract chord events from MIDI note clusters (quantise to beat grid)
- Map MIDI note groups → chord names using a lookup/algorithm
- Return list of: `{ time_seconds: float, chord: str }` e.g. `{ time_seconds: 0.0, chord: "Em" }`

**Step 4 — NNS conversion**
- Given the detected key and a list of chords, convert each chord to its NNS numeral
- Support: 1–7, with maj/min/dom qualifiers (e.g. `4m`, `5`)
- Return parallel NNS list alongside standard chords

**Processing time note:** This pipeline will take 30–90 seconds for a typical 3–4 minute MP3. The UI must reflect this with a progress indicator.

### 3. Chord Sheet Format

```
╔══════════════════════════════════════════╗
  ChordLift
  Song:    Superstition (detected)
  Artist:  Stevie Wonder (detected)
  Key:     Em  |  BPM: 102
══════════════════════════════════════════╝

Time      Standard    NNS
────────────────────────────
0:00      Em          1
0:08      Am          4
0:16      B7          5
0:24      Em          1
0:32      C           6b
...
```

- Time format: `M:SS`
- Chords that repeat consecutively for a long stretch should show duration too (optional enhancement)
- Section headers (verse/chorus) are **not** in scope for v1

### 4. Transposition

- After a chord sheet is generated, show a **transpose control** in the UI
- UI: dropdown or +/- semitone buttons (range: -6 to +6 semitones)
- Transposition is **client-side only** — no server round-trip
- Re-renders the chord table in the browser instantly
- NNS numerals stay the same; only standard chord names change (and the displayed key updates)
- PDF/TXT export should reflect the currently transposed key

### 5. Export

**Plain text (`.txt`)**
- ASCII formatted version of the chord sheet
- Matches exactly what's shown on screen (including transposition)
- Filename: `[song-name]-chords.txt` or `track-chords.txt` if unknown

**PDF**
- Generated server-side via WeasyPrint from an HTML template
- Clean, readable font (suggest: monospace for chord table, sans-serif for header)
- Single page if possible; paginate gracefully if not
- Filename: `[song-name]-chords.pdf`
- POST the current chord state (including transposition) to `/export/pdf` to generate

### 6. Session History

- Users must create an account (email + password) to save history
- Flask-Login handles session management
- Each processed track is saved to SQLite with:
  - `id`, `user_id`, `filename`, `detected_title`, `detected_artist`, `key`, `bpm`, `chord_data` (JSON), `created_at`
- History page shows list of past tracks, click to reload chord sheet
- No account = can still use the app, but history is not saved (guest mode)
- Passwords hashed with `bcrypt`

### 7. UI Pages

| Route | Description |
|---|---|
| `/` | Main page — drag-drop upload, chord sheet display, transpose, export |
| `/login` | Email + password login |
| `/register` | Account creation |
| `/history` | List of saved chord sheets (logged-in users only) |
| `/history/<id>` | Load a saved chord sheet |
| `/export/pdf` | POST endpoint — accepts chord JSON, returns PDF file |

---

## API Endpoints

### `POST /upload`
- Accepts: `multipart/form-data` with `file` field
- Validates: MP3 only, max 10MB
- Returns: JSON
```json
{
  "job_id": "abc123",
  "status": "processing"
}
```

### `GET /status/<job_id>`
- Poll this every 3 seconds from the frontend
- Returns:
```json
{
  "status": "complete",
  "result": {
    "title": "Superstition",
    "artist": "Stevie Wonder",
    "key": "Em",
    "bpm": 102,
    "chords": [
      { "time": "0:00", "time_seconds": 0.0, "chord": "Em", "nns": "1" },
      { "time": "0:08", "time_seconds": 8.0, "chord": "Am", "nns": "4" }
    ]
  }
}
```
- Or `{ "status": "processing" }` while running
- Or `{ "status": "error", "message": "..." }` on failure

### `POST /export/pdf`
- Accepts JSON: `{ title, artist, key, bpm, chords[] }`
- Returns: PDF file as binary response

---

## Background Job Handling

- Audio processing must run in a background thread (not block the Flask request)
- Use Python's `threading` module or `concurrent.futures.ThreadPoolExecutor`
- Store job state in-memory (dict keyed by `job_id`) for v1 — no Redis needed at this scale
- `job_id` is a UUID generated at upload time

---

## Environment Variables (`.env`)

```
SECRET_KEY=changeme
DATABASE_URL=sqlite:///chordlift.db
MAX_UPLOAD_MB=10
ACOUSTID_API_KEY=your_key_here   # Free at acoustid.org
FLASK_ENV=production
```

---

## Docker Setup

**`Dockerfile`**
- Base image: `python:3.11-slim`
- Install system deps: `ffmpeg` (required by librosa), `libsndfile1`, WeasyPrint deps
- Copy app, install `requirements.txt`
- Expose port 5000
- CMD: `gunicorn -w 2 -b 0.0.0.0:5000 "app:create_app()"`

**`docker-compose.yml`**
- Single service: `web`
- Mount a volume for SQLite DB persistence
- Load `.env` file

---

## Requirements.txt (key packages)

```
flask
flask-login
flask-sqlalchemy
flask-session
flask-bcrypt
basic-pitch
librosa
pyacoustid
musicbrainzngs
weasyprint
gunicorn
python-dotenv
soundfile
demucs
```

---

## Build Order for Claude Code

Execute in this sequence to avoid circular dependency issues:

1. **Scaffold** — project structure, `__init__.py`, Flask app factory, config
2. **Models** — `User`, `Track` SQLAlchemy models, DB init
3. **Auth** — register, login, logout routes + templates
4. **Audio pipeline** — `audio.py` end to end, test with a sample MP3
5. **Chord logic** — `chords.py` NNS conversion, transposition math
6. **Routes** — upload, status polling, history endpoints
7. **Export** — PDF + TXT generation
8. **Frontend** — `index.html` + `main.js` (drag-drop, polling, transpose UI, download buttons)
9. **Docker** — Dockerfile + docker-compose
10. **Tests** — unit tests for chord conversion and transposition
11. **README** — setup instructions, Render/Railway deploy steps, AcoustID key setup

---

## Known Constraints & Notes

- **Vocal separation toggle:** Checkbox in the UI labelled *"Separate instruments before analysis (slower, may improve accuracy on vocal-heavy tracks)"*. Unchecked by default. When checked, `demucs` runs as Step 0 in the pipeline. The status polling response should include a `stage` field so the frontend can show contextual messages like "Separating instruments…" vs "Detecting chords…"
- **`demucs` RAM usage:** The `htdemucs` model requires ~2GB RAM at peak. Render's Starter plan ($7/mo) provides 512MB — **upgrade to the Standard plan (~$25/mo) if you want to use vocal separation reliably**, or warn the user that the feature may fail on low-memory deployments. Alternatively, gate the feature as "experimental" in the UI.
- **`basic-pitch` accuracy:** Works best on recordings where instruments are relatively isolated. Dense mixes may produce messier results — this is a fundamental limitation of the approach, not a bug.
- **AcoustID key:** Free API key required from acoustid.org — takes 2 minutes to get. Without it, song identification is skipped gracefully.
- **WeasyPrint system deps:** Needs `libpango`, `libcairo` etc. — these must be installed in the Dockerfile explicitly.
- **Processing time:** Do not set a short request timeout. The `/upload` endpoint returns immediately with a job ID; processing happens async.
- **Transposition is client-side:** The server never needs to reprocess audio for a key change. The frontend holds the original chord data and remaps it.

---

## Resume Description (suggested)

> **ChordLift** — Full-stack web app for musicians. Accepts MP3 audio and produces a timestamped chord sheet using Spotify's `basic-pitch` ML model for chord detection and `librosa` for key/BPM analysis. Optional vocal separation via Meta's `demucs` model isolates the instrumental before analysis. Features real-time client-side transposition, PDF export, song fingerprinting via AcoustID, and session-based history. Built with Python/Flask, deployed via Docker on Render.
