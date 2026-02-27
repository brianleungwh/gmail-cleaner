/**
 * Application-wide constants
 */

// Subject line truncation limits for display
export const SUBJECT_TRUNCATE_COLLECTOR = 60;
export const SUBJECT_TRUNCATE_CLEANER = 50;

// How often to yield control to the UI event loop (every N threads)
export const UI_YIELD_INTERVAL = 10;

// Gmail API page size for listing threads
export const THREAD_PAGE_SIZE = 100;

// Max log entries kept in the progress log store
export const MAX_LOG_MESSAGES = 200;
