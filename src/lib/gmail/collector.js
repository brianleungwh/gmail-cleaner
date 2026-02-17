/**
 * Domain Collector - Handles domain collection from Gmail inbox
 *
 * Port of app/collector.py
 */

import { getInboxInfo, listThreads, getThread } from './api.js';

export class DomainCollector {
  constructor(config, progressCallback = null) {
    this.config = config;
    this.progressCallback = progressCallback;

    // Results - exposed for cleanup to access
    this.threadsById = {};      // threadId -> ThreadMetadata
    this.threadsByDomain = {};  // domain -> [threadId, ...]
    this.interrupted = false;
  }

  // === Main Entry Point ===

  async collect() {
    const totalThreadCount = await this._getTotalThreadCount();
    const effectiveTotal = this.config.limit
      ? Math.min(this.config.limit, totalThreadCount)
      : totalThreadCount;

    const message = this.config.limit
      ? `Starting domain collection (limit: ${this.config.limit} threads)...`
      : 'Starting domain collection...';

    await this._reportProgress('collection_started', {
      message,
      total_threads: effectiveTotal,
      limit: this.config.limit,
    });

    // Clear any previous state
    this.threadsById = {};
    this.threadsByDomain = {};

    const domainData = {}; // domain -> { count, subjects[] }
    let pageToken = null;
    let totalThreads = 0;

    while (!this.interrupted) {
      try {
        const { threads, nextPageToken } = await this._fetchThreadPage(pageToken);

        if (!threads || threads.length === 0) {
          break;
        }

        for (const thread of threads) {
          if (this.interrupted) break;

          const threadId = thread.id;
          const metadata = await this._getThreadMetadata(threadId);

          if (metadata === null) continue;
          if (!this._shouldInclude(metadata)) continue;

          // Store thread
          this._storeThread(metadata);

          // Update domain data
          if (!domainData[metadata.domain]) {
            domainData[metadata.domain] = { count: 0, subjects: [] };
          }
          domainData[metadata.domain].count += 1;
          if (
            !domainData[metadata.domain].subjects.includes(metadata.subject) &&
            domainData[metadata.domain].subjects.length < 3
          ) {
            domainData[metadata.domain].subjects.push(metadata.subject);
          }

          totalThreads += 1;

          // Send progress update
          const truncatedSubject = metadata.subject.length > 60
            ? metadata.subject.slice(0, 60) + '...'
            : metadata.subject;

          await this._reportProgress('thread_processed', {
            thread_id: threadId,
            domain: metadata.domain,
            subject: truncatedSubject,
            processed_threads: totalThreads,
            total_threads: effectiveTotal,
            unique_domains: Object.keys(domainData).length,
          });

          // Check limit
          if (this.config.limit && totalThreads >= this.config.limit) {
            break;
          }

          // Yield control every 10 threads to let UI update
          if (totalThreads % 10 === 0) {
            await new Promise((r) => setTimeout(r, 0));
          }
        }

        // Check if we hit limit
        if (this.config.limit && totalThreads >= this.config.limit) {
          break;
        }

        pageToken = nextPageToken;
        if (!pageToken) break;
      } catch (error) {
        await this._reportProgress('error', {
          message: `Error fetching threads: ${error.message || error}`,
        });
        break;
      }
    }

    // Build results
    const result = this._buildResults(domainData);

    const limitMsg = this.config.limit ? ` (limited to ${this.config.limit})` : '';
    await this._reportProgress('collection_completed', {
      processed_threads: totalThreads,
      total_threads: effectiveTotal,
      unique_domains: Object.keys(result).length,
      message: `Collection complete${limitMsg}: ${totalThreads.toLocaleString()} threads processed, ${Object.keys(result).length.toLocaleString()} unique domains`,
    });

    return result;
  }

  // === Thread Fetching ===

  async _getTotalThreadCount() {
    try {
      const inboxInfo = await getInboxInfo();
      return inboxInfo.threadsTotal || 0;
    } catch (e) {
      console.warn('Could not get inbox thread count:', e);
      return 0;
    }
  }

  async _fetchThreadPage(pageToken) {
    const result = await listThreads({
      maxResults: 100,
      pageToken,
      q: 'in:inbox',
    });

    return {
      threads: result.threads || [],
      nextPageToken: result.nextPageToken || null,
    };
  }

  async _getThreadMetadata(threadId) {
    const threadData = await getThread(threadId, {
      format: 'metadata',
      metadataHeaders: ['From', 'Subject'],
    });

    const messages = threadData.messages || [];
    if (messages.length === 0) return null;

    const firstMessage = messages[0];
    const headers = {};
    for (const h of (firstMessage.payload?.headers || [])) {
      headers[h.name] = h.value;
    }

    const sender = headers['From'] || '(Unknown Sender)';
    const subject = headers['Subject'] || '(No Subject)';
    const senderEmail = DomainCollector.extractEmailAddress(sender);

    // Get labels from both thread and message level
    const threadLabelIds = threadData.labelIds || [];
    const firstMessageLabelIds = firstMessage.labelIds || [];
    const allLabelIds = [...new Set([...threadLabelIds, ...firstMessageLabelIds])];

    const domain = DomainCollector.extractDomain(senderEmail);
    if (!domain) return null;

    return {
      threadId,
      domain,
      subject,
      sender: senderEmail,
      messageCount: messages.length,
      labelIds: allLabelIds,
    };
  }

  // === Filtering ===

  _isProtected(labelIds) {
    // Always protect IMPORTANT and STARRED
    if (labelIds.includes('IMPORTANT') || labelIds.includes('STARRED')) {
      return true;
    }

    // Skip label protection if disabled
    if (!this.config.useLabelProtection) {
      return false;
    }

    // Check for custom user labels
    const customLabels = labelIds.filter((l) => l.startsWith('Label_'));
    if (customLabels.length === 0) return false;

    // If specific labels provided, only protect those
    if (this.config.protectedLabelIds !== null) {
      return customLabels.some((l) => this.config.protectedLabelIds.has(l));
    }

    // Otherwise protect any custom label (default behavior)
    return true;
  }

  _isExcluded(domain) {
    return this.config.excludedDomains.has(domain);
  }

  _shouldInclude(metadata) {
    if (this._isProtected(metadata.labelIds)) return false;
    if (this._isExcluded(metadata.domain)) return false;
    return true;
  }

  // === Storage ===

  _storeThread(metadata) {
    this.threadsById[metadata.threadId] = metadata;
    if (!this.threadsByDomain[metadata.domain]) {
      this.threadsByDomain[metadata.domain] = [];
    }
    this.threadsByDomain[metadata.domain].push(metadata.threadId);
  }

  // === Results ===

  _buildResults(domainData) {
    const result = {};

    for (const [domain, data] of Object.entries(domainData)) {
      const threadIds = this.threadsByDomain[domain] || [];
      const threads = [];

      for (const threadId of threadIds) {
        const metadata = this.threadsById[threadId];
        if (metadata) {
          threads.push({
            thread_id: threadId,
            subject: metadata.subject,
            sender: metadata.sender,
            message_count: metadata.messageCount,
          });
        }
      }

      result[domain] = {
        domain,
        count: data.count,
        threads,
      };
    }

    return result;
  }

  // === Progress ===

  async _reportProgress(event, data) {
    if (this.progressCallback) {
      await this.progressCallback(event, data);
    }
  }

  // === Utilities ===

  static extractEmailAddress(sender) {
    const match = sender.match(/<([^>]+)>/);
    if (match) return match[1].toLowerCase();
    return sender.trim().toLowerCase();
  }

  static extractDomain(email) {
    if (email.includes('@')) {
      return email.split('@')[1].toLowerCase();
    }
    return '';
  }
}
