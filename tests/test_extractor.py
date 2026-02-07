"""Tests for the extractor module."""

from media_toolkit.extractor.base import MediaItem, MediaExtractor
from media_toolkit.extractor.video import YouTubeExtractor
from media_toolkit.extractor.web_image import WebImageExtractor
from media_toolkit.extractor import get_all_extractors, extract_media


class TestMediaItem:
    """Tests for MediaItem dataclass."""

    def test_create_video_item(self):
        item = MediaItem(
            url="https://example.com/video.mp4",
            type="video",
            title="Test Video",
            file_size="10.00 MB",
        )
        assert item.url == "https://example.com/video.mp4"
        assert item.type == "video"
        assert item.title == "Test Video"
        assert item.thumbnail_url is None

    def test_create_image_item(self):
        item = MediaItem(
            url="https://example.com/image.jpg",
            type="image",
            thumbnail_url="https://example.com/image.jpg",
            title="Test Image",
            file_size="Unknown",
        )
        assert item.type == "image"
        assert item.thumbnail_url == item.url


class TestYouTubeExtractor:
    """Tests for YouTubeExtractor."""

    def test_is_supported_any_url(self):
        extractor = YouTubeExtractor()
        # yt-dlp supports any URL (returns True always)
        assert extractor.is_supported("https://www.youtube.com/watch?v=abc") is True
        assert extractor.is_supported("https://example.com") is True


class TestWebImageExtractor:
    """Tests for WebImageExtractor."""

    def test_is_supported_any_url(self):
        extractor = WebImageExtractor()
        # Fallback extractor - supports any URL
        assert extractor.is_supported("https://example.com") is True


class TestGetAllExtractors:
    """Tests for get_all_extractors."""

    def test_returns_extractors_in_order(self):
        extractors = get_all_extractors()
        assert len(extractors) == 2
        assert isinstance(extractors[0], YouTubeExtractor)
        assert isinstance(extractors[1], WebImageExtractor)

    def test_all_are_media_extractors(self):
        extractors = get_all_extractors()
        for ext in extractors:
            assert isinstance(ext, MediaExtractor)
