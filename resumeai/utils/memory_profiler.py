"""
resumeai/utils/memory_profiler.py — Lightweight memory profiling.
"""
import os
import logging
import psutil

logger = logging.getLogger(__name__)

# Check if we should log memory. Could check DEBUG flag, for now we will log if called.
def log_memory(stage: str):
    """
    Log the current RSS memory footprint.
    Only active in DEBUG mode.
    """
    try:
        from core.config import settings
        if not getattr(settings, "DEBUG", True):
            return
    except Exception:
        pass  # Default to log if config not found
        
    process = psutil.Process(os.getpid())
    rss_mb = process.memory_info().rss / (1024 * 1024)
    print(f"[MEMORY] Stage: {stage:25s} | RSS: {rss_mb:6.1f} MB", flush=True)

def get_rss_memory() -> float:
    """Return current RSS memory in MB."""
    try:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0

