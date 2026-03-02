/**
 * Domain Collector - Handles domain collection from Gmail inbox
 */

import { getInboxInfo, listThreads, getThread } from './api.js';
import { ThreadsList, Thread, CleanupThread, DomainResult, CollectionResult } from '../models/index.js';
import {
  SUBJECT_TRUNCATE_COLLECTOR,
  MILESTONE_LOG_INTERVAL,
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

    // Pollable progress state — UI reads this via setInterval
    this.progress = {
      processedThreads: 0,
      totalThreads: 0,
      uniqueDomains: 0,
      currentDomain: '',
      status: 'idle', // 'idle' | 'running' | 'completed' | 'error'
      errorMessage: null,
    };
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

    // Initialize pollable progress
    this.progress.status = 'running';
    this.progress.totalThreads = effectiveTotal;
    this.progress.processedThreads = 0;
    this.progress.uniqueDomains = 0;
    this.progress.currentDomain = '';
    this.progress.errorMessage = null;

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

          // Update pollable progress in-place (no await, no callback)
          this.progress.processedThreads = totalThreads;
          this.progress.uniqueDomains = Object.keys(domainCounts).length;
          this.progress.currentDomain = domain;

          // Milestone logging — infrequent, so callback cost is fine
          if (totalThreads % MILESTONE_LOG_INTERVAL === 0) {
            await this._reportProgress('milestone', {
              processed_threads: totalThreads,
              total_threads: effectiveTotal,
              unique_domains: Object.keys(domainCounts).length,
            });
          }

          // Check limit
          if (this.config.limit && totalThreads >= this.config.limit) {
            break;
          }
        }

        // Check if we hit limit
        if (this.config.limit && totalThreads >= this.config.limit) {
          break;
        }

        pageToken = page.nextPageToken;
        if (!pageToken) break;
      } catch (error) {
        this.progress.status = 'error';
        this.progress.errorMessage = getErrorMessage(error);
        await this._reportProgress('error', {
          message: `Error fetching threads: ${getErrorMessage(error)}`,
        });
        break;
      }
    }

    // Build results
    const result = this._buildResults(domainCounts);

    const limitMsg = this.config.limit ? ` (limited to ${this.config.limit})` : '';
    this.progress.status = 'completed';

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
