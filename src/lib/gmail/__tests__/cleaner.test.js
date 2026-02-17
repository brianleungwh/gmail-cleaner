/**
 * Tests for DomainCleaner class
 *
 * Port of tests/test_cleaner.py
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DomainCleaner } from '../cleaner.js';
import { createApiMocks, sampleInbox } from './testUtils.js';

// Top-level mock with vi.fn() stubs — hoisted safely
vi.mock('../api.js', () => ({
  getInboxInfo: vi.fn(),
  listThreads: vi.fn(),
  getThread: vi.fn(),
  trashThread: vi.fn(),
}));

import * as api from '../api.js';

// === Sample Thread Data ===

function makeCleanupThread(threadId, domain, subject, sender, messageCount = 1) {
  return {
    thread_id: threadId,
    domain,
    subject,
    sender,
    message_count: messageCount,
  };
}

function sampleThreads() {
  return [
    makeCleanupThread('thread_001', 'spam.com', 'Buy now!', 'promo@spam.com', 2),
    makeCleanupThread('thread_002', 'spam.com', 'Limited offer', 'deals@spam.com', 1),
    makeCleanupThread('thread_003', 'junk.com', 'You won!', 'winner@junk.com', 3),
  ];
}

// Track mocks at module level so we can check trashedThreads in assertions
let currentMocks;

// === Cleanup Tests ===

describe('cleanup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentMocks = createApiMocks(sampleInbox());

    api.getInboxInfo.mockImplementation(currentMocks.getInboxInfo);
    api.listThreads.mockImplementation(currentMocks.listThreads);
    api.getThread.mockImplementation(currentMocks.getThread);
    api.trashThread.mockImplementation(currentMocks.trashThread);
  });

  it('dry run reports deletions without actually trashing', async () => {
    const cleaner = new DomainCleaner({ dryRun: true, limit: null });
    const result = await cleaner.cleanup(sampleThreads());

    // Should report all threads as deleted
    expect(result.threads_processed).toBe(3);
    expect(result.threads_deleted).toBe(3);
    expect(result.messages_deleted).toBe(6); // 2 + 1 + 3

    // But no threads should actually be trashed
    expect(currentMocks.trashedThreads.size).toBe(0);
  });

  it('live run actually trashes threads', async () => {
    const cleaner = new DomainCleaner({ dryRun: false, limit: null });
    const result = await cleaner.cleanup(sampleThreads());

    // Should report all threads as deleted
    expect(result.threads_processed).toBe(3);
    expect(result.threads_deleted).toBe(3);
    expect(result.messages_deleted).toBe(6);

    // Threads should actually be trashed
    expect(currentMocks.trashedThreads.size).toBe(3);
    expect(currentMocks.trashedThreads.has('thread_001')).toBe(true);
    expect(currentMocks.trashedThreads.has('thread_002')).toBe(true);
    expect(currentMocks.trashedThreads.has('thread_003')).toBe(true);
  });

  it('empty thread list returns zero stats', async () => {
    const cleaner = new DomainCleaner({ dryRun: true, limit: null });
    const result = await cleaner.cleanup([]);

    expect(result.threads_processed).toBe(0);
    expect(result.threads_deleted).toBe(0);
    expect(result.messages_deleted).toBe(0);
    expect(result.messages_kept).toBe(0);
  });

  it('handles trash error gracefully', async () => {
    const failMocks = createApiMocks(sampleInbox(), { failThreads: new Set(['thread_001']) });
    api.trashThread.mockImplementation(failMocks.trashThread);
    currentMocks = failMocks;

    const cleaner = new DomainCleaner({ dryRun: false, limit: null });
    const result = await cleaner.cleanup(sampleThreads());

    // All threads processed
    expect(result.threads_processed).toBe(3);

    // thread_001 should fail, others succeed
    expect(result.threads_deleted).toBe(2);
    expect(result.messages_kept).toBe(2); // thread_001 has 2 messages
    expect(result.messages_deleted).toBe(4); // 1 + 3 from successful threads
  });

  it('calls progress callback during cleanup', async () => {
    const progressEvents = [];
    const callback = async (event, data) => progressEvents.push([event, data]);

    const cleaner = new DomainCleaner({ dryRun: true, limit: null }, callback);
    await cleaner.cleanup(sampleThreads());

    const eventTypes = progressEvents.map(e => e[0]);
    expect(eventTypes).toContain('cleanup_started');
    expect(eventTypes).toContain('cleanup_completed');
    expect(eventTypes).toContain('thread_analyzed');
    expect(eventTypes).toContain('would_delete'); // dry run
  });

  it('live cleanup emits deleted events instead of would_delete', async () => {
    const progressEvents = [];
    const callback = async (event, data) => progressEvents.push([event, data]);

    const cleaner = new DomainCleaner({ dryRun: false, limit: null }, callback);
    await cleaner.cleanup(sampleThreads());

    const eventTypes = progressEvents.map(e => e[0]);
    expect(eventTypes).toContain('deleted');
    expect(eventTypes).not.toContain('would_delete');
  });
});

// === Build Stats Tests ===

describe('buildStats', () => {
  it('includes all fields', () => {
    const result = DomainCleaner.buildStats(10, 8, 20, 5);

    expect(result.threads_processed).toBe(10);
    expect(result.threads_deleted).toBe(8);
    expect(result.messages_deleted).toBe(20);
    expect(result.messages_kept).toBe(5);
  });

  it('handles all zeros', () => {
    const result = DomainCleaner.buildStats(0, 0, 0, 0);

    expect(result.threads_processed).toBe(0);
    expect(result.threads_deleted).toBe(0);
    expect(result.messages_deleted).toBe(0);
    expect(result.messages_kept).toBe(0);
  });
});

// === Interrupt Handling Tests ===

describe('interrupt handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const mocks = createApiMocks(sampleInbox());

    api.getInboxInfo.mockImplementation(mocks.getInboxInfo);
    api.listThreads.mockImplementation(mocks.listThreads);
    api.getThread.mockImplementation(mocks.getThread);
    api.trashThread.mockImplementation(mocks.trashThread);
  });

  it('stops when interrupted flag is set', async () => {
    const cleaner = new DomainCleaner({ dryRun: true, limit: null });

    let processedCount = 0;
    cleaner.progressCallback = async (event) => {
      if (event === 'thread_analyzed') {
        processedCount += 1;
        if (processedCount >= 1) {
          cleaner.interrupted = true;
        }
      }
    };

    const result = await cleaner.cleanup(sampleThreads());

    // Should have stopped early
    expect(result.threads_processed).toBeLessThan(sampleThreads().length);
  });
});
