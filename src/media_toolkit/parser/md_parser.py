"""Markdown file parser for extracting social media URLs."""

import re
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict


# Regex patterns for social media URLs
URL_PATTERNS = {
    "instagram": re.compile(
        r'https?://(?:www\.)?instagram\.com/(?:p|reel|stories|tv)/[A-Za-z0-9_-]+/?(?:\?[^\s]*)?',
        re.IGNORECASE
    ),
    "facebook": re.compile(
        r'https?://(?:www\.)?facebook\.com/(?:share/[rv]/|watch/?\?v=|reel/)[A-Za-z0-9_-]+/?(?:\?[^\s]*)?',
        re.IGNORECASE
    ),
    "linkedin": re.compile(
        r'https?://(?:www\.)?linkedin\.com/(?:posts|feed/update)/[^\s]+',
        re.IGNORECASE
    ),
    "threads": re.compile(
        r'https?://(?:www\.)?threads\.net/@[A-Za-z0-9_.]+/post/[A-Za-z0-9_-]+',
        re.IGNORECASE
    ),
}

# Combined pattern for any social media URL
COMBINED_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:instagram|facebook|linkedin|threads)\.(?:com|net)/[^\s\]\)]+',
    re.IGNORECASE
)


@dataclass
class ExtractedURL:
    """Represents a URL extracted from a Markdown file."""
    
    url: str
    platform: str
    source_file: Path
    line_number: int
    context: Optional[str] = None  # Nearby text/comment
    
    @property
    def id(self) -> str:
        """Generate a unique ID from the URL."""
        # Normalize URL before hashing (remove tracking params)
        normalized = self._normalize_url(self.url)
        return hashlib.sha256(normalized.encode()).hexdigest()[:12]
    
    def _normalize_url(self, url: str) -> str:
        """Remove tracking parameters for consistent ID generation."""
        # Remove common tracking params like igsh, mibextid, img_index
        url = re.sub(r'[?&](igsh|mibextid|img_index)=[^&\s]*', '', url)
        # Clean up leftover ? or &
        url = re.sub(r'\?$', '', url)
        url = re.sub(r'\?&', '?', url)
        return url.rstrip('/')


@dataclass
class URLCollection:
    """Collection of URLs extracted from multiple files."""
    
    urls: list[ExtractedURL] = field(default_factory=list)
    source_files: set[Path] = field(default_factory=set)
    
    def add(self, url: ExtractedURL) -> None:
        """Add a URL to the collection."""
        self.urls.append(url)
        self.source_files.add(url.source_file)
    
    def __len__(self) -> int:
        return len(self.urls)
    
    def __iter__(self):
        return iter(self.urls)
    
    def by_platform(self) -> dict[str, list[ExtractedURL]]:
        """Group URLs by platform."""
        result = defaultdict(list)
        for url in self.urls:
            result[url.platform].append(url)
        return dict(result)
    
    def unique_urls(self) -> list[ExtractedURL]:
        """Return deduplicated URLs (first occurrence of each)."""
        seen = set()
        unique = []
        for url in self.urls:
            if url.id not in seen:
                seen.add(url.id)
                unique.append(url)
        return unique


@dataclass
class DuplicateReport:
    """Report of duplicate URLs found across files."""
    
    duplicates: dict[str, list[ExtractedURL]] = field(default_factory=dict)
    
    @property
    def total_duplicates(self) -> int:
        """Total number of duplicate entries (excluding originals)."""
        return sum(len(urls) - 1 for urls in self.duplicates.values())
    
    @property  
    def unique_duplicated_count(self) -> int:
        """Number of unique URLs that have duplicates."""
        return len(self.duplicates)
    
    def __bool__(self) -> bool:
        return bool(self.duplicates)


def detect_platform(url: str) -> str:
    """Detect the platform from a URL."""
    url_lower = url.lower()
    if 'instagram.com' in url_lower:
        return 'instagram'
    elif 'facebook.com' in url_lower:
        return 'facebook'
    elif 'linkedin.com' in url_lower:
        return 'linkedin'
    elif 'threads.net' in url_lower:
        return 'threads'
    return 'unknown'


def extract_context(lines: list[str], line_idx: int, context_lines: int = 1) -> Optional[str]:
    """Extract context (nearby text) around a URL."""
    context_parts = []
    
    # Get preceding non-empty, non-URL lines
    for i in range(max(0, line_idx - context_lines), line_idx):
        line = lines[i].strip()
        if line and not COMBINED_PATTERN.search(line):
            context_parts.append(line)
    
    return ' | '.join(context_parts) if context_parts else None


def parse_md_file(path: Path) -> list[ExtractedURL]:
    """
    Parse a single Markdown file and extract all social media URLs.
    
    Args:
        path: Path to the Markdown file
        
    Returns:
        List of ExtractedURL objects found in the file
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    extracted = []
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
    
    # Skip YAML frontmatter if present
    start_line = 0
    if content.startswith('---'):
        # Find closing ---
        end_match = re.search(r'\n---\n', content[3:])
        if end_match:
            frontmatter_end = end_match.end() + 3
            start_line = content[:frontmatter_end].count('\n')
    
    # Extract URLs from each line
    for line_idx, line in enumerate(lines):
        if line_idx < start_line:
            continue
            
        # Find all URLs in this line
        for match in COMBINED_PATTERN.finditer(line):
            url = match.group(0)
            # Clean trailing punctuation
            url = url.rstrip('.,;:!?)\'\"')
            
            platform = detect_platform(url)
            context = extract_context(lines, line_idx)
            
            extracted.append(ExtractedURL(
                url=url,
                platform=platform,
                source_file=path,
                line_number=line_idx + 1,  # 1-indexed
                context=context,
            ))
    
    return extracted


def scan_directory(path: Path, pattern: str = "*.md", recursive: bool = True) -> URLCollection:
    """
    Scan a directory for Markdown files and extract all URLs.
    
    Args:
        path: Directory path to scan
        pattern: Glob pattern for files (default: *.md)
        recursive: Whether to scan subdirectories
        
    Returns:
        URLCollection containing all extracted URLs
    """
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    
    collection = URLCollection()
    
    # Get matching files
    if recursive:
        files = list(path.rglob(pattern))
    else:
        files = list(path.glob(pattern))
    
    for file_path in sorted(files):
        try:
            urls = parse_md_file(file_path)
            for url in urls:
                collection.add(url)
        except Exception as e:
            # Log error but continue processing
            print(f"Warning: Error parsing {file_path}: {e}")
    
    return collection


def detect_duplicates(urls: list[ExtractedURL]) -> DuplicateReport:
    """
    Identify duplicate URLs across the collection.
    
    Args:
        urls: List of ExtractedURL objects
        
    Returns:
        DuplicateReport with grouped duplicates
    """
    # Group by normalized URL ID
    by_id: dict[str, list[ExtractedURL]] = defaultdict(list)
    
    for url in urls:
        by_id[url.id].append(url)
    
    # Filter to only those with duplicates
    duplicates = {
        url_id: url_list 
        for url_id, url_list in by_id.items() 
        if len(url_list) > 1
    }
    
    return DuplicateReport(duplicates=duplicates)
