/**
 * Domain Cleaner - Handles email cleanup for selected domains
 */

import { trashThread } from './api.js';
import { CleanupStats } from '../models/index.js';
import { SUBJECT_TRUNCATE_CLEANER } from '../constants.js';

export class DomainCleaner {
  constructor(config, progressCallback = null) {
    this.config = config;
    this.progressCallback = progressCallback;
    this.interrupted = false;

    // Pollable progress state — UI reads this via setInterval
    this.progress = {
      totalToProcess: 0,
      totalProcessed: 0,
      threadsDeleted: 0,
      messagesDeleted: 0,
      currentSubject: '',
      dryRun: false,
      status: 'idle',
    };
  }

  // === Main Entry Point ===

  async cleanup(threads) {
    if (!threads || threads.length === 0) {
      return DomainCleaner.buildStats(0, 0, 0, 0);
    }

    // Initialize pollable progress
    this.progress.totalToProcess = threads.length;
    this.progress.dryRun = this.config.dryRun;
    this.progress.status = 'running';
    this.progress.totalProcessed = 0;
    this.progress.threadsDeleted = 0;
    this.progress.messagesDeleted = 0;
    this.progress.currentSubject = '';

    await this._reportProgress('cleanup_started', {
      dry_run: this.config.dryRun,
      limit: this.config.limit,
      threads_to_process: threads.length,
    });

    let totalProcessed = 0;
    let threadsDeleted = 0;
    let messagesDeleted = 0;
    let messagesKept = 0;

    for (const thread of threads) {
      if (this.interrupted) break;

      const { thread_id, domain, subject, sender, message_count } = thread;

      const truncatedSubject = subject.length > SUBJECT_TRUNCATE_CLEANER
        ? subject.slice(0, SUBJECT_TRUNCATE_CLEANER) + '...'
        : subject;

      // Update pollable progress in-place
      this.progress.currentSubject = truncatedSubject;

      if (this.config.dryRun) {
        // Dry run - just count what would happen
        threadsDeleted += 1;
        messagesDeleted += message_count;
      } else {
        // Actually delete the thread
        const success = await this._trashThread(thread_id);

        if (success) {
          threadsDeleted += 1;
          messagesDeleted += message_count;
        } else {
          messagesKept += message_count;
        }
      }

      totalProcessed += 1;

      // Update pollable progress in-place
      this.progress.totalProcessed = totalProcessed;
      this.progress.threadsDeleted = threadsDeleted;
      this.progress.messagesDeleted = messagesDeleted;
    }

    this.progress.status = 'completed';

    const result = DomainCleaner.buildStats(totalProcessed, threadsDeleted, messagesDeleted, messagesKept);
    await this._reportProgress('cleanup_completed', result);

    return result;
  }

  // === Thread Processing ===

  async _trashThread(threadId) {
    try {
      await trashThread(threadId);
      return true;
    } catch (error) {
      console.error(`Error trashing thread ${threadId}:`, error);
      return false;
    }
  }

  // === Progress ===

  async _reportProgress(event, data) {
    if (this.progressCallback) {
      await this.progressCallback(event, data);
    }
  }

  // === Results ===

  static buildStats(processed, deleted, messagesDeleted, kept) {
    return new CleanupStats({
      threads_processed: processed,
      threads_deleted: deleted,
      messages_deleted: messagesDeleted,
      messages_kept: kept,
    });
  }
}
