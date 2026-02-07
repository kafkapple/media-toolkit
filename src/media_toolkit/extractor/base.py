from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class MediaItem:
    url: str
    type: str  # 'image' or 'video'
    thumbnail_url: Optional[str] = None
    title: Optional[str] = None
    file_size: Optional[str] = None  # Human readable size
    original_data: Optional[dict] = None # Store raw metadata if needed

class MediaExtractor(ABC):
    @abstractmethod
    def extract(self, url: str) -> List[MediaItem]:
        """Extract media items from the given URL."""
        pass

    @abstractmethod
    def is_supported(self, url: str) -> bool:
        """Check if this extractor supports the given URL."""
        pass
