"""Instagram scraper using yt-dlp."""

import asyncio
import json
import subprocess
import re
from datetime import datetime
from typing import Optional

from .base import BaseScraper, ScrapeResult


class InstagramScraper(BaseScraper):
    """Scraper for Instagram posts using yt-dlp."""
    
    platform = "instagram"
    
    # URL patterns for Instagram
    URL_PATTERNS = [
        r'instagram\.com/p/',
        r'instagram\.com/reel/',
        r'instagram\.com/stories/',
        r'instagram\.com/tv/',
    ]
    
    def supports(self, url: str) -> bool:
        """Check if URL is an Instagram URL."""
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in self.URL_PATTERNS)
    
    async def scrape(self, url: str) -> ScrapeResult:
        """
        Scrape Instagram post metadata using yt-dlp.
        
        yt-dlp can extract metadata from Instagram without authentication
        for public posts. Private posts will fail.
        """
        try:
            # Use yt-dlp to extract metadata (JSON only, no download)
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--no-download',
                '--no-warnings',
            ]
            # Add cookie authentication if configured
            cmd.extend(self._get_cookie_args())
            cmd.append(url)
            
            # Run yt-dlp asynchronously
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
                
                # Check for specific error types
                if 'login' in error_msg.lower() or 'private' in error_msg.lower():
                    return ScrapeResult(
                        success=False,
                        url=url,
                        platform=self.platform,
                        error_message="Private or login required",
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
                error_message=f"Invalid JSON response: {e}",
            )
        except FileNotFoundError:
            return ScrapeResult(
                success=False,
                url=url,
                platform=self.platform,
                error_message="yt-dlp not installed. Run: pip install yt-dlp",
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
        author_url = data.get('uploader_url') or data.get('channel_url')
        
        # Extract content
        title = data.get('title')
        content = data.get('description')
        
        # Parse upload date
        posted_at = None
        upload_date = data.get('upload_date')  # Format: YYYYMMDD
        if upload_date and len(upload_date) == 8:
            try:
                posted_at = datetime.strptime(upload_date, '%Y%m%d')
            except ValueError:
                pass
        
        # Also try timestamp
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
        
        # Extract media URLs
        thumbnail_url = data.get('thumbnail')
        media_urls = []
        
        # Get the best format URL
        if 'url' in data:
            media_urls.append(data['url'])
        elif 'formats' in data:
            # Get the best quality format
            formats = data['formats']
            if formats:
                best = max(formats, key=lambda f: f.get('height', 0) or 0)
                if 'url' in best:
                    media_urls.append(best['url'])
        
        # Determine media type
        media_type = 'video'  # Instagram reels/videos
        if '/p/' in url and not data.get('duration'):
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
            thumbnail_url=thumbnail_url,
            media_urls=media_urls,
            media_type=media_type,
        )
