"""
Tests for the subtitle_burner module.
"""

import tempfile
from pathlib import Path

from pipeline.models import TranscriptWord
from pipeline.subtitle_burner import (
    _escape_ass_text,
    _seconds_to_ass_time,
    _seconds_to_srt_time,
    generate_ass_subtitle,
    generate_srt_subtitle,
)


class TestTimeConversions:
    def test_ass_time_format(self):
        assert _seconds_to_ass_time(0) == "0:00:00.00"
        assert _seconds_to_ass_time(61.5) == "0:01:01.50"
        assert _seconds_to_ass_time(3661.25) == "1:01:01.25"

    def test_srt_time_format(self):
        assert _seconds_to_srt_time(0) == "00:00:00,000"
        assert _seconds_to_srt_time(61.5) == "00:01:01,500"
        assert _seconds_to_srt_time(3661.25) == "01:01:01,250"


class TestEscapeAssText:
    def test_curly_braces_escaped(self):
        assert "\\{" in _escape_ass_text("{test}")

    def test_normal_text_unchanged(self):
        assert _escape_ass_text("Hello world") == "Hello world"

    def test_backslash_escaped(self):
        assert _escape_ass_text("a\\b") == "a\\\\b"


class TestGenerateAssSubtitle:
    def test_generates_file(self):
        words = [
            TranscriptWord(start=0.0, end=0.5, word="Hello"),
            TranscriptWord(start=0.5, end=1.0, word="world"),
            TranscriptWord(start=1.0, end=1.5, word="test"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "test.ass")
            result = generate_ass_subtitle(words, path)
            assert Path(result).exists()
            content = Path(result).read_text()
            assert "[Script Info]" in content
            assert "Dialogue:" in content

    def test_highlight_mode(self):
        words = [
            TranscriptWord(start=0.0, end=0.5, word="Hello"),
            TranscriptWord(start=0.5, end=1.0, word="world"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "highlight.ass")
            generate_ass_subtitle(words, path, highlight_words=True)
            content = Path(path).read_text()
            assert "\\kf" in content  # Karaoke fill tag


class TestGenerateSrtSubtitle:
    def test_generates_srt(self):
        words = [
            TranscriptWord(start=0.0, end=0.5, word="Hello"),
            TranscriptWord(start=0.5, end=1.0, word="world"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "test.srt")
            result = generate_srt_subtitle(words, path, words_per_group=2)
            assert Path(result).exists()
            content = Path(result).read_text()
            assert "-->" in content
            assert "Hello world" in content
