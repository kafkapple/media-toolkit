"""JSON-based database for storing posts."""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from collections import defaultdict

from .models import Post, PostStatus, Platform, Statistics, FilterOptions
import frontmatter



class Database:
    """JSON file-based database for posts."""
    
    def __init__(self, data_dir: Path):
        """
        Initialize the database.
        
        Args:
            data_dir: Root directory for data storage
        """
        self.data_dir = Path(data_dir)
        self.posts_dir = self.data_dir / "posts"
        self.index_file = self.data_dir / "index.json"
        self.stats_file = self.data_dir / "stats.json"
        
        # Ensure directories exist
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory index for fast lookups
        self._index: dict[str, dict] = {}
        self._load_index()
    
    def _load_index(self) -> None:
        """Load the index from disk."""
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                self._index = json.load(f)
        else:
            self._index = {}
    
    def _save_index(self) -> None:
        """Persist the index to disk."""
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self._index, f, indent=2, default=str)
    
    def _post_path(self, post_id: str) -> Path:
        """Get the file path for a post."""
        return self.posts_dir / f"{post_id}.md"
    
    def save_post(self, post: Post) -> None:
        """
        Save or update a post.
        
        Args:
            post: The post to save
        """
        # Prepare metadata for frontmatter
        post_data = post.model_dump(exclude={"content", "note"})
        
        # Convert enums to strings
        for key, value in post_data.items():
            if hasattr(value, "value"):
                post_data[key] = value.value
            elif isinstance(value, datetime):
                post_data[key] = value.isoformat()
        
        # Create frontmatter object
        fm = frontmatter.Post(post.content or "")
        fm.metadata = post_data
        
        # Add note if exists (store in metadata or body? Plan said body, but specialized field is better for clean separation if supported.
        # However, user asked for "Markdown Body: content, user note". 
        # Let's append note to content if it exists, or keep it in metadata. 
        # The prompt said: "Markdown Body: content, user note".
        # Let's put content in the body. Note in the body might be confusing if it mixes with content.
        # But for Obsidian, usually the whole file is the "Note".
        # Let's stick to: Content -> Body. Note -> Frontmatter field 'note', OR 'User Note' section in body.
        # The model `Post` has a `note` field. I will keep it in metadata for now for structured access, 
        # unless user explicitly wants it in body. User said: "md 파일 형식으로 수집 자료 개별 작성하고... 주요 정보 작성하면 어떨까?"
        # I will keep `note` in frontmatter strictly for now to preserve structure. `content` goes to body.
        
        if post.note:
            fm.metadata['note'] = post.note

        # Save as Markdown
        post_path = self._post_path(post.id)
        with open(post_path, 'wb') as f:
            frontmatter.dump(fm, f)
        
        # Update index with essential fields for fast filtering
        self._index[post.id] = {
            "url": post.url,
            "platform": post.platform,
            "author": post.author,
            "status": post.status,
            "posted_at": post.posted_at.isoformat() if post.posted_at else None,
            "scraped_at": post.scraped_at.isoformat() if post.scraped_at else None,
            "tags": post.tags,
            "category": post.category,
            "has_media": bool(post.media_paths),
            "media_type": post.media_type,
            # Stats for sorting
            "views": post.views,
            "likes": post.likes,
            "comments": post.comments,
            "thumbnail_path": post.thumbnail_path # Added for dashboard
        }
        self._save_index()
        self.export_static_data() # Update static data on save
    
    def get_post(self, post_id: str) -> Optional[Post]:
        """
        Retrieve a post by ID.
        
        Args:
            post_id: The post ID
            
        Returns:
            Post object or None if not found
        """
        post_path = self._post_path(post_id)
        if not post_path.exists():
            return None
        
        try:
            with open(post_path, 'r', encoding='utf-8') as f:
                fm = frontmatter.load(f)
            
            data = fm.metadata
            data["content"] = fm.content
            # ID is usually not in metadata if it's in filename, but let's assume we stored it in metadata in save_post
            # Actually save_post took post_data from post.model_dump, so ID is there.
            
            return Post.model_validate(data)
        except Exception as e:
            print(f"Error loading post {post_id}: {e}")
            return None
    
    def delete_post(self, post_id: str) -> bool:
        """
        Delete a post.
        
        Args:
            post_id: The post ID
            
        Returns:
            True if deleted, False if not found
        """
        post_path = self._post_path(post_id)
        if not post_path.exists():
            return False
        
        post_path.unlink()
        if post_id in self._index:
            del self._index[post_id]
            self._save_index()
        
        return True
    
    def exists(self, post_id: str) -> bool:
        """Check if a post exists."""
        return post_id in self._index
    
    def list_posts(self, filters: Optional[FilterOptions] = None) -> list[Post]:
        """
        List posts with optional filtering.
        
        Args:
            filters: Optional filter options
            
        Returns:
            List of matching posts
        """
        if filters is None:
            filters = FilterOptions()
        
        # Filter using index first for performance
        matching_ids = []
        
        for post_id, meta in self._index.items():
            if not self._matches_filter(meta, filters):
                continue
            matching_ids.append((post_id, meta))
        
        # Sort
        sort_key = filters.sort_by
        
        def get_sort_value(item):
            val = item[1].get(sort_key)
            # Handle numeric fields
            if sort_key in ['views', 'likes', 'comments', 'shares']:
                return val or 0
            # Handle string fields
            return val or ""

        matching_ids.sort(
            key=get_sort_value,
            reverse=filters.sort_desc,
        )
        
        # Apply pagination
        start = filters.offset
        end = start + filters.limit
        paginated = matching_ids[start:end]
        
        # Load full posts
        posts = []
        for post_id, _ in paginated:
            post = self.get_post(post_id)
            if post:
                posts.append(post)
        
        return posts
    
    def _matches_filter(self, meta: dict, filters: FilterOptions) -> bool:
        """Check if a post metadata matches the filter criteria."""
        
        # Platform filter
        if filters.platforms:
            if meta.get("platform") not in [p.value if isinstance(p, Platform) else p for p in filters.platforms]:
                return False
        
        # Status filter
        if filters.statuses:
            if meta.get("status") not in [s.value if isinstance(s, PostStatus) else s for s in filters.statuses]:
                return False
        
        # Author filter
        if filters.authors:
            if meta.get("author") not in filters.authors:
                return False
        
        # Tags filter (match any)
        if filters.tags:
            post_tags = set(meta.get("tags", []))
            if not post_tags.intersection(filters.tags):
                return False
        
        # Category filter
        if filters.categories:
            if meta.get("category") not in filters.categories:
                return False
        
        # Date range
        if filters.posted_after:
            posted_at = meta.get("posted_at")
            if not posted_at or datetime.fromisoformat(posted_at) < filters.posted_after:
                return False
        
            if not posted_at or datetime.fromisoformat(posted_at) > filters.posted_before:
                return False
        
        # Media Type filter
        if filters.media_types:
            if meta.get("media_type") not in filters.media_types:
                return False
        
        return True
    
    def get_all_tags(self) -> list[str]:
        """Get all unique tags."""
        tags = set()
        for meta in self._index.values():
            tags.update(meta.get("tags", []))
        return sorted(tags)
    
    def get_all_categories(self) -> list[str]:
        """Get all unique categories."""
        categories = set()
        for meta in self._index.values():
            cat = meta.get("category")
            if cat:
                categories.add(cat)
        return sorted(categories)
    
    def get_all_authors(self) -> list[str]:
        """Get all unique authors."""
        authors = set()
        for meta in self._index.values():
            author = meta.get("author")
            if author:
                authors.add(author)
        return sorted(authors)
    
    def update_tags(self, post_id: str, tags: list[str]) -> bool:
        """
        Update tags for a post.
        
        Args:
            post_id: The post ID
            tags: New list of tags
            
        Returns:
            True if updated, False if not found
        """
        post = self.get_post(post_id)
        if not post:
            return False
        
        post.tags = tags
        self.save_post(post)
        return True
    
    def update_category(self, post_id: str, category: Optional[str]) -> bool:
        """
        Update category for a post.
        
        Args:
            post_id: The post ID
            category: New category (or None to remove)
            
        Returns:
            True if updated, False if not found
        """
        post = self.get_post(post_id)
        if not post:
            return False
        
        post.category = category
        self.save_post(post)
        return True
    
    def get_stats(self) -> Statistics:
        """
        Calculate and return statistics.
        
        Returns:
            Statistics object
        """
        stats = Statistics()
        
        by_platform = defaultdict(int)
        by_author = defaultdict(int)
        
        for meta in self._index.values():
            stats.total_posts += 1
            
            # By status
            status = meta.get("status", "pending")
            if status == "accessible":
                stats.accessible += 1
            elif status == "private":
                stats.private += 1
            elif status == "deleted":
                stats.deleted += 1
            elif status == "pending":
                stats.pending += 1
            elif status == "failed":
                stats.failed += 1
            
            # By platform
            platform = meta.get("platform", "unknown")
            by_platform[platform] += 1
            
            # By author
            author = meta.get("author")
            if author:
                by_author[author] += 1
            
            # Count media
            if meta.get("has_media"):
                stats.total_media_downloaded += 1
        
        stats.unique_posts = len(self._index)
        stats.by_platform = dict(by_platform)
        stats.by_author = dict(sorted(by_author.items(), key=lambda x: -x[1])[:20])  # Top 20
        stats.last_updated = datetime.now()
        
        # Save stats
        with open(self.stats_file, 'w', encoding='utf-8') as f:
            f.write(stats.model_dump_json(indent=2))
        
        return stats
    
    def count(self) -> int:
        """Get total number of posts."""
        return len(self._index)

    def reindex(self) -> int:
        """Rebuild index from files."""
        count = 0
        new_index = {}
        
        if not self.posts_dir.exists():
            return 0
            
        for post_file in self.posts_dir.glob("*.md"):
            try:
                with open(post_file, 'r', encoding='utf-8') as f:
                    fm = frontmatter.load(f)
                    
                data = fm.metadata
                data["content"] = fm.content
                post = Post.model_validate(data)
                    
                new_index[post.id] = {
                    "url": post.url,
                    "platform": post.platform,
                    "author": post.author,
                    "status": post.status,
                    "posted_at": post.posted_at.isoformat() if post.posted_at else None,
                    "scraped_at": post.scraped_at.isoformat() if post.scraped_at else None,
                    "tags": post.tags,
                    "category": post.category,
                    "has_media": bool(post.media_paths),
                    "media_type": post.media_type,
                    "views": post.views,
                    "likes": post.likes,
                    "comments": post.comments,
                    "thumbnail_path": post.thumbnail_path
                }
                count += 1
            except Exception:
                continue
        
        self._index = new_index
        self._save_index()
        self.export_static_data()
        return count

    def export_static_data(self) -> None:
        """Export index to a JS file for the static dashboard."""
        data_js_path = self.data_dir / "data.js"
        
        # Convert index to list and sort by scraped_at desc
        posts_list = []
        for pid, meta in self._index.items():
            item = meta.copy()
            item['id'] = pid
            posts_list.append(item)
            
        # Sort by date (newest first)
        posts_list.sort(key=lambda x: x.get('scraped_at') or "", reverse=True)
            
        js_content = f"window.POSTS_DATA = {json.dumps(posts_list, indent=2)};"
        
        with open(data_js_path, 'w', encoding='utf-8') as f:
            f.write(js_content)

    def get_analytics(self) -> dict:
        """Get detailed analytics."""
        analytics = {
            "platform_counts": {},
            "author_stats": [],
            "media_type_counts": {"image": 0, "video": 0, "carousel": 0},
            "status_counts": {},
        }
        
        author_map = {}
        
        for meta in self._index.values():
            # Platform
            plat = meta.get("platform", "unknown")
            analytics["platform_counts"][plat] = analytics["platform_counts"].get(plat, 0) + 1
            
            # Status
            status = meta.get("status", "unknown")
            analytics["status_counts"][status] = analytics["status_counts"].get(status, 0) + 1
            
            # Media Type
            mtype = meta.get("media_type")
            if mtype in analytics["media_type_counts"]:
                analytics["media_type_counts"][mtype] += 1
            
            # Author Stats
            author = meta.get("author") or "Unknown"
            if author not in author_map:
                author_map[author] = {"name": author, "count": 0, "likes": 0, "comments": 0}
            
            author_map[author]["count"] += 1
            author_map[author]["likes"] += (meta.get("likes") or 0)
            author_map[author]["comments"] += (meta.get("comments") or 0)
        
        # Convert author map to list and sort by count
        analytics["author_stats"] = sorted(
            author_map.values(), 
            key=lambda x: x["count"], 
            reverse=True
        )
        
        return analytics
