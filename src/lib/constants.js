/**
 * Application-wide constants
 */

// Subject line truncation limits for display
export const SUBJECT_TRUNCATE_COLLECTOR = 60;
export const SUBJECT_TRUNCATE_CLEANER = 50;

// How often the UI polls the worker's progress object (ms)
export const PROGRESS_POLL_INTERVAL_MS = 200;

// Log a milestone summary every N threads during collection
export const MILESTONE_LOG_INTERVAL = 100;

// Yield to the macrotask queue every N threads so setInterval (poller) can fire
export const MACROTASK_YIELD_INTERVAL = 50;

// Gmail API page size for listing threads
export const THREAD_PAGE_SIZE = 100;

// Max log entries kept in the progress log store
export const MAX_LOG_MESSAGES = 50;
