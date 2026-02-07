"""General-purpose media download manager (from media_downloader)."""

import requests
import yt_dlp
from typing import List, Callable, Optional
from ..extractor.base import MediaItem
from pathlib import Path
from fake_useragent import UserAgent


class DownloadManager:
    def __init__(self, save_dir: str, cookies_browser: Optional[str] = None):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.ua = UserAgent()
        self.cookies_browser = cookies_browser

    def download_items(self, items: List[MediaItem], progress_callback: Optional[Callable[[str], None]] = None):
        total = len(items)
        for idx, item in enumerate(items):
            try:
                if progress_callback:
                    progress_callback(f"Downloading {idx+1}/{total}: {item.title}")

                if item.type == 'video':
                    self._download_video(item)
                elif item.type == 'image':
                    self._download_image(item)

            except Exception as e:
                print(f"Failed to download {item.title}: {e}")

    def _download_video(self, item: MediaItem):
        # For video, we delegate to yt-dlp again to download
        ydl_opts = {
            'outtmpl': str(self.save_dir / '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
        }

        if self.cookies_browser:
            ydl_opts['cookiesfrombrowser'] = (self.cookies_browser, )

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([item.url])

    def _download_image(self, item: MediaItem):
        headers = {'User-Agent': self.ua.random}
        response = requests.get(item.url, headers=headers, stream=True)
        response.raise_for_status()

        # Determine filename
        filename = item.title
        if not filename or len(filename) > 50:
            filename = item.url.split('/')[-1]
            if '?' in filename:
                filename = filename.split('?')[0]

        # Ensure extension
        if '.' not in filename:
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                filename += '.jpg'
            elif 'png' in content_type:
                filename += '.png'
            elif 'gif' in content_type:
                filename += '.gif'
            else:
                 filename += '.jpg' # Default

        # Clean filename
        filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in " ._-()"]).rstrip()
        filepath = self.save_dir / filename

        # Avoid overwrite
        counter = 1
        original_filepath = filepath
        while filepath.exists():
            filepath = original_filepath.with_name(f"{original_filepath.stem}_{counter}{original_filepath.suffix}")
            counter += 1

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
