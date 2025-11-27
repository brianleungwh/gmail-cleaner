"""
Tests for DomainCollector class
"""

import pytest
from app.collector import DomainCollector
from app.models import CollectionConfig, ThreadMetadata


# === Static Method Tests ===

class TestExtractEmailAddress:
    """Tests for extract_email_address static method"""

    def test_with_name_and_brackets(self):
        """Extract email from 'Name <email@domain.com>' format"""
        result = DomainCollector.extract_email_address('John Doe <john@example.com>')
        assert result == 'john@example.com'

    def test_plain_email(self):
        """Extract email when just plain email is provided"""
        result = DomainCollector.extract_email_address('john@example.com')
        assert result == 'john@example.com'

    def test_uppercase_normalized(self):
        """Email should be lowercased"""
        result = DomainCollector.extract_email_address('John@EXAMPLE.COM')
        assert result == 'john@example.com'

    def test_with_extra_whitespace(self):
        """Handle whitespace around email"""
        result = DomainCollector.extract_email_address('  john@example.com  ')
        assert result == 'john@example.com'

    def test_complex_name(self):
        """Handle complex display names"""
        result = DomainCollector.extract_email_address('"Doe, John" <john@example.com>')
        assert result == 'john@example.com'


class TestExtractDomain:
    """Tests for extract_domain static method"""

    def test_simple_domain(self):
        """Extract domain from simple email"""
        result = DomainCollector.extract_domain('john@example.com')
        assert result == 'example.com'

    def test_subdomain(self):
        """Extract domain including subdomain"""
        result = DomainCollector.extract_domain('john@mail.example.com')
        assert result == 'mail.example.com'

    def test_uppercase_normalized(self):
        """Domain should be lowercased"""
        result = DomainCollector.extract_domain('john@EXAMPLE.COM')
        assert result == 'example.com'

    def test_no_at_symbol(self):
        """Return empty string if no @ symbol"""
        result = DomainCollector.extract_domain('invalid')
        assert result == ''

    def test_empty_string(self):
        """Handle empty string"""
        result = DomainCollector.extract_domain('')
        assert result == ''


# === Protection Logic Tests ===

class TestIsProtected:
    """Tests for _is_protected method"""

    def test_important_label_protected(self, mock_gmail_service, default_collection_config):
        """IMPORTANT label should always protect"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        assert collector._is_protected(['INBOX', 'IMPORTANT']) is True

    def test_starred_label_protected(self, mock_gmail_service, default_collection_config):
        """STARRED label should always protect"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        assert collector._is_protected(['INBOX', 'STARRED']) is True

    def test_custom_label_protected_by_default(self, mock_gmail_service, default_collection_config):
        """Custom labels (Label_xxx) should protect by default"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        assert collector._is_protected(['INBOX', 'Label_12345']) is True

    def test_custom_label_not_protected_when_disabled(self, mock_gmail_service):
        """Custom labels should not protect when use_label_protection=False"""
        config = CollectionConfig(use_label_protection=False)
        collector = DomainCollector(mock_gmail_service, config)
        assert collector._is_protected(['INBOX', 'Label_12345']) is False

    def test_important_still_protected_when_label_protection_disabled(self, mock_gmail_service):
        """IMPORTANT should still protect even when use_label_protection=False"""
        config = CollectionConfig(use_label_protection=False)
        collector = DomainCollector(mock_gmail_service, config)
        assert collector._is_protected(['INBOX', 'IMPORTANT']) is True

    def test_specific_label_ids_only_protect_matching(self, mock_gmail_service):
        """Only specific protected_label_ids should protect when specified"""
        config = CollectionConfig(protected_label_ids={'Label_12345'})
        collector = DomainCollector(mock_gmail_service, config)

        # Matching label should protect
        assert collector._is_protected(['INBOX', 'Label_12345']) is True

        # Non-matching custom label should not protect
        assert collector._is_protected(['INBOX', 'Label_99999']) is False

    def test_regular_inbox_not_protected(self, mock_gmail_service, default_collection_config):
        """Regular INBOX label should not protect"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        assert collector._is_protected(['INBOX']) is False

    def test_empty_labels_not_protected(self, mock_gmail_service, default_collection_config):
        """Empty label list should not protect"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        assert collector._is_protected([]) is False


# === Exclusion Logic Tests ===

class TestIsExcluded:
    """Tests for _is_excluded method"""

    def test_domain_in_exclusion_list(self, mock_gmail_service):
        """Domain in excluded_domains should be excluded"""
        config = CollectionConfig(excluded_domains={'spam.com', 'junk.com'})
        collector = DomainCollector(mock_gmail_service, config)
        assert collector._is_excluded('spam.com') is True

    def test_domain_not_in_exclusion_list(self, mock_gmail_service):
        """Domain not in excluded_domains should not be excluded"""
        config = CollectionConfig(excluded_domains={'spam.com', 'junk.com'})
        collector = DomainCollector(mock_gmail_service, config)
        assert collector._is_excluded('social.com') is False

    def test_empty_exclusion_list(self, mock_gmail_service, default_collection_config):
        """No domains excluded when excluded_domains is empty"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        assert collector._is_excluded('spam.com') is False


# === Should Include Tests ===

class TestShouldInclude:
    """Tests for _should_include method"""

    def test_regular_thread_included(self, mock_gmail_service, default_collection_config):
        """Regular thread without protection/exclusion should be included"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        metadata = ThreadMetadata(
            thread_id='test',
            domain='spam.com',
            subject='Test',
            sender='test@spam.com',
            message_count=1,
            label_ids=['INBOX']
        )
        assert collector._should_include(metadata) is True

    def test_protected_thread_excluded(self, mock_gmail_service, default_collection_config):
        """Protected thread should not be included"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        metadata = ThreadMetadata(
            thread_id='test',
            domain='important.com',
            subject='Test',
            sender='test@important.com',
            message_count=1,
            label_ids=['INBOX', 'IMPORTANT']
        )
        assert collector._should_include(metadata) is False

    def test_excluded_domain_excluded(self, mock_gmail_service):
        """Thread from excluded domain should not be included"""
        config = CollectionConfig(excluded_domains={'spam.com'})
        collector = DomainCollector(mock_gmail_service, config)
        metadata = ThreadMetadata(
            thread_id='test',
            domain='spam.com',
            subject='Test',
            sender='test@spam.com',
            message_count=1,
            label_ids=['INBOX']
        )
        assert collector._should_include(metadata) is False


# === Collection Tests (Async) ===

@pytest.mark.asyncio
class TestCollect:
    """Tests for the async collect method"""

    async def test_collect_basic(self, mock_gmail_service, default_collection_config):
        """Basic collection groups threads by domain"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        result = await collector.collect()

        # Should have collected domains (excluding protected ones)
        assert len(result) > 0

        # spam.com should have 2 threads (thread_001, thread_002)
        assert 'spam.com' in result
        assert result['spam.com'].count == 2

        # social.com should have 1 thread
        assert 'social.com' in result
        assert result['social.com'].count == 1

    async def test_collect_skips_protected_threads(self, mock_gmail_service, default_collection_config):
        """Protected threads should not appear in results"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        result = await collector.collect()

        # important.com is IMPORTANT labeled - should not be in results
        assert 'important.com' not in result

        # starred.com is STARRED labeled - should not be in results
        assert 'starred.com' not in result

        # labeled.com has custom label - should not be in results
        assert 'labeled.com' not in result

    async def test_collect_with_limit(self, mock_gmail_service):
        """Collection should respect limit parameter"""
        config = CollectionConfig(limit=2)
        collector = DomainCollector(mock_gmail_service, config)
        result = await collector.collect()

        # Should have at most 2 threads total across all domains
        total_threads = sum(domain_info.count for domain_info in result.values())
        assert total_threads <= 2

    async def test_collect_skips_excluded_domains(self, mock_gmail_service):
        """Excluded domains should not appear in results"""
        config = CollectionConfig(excluded_domains={'spam.com'})
        collector = DomainCollector(mock_gmail_service, config)
        result = await collector.collect()

        # spam.com should not be in results
        assert 'spam.com' not in result

        # Other domains should still be present
        assert 'social.com' in result

    async def test_collect_empty_inbox(self, mock_gmail_service_empty, default_collection_config):
        """Empty inbox should return empty dict"""
        collector = DomainCollector(mock_gmail_service_empty, default_collection_config)
        result = await collector.collect()

        assert result == {}

    async def test_collect_stores_thread_metadata(self, mock_gmail_service, default_collection_config):
        """Collection should populate threads_by_id and threads_by_domain"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        await collector.collect()

        # Should have stored threads
        assert len(collector.threads_by_id) > 0
        assert len(collector.threads_by_domain) > 0

        # Check that spam.com threads are stored
        assert 'spam.com' in collector.threads_by_domain
        spam_thread_ids = collector.threads_by_domain['spam.com']
        assert len(spam_thread_ids) == 2

    async def test_collect_multi_message_thread(self, mock_gmail_service, default_collection_config):
        """Multi-message threads should report correct message count"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        result = await collector.collect()

        # multi.com thread has 3 messages
        assert 'multi.com' in result
        threads = result['multi.com'].threads
        assert len(threads) == 1
        assert threads[0]['message_count'] == 3

    async def test_collect_handles_edge_format(self, mock_gmail_service, default_collection_config):
        """Should handle plain email format (no angle brackets)"""
        collector = DomainCollector(mock_gmail_service, default_collection_config)
        result = await collector.collect()

        # edge.com uses plain email format
        assert 'edge.com' in result

    async def test_collect_progress_callback(self, mock_gmail_service, default_collection_config):
        """Progress callback should be called during collection"""
        progress_events = []

        async def capture_progress(event: str, data: dict):
            progress_events.append((event, data))

        collector = DomainCollector(mock_gmail_service, default_collection_config, progress_callback=capture_progress)
        await collector.collect()

        # Should have received progress events
        event_types = [e[0] for e in progress_events]
        assert 'collection_started' in event_types
        assert 'collection_completed' in event_types
        assert 'thread_processed' in event_types

    async def test_collect_with_label_protection_disabled(self, mock_gmail_service):
        """With label protection disabled, custom-labeled threads should be collected"""
        config = CollectionConfig(use_label_protection=False)
        collector = DomainCollector(mock_gmail_service, config)
        result = await collector.collect()

        # labeled.com should now be in results (custom label no longer protects)
        assert 'labeled.com' in result

        # But IMPORTANT and STARRED should still be protected
        assert 'important.com' not in result
        assert 'starred.com' not in result
