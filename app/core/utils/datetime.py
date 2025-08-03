from datetime import datetime, timezone
from functools import lru_cache


@lru_cache()
def get_current_date() -> str:
    """
    Returns the current date and time in the UTC timezone in US format.
    Example: '08-15-2025 10:00:00PM'
    """
    return datetime \
        .now(timezone.utc) \
        .strftime("%m-%d-%Y %I:%M:%S%p")
