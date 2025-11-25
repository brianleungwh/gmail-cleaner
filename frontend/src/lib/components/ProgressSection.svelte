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
  <div class="bg-white rounded-2xl shadow-xl shadow-gray-200/50 p-8 border border-gray-100/50 hover:shadow-2xl transition-shadow duration-300">
    <h3 class="text-2xl font-bold text-gray-900 mb-6">Progress</h3>

    <!-- Progress Bar -->
    <div class="bg-gradient-to-r from-purple-100 to-blue-100 rounded-full h-3 mb-4 shadow-inner">
      <div
        class="h-3 rounded-full transition-all duration-300 shadow-md"
        class:bg-gradient-to-r={!$progressIndeterminate}
        class:from-purple-500={!$progressIndeterminate}
        class:to-blue-500={!$progressIndeterminate}
        class:indeterminate={$progressIndeterminate}
        style="width: {$progressPercent}%"
      ></div>
    </div>

    <div class="text-sm font-medium text-gray-700 mb-6">{$progressText}</div>

    <!-- Live Log -->
    <div class="border-2 border-purple-100 rounded-xl overflow-hidden">
      <div class="bg-gradient-to-r from-purple-50 to-blue-50 px-4 py-3 border-b-2 border-purple-200">
        <h4 class="text-sm font-bold text-gray-800">Live Activity Log</h4>
      </div>
      <div bind:this={logBoxElement} class="bg-gray-50 p-4 h-64 overflow-y-auto">
        <div class="space-y-1">
          {#if $logs.length === 0}
            <div class="text-sm text-gray-500 italic">Log messages will appear here...</div>
          {:else}
            {#each $logs as log}
              <div class="text-sm {getLogColor(log.type)} font-mono">
                <span class="text-gray-400">[{log.timestamp}]</span> {log.message}
              </div>
            {/each}
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}
