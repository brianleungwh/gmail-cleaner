#!/usr/bin/env python3
"""
Gmail Service - Reusable service class for Gmail operations
"""

import os
import json
import signal
import sys
import re
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set, Callable
from dataclasses import dataclass
from collections import defaultdict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set up logger
logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


@dataclass
class DomainInfo:
    """Domain information for collection"""
    domain: str
    count: int
    sample_subjects: List[str]


class GmailService:
    def __init__(self, credentials_path: str = 'data/credentials.json', token_path: str = 'data/token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.interrupted = False
        self.flow = None  # OAuth flow instance

        # Progress callback for real-time updates
        self.progress_callback: Optional[Callable] = None

        # Thread storage for efficient cleanup
        self.threads_by_id: Dict[str, Dict] = {}  # thread_id -> {domain, subject, sender, message_count}
        self.threads_by_domain: Dict[str, List[str]] = defaultdict(list)  # domain -> [thread_ids]

        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_interrupt)
    
    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        if not self.interrupted:
            self.interrupted = True
        else:
            sys.exit(1)
    
    def set_progress_callback(self, callback: Callable[[str, Dict], None]):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    async def _log_progress(self, message: str, data: Dict = None):
        """Send progress update via callback"""
        if self.progress_callback:
            await self.progress_callback(message, data or {})
    
    def _log_progress_sync(self, message: str, data: Dict = None):
        """Send progress update via callback (sync version for authenticate)"""
        if self.progress_callback:
            # For sync methods, we can't await, so we'll just ignore progress
            pass
    
    def create_oauth_flow(self, redirect_uri: str = None) -> str:
        """Create OAuth2 flow and return authorization URL"""
        import os
        
        if not os.path.exists(self.credentials_path):
            raise Exception("Credentials file not found. Please upload credentials.json first.")
        
        # Use credentials file to create flow
        self.flow = Flow.from_client_secrets_file(
            self.credentials_path,
            scopes=SCOPES,
            redirect_uri=redirect_uri or "http://localhost:8000/oauth/callback"
        )
        
        # Generate authorization URL
        auth_url, _ = self.flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        return auth_url
    
    def complete_oauth_flow(self, authorization_code: str) -> bool:
        """Complete OAuth flow with authorization code"""
        try:
            if not self.flow:
                raise Exception("OAuth flow not initialized. Call create_oauth_flow first.")
            
            # Exchange authorization code for credentials
            self.flow.fetch_token(code=authorization_code)
            
            # Save credentials
            creds = self.flow.credentials
            token_path = Path(self.token_path)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())
            
            # Build service
            self.service = build('gmail', 'v1', credentials=creds)
            self._log_progress_sync("authenticated", {"message": "Successfully authenticated with Gmail"})
            return True
            
        except Exception as error:
            self._log_progress_sync("error", {"message": f"OAuth authentication failed: {error}"})
            return False
    
    def authenticate(self) -> bool:
        """Check if already authenticated and refresh credentials if needed

        This method only handles existing credentials. For new authentication,
        use create_oauth_flow() and complete_oauth_flow() instead.
        """
        try:
            token_path = Path(self.token_path)

            # Only try to authenticate if token already exists
            if not token_path.exists():
                logger.info("No existing token found - user needs to authenticate via OAuth")
                return False

            # Load existing credentials
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

            # Check if valid or can be refreshed
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired credentials")
                    creds.refresh(Request())
                    # Save refreshed credentials
                    token_path.write_text(creds.to_json())
                else:
                    logger.warning("Credentials invalid and cannot be refreshed - user needs to re-authenticate")
                    return False

            # Build service with valid credentials
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Successfully authenticated with existing credentials")
            return True

        except Exception as error:
            logger.error(f"Authentication failed: {error}")
            return False
    
    def _extract_email_address(self, sender: str) -> str:
        """Extract email address from sender string like 'Name <email@domain.com>'"""
        # Try to extract email from angle brackets
        match = re.search(r'<([^>]+)>', sender)
        if match:
            return match.group(1).lower()
        # If no angle brackets, assume the whole string is the email
        return sender.strip().lower()
    
    def _extract_domain(self, email: str) -> str:
        """Extract domain from email address"""
        if '@' in email:
            return email.split('@')[1].lower()
        return ''
    
    def _is_thread_protected(self, label_ids: List[str]) -> bool:
        """Check if a thread should be protected from deletion based on its labels"""
        # Check for important or starred
        if 'IMPORTANT' in label_ids or 'STARRED' in label_ids:
            logger.debug("Protected by IMPORTANT/STARRED")
            return True

        # Check for custom user labels
        custom_labels = [label for label in label_ids if label.startswith('Label_')]
        if custom_labels:
            logger.debug(f"Protected by custom labels: {custom_labels}")
            return True

        # Check for other system labels that might indicate user organization
        # Categories are user-applied in Gmail
        category_labels = [label for label in label_ids if label.startswith('CATEGORY_')]
        if category_labels:
            logger.debug(f"Has category labels (not protected): {category_labels}")

        return False
    
    async def collect_domains(self, limit: Optional[int] = None) -> Dict[str, DomainInfo]:
        """Collect all unique sender domains from inbox

        Args:
            limit: Optional limit on number of threads to process
        """
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")

        # Get total thread count first for accurate progress
        try:
            inbox_info = await asyncio.to_thread(
                lambda: self.service.users().labels().get(
                    userId='me',
                    id='INBOX'
                ).execute()
            )
            total_thread_count = inbox_info.get('threadsTotal', 0)
        except Exception as e:
            logger.warning(f"Could not get inbox thread count: {e}")
            total_thread_count = 0

        # If limit is set, use it as the effective total
        effective_total = min(limit, total_thread_count) if limit else total_thread_count

        message = f"Starting domain collection (limit: {limit} threads)..." if limit else "Starting domain collection..."
        await self._log_progress("collection_started", {
            "message": message,
            "total_threads": effective_total,
            "limit": limit
        })

        # Clear previous thread storage for fresh scan
        self.threads_by_id.clear()
        self.threads_by_domain.clear()
        logger.debug("Cleared thread storage for new scan")

        # Dictionary to store domain info: domain -> {count, subjects}
        domain_data = defaultdict(lambda: {'count': 0, 'subjects': []})
        page_token = None
        total_threads = 0
        
        while True:
            if self.interrupted:
                break
            
            try:
                # Get ALL threads from inbox (no filtering)
                # Run in thread pool to avoid blocking event loop
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
                
                if not threads:
                    break
                
                for thread in threads:
                    if self.interrupted:
                        break
                    
                    thread_id = thread['id']
                    
                    # Get thread details - run in thread pool
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
                        continue

                    # Get first message info
                    first_message = messages[0]
                    headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
                    sender = headers.get('From', '(Unknown Sender)')
                    subject = headers.get('Subject', '(No Subject)')
                    sender_email = self._extract_email_address(sender)

                    # DEBUG: Check labels during collection
                    thread_label_ids = thread_data.get('labelIds', [])
                    first_message_label_ids = first_message.get('labelIds', [])
                    all_label_ids = list(set(thread_label_ids + first_message_label_ids))

                    logger.debug(f"COLLECT - Thread {thread_id}: subject='{subject[:40]}', thread_labels={thread_label_ids}, message_labels={first_message_label_ids}, combined={all_label_ids}")

                    # Check if protected - skip if so
                    if self._is_thread_protected(all_label_ids):
                        logger.debug(f"COLLECT - SKIPPING PROTECTED thread {thread_id} with labels: {all_label_ids}")
                        continue  # Skip protected threads from domain collection

                    # Extract domain from email
                    domain = self._extract_domain(sender_email)
                    if not domain:
                        continue  # Skip if no valid domain
                    
                    # Store domain data
                    domain_data[domain]['count'] += 1
                    # Keep only first 3 unique subjects as examples
                    if subject not in domain_data[domain]['subjects'] and len(domain_data[domain]['subjects']) < 3:
                        domain_data[domain]['subjects'].append(subject)

                    # Store thread metadata for efficient cleanup
                    message_count = len(messages)
                    self.threads_by_id[thread_id] = {
                        'domain': domain,
                        'subject': subject,
                        'sender': sender_email,
                        'message_count': message_count
                    }
                    self.threads_by_domain[domain].append(thread_id)

                    total_threads += 1

                    # Send progress update
                    await self._log_progress("thread_processed", {
                        "thread_id": thread_id,
                        "domain": domain,
                        "subject": subject[:60] + "..." if len(subject) > 60 else subject,
                        "processed_threads": total_threads,
                        "total_threads": effective_total,
                        "unique_domains": len(domain_data)
                    })

                    # Check if we've hit the limit
                    if limit and total_threads >= limit:
                        logger.info(f"Reached limit of {limit} threads, stopping collection")
                        break

                    # Yield control to event loop every 10 threads for real-time updates
                    if total_threads % 10 == 0:
                        await asyncio.sleep(0)

                # Break outer loop if we hit the limit
                if limit and total_threads >= limit:
                    break
                
                page_token = next_page_token
                if not page_token:
                    break
                    
            except HttpError as error:
                await self._log_progress("error", {"message": f"Error fetching threads: {error}"})
                break
        
        # Convert to DomainInfo objects
        result = {}
        for domain, data in domain_data.items():
            # Truncate long subjects
            truncated_subjects = []
            for subject in data['subjects']:
                if len(subject) > 60:
                    subject = subject[:57] + "..."
                truncated_subjects.append(subject)
            
            result[domain] = DomainInfo(
                domain=domain,
                count=data['count'],
                sample_subjects=truncated_subjects
            )
        
        limit_msg = f" (limited to {limit})" if limit else ""
        await self._log_progress("collection_completed", {
            "processed_threads": total_threads,
            "total_threads": effective_total,
            "unique_domains": len(result),
            "message": f"Collection complete{limit_msg}: {total_threads:,} threads processed, {len(result):,} unique domains"
        })

        # Debug: Log thread storage stats
        total_stored_threads = len(self.threads_by_id)
        logger.debug(f"Stored {total_stored_threads} threads across {len(self.threads_by_domain)} domains in memory")

        return result

    def get_threads_for_domains(self, domains: Set[str]) -> List[Dict]:
        """Get stored thread metadata for selected domains

        Args:
            domains: Set of domain names to get threads for

        Returns:
            List of thread metadata dicts with keys: thread_id, domain, subject, sender, message_count
        """
        threads = []
        for domain in domains:
            thread_ids = self.threads_by_domain.get(domain, [])
            for thread_id in thread_ids:
                thread_metadata = self.threads_by_id.get(thread_id)
                if thread_metadata:
                    threads.append({
                        'thread_id': thread_id,
                        **thread_metadata  # Spread the metadata dict
                    })

        logger.debug(f"Retrieved {len(threads)} threads for {len(domains)} selected domains")
        return threads

    async def cleanup_emails(self, junk_domains: Set[str], dry_run: bool = True, total_limit: Optional[int] = None) -> Dict[str, int]:
        """Clean up emails based on junk domains list using stored thread data"""
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")

        # Get threads for selected domains from storage
        threads_to_process = self.get_threads_for_domains(junk_domains)

        if not threads_to_process:
            logger.warning("No threads found for selected domains. Did you run a scan first?")
            return {
                "threads_processed": 0,
                "threads_deleted": 0,
                "messages_deleted": 0,
                "messages_kept": 0
            }

        # Apply limit if specified
        if total_limit and len(threads_to_process) > total_limit:
            threads_to_process = threads_to_process[:total_limit]
            logger.debug(f"Limited to {total_limit} threads (from {len(self.get_threads_for_domains(junk_domains))} total)")

        await self._log_progress("cleanup_started", {
            "domains_count": len(junk_domains),
            "dry_run": dry_run,
            "limit": total_limit,
            "threads_to_process": len(threads_to_process)
        })

        total_processed = 0
        threads_deleted = 0
        messages_deleted = 0
        messages_kept = 0

        # Process each thread from storage
        for thread_metadata in threads_to_process:
            if self.interrupted:
                break

            thread_id = thread_metadata['thread_id']
            domain = thread_metadata['domain']
            subject = thread_metadata['subject']
            sender = thread_metadata['sender']
            message_count = thread_metadata['message_count']

            # Log what we're analyzing
            await self._log_progress("thread_analyzed", {
                "thread_id": thread_id,
                "subject": subject[:50] + "..." if len(subject) > 50 else subject,
                "sender": sender
            })

            # All threads from selected domains should be deleted
            # (already filtered out protected threads during scan)
            if dry_run:
                await self._log_progress("would_delete", {
                    "thread_id": thread_id,
                    "subject": subject[:50] + "..." if len(subject) > 50 else subject,
                    "sender": sender,
                    "message_count": message_count
                })
                threads_deleted += 1
                messages_deleted += message_count
            else:
                # Actually delete the thread
                try:
                    await asyncio.to_thread(
                        lambda: self.service.users().threads().trash(userId='me', id=thread_id).execute()
                    )

                    await self._log_progress("deleted", {
                        "thread_id": thread_id,
                        "subject": subject[:50] + "..." if len(subject) > 50 else subject,
                        "sender": sender,
                        "message_count": message_count
                    })
                    threads_deleted += 1
                    messages_deleted += message_count

                except HttpError as error:
                    # Thread might not exist anymore (e.g., already deleted)
                    await self._log_progress("delete_error", {
                        "thread_id": thread_id,
                        "error": str(error)
                    })
                    messages_kept += message_count

            total_processed += 1

        result = {
            "threads_processed": total_processed,
            "threads_deleted": threads_deleted,
            "messages_deleted": messages_deleted,
            "messages_kept": messages_kept
        }

        await self._log_progress("cleanup_completed", result)
        return result