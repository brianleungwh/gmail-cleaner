"""
Domain Cleaner - Handles email cleanup for selected domains
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable

from googleapiclient.errors import HttpError

from app.models import CleanupConfig


logger = logging.getLogger(__name__)


class DomainCleaner:
    """Handles email cleanup for selected domains"""

    def __init__(
        self,
        service,  # Gmail API service object
        config: CleanupConfig,
        progress_callback: Optional[Callable] = None
    ):
        self.service = service
        self.config = config
        self.progress_callback = progress_callback
        self.interrupted = False

    # === Main Entry Point ===

    async def cleanup(self, threads: List[Dict]) -> Dict[str, int]:
        """Clean up provided threads, returns stats dict"""
        if not threads:
            logger.warning("No threads provided for cleanup")
            return self._build_stats(0, 0, 0, 0)

        await self._report_progress("cleanup_started", {
            "dry_run": self.config.dry_run,
            "limit": self.config.limit,
            "threads_to_process": len(threads)
        })

        total_processed = 0
        threads_deleted = 0
        messages_deleted = 0
        messages_kept = 0

        for thread in threads:
            if self.interrupted:
                break

            thread_id = thread['thread_id']
            domain = thread['domain']
            subject = thread['subject']
            sender = thread['sender']
            message_count = thread['message_count']

            # Log what we're analyzing
            await self._report_progress("thread_analyzed", {
                "thread_id": thread_id,
                "subject": subject[:50] + "..." if len(subject) > 50 else subject,
                "sender": sender
            })

            if self.config.dry_run:
                # Dry run - just report what would happen
                await self._report_progress("would_delete", {
                    "thread_id": thread_id,
                    "subject": subject[:50] + "..." if len(subject) > 50 else subject,
                    "sender": sender,
                    "message_count": message_count
                })
                threads_deleted += 1
                messages_deleted += message_count
            else:
                # Actually delete the thread
                success = await self._trash_thread(thread_id)

                if success:
                    await self._report_progress("deleted", {
                        "thread_id": thread_id,
                        "subject": subject[:50] + "..." if len(subject) > 50 else subject,
                        "sender": sender,
                        "message_count": message_count
                    })
                    threads_deleted += 1
                    messages_deleted += message_count
                else:
                    await self._report_progress("delete_error", {
                        "thread_id": thread_id,
                        "error": "Failed to trash thread"
                    })
                    messages_kept += message_count

            total_processed += 1

        result = self._build_stats(total_processed, threads_deleted, messages_deleted, messages_kept)
        await self._report_progress("cleanup_completed", result)

        return result

    # === Thread Processing ===

    async def _trash_thread(self, thread_id: str) -> bool:
        """Move thread to trash, returns success"""
        try:
            await asyncio.to_thread(
                lambda: self.service.users().threads().trash(
                    userId='me',
                    id=thread_id
                ).execute()
            )
            return True
        except HttpError as error:
            logger.error(f"Error trashing thread {thread_id}: {error}")
            return False

    # === Progress ===

    async def _report_progress(self, event: str, data: Dict) -> None:
        """Send progress update if callback is set"""
        if self.progress_callback:
            await self.progress_callback(event, data)

    # === Results ===

    @staticmethod
    def _build_stats(processed: int, deleted: int, messages_deleted: int, kept: int) -> Dict[str, int]:
        """Build result statistics dict"""
        return {
            "threads_processed": processed,
            "threads_deleted": deleted,
            "messages_deleted": messages_deleted,
            "messages_kept": kept
        }
