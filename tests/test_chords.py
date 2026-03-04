"""Unit tests for chord logic — no audio processing required."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.chords import (
    notes_to_chord_name,
    chord_to_nns,
    transpose_chord,
    transpose_key,
    format_time,
    build_chord_list,
)


# ---------------------------------------------------------------------------
# notes_to_chord_name
# ---------------------------------------------------------------------------

class TestNotesToChordName:
    def test_c_major(self):
        # C=0, E=4, G=7
        assert notes_to_chord_name({0, 4, 7}) == "C"

    def test_a_minor(self):
        # A=9, C=0, E=4
        assert notes_to_chord_name({9, 0, 4}) == "Am"

    def test_g_major(self):
        # G=7, B=11, D=2
        assert notes_to_chord_name({7, 11, 2}) == "G"

    def test_too_few_notes(self):
        assert notes_to_chord_name({0}) is None

    def test_dominant_seventh(self):
        # G7: G=7, B=11, D=2, F=5
        result = notes_to_chord_name({7, 11, 2, 5})
        assert result == "G7"


# ---------------------------------------------------------------------------
# chord_to_nns
# ---------------------------------------------------------------------------

class TestChordToNns:
    def test_tonic(self):
        assert chord_to_nns("C", "C") == "1"

    def test_four_chord(self):
        assert chord_to_nns("F", "C") == "4"

    def test_five_chord(self):
        assert chord_to_nns("G", "C") == "5"

    def test_minor_two(self):
        assert chord_to_nns("Dm", "C") == "2m"

    def test_minor_key_one(self):
        assert chord_to_nns("Am", "Am") == "1m"

    def test_minor_key_three(self):
        # In Am, C major is the 3 chord
        assert chord_to_nns("C", "Am") == "3"

    def test_flat_six(self):
        # In E major, C is b6
        result = chord_to_nns("C", "E")
        assert "b" in result or "6" in result


# ---------------------------------------------------------------------------
# transpose_chord
# ---------------------------------------------------------------------------

class TestTransposeChord:
    def test_up_two_semitones(self):
        assert transpose_chord("C", 2) == "D"

    def test_down_semitone(self):
        assert transpose_chord("D", -1) == "C#"

    def test_wraps_around(self):
        assert transpose_chord("B", 1) == "C"

    def test_preserves_quality(self):
        assert transpose_chord("Am", 3) == "Cm"

    def test_seventh_preserved(self):
        assert transpose_chord("G7", 2) == "A7"

    def test_zero_semitones(self):
        assert transpose_chord("Em", 0) == "Em"


# ---------------------------------------------------------------------------
# transpose_key
# ---------------------------------------------------------------------------

class TestTransposeKey:
    def test_major_up(self):
        assert transpose_key("C", 2) == "D"

    def test_minor_preserved(self):
        assert transpose_key("Am", 3) == "Cm"

    def test_wraps(self):
        assert transpose_key("B", 1) == "C"


# ---------------------------------------------------------------------------
# format_time
# ---------------------------------------------------------------------------

class TestFormatTime:
    def test_zero(self):
        assert format_time(0) == "0:00"

    def test_one_minute(self):
        assert format_time(60) == "1:00"

    def test_padding(self):
        assert format_time(65) == "1:05"

    def test_long_track(self):
        assert format_time(215) == "3:35"


# ---------------------------------------------------------------------------
# build_chord_list
# ---------------------------------------------------------------------------

class TestBuildChordList:
    def test_full_pipeline(self):
        raw = [
            {"time_seconds": 0.0, "chord": "Em"},
            {"time_seconds": 8.0, "chord": "Am"},
            {"time_seconds": 16.0, "chord": "B7"},
        ]
        result = build_chord_list(raw, "Em")
        assert len(result) == 3
        assert result[0]["time"] == "0:00"
        assert result[0]["chord"] == "Em"
        assert result[0]["nns"] == "1m"
        assert result[1]["chord"] == "Am"
        assert result[2]["chord"] == "B7"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
