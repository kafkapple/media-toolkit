"""Scraper module for extracting metadata from social media posts."""

from .base import BaseScraper, ScrapeResult
from .instagram import InstagramScraper
from .facebook import FacebookScraper
from .threads import ThreadsScraper
from .linkedin import LinkedInScraper
from .factory import get_scraper, scrape_url, list_supported_platforms

__all__ = [
    "BaseScraper",
    "ScrapeResult",
    "InstagramScraper",
    "FacebookScraper",
    "ThreadsScraper",
    "LinkedInScraper",
    "get_scraper",
    "scrape_url",
    "list_supported_platforms",
]

