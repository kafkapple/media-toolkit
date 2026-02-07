"""FastAPI web server for the viewer."""

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..storage import Database, Post, FilterOptions, Platform, Statistics
from ..storage.models import PostStatus
from ..parser import scan_directory, detect_duplicates
from ..validator import URLValidator, URLStatus
from ..scraper import scrape_url
from ..downloader import MediaDownloader


# Get module directory for templates
MODULE_DIR = Path(__file__).parent


class TagsUpdate(BaseModel):
    """Request body for updating tags."""
    tags: list[str]


class CategoryUpdate(BaseModel):
    """Request body for updating category."""
    category: Optional[str]


class NoteUpdate(BaseModel):
    """Request body for updating note."""
    note: Optional[str]


class ScanRequest(BaseModel):
    """Request body for scanning MD files."""
    source_dir: str
    file_pattern: str = "*.md"
    recursive: bool = True


class ProcessRequest(BaseModel):
    """Request body for processing URLs."""
    post_ids: Optional[list[str]] = None  # None means all pending


class DownloadBatchRequest(BaseModel):
    """Request body for batch download."""
    post_ids: list[str]


# Global state for background tasks
class TaskState:
    is_running: bool = False
    current_task: str = ""
    progress: int = 0
    total: int = 0
    message: str = ""
    errors: list[str] = []
    recent_posts: list[dict] = []  # Recently collected posts for live updates

task_state = TaskState()


def create_app(data_dir: Path, source_dir: Optional[Path] = None) -> FastAPI:
    """
    Create the FastAPI application.
    
    Args:
        data_dir: Path to the data directory
        source_dir: Default source directory for MD files
        
    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="Media Toolkit",
        description="Social media collection + general media download tool",
        version="0.2.0",
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize components
    db = Database(data_dir)
    
    @app.on_event("startup")
    async def startup_event():
        """Reindex database on startup."""
        print("Building database index...")
        count = db.reindex()
        print(f"Index rebuilt: {count} posts")
    downloader = MediaDownloader(
        media_dir=data_dir / "media",
        thumbnails_dir=data_dir / "thumbnails",
    )
    validator = URLValidator(timeout=10)
    
    # Mutable config state
    config_state = {
        "source_dir": source_dir or Path("/Users/joon/Documents/Obsidian/02_INBOX/_Hub/_Creative/GP"),
        "cookies_from_browser": "chrome",  # Use Chrome cookies by default
        "cookies_file": None,  # Optional: path to cookies.txt
    }
    
    # Mount static files
    static_dir = MODULE_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Mount data directories for media access
    media_dir = data_dir / "media"
    thumbnails_dir = data_dir / "thumbnails"
    
    # Ensure directories exist
    media_dir.mkdir(parents=True, exist_ok=True)
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    
    if media_dir.exists():
        app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")
    if thumbnails_dir.exists():
        app.mount("/thumbnails", StaticFiles(directory=str(thumbnails_dir)), name="thumbnails")
    
    # ==================== PAGE ROUTES ====================
    
    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve the main HTML page."""
        template_path = MODULE_DIR / "templates" / "index.html"
        if not template_path.exists():
            return HTMLResponse("<h1>Template not found</h1>", status_code=500)
        
        with open(template_path, 'r', encoding='utf-8') as f:
            return HTMLResponse(f.read())
    
    # ==================== POSTS API ====================
    
    @app.get("/api/posts")
    async def list_posts(
        platform: Optional[str] = None,
        status: Optional[str] = None,
        author: list[str] = Query(None),
        tag: Optional[str] = None,
        category: Optional[str] = None,
        media_type: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        sort_by: str = "scraped_at",
        sort_desc: bool = True,
    ):
        """List posts with optional filtering."""
        filters = FilterOptions(
            platforms=[Platform(platform)] if platform else None,
            statuses=[PostStatus(status)] if status else None,
            authors=author,
            tags=[tag] if tag else None,
            categories=[category] if category else None,
            media_types=[media_type] if media_type else None,
            search_query=search,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )
        
        posts = db.list_posts(filters)
        total = db.count()
        
        return {
            "posts": [post.model_dump() for post in posts],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    
    @app.get("/api/posts/{post_id}")
    async def get_post(post_id: str):
        """Get a single post by ID."""
        post = db.get_post(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        return post.model_dump()
    
    @app.delete("/api/posts/{post_id}")
    async def delete_post(post_id: str):
        """Delete a post."""
        if not db.delete_post(post_id):
            raise HTTPException(status_code=404, detail="Post not found")
        # Also delete media
        downloader.delete_media(post_id)
        return {"success": True}
    
    @app.patch("/api/posts/{post_id}/tags")
    async def update_tags(post_id: str, body: TagsUpdate):
        """Update tags for a post."""
        if not db.update_tags(post_id, body.tags):
            raise HTTPException(status_code=404, detail="Post not found")
        return {"success": True, "tags": body.tags}

    @app.patch("/api/posts/{post_id}/note")
    async def update_note(post_id: str, body: NoteUpdate):
        """Update note for a post."""
        post = db.get_post(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        post.note = body.note
        db.save_post(post)
        return {"success": True, "note": body.note}
    
    @app.patch("/api/posts/{post_id}/category")
    async def update_category(post_id: str, body: CategoryUpdate):
        """Update category for a post."""
        if not db.update_category(post_id, body.category):
            raise HTTPException(status_code=404, detail="Post not found")
        return {"success": True, "category": body.category}
    
    # ==================== STATS & FILTERS API ====================
    
    @app.get("/api/stats")
    async def get_stats():
        """Get collection statistics."""
        stats = db.get_stats()
        return stats.model_dump()
    
    @app.get("/api/analytics")
    async def get_analytics():
        """Get detailed analytics."""
        return db.get_analytics()
    
    @app.get("/api/filters")
    async def get_filter_options():
        """Get available filter options."""
        return {
            "platforms": [p.value for p in Platform],
            "statuses": [s.value for s in PostStatus],
            "authors": db.get_all_authors(),
            "tags": db.get_all_tags(),
            "categories": db.get_all_categories(),
        }
    
    @app.get("/api/thumbnail/{post_id}")
    async def get_thumbnail(post_id: str):
        """Get thumbnail for a post."""
        thumb_path = thumbnails_dir / f"{post_id}.jpg"
        if thumb_path.exists():
            return FileResponse(thumb_path)
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    
    # ==================== COLLECTION MANAGEMENT API ====================
    
    @app.get("/api/config")
    async def get_config():
        """Get current configuration."""
        return {
            "source_dir": str(config_state["source_dir"]),
            "data_dir": str(data_dir),
        }
    
    class ConfigUpdate(BaseModel):
        source_dir: str
    
    @app.post("/api/config")
    async def update_config(body: ConfigUpdate):
        """Update configuration."""
        new_path = Path(body.source_dir)
        if not new_path.exists():
            raise HTTPException(status_code=400, detail=f"Directory not found: {body.source_dir}")
        config_state["source_dir"] = new_path
        
        # Update cookie settings
        if hasattr(body, 'cookies_from_browser'):
            config_state["cookies_from_browser"] = body.cookies_from_browser
        if hasattr(body, 'cookies_file'):
            config_state["cookies_file"] = body.cookies_file
            
        return {"success": True, "source_dir": str(new_path)}

    class DeleteRequest(BaseModel):
        ids: list[str]

    def _delete_post_files(post_id: str):
        """Helper to delete files associated with a post."""
        post = db.get_post(post_id)
        if post:
            # Explicit paths
            if post.thumbnail_path:
                Path(post.thumbnail_path).unlink(missing_ok=True)
            for media_path in post.media_paths:
                Path(media_path).unlink(missing_ok=True)
        
        # Cleanup by convention
        (downloader.thumbnails_dir / f"{post_id}.jpg").unlink(missing_ok=True)
        for f in downloader.media_dir.glob(f"{post_id}.*"):
            f.unlink(missing_ok=True)

    @app.delete("/api/posts/{post_id}")
    async def delete_post(post_id: str):
        """Delete a single post and its files."""
        if not db.exists(post_id):
            raise HTTPException(status_code=404, detail="Post not found")
        
        _delete_post_files(post_id)
        db.delete_post(post_id)
        return {"success": True, "id": post_id}

    @app.delete("/api/posts")
    async def delete_posts(body: DeleteRequest):
        """Delete multiple posts."""
        deleted_count = 0
        errors = []
        
        for post_id in body.ids:
            try:
                if db.exists(post_id):
                    _delete_post_files(post_id)
                    db.delete_post(post_id)
                    deleted_count += 1
            except Exception as e:
                errors.append(f"{post_id}: {str(e)}")
        
        return {
            "success": True, 
            "deleted_count": deleted_count, 
            "errors": errors
        }

    @app.get("/api/posts/inaccessible")
    async def get_inaccessible_posts():
        """Get list of inaccessible (private/deleted) posts."""
        filters = FilterOptions(
            statuses=[PostStatus.PRIVATE, PostStatus.DELETED],
            limit=500,
        )
        posts = db.list_posts(filters)
        return [
            {
                "id": p.id,
                "url": p.url,
                "status": p.status,
                "platform": p.platform,
                "source_file": p.source_file,
                "error_message": p.error_message,
            }
            for p in posts
        ]
    
    @app.post("/api/scan")
    async def scan_urls(body: Optional[ScanRequest] = None):
        """
        Scan MD files and extract URLs.
        This creates pending posts for new URLs.
        """
        if task_state.is_running:
            raise HTTPException(status_code=409, detail="Another task is running")
            
        try:
            source = Path(body.source_dir) if body and body.source_dir else config_state["source_dir"]
            pattern = body.file_pattern if body else "*.md"
            recursive = body.recursive if body else True
            
            if not source.exists():
                raise HTTPException(status_code=400, detail=f"Source directory not found: {source}")
            
            # Scan for URLs
            collection = scan_directory(source, pattern=pattern, recursive=recursive)
            duplicates_report = detect_duplicates(collection.urls)
            unique_urls = collection.unique_urls()
            
            # Count new vs existing
            new_count = 0
            existing_count = 0
            
            for url_obj in unique_urls:
                if db.exists(url_obj.id):
                    existing_count += 1
                else:
                    new_count += 1
                    # Create pending post
                    post = Post(
                        id=url_obj.id,
                        url=url_obj.url,
                        platform=Platform(url_obj.platform),
                        status=PostStatus.PENDING,
                        source_file=str(url_obj.source_file),
                        source_context=url_obj.context,
                    )
                    db.save_post(post)
            
            # Get platform breakdown
            by_platform = {}
            for url_obj in unique_urls:
                by_platform[url_obj.platform] = by_platform.get(url_obj.platform, 0) + 1
                
            # Prepare duplicate list
            duplicate_items = []
            for url_id, urls in list(duplicates_report.duplicates.items())[:50]:
                if not urls: continue
                duplicate_items.append({
                    "url": urls[0].url,
                    "count": len(urls),
                    "files": [str(u.source_file) for u in urls]
                })
            
            return {
                "success": True,
                "source_dir": str(source),
                "files_scanned": len(collection.source_files),
                "total_urls": len(collection),
                "unique_urls": len(unique_urls),
                "new_urls": new_count,
                "existing_urls": existing_count,
                "duplicates": duplicates_report.total_duplicates,
                "duplicate_list": duplicate_items,
                "by_platform": by_platform,
            }
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")
    
    @app.get("/api/task/status")
    async def get_task_status():
        """Get current background task status."""
        # Get and clear recent posts
        recent = task_state.recent_posts[-10:]
        task_state.recent_posts = []
        
        return {
            "is_running": task_state.is_running,
            "current_task": task_state.current_task,
            "progress": task_state.progress,
            "total": task_state.total,
            "message": task_state.message,
            "errors": task_state.errors[-10:],
            "recent_posts": recent,  # New posts collected since last check
        }
    
    @app.post("/api/validate")
    async def validate_urls(background_tasks: BackgroundTasks, body: Optional[ProcessRequest] = None):
        """
        Validate pending URLs to check accessibility.
        Runs in background.
        """
        if task_state.is_running:
            raise HTTPException(status_code=409, detail="Another task is running")
        
        # Get posts to validate
        if body and body.post_ids:
            posts = [db.get_post(pid) for pid in body.post_ids if db.get_post(pid)]
        else:
            # Get all pending posts
            filters = FilterOptions(statuses=[PostStatus.PENDING], limit=500)
            posts = db.list_posts(filters)
        
        if not posts:
            return {"success": True, "message": "No posts to validate", "count": 0}
        
        async def validate_task():
            task_state.is_running = True
            task_state.current_task = "Validating URLs"
            task_state.progress = 0
            task_state.total = len(posts)
            task_state.errors = []
            
            try:
                for i, post in enumerate(posts):
                    task_state.progress = i + 1
                    task_state.message = f"Validating {post.url[:50]}..."
                    
                    try:
                        result = await validator.validate(post.url)
                        
                        # Map validation result to post status
                        status_map = {
                            URLStatus.ACCESSIBLE: PostStatus.ACCESSIBLE,
                            URLStatus.PRIVATE: PostStatus.PRIVATE,
                            URLStatus.LOGIN_REQUIRED: PostStatus.PRIVATE,
                            URLStatus.DELETED: PostStatus.DELETED,
                        }
                        
                        post.status = status_map.get(result.status, PostStatus.FAILED)
                        post.validated_at = datetime.now()
                        post.error_message = result.error_message
                        db.save_post(post)
                        
                    except Exception as e:
                        task_state.errors.append(f"{post.id}: {str(e)}")
                    
                    await asyncio.sleep(0.5)  # Rate limiting
                    
            finally:
                task_state.is_running = False
                task_state.message = "Validation complete"
        
        background_tasks.add_task(validate_task)
        
        return {
            "success": True,
            "message": f"Validation started for {len(posts)} posts",
            "count": len(posts),
        }
    
    @app.post("/api/scrape")
    async def scrape_posts(background_tasks: BackgroundTasks, body: Optional[ProcessRequest] = None):
        """
        Scrape metadata for accessible URLs.
        Runs in background.
        """
        if task_state.is_running:
            raise HTTPException(status_code=409, detail="Another task is running")
        
        # Get posts to scrape
        if body and body.post_ids:
            posts = [db.get_post(pid) for pid in body.post_ids if db.get_post(pid)]
        else:
            # Get accessible posts without scraped data
            filters = FilterOptions(statuses=[PostStatus.ACCESSIBLE], limit=500)
            posts = [p for p in db.list_posts(filters) if not p.scraped_at]
        
        if not posts:
            return {"success": True, "message": "No posts to scrape", "count": 0}
        
        async def scrape_task():
            task_state.is_running = True
            task_state.current_task = "Scraping metadata"
            task_state.progress = 0
            task_state.total = len(posts)
            task_state.errors = []
            
            try:
                for i, post in enumerate(posts):
                    task_state.progress = i + 1
                    task_state.message = f"Scraping {post.url[:50]}..."
                    
                    try:
                        result = await scrape_url(
                            post.url, 
                            timeout=30,
                            cookies_from_browser=config_state.get("cookies_from_browser"),
                            cookies_file=config_state.get("cookies_file"),
                        )
                        
                        if result.success:
                            post.author = result.author
                            post.author_url = result.author_url
                            post.title = result.title
                            post.content = result.content
                            post.posted_at = result.posted_at
                            post.views = result.views
                            post.likes = result.likes
                            post.comments = result.comments
                            post.shares = result.shares
                            post.thumbnail_url = result.thumbnail_url
                            post.media_urls = result.media_urls
                            post.media_type = result.media_type
                            post.scraped_at = datetime.now()
                            
                            # Download thumbnail
                            if result.thumbnail_url:
                                thumb_path = await downloader.download_thumbnail_only(
                                    post.url, post.id, cookies_from_browser=config_state.get('cookies_from_browser')
                                )
                                if thumb_path:
                                    post.thumbnail_path = thumb_path
                            
                            # Add to recent posts for live UI update
                            task_state.recent_posts.append({
                                "id": post.id,
                                "url": post.url,
                                "platform": post.platform,
                                "author": post.author,
                                "content": post.content[:100] if post.content else None,
                                "views": post.views,
                                "likes": post.likes,
                                "thumbnail_path": post.thumbnail_path,
                            })
                        else:
                            post.error_message = result.error_message
                        
                        db.save_post(post)
                        
                    except Exception as e:
                        task_state.errors.append(f"{post.id}: {str(e)}")
                    
                    await asyncio.sleep(1.0)  # Rate limiting
                    
            finally:
                task_state.is_running = False
                task_state.message = "Scraping complete"
        
        background_tasks.add_task(scrape_task)
        
        return {
            "success": True,
            "message": f"Scraping started for {len(posts)} posts",
            "count": len(posts),
        }
    
    @app.post("/api/open/{post_id}")
    async def open_media_folder(post_id: str):
        """Open the folder containing the post media."""
        import subprocess
        import sys
        
        post = db.get_post(post_id)
        if not post or not post.media_paths:
            # Fallback to opening media root if no file
            folder = downloader.media_dir
        else:
            # Open the folder of the first media file
            folder = Path(post.media_paths[0]).parent
            
        if not folder.exists():
             raise HTTPException(status_code=404, detail="Folder not found")
             
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(folder)])
            elif sys.platform == "win32":
                os.startfile(str(folder))
            else:
                subprocess.run(["xdg-open", str(folder)])
            return {"success": True, "message": "Folder opened"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/download/{post_id}")
    async def download_media(post_id: str, background_tasks: BackgroundTasks):
        """Download media for a specific post."""
        post = db.get_post(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        if post.media_paths:
            return {"success": True, "message": "Media already downloaded", "paths": post.media_paths}
        
        async def download_task():
            try:
                result = await downloader.download(post.url, post.id, media_urls=post.media_urls, cookies_from_browser=config_state.get('cookies_from_browser'), author=post.author)
                if result.success:
                    post.media_paths = result.media_paths
                    if result.thumbnail_path:
                        post.thumbnail_path = result.thumbnail_path
                    db.save_post(post)
            except Exception as e:
                pass  # Silently fail for individual downloads
        
        background_tasks.add_task(download_task)
        
        return {"success": True, "message": "Download started"}
    
    @app.post("/api/download-batch")
    async def download_batch(body: DownloadBatchRequest, background_tasks: BackgroundTasks):
        """Download media for specific posts."""
        if task_state.is_running:
            raise HTTPException(status_code=409, detail="Another task is running")
        
        # Filter posts that need download
        posts = []
        for pid in body.post_ids:
            post = db.get_post(pid)
            if post and not post.media_paths:
                posts.append(post)
        
        if not posts:
            return {"success": True, "message": "No media to download", "count": 0}
        
        async def download_batch_task():
            task_state.is_running = True
            task_state.current_task = "Batch Downloading"
            task_state.progress = 0
            task_state.total = len(posts)
            task_state.errors = []
            
            try:
                for i, post in enumerate(posts):
                    task_state.progress = i + 1
                    task_state.message = f"Downloading {post.id}..."
                    
                    try:
                        result = await downloader.download(post.url, post.id, media_urls=post.media_urls, cookies_from_browser=config_state.get('cookies_from_browser'), author=post.author)
                        if result.success:
                            post.media_paths = result.media_paths
                            if result.thumbnail_path:
                                post.thumbnail_path = result.thumbnail_path
                            db.save_post(post)
                    except Exception as e:
                        task_state.errors.append(f"{post.id}: {str(e)}")
                    
                    await asyncio.sleep(0.5)
            finally:
                task_state.is_running = False
                task_state.message = "Batch download complete"
        
        background_tasks.add_task(download_batch_task)
        return {"success": True, "message": f"Batch download started for {len(posts)} posts", "count": len(posts)}

    @app.post("/api/reindex")
    async def reindex_db():
        """Rebuild database index."""
        count = db.reindex()
        return {"success": True, "message": f"Re-indexed {count} posts", "count": count}

    @app.post("/api/download-all")
    async def download_all_media(background_tasks: BackgroundTasks):
        """Download media for all accessible posts without media."""
        if task_state.is_running:
            raise HTTPException(status_code=409, detail="Another task is running")
        
        filters = FilterOptions(statuses=[PostStatus.ACCESSIBLE], limit=500)
        posts = [p for p in db.list_posts(filters) if not p.media_paths]
        
        if not posts:
            return {"success": True, "message": "No media to download", "count": 0}
        
        async def download_all_task():
            task_state.is_running = True
            task_state.current_task = "Downloading media"
            task_state.progress = 0
            task_state.total = len(posts)
            task_state.errors = []
            
            try:
                for i, post in enumerate(posts):
                    task_state.progress = i + 1
                    task_state.message = f"Downloading {post.id}..."
                    
                    try:
                        result = await downloader.download(post.url, post.id, media_urls=post.media_urls, cookies_from_browser=config_state.get('cookies_from_browser'), author=post.author)
                        if result.success:
                            post.media_paths = result.media_paths
                            if result.thumbnail_path:
                                post.thumbnail_path = result.thumbnail_path
                            db.save_post(post)
                    except Exception as e:
                        task_state.errors.append(f"{post.id}: {str(e)}")
                    
                    await asyncio.sleep(0.5)
                    
            finally:
                task_state.is_running = False
                task_state.message = "Download complete"
        
        background_tasks.add_task(download_all_task)
        
        return {
            "success": True,
            "message": f"Download started for {len(posts)} posts",
            "count": len(posts),
        }
    
    @app.post("/api/process-all")
    async def process_all(background_tasks: BackgroundTasks):
        """
        Run full pipeline: scan -> validate -> scrape -> download thumbnails.
        """
        if task_state.is_running:
            raise HTTPException(status_code=409, detail="Another task is running")
        
        async def full_pipeline():
            task_state.is_running = True
            task_state.errors = []
            
            try:
                # Step 1: Scan
                task_state.current_task = "Scanning MD files"
                task_state.message = "Scanning for URLs..."
                
                collection = scan_directory(config_state["source_dir"], pattern="*.md", recursive=True)
                unique_urls = collection.unique_urls()
                
                new_posts = []
                for url_obj in unique_urls:
                    if not db.exists(url_obj.id):
                        post = Post(
                            id=url_obj.id,
                            url=url_obj.url,
                            platform=Platform(url_obj.platform),
                            status=PostStatus.PENDING,
                            source_file=str(url_obj.source_file),
                            source_context=url_obj.context,
                        )
                        db.save_post(post)
                        new_posts.append(post)
                
                # Step 2: Validate new posts
                task_state.current_task = "Validating URLs"
                task_state.total = len(new_posts)
                
                for i, post in enumerate(new_posts):
                    task_state.progress = i + 1
                    task_state.message = f"Validating {i+1}/{len(new_posts)}..."
                    
                    try:
                        result = await validator.validate(post.url)
                        status_map = {
                            URLStatus.ACCESSIBLE: PostStatus.ACCESSIBLE,
                            URLStatus.PRIVATE: PostStatus.PRIVATE,
                            URLStatus.LOGIN_REQUIRED: PostStatus.PRIVATE,
                            URLStatus.DELETED: PostStatus.DELETED,
                        }
                        post.status = status_map.get(result.status, PostStatus.FAILED)
                        post.validated_at = datetime.now()
                        db.save_post(post)
                    except Exception as e:
                        task_state.errors.append(f"Validate {post.id}: {e}")
                    
                    await asyncio.sleep(0.5)
                
                # Step 3: Scrape accessible posts
                accessible = [p for p in new_posts if p.status == PostStatus.ACCESSIBLE]
                task_state.current_task = "Scraping metadata"
                task_state.total = len(accessible)
                
                for i, post in enumerate(accessible):
                    task_state.progress = i + 1
                    task_state.message = f"Scraping {i+1}/{len(accessible)}..."
                    
                    try:
                        result = await scrape_url(post.url, timeout=30)
                        if result.success:
                            post.author = result.author
                            post.content = result.content
                            post.posted_at = result.posted_at
                            post.views = result.views
                            post.likes = result.likes
                            post.thumbnail_url = result.thumbnail_url
                            post.media_urls = result.media_urls
                            post.scraped_at = datetime.now()
                            
                            # Download thumbnail
                            thumb = await downloader.download_thumbnail_only(post.url, post.id)
                            if thumb:
                                post.thumbnail_path = thumb
                        
                        db.save_post(post)
                    except Exception as e:
                        task_state.errors.append(f"Scrape {post.id}: {e}")
                    
                    await asyncio.sleep(1.0)
                
                task_state.message = f"Complete: {len(new_posts)} new, {len(accessible)} scraped"
                
            finally:
                task_state.is_running = False
        
        background_tasks.add_task(full_pipeline)
        
        return {"success": True, "message": "Full pipeline started"}
    
    return app


def run_server(
    data_dir: Path,
    host: str = "localhost",
    port: int = 8080,
    debug: bool = False,
    source_dir: Optional[Path] = None,
):
    """
    Run the viewer server.
    
    Args:
        data_dir: Path to data directory
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode
        source_dir: Default source directory for MD files
    """
    import uvicorn
    
    app = create_app(data_dir, source_dir)
    uvicorn.run(app, host=host, port=port, reload=debug)

