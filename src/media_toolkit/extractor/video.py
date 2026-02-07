import yt_dlp
from typing import List
from .base import MediaExtractor, MediaItem
from ..utils.formatting import human_readable_size

class YouTubeExtractor(MediaExtractor):
    def is_supported(self, url: str) -> bool:
        # We'll allow yt-dlp to try on any URL since it supports thousands of sites.
        # The extract method handles failures gracefully.
        return True

    def extract(self, url: str, cookies_browser: str = None) -> List[MediaItem]:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True, # Fast extraction for playlists
            'nocheckcertificate': True, # Sometimes helps with SSL issues
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
        }

        if cookies_browser:
            ydl_opts['cookiesfrombrowser'] = (cookies_browser, ) # Tuple required

        items = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)

                # Check if it's a playlist or single video
                if 'entries' in info:
                    entries = info['entries']
                else:
                    entries = [info]

                for entry in entries:
                    if not entry: continue

                    title = entry.get('title', 'Unknown Title')
                    original_url = entry.get('url', entry.get('webpage_url'))
                    thumbs = entry.get('thumbnails', [])
                    thumbnail = thumbs[-1]['url'] if thumbs else None

                    filesize = entry.get('filesize')
                    if filesize:
                        size_str = human_readable_size(filesize)
                    else:
                        size_str = "Calc upon download"

                    items.append(MediaItem(
                        url=original_url or url,
                        type='video',
                        thumbnail_url=thumbnail,
                        title=title,
                        file_size=size_str,
                        original_data=entry
                    ))
            except Exception as e:
                # Re-raise to be caught by the manager with the specific error
                raise Exception(f"yt-dlp processing failed: {str(e)}")

        return items
