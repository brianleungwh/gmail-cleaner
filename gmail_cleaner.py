#!/usr/bin/env python3
"""
Gmail Cleaner - Pattern-based email cleanup without AI
"""
from logging import disable
import ipdb

import os
import json
import time
import signal
import sys
import argparse
import re
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

# Load environment variables
load_dotenv()

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

console = Console()


@dataclass
class ThreadInfo:
    """Thread information for processing"""
    id: str
    messages: List[Dict]  # List of message data from the thread


@dataclass
class EmailInfo:
    """Minimal email information for analysis"""
    id: str
    subject: str
    sender: str
    date: str
    snippet: str
    labels: List[str]


@dataclass
class JunkDetectionResult:
    """Result of junk detection with scoring details"""
    is_junk: bool
    score: float
    reasons: List[str]
    confidence: str  # 'high', 'medium', 'low'


class GmailCleaner:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.service = self._authenticate_gmail()
        self.processed_count = 0
        self.deleted_count = 0
        self.kept_count = 0
        self.interrupted = False
        
        # Aggressive mode stats (simplified)
        self.aggressive_deletes = 0
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_interrupt)
        
        # Load junk senders list
        console.print("[dim]Loading junk senders list...[/dim]")
        self.junk_senders = self._load_junk_senders()
        console.print("[dim]Configuration loaded successfully.[/dim]\n")
    
    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        if not self.interrupted:
            console.print("\n[yellow]Interrupt received. Finishing current batch before exiting...[/yellow]")
            self.interrupted = True
        else:
            console.print("\n[red]Force quit requested. Exiting immediately.[/red]")
            sys.exit(1)
    
    def _load_junk_senders(self) -> Set[str]:
        """Load list of known junk email senders"""
        junk_file = Path('junk_senders.txt')
        if junk_file.exists():
            with open(junk_file, 'r') as f:
                # Read lines, strip whitespace, convert to lowercase, ignore empty lines and comments
                senders = {line.strip().lower() for line in f 
                          if line.strip() and not line.strip().startswith('#')}
                console.print(f"[green]Loaded {len(senders)} junk senders from junk_senders.txt[/green]")
                return senders
        return set()
    
    
    def _authenticate_gmail(self):
        """Authenticate and return Gmail service instance"""
        creds = None
        token_path = Path('token.json')
        
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials.json'), SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            token_path.write_text(creds.to_json())
        
        return build('gmail', 'v1', credentials=creds)
    
    def _extract_email_address(self, sender: str) -> str:
        """Extract email address from sender string like 'Name <email@domain.com>'"""
        # Try to extract email from angle brackets
        match = re.search(r'<([^>]+)>', sender)
        if match:
            return match.group(1).lower()
        # If no angle brackets, assume the whole string is the email
        return sender.strip().lower()
    
    
    def detect_junk(self, thread: ThreadInfo) -> JunkDetectionResult:
        """Enhanced aggressive mode: Check junk senders first, then delete everything else"""
        # Check the first message's sender against junk patterns
        if thread.messages:
            first_message = thread.messages[0]
            headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
            sender = headers.get('From', '(Unknown Sender)')
            sender_email = self._extract_email_address(sender)
            
            # First check: sender pattern match from junk_senders.txt
            for junk_pattern in self.junk_senders:
                if junk_pattern in sender_email:
                    return JunkDetectionResult(
                        is_junk=True,
                        score=100,
                        reasons=[f"Sender '{sender_email}' matches junk pattern '{junk_pattern}'"],
                        confidence='high'
                    )
        
        # AGGRESSIVE MODE: Delete everything else since threads are pre-filtered
        # Only threads without labels, not marked important, and not starred reach this point
        self.aggressive_deletes += 1
        return JunkDetectionResult(
            is_junk=True,
            score=100,
            reasons=["Aggressive mode: No custom labels, importance, or stars"],
            confidence='high'
        )
    
    def get_threads_batch(self, page_token: Optional[str] = None, batch_size: int = 100) -> tuple[List[ThreadInfo], Optional[str]]:
        """Fetch a batch of threads and their messages for processing"""
        try:
            # Get ALL threads from inbox - we'll do filtering manually
            results = self.service.users().threads().list(
                userId='me',
                maxResults=batch_size,
                pageToken=page_token,
                q='in:inbox'  # Just get inbox threads
            ).execute()
            
            threads = results.get('threads', [])
            next_page_token = results.get('nextPageToken')
            
            console.print(f"[dim]Gmail API returned {len(threads)} threads, next_page_token: {next_page_token[:20] + '...' if next_page_token else 'None'}[/dim]")
            
            if not threads:
                console.print(f"[yellow]Gmail API returned no threads for current page[/yellow]")
                return [], next_page_token
            
            threads_to_process = []
            threads_protected = 0
            
            for thread in threads:
                thread_id = thread['id']
                console.print(f"[dim]Processing thread ID: {thread_id}[/dim]")
                
                # Get full thread details with all messages
                thread_data = self.service.users().threads().get(
                    userId='me',
                    id=thread_id,
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                messages = thread_data.get('messages', [])
                if not messages:
                    console.print(f"[dim]Thread {thread_id} has no messages, skipping[/dim]")
                    continue
                
                # Check ONLY the first message in the thread for protection
                first_message = messages[0]
                first_label_ids = first_message.get('labelIds', [])
                
                # Check if thread is protected (based on first message)
                # Protected if: IMPORTANT, STARRED, or has custom labels (Label_*)
                has_custom_label = any(label.startswith('Label_') for label in first_label_ids)
                is_protected = ('IMPORTANT' in first_label_ids or 
                               'STARRED' in first_label_ids or 
                               has_custom_label)
                
                if is_protected:
                    console.print(f"[dim]Thread {thread_id} is PROTECTED (important/starred/custom label)[/dim]")
                    threads_protected += 1
                    continue  # Skip this entire thread
                
                # Add unprotected thread to list for processing
                thread_info = ThreadInfo(
                    id=thread_id,
                    messages=messages
                )
                threads_to_process.append(thread_info)
            
            console.print(f"[dim]Found {len(threads_to_process)} unprotected threads ({threads_protected} protected)[/dim]")
            
            return threads_to_process, next_page_token
            
        except HttpError as error:
            console.print(f"[red]An error occurred: {error}[/red]")
            return [], None
    
    def delete_thread(self, thread: ThreadInfo, detection: JunkDetectionResult):
        """Move all messages in thread to trash"""
        # Get first message info for display
        if not thread.messages:
            return
        
        first_message = thread.messages[0]
        headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
        subject = headers.get('Subject', '(No Subject)')
        sender = headers.get('From', '(Unknown Sender)')
        sender_email = self._extract_email_address(sender)
        
        
        messages_count = len(thread.messages)
        
        if self.dry_run:
            confidence_color = {'high': 'green', 'medium': 'yellow', 'low': 'red'}.get(detection.confidence, 'white')
            console.print(f"[red]WOULD DELETE THREAD[/red] ({messages_count} messages) - [bold]Subject:[/bold] '{subject[:60]}{'...' if len(subject) > 60 else ''}'")
            console.print(f"    [dim]From:[/dim] {sender_email}")
            console.print(f"    [{confidence_color}]Confidence: {detection.confidence.upper()} | Score: {detection.score:.1f}[/{confidence_color}]")
            
            # Show all reasons, not just the first one
            for i, reason in enumerate(detection.reasons[:3], 1):  # Show up to 3 reasons
                console.print(f"    [dim]{i}. {reason}[/dim]")
            if len(detection.reasons) > 3:
                console.print(f"    [dim]... and {len(detection.reasons) - 3} more reasons[/dim]")
            console.print()
        else:
            try:
                # Delete the entire thread at once using threads API
                self.service.users().threads().trash(userId='me', id=thread.id).execute()
                
                console.print(f"[green]DELETED THREAD[/green] ({messages_count} messages) - [bold]Subject:[/bold] '{subject[:60]}{'...' if len(subject) > 60 else ''}'")
                console.print(f"    [dim]From:[/dim] {sender_email}")
                console.print(f"    [green]Confidence: {detection.confidence.upper()} | Score: {detection.score:.1f}[/green]")
                console.print()
            except HttpError as error:
                console.print(f"[red]ERROR DELETING THREAD[/red] - [bold]Subject:[/bold] '{subject[:60]}{'...' if len(subject) > 60 else ''}'")
                console.print(f"    [dim]From:[/dim] {sender_email}")
                console.print(f"    [red]Error: {error}[/red]")
                console.print()
    
    def process_emails(self, total_limit: Optional[int] = None):
        """Process all emails in batches"""
        batch_size = int(os.getenv('BATCH_SIZE', '100'))
        page_token = None
        total_processed = 0
        
        # Show detailed startup information
        console.print(f"\n[bold blue]Starting Gmail Cleanup - AGGRESSIVE MODE[/bold blue]")
        console.print(f"[yellow]Mode: {'DRY RUN (no emails will be deleted)' if self.dry_run else 'LIVE MODE (emails will be permanently deleted)'}[/yellow]")
        console.print(f"[cyan]Detection Method: Aggressive deletion (delete ALL unlabeled emails)[/cyan]")
        console.print(f"[green]Batch Size: {batch_size} emails per batch[/green]")
        if total_limit:
            console.print(f"[blue]Processing Limit: {total_limit:,} emails[/blue]")
        else:
            console.print(f"[blue]Processing Limit: All available emails[/blue]")
        
        console.print(f"\n[bold red]WARNING - AGGRESSIVE DELETION MODE:[/bold red]")
        console.print(f"[red]This script will DELETE ALL EMAILS except those that are:[/red]")
        console.print(f"  - Marked as IMPORTANT")
        console.print(f"  - STARRED")
        console.print(f"  - Have CUSTOM LABELS applied")
        console.print(f"  - Are in SENT, DRAFTS, or SPAM folders")
        console.print(f"[red]If you haven't starred/labeled important emails, STOP NOW and mark them first![/red]")
        
        console.print(f"\n[bold yellow]Protection Rules (emails that will be SKIPPED):[/bold yellow]")
        console.print(f"  - Emails with user labels: PROTECTED")
        console.print(f"  - Emails marked as important: PROTECTED")
        console.print(f"  - Starred emails: PROTECTED")
        console.print(f"  - Sent emails: PROTECTED")
        console.print(f"  - Draft emails: PROTECTED")
        
        console.print(f"\n[bold cyan]What Will Be DELETED:[/bold cyan]")
        console.print(f"  - ALL inbox emails without custom labels")
        console.print(f"  - ALL inbox emails not marked important or starred")
        console.print(f"  - Promotional emails, newsletters, notifications")
        console.print(f"  - Banking alerts, receipts, confirmations (if not starred/labeled)")
        console.print(f"  - Personal emails (if not starred/labeled or marked important)")
        console.print()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
            disable=True
        ) as progress:
            
            # Create progress task
            if total_limit:
                task = progress.add_task("Processing emails...", total=total_limit)
            else:
                task = progress.add_task("Processing emails...", total=None)
            
            while True:
                # Check for interrupt before starting new batch
                if self.interrupted:
                    console.print("\n[yellow]Stopping after current batch...[/yellow]")
                    break
                
                # Check if we've reached the limit
                if total_limit and total_processed >= total_limit:
                    break
                
                # Adjust batch size if approaching limit
                current_batch_size = batch_size
                if total_limit and (total_processed + batch_size > total_limit):
                    current_batch_size = total_limit - total_processed
                
                # Fetch batch of threads
                console.print(f"[dim]Fetching batch with page_token: {page_token[:20] + '...' if page_token else 'None'}[/dim]")
                threads, next_page_token = self.get_threads_batch(page_token, current_batch_size)
                
                # Only break if no threads AND no more pages
                if not threads and not next_page_token:
                    console.print(f"[dim]No more threads to process (threads: {len(threads)}, next_page_token: {next_page_token})[/dim]")
                    break
                
                # Update page token for next iteration
                page_token = next_page_token
                console.print(f"[dim]Updated page_token for next iteration: {page_token[:20] + '...' if page_token else 'None'}[/dim]")
                
                # Skip to next batch if current batch is empty but there are more pages
                if not threads:
                    console.print(f"[dim]Batch had no eligible threads after filtering, checking next batch...[/dim]")
                    continue
                
                # Truncate threads list if it would exceed the limit
                if total_limit and (total_processed + len(threads) > total_limit):
                    threads = threads[:total_limit - total_processed]
                    console.print(f"[yellow]Limiting batch to {len(threads)} threads to respect limit of {total_limit}[/yellow]")
                
                # Analyze batch using pattern matching
                console.print(f"\n[cyan]Processing batch of {len(threads)} threads...[/cyan]")
                
                batch_deleted = 0
                batch_kept = 0
                
                # Process each thread
                for i, thread in enumerate(threads, 1):
                    # Get first message info for display
                    if thread.messages:
                        first_message = thread.messages[0]
                        headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
                        sender = headers.get('From', '(Unknown Sender)')
                        sender_email = self._extract_email_address(sender)
                        console.print(f"[dim]({i}/{len(threads)}) Analyzing thread from: {sender_email}[/dim]")
                    
                    detection = self.detect_junk(thread)
                    
                    if detection.is_junk:
                        self.delete_thread(thread, detection)
                        # Count all messages in thread as deleted
                        messages_deleted = len([m for m in thread.messages if 'INBOX' in m.get('labelIds', [])])
                        self.deleted_count += messages_deleted
                        batch_deleted += messages_deleted
                    else:
                        # Show kept threads in verbose mode
                        if thread.messages:
                            first_message = thread.messages[0]
                            headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
                            subject = headers.get('Subject', '(No Subject)')
                            console.print(f"[green]KEEPING THREAD[/green] ({len(thread.messages)} messages) - [bold]Subject:[/bold] '{subject[:60]}{'...' if len(subject) > 60 else ''}'")
                            console.print(f"    [dim]From:[/dim] {sender_email}")
                            console.print(f"    [green]No junk sender match found[/green]")
                            console.print()
                        messages_kept = len([m for m in thread.messages if 'INBOX' in m.get('labelIds', [])])
                        self.kept_count += messages_kept
                        batch_kept += messages_kept
                    
                    self.processed_count += 1
                    # Update total processed based on thread count
                    total_processed += 1
                    
                    # Update progress
                    if total_limit:
                        progress.update(task, completed=min(total_processed, total_limit))
                    
                    # Stop if we've reached the limit
                    if total_limit and total_processed >= total_limit:
                        break
                
                # Show detailed batch summary
                console.print(f"\n[bold cyan]Batch Summary:[/bold cyan]")
                console.print(f"  [green]Messages Deleted: {batch_deleted}[/green] | [blue]Messages Kept: {batch_kept}[/blue] | [yellow]Threads in batch: {len(threads)}[/yellow]")
                console.print(f"  [dim]Running totals - Processed: {self.processed_count} | Deleted: {self.deleted_count} | Kept: {self.kept_count}[/dim]")
                
                if next_page_token:
                    console.print(f"  [dim]More emails available for processing...[/dim]")
                else:
                    console.print(f"  [dim]Reached end of email list.[/dim]")
                
                # Check if interrupted during batch processing
                if self.interrupted:
                    console.print("\n[yellow]Gracefully stopping after completing current batch.[/yellow]")
                    break
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
        
        # Final summary
        self._print_summary()
        
        if self.interrupted:
            console.print("\n[yellow]Process interrupted by user. Summary shows emails processed before interruption.[/yellow]")
    
    def _print_summary(self):
        """Print final summary table"""
        console.print(f"\n[bold green]Aggressive Cleanup Complete![/bold green]")
        
        # Main statistics table
        table = Table(title="Gmail Aggressive Cleanup Results", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan", width=25)
        table.add_column("Count", justify="right", style="green", width=10)
        table.add_column("Percentage", justify="right", style="yellow", width=12)
        
        delete_pct = (self.deleted_count / self.processed_count * 100) if self.processed_count > 0 else 0
        keep_pct = (self.kept_count / self.processed_count * 100) if self.processed_count > 0 else 0
        
        table.add_row("Total Processed", f"{self.processed_count:,}", "100.0%")
        table.add_row("Emails Deleted", f"{self.deleted_count:,}", f"{delete_pct:.1f}%")
        table.add_row("Emails Kept", f"{self.kept_count:,}", f"{keep_pct:.1f}%")
        table.add_row("", "", "")
        table.add_row("Aggressive Deletes", f"{self.aggressive_deletes:,}", f"{delete_pct:.1f}%")
        
        console.print(table)
        
        # Performance metrics
        console.print(f"\n[bold cyan]Performance Metrics:[/bold cyan]")
        console.print(f"  - Detection Speed: Instant (aggressive mode)")
        console.print(f"  - Cost: $0.00 (no AI API usage)")
        console.print(f"  - Method: Delete all unlabeled/non-important emails")
        
        if self.kept_count > 0:
            console.print(f"\n[bold blue]Unexpected Keeps:[/bold blue]")
            console.print(f"  - {self.kept_count:,} emails were kept (this should be 0 in aggressive mode)")
            console.print(f"  - This may indicate an issue with the filtering logic")
        
        if self.dry_run:
            console.print(f"\n[bold yellow]DRY RUN MODE:[/bold yellow]")
            console.print(f"  - No emails were actually deleted")
            console.print(f"  - Run with --no-dry-run to actually delete emails")
            console.print(f"  - Space savings: {self.deleted_count:,} emails would be removed")
            console.print(f"  - REMEMBER: Only labeled/important emails are protected!")
        else:
            console.print(f"\n[bold green]LIVE MODE COMPLETED:[/bold green]")
            console.print(f"  - {self.deleted_count:,} emails were permanently moved to trash")
            console.print(f"  - {self.kept_count:,} emails remain in your inbox")
            console.print(f"  - You can restore deleted emails from the Trash folder if needed")
            console.print(f"  - Protected emails (labeled/important) were automatically skipped")


def main():
    """Main entry point"""

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Aggressive Gmail inbox cleaner - deletes ALL unlabeled emails')
    parser.add_argument('--limit', type=int, help='Maximum number of emails to process')
    parser.add_argument('--batch-size', type=int, default=100, help='Number of emails per batch (default: 100)')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode (don\'t actually delete)')
    parser.add_argument('--no-dry-run', dest='dry_run', action='store_false', help='Actually delete emails')
    parser.set_defaults(dry_run=None)
    
    args = parser.parse_args()
    
    # Check for Gmail credentials
    if not os.path.exists(os.getenv('GMAIL_CREDENTIALS_PATH', 'credentials.json')):
        console.print("[red]Error: Gmail credentials file not found[/red]")
        console.print("Please download your credentials.json from Google Cloud Console")
        console.print("and place it in the project directory")
        return
    
    # Determine dry_run mode (CLI args override env var)
    if args.dry_run is None:
        dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
    else:
        dry_run = args.dry_run
    
    # Override batch size from env if provided in args
    if args.batch_size != 100:
        os.environ['BATCH_SIZE'] = str(args.batch_size)
    
    # Create and run cleaner
    cleaner = GmailCleaner(dry_run=dry_run)

    # Process emails with optional limit
    cleaner.process_emails(total_limit=args.limit)


if __name__ == "__main__":
    main()
