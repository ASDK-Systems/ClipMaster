"""
Tests for the downloader module.
"""

import pytest

from pipeline.downloader import DownloadError, _validate_url


class TestValidateUrl:
    def test_valid_youtube_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert _validate_url(url) == url

    def test_valid_short_url(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert _validate_url(url) == url

    def test_strips_whitespace(self):
        url = "  https://www.youtube.com/watch?v=test  "
        assert _validate_url(url) == "https://www.youtube.com/watch?v=test"

    def test_invalid_url_raises(self):
        with pytest.raises(DownloadError, match="Invalid YouTube URL"):
            _validate_url("https://www.example.com/video")

    def test_empty_url_raises(self):
        with pytest.raises(DownloadError, match="Invalid YouTube URL"):
            _validate_url("")

    def test_non_youtube_video_site_raises(self):
        with pytest.raises(DownloadError):
            _validate_url("https://vimeo.com/123456")
