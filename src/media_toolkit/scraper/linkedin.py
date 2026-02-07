"""LinkedIn scraper for LinkedIn posts."""

import re
from datetime import datetime
from typing import Optional
import aiohttp

from .base import BaseScraper, ScrapeResult


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn posts."""
    
    platform = "linkedin"
    
    # URL patterns for LinkedIn
    URL_PATTERNS = [
        r'linkedin\.com/posts/',
        r'linkedin\.com/feed/update/',
        r'linkedin\.com/pulse/',
        r'linkedin\.com/video/',
    ]
    
    def supports(self, url: str) -> bool:
        """Check if URL is a LinkedIn post."""
        return any(re.search(pattern, url) for pattern in self.URL_PATTERNS)
    
    async def scrape(self, url: str) -> ScrapeResult:
        """Scrape metadata from a LinkedIn post."""
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=self.timeout) as response:
                    if response.status != 200:
                        return ScrapeResult(
                            success=False,
                            url=url,
                            platform=self.platform,
                            error_message=f"HTTP {response.status}",
                        )
                    
                    html = await response.text()
            
            # Extract data from HTML
            result = self._parse_html(html, url)
            return result
            
        except aiohttp.ClientError as e:
            return ScrapeResult(
                success=False,
                url=url,
                platform=self.platform,
                error_message=f"Network error: {str(e)}",
            )
        except Exception as e:
            return ScrapeResult(
                success=False,
                url=url,
                platform=self.platform,
                error_message=str(e),
            )
    
    def _parse_html(self, html: str, url: str) -> ScrapeResult:
        """Parse LinkedIn HTML for metadata."""
        # Extract from Open Graph meta tags
        title = self._extract_meta(html, 'og:title')
        content = self._extract_meta(html, 'og:description')
        thumbnail = self._extract_meta(html, 'og:image')
        
        # Try to extract author from title or page
        author = None
        if title:
            # LinkedIn titles often format as "Author Name on LinkedIn: content..."
            author_match = re.match(r'^(.+?) on LinkedIn', title)
            if author_match:
                author = author_match.group(1)
        
        # Try to extract from article:author
        if not author:
            author = self._extract_meta(html, 'article:author')
        
        # Try to extract reactions count
        likes = None
        reactions_match = re.search(r'"numLikes":\s*(\d+)', html)
        if reactions_match:
            likes = int(reactions_match.group(1))
        
        # Comments
        comments = None
        comments_match = re.search(r'"numComments":\s*(\d+)', html)
        if comments_match:
            comments = int(comments_match.group(1))
        
        return ScrapeResult(
            success=True,
            url=url,
            platform=self.platform,
            author=author,
            title=self._clean_text(title),
            content=self._clean_text(content),
            likes=likes,
            comments=comments,
            thumbnail_url=thumbnail,
        )
    
    def _extract_meta(self, html: str, property_name: str) -> Optional[str]:
        """Extract content from meta tag."""
        # Try property attribute
        pattern = rf'<meta[^>]+property="{property_name}"[^>]+content="([^"]*)"'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Try alternate format
        pattern = rf'<meta[^>]+content="([^"]*)"[^>]+property="{property_name}"'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Try name attribute (LinkedIn sometimes uses this)
        pattern = rf'<meta[^>]+name="{property_name}"[^>]+content="([^"]*)"'
        match = re.search(pattern, html, re.IGNORECASE)
        return match.group(1) if match else None
