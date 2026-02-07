"""Tests for the scraper module."""

import pytest

from media_toolkit.scraper import (
    BaseScraper,
    ScrapeResult,
    InstagramScraper,
    FacebookScraper,
    get_scraper,
    list_supported_platforms,
)


class TestScrapeResult:
    """Tests for ScrapeResult dataclass."""
    
    def test_create_success_result(self):
        result = ScrapeResult(
            success=True,
            url="https://instagram.com/p/test/",
            author="@testuser",
            platform="instagram",
        )
        assert result.success is True
        assert result.author == "@testuser"
        assert result.error_message is None
    
    def test_create_failure_result(self):
        result = ScrapeResult(
            success=False,
            url="https://instagram.com/p/test/",
            error_message="Failed to scrape",
        )
        assert result.success is False
        assert result.error_message == "Failed to scrape"


class TestBaseScraper:
    """Tests for BaseScraper abstract class."""
    
    def test_parse_count_normal(self):
        # Create a concrete implementation for testing
        class TestScraper(BaseScraper):
            def supports(self, url): return False
            async def scrape(self, url): return ScrapeResult(success=False, url=url)
        
        scraper = TestScraper()
        
        assert scraper._parse_count("1000") == 1000
        assert scraper._parse_count("1,000") == 1000
        assert scraper._parse_count("1.5K") == 1500
        assert scraper._parse_count("2.3M") == 2300000
        assert scraper._parse_count("1B") == 1000000000
        assert scraper._parse_count(None) is None
        assert scraper._parse_count("invalid") is None
    
    def test_clean_text(self):
        class TestScraper(BaseScraper):
            def supports(self, url): return False
            async def scrape(self, url): return ScrapeResult(success=False, url=url)
        
        scraper = TestScraper()
        
        assert scraper._clean_text("  hello   world  ") == "hello world"
        assert scraper._clean_text(None) is None
        assert scraper._clean_text("   ") is None


class TestInstagramScraper:
    """Tests for InstagramScraper."""
    
    @pytest.fixture
    def scraper(self):
        return InstagramScraper()
    
    def test_supports_instagram_urls(self, scraper):
        valid_urls = [
            "https://www.instagram.com/reel/ABC123/",
            "https://instagram.com/p/XYZ789/?igsh=abc",
            "https://www.instagram.com/stories/user/1234/",
            "https://www.instagram.com/tv/ABC123/",
        ]
        for url in valid_urls:
            assert scraper.supports(url) is True
    
    def test_does_not_support_other_urls(self, scraper):
        invalid_urls = [
            "https://www.facebook.com/share/r/ABC/",
            "https://www.youtube.com/watch?v=ABC",
            "https://twitter.com/user/status/123",
        ]
        for url in invalid_urls:
            assert scraper.supports(url) is False


class TestFacebookScraper:
    """Tests for FacebookScraper."""
    
    @pytest.fixture
    def scraper(self):
        return FacebookScraper()
    
    def test_supports_facebook_urls(self, scraper):
        valid_urls = [
            "https://www.facebook.com/share/r/ABC123/",
            "https://facebook.com/share/v/XYZ789/",
            "https://www.facebook.com/watch?v=123456",
            "https://www.facebook.com/reel/ABC123/",
        ]
        for url in valid_urls:
            assert scraper.supports(url) is True
    
    def test_does_not_support_other_urls(self, scraper):
        invalid_urls = [
            "https://www.instagram.com/p/ABC/",
            "https://www.youtube.com/watch?v=ABC",
        ]
        for url in invalid_urls:
            assert scraper.supports(url) is False


class TestGetScraper:
    """Tests for scraper factory."""
    
    def test_get_instagram_scraper(self):
        scraper = get_scraper("https://www.instagram.com/reel/ABC/")
        assert isinstance(scraper, InstagramScraper)
    
    def test_get_facebook_scraper(self):
        scraper = get_scraper("https://www.facebook.com/share/r/ABC/")
        assert isinstance(scraper, FacebookScraper)
    
    def test_get_scraper_unknown_url(self):
        scraper = get_scraper("https://www.youtube.com/watch?v=ABC")
        assert scraper is None


class TestListSupportedPlatforms:
    """Tests for list_supported_platforms."""
    
    def test_lists_platforms(self):
        platforms = list_supported_platforms()
        assert "instagram" in platforms
        assert "facebook" in platforms
