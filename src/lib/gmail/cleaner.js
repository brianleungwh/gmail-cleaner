/**
 * Domain Cleaner - Handles email cleanup for selected domains
 *
 * Port of app/cleaner.py
 */

import { trashThread } from './api.js';

export class DomainCleaner {
  constructor(config, progressCallback = null) {
    this.config = config;
    this.progressCallback = progressCallback;
    this.interrupted = false;
  }

  // === Main Entry Point ===

  async cleanup(threads) {
    if (!threads || threads.length === 0) {
      return DomainCleaner.buildStats(0, 0, 0, 0);
    }

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

      const truncatedSubject = subject.length > 50
        ? subject.slice(0, 50) + '...'
        : subject;

      // Log what we're analyzing
      await this._reportProgress('thread_analyzed', {
        thread_id,
        subject: truncatedSubject,
        sender,
      });

      if (this.config.dryRun) {
        // Dry run - just report what would happen
        await this._reportProgress('would_delete', {
          thread_id,
          subject: truncatedSubject,
          sender,
          message_count,
        });
        threadsDeleted += 1;
        messagesDeleted += message_count;
      } else {
        // Actually delete the thread
        const success = await this._trashThread(thread_id);

        if (success) {
          await this._reportProgress('deleted', {
            thread_id,
            subject: truncatedSubject,
            sender,
            message_count,
          });
          threadsDeleted += 1;
          messagesDeleted += message_count;
        } else {
          await this._reportProgress('delete_error', {
            thread_id,
            error: 'Failed to trash thread',
          });
          messagesKept += message_count;
        }
      }

      totalProcessed += 1;
    }

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
    return {
      threads_processed: processed,
      threads_deleted: deleted,
      messages_deleted: messagesDeleted,
      messages_kept: kept,
    };
  }
}
