"""
Shared data models for Gmail Cleaner
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set


@dataclass
class ThreadMetadata:
    """Metadata for a single email thread"""
    thread_id: str
    domain: str
    subject: str
    sender: str
    message_count: int
    label_ids: List[str] = field(default_factory=list)


@dataclass
class DomainInfo:
    """Domain information for collection results"""
    domain: str
    count: int
    threads: List[Dict]  # [{thread_id, subject, sender, message_count}, ...]


@dataclass
class CollectionConfig:
    """Configuration for domain collection"""
    limit: Optional[int] = None
    excluded_domains: Set[str] = field(default_factory=set)
    use_label_protection: bool = True
    protected_label_ids: Optional[Set[str]] = None


@dataclass
class CleanupConfig:
    """Configuration for email cleanup"""
    dry_run: bool = True
    limit: Optional[int] = None
