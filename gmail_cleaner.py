#!/usr/bin/env python3
"""
Gmail Cleaner - Pattern-based email cleanup without AI
"""

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
        
        # Load junk detection data
        console.print("[dim]Loading junk detection configuration...[/dim]")
        self.junk_senders = self._load_junk_senders()
        self.junk_patterns = self._load_junk_patterns()
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
    
    def _load_junk_patterns(self) -> Dict:
        """Load junk detection patterns from JSON file"""
        patterns_file = Path('junk_patterns.json')
        if patterns_file.exists():
            with open(patterns_file, 'r') as f:
                patterns = json.load(f)
                console.print(f"[green]Loaded junk patterns from junk_patterns.json[/green]")
                return patterns
        else:
            console.print("[yellow]Warning: junk_patterns.json not found, using sender list only[/yellow]")
            return {
                'subject_patterns': [],
                'sender_name_patterns': [],
                'snippet_patterns': [],
                'domain_patterns': [],
                'scoring': {
                    'subject_weight': 3,
                    'sender_weight': 2,
                    'snippet_weight': 2,
                    'domain_weight': 4,
                    'threshold': 5,
                    'auto_delete_threshold': 8
                }
            }
    
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
    
    def _calculate_pattern_score(self, email: EmailInfo) -> Tuple[float, List[str]]:
        """Calculate junk score based on pattern matching"""
        score = 0
        reasons = []
        scoring = self.junk_patterns.get('scoring', {})
        
        # Check subject patterns - count ALL matches
        subject_lower = email.subject.lower()
        subject_matches = 0
        for pattern in self.junk_patterns.get('subject_patterns', []):
            if pattern.lower() in subject_lower:
                subject_matches += 1
                reasons.append(f"Subject contains '{pattern}'")
        if subject_matches > 0:
            score += subject_matches * scoring.get('subject_weight', 3)
        
        # Check sender name patterns - count ALL matches
        sender_lower = email.sender.lower()
        sender_matches = 0
        for pattern in self.junk_patterns.get('sender_name_patterns', []):
            if pattern.lower() in sender_lower:
                sender_matches += 1
                reasons.append(f"Sender contains '{pattern}'")
        if sender_matches > 0:
            score += sender_matches * scoring.get('sender_weight', 2)
        
        # Check snippet patterns - count ALL matches
        snippet_lower = email.snippet.lower()
        snippet_matches = 0
        for pattern in self.junk_patterns.get('snippet_patterns', []):
            if pattern.lower() in snippet_lower:
                snippet_matches += 1
                reasons.append(f"Content contains '{pattern}'")
        if snippet_matches > 0:
            score += snippet_matches * scoring.get('snippet_weight', 2)
        
        # Check domain patterns - count ALL matches
        email_addr = self._extract_email_address(email.sender)
        domain = self._extract_domain(email_addr)
        domain_matches = 0
        for pattern in self.junk_patterns.get('domain_patterns', []):
            if pattern.lower() in domain:
                domain_matches += 1
                reasons.append(f"Domain contains '{pattern}'")
        if domain_matches > 0:
            score += domain_matches * scoring.get('domain_weight', 4)
        
        return score, reasons
    
    def detect_junk(self, email: EmailInfo) -> JunkDetectionResult:
        """Aggressive mode: Delete ALL emails that reach this point (no labels, not important, not starred)"""
        sender_email = self._extract_email_address(email.sender)
        
        # AGGRESSIVE MODE: Delete everything since emails are pre-filtered
        # Only emails without labels, not marked important, and not starred reach this point
        self.aggressive_deletes += 1
        return JunkDetectionResult(
            is_junk=True,
            score=100,
            reasons=["Aggressive mode: No custom labels, importance, or stars"],
            confidence='high'
        )
    
    def get_emails_batch(self, page_token: Optional[str] = None, batch_size: int = 100) -> tuple[List[EmailInfo], Optional[str]]:
        """Fetch a batch of emails without any labels, important markers, or stars"""
        try:
            # Get all emails from anywhere excluding those with user labels, marked as important, or starred
            # Note: This will get emails from inbox, sent, etc. but our filtering will handle that
            results = self.service.users().messages().list(
                userId='me',
                maxResults=batch_size,
                pageToken=page_token,
                q='-has:userlabels -is:important -is:starred'  # Exclude protected emails
            ).execute()
            
            messages = results.get('messages', [])
            next_page_token = results.get('nextPageToken')
            
            emails = []
            for msg in messages:
                # Get full message details
                message = self.service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='metadata',
                    metadataHeaders=['From', 'Subject', 'Date']
                ).execute()
                
                # Skip if email has any user labels, is marked important, or is starred (double-check)
                label_ids = message.get('labelIds', [])
                system_labels = {'INBOX', 'SPAM', 'TRASH', 'UNREAD', 'SENT', 'DRAFT', 'IMPORTANT', 'STARRED', 'CATEGORY_PERSONAL', 
                               'CATEGORY_SOCIAL', 'CATEGORY_PROMOTIONS', 'CATEGORY_UPDATES', 'CATEGORY_FORUMS'}
                
                # Skip if marked as IMPORTANT or STARRED
                if 'IMPORTANT' in label_ids or 'STARRED' in label_ids:
                    continue
                
                # Skip if not in INBOX (must have INBOX label to be processed)
                if 'INBOX' not in label_ids:
                    continue
                
                # Skip SENT, DRAFT, SPAM, TRASH emails
                if any(label in label_ids for label in ['SENT', 'DRAFT', 'SPAM', 'TRASH']):
                    continue
                
                # If email has any label that's not a system label, skip it
                user_labels = [label for label in label_ids if label not in system_labels]
                if user_labels:
                    continue
                
                # Extract metadata
                headers = {h['name']: h['value'] for h in message['payload'].get('headers', [])}
                
                email_info = EmailInfo(
                    id=message['id'],
                    subject=headers.get('Subject', '(No Subject)'),
                    sender=headers.get('From', '(Unknown Sender)'),
                    date=headers.get('Date', ''),
                    snippet=message.get('snippet', ''),
                    labels=label_ids
                )
                emails.append(email_info)
            
            return emails, next_page_token
            
        except HttpError as error:
            console.print(f"[red]An error occurred: {error}[/red]")
            return [], None
    
    def delete_email(self, email_info: EmailInfo, detection: JunkDetectionResult):
        """Move email to trash"""
        sender_email = self._extract_email_address(email_info.sender)
        
        if self.dry_run:
            confidence_color = {'high': 'green', 'medium': 'yellow', 'low': 'red'}.get(detection.confidence, 'white')
            console.print(f"[red]WOULD DELETE[/red] - [bold]Subject:[/bold] '{email_info.subject[:60]}{'...' if len(email_info.subject) > 60 else ''}'")
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
                self.service.users().messages().trash(userId='me', id=email_info.id).execute()
                console.print(f"[green]DELETED[/green] - [bold]Subject:[/bold] '{email_info.subject[:60]}{'...' if len(email_info.subject) > 60 else ''}'")
                console.print(f"    [dim]From:[/dim] {sender_email}")
                console.print(f"    [green]Confidence: {detection.confidence.upper()} | Score: {detection.score:.1f}[/green]")
                console.print()
            except HttpError as error:
                console.print(f"[red]ERROR DELETING[/red] - [bold]Subject:[/bold] '{email_info.subject[:60]}{'...' if len(email_info.subject) > 60 else ''}'")
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
            console=console
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
                
                # Fetch batch of emails
                emails, page_token = self.get_emails_batch(page_token, current_batch_size)
                
                if not emails:
                    break
                
                # Truncate emails list if it would exceed the limit
                if total_limit and (total_processed + len(emails) > total_limit):
                    emails = emails[:total_limit - total_processed]
                    console.print(f"[yellow]Limiting batch to {len(emails)} emails to respect limit of {total_limit}[/yellow]")
                
                # Analyze batch using pattern matching
                console.print(f"\n[cyan]Processing batch of {len(emails)} emails...[/cyan]")
                
                batch_deleted = 0
                batch_kept = 0
                
                # Process each email
                for i, email in enumerate(emails, 1):
                    sender_email = self._extract_email_address(email.sender)
                    console.print(f"[dim]({i}/{len(emails)}) Analyzing: {sender_email}[/dim]")
                    
                    detection = self.detect_junk(email)
                    
                    if detection.is_junk:
                        self.delete_email(email, detection)
                        self.deleted_count += 1
                        batch_deleted += 1
                    else:
                        # Show kept emails in verbose mode
                        console.print(f"[green]KEEPING[/green] - [bold]Subject:[/bold] '{email.subject[:60]}{'...' if len(email.subject) > 60 else ''}'")
                        console.print(f"    [dim]From:[/dim] {sender_email}")
                        if detection.score > 0:
                            console.print(f"    [yellow]Score: {detection.score:.1f} (below threshold {self.junk_patterns.get('scoring', {}).get('threshold', 5)})[/yellow]")
                            if detection.reasons:
                                console.print(f"    [dim]Weak indicators: {', '.join(detection.reasons[:2])}[/dim]")
                        else:
                            console.print(f"    [green]Score: {detection.score:.1f} (no junk indicators)[/green]")
                        console.print()
                        self.kept_count += 1
                        batch_kept += 1
                    
                    self.processed_count += 1
                    total_processed += 1
                    
                    # Update progress
                    if total_limit:
                        progress.update(task, completed=min(total_processed, total_limit))
                    
                    # Stop if we've reached the limit
                    if total_limit and total_processed >= total_limit:
                        break
                
                # Show detailed batch summary
                console.print(f"\n[bold cyan]Batch Summary:[/bold cyan]")
                console.print(f"  [green]Deleted: {batch_deleted}[/green] | [blue]Kept: {batch_kept}[/blue] | [yellow]Total in batch: {len(emails)}[/yellow]")
                console.print(f"  [dim]Running totals - Processed: {self.processed_count} | Deleted: {self.deleted_count} | Kept: {self.kept_count}[/dim]")
                
                if page_token:
                    console.print(f"  [dim]More emails available for processing...[/dim]")
                else:
                    console.print(f"  [dim]No more emails to process.[/dim]")
                
                # Check if interrupted during batch processing
                if self.interrupted:
                    console.print("\n[yellow]Gracefully stopping after completing current batch.[/yellow]")
                    break
                
                # Check if there are more emails
                if not page_token:
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
