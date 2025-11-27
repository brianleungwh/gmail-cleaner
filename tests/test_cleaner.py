"""
Tests for DomainCleaner class
"""

import pytest
from app.cleaner import DomainCleaner
from app.models import CleanupConfig


# === Sample Thread Data ===

def make_cleanup_thread(thread_id: str, domain: str, subject: str, sender: str, message_count: int = 1) -> dict:
    """Helper to create thread dict for cleanup tests"""
    return {
        'thread_id': thread_id,
        'domain': domain,
        'subject': subject,
        'sender': sender,
        'message_count': message_count
    }


@pytest.fixture
def sample_threads():
    """Sample threads for cleanup tests"""
    return [
        make_cleanup_thread('thread_001', 'spam.com', 'Buy now!', 'promo@spam.com', 2),
        make_cleanup_thread('thread_002', 'spam.com', 'Limited offer', 'deals@spam.com', 1),
        make_cleanup_thread('thread_003', 'junk.com', 'You won!', 'winner@junk.com', 3),
    ]


# === Cleanup Tests ===

@pytest.mark.asyncio
class TestCleanup:
    """Tests for the async cleanup method"""

    async def test_cleanup_dry_run(self, mock_gmail_service, default_cleanup_config, sample_threads):
        """Dry run should report deletions without actually trashing"""
        cleaner = DomainCleaner(mock_gmail_service, default_cleanup_config)
        result = await cleaner.cleanup(sample_threads)

        # Should report all threads as deleted
        assert result['threads_processed'] == 3
        assert result['threads_deleted'] == 3
        assert result['messages_deleted'] == 6  # 2 + 1 + 3

        # But no threads should actually be trashed
        assert len(mock_gmail_service.trashed_threads) == 0

    async def test_cleanup_live_run(self, mock_gmail_service, live_cleanup_config, sample_threads):
        """Live run should actually trash threads"""
        cleaner = DomainCleaner(mock_gmail_service, live_cleanup_config)
        result = await cleaner.cleanup(sample_threads)

        # Should report all threads as deleted
        assert result['threads_processed'] == 3
        assert result['threads_deleted'] == 3
        assert result['messages_deleted'] == 6

        # Threads should actually be trashed
        assert len(mock_gmail_service.trashed_threads) == 3
        assert 'thread_001' in mock_gmail_service.trashed_threads
        assert 'thread_002' in mock_gmail_service.trashed_threads
        assert 'thread_003' in mock_gmail_service.trashed_threads

    async def test_cleanup_empty_threads(self, mock_gmail_service, default_cleanup_config):
        """Empty thread list should return zero stats"""
        cleaner = DomainCleaner(mock_gmail_service, default_cleanup_config)
        result = await cleaner.cleanup([])

        assert result['threads_processed'] == 0
        assert result['threads_deleted'] == 0
        assert result['messages_deleted'] == 0
        assert result['messages_kept'] == 0

    async def test_cleanup_handles_trash_error(self, mock_gmail_service_with_failures, live_cleanup_config, sample_threads):
        """Cleanup should continue and track kept messages on API error"""
        cleaner = DomainCleaner(mock_gmail_service_with_failures, live_cleanup_config)
        result = await cleaner.cleanup(sample_threads)

        # All threads processed
        assert result['threads_processed'] == 3

        # thread_001 should fail (configured in fixture), others succeed
        assert result['threads_deleted'] == 2
        assert result['messages_kept'] == 2  # thread_001 has 2 messages
        assert result['messages_deleted'] == 4  # 1 + 3 from successful threads

    async def test_cleanup_progress_callback(self, mock_gmail_service, default_cleanup_config, sample_threads):
        """Progress callback should be called during cleanup"""
        progress_events = []

        async def capture_progress(event: str, data: dict):
            progress_events.append((event, data))

        cleaner = DomainCleaner(mock_gmail_service, default_cleanup_config, progress_callback=capture_progress)
        await cleaner.cleanup(sample_threads)

        # Should have received progress events
        event_types = [e[0] for e in progress_events]
        assert 'cleanup_started' in event_types
        assert 'cleanup_completed' in event_types
        assert 'thread_analyzed' in event_types
        assert 'would_delete' in event_types  # dry run

    async def test_cleanup_live_progress_events(self, mock_gmail_service, live_cleanup_config, sample_threads):
        """Live cleanup should emit 'deleted' events instead of 'would_delete'"""
        progress_events = []

        async def capture_progress(event: str, data: dict):
            progress_events.append((event, data))

        cleaner = DomainCleaner(mock_gmail_service, live_cleanup_config, progress_callback=capture_progress)
        await cleaner.cleanup(sample_threads)

        event_types = [e[0] for e in progress_events]
        assert 'deleted' in event_types
        assert 'would_delete' not in event_types


# === Build Stats Tests ===

class TestBuildStats:
    """Tests for _build_stats static method"""

    def test_build_stats_all_values(self):
        """Build stats should include all fields"""
        result = DomainCleaner._build_stats(10, 8, 20, 5)

        assert result['threads_processed'] == 10
        assert result['threads_deleted'] == 8
        assert result['messages_deleted'] == 20
        assert result['messages_kept'] == 5

    def test_build_stats_zeros(self):
        """Build stats should handle all zeros"""
        result = DomainCleaner._build_stats(0, 0, 0, 0)

        assert result['threads_processed'] == 0
        assert result['threads_deleted'] == 0
        assert result['messages_deleted'] == 0
        assert result['messages_kept'] == 0


# === Interrupt Handling Tests ===

@pytest.mark.asyncio
class TestInterruptHandling:
    """Tests for interrupt handling during cleanup"""

    async def test_cleanup_respects_interrupt(self, mock_gmail_service, default_cleanup_config, sample_threads):
        """Cleanup should stop when interrupted flag is set"""
        cleaner = DomainCleaner(mock_gmail_service, default_cleanup_config)

        # Set interrupt after first thread
        processed_count = 0

        async def interrupt_after_first(event: str, data: dict):
            nonlocal processed_count
            if event == 'thread_analyzed':
                processed_count += 1
                if processed_count >= 1:
                    cleaner.interrupted = True

        cleaner.progress_callback = interrupt_after_first
        result = await cleaner.cleanup(sample_threads)

        # Should have stopped early
        assert result['threads_processed'] < len(sample_threads)
