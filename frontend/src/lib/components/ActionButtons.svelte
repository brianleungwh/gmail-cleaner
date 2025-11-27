<script>
  import {
    isAuthenticated,
    isCollecting,
    isCleaning,
    hasCollectedDomains,
    hasSelection,
    selectedDomains,
    addLog,
    showProgress,
    hideProgress,
    showDomains
  } from '../stores/appState';

  let collectBtnText = 'Scan Inbox';
  let scanLimit = null;
  let scanLimitInput = '';

  async function collectDomains() {
    if ($isCollecting) return;

    $isCollecting = true;
    showProgress();
    collectBtnText = 'Scanning...';

    // Parse limit from input
    const limit = scanLimitInput ? parseInt(scanLimitInput, 10) : null;

    try {
      const response = await fetch('/collect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit })
      });

      if (!response.ok) {
        const result = await response.json();
        throw new Error(result.detail || 'Collection failed');
      }

      const result = await response.json();

      // Data will be handled via WebSocket messages
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

    const selectedDomainsArray = Array.from($selectedDomains);

    try {
      const response = await fetch('/cleanup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          domains: selectedDomainsArray,
          dry_run: dryRun,
          limit: null
        })
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || 'Cleanup failed');
      }

      // Results will be handled via WebSocket messages
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
