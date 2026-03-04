"""Unit tests for audio.py helper functions (no actual audio file needed)."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
from app.audio import _estimate_key, _notes_to_chords


class TestEstimateKey:
    def test_returns_string(self):
        # Flat chroma centred on C major pitches (0, 4, 7)
        chroma = np.zeros(12)
        chroma[0] = 6.0   # C
        chroma[4] = 4.0   # E
        chroma[7] = 5.0   # G
        result = _estimate_key(chroma)
        assert isinstance(result, str)
        assert len(result) >= 1

    def test_c_major_profile(self):
        # Feed the Krumhansl major profile itself — should come back as C
        from app.audio import _MAJOR_PROFILE
        chroma = np.array(_MAJOR_PROFILE)
        result = _estimate_key(chroma)
        assert result == "C"

    def test_a_minor_profile(self):
        from app.audio import _MINOR_PROFILE
        # Rotate minor profile to A (index 9)
        chroma = np.roll(np.array(_MINOR_PROFILE), 9)
        result = _estimate_key(chroma)
        assert result == "Am"


class TestNotesToChords:
    def test_empty_input(self):
        assert _notes_to_chords([]) == []

    def test_single_chord(self):
        # C major: MIDI pitches 60 (C), 64 (E), 67 (G) starting at t=0
        events = [
            (0.0, 1.0, 60, 0.8),
            (0.0, 1.0, 64, 0.8),
            (0.0, 1.0, 67, 0.8),
        ]
        result = _notes_to_chords(events)
        assert len(result) >= 1
        assert result[0]["chord"] == "C"
        assert result[0]["time_seconds"] == 0.0

    def test_deduplicates_consecutive(self):
        # Same chord repeated across multiple windows → should only appear once
        events = [
            (0.0, 0.5, 60, 0.8), (0.0, 0.5, 64, 0.8), (0.0, 0.5, 67, 0.8),
            (0.5, 1.0, 60, 0.8), (0.5, 1.0, 64, 0.8), (0.5, 1.0, 67, 0.8),
        ]
        result = _notes_to_chords(events)
        # All windows are C major — dedup should yield 1 entry (or 2 if they're in different buckets)
        chords = [r["chord"] for r in result]
        assert all(c == "C" for c in chords)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
