import threading

from src.core.downloader import DownloadManager
from src.core.rate_limiter import RateLimitConfig, RateLimiter


class DummyFileManager:
    pass


def make_download_manager() -> DownloadManager:
    return DownloadManager(
        {
            "max_threads": 1,
            "timeout": 1,
            "retry_times": 1,
            "chunk_size": 1024,
            "base_rate": 100,
            "max_rate": 100,
        },
        DummyFileManager(),
    )


def test_start_initializes_all_download_counters():
    manager = make_download_manager()

    manager.start()
    try:
        stats = manager.get_stats()
    finally:
        manager.stop()

    assert stats["total"] == 0
    assert stats["success"] == 0
    assert stats["failed"] == 0
    assert stats["skipped"] == 0
    assert stats["retry"] == 0
    assert stats["server_errors"] == 0
    assert stats["bytes_downloaded"] == 0


def test_is_downloading_tracks_in_progress_items_after_queue_is_empty():
    manager = make_download_manager()
    manager.is_running = True
    manager.stats = {
        "total": 2,
        "success": 1,
        "failed": 0,
        "skipped": 0,
        "retry": 0,
        "server_errors": 0,
        "bytes_downloaded": 0,
    }

    assert manager.is_downloading() is True

    manager.stats["success"] = 2

    assert manager.is_downloading() is False


def test_rate_limiter_get_status_does_not_deadlock():
    limiter = RateLimiter(
        RateLimitConfig(max_requests_per_second=1.0, burst_capacity=1)
    )

    result = {}

    def read_status():
        result["status"] = limiter.get_status()

    thread = threading.Thread(target=read_status, daemon=True)
    thread.start()
    thread.join(timeout=0.5)

    assert not thread.is_alive()
    assert result["status"]["wait_time_for_one"] == 0.0
