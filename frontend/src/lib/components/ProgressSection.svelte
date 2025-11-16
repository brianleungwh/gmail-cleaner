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
  <div class="bg-white rounded-lg shadow-md p-6 mb-6">
    <h3 class="text-lg font-semibold text-gray-800 mb-4">Progress</h3>
    <div class="bg-gray-200 rounded-full h-2 mb-4">
      <div
        class="h-2 rounded-full transition-all duration-300"
        class:bg-blue-500={!$progressIndeterminate}
        class:indeterminate={$progressIndeterminate}
        style="width: {$progressPercent}%"
      ></div>
    </div>
    <div class="text-sm text-gray-600 mb-4">{$progressText}</div>

    <!-- Live Log -->
    <div bind:this={logBoxElement} class="bg-gray-100 rounded p-4 h-64 overflow-y-auto">
      <div class="space-y-1">
        {#if $logs.length === 0}
          <div class="text-sm text-gray-500">Log messages will appear here...</div>
        {:else}
          {#each $logs as log}
            <div class="text-sm {getLogColor(log.type)}">
              <span class="text-gray-400">[{log.timestamp}]</span> {log.message}
            </div>
          {/each}
        {/if}
      </div>
    </div>
  </div>
{/if}
