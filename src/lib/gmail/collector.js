/**
 * Domain Collector - Handles domain collection from Gmail inbox
 */

import { getInboxInfo, listThreads, getThread } from './api.js';
import { ThreadsList, Thread, CleanupThread, DomainResult, CollectionResult } from '../models/index.js';
import {
  SUBJECT_TRUNCATE_COLLECTOR,
  UI_YIELD_INTERVAL,
  THREAD_PAGE_SIZE,
} from '../constants.js';
import { getErrorMessage } from '../errors.js';

export class DomainCollector {
  constructor(config, progressCallback = null) {
    this.config = config;
    this.progressCallback = progressCallback;

    // Results - exposed for cleanup to access
    this.threadsById = {};      // threadId -> Thread
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

    const domainCounts = {}; // domain -> count
    let pageToken = null;
    let totalThreads = 0;

    while (!this.interrupted) {
      try {
        const page = await this._fetchThreadPage(pageToken);

        if (page.threadIds.length === 0) {
          break;
        }

        for (const threadId of page.threadIds) {
          if (this.interrupted) break;

          const thread = await this._getThread(threadId);

          if (thread === null) continue;
          if (!this._shouldInclude(thread)) continue;

          // Store thread
          this._storeThread(thread);

          // Track domain count
          const domain = thread.getDomain();
          domainCounts[domain] = (domainCounts[domain] || 0) + 1;

          totalThreads += 1;

          // Send progress update
          const subject = thread.getSubject();
          const truncatedSubject = subject.length > SUBJECT_TRUNCATE_COLLECTOR
            ? subject.slice(0, SUBJECT_TRUNCATE_COLLECTOR) + '...'
            : subject;

          await this._reportProgress('thread_processed', {
            thread_id: threadId,
            domain,
            subject: truncatedSubject,
            processed_threads: totalThreads,
            total_threads: effectiveTotal,
            unique_domains: Object.keys(domainCounts).length,
          });

          // Check limit
          if (this.config.limit && totalThreads >= this.config.limit) {
            break;
          }

          // Yield control periodically to let UI update
          if (totalThreads % UI_YIELD_INTERVAL === 0) {
            await new Promise((r) => setTimeout(r, 0));
          }
        }

        // Check if we hit limit
        if (this.config.limit && totalThreads >= this.config.limit) {
          break;
        }

        pageToken = page.nextPageToken;
        if (!pageToken) break;
      } catch (error) {
        await this._reportProgress('error', {
          message: `Error fetching threads: ${getErrorMessage(error)}`,
        });
        break;
      }
    }

    // Build results
    const result = this._buildResults(domainCounts);

    const limitMsg = this.config.limit ? ` (limited to ${this.config.limit})` : '';
    await this._reportProgress('collection_completed', {
      processed_threads: totalThreads,
      total_threads: effectiveTotal,
      unique_domains: Object.keys(result.domainResults).length,
      message: `Collection complete${limitMsg}: ${totalThreads.toLocaleString()} threads processed, ${Object.keys(result.domainResults).length.toLocaleString()} unique domains`,
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
    const raw = await listThreads({
      maxResults: THREAD_PAGE_SIZE,
      pageToken,
      q: 'in:inbox',
    });

    return new ThreadsList(raw);
  }

  async _getThread(threadId) {
    const raw = await getThread(threadId, {
      format: 'metadata',
      metadataHeaders: ['From', 'Subject'],
    });

    const thread = new Thread(threadId, raw);
    if (thread.isEmpty() || !thread.getDomain()) return null;

    return thread;
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

  _shouldInclude(thread) {
    if (this._isProtected(thread.getLabelIds())) return false;
    if (this._isExcluded(thread.getDomain())) return false;
    return true;
  }

  // === Storage ===

  _storeThread(thread) {
    const domain = thread.getDomain();
    this.threadsById[thread.threadId] = thread;
    if (!this.threadsByDomain[domain]) {
      this.threadsByDomain[domain] = [];
    }
    this.threadsByDomain[domain].push(thread.threadId);
  }

  // === Results ===

  _buildResults(domainCounts) {
    const domainResults = {};

    for (const [domain, count] of Object.entries(domainCounts)) {
      const threadIds = this.threadsByDomain[domain] || [];
      const threads = threadIds
        .map((id) => this.threadsById[id])
        .filter(Boolean)
        .map((thread) => CleanupThread.fromThread(thread));

      domainResults[domain] = new DomainResult({ domain, count, threads });
    }

    return new CollectionResult(domainResults, this.threadsById, this.threadsByDomain);
  }

  // === Progress ===

  async _reportProgress(event, data) {
    if (this.progressCallback) {
      await this.progressCallback(event, data);
    }
  }

}
