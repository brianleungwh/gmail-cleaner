<script>
  import {
    isAuthenticated,
    isCollecting,
    isCleaning,
    hasCollectedDomains,
    hasSelection,
    selectedDomains,
    domains,
    excludedDomains,
    useLabelProtection,
    protectedLabelIds,
    addLog,
    showProgress,
    hideProgress,
    showDomains,
  } from '../stores/appState';

  import { DomainCollector } from '../gmail/collector.js';
  import { DomainCleaner } from '../gmail/cleaner.js';
  import { createProgressHandler } from '../gmail/progressHandler.js';

  let collectBtnText = 'Scan Inbox';
  let scanLimitInput = '';

  // Store the collector's thread data for cleanup to reference
  let collectorThreadsById = {};
  let collectorThreadsByDomain = {};

  async function collectDomains() {
    if ($isCollecting) return;

    $isCollecting = true;
    showProgress();
    collectBtnText = 'Scanning...';

    const limit = scanLimitInput ? parseInt(scanLimitInput, 10) : null;

    const config = {
      limit,
      excludedDomains: new Set($excludedDomains),
      useLabelProtection: $useLabelProtection,
      protectedLabelIds: $protectedLabelIds ? new Set($protectedLabelIds) : null,
    };

    const progressHandler = createProgressHandler();
    const collector = new DomainCollector(config, progressHandler);

    try {
      const result = await collector.collect();

      // Store thread maps for cleanup
      collectorThreadsById = collector.threadsById;
      collectorThreadsByDomain = collector.threadsByDomain;

      // Sort by count descending and set domains
      const sorted = Object.fromEntries(
        Object.entries(result).sort(([, a], [, b]) => b.count - a.count)
      );
      $domains = Object.fromEntries(
        Object.entries(sorted).map(([domain, info]) => [domain, {
          count: info.count,
          threads: info.threads,
        }])
      );

      setTimeout(() => {
        hideProgress();
        showDomains();
      }, 1000);
    } catch (error) {
      console.error('Collection error:', error);
      addLog(`Collection failed: ${error.message}`, 'error');
      hideProgress();
    } finally {
      $isCollecting = false;
      collectBtnText = 'Scan Inbox';
    }
  }

  async function performCleanup(dryRun) {
    if ($isCleaning) return;

    if (!dryRun) {
      if (!confirm('Are you sure you want to delete the selected domains? This action cannot be undone.')) {
        return;
      }
    }

    $isCleaning = true;
    showProgress();

    // Build the thread list from stored collector data
    const selectedDomainsArray = Array.from($selectedDomains);
    const threads = [];
    for (const domain of selectedDomainsArray) {
      const threadIds = collectorThreadsByDomain[domain] || [];
      for (const threadId of threadIds) {
        const metadata = collectorThreadsById[threadId];
        if (metadata) {
          threads.push({
            thread_id: threadId,
            domain: metadata.domain,
            subject: metadata.subject,
            sender: metadata.sender,
            message_count: metadata.messageCount,
          });
        }
      }
    }

    const config = { dryRun, limit: null };
    const progressHandler = createProgressHandler();
    const cleaner = new DomainCleaner(config, progressHandler);

    try {
      await cleaner.cleanup(threads);
    } catch (error) {
      addLog(`Cleanup failed: ${error.message}`, 'error');
      hideProgress();
    } finally {
      $isCleaning = false;
    }
  }

  function previewCleanup() {
    performCleanup(true);
  }

  function executeCleanup() {
    performCleanup(false);
  }

  $: collectDisabled = !$isAuthenticated || $isCollecting;
  $: previewDisabled = !$hasCollectedDomains || !$hasSelection || $isCleaning;
  $: cleanupDisabled = !$hasCollectedDomains || !$hasSelection || $isCleaning;
</script>

<div class="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
  <div class="flex flex-col gap-4">
    <!-- Scan Controls -->
    <div class="flex flex-wrap items-center gap-4">
      <button
        on:click={collectDomains}
        disabled={collectDisabled}
        class="bg-slate-800 hover:bg-slate-700 text-white font-medium py-2 px-5 rounded-lg disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
      >
        {collectBtnText}
      </button>

      <div class="flex items-center gap-2">
        <label for="scan-limit" class="text-sm text-gray-600">Limit:</label>
        <input
          id="scan-limit"
          type="number"
          bind:value={scanLimitInput}
          placeholder="All"
          min="1"
          class="w-24 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-transparent text-sm"
        />
      </div>
    </div>

    <!-- Cleanup Controls -->
    <div class="flex flex-wrap gap-3">
      <button
        on:click={previewCleanup}
        disabled={previewDisabled}
        class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-5 rounded-lg disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
      >
        Preview Cleanup
      </button>
      <button
        on:click={executeCleanup}
        disabled={cleanupDisabled}
        class="bg-red-600 hover:bg-red-700 text-white font-medium py-2 px-5 rounded-lg disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
      >
        Execute Cleanup
      </button>
    </div>
  </div>
</div>
