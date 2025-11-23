<script>
  import { selectedDomains, expandedDomains } from '../stores/appState';

  export let domain;
  export let info;

  let isSelected = false;
  let isExpanded = false;

  // Subscribe to selected domains and check if this domain is selected
  $: isSelected = $selectedDomains.has(domain);

  // Subscribe to expanded domains
  $: isExpanded = $expandedDomains.has(domain);

  // Auto-expand when domain is selected
  $: if (isSelected && !isExpanded) {
    expandedDomains.update(set => {
      const newSet = new Set(set);
      newSet.add(domain);
      return newSet;
    });
  }

  function toggleSelection() {
    selectedDomains.update(set => {
      const newSet = new Set(set);
      if (newSet.has(domain)) {
        newSet.delete(domain);
      } else {
        newSet.add(domain);
      }
      return newSet;
    });
  }

  function toggleExpand() {
    expandedDomains.update(set => {
      const newSet = new Set(set);
      if (newSet.has(domain)) {
        newSet.delete(domain);
      } else {
        newSet.add(domain);
      }
      return newSet;
    });
  }
</script>

<div class="hover:bg-gray-50 transition-colors">
  <div class="px-4 py-3">
    <div class="flex items-center gap-3">
      <!-- Checkbox -->
      <div class="w-5 flex-shrink-0">
        <input
          type="checkbox"
          class="h-4 w-4 text-blue-600 border-gray-300 rounded cursor-pointer focus:ring-2 focus:ring-blue-500"
          checked={isSelected}
          on:change={toggleSelection}
        >
      </div>

      <!-- Domain Name -->
      <div class="flex-1 min-w-0">
        <div class="font-medium text-gray-900 truncate">{domain}</div>
      </div>

      <!-- Thread Count -->
      <div class="w-24 flex-shrink-0 text-right">
        <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
          {info.count}
        </span>
      </div>

      <!-- Expand Button -->
      <div class="w-10 flex-shrink-0 flex justify-center">
        <button
          on:click={toggleExpand}
          class="text-gray-400 hover:text-blue-600 transition-all p-1 rounded hover:bg-blue-50"
          class:rotate-180={isExpanded}
          class:text-blue-600={isExpanded}
          aria-label="Toggle threads"
        >
          <svg class="w-5 h-5 transform transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
          </svg>
        </button>
      </div>
    </div>

    <!-- Expanded Thread List -->
    {#if isExpanded}
      <div class="mt-3 ml-8 pl-4 border-l-2 border-blue-200 animate-slideDown">
        <div class="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
          Threads ({info.threads?.length || 0}):
        </div>
        {#if !info.threads || info.threads.length === 0}
          <div class="text-sm text-gray-400 italic">No threads available</div>
        {:else}
          <div class="space-y-2 max-h-96 overflow-y-auto pr-2">
            {#each info.threads as thread}
              <div class="text-sm bg-white rounded border border-gray-200 p-2 hover:border-blue-300 transition-colors">
                <div class="flex items-start gap-2">
                  <span class="text-blue-400 mt-1 flex-shrink-0">•</span>
                  <div class="flex-1 min-w-0">
                    <div class="font-medium text-gray-900 break-words" title={thread.subject}>
                      {thread.subject}
                    </div>
                    <div class="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
                      <span class="truncate" title={thread.sender}>{thread.sender}</span>
                      <span class="flex-shrink-0">
                        ({thread.message_count} {thread.message_count === 1 ? 'message' : 'messages'})
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  @keyframes slideDown {
    from {
      opacity: 0;
      max-height: 0;
    }
    to {
      opacity: 1;
      max-height: 500px;
    }
  }

  .animate-slideDown {
    animation: slideDown 0.2s ease-out;
  }
</style>
