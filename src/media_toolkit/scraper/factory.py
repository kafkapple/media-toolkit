"""Scraper factory for selecting the appropriate scraper."""

from typing import Optional

from .base import BaseScraper, ScrapeResult
from .instagram import InstagramScraper
from .facebook import FacebookScraper
from .threads import ThreadsScraper
from .linkedin import LinkedInScraper


# Registry of available scrapers
_SCRAPERS: list[type[BaseScraper]] = [
    InstagramScraper,
    FacebookScraper,
    ThreadsScraper,
    LinkedInScraper,
]


def get_scraper(url: str, **kwargs) -> Optional[BaseScraper]:
    """
    Get the appropriate scraper for a URL.
    
    Args:
        url: URL to find scraper for
        **kwargs: Additional arguments passed to scraper constructor
        
    Returns:
        Scraper instance or None if no matching scraper
    """
    for scraper_class in _SCRAPERS:
        scraper = scraper_class(**kwargs)
        if scraper.supports(url):
            return scraper
    return None


async def scrape_url(url: str, **kwargs) -> ScrapeResult:
    """
    Convenience function to scrape a URL.
    
    Args:
        url: URL to scrape
        **kwargs: Additional arguments passed to scraper
        
    Returns:
        ScrapeResult with extracted data or error
    """
    scraper = get_scraper(url, **kwargs)
    
    if not scraper:
        return ScrapeResult(
            success=False,
            url=url,
            error_message=f"No scraper available for this URL type",
        )
    
    return await scraper.scrape(url)


def register_scraper(scraper_class: type[BaseScraper]) -> None:
    """
    Register a new scraper class.
    
    Args:
        scraper_class: Scraper class to register
    """
    if scraper_class not in _SCRAPERS:
        _SCRAPERS.append(scraper_class)


def list_supported_platforms() -> list[str]:
    """List all supported platforms."""
    platforms = set()
    for scraper_class in _SCRAPERS:
        platforms.add(scraper_class.platform)
    return sorted(platforms)
