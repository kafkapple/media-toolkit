def human_readable_size(size_in_bytes: int) -> str:
    """Converts bytes to a human readable string (e.g. 10.5 MB)."""
    if size_in_bytes is None:
        return "Unknown"

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"
