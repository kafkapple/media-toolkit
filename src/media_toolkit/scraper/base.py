"""Base scraper interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ScrapeResult:
    """Result of scraping a URL."""
    
    success: bool
    url: str
    
    # Author info
    author: Optional[str] = None
    author_url: Optional[str] = None
    
    # Content
    title: Optional[str] = None
    content: Optional[str] = None
    posted_at: Optional[datetime] = None
    
    # Metrics
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    
    # Media
    thumbnail_url: Optional[str] = None
    media_urls: list[str] = field(default_factory=list)
    media_type: Optional[str] = None  # video, image, carousel
    
    # Metadata
    platform: str = "unknown"
    scraped_at: datetime = field(default_factory=datetime.now)
    
    # Error info
    error_message: Optional[str] = None


class BaseScraper(ABC):
    """Abstract base class for social media scrapers."""
    
    platform: str = "unknown"
    
    def __init__(
        self,
        timeout: int = 30,
        user_agent: Optional[str] = None,
        cookies_from_browser: Optional[str] = None,  # e.g., "chrome", "firefox"
        cookies_file: Optional[str] = None,  # Path to cookies.txt
    ):
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.cookies_from_browser = cookies_from_browser
        self.cookies_file = cookies_file
    
    def _get_cookie_args(self) -> list[str]:
        """Get yt-dlp cookie arguments."""
        args = []
        if self.cookies_from_browser:
            args.extend(['--cookies-from-browser', self.cookies_from_browser])
        elif self.cookies_file:
            args.extend(['--cookies', self.cookies_file])
        return args
    
    @abstractmethod
    def supports(self, url: str) -> bool:
        """
        Check if this scraper supports the given URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if this scraper can handle the URL
        """
        pass
    
    @abstractmethod
    async def scrape(self, url: str) -> ScrapeResult:
        """
        Scrape metadata from a URL.
        
        Args:
            url: URL to scrape
            
        Returns:
            ScrapeResult with extracted data
        """
        pass
    
    def _clean_text(self, text: Optional[str]) -> Optional[str]:
        """Clean and normalize text content."""
        if not text:
            return None
        # Remove excessive whitespace
        text = ' '.join(text.split())
        return text.strip() if text else None
    
    def _parse_count(self, text: Optional[str]) -> Optional[int]:
        """Parse a count string like '1.2K' or '3M' to integer."""
        if not text:
            return None
        
        text = text.strip().upper().replace(',', '')
        
        try:
            if 'K' in text:
                return int(float(text.replace('K', '')) * 1000)
            elif 'M' in text:
                return int(float(text.replace('M', '')) * 1000000)
            elif 'B' in text:
                return int(float(text.replace('B', '')) * 1000000000)
            else:
                return int(text)
        except (ValueError, TypeError):
            return None
