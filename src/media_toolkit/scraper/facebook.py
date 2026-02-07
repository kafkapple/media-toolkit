"""Facebook scraper using yt-dlp."""

import asyncio
import json
import re
from datetime import datetime
from typing import Optional

from .base import BaseScraper, ScrapeResult


class FacebookScraper(BaseScraper):
    """Scraper for Facebook posts using yt-dlp."""
    
    platform = "facebook"
    
    # URL patterns for Facebook
    URL_PATTERNS = [
        r'facebook\.com/share/[rv]/',
        r'facebook\.com/watch',
        r'facebook\.com/reel/',
        r'facebook\.com/.+/videos/',
        r'fb\.watch/',
    ]
    
    def supports(self, url: str) -> bool:
        """Check if URL is a Facebook URL."""
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in self.URL_PATTERNS)
    
    async def scrape(self, url: str) -> ScrapeResult:
        """
        Scrape Facebook post metadata using yt-dlp.
        
        Facebook scraping is more limited than Instagram.
        Many posts require authentication.
        """
        try:
            # Use yt-dlp to extract metadata
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                '--no-warnings',
                url,
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore').strip()
                
                # Check for private/login errors
                if any(x in error_msg.lower() for x in ['login', 'private', 'sign in']):
                    return ScrapeResult(
                        success=False,
                        url=url,
                        platform=self.platform,
                        error_message="Login required or private post",
                    )
                
                return ScrapeResult(
                    success=False,
                    url=url,
                    platform=self.platform,
                    error_message=f"yt-dlp failed: {error_msg[:200]}",
                )
            
            # Parse JSON output
            data = json.loads(stdout.decode('utf-8'))
            
            return self._parse_ytdlp_result(url, data)
            
        except asyncio.TimeoutError:
            return ScrapeResult(
                success=False,
                url=url,
                platform=self.platform,
                error_message=f"Timeout after {self.timeout}s",
            )
        except json.JSONDecodeError as e:
            return ScrapeResult(
                success=False,
                url=url,
                platform=self.platform,
                error_message=f"Invalid JSON: {e}",
            )
        except FileNotFoundError:
            return ScrapeResult(
                success=False,
                url=url,
                platform=self.platform,
                error_message="yt-dlp not installed",
            )
        except Exception as e:
            return ScrapeResult(
                success=False,
                url=url,
                platform=self.platform,
                error_message=str(e),
            )
    
    def _parse_ytdlp_result(self, url: str, data: dict) -> ScrapeResult:
        """Parse yt-dlp JSON output into ScrapeResult."""
        
        # Extract author
        author = data.get('uploader') or data.get('channel')
        author_url = data.get('uploader_url')
        
        # Extract content
        title = data.get('title')
        content = data.get('description')
        
        # Parse upload date
        posted_at = None
        upload_date = data.get('upload_date')
        if upload_date and len(upload_date) == 8:
            try:
                posted_at = datetime.strptime(upload_date, '%Y%m%d')
            except ValueError:
                pass
        
        if not posted_at:
            timestamp = data.get('timestamp')
            if timestamp:
                try:
                    posted_at = datetime.fromtimestamp(timestamp)
                except (ValueError, OSError):
                    pass
        
        # Extract metrics
        views = data.get('view_count')
        likes = data.get('like_count')
        comments = data.get('comment_count')
        shares = data.get('repost_count')
        
        # Extract media
        thumbnail_url = data.get('thumbnail')
        media_urls = []
        
        if 'url' in data:
            media_urls.append(data['url'])
        elif 'formats' in data and data['formats']:
            best = max(data['formats'], key=lambda f: f.get('height', 0) or 0)
            if 'url' in best:
                media_urls.append(best['url'])
        
        # Determine media type
        media_type = 'video'
        duration = data.get('duration')
        if not duration:
            media_type = 'image'
        
        return ScrapeResult(
            success=True,
            url=url,
            platform=self.platform,
            author=author,
            author_url=author_url,
            title=self._clean_text(title),
            content=self._clean_text(content),
            posted_at=posted_at,
            views=views,
            likes=likes,
            comments=comments,
            shares=shares,
            thumbnail_url=thumbnail_url,
            media_urls=media_urls,
            media_type=media_type,
        )
