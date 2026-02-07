"""Parser module for extracting URLs from Markdown files."""

from .md_parser import (
    ExtractedURL,
    URLCollection,
    DuplicateReport,
    parse_md_file,
    scan_directory,
    detect_duplicates,
    detect_platform,
)

__all__ = [
    "ExtractedURL",
    "URLCollection", 
    "DuplicateReport",
    "parse_md_file",
    "scan_directory",
    "detect_duplicates",
    "detect_platform",
]
