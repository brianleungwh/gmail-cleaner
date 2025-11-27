#!/usr/bin/env python3
"""
Gmail Service - Facade for Gmail operations
Handles authentication and delegates to specialized classes
"""

import signal
import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.models import DomainInfo, CollectionConfig, CleanupConfig, ThreadMetadata
from app.collector import DomainCollector
from app.cleaner import DomainCleaner


logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


class GmailService:
    """Facade for Gmail operations - handles auth and delegates to specialized classes"""

    def __init__(self, credentials_path: str = 'data/credentials.json', token_path: str = 'data/token.json'):
        # Auth-related
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.flow = None

        # Progress callback
        self.progress_callback: Optional[Callable] = None

        # Thread storage (populated by collector, used by cleaner)
        self.threads_by_id: Dict[str, ThreadMetadata] = {}
        self.threads_by_domain: Dict[str, List[str]] = {}

        # Signal handling
        self.interrupted = False
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

    # === Authentication ===

    def create_oauth_flow(self, redirect_uri: str = None) -> str:
        """Create OAuth2 flow and return authorization URL"""
        import os

        if not os.path.exists(self.credentials_path):
            raise Exception("Credentials file not found. Please upload credentials.json first.")

        self.flow = Flow.from_client_secrets_file(
            self.credentials_path,
            scopes=SCOPES,
            redirect_uri=redirect_uri or "http://localhost:8000/oauth/callback"
        )

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

            self.flow.fetch_token(code=authorization_code)

            creds = self.flow.credentials
            token_path = Path(self.token_path)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json())

            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Successfully authenticated with Gmail via OAuth")
            return True

        except Exception as error:
            logger.error(f"OAuth authentication failed: {error}")
            return False

    def authenticate(self) -> bool:
        """Check if already authenticated and refresh credentials if needed"""
        try:
            token_path = Path(self.token_path)

            if not token_path.exists():
                logger.info("No existing token found - user needs to authenticate via OAuth")
                return False

            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Refreshing expired credentials")
                    creds.refresh(Request())
                    token_path.write_text(creds.to_json())
                else:
                    logger.warning("Credentials invalid and cannot be refreshed - user needs to re-authenticate")
                    return False

            self.service = build('gmail', 'v1', credentials=creds)
            logger.info("Successfully authenticated with existing credentials")
            return True

        except Exception as error:
            logger.error(f"Authentication failed: {error}")
            return False

    # === Labels ===

    def get_labels(self) -> List[Dict]:
        """Fetch all custom labels from Gmail"""
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")

        try:
            results = self.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])

            custom_labels = [
                {'id': label.get('id', ''), 'name': label.get('name', '')}
                for label in labels
                if label.get('type') == 'user'
            ]

            custom_labels.sort(key=lambda x: x['name'].lower())
            return custom_labels

        except HttpError as error:
            logger.error(f"Error fetching labels: {error}")
            return []

    # === Collection (delegates to DomainCollector) ===

    async def collect_domains(
        self,
        limit: Optional[int] = None,
        excluded_domains: Optional[Set[str]] = None,
        use_label_protection: bool = True,
        protected_label_ids: Optional[Set[str]] = None
    ) -> Dict[str, DomainInfo]:
        """Collect all unique sender domains from inbox"""
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")

        config = CollectionConfig(
            limit=limit,
            excluded_domains=excluded_domains or set(),
            use_label_protection=use_label_protection,
            protected_label_ids=protected_label_ids
        )

        collector = DomainCollector(self.service, config, self.progress_callback)
        result = await collector.collect()

        # Store for cleanup operations
        self.threads_by_id = collector.threads_by_id
        self.threads_by_domain = collector.threads_by_domain

        return result

    # === Thread Access ===

    def get_threads_for_domains(self, domains: Set[str]) -> List[Dict]:
        """Get stored thread metadata for selected domains"""
        threads = []

        for domain in domains:
            thread_ids = self.threads_by_domain.get(domain, [])
            for thread_id in thread_ids:
                metadata = self.threads_by_id.get(thread_id)
                if metadata:
                    threads.append({
                        'thread_id': thread_id,
                        'domain': metadata.domain,
                        'subject': metadata.subject,
                        'sender': metadata.sender,
                        'message_count': metadata.message_count
                    })

        logger.debug(f"Retrieved {len(threads)} threads for {len(domains)} selected domains")
        return threads

    # === Cleanup (delegates to DomainCleaner) ===

    async def cleanup_emails(
        self,
        junk_domains: Set[str],
        dry_run: bool = True,
        total_limit: Optional[int] = None
    ) -> Dict[str, int]:
        """Clean up emails based on junk domains list using stored thread data"""
        if not self.service:
            raise Exception("Not authenticated. Call authenticate() first.")

        threads = self.get_threads_for_domains(junk_domains)

        if not threads:
            logger.warning("No threads found for selected domains. Did you run a scan first?")
            return {
                "threads_processed": 0,
                "threads_deleted": 0,
                "messages_deleted": 0,
                "messages_kept": 0
            }

        if total_limit and len(threads) > total_limit:
            threads = threads[:total_limit]
            logger.debug(f"Limited to {total_limit} threads")

        config = CleanupConfig(dry_run=dry_run, limit=total_limit)
        cleaner = DomainCleaner(self.service, config, self.progress_callback)

        return await cleaner.cleanup(threads)
