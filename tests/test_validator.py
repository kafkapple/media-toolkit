"""Tests for the validator module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from media_toolkit.validator import (
    URLStatus,
    ValidationResult,
    URLValidator,
    validate_url,
)


class TestURLStatus:
    """Tests for URLStatus enum."""
    
    def test_status_values(self):
        assert URLStatus.ACCESSIBLE.value == "accessible"
        assert URLStatus.PRIVATE.value == "private"
        assert URLStatus.DELETED.value == "deleted"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""
    
    def test_create_result(self):
        result = ValidationResult(
            url="https://instagram.com/p/test/",
            status=URLStatus.ACCESSIBLE,
            http_status=200,
        )
        assert result.url == "https://instagram.com/p/test/"
        assert result.status == URLStatus.ACCESSIBLE
        assert result.error_message is None


class TestURLValidator:
    """Tests for URLValidator class."""
    
    @pytest.fixture
    def validator(self):
        return URLValidator(timeout=5, max_retries=1)
    
    def test_status_mapping(self, validator):
        assert validator.STATUS_MAPPING[200] == URLStatus.ACCESSIBLE
        assert validator.STATUS_MAPPING[404] == URLStatus.DELETED
        assert validator.STATUS_MAPPING[403] == URLStatus.PRIVATE
    
    def test_analyze_content_private(self, validator):
        content = "Sorry, this page isn't available. The link may be broken."
        assert validator._analyze_content(content) == URLStatus.PRIVATE
    
    def test_analyze_content_deleted(self, validator):
        content = "Page Not Found - this content has been removed"
        assert validator._analyze_content(content) == URLStatus.DELETED
    
    def test_analyze_content_accessible(self, validator):
        content = "<html><body>Normal page content here</body></html>"
        assert validator._analyze_content(content) == URLStatus.ACCESSIBLE


class TestBatchValidate:
    """Tests for batch validation."""
    
    @pytest.mark.asyncio
    async def test_batch_validate_empty(self):
        validator = URLValidator()
        results = await validator.batch_validate([])
        assert results == []
