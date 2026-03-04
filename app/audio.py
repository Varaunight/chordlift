"""
Audio processing pipeline.

Order of execution:
  0. (Optional) Vocal separation via demucs
  1. Song identification via pyacoustid + MusicBrainz
  2. Key + BPM detection via librosa
  3. Chord detection via basic-pitch → MIDI → chord names
  4. NNS conversion (delegated to chords.py)
"""

import os
import logging
import tempfile
import subprocess

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def process_audio(filepath: str, *, separate_vocals: bool = False, job_id: str = None, jobs: dict = None) -> dict:
    """Run the full pipeline and return a result dict."""

    def update_stage(stage: str):
        if job_id and jobs and job_id in jobs:
            jobs[job_id]["stage"] = stage

    audio_path = filepath

    # Step 0 — Vocal separation
    if separate_vocals:
        update_stage("Separating instruments…")
        try:
            audio_path = _separate_vocals(filepath)
        except Exception as e:
            logger.warning("demucs failed, falling back to original audio: %s", e)
            audio_path = filepath

    # Step 1 — Song identification
    update_stage("Identifying song…")
    title, artist = _identify_song(audio_path)

    # Step 2 — Key + BPM
    update_stage("Detecting key and BPM…")
    key, bpm = _detect_key_bpm(audio_path)

    # Step 3 — Chord detection
    update_stage("Detecting chords…")
    raw_chords = _detect_chords(audio_path)

    # Step 4 — NNS conversion
    update_stage("Generating chord sheet…")
    from app.chords import build_chord_list
    chords = build_chord_list(raw_chords, key)

    # Clean up demucs output if we made a temp file
    if audio_path != filepath:
        try:
            os.unlink(audio_path)
        except OSError:
            pass

    return {
        "title": title,
        "artist": artist,
        "key": key,
        "bpm": round(bpm, 1) if bpm else None,
        "chords": chords,
    }


# ---------------------------------------------------------------------------
# Step 0 — Vocal separation
# ---------------------------------------------------------------------------

def _separate_vocals(filepath: str) -> str:
    """Run demucs htdemucs and return path to the no_vocals stem."""
    out_dir = tempfile.mkdtemp()
    subprocess.run(
        ["python", "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", out_dir, filepath],
        check=True,
        capture_output=True,
    )
    # demucs outputs to: out_dir/htdemucs/<track_name>/no_vocals.wav
    base = os.path.splitext(os.path.basename(filepath))[0]
    no_vocals = os.path.join(out_dir, "htdemucs", base, "no_vocals.wav")
    if not os.path.exists(no_vocals):
        raise FileNotFoundError(f"demucs output not found: {no_vocals}")
    return no_vocals


# ---------------------------------------------------------------------------
# Step 1 — Song identification
# ---------------------------------------------------------------------------

def _identify_song(filepath: str):
    """Return (title, artist) or (None, None) if identification fails."""
    try:
        import acoustid
        import musicbrainzngs

        musicbrainzngs.set_useragent("ChordLift", "1.0", "https://github.com/chordlift")

        api_key = os.getenv("ACOUSTID_API_KEY", "")
        if not api_key:
            return None, None

        results = acoustid.match(api_key, filepath)
        for score, recording_id, title, artist in results:
            if score > 0.5 and title:
                return title, artist
    except Exception as e:
        logger.info("Song identification failed (non-fatal): %s", e)
    return None, None


# ---------------------------------------------------------------------------
# Step 2 — Key + BPM detection
# ---------------------------------------------------------------------------

def _detect_key_bpm(filepath: str):
    """Return (key_str, bpm_float) using librosa."""
    import librosa
    import numpy as np

    y, sr = librosa.load(filepath, sr=None, mono=True)

    # BPM
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo)

    # Key estimation via chroma + Krumhansl–Schmuckler profiles
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)

    key_str = _estimate_key(chroma_mean)
    return key_str, bpm


# Krumhansl–Schmuckler key profiles
_MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _estimate_key(chroma_mean):
    import numpy as np

    best_score = -999
    best_key = "C"

    for i, note in enumerate(_NOTE_NAMES):
        rotated = np.roll(chroma_mean, -i)
        maj_score = float(np.corrcoef(rotated, _MAJOR_PROFILE)[0, 1])
        min_score = float(np.corrcoef(rotated, _MINOR_PROFILE)[0, 1])
        if maj_score > best_score:
            best_score = maj_score
            best_key = note
        if min_score > best_score:
            best_score = min_score
            best_key = f"{note}m"

    return best_key


# ---------------------------------------------------------------------------
# Step 3 — Chord detection via basic-pitch
# ---------------------------------------------------------------------------

def _detect_chords(filepath: str) -> list:
    """
    Run basic-pitch to get MIDI, then cluster simultaneous notes into chord names.
    Returns list of { time_seconds: float, chord: str }.
    """
    import numpy as np
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    model_output, midi_data, note_events = predict(filepath)

    # note_events: list of (start_time, end_time, pitch, amplitude, ...)
    # Group notes that overlap in time into chord "frames"
    chords = _notes_to_chords(note_events)
    return chords


def _notes_to_chords(note_events) -> list:
    """
    Cluster note events into chords by grouping notes with overlapping time windows.
    Uses a simple beat-grid quantisation: 0.5s windows.
    """
    from app.chords import notes_to_chord_name

    if not note_events:
        return []

    WINDOW = 0.5  # seconds

    # Build time-bucketed note groups
    buckets = {}
    for event in note_events:
        start = event[0]
        pitch = int(event[2])
        bucket_key = round(start / WINDOW) * WINDOW
        buckets.setdefault(bucket_key, set()).add(pitch % 12)  # pitch class only

    result = []
    prev_chord = None
    for t in sorted(buckets):
        pitch_classes = buckets[t]
        chord_name = notes_to_chord_name(pitch_classes)
        if chord_name and chord_name != prev_chord:
            result.append({"time_seconds": t, "chord": chord_name})
            prev_chord = chord_name

    return result
