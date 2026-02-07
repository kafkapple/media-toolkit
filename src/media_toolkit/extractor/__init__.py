"""Media extraction module - extract media items from URLs."""

from typing import List
from .base import MediaExtractor, MediaItem
from .video import YouTubeExtractor
from .web_image import WebImageExtractor

def get_all_extractors() -> List[MediaExtractor]:
    return [
        YouTubeExtractor(),
        WebImageExtractor() # Generic fallback
    ]

def extract_media(url: str, cookies_browser: str = None) -> tuple[list, list]:
    """Extract media items from a URL using available extractors.

    Returns:
        (items, logs) - list of MediaItem and list of error/info messages
    """
    extractors = get_all_extractors()
    logs = []

    for extractor in extractors:
        if extractor.is_supported(url):
            try:
                # Check if extractor supports cookies
                if hasattr(extractor.extract, '__code__') and 'cookies_browser' in extractor.extract.__code__.co_varnames:
                     items = extractor.extract(url, cookies_browser=cookies_browser)
                else:
                     items = extractor.extract(url)

                if items:
                    return items, []
                else:
                    logs.append(f"{extractor.__class__.__name__}: Found 0 items.")
            except Exception as e:
                logs.append(f"{extractor.__class__.__name__} failed: {str(e)}")

    return [], logs

__all__ = [
    "MediaExtractor",
    "MediaItem",
    "YouTubeExtractor",
    "WebImageExtractor",
    "get_all_extractors",
    "extract_media",
]
