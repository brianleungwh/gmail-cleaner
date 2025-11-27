"""
Domain Collector - Handles domain collection from Gmail inbox
"""

import re
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Tuple
from collections import defaultdict

from googleapiclient.errors import HttpError

from app.models import ThreadMetadata, DomainInfo, CollectionConfig


logger = logging.getLogger(__name__)


class DomainCollector:
    """Handles domain collection from Gmail inbox"""

    def __init__(
        self,
        service,  # Gmail API service object
        config: CollectionConfig,
        progress_callback: Optional[Callable] = None
    ):
        self.service = service
        self.config = config
        self.progress_callback = progress_callback

        # Results - exposed for GmailService to access
        self.threads_by_id: Dict[str, ThreadMetadata] = {}
        self.threads_by_domain: Dict[str, List[str]] = defaultdict(list)
        self.interrupted = False

    # === Main Entry Point ===

    async def collect(self) -> Dict[str, DomainInfo]:
        """Orchestrates the collection process"""
        total_thread_count = await self._get_total_thread_count()
        effective_total = min(self.config.limit, total_thread_count) if self.config.limit else total_thread_count

        message = f"Starting domain collection (limit: {self.config.limit} threads)..." if self.config.limit else "Starting domain collection..."
        await self._report_progress("collection_started", {
            "message": message,
            "total_threads": effective_total,
            "limit": self.config.limit
        })

        # Clear any previous state
        self.threads_by_id.clear()
        self.threads_by_domain.clear()

        domain_data = defaultdict(lambda: {'count': 0, 'subjects': []})
        page_token = None
        total_threads = 0

        while not self.interrupted:
            try:
                threads, next_page_token = await self._fetch_thread_page(page_token)

                if not threads:
                    break

                for thread in threads:
                    if self.interrupted:
                        break

                    thread_id = thread['id']
                    metadata = await self._get_thread_metadata(thread_id)

                    if metadata is None:
                        continue

                    if not self._should_include(metadata):
                        continue

                    # Store thread
                    self._store_thread(metadata)

                    # Update domain data
                    domain_data[metadata.domain]['count'] += 1
                    if metadata.subject not in domain_data[metadata.domain]['subjects'] and len(domain_data[metadata.domain]['subjects']) < 3:
                        domain_data[metadata.domain]['subjects'].append(metadata.subject)

                    total_threads += 1

                    # Send progress update
                    await self._report_progress("thread_processed", {
                        "thread_id": thread_id,
                        "domain": metadata.domain,
                        "subject": metadata.subject[:60] + "..." if len(metadata.subject) > 60 else metadata.subject,
                        "processed_threads": total_threads,
                        "total_threads": effective_total,
                        "unique_domains": len(domain_data)
                    })

                    # Check limit
                    if self.config.limit and total_threads >= self.config.limit:
                        logger.info(f"Reached limit of {self.config.limit} threads, stopping collection")
                        break

                    # Yield control every 10 threads
                    if total_threads % 10 == 0:
                        await asyncio.sleep(0)

                # Check if we hit limit
                if self.config.limit and total_threads >= self.config.limit:
                    break

                page_token = next_page_token
                if not page_token:
                    break

            except HttpError as error:
                await self._report_progress("error", {"message": f"Error fetching threads: {error}"})
                break

        # Build results
        result = self._build_results(domain_data)

        limit_msg = f" (limited to {self.config.limit})" if self.config.limit else ""
        await self._report_progress("collection_completed", {
            "processed_threads": total_threads,
            "total_threads": effective_total,
            "unique_domains": len(result),
            "message": f"Collection complete{limit_msg}: {total_threads:,} threads processed, {len(result):,} unique domains"
        })

        logger.debug(f"Stored {len(self.threads_by_id)} threads across {len(self.threads_by_domain)} domains in memory")

        return result

    # === Thread Fetching ===

    async def _get_total_thread_count(self) -> int:
        """Get inbox thread count for progress reporting"""
        try:
            inbox_info = await asyncio.to_thread(
                lambda: self.service.users().labels().get(
                    userId='me',
                    id='INBOX'
                ).execute()
            )
            return inbox_info.get('threadsTotal', 0)
        except Exception as e:
            logger.warning(f"Could not get inbox thread count: {e}")
            return 0

    async def _fetch_thread_page(self, page_token: Optional[str]) -> Tuple[List[Dict], Optional[str]]:
        """Fetch a page of threads, returns (threads, next_page_token)"""
        results = await asyncio.to_thread(
            lambda: self.service.users().threads().list(
                userId='me',
                maxResults=100,
                pageToken=page_token,
                q='in:inbox'
            ).execute()
        )

        threads = results.get('threads', [])
        next_page_token = results.get('nextPageToken')

        return threads, next_page_token

    async def _get_thread_metadata(self, thread_id: str) -> Optional[ThreadMetadata]:
        """Fetch and parse metadata for a single thread"""
        thread_data = await asyncio.to_thread(
            lambda: self.service.users().threads().get(
                userId='me',
                id=thread_id,
                format='metadata',
                metadataHeaders=['From', 'Subject']
            ).execute()
        )

        messages = thread_data.get('messages', [])
        if not messages:
            return None

        first_message = messages[0]
        headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
        sender = headers.get('From', '(Unknown Sender)')
        subject = headers.get('Subject', '(No Subject)')
        sender_email = self.extract_email_address(sender)

        # Get labels from both thread and message level
        thread_label_ids = thread_data.get('labelIds', [])
        first_message_label_ids = first_message.get('labelIds', [])
        all_label_ids = list(set(thread_label_ids + first_message_label_ids))

        domain = self.extract_domain(sender_email)
        if not domain:
            return None

        return ThreadMetadata(
            thread_id=thread_id,
            domain=domain,
            subject=subject,
            sender=sender_email,
            message_count=len(messages),
            label_ids=all_label_ids
        )

    # === Filtering ===

    def _is_protected(self, label_ids: List[str]) -> bool:
        """Check if thread is protected by labels (IMPORTANT, STARRED, custom)"""
        # Always protect IMPORTANT and STARRED
        if 'IMPORTANT' in label_ids or 'STARRED' in label_ids:
            logger.debug("Protected by IMPORTANT/STARRED")
            return True

        # Skip label protection if disabled
        if not self.config.use_label_protection:
            return False

        # Check for custom user labels
        custom_labels = [label for label in label_ids if label.startswith('Label_')]
        if not custom_labels:
            return False

        # If specific labels provided, only protect those
        if self.config.protected_label_ids is not None:
            protected = any(label in self.config.protected_label_ids for label in custom_labels)
            if protected:
                matching = [l for l in custom_labels if l in self.config.protected_label_ids]
                logger.debug(f"Protected by selected labels: {matching}")
            return protected

        # Otherwise protect any custom label (default behavior)
        logger.debug(f"Protected by custom labels: {custom_labels}")
        return True

    def _is_excluded(self, domain: str) -> bool:
        """Check if domain is in exclusion list"""
        return domain in self.config.excluded_domains

    def _should_include(self, metadata: ThreadMetadata) -> bool:
        """Determine if thread should be included in results"""
        if self._is_protected(metadata.label_ids):
            logger.debug(f"COLLECT - SKIPPING PROTECTED thread {metadata.thread_id} with labels: {metadata.label_ids}")
            return False

        if self._is_excluded(metadata.domain):
            logger.debug(f"COLLECT - SKIPPING EXCLUDED domain: {metadata.domain}")
            return False

        return True

    # === Storage ===

    def _store_thread(self, metadata: ThreadMetadata) -> None:
        """Store thread in internal dictionaries"""
        self.threads_by_id[metadata.thread_id] = metadata
        self.threads_by_domain[metadata.domain].append(metadata.thread_id)

    # === Results ===

    def _build_results(self, domain_data: Dict) -> Dict[str, DomainInfo]:
        """Aggregate stored threads into DomainInfo objects"""
        result = {}

        for domain, data in domain_data.items():
            thread_ids = self.threads_by_domain.get(domain, [])
            threads = []

            for thread_id in thread_ids:
                metadata = self.threads_by_id.get(thread_id)
                if metadata:
                    threads.append({
                        'thread_id': thread_id,
                        'subject': metadata.subject,
                        'sender': metadata.sender,
                        'message_count': metadata.message_count
                    })

            result[domain] = DomainInfo(
                domain=domain,
                count=data['count'],
                threads=threads
            )

        return result

    # === Progress ===

    async def _report_progress(self, event: str, data: Dict) -> None:
        """Send progress update if callback is set"""
        if self.progress_callback:
            await self.progress_callback(event, data)

    # === Utilities ===

    @staticmethod
    def extract_email_address(sender: str) -> str:
        """Extract email from 'Name <email@domain.com>' format"""
        match = re.search(r'<([^>]+)>', sender)
        if match:
            return match.group(1).lower()
        return sender.strip().lower()

    @staticmethod
    def extract_domain(email: str) -> str:
        """Extract domain from email address"""
        if '@' in email:
            return email.split('@')[1].lower()
        return ''
