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
from pathlib import Path
from typing import List, Dict, Optional, Set, Callable
from dataclasses import dataclass
from collections import defaultdict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


@dataclass
class ThreadInfo:
    """Thread information for processing"""
    id: str
    messages: List[Dict]  # List of message data from the thread


@dataclass
class JunkDetectionResult:
    """Result of junk detection with scoring details"""
    is_junk: bool
    score: float
    reasons: List[str]
    confidence: str  # 'high', 'medium', 'low'


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
        """Authenticate with Gmail API"""
        try:
            creds = None
            token_path = Path(self.token_path)
            
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_path):
                        self._log_progress_sync("error", {"message": "Gmail credentials file not found"})
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Save the credentials for the next run
                token_path.write_text(creds.to_json())
            
            self.service = build('gmail', 'v1', credentials=creds)
            self._log_progress_sync("authenticated", {"message": "Successfully authenticated with Gmail"})
            return True
            
        except Exception as error:
            self._log_progress_sync("error", {"message": f"Authentication failed: {error}"})
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
            print(f"DEBUG - Protected by IMPORTANT/STARRED", flush=True)
            return True

        # Check for custom user labels
        custom_labels = [label for label in label_ids if label.startswith('Label_')]
        if custom_labels:
            print(f"DEBUG - Protected by custom labels: {custom_labels}", flush=True)
            return True

        # Check for other system labels that might indicate user organization
        # Categories are user-applied in Gmail
        category_labels = [label for label in label_ids if label.startswith('CATEGORY_')]
        if category_labels:
            print(f"DEBUG - Has category labels (not protected): {category_labels}", flush=True)

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
            print(f"Could not get inbox thread count: {e}")
            total_thread_count = 0

        # If limit is set, use it as the effective total
        effective_total = min(limit, total_thread_count) if limit else total_thread_count

        message = f"Starting domain collection (limit: {limit} threads)..." if limit else "Starting domain collection..."
        await self._log_progress("collection_started", {
            "message": message,
            "total_threads": effective_total,
            "limit": limit
        })
        
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

                    print(f"DEBUG COLLECT - Thread {thread_id}: subject='{subject[:40]}', thread_labels={thread_label_ids}, message_labels={first_message_label_ids}, combined={all_label_ids}", flush=True)

                    # Check if protected - skip if so
                    if self._is_thread_protected(all_label_ids):
                        print(f"DEBUG COLLECT - SKIPPING PROTECTED thread {thread_id} with labels: {all_label_ids}", flush=True)
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
                        print(f"Reached limit of {limit} threads, stopping collection", flush=True)
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
        
        return result
    
    async def cleanup_emails(self, junk_domains: Set[str], dry_run: bool = True, total_limit: Optional[int] = None) -> Dict[str, int]:
        """Clean up emails based on junk domains list"""
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")

        await self._log_progress("cleanup_started", {
            "domains_count": len(junk_domains),
            "dry_run": dry_run,
            "limit": total_limit
        })

        page_token = None
        total_processed = 0
        threads_deleted = 0
        messages_deleted = 0
        messages_kept = 0
        batch_size = 100

        # Build Gmail search query to only get threads from selected domains
        # Format: "from:@domain1.com OR from:@domain2.com OR ..."
        domain_query_parts = [f"from:@{domain}" for domain in junk_domains]
        search_query = f"in:inbox ({' OR '.join(domain_query_parts)})"

        print(f"DEBUG - Cleanup search query: {search_query[:200]}...", flush=True)

        while True:
            if self.interrupted:
                break

            # Check if we've reached the limit
            if total_limit and total_processed >= total_limit:
                break

            # Adjust batch size if approaching limit
            current_batch_size = batch_size
            if total_limit and (total_processed + batch_size > total_limit):
                current_batch_size = total_limit - total_processed

            # Fetch batch of threads using domain-filtered query
            threads, next_page_token = await self.get_threads_batch(page_token, current_batch_size, search_query=search_query)
            
            # Only break if no threads AND no more pages
            if not threads and not next_page_token:
                break
            
            # Update page token for next iteration
            page_token = next_page_token
            
            # Skip to next batch if current batch is empty but there are more pages
            if not threads:
                continue
            
            # Truncate threads list if it would exceed the limit
            if total_limit and (total_processed + len(threads) > total_limit):
                threads = threads[:total_limit - total_processed]
            
            # Process each thread
            for thread in threads:
                detection = self.detect_junk(thread, junk_domains)
                
                if detection.is_junk:
                    if await self.delete_thread(thread, dry_run):
                        threads_deleted += 1
                        # Count all messages in thread as deleted
                        thread_messages = len([m for m in thread.messages if 'INBOX' in m.get('labelIds', [])])
                        messages_deleted += thread_messages
                else:
                    # Count messages kept
                    thread_messages = len([m for m in thread.messages if 'INBOX' in m.get('labelIds', [])])
                    messages_kept += thread_messages
                
                total_processed += 1
                
                # Stop if we've reached the limit
                if total_limit and total_processed >= total_limit:
                    break
        
        result = {
            "threads_processed": total_processed,
            "threads_deleted": threads_deleted,
            "messages_deleted": messages_deleted,
            "messages_kept": messages_kept
        }
        
        await self._log_progress("cleanup_completed", result)
        return result
    
    def detect_junk(self, thread: ThreadInfo, junk_domains: Set[str]) -> JunkDetectionResult:
        """Determine if thread should be deleted based on junk sender domains"""
        # Check the first message's sender domain against junk domains
        if thread.messages:
            first_message = thread.messages[0]
            headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
            sender = headers.get('From', '(Unknown Sender)')
            sender_email = self._extract_email_address(sender)
            sender_domain = self._extract_domain(sender_email)
            
            # Check if sender domain is in junk domains list
            if sender_domain in junk_domains:
                return JunkDetectionResult(
                    is_junk=True,
                    score=100,
                    reasons=[f"Domain '{sender_domain}' is in junk domains list"],
                    confidence='high'
                )
        
        # Keep threads from domains not in junk list
        return JunkDetectionResult(
            is_junk=False,
            score=0,
            reasons=["Domain not in junk list"],
            confidence='high'
        )
    
    async def get_threads_batch(self, page_token: Optional[str] = None, batch_size: int = 100, search_query: Optional[str] = None) -> tuple[List[ThreadInfo], Optional[str]]:
        """Fetch a batch of threads and their messages for processing

        Args:
            page_token: Token for pagination
            batch_size: Number of threads to fetch
            search_query: Gmail search query (defaults to 'in:inbox' if None)
        """
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")

        try:
            # Use provided search query or default to inbox
            query = search_query if search_query else 'in:inbox'

            # Get threads matching the query
            results = self.service.users().threads().list(
                userId='me',
                maxResults=batch_size,
                pageToken=page_token,
                q=query
            ).execute()
            
            threads = results.get('threads', [])
            next_page_token = results.get('nextPageToken')
            
            if not threads:
                return [], next_page_token
            
            threads_to_process = []
            threads_protected = 0
            
            for thread in threads:
                thread_id = thread['id']
                
                # Get full thread details with all messages
                thread_data = self.service.users().threads().get(
                    userId='me',
                    id=thread_id,
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                messages = thread_data.get('messages', [])
                if not messages:
                    continue  # Skip empty threads
                
                # Check ONLY the first message in the thread for protection
                first_message = messages[0]
                headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
                subject = headers.get('Subject', '(No Subject)')
                sender = headers.get('From', '(Unknown Sender)')
                sender_email = self._extract_email_address(sender)

                # Get labels from both thread and first message
                thread_label_ids = thread_data.get('labelIds', [])
                first_message_label_ids = first_message.get('labelIds', [])

                # Combine both sets of labels for checking
                all_label_ids = list(set(thread_label_ids + first_message_label_ids))

                # DEBUG: Log labels for investigation
                print(f"DEBUG - Thread {thread_id}: thread_labels={thread_label_ids}, message_labels={first_message_label_ids}, combined={all_label_ids}", flush=True)

                # Check if thread is protected (based on combined labels)
                if self._is_thread_protected(all_label_ids):
                    threads_protected += 1
                    print(f"DEBUG - PROTECTED thread {thread_id} with labels: {all_label_ids}", flush=True)
                    continue  # Skip protected thread
                
                # Add unprotected thread to list for processing
                thread_info = ThreadInfo(
                    id=thread_id,
                    messages=messages
                )
                threads_to_process.append(thread_info)
                
                # Log thread processing
                await self._log_progress("thread_analyzed", {
                    "thread_id": thread_id,
                    "subject": subject[:40] + "..." if len(subject) > 40 else subject,
                    "sender": sender_email
                })
            
            if threads_to_process or threads_protected:
                await self._log_progress("batch_processed", {
                    "unprotected_threads": len(threads_to_process),
                    "protected_threads": threads_protected
                })
            
            return threads_to_process, next_page_token
            
        except HttpError as error:
            await self._log_progress("error", {"message": f"An error occurred: {error}"})
            return [], None
    
    async def delete_thread(self, thread: ThreadInfo, dry_run: bool = True) -> bool:
        """Move thread to trash"""
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        # Get first message info for display
        if not thread.messages:
            return False
        
        first_message = thread.messages[0]
        headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
        subject = headers.get('Subject', '(No Subject)')
        sender = headers.get('From', '(Unknown Sender)')
        sender_email = self._extract_email_address(sender)
        
        messages_count = len(thread.messages)
        
        if dry_run:
            await self._log_progress("would_delete", {
                "thread_id": thread.id,
                "subject": subject[:50] + "..." if len(subject) > 50 else subject,
                "sender": sender_email,
                "message_count": messages_count
            })
            return True
        else:
            try:
                # Delete the entire thread at once using threads API
                self.service.users().threads().trash(userId='me', id=thread.id).execute()
                
                await self._log_progress("deleted", {
                    "thread_id": thread.id,
                    "subject": subject[:50] + "..." if len(subject) > 50 else subject,
                    "sender": sender_email,
                    "message_count": messages_count
                })
                return True
                
            except HttpError as error:
                await self._log_progress("delete_error", {
                    "thread_id": thread.id,
                    "error": str(error)
                })
                return False