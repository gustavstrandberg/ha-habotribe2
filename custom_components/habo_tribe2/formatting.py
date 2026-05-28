"""Formatting helpers for HABO Tribe2 entities."""

from __future__ import annotations


def duration_text(seconds: int | None) -> str | None:
    """Format seconds as the duration text shown by the HABO app."""

    if seconds is None:
        return None
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days} d {hours} h {minutes} m {seconds} s"
