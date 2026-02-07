"""Threads scraper for Meta's Threads platform."""

import re
from datetime import datetime
from typing import Optional
import aiohttp

from .base import BaseScraper, ScrapeResult


class ThreadsScraper(BaseScraper):
    """Scraper for Threads posts."""
    
    platform = "threads"
    
    # URL patterns for Threads
    URL_PATTERNS = [
        r'threads\.net/@[\w.]+/post/[\w-]+',
        r'threads\.net/t/[\w-]+',
    ]
    
    def supports(self, url: str) -> bool:
        """Check if URL is a Threads post."""
        return any(re.search(pattern, url) for pattern in self.URL_PATTERNS)
    
    async def scrape(self, url: str) -> ScrapeResult:
        """Scrape metadata from a Threads post."""
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
        """Parse Threads HTML for metadata."""
        # Extract author from URL
        author_match = re.search(r'threads\.net/@([\w.]+)', url)
        author = f"@{author_match.group(1)}" if author_match else None
        
        # Try to extract from meta tags
        title = self._extract_meta(html, 'og:title')
        content = self._extract_meta(html, 'og:description')
        thumbnail = self._extract_meta(html, 'og:image')
        
        # Try to parse likes/replies from content
        likes = None
        comments = None
        
        likes_match = re.search(r'"likeCount":\s*(\d+)', html)
        if likes_match:
            likes = int(likes_match.group(1))
        
        replies_match = re.search(r'"replyCount":\s*(\d+)', html)
        if replies_match:
            comments = int(replies_match.group(1))
        
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
        pattern = rf'<meta[^>]+property="{property_name}"[^>]+content="([^"]*)"'
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Try alternate format
        pattern = rf'<meta[^>]+content="([^"]*)"[^>]+property="{property_name}"'
        match = re.search(pattern, html, re.IGNORECASE)
        return match.group(1) if match else None
