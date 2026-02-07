"""Media downloader using yt-dlp."""

import asyncio
import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable
from PIL import Image
import aiohttp


@dataclass
class DownloadResult:
    """Result of a media download operation."""
    
    success: bool
    url: str
    post_id: str
    
    # Paths to downloaded files
    media_paths: list[str] = field(default_factory=list)
    thumbnail_path: Optional[str] = None
    
    # Metadata
    total_size_bytes: int = 0
    duration_seconds: Optional[float] = None
    
    # Error info
    error_message: Optional[str] = None
    
    downloaded_at: datetime = field(default_factory=datetime.now)


class MediaDownloader:
    """Downloads media from social media posts using yt-dlp."""
    
    def __init__(
        self,
        media_dir: Path,
        thumbnails_dir: Path,
        thumbnail_size: tuple[int, int] = (200, 200),
    ):
        """
        Initialize the downloader.
        
        Args:
            media_dir: Directory to save downloaded media
            thumbnails_dir: Directory to save thumbnails
            thumbnail_size: Size for thumbnails (width, height)
        """
        self.media_dir = Path(media_dir)
        self.thumbnails_dir = Path(thumbnails_dir)
        self.thumbnail_size = thumbnail_size
        
        # Ensure directories exist
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)
    
    async def download(
        self,
        url: str,
        post_id: str,
        media_urls: Optional[list[str]] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        cookies_from_browser: Optional[str] = None,
        author: Optional[str] = None,
    ) -> DownloadResult:
        """
        Download media from a URL.
        
        Args:
            url: URL to download from
            post_id: Unique ID for naming the file
            progress_callback: Optional callback for progress updates (0-100)
            
        Returns:
            DownloadResult with paths to downloaded files
        """
        # Create author directory
        author_clean = self._sanitize_filename(author or "unknown")
        author_dir = self.media_dir / author_clean
        author_dir.mkdir(parents=True, exist_ok=True)
        
        # Save as author/title-id.ext
        # Note: id is unique, title adds context
        output_template = str(author_dir / f"%(title).100s-%(id)s.%(ext)s")
        
        cmd = [
            'yt-dlp',
            '--no-warnings',
            '--no-playlist',
            '-o', output_template,
            '--write-thumbnail',
            '--convert-thumbnails', 'jpg',
            url,
        ]
        
        if cookies_from_browser:
            cmd.extend(['--cookies-from-browser', cookies_from_browser])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore').strip()
                return DownloadResult(
                    success=False,
                    url=url,
                    post_id=post_id,
                    error_message=f"yt-dlp failed: {error_msg[:200]}",
                )
            
            # Find downloaded files
            media_paths = []
            thumbnail_path = None
            total_size = 0
            
            for file in self.media_dir.glob(f"{post_id}.*"):
                file_size = file.stat().st_size
                total_size += file_size
                
                # Check if it's a thumbnail
                if file.suffix.lower() in ['.jpg', '.jpeg', '.webp', '.png']:
                    # Move to thumbnails dir and resize
                    thumb_dest = self.thumbnails_dir / f"{post_id}.jpg"
                    thumbnail_path = await self._process_thumbnail(file, thumb_dest)
                else:
                    media_paths.append(str(file))
            
            if not media_paths and not thumbnail_path:
                return DownloadResult(
                    success=False,
                    url=url,
                    post_id=post_id,
                    error_message="No files downloaded",
                )
            
            return DownloadResult(
                success=True,
                url=url,
                post_id=post_id,
                media_paths=media_paths,
                thumbnail_path=thumbnail_path,
                total_size_bytes=total_size,
            )
            
        except FileNotFoundError:
            return DownloadResult(
                success=False,
                url=url,
                post_id=post_id,
                error_message="yt-dlp not installed",
            )
        except Exception as e:
            # Try fallback if media_urls provided
            if media_urls:
                try:
                    downloaded_paths = []
                    async with aiohttp.ClientSession() as session:
                        for i, media_url in enumerate(media_urls):
                            ext = "jpg"  # Default to jpg for images
                            if "mp4" in media_url: ext = "mp4"
                            
                            filename = f"{post_id}_{i}.{ext}" if len(media_urls) > 1 else f"{post_id}.{ext}"
                            dest = self.media_dir / filename
                            
                            async with session.get(media_url) as response:
                                if response.status == 200:
                                    with open(dest, 'wb') as f:
                                        while True:
                                            chunk = await response.content.read(1024)
                                            if not chunk:
                                                break
                                            f.write(chunk)
                                    downloaded_paths.append(str(dest))
                    
                    if downloaded_paths:
                        return DownloadResult(
                            success=True,
                            url=url,
                            post_id=post_id,
                            media_paths=downloaded_paths,
                            total_size_bytes=sum(os.path.getsize(p) for p in downloaded_paths),
                        )
                except Exception as fallback_error:
                    return DownloadResult(
                        success=False,
                        url=url,
                        post_id=post_id,
                        error_message=f"Both yt-dlp and fallback failed: {str(e)} | {str(fallback_error)}",
                    )

            return DownloadResult(
                success=False,
                url=url,
                post_id=post_id,
                error_message=str(e),
            )
    
    async def _process_thumbnail(self, source: Path, dest: Path) -> Optional[str]:
        """
        Process and resize a thumbnail image.
        
        Args:
            source: Source image path
            dest: Destination path
            
        Returns:
            Path to processed thumbnail or None on failure
        """
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._resize_image, source, dest)
            
            # Remove original if different from dest
            if source != dest and source.exists():
                source.unlink()
            
            return str(dest) if dest.exists() else None
            
        except Exception:
            # If processing fails, try simple copy
            try:
                shutil.copy2(source, dest)
                if source != dest:
                    source.unlink()
                return str(dest)
            except Exception:
                return None
    
    def _resize_image(self, source: Path, dest: Path) -> None:
        """Resize an image to thumbnail size."""
        with Image.open(source) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize maintaining aspect ratio
            img.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
            
            # Save as JPEG
            img.save(dest, 'JPEG', quality=85)
    
    async def download_thumbnail_only(
        self,
        url: str,
        post_id: str,
        cookies_from_browser: Optional[str] = None,
    ) -> Optional[str]:
        """
        Download only the thumbnail from a URL.
        
        Args:
            url: URL to get thumbnail from
            post_id: Unique ID for naming
            
        Returns:
            Path to thumbnail or None
        """
        output_template = str(self.thumbnails_dir / f"{post_id}.%(ext)s")
        
        cmd = [
            'yt-dlp',
            '--no-warnings',
            '--skip-download',
            '--write-thumbnail',
            '--convert-thumbnails', 'jpg',
            '-o', output_template,
            url,
        ]
        
        if cookies_from_browser:
            cmd.extend(['--cookies-from-browser', cookies_from_browser])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            await process.communicate()
            
            # Find the thumbnail
            for ext in ['jpg', 'jpeg', 'webp', 'png']:
                thumb_path = self.thumbnails_dir / f"{post_id}.{ext}"
                if thumb_path.exists():
                    # Resize if needed
                    final_path = self.thumbnails_dir / f"{post_id}.jpg"
                    if thumb_path != final_path:
                        await self._process_thumbnail(thumb_path, final_path)
                        return str(final_path)
                    return str(thumb_path)
            
            return None
            
        except Exception:
            return None
    
    def get_thumbnail(self, post_id: str) -> Optional[Path]:
        """
        Get the cached thumbnail path for a post.
        
        Args:
            post_id: Post ID
            
        Returns:
            Path to thumbnail or None if not exists
        """
        thumb_path = self.thumbnails_dir / f"{post_id}.jpg"
        return thumb_path if thumb_path.exists() else None
    
    def get_media_files(self, post_id: str) -> list[Path]:
        """
        Get all media files for a post.
        
        Args:
            post_id: Post ID
            
        Returns:
            List of paths to media files
        """
        files = []
        for file in self.media_dir.glob(f"{post_id}.*"):
            # Exclude thumbnails
            if file.suffix.lower() not in ['.jpg', '.jpeg', '.webp', '.png']:
                files.append(file)
        return files
    
    def delete_media(self, post_id: str) -> bool:
        """
        Delete all media files for a post.
        
        Args:
            post_id: Post ID
            
        Returns:
            True if any files were deleted
        """
        deleted = False
        
        # Delete media files
        for file in self.media_dir.glob(f"{post_id}.*"):
            file.unlink()
            deleted = True
        
        # Delete thumbnail
        thumb_path = self.thumbnails_dir / f"{post_id}.jpg"
        if thumb_path.exists():
            thumb_path.unlink()
            deleted = True
        
        return deleted
