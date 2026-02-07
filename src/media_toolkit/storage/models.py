"""Data models for social media posts."""

from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Platform(str, Enum):
    """Supported social media platforms."""
    
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    THREADS = "threads"
    UNKNOWN = "unknown"


class PostStatus(str, Enum):
    """Status of a post."""
    
    PENDING = "pending"          # Not yet validated
    ACCESSIBLE = "accessible"    # Can be accessed
    PRIVATE = "private"          # Requires login or is private
    DELETED = "deleted"          # No longer exists
    FAILED = "failed"            # Failed to scrape


class Post(BaseModel):
    """Represents a social media post."""
    
    # Core identifiers
    id: str = Field(..., description="Unique SHA-based ID from URL")
    url: str = Field(..., description="Original URL")
    platform: Platform = Field(..., description="Source platform")
    
    # Author info
    author: Optional[str] = Field(None, description="Username or page name")
    author_url: Optional[str] = Field(None, description="Link to author profile")
    
    # Content
    title: Optional[str] = Field(None, description="Post title if available")
    content: Optional[str] = Field(None, description="Post text/caption")
    posted_at: Optional[datetime] = Field(None, description="Original post date")
    
    # Status tracking
    status: PostStatus = Field(default=PostStatus.PENDING)
    scraped_at: Optional[datetime] = Field(None, description="When metadata was extracted")
    validated_at: Optional[datetime] = Field(None, description="When URL was validated")
    
    # Metrics (nullable - may not be available)
    views: Optional[int] = Field(None, ge=0)
    likes: Optional[int] = Field(None, ge=0)
    comments: Optional[int] = Field(None, ge=0)
    shares: Optional[int] = Field(None, ge=0)
    
    # Media
    thumbnail_url: Optional[str] = Field(None, description="Remote thumbnail URL")
    thumbnail_path: Optional[str] = Field(None, description="Local thumbnail path")
    media_urls: list[str] = Field(default_factory=list, description="Remote media URLs")
    media_paths: list[str] = Field(default_factory=list, description="Local media paths")
    media_type: Optional[str] = Field(None, description="video, image, carousel")
    
    # Organization
    tags: list[str] = Field(default_factory=list)
    category: Optional[str] = Field(None)
    
    # Source tracking
    source_file: str = Field(..., description="Original MD file path")
    source_context: Optional[str] = Field(None, description="Nearby text from MD file")
    
    # Error tracking
    error_message: Optional[str] = Field(None)
    
    # User Notes
    note: Optional[str] = Field(None, description="User notes")
    
    class Config:
        use_enum_values = True


class Statistics(BaseModel):
    """Statistics about the collected posts."""
    
    total_posts: int = 0
    unique_posts: int = 0
    
    # By status
    accessible: int = 0
    private: int = 0
    deleted: int = 0
    pending: int = 0
    failed: int = 0
    
    # By platform
    by_platform: dict[str, int] = Field(default_factory=dict)
    
    # By author (top authors)
    by_author: dict[str, int] = Field(default_factory=dict)
    
    # Media stats
    total_media_downloaded: int = 0
    total_media_size_mb: float = 0.0
    
    # Timestamps
    first_collected: Optional[datetime] = None
    last_updated: Optional[datetime] = None


class FilterOptions(BaseModel):
    """Options for filtering posts."""
    
    platforms: Optional[list[Platform]] = None
    statuses: Optional[list[PostStatus]] = None
    authors: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    categories: Optional[list[str]] = None
    media_types: Optional[list[str]] = None
    
    # User Notes
    note: Optional[str] = None
    
    # Date range
    posted_after: Optional[datetime] = None
    posted_before: Optional[datetime] = None
    
    # Search
    search_query: Optional[str] = None
    
    # Pagination
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    
    # Sorting
    sort_by: str = Field(default="scraped_at")
    sort_desc: bool = True
