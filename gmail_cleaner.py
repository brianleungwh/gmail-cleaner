#!/usr/bin/env python3
"""
Gmail Cleaner - Automated cleanup of unprotected emails
"""
import os
import time
import signal
import sys
import argparse
import re
import json
from typing import List, Dict, Optional, Set
from collections import defaultdict
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
class JunkDetectionResult:
    """Result of junk detection with scoring details"""
    is_junk: bool
    score: float
    reasons: List[str]
    confidence: str  # 'high', 'medium', 'low'


class GmailCleaner:
    def __init__(self, dry_run: bool = True, senders_file: Optional[str] = None):
        self.dry_run = dry_run
        self.service = self._authenticate_gmail()
        self.threads_processed = 0
        self.threads_deleted = 0
        self.messages_deleted = 0
        self.messages_kept = 0
        self.interrupted = False
        self.senders_file = senders_file
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_interrupt)
        
        # Load junk senders list (if doing cleanup)
        self.junk_senders = set()  # Will be loaded when needed
    
    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        if not self.interrupted:
            console.print("\n[yellow]Interrupt received. Finishing current batch before exiting...[/yellow]")
            self.interrupted = True
        else:
            console.print("\n[red]Force quit requested. Exiting immediately.[/red]")
            sys.exit(1)
    
    def _load_junk_senders(self, senders_file: Optional[str] = None) -> Set[str]:
        """Load list of known junk email domains"""
        # Use provided file or default to senders_to_review.json
        junk_file = Path(senders_file) if senders_file else Path('senders_to_review.json')
        
        if junk_file.exists():
            try:
                # Try to parse as JSON first (new format)
                with open(junk_file, 'r') as f:
                    data = json.load(f)
                    if 'domains' in data:
                        domains = set(data['domains'].keys())
                        console.print(f"[green]Loaded {len(domains)} junk domains from {junk_file.name} (JSON)[/green]")
                        return domains
            except json.JSONDecodeError:
                # Fall back to text format (old format)
                with open(junk_file, 'r') as f:
                    senders = set()
                    for line in f:
                        line = line.strip()
                        # Skip empty lines and comments
                        if not line or line.startswith('#'):
                            continue
                        # Extract email/domain from lines like "email@domain.com (5 threads)"
                        item = line.split(' (')[0].strip().lower()
                        if item:
                            # If it's an email, extract domain; if already domain, use as-is
                            if '@' in item:
                                domain = self._extract_domain(item)
                                if domain:
                                    senders.add(domain)
                            else:
                                senders.add(item)
                    console.print(f"[green]Loaded {len(senders)} junk patterns from {junk_file.name} (text)[/green]")
                    return senders
        console.print(f"[yellow]No {junk_file.name} found - will keep all unprotected threads[/yellow]")
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
    
    def _extract_domain(self, email: str) -> str:
        """Extract domain from email address"""
        if '@' in email:
            return email.split('@')[1].lower()
        return ''
    
    def _is_thread_protected(self, label_ids: List[str]) -> bool:
        """Check if a thread should be protected from deletion based on its labels
        
        Protected if:
        - Has IMPORTANT label
        - Has STARRED label  
        - Has any custom user labels (starting with Label_)
        """
        # Check for important or starred
        # if 'IMPORTANT' in label_ids or 'STARRED' in label_ids:
        #     return True
        
        # Check for custom user labels
        has_custom_label = any(label.startswith('Label_') for label in label_ids)
        return has_custom_label
    
    
    def detect_junk(self, thread: ThreadInfo) -> JunkDetectionResult:
        """Determine if thread should be deleted based on junk sender domains"""
        # Check the first message's sender domain against junk domains
        if thread.messages:
            first_message = thread.messages[0]
            headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
            sender = headers.get('From', '(Unknown Sender)')
            sender_email = self._extract_email_address(sender)
            sender_domain = self._extract_domain(sender_email)
            
            # Check if sender domain is in junk domains list
            if sender_domain in self.junk_senders:
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
            
            # Only show debug logging if there are threads
            if threads:
                console.print(f"[dim]Found {len(threads)} threads in batch[/dim]")
            
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
                
                console.print(f"[dim]Thread {thread_id}: '{subject[:40]}...' from {sender_email}[/dim]")
                
                first_label_ids = first_message.get('labelIds', [])
                
                # Check if thread is protected (based on first message)
                if self._is_thread_protected(first_label_ids):
                    threads_protected += 1
                    continue  # Skip protected thread
                
                # Add unprotected thread to list for processing
                thread_info = ThreadInfo(
                    id=thread_id,
                    messages=messages
                )
                threads_to_process.append(thread_info)
            
            if threads_to_process or threads_protected:
                console.print(f"[cyan]{len(threads_to_process)} unprotected threads ready to process ({threads_protected} protected)[/cyan]")
            
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
            console.print(f"[red]WOULD DELETE[/red] Thread ({messages_count} msgs): {subject[:50]}... from {sender_email}")
            if detection.reasons[0].startswith("Sender"):
                console.print(f"    [dim]Reason: {detection.reasons[0]}[/dim]")
        else:
            try:
                # Delete the entire thread at once using threads API
                self.service.users().threads().trash(userId='me', id=thread.id).execute()
                
                console.print(f"[red]DELETED[/red] Thread ({messages_count} msgs): {subject[:50]}... from {sender_email}")
            except HttpError as error:
                console.print(f"[red]ERROR DELETING[/red] Thread: {error}")
    
    def collect_senders(self, output_file: str = 'senders_to_review.json'):
        """Collect all unique sender domains from inbox and output to JSON file for review"""
        console.print(f"\n[bold blue]Collecting Sender Domain Information[/bold blue]")
        console.print(f"[yellow]This will scan all inbox threads and create a JSON file for review[/yellow]\n")
        
        # Dictionary to store domain info: domain -> {count, subjects}
        domain_data = defaultdict(lambda: {'count': 0, 'subjects': []})
        page_token = None
        total_threads = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Scanning inbox threads...", total=None)
            
            while True:
                # Get ALL threads from inbox (no filtering)
                try:
                    results = self.service.users().threads().list(
                        userId='me',
                        maxResults=100,
                        pageToken=page_token,
                        q='in:inbox'
                    ).execute()
                    
                    threads = results.get('threads', [])
                    next_page_token = results.get('nextPageToken')
                    
                    if not threads:
                        break
                    
                    for thread in threads:
                        thread_id = thread['id']
                        
                        # Get thread details
                        thread_data = self.service.users().threads().get(
                            userId='me',
                            id=thread_id,
                            format='metadata',
                            metadataHeaders=['From', 'Subject']
                        ).execute()
                        
                        messages = thread_data.get('messages', [])
                        if not messages:
                            continue
                        
                        # Get first message info
                        first_message = messages[0]
                        headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
                        sender = headers.get('From', '(Unknown Sender)')
                        subject = headers.get('Subject', '(No Subject)')
                        sender_email = self._extract_email_address(sender)
                        
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
                        progress.update(task, description=f"Scanned {total_threads} threads...")
                    
                    page_token = next_page_token
                    if not page_token:
                        break
                        
                except HttpError as error:
                    console.print(f"[red]Error fetching threads: {error}[/red]")
                    break
        
        # Sort domains by frequency (highest first)
        sorted_domains = sorted(domain_data.items(), key=lambda x: x[1]['count'], reverse=True)
        
        # Create JSON structure
        output_data = {
            "instructions": "Delete entries for domains you want to KEEP. Keep entries for domains you want to DELETE.",
            "domains": {}
        }
        
        for domain, data in sorted_domains:
            # Truncate long subjects
            truncated_subjects = []
            for subject in data['subjects']:
                if len(subject) > 60:
                    subject = subject[:57] + "..."
                truncated_subjects.append(subject)
            
            output_data["domains"][domain] = {
                "count": data['count'],
                "sample_subjects": truncated_subjects
            }
        
        # Write JSON to file
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        # Print summary
        console.print(f"\n[bold green]Collection Complete![/bold green]")
        console.print(f"  - Total threads scanned: {total_threads:,}")
        console.print(f"  - Unique domains found: {len(domain_data):,}")
        console.print(f"  - Output file: [cyan]{output_file}[/cyan]")
        console.print(f"\n[yellow]Next steps:[/yellow]")
        console.print(f"  1. Edit [cyan]{output_file}[/cyan]")
        console.print(f"  2. DELETE entries for domains you want to KEEP")
        console.print(f"  3. KEEP entries for domains you want to DELETE")
        console.print(f"  4. Run: python gmail_cleaner.py --cleanup-emails --senders-file {output_file}")
    
    def process_emails(self, total_limit: Optional[int] = None):
        """Process all emails in batches"""
        # Load junk senders list for cleanup
        self.junk_senders = self._load_junk_senders(self.senders_file)
        
        batch_size = int(os.getenv('BATCH_SIZE', '100'))
        page_token = None
        total_processed = 0
        
        # Show detailed startup information
        console.print(f"\n[bold blue]Starting Gmail Cleanup[/bold blue]")
        console.print(f"[yellow]Mode: {'DRY RUN (no emails will be deleted)' if self.dry_run else 'LIVE MODE (emails will be permanently deleted)'}[/yellow]")
        console.print(f"[cyan]Detection Method: Pattern-based junk detection[/cyan]")  
        console.print(f"[green]Batch Size: {batch_size} threads per batch[/green]")
        if total_limit:
            console.print(f"[blue]Processing Limit: {total_limit:,} emails[/blue]")
        else:
            console.print(f"[blue]Processing Limit: All available emails[/blue]")
        
        console.print(f"\n[bold red]WARNING:[/bold red]")
        console.print(f"[red]This script will DELETE emails except those that are:[/red]")
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
            console=console
        ) as progress:
            
            # Create progress task
            if total_limit:
                task = progress.add_task("Processing threads...", total=total_limit)
            else:
                task = progress.add_task("Processing threads...", total=None)
            
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
                threads, next_page_token = self.get_threads_batch(page_token, current_batch_size)
                
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
                        subject = headers.get('Subject', '(No Subject)')
                        sender_email = self._extract_email_address(sender)
                        console.print(f"[dim]({i}/{len(threads)}) Thread {thread.id}: '{subject[:40]}...' from {sender_email}[/dim]")
                    
                    detection = self.detect_junk(thread)
                    
                    if detection.is_junk:
                        self.delete_thread(thread, detection)
                        # Count threads and messages deleted
                        self.threads_deleted += 1
                        messages_deleted = len([m for m in thread.messages if 'INBOX' in m.get('labelIds', [])])
                        self.messages_deleted += messages_deleted
                        batch_deleted += messages_deleted
                    else:
                        # Show kept threads in verbose mode
                        if thread.messages:
                            first_message = thread.messages[0]
                            headers = {h['name']: h['value'] for h in first_message['payload'].get('headers', [])}
                            subject = headers.get('Subject', '(No Subject)')
                            console.print(f"[green]KEEPING[/green] Thread ({len(thread.messages)} msgs): {subject[:50]}... from {sender_email}")
                        messages_kept = len([m for m in thread.messages if 'INBOX' in m.get('labelIds', [])])
                        self.messages_kept += messages_kept
                        batch_kept += messages_kept
                    
                    self.threads_processed += 1
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
                console.print(f"  [dim]Running totals - Threads: {self.threads_processed} | Deleted: {self.messages_deleted} msgs | Kept: {self.messages_kept} msgs[/dim]")
                
                # Remove redundant pagination status messages
                
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
        console.print(f"\n[bold green]Gmail Cleanup Complete![/bold green]")
        
        # Main statistics table
        table = Table(title="Gmail Cleanup Results", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan", width=25)
        table.add_column("Count", justify="right", style="green", width=10)
        
        table.add_row("Threads Processed", f"{self.threads_processed:,}")
        table.add_row("Threads Deleted", f"{self.threads_deleted:,}")
        table.add_row("Messages Deleted", f"{self.messages_deleted:,}")
        
        # Show kept messages if any
        if self.messages_kept > 0:
            table.add_row("Messages Kept", f"{self.messages_kept:,}")
        
        console.print(table)
        
        # Performance metrics
        console.print(f"\n[bold cyan]Summary:[/bold cyan]")
        console.print(f"  - Method: Pattern-based detection using junk_senders.txt")
        
        if self.dry_run:
            console.print(f"\n[bold yellow]DRY RUN MODE:[/bold yellow]")
            console.print(f"  - No emails were actually deleted")
            console.print(f"  - Run with --no-dry-run to actually delete emails")
            console.print(f"  - Space savings: {self.messages_deleted:,} messages would be removed")
            console.print(f"  - REMEMBER: Only labeled/important emails are protected!")
        else:
            console.print(f"\n[bold green]LIVE MODE COMPLETED:[/bold green]")
            console.print(f"  - {self.messages_deleted:,} messages were permanently moved to trash")
            console.print(f"  - {self.messages_kept:,} messages remain in your inbox")
            console.print(f"  - You can restore deleted emails from the Trash folder if needed")
            console.print(f"  - Protected emails (labeled/important) were automatically skipped")


def main():
    """Main entry point"""

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Gmail inbox cleaner - collect senders or delete emails based on patterns')
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--collect-senders-emails', action='store_true', 
                            help='Collect all sender domains and output to JSON file for review')
    mode_group.add_argument('--cleanup-emails', action='store_true',
                            help='Clean up emails based on junk domains list')
    
    # Cleanup options
    parser.add_argument('--senders-file', type=str, 
                       help='Path to domains file (default: junk_senders.txt for cleanup, outputs to senders_to_review.json for collection)')
    parser.add_argument('--limit', type=int, help='Maximum number of threads to process (cleanup mode only)')
    parser.add_argument('--batch-size', type=int, default=100, help='Number of threads per batch (default: 100)')
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
    
    # Handle collection mode
    if args.collect_senders_emails:
        # Collection mode doesn't need dry_run
        cleaner = GmailCleaner(dry_run=True)  # Always dry-run for collection
        
        # Determine output file
        output_file = args.senders_file if args.senders_file else 'senders_to_review.json'
        cleaner.collect_senders(output_file=output_file)
    
    # Handle cleanup mode
    elif args.cleanup_emails:
        # Determine dry_run mode (CLI args override env var)
        if args.dry_run is None:
            dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
        else:
            dry_run = args.dry_run
        
        # Override batch size from env if provided in args
        if args.batch_size != 100:
            os.environ['BATCH_SIZE'] = str(args.batch_size)
        
        # Create cleaner with senders file
        cleaner = GmailCleaner(dry_run=dry_run, senders_file=args.senders_file)
        
        # Process emails with optional limit
        cleaner.process_emails(total_limit=args.limit)


if __name__ == "__main__":
    main()
