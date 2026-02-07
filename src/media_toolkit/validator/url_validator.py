"""URL validator for checking accessibility of social media URLs."""

import asyncio
import aiohttp
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class URLStatus(Enum):
    """Status of a URL after validation."""
    
    ACCESSIBLE = "accessible"
    PRIVATE = "private"
    DELETED = "deleted"
    LOGIN_REQUIRED = "login_required"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    """Result of URL validation."""
    
    url: str
    status: URLStatus
    http_status: Optional[int] = None
    error_message: Optional[str] = None
    validated_at: datetime = field(default_factory=datetime.now)
    response_time_ms: Optional[float] = None


class URLValidator:
    """Validates URLs for accessibility."""
    
    # HTTP status codes and their meanings for social media
    STATUS_MAPPING = {
        200: URLStatus.ACCESSIBLE,
        401: URLStatus.LOGIN_REQUIRED,
        403: URLStatus.PRIVATE,
        404: URLStatus.DELETED,
        429: URLStatus.RATE_LIMITED,
    }
    
    # Patterns in response that indicate private/deleted content
    PRIVATE_INDICATORS = [
        "This page isn't available",
        "Sorry, this page isn't available",
        "content isn't available",
        "This content isn't available",
        "private account",
        "Log in to see photos",
    ]
    
    DELETED_INDICATORS = [
        "Page Not Found",
        "This page may have been removed",
        "content has been removed",
        "no longer available",
    ]
    
    def __init__(
        self,
        timeout: int = 10,
        max_retries: int = 3,
        user_agent: Optional[str] = None,
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    
    async def validate(self, url: str) -> ValidationResult:
        """
        Validate a single URL for accessibility.
        
        Args:
            url: The URL to validate
            
        Returns:
            ValidationResult with status information
        """
        start_time = datetime.now()
        
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, headers=headers, allow_redirects=True) as response:
                        elapsed = (datetime.now() - start_time).total_seconds() * 1000
                        
                        # Check HTTP status first
                        status = self.STATUS_MAPPING.get(response.status, URLStatus.UNKNOWN)
                        
                        # For 200 responses, check content for private/deleted indicators
                        if response.status == 200:
                            try:
                                content = await response.text()
                                status = self._analyze_content(content)
                            except Exception:
                                # If we can't read content, assume accessible
                                pass
                        
                        return ValidationResult(
                            url=url,
                            status=status,
                            http_status=response.status,
                            response_time_ms=elapsed,
                        )
                        
            except asyncio.TimeoutError:
                if attempt == self.max_retries - 1:
                    return ValidationResult(
                        url=url,
                        status=URLStatus.TIMEOUT,
                        error_message=f"Timeout after {self.timeout}s",
                    )
                await asyncio.sleep(1)  # Brief delay before retry
                
            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    return ValidationResult(
                        url=url,
                        status=URLStatus.UNKNOWN,
                        error_message=str(e),
                    )
                await asyncio.sleep(1)
        
        return ValidationResult(
            url=url,
            status=URLStatus.UNKNOWN,
            error_message="Max retries exceeded",
        )
    
    def _analyze_content(self, content: str) -> URLStatus:
        """Analyze page content to detect private/deleted posts."""
        content_lower = content.lower()
        
        for indicator in self.DELETED_INDICATORS:
            if indicator.lower() in content_lower:
                return URLStatus.DELETED
        
        for indicator in self.PRIVATE_INDICATORS:
            if indicator.lower() in content_lower:
                return URLStatus.PRIVATE
        
        return URLStatus.ACCESSIBLE
    
    async def batch_validate(
        self,
        urls: list[str],
        concurrent_limit: int = 5,
        delay: float = 1.0,
    ) -> list[ValidationResult]:
        """
        Validate multiple URLs with concurrency control.
        
        Args:
            urls: List of URLs to validate
            concurrent_limit: Maximum concurrent requests
            delay: Delay between batches (to avoid rate limiting)
            
        Returns:
            List of ValidationResults in the same order as input
        """
        semaphore = asyncio.Semaphore(concurrent_limit)
        
        async def validate_with_semaphore(url: str) -> ValidationResult:
            async with semaphore:
                result = await self.validate(url)
                await asyncio.sleep(delay)  # Rate limiting
                return result
        
        tasks = [validate_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)


# Convenience functions
async def validate_url(url: str, timeout: int = 10) -> ValidationResult:
    """Validate a single URL."""
    validator = URLValidator(timeout=timeout)
    return await validator.validate(url)


async def batch_validate(
    urls: list[str],
    concurrent_limit: int = 5,
    delay: float = 1.0,
) -> list[ValidationResult]:
    """Validate multiple URLs."""
    validator = URLValidator()
    return await validator.batch_validate(urls, concurrent_limit, delay)
