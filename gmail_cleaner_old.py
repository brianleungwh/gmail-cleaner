#!/usr/bin/env python3
"""
Gmail Cleaner - AI-powered email cleanup using Anthropic API
"""

import os
import json
import time
import signal
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from tqdm import tqdm

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


class GmailCleaner:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.anthropic = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.service = self._authenticate_gmail()
        self.processed_count = 0
        self.deleted_count = 0
        self.kept_count = 0
        self.skipped_api_count = 0
        self.api_call_count = 0
        self.interrupted = False
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_interrupt)
        
        # Load junk senders list
        self.junk_senders = self._load_junk_senders()
    
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
    
    def _extract_email_address(self, sender: str) -> str:
        """Extract email address from sender string like 'Name <email@domain.com>'"""
        import re
        # Try to extract email from angle brackets
        match = re.search(r'<([^>]+)>', sender)
        if match:
            return match.group(1).lower()
        # If no angle brackets, assume the whole string is the email
        return sender.strip().lower()
        
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
    
    def get_all_labels(self) -> Set[str]:
        """Get all label IDs in the account"""
        try:
            results = self.service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            return {label['id'] for label in labels}
        except HttpError as error:
            console.print(f"[red]An error occurred: {error}[/red]")
            return set()
    
    def get_emails_batch(self, page_token: Optional[str] = None, batch_size: int = 100) -> tuple[List[EmailInfo], Optional[str]]:
        """Fetch a batch of emails without any labels or important markers"""
        try:
            # Get all emails excluding those with user labels or marked as important
            results = self.service.users().messages().list(
                userId='me',
                maxResults=batch_size,
                pageToken=page_token,
                q='-has:userlabels -is:important'  # Exclude emails with user labels or marked important
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
                
                # Skip if email has any user labels or is marked important (double-check)
                label_ids = message.get('labelIds', [])
                system_labels = {'INBOX', 'SPAM', 'TRASH', 'UNREAD', 'SENT', 'DRAFT', 'IMPORTANT', 'CATEGORY_PERSONAL', 
                               'CATEGORY_SOCIAL', 'CATEGORY_PROMOTIONS', 'CATEGORY_UPDATES', 'CATEGORY_FORUMS'}
                
                # Skip if marked as IMPORTANT
                if 'IMPORTANT' in label_ids:
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
    
    def analyze_email_batch(self, emails: List[EmailInfo]) -> Dict[str, bool]:
        """Analyze a batch of emails, using predefined list first, then Claude for uncertain ones"""
        if not emails:
            return {}
        
        results = {}
        emails_needing_ai = []
        
        # First pass: check against known junk senders
        for email in emails:
            sender_email = self._extract_email_address(email.sender)
            
            # Check if sender is in junk list
            if sender_email in self.junk_senders:
                results[email.id] = True  # Mark for deletion
                self.skipped_api_count += 1
            else:
                # Need AI analysis for this one
                emails_needing_ai.append(email)
        
        # If no emails need AI analysis, return early
        if not emails_needing_ai:
            console.print(f"[green]Skipped API calls for all {len(emails)} emails (matched junk list)[/green]")
            return results
        
        # Only call API for emails not in junk list
        if emails_needing_ai:
            console.print(f"[cyan]Using AI for {len(emails_needing_ai)} emails, skipped {len(emails) - len(emails_needing_ai)} (matched junk list)[/cyan]")
            self.api_call_count += 1
            
            # Prepare email data for analysis
            email_data = []
            for email in emails_needing_ai:
                email_data.append({
                    'id': email.id,
                    'subject': email.subject,
                    'sender': email.sender,
                    'snippet': email.snippet[:100]  # First 100 chars of preview
                })
            
            prompt = f"""Analyze these emails and determine which ones are likely junk/spam that can be deleted.
            Consider emails as junk if they are:
            - Marketing/promotional emails
            - Newsletters that are clearly not important
            - Social media notifications
            - Automated system emails that are outdated
            - Spam
            
            DO NOT mark as junk:
            - Personal emails
            - Important business communications
            - Financial/banking emails
            - Order confirmations or receipts
            - Government or legal communications
            - Anything that might be important to keep
            
            Return a JSON object where keys are email IDs and values are boolean (true = delete, false = keep).
            Be conservative - when in doubt, keep the email.
            
            Emails to analyze:
            {json.dumps(email_data, indent=2)}
            
            Return only the JSON object, no other text."""
            
            try:
                response = self.anthropic.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=4000,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                # Parse the response
                result_text = response.content[0].text.strip()
                # Remove any markdown code blocks if present
                if result_text.startswith('```'):
                    result_text = result_text.split('\n', 1)[1].rsplit('\n```', 1)[0]
                
                ai_results = json.loads(result_text)
                results.update(ai_results)
                
            except Exception as e:
                console.print(f"[red]Error analyzing emails: {e}[/red]")
                # Return all uncertain emails as "keep" on error
                for email in emails_needing_ai:
                    results[email.id] = False
        
        return results
    
    def delete_email(self, email_info: EmailInfo):
        """Move email to trash"""
        if self.dry_run:
            console.print(f"[yellow]DRY RUN: Would delete - Subject: '{email_info.subject[:50]}...' | From: {email_info.sender}[/yellow]")
        else:
            try:
                self.service.users().messages().trash(userId='me', id=email_info.id).execute()
                console.print(f"[green]Deleted - Subject: '{email_info.subject[:50]}...' | From: {email_info.sender}[/green]")
            except HttpError as error:
                console.print(f"[red]Error deleting email - Subject: '{email_info.subject[:50]}...' | From: {email_info.sender} | Error: {error}[/red]")
    
    def process_emails(self, total_limit: Optional[int] = None):
        """Process all emails in batches"""
        batch_size = int(os.getenv('BATCH_SIZE', '100'))
        page_token = None
        total_processed = 0
        
        console.print(f"[bold blue]Starting Gmail cleanup (Dry Run: {self.dry_run})[/bold blue]")
        console.print("[yellow]Note: Emails with labels or marked as important will be skipped[/yellow]\n")
        
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
                
                # Analyze batch
                console.print(f"\n[cyan]Analyzing batch of {len(emails)} emails...[/cyan]")
                deletion_decisions = self.analyze_email_batch(emails)
                
                # Process decisions
                for email in emails:
                    should_delete = deletion_decisions.get(email.id, False)
                    
                    if should_delete:
                        self.delete_email(email)
                        self.deleted_count += 1
                    else:
                        self.kept_count += 1
                    
                    self.processed_count += 1
                    total_processed += 1
                    
                    # Update progress
                    if total_limit:
                        progress.update(task, completed=min(total_processed, total_limit))
                    
                    # Stop if we've reached the limit
                    if total_limit and total_processed >= total_limit:
                        break
                
                # Show batch summary
                console.print(f"[dim]Batch complete. Total processed: {self.processed_count}[/dim]")
                
                # Check if interrupted during batch processing
                if self.interrupted:
                    console.print("\n[yellow]Gracefully stopping after completing current batch.[/yellow]")
                    break
                
                # Check if there are more emails
                if not page_token:
                    break
                
                # Small delay to avoid rate limiting
                time.sleep(1)
        
        # Final summary
        self._print_summary()
        
        if self.interrupted:
            console.print("\n[yellow]Process interrupted by user. Summary shows emails processed before interruption.[/yellow]")
    
    def _print_summary(self):
        """Print final summary table"""
        table = Table(title="Gmail Cleanup Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")
        
        table.add_row("Total Processed", str(self.processed_count))
        table.add_row("Emails Deleted", str(self.deleted_count))
        table.add_row("Emails Kept", str(self.kept_count))
        table.add_row("", "")
        table.add_row("API Calls Made", str(self.api_call_count))
        table.add_row("Emails Matched Junk List", str(self.skipped_api_count))
        
        console.print("\n")
        console.print(table)
        
        if self.dry_run:
            console.print("\n[yellow]This was a DRY RUN. No emails were actually deleted.[/yellow]")
            console.print("[yellow]Set DRY_RUN=false in .env to actually delete emails.[/yellow]")


def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='AI-powered Gmail inbox cleaner')
    parser.add_argument('--limit', type=int, help='Maximum number of emails to process')
    parser.add_argument('--batch-size', type=int, default=100, help='Number of emails per batch (default: 100)')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode (don\'t actually delete)')
    parser.add_argument('--no-dry-run', dest='dry_run', action='store_false', help='Actually delete emails')
    parser.set_defaults(dry_run=None)
    
    args = parser.parse_args()
    
    # Check for required environment variables
    if not os.getenv('ANTHROPIC_API_KEY'):
        console.print("[red]Error: ANTHROPIC_API_KEY not found in environment variables[/red]")
        console.print("Please create a .env file with your Anthropic API key")
        return
    
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