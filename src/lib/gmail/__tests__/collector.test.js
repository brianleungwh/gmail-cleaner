/**
 * Tests for DomainCollector class
 *
 * Port of tests/test_collector.py
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DomainCollector } from '../collector.js';
import { sampleInbox, createApiMocks } from './testUtils.js';

// Top-level mock with vi.fn() stubs — hoisted safely
vi.mock('../api.js', () => ({
  getInboxInfo: vi.fn(),
  listThreads: vi.fn(),
  getThread: vi.fn(),
  trashThread: vi.fn(),
}));

import * as api from '../api.js';

// === Static Method Tests ===

describe('extractEmailAddress', () => {
  it('extracts email from Name <email> format', () => {
    const result = DomainCollector.extractEmailAddress('John Doe <john@example.com>');
    expect(result).toBe('john@example.com');
  });

  it('handles plain email', () => {
    const result = DomainCollector.extractEmailAddress('john@example.com');
    expect(result).toBe('john@example.com');
  });

  it('normalizes to lowercase', () => {
    const result = DomainCollector.extractEmailAddress('John@EXAMPLE.COM');
    expect(result).toBe('john@example.com');
  });

  it('handles whitespace around email', () => {
    const result = DomainCollector.extractEmailAddress('  john@example.com  ');
    expect(result).toBe('john@example.com');
  });

  it('handles complex display names', () => {
    const result = DomainCollector.extractEmailAddress('"Doe, John" <john@example.com>');
    expect(result).toBe('john@example.com');
  });
});

describe('extractDomain', () => {
  it('extracts domain from simple email', () => {
    const result = DomainCollector.extractDomain('john@example.com');
    expect(result).toBe('example.com');
  });

  it('extracts domain including subdomain', () => {
    const result = DomainCollector.extractDomain('john@mail.example.com');
    expect(result).toBe('mail.example.com');
  });

  it('normalizes domain to lowercase', () => {
    const result = DomainCollector.extractDomain('john@EXAMPLE.COM');
    expect(result).toBe('example.com');
  });

  it('returns empty string if no @ symbol', () => {
    const result = DomainCollector.extractDomain('invalid');
    expect(result).toBe('');
  });

  it('handles empty string', () => {
    const result = DomainCollector.extractDomain('');
    expect(result).toBe('');
  });
});

// === Protection Logic Tests ===

describe('isProtected', () => {
  function makeCollector(configOverrides = {}) {
    const config = {
      limit: null,
      excludedDomains: new Set(),
      useLabelProtection: true,
      protectedLabelIds: null,
      ...configOverrides,
    };
    return new DomainCollector(config);
  }

  it('IMPORTANT label should always protect', () => {
    const collector = makeCollector();
    expect(collector._isProtected(['INBOX', 'IMPORTANT'])).toBe(true);
  });

  it('STARRED label should always protect', () => {
    const collector = makeCollector();
    expect(collector._isProtected(['INBOX', 'STARRED'])).toBe(true);
  });

  it('custom labels protect by default', () => {
    const collector = makeCollector();
    expect(collector._isProtected(['INBOX', 'Label_12345'])).toBe(true);
  });

  it('custom labels do not protect when disabled', () => {
    const collector = makeCollector({ useLabelProtection: false });
    expect(collector._isProtected(['INBOX', 'Label_12345'])).toBe(false);
  });

  it('IMPORTANT still protects when label protection disabled', () => {
    const collector = makeCollector({ useLabelProtection: false });
    expect(collector._isProtected(['INBOX', 'IMPORTANT'])).toBe(true);
  });

  it('specific protectedLabelIds only protect matching labels', () => {
    const collector = makeCollector({ protectedLabelIds: new Set(['Label_12345']) });

    // Matching label should protect
    expect(collector._isProtected(['INBOX', 'Label_12345'])).toBe(true);

    // Non-matching custom label should not protect
    expect(collector._isProtected(['INBOX', 'Label_99999'])).toBe(false);
  });

  it('regular INBOX label does not protect', () => {
    const collector = makeCollector();
    expect(collector._isProtected(['INBOX'])).toBe(false);
  });

  it('empty labels do not protect', () => {
    const collector = makeCollector();
    expect(collector._isProtected([])).toBe(false);
  });
});

// === Exclusion Logic Tests ===

describe('isExcluded', () => {
  function makeCollector(excludedDomains = new Set()) {
    return new DomainCollector({
      limit: null,
      excludedDomains,
      useLabelProtection: true,
      protectedLabelIds: null,
    });
  }

  it('domain in exclusion list is excluded', () => {
    const collector = makeCollector(new Set(['spam.com', 'junk.com']));
    expect(collector._isExcluded('spam.com')).toBe(true);
  });

  it('domain not in exclusion list is not excluded', () => {
    const collector = makeCollector(new Set(['spam.com', 'junk.com']));
    expect(collector._isExcluded('social.com')).toBe(false);
  });

  it('empty exclusion list excludes nothing', () => {
    const collector = makeCollector();
    expect(collector._isExcluded('spam.com')).toBe(false);
  });
});

// === Should Include Tests ===

describe('shouldInclude', () => {
  function makeCollector(configOverrides = {}) {
    const config = {
      limit: null,
      excludedDomains: new Set(),
      useLabelProtection: true,
      protectedLabelIds: null,
      ...configOverrides,
    };
    return new DomainCollector(config);
  }

  it('regular thread is included', () => {
    const collector = makeCollector();
    const metadata = {
      threadId: 'test',
      domain: 'spam.com',
      subject: 'Test',
      sender: 'test@spam.com',
      messageCount: 1,
      labelIds: ['INBOX'],
    };
    expect(collector._shouldInclude(metadata)).toBe(true);
  });

  it('protected thread is excluded', () => {
    const collector = makeCollector();
    const metadata = {
      threadId: 'test',
      domain: 'important.com',
      subject: 'Test',
      sender: 'test@important.com',
      messageCount: 1,
      labelIds: ['INBOX', 'IMPORTANT'],
    };
    expect(collector._shouldInclude(metadata)).toBe(false);
  });

  it('excluded domain thread is excluded', () => {
    const collector = makeCollector({ excludedDomains: new Set(['spam.com']) });
    const metadata = {
      threadId: 'test',
      domain: 'spam.com',
      subject: 'Test',
      sender: 'test@spam.com',
      messageCount: 1,
      labelIds: ['INBOX'],
    };
    expect(collector._shouldInclude(metadata)).toBe(false);
  });
});

// === Collection Tests (Async) ===

describe('collect', () => {
  let mocks;

  beforeEach(() => {
    vi.clearAllMocks();
    mocks = createApiMocks(sampleInbox());

    api.getInboxInfo.mockImplementation(mocks.getInboxInfo);
    api.listThreads.mockImplementation(mocks.listThreads);
    api.getThread.mockImplementation(mocks.getThread);
    api.trashThread.mockImplementation(mocks.trashThread);
  });

  function defaultConfig(overrides = {}) {
    return {
      limit: null,
      excludedDomains: new Set(),
      useLabelProtection: true,
      protectedLabelIds: null,
      ...overrides,
    };
  }

  it('basic collection groups threads by domain', async () => {
    const collector = new DomainCollector(defaultConfig());
    const result = await collector.collect();

    // Should have collected domains (excluding protected ones)
    expect(Object.keys(result).length).toBeGreaterThan(0);

    // spam.com should have 2 threads (thread_001, thread_002)
    expect(result['spam.com']).toBeDefined();
    expect(result['spam.com'].count).toBe(2);

    // social.com should have 1 thread
    expect(result['social.com']).toBeDefined();
    expect(result['social.com'].count).toBe(1);
  });

  it('skips protected threads', async () => {
    const collector = new DomainCollector(defaultConfig());
    const result = await collector.collect();

    // important.com is IMPORTANT labeled - should not be in results
    expect(result['important.com']).toBeUndefined();

    // starred.com is STARRED labeled - should not be in results
    expect(result['starred.com']).toBeUndefined();

    // labeled.com has custom label - should not be in results
    expect(result['labeled.com']).toBeUndefined();
  });

  it('respects limit parameter', async () => {
    const collector = new DomainCollector(defaultConfig({ limit: 2 }));
    const result = await collector.collect();

    // Should have at most 2 threads total across all domains
    const totalThreads = Object.values(result).reduce((sum, info) => sum + info.count, 0);
    expect(totalThreads).toBeLessThanOrEqual(2);
  });

  it('skips excluded domains', async () => {
    const collector = new DomainCollector(defaultConfig({ excludedDomains: new Set(['spam.com']) }));
    const result = await collector.collect();

    // spam.com should not be in results
    expect(result['spam.com']).toBeUndefined();

    // Other domains should still be present
    expect(result['social.com']).toBeDefined();
  });

  it('empty inbox returns empty dict', async () => {
    const emptyMocks = createApiMocks({ threadsTotal: 0, threads: [] });
    api.getInboxInfo.mockImplementation(emptyMocks.getInboxInfo);
    api.listThreads.mockImplementation(emptyMocks.listThreads);
    api.getThread.mockImplementation(emptyMocks.getThread);
    api.trashThread.mockImplementation(emptyMocks.trashThread);

    const collector = new DomainCollector(defaultConfig());
    const result = await collector.collect();

    expect(Object.keys(result).length).toBe(0);
  });

  it('stores thread metadata', async () => {
    const collector = new DomainCollector(defaultConfig());
    await collector.collect();

    // Should have stored threads
    expect(Object.keys(collector.threadsById).length).toBeGreaterThan(0);
    expect(Object.keys(collector.threadsByDomain).length).toBeGreaterThan(0);

    // Check that spam.com threads are stored
    expect(collector.threadsByDomain['spam.com']).toBeDefined();
    expect(collector.threadsByDomain['spam.com'].length).toBe(2);
  });

  it('multi-message thread reports correct message count', async () => {
    const collector = new DomainCollector(defaultConfig());
    const result = await collector.collect();

    // multi.com thread has 3 messages
    expect(result['multi.com']).toBeDefined();
    expect(result['multi.com'].threads.length).toBe(1);
    expect(result['multi.com'].threads[0].message_count).toBe(3);
  });

  it('handles plain email format (no angle brackets)', async () => {
    const collector = new DomainCollector(defaultConfig());
    const result = await collector.collect();

    // edge.com uses plain email format
    expect(result['edge.com']).toBeDefined();
  });

  it('calls progress callback', async () => {
    const progressEvents = [];
    const callback = async (event, data) => progressEvents.push([event, data]);

    const collector = new DomainCollector(defaultConfig(), callback);
    await collector.collect();

    const eventTypes = progressEvents.map(e => e[0]);
    expect(eventTypes).toContain('collection_started');
    expect(eventTypes).toContain('collection_completed');
    expect(eventTypes).toContain('thread_processed');
  });

  it('with label protection disabled, custom-labeled threads are collected', async () => {
    const collector = new DomainCollector(defaultConfig({ useLabelProtection: false }));
    const result = await collector.collect();

    // labeled.com should now be in results (custom label no longer protects)
    expect(result['labeled.com']).toBeDefined();

    // But IMPORTANT and STARRED should still be protected
    expect(result['important.com']).toBeUndefined();
    expect(result['starred.com']).toBeUndefined();
  });
});
