/**
 * Progress Handler - Creates callbacks that update Svelte stores
 *
 * Extracted from App.svelte's WebSocket message handlers.
 */

import {
  totalThreads,
  progressPercent,
  progressText,
  progressIndeterminate,
  addLog,
  hideProgress,
  showResults,
} from '../stores/appState';

/**
 * Creates a progress callback function for use with DomainCollector and DomainCleaner.
 * The returned function updates Svelte stores directly based on event type.
 */
export function createProgressHandler() {
  return async function handleProgress(type, data) {
    switch (type) {
      case 'collection_started':
        handleCollectionStarted(data);
        break;
      case 'thread_processed':
        handleThreadProcessed(data);
        break;
      case 'collection_completed':
        handleCollectionCompleted(data);
        break;
      case 'cleanup_started':
        handleCleanupStarted(data);
        break;
      case 'thread_analyzed':
        handleThreadAnalyzed(data);
        break;
      case 'would_delete':
        handleWouldDelete(data);
        break;
      case 'deleted':
        handleDeleted(data);
        break;
      case 'cleanup_completed':
        handleCleanupCompleted(data);
        break;
      case 'error':
        handleError(data);
        break;
      default:
        console.warn('Unknown progress event type:', type, data);
    }
  };
}

function handleCollectionStarted(data) {
  const total = data.total_threads || 0;
  totalThreads.set(total);

  if (total > 0) {
    addLog(`Starting domain collection... (${total} total threads)`, 'info');
    progressText.set(`Scanning ${total} inbox threads...`);
  } else {
    addLog('Starting domain collection...', 'info');
    progressText.set('Scanning inbox threads...');
  }

  progressIndeterminate.set(false);
  progressPercent.set(0);
}

function handleThreadProcessed(data) {
  const { thread_id, domain, subject, processed_threads, total_threads, unique_domains } = data;
  addLog(`Thread ${thread_id}: ${domain} - "${subject}"`, 'info');

  if (total_threads > 0) {
    const percentage = Math.round((processed_threads / total_threads) * 100);
    progressIndeterminate.set(false);
    progressPercent.set(percentage);
    progressText.set(`Processed ${processed_threads}/${total_threads} threads (${percentage}%), found ${unique_domains} unique domains`);
  } else {
    progressText.set(`Processed ${processed_threads} threads, found ${unique_domains} unique domains`);
    // Use get() to check current value without subscribing
    progressIndeterminate.set(true);
    progressPercent.set(100);
  }
}

function handleCollectionCompleted(data) {
  const { processed_threads, unique_domains } = data;
  addLog(`Collection complete: ${processed_threads} threads processed, ${unique_domains} domains found`, 'success');

  progressIndeterminate.set(false);
  progressPercent.set(100);
  progressText.set('Collection complete!');
}

function handleCleanupStarted(data) {
  const { threads_to_process, dry_run } = data;
  const mode = dry_run ? 'preview' : 'cleanup';
  addLog(`Starting ${mode} for ${threads_to_process} threads...`, 'info');
  progressText.set(`${dry_run ? 'Previewing' : 'Cleaning'} selected domains...`);
}

function handleThreadAnalyzed(data) {
  const { subject, sender } = data;
  addLog(`Analyzing: ${sender} - "${subject}"`, 'info');
}

function handleWouldDelete(data) {
  const { subject, sender, message_count } = data;
  addLog(`WOULD DELETE: ${sender} - "${subject}" (${message_count} msgs)`, 'warning');
}

function handleDeleted(data) {
  const { subject, sender, message_count } = data;
  addLog(`DELETED: ${sender} - "${subject}" (${message_count} msgs)`, 'success');
}

function handleCleanupCompleted(data) {
  const { threads_processed, threads_deleted } = data;
  addLog(`Cleanup complete: ${threads_deleted}/${threads_processed} threads deleted`, 'success');

  hideProgress();
  showResults(data);
}

function handleError(data) {
  addLog(`Error: ${data.message}`, 'error');
  hideProgress();
}
