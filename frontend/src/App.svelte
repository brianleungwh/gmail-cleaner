<script>
  import { onMount } from 'svelte';
  import { websocket } from './lib/stores/websocket';
  import {
    domains,
    totalThreads,
    progressPercent,
    progressText,
    progressIndeterminate,
    addLog,
    hideProgress,
    showDomains,
    showResults
  } from './lib/stores/appState';

  import Header from './lib/components/Header.svelte';
  import AuthSection from './lib/components/AuthSection.svelte';
  import ActionButtons from './lib/components/ActionButtons.svelte';
  import ProgressSection from './lib/components/ProgressSection.svelte';
  import DomainSection from './lib/components/DomainSection.svelte';
  import ResultsSection from './lib/components/ResultsSection.svelte';

  // Handle WebSocket messages
  let unsubscribe;

  onMount(() => {
    // Connect to WebSocket
    websocket.connect();

    // Subscribe to WebSocket messages
    unsubscribe = websocket.subscribe((state) => {
      if (state.messages.length > 0) {
        const message = state.messages[state.messages.length - 1];
        handleWebSocketMessage(message);
      }
    });

    return () => {
      if (unsubscribe) unsubscribe();
    };
  });

  function handleWebSocketMessage(message) {
    const { type, data } = message;

    switch (type) {
      case 'authenticated':
        handleAuthenticated(data);
        break;
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
        console.warn('Unknown WebSocket message type:', type, data);
    }
  }

  function handleAuthenticated(data) {
    addLog(data.message || 'Successfully authenticated with Gmail', 'success');
  }

  function handleCollectionStarted(data) {
    const { total_threads } = data;
    $totalThreads = total_threads || 0;

    if ($totalThreads > 0) {
      addLog(`Starting domain collection... (${$totalThreads} total threads)`, 'info');
      $progressText = `Scanning ${$totalThreads} inbox threads...`;
    } else {
      addLog('Starting domain collection...', 'info');
      $progressText = 'Scanning inbox threads...';
    }

    // Reset progress bar
    $progressIndeterminate = false;
    $progressPercent = 0;
  }

  function handleThreadProcessed(data) {
    const { thread_id, domain, subject, processed_threads, total_threads, unique_domains } = data;
    addLog(`Thread ${thread_id}: ${domain} - "${subject}"`, 'info');

    if (total_threads > 0) {
      // We know the total, show accurate progress
      const percentage = Math.round((processed_threads / total_threads) * 100);
      $progressIndeterminate = false;
      $progressPercent = percentage;
      $progressText = `Processed ${processed_threads}/${total_threads} threads (${percentage}%), found ${unique_domains} unique domains`;
    } else {
      // Fallback to indeterminate if we don't know total
      $progressText = `Processed ${processed_threads} threads, found ${unique_domains} unique domains`;
      if (!$progressIndeterminate) {
        $progressIndeterminate = true;
        $progressPercent = 100;
      }
    }
  }

  async function handleCollectionCompleted(data) {
    const { processed_threads, total_threads, unique_domains } = data;
    addLog(`Collection complete: ${processed_threads} threads processed, ${unique_domains} domains found`, 'success');

    // Remove indeterminate animation and show complete
    $progressIndeterminate = false;
    $progressPercent = 100;
    $progressText = 'Collection complete!';

    // Load domains from server
    await loadDomains();

    setTimeout(() => {
      hideProgress();
      showDomains();
    }, 1000);
  }

  function handleCleanupStarted(data) {
    const { domains_count, dry_run } = data;
    const mode = dry_run ? 'preview' : 'cleanup';
    addLog(`Starting ${mode} for ${domains_count} domains...`, 'info');
    $progressText = `${dry_run ? 'Previewing' : 'Cleaning'} selected domains...`;
  }

  function handleThreadAnalyzed(data) {
    const { thread_id, subject, sender } = data;
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
    const { threads_processed, threads_deleted, messages_deleted, messages_kept } = data;
    addLog(`Cleanup complete: ${threads_deleted}/${threads_processed} threads deleted`, 'success');

    hideProgress();
    showResults(data);
  }

  function handleError(data) {
    addLog(`Error: ${data.message}`, 'error');
    hideProgress();
  }

  async function loadDomains() {
    try {
      const response = await fetch('/domains');
      const result = await response.json();

      if (response.ok) {
        $domains = result.domains;
      }
    } catch (error) {
      addLog(`Failed to load domains: ${error.message}`, 'error');
    }
  }
</script>

<div class="min-h-screen bg-gray-100">
  <div class="container mx-auto px-4 py-8 max-w-5xl">
    <Header />
    <div class="space-y-4">
      <AuthSection />
      <ActionButtons />
      <ProgressSection />
      <DomainSection />
      <ResultsSection />
    </div>
  </div>
</div>
