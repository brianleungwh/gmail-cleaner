/**
 * Progress Poller - Reads worker.progress on a timer and writes to Svelte stores
 */

import { progressPercent, progressText, progressIndeterminate } from '../stores/progressStore.js';
import { PROGRESS_POLL_INTERVAL_MS } from '../constants.js';

let intervalId = null;

/**
 * Start polling a worker's .progress object and writing to Svelte stores.
 * @param {object} worker - A DomainCollector or DomainCleaner instance with a .progress property
 * @param {'collection' | 'cleanup'} mode
 */
export function startProgressPolling(worker, mode) {
  stopProgressPolling();

  intervalId = setInterval(() => {
    const p = worker.progress;
    if (!p || p.status === 'idle') return;

    if (mode === 'collection') {
      pollCollection(p);
    } else if (mode === 'cleanup') {
      pollCleanup(p);
    }
  }, PROGRESS_POLL_INTERVAL_MS);
}

/**
 * Stop the progress polling interval.
 */
export function stopProgressPolling() {
  if (intervalId !== null) {
    clearInterval(intervalId);
    intervalId = null;
  }
}

function pollCollection(p) {
  const { matchedThreads, threadsExamined, totalInboxThreads, limit, uniqueDomains } = p;

  if (limit) {
    // User set a cap — progress = threads examined toward the cap
    const percentage = Math.min(Math.round((threadsExamined / limit) * 100), 99);
    progressIndeterminate.set(false);
    progressPercent.set(percentage);
    progressText.set(
      `Scanned ${threadsExamined.toLocaleString()}/${limit.toLocaleString()} threads, found ${matchedThreads.toLocaleString()} in ${uniqueDomains.toLocaleString()} domains`
    );
  } else if (totalInboxThreads > 0) {
    // No limit — progress = how far through the inbox we've scanned
    const percentage = Math.min(Math.round((threadsExamined / totalInboxThreads) * 100), 99);
    progressIndeterminate.set(false);
    progressPercent.set(percentage);
    progressText.set(
      `Scanned ${threadsExamined.toLocaleString()}/${totalInboxThreads.toLocaleString()} threads, found ${matchedThreads.toLocaleString()} in ${uniqueDomains.toLocaleString()} domains`
    );
  } else {
    progressIndeterminate.set(true);
    progressPercent.set(100);
    progressText.set(
      `Scanned ${threadsExamined.toLocaleString()} threads, found ${matchedThreads.toLocaleString()} in ${uniqueDomains.toLocaleString()} domains`
    );
  }
}

function pollCleanup(p) {
  const { totalProcessed, totalToProcess, threadsDeleted, dryRun } = p;
  const action = dryRun ? 'Previewing' : 'Cleaning';

  if (totalToProcess > 0) {
    const percentage = Math.round((totalProcessed / totalToProcess) * 100);
    progressIndeterminate.set(false);
    progressPercent.set(percentage);
    progressText.set(
      `${action}: ${totalProcessed}/${totalToProcess} threads (${threadsDeleted} deleted)`
    );
  } else {
    progressText.set(`${action}...`);
  }
}
