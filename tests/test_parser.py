"""Tests for the parser module."""

import tempfile
from pathlib import Path
import pytest

from media_toolkit.parser import (
    ExtractedURL,
    URLCollection,
    DuplicateReport,
    parse_md_file,
    scan_directory,
    detect_duplicates,
    detect_platform,
)


class TestDetectPlatform:
    """Tests for platform detection."""
    
    def test_detect_instagram(self):
        urls = [
            "https://www.instagram.com/reel/ABC123/",
            "https://instagram.com/p/XYZ789/?igsh=abc",
            "https://www.instagram.com/stories/user/123456/",
        ]
        for url in urls:
            assert detect_platform(url) == "instagram"
    
    def test_detect_facebook(self):
        urls = [
            "https://www.facebook.com/share/r/ABC123/",
            "https://facebook.com/share/v/XYZ789/?mibextid=abc",
            "https://www.facebook.com/watch?v=123456",
        ]
        for url in urls:
            assert detect_platform(url) == "facebook"
    
    def test_detect_linkedin(self):
        urls = [
            "https://www.linkedin.com/posts/user_activity-123",
            "https://linkedin.com/feed/update/urn:li:activity:123",
        ]
        for url in urls:
            assert detect_platform(url) == "linkedin"
    
    def test_detect_threads(self):
        url = "https://www.threads.net/@username/post/ABC123"
        assert detect_platform(url) == "threads"
    
    def test_detect_unknown(self):
        url = "https://www.youtube.com/watch?v=ABC123"
        assert detect_platform(url) == "unknown"


class TestExtractedURL:
    """Tests for ExtractedURL class."""
    
    def test_id_generation(self):
        """Same URL should generate same ID."""
        url1 = ExtractedURL(
            url="https://instagram.com/p/ABC123/",
            platform="instagram",
            source_file=Path("/test.md"),
            line_number=1,
        )
        url2 = ExtractedURL(
            url="https://instagram.com/p/ABC123/",
            platform="instagram",
            source_file=Path("/other.md"),
            line_number=5,
        )
        assert url1.id == url2.id
    
    def test_id_ignores_tracking_params(self):
        """ID should be same regardless of tracking params."""
        url1 = ExtractedURL(
            url="https://instagram.com/reel/ABC123/",
            platform="instagram",
            source_file=Path("/test.md"),
            line_number=1,
        )
        url2 = ExtractedURL(
            url="https://instagram.com/reel/ABC123/?igsh=xyz123",
            platform="instagram",
            source_file=Path("/test.md"),
            line_number=1,
        )
        assert url1.id == url2.id


class TestURLCollection:
    """Tests for URLCollection class."""
    
    def test_add_and_len(self):
        collection = URLCollection()
        url = ExtractedURL(
            url="https://instagram.com/p/ABC/",
            platform="instagram",
            source_file=Path("/test.md"),
            line_number=1,
        )
        collection.add(url)
        assert len(collection) == 1
        assert Path("/test.md") in collection.source_files
    
    def test_by_platform(self):
        collection = URLCollection()
        collection.add(ExtractedURL(
            url="https://instagram.com/p/1/",
            platform="instagram",
            source_file=Path("/test.md"),
            line_number=1,
        ))
        collection.add(ExtractedURL(
            url="https://facebook.com/share/r/2/",
            platform="facebook",
            source_file=Path("/test.md"),
            line_number=2,
        ))
        collection.add(ExtractedURL(
            url="https://instagram.com/p/3/",
            platform="instagram",
            source_file=Path("/test.md"),
            line_number=3,
        ))
        
        by_platform = collection.by_platform()
        assert len(by_platform["instagram"]) == 2
        assert len(by_platform["facebook"]) == 1
    
    def test_unique_urls(self):
        collection = URLCollection()
        collection.add(ExtractedURL(
            url="https://instagram.com/p/ABC/",
            platform="instagram",
            source_file=Path("/file1.md"),
            line_number=1,
        ))
        collection.add(ExtractedURL(
            url="https://instagram.com/p/ABC/",  # duplicate
            platform="instagram",
            source_file=Path("/file2.md"),
            line_number=5,
        ))
        collection.add(ExtractedURL(
            url="https://instagram.com/p/XYZ/",  # different
            platform="instagram",
            source_file=Path("/file1.md"),
            line_number=2,
        ))
        
        unique = collection.unique_urls()
        assert len(unique) == 2


class TestParseMdFile:
    """Tests for parse_md_file function."""
    
    def test_parse_simple_file(self):
        content = """# Test File

https://www.instagram.com/reel/ABC123/

Some text here

https://www.facebook.com/share/r/XYZ789/
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            
            urls = parse_md_file(Path(f.name))
            
        assert len(urls) == 2
        assert urls[0].platform == "instagram"
        assert urls[1].platform == "facebook"
    
    def test_parse_with_frontmatter(self):
        content = """---
created: 2024-01-01
tags: [test]
---
# Test

https://www.instagram.com/p/ABC123/
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            
            urls = parse_md_file(Path(f.name))
        
        assert len(urls) == 1
        assert urls[0].platform == "instagram"
    
    def test_parse_with_context(self):
        content = """# Test

가요이
https://www.instagram.com/reel/ABC123/
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            f.flush()
            
            urls = parse_md_file(Path(f.name))
        
        assert len(urls) == 1
        assert urls[0].context == "가요이"
    
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_md_file(Path("/nonexistent/file.md"))


class TestDetectDuplicates:
    """Tests for detect_duplicates function."""
    
    def test_no_duplicates(self):
        urls = [
            ExtractedURL(
                url="https://instagram.com/p/ABC/",
                platform="instagram",
                source_file=Path("/test.md"),
                line_number=1,
            ),
            ExtractedURL(
                url="https://instagram.com/p/XYZ/",
                platform="instagram",
                source_file=Path("/test.md"),
                line_number=2,
            ),
        ]
        
        report = detect_duplicates(urls)
        assert not report
        assert report.total_duplicates == 0
    
    def test_with_duplicates(self):
        urls = [
            ExtractedURL(
                url="https://instagram.com/p/ABC/",
                platform="instagram",
                source_file=Path("/file1.md"),
                line_number=1,
            ),
            ExtractedURL(
                url="https://instagram.com/p/ABC/",
                platform="instagram",
                source_file=Path("/file2.md"),
                line_number=1,
            ),
            ExtractedURL(
                url="https://instagram.com/p/ABC/?igsh=xyz",
                platform="instagram",
                source_file=Path("/file3.md"),
                line_number=1,
            ),
        ]
        
        report = detect_duplicates(urls)
        assert report
        assert report.total_duplicates == 2  # 3 total - 1 original = 2 duplicates
        assert report.unique_duplicated_count == 1  # 1 unique URL with duplicates
