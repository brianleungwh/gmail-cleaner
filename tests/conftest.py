"""
Shared test fixtures for Gmail Cleaner tests
"""

import pytest
from typing import Dict, List, Optional, Set
from googleapiclient.errors import HttpError

from app.models import CollectionConfig, CleanupConfig


# === Mock Gmail API Service ===

class MockExecute:
    """Mock for the .execute() call that returns stored data"""
    def __init__(self, data):
        self._data = data

    def execute(self):
        return self._data


class MockLabelsGet:
    """Mock for labels().get()"""
    def __init__(self, inbox_data: dict):
        self._inbox_data = inbox_data

    def get(self, userId: str, id: str):
        if id == 'INBOX':
            return MockExecute({
                'id': 'INBOX',
                'name': 'INBOX',
                'threadsTotal': self._inbox_data.get('threads_total', 0)
            })
        return MockExecute({})


class MockThreadsList:
    """Mock for threads().list()"""
    def __init__(self, inbox_data: dict, page_size: int = 100):
        self._inbox_data = inbox_data
        self._page_size = page_size

    def list(self, userId: str, maxResults: int = 100, pageToken: Optional[str] = None, q: str = None):
        threads = self._inbox_data.get('threads', [])

        # Handle pagination
        start_idx = 0
        if pageToken:
            start_idx = int(pageToken)

        end_idx = min(start_idx + maxResults, len(threads))
        page_threads = threads[start_idx:end_idx]

        # Only include id in list response (like real API)
        thread_list = [{'id': t['id']} for t in page_threads]

        result = {'threads': thread_list}

        # Add nextPageToken if there are more threads
        if end_idx < len(threads):
            result['nextPageToken'] = str(end_idx)

        return MockExecute(result)


class MockThreadsGet:
    """Mock for threads().get()"""
    def __init__(self, inbox_data: dict):
        self._inbox_data = inbox_data
        self._threads_by_id = {t['id']: t for t in inbox_data.get('threads', [])}

    def get(self, userId: str, id: str, format: str = None, metadataHeaders: List[str] = None):
        thread = self._threads_by_id.get(id)
        if thread:
            return MockExecute(thread)
        # Return empty thread if not found
        return MockExecute({'id': id, 'messages': []})


class MockHttpResponse:
    """Mock HTTP response for HttpError"""
    def __init__(self, status: int, reason: str):
        self.status = status
        self.reason = reason


class MockThreadsTrash:
    """Mock for threads().trash()"""
    def __init__(self, trashed_threads: Set[str], fail_threads: Set[str] = None):
        self._trashed_threads = trashed_threads
        self._fail_threads = fail_threads or set()

    def trash(self, userId: str, id: str):
        if id in self._fail_threads:
            # Simulate API error with proper response object
            resp = MockHttpResponse(404, 'Not Found')
            raise HttpError(resp=resp, content=b'Thread not found')
        self._trashed_threads.add(id)
        return MockExecute({'id': id, 'labelIds': ['TRASH']})


class MockThreads:
    """Mock for users().threads()"""
    def __init__(self, inbox_data: dict, trashed_threads: Set[str], fail_threads: Set[str] = None):
        self._list = MockThreadsList(inbox_data)
        self._get = MockThreadsGet(inbox_data)
        self._trash = MockThreadsTrash(trashed_threads, fail_threads)

    def list(self, **kwargs):
        return self._list.list(**kwargs)

    def get(self, **kwargs):
        return self._get.get(**kwargs)

    def trash(self, **kwargs):
        return self._trash.trash(**kwargs)


class MockLabels:
    """Mock for users().labels()"""
    def __init__(self, inbox_data: dict):
        self._get = MockLabelsGet(inbox_data)

    def get(self, **kwargs):
        return self._get.get(**kwargs)


class MockUsers:
    """Mock for service.users()"""
    def __init__(self, inbox_data: dict, trashed_threads: Set[str], fail_threads: Set[str] = None):
        self._threads = MockThreads(inbox_data, trashed_threads, fail_threads)
        self._labels = MockLabels(inbox_data)

    def threads(self):
        return self._threads

    def labels(self):
        return self._labels


class MockGmailService:
    """Mock Gmail API service that simulates a realistic inbox"""

    def __init__(self, inbox_data: dict, fail_threads: Set[str] = None):
        self._inbox_data = inbox_data
        self._trashed_threads: Set[str] = set()
        self._fail_threads = fail_threads or set()

    def users(self):
        return MockUsers(self._inbox_data, self._trashed_threads, self._fail_threads)

    @property
    def trashed_threads(self) -> Set[str]:
        """Get the set of thread IDs that have been trashed"""
        return self._trashed_threads


# === Helper to create thread data ===

def make_thread(
    thread_id: str,
    sender: str,
    subject: str,
    labels: List[str] = None,
    message_count: int = 1
) -> dict:
    """Helper to create a thread dict matching Gmail API structure"""
    labels = labels or ['INBOX']

    messages = []
    for i in range(message_count):
        messages.append({
            'id': f'{thread_id}_msg_{i}',
            'labelIds': labels,
            'payload': {
                'headers': [
                    {'name': 'From', 'value': sender},
                    {'name': 'Subject', 'value': subject}
                ]
            }
        })

    return {
        'id': thread_id,
        'labelIds': labels,
        'messages': messages
    }


def make_thread_no_messages(thread_id: str) -> dict:
    """Create a thread with no messages (edge case)"""
    return {
        'id': thread_id,
        'labelIds': ['INBOX'],
        'messages': []
    }


def make_thread_no_from_header(thread_id: str, subject: str) -> dict:
    """Create a thread with missing From header"""
    return {
        'id': thread_id,
        'labelIds': ['INBOX'],
        'messages': [{
            'id': f'{thread_id}_msg_0',
            'labelIds': ['INBOX'],
            'payload': {
                'headers': [
                    {'name': 'Subject', 'value': subject}
                ]
            }
        }]
    }


# === Fixtures ===

@pytest.fixture
def sample_inbox() -> dict:
    """Returns a realistic inbox data structure with various thread types"""
    threads = [
        # Regular collectible threads
        make_thread('thread_001', 'Newsletter <newsletter@spam.com>', 'Buy now! 50% off', ['INBOX']),
        make_thread('thread_002', 'Promo <promo@spam.com>', 'Limited time offer', ['INBOX']),
        make_thread('thread_003', 'Updates <updates@social.com>', 'New friend request', ['INBOX']),

        # Protected threads
        make_thread('thread_004', 'Boss <boss@important.com>', 'Q4 Review', ['INBOX', 'IMPORTANT']),
        make_thread('thread_005', 'Friend <friend@starred.com>', 'Party invite', ['INBOX', 'STARRED']),
        make_thread('thread_006', 'Bank <bank@labeled.com>', 'Statement', ['INBOX', 'Label_12345']),

        # Multi-message thread
        make_thread('thread_007', 'Support <support@multi.com>', 'Ticket #1234', ['INBOX'], message_count=3),

        # Plain email format (no angle brackets)
        make_thread('thread_008', 'plain@edge.com', 'Plain sender format', ['INBOX']),

        # Edge cases
        make_thread_no_messages('thread_009'),
        make_thread_no_from_header('thread_010', 'No sender thread'),
    ]

    return {
        'threads_total': len(threads),
        'threads': threads
    }


@pytest.fixture
def mock_gmail_service(sample_inbox) -> MockGmailService:
    """Returns a MockGmailService with the sample inbox"""
    return MockGmailService(sample_inbox)


@pytest.fixture
def mock_gmail_service_with_failures(sample_inbox) -> MockGmailService:
    """Returns a MockGmailService that fails to trash certain threads"""
    return MockGmailService(sample_inbox, fail_threads={'thread_001'})


@pytest.fixture
def empty_inbox() -> dict:
    """Returns an empty inbox"""
    return {
        'threads_total': 0,
        'threads': []
    }


@pytest.fixture
def mock_gmail_service_empty(empty_inbox) -> MockGmailService:
    """Returns a MockGmailService with an empty inbox"""
    return MockGmailService(empty_inbox)


@pytest.fixture
def default_collection_config() -> CollectionConfig:
    """Default CollectionConfig for tests"""
    return CollectionConfig()


@pytest.fixture
def default_cleanup_config() -> CleanupConfig:
    """Default CleanupConfig for tests (dry run)"""
    return CleanupConfig(dry_run=True)


@pytest.fixture
def live_cleanup_config() -> CleanupConfig:
    """CleanupConfig for live (non-dry-run) tests"""
    return CleanupConfig(dry_run=False)
