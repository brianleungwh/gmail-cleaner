<script>
  import { progressVisible, progressPercent, progressText, progressIndeterminate, logs } from '../stores/appState';
  import { onMount, afterUpdate } from 'svelte';

  let logBoxElement;

  // Auto-scroll log box to bottom when new logs are added
  afterUpdate(() => {
    if (logBoxElement) {
      logBoxElement.scrollTop = logBoxElement.scrollHeight;
    }
  });

  function getLogColor(type) {
    const colors = {
      info: 'text-blue-600',
      success: 'text-green-600',
      warning: 'text-yellow-600',
      error: 'text-red-600'
    };
    return colors[type] || 'text-gray-600';
  }
</script>

{#if $progressVisible}
  <div class="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
    <h3 class="text-lg font-semibold text-gray-900 mb-4">Progress</h3>

    <!-- Progress Bar -->
    <div class="bg-gray-200 rounded-full h-2 mb-3">
      <div
        class="h-2 rounded-full transition-all duration-300 bg-slate-600"
        class:indeterminate={$progressIndeterminate}
        style="width: {$progressPercent}%"
      ></div>
    </div>

    <div class="text-sm text-gray-600 mb-4">{$progressText}</div>

    <!-- Live Log -->
    <div class="border border-gray-200 rounded-lg overflow-hidden">
      <div class="bg-gray-50 px-4 py-2 border-b border-gray-200">
        <h4 class="text-xs font-semibold text-gray-600 uppercase tracking-wide">Activity Log</h4>
      </div>
      <div bind:this={logBoxElement} class="bg-white p-3 h-48 overflow-y-auto">
        <div class="space-y-1">
          {#if $logs.length === 0}
            <div class="text-sm text-gray-400">Log messages will appear here...</div>
          {:else}
            {#each $logs as log}
              <div class="text-xs {getLogColor(log.type)} font-mono">
                <span class="text-gray-400">[{log.timestamp}]</span> {log.message}
              </div>
            {/each}
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}
