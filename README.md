# ChordLift

Upload an MP3, get a timestamped chord sheet with key detection, BPM, standard notation, and Nashville Number System (NNS). Client-side transposition, PDF/TXT export, and optional session history.

## Quick start (local)

```bash
# 1. Clone and set up environment
cp .env.example .env
# Edit .env — set SECRET_KEY at minimum

# 2. Install dependencies (Python 3.11 recommended)
pip install -r requirements.txt

# 3. Run
python wsgi.py
# → http://localhost:5000
```

## Docker

```bash
cp .env.example .env
docker-compose up --build
# → http://localhost:5000
```

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Flask session secret — **change this in production** | `dev-secret-key` |
| `DATABASE_URL` | SQLAlchemy DB URL | `sqlite:///chordlift.db` |
| `MAX_UPLOAD_MB` | Upload size limit in MB | `10` |
| `ACOUSTID_API_KEY` | Free key from [acoustid.org](https://acoustid.org/login) — enables song fingerprinting | *(empty — skipped gracefully)* |

## AcoustID setup (song fingerprinting)

1. Register at https://acoustid.org/login (free)
2. Create an application to get an API key
3. Add it to `.env` as `ACOUSTID_API_KEY=your_key`

Without it, the app still works — song title/artist just shows as "Unknown".

## Deploy to Render

1. Push to a GitHub repo
2. Create a new **Web Service** on [render.com](https://render.com)
3. Set runtime to **Docker**
4. Add environment variables in the Render dashboard
5. **Important:** Use the **Standard plan (~$25/mo)** if you want vocal separation (`demucs` needs ~2GB RAM). The Starter plan (512MB) will work for everything else.

## Deploy to Railway

```bash
railway login
railway init
railway up
# Set env vars in Railway dashboard
```

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

Tests cover chord recognition, NNS conversion, transposition, key estimation, and the notes→chords pipeline. No audio file required.

## Architecture notes

- **Processing is async** — upload returns a `job_id` immediately; frontend polls `/status/<job_id>` every 3s
- **Transposition is client-side** — the server never reprocesses audio for a key change
- **Vocal separation is optional** — uses Meta's `demucs htdemucs` model; ~60–120s extra processing time; requires ~2GB RAM
- **Chord detection pipeline:** `basic-pitch` (Spotify) → MIDI → pitch-class clustering → chord name matching using interval templates
