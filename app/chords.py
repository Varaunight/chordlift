"""
Chord logic: pitch-class → chord name, NNS conversion, transposition.
"""

from __future__ import annotations

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTE_INDEX = {n: i for i, n in enumerate(NOTE_NAMES)}

# Enharmonic aliases → normalise to sharps
_ENHARMONIC = {
    "Db": "C#", "Eb": "D#", "Fb": "E", "Gb": "F#",
    "Ab": "G#", "Bb": "A#", "Cb": "B",
}

# ---------------------------------------------------------------------------
# Pitch-class set → chord name
# ---------------------------------------------------------------------------

# Intervals from root (as frozenset of pitch-class offsets) → chord quality suffix
_CHORD_TEMPLATES: list[tuple[frozenset, str]] = [
    # Triads
    (frozenset({0, 4, 7}),  ""),       # Major
    (frozenset({0, 3, 7}),  "m"),      # Minor
    (frozenset({0, 4, 8}),  "aug"),    # Augmented
    (frozenset({0, 3, 6}),  "dim"),    # Diminished
    # 7ths
    (frozenset({0, 4, 7, 10}), "7"),   # Dominant 7
    (frozenset({0, 4, 7, 11}), "maj7"),# Major 7
    (frozenset({0, 3, 7, 10}), "m7"),  # Minor 7
    (frozenset({0, 3, 6, 10}), "m7b5"),# Half-diminished
    (frozenset({0, 3, 6, 9}),  "dim7"),# Diminished 7
    # Sus
    (frozenset({0, 5, 7}),  "sus4"),
    (frozenset({0, 2, 7}),  "sus2"),
]


def notes_to_chord_name(pitch_classes: set[int]) -> str | None:
    """
    Given a set of pitch classes (0–11), return the best-matching chord name
    (e.g. "Am", "G7") or None if no decent match found.
    """
    if len(pitch_classes) < 2:
        return None

    best_name = None
    best_matched = 0

    for root_pc in pitch_classes:
        # Normalise intervals relative to this root
        intervals = frozenset((pc - root_pc) % 12 for pc in pitch_classes)
        for template, suffix in _CHORD_TEMPLATES:
            matched = len(intervals & template)
            coverage = matched / len(template)
            if coverage >= 0.75 and matched > best_matched:
                best_matched = matched
                best_name = NOTE_NAMES[root_pc] + suffix

    return best_name


# ---------------------------------------------------------------------------
# Time formatting
# ---------------------------------------------------------------------------

def format_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


# ---------------------------------------------------------------------------
# NNS conversion
# ---------------------------------------------------------------------------

# Scale degrees for major and minor keys (intervals from root)
_MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
_MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]

# NNS numeral labels (1-indexed)
_NNS_NUMERALS = ["1", "2", "3", "4", "5", "6", "7"]


def _parse_key(key_str: str) -> tuple[int, bool]:
    """Return (root_pitch_class, is_minor)."""
    key_str = key_str.strip()
    is_minor = key_str.endswith("m")
    root_str = key_str.rstrip("m")
    root_str = _ENHARMONIC.get(root_str, root_str)
    root_pc = NOTE_INDEX.get(root_str, 0)
    return root_pc, is_minor


def _parse_chord(chord_str: str) -> tuple[int, str]:
    """Return (root_pitch_class, quality_suffix)."""
    # Extract root note (1 or 2 chars) + quality
    if len(chord_str) >= 2 and chord_str[1] in ("#", "b"):
        root_str = chord_str[:2]
        quality = chord_str[2:]
    else:
        root_str = chord_str[:1]
        quality = chord_str[1:]
    root_str = _ENHARMONIC.get(root_str, root_str)
    root_pc = NOTE_INDEX.get(root_str, 0)
    return root_pc, quality


def chord_to_nns(chord_str: str, key_str: str) -> str:
    """Convert a chord name to its NNS numeral given the key."""
    key_root, is_minor = _parse_key(key_str)
    chord_root, quality = _parse_chord(chord_str)

    scale = _MINOR_SCALE if is_minor else _MAJOR_SCALE
    interval = (chord_root - key_root) % 12

    # Find closest scale degree
    best_numeral = None
    best_dist = 999
    for i, degree in enumerate(scale):
        dist = abs(interval - degree)
        if dist < best_dist:
            best_dist = dist
            degree_interval = degree
            best_numeral = _NNS_NUMERALS[i]

    if best_numeral is None:
        return "?"

    # Flat/sharp modifier
    diff = interval - degree_interval
    prefix = ""
    if diff == -1 or diff == 11:
        prefix = "b"
    elif diff == 1 or diff == -11:
        prefix = "#"

    # Quality suffix: minor chords get lowercase-style suffix in NNS
    nns_suffix = ""
    if quality.startswith("m") and not quality.startswith("maj"):
        nns_suffix = "m"
    elif quality in ("dim", "dim7"):
        nns_suffix = "°"
    elif quality in ("aug",):
        nns_suffix = "+"
    elif "7" in quality:
        nns_suffix = "7" if "maj" not in quality else "△7"

    return f"{prefix}{best_numeral}{nns_suffix}"


# ---------------------------------------------------------------------------
# Transposition
# ---------------------------------------------------------------------------

def transpose_chord(chord_str: str, semitones: int) -> str:
    """Shift a chord name by `semitones` (can be negative)."""
    if not chord_str or chord_str == "N/A":
        return chord_str
    root_pc, quality = _parse_chord(chord_str)
    new_root = (root_pc + semitones) % 12
    return NOTE_NAMES[new_root] + quality


def transpose_key(key_str: str, semitones: int) -> str:
    """Shift a key string by `semitones`."""
    root_pc, is_minor = _parse_key(key_str)
    new_root = (root_pc + semitones) % 12
    return NOTE_NAMES[new_root] + ("m" if is_minor else "")


# ---------------------------------------------------------------------------
# Build the final chord list (step 4)
# ---------------------------------------------------------------------------

def build_chord_list(raw_chords: list[dict], key: str) -> list[dict]:
    """
    Enrich raw chord events with formatted time and NNS numeral.
    raw_chords: [{ time_seconds, chord }]
    Returns:   [{ time, time_seconds, chord, nns }]
    """
    result = []
    for item in raw_chords:
        t = item["time_seconds"]
        chord = item["chord"]
        result.append({
            "time": format_time(t),
            "time_seconds": t,
            "chord": chord,
            "nns": chord_to_nns(chord, key) if key else "?",
        })
    return result
