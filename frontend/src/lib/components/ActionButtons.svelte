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

<div class="bg-white rounded-2xl shadow-xl shadow-gray-200/50 p-8 border border-gray-100/50 hover:shadow-2xl transition-shadow duration-300">
  <div class="flex flex-col gap-6">
    <!-- Scan Controls -->
    <div class="flex flex-wrap items-center gap-4">
      <button
        on:click={collectDomains}
        disabled={collectDisabled}
        class="bg-gradient-to-r from-purple-500 to-blue-500 hover:from-purple-600 hover:to-blue-600 text-white font-semibold py-3 px-6 rounded-xl shadow-lg shadow-purple-500/30 disabled:bg-gray-300 disabled:cursor-not-allowed disabled:shadow-none transition-all duration-200 hover:scale-105 active:scale-95"
      >
        🔍 {collectBtnText}
      </button>

      <div class="flex items-center gap-3">
        <label for="scan-limit" class="text-sm font-medium text-gray-700">Limit threads:</label>
        <input
          id="scan-limit"
          type="number"
          bind:value={scanLimitInput}
          placeholder="All"
          min="1"
          class="w-28 px-4 py-2 border-2 border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-transparent transition-all"
        />
        <span class="text-xs text-gray-500">(leave empty for all)</span>
      </div>
    </div>

    <!-- Cleanup Controls -->
    <div class="flex flex-wrap gap-4">
      <button
        on:click={previewCleanup}
        disabled={previewDisabled}
        class="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white font-semibold py-3 px-6 rounded-xl shadow-lg shadow-blue-500/30 disabled:bg-gray-300 disabled:cursor-not-allowed disabled:shadow-none transition-all duration-200 hover:scale-105 active:scale-95"
      >
        👁️ Preview Cleanup
      </button>
      <button
        on:click={executeCleanup}
        disabled={cleanupDisabled}
        class="bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 text-white font-semibold py-3 px-6 rounded-xl shadow-lg shadow-orange-500/30 disabled:bg-gray-300 disabled:cursor-not-allowed disabled:shadow-none transition-all duration-200 hover:scale-105 active:scale-95"
      >
        🔥 Execute Cleanup
      </button>
    </div>
  </div>
</div>
