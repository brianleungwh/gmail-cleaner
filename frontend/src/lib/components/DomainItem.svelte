<script>
  import { selectedDomains } from '../stores/appState';

  export let domain;
  export let info;

  let expanded = false;
  let isSelected = false;

  // Subscribe to selected domains and check if this domain is selected
  $: isSelected = $selectedDomains.has(domain);

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
    expanded = !expanded;
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
          class:rotate-180={expanded}
          class:text-blue-600={expanded}
          aria-label="Toggle sample subjects"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
          </svg>
        </button>
      </div>
    </div>

    <!-- Expanded Sample Subjects -->
    {#if expanded}
      <div class="mt-3 ml-8 pl-4 border-l-2 border-blue-200">
        <div class="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Sample Subjects:</div>
        {#if info.sample_subjects.length === 0}
          <div class="text-sm text-gray-400 italic">No sample subjects available</div>
        {:else}
          <div class="space-y-1">
            {#each info.sample_subjects as subject}
              <div class="text-sm text-gray-700 flex items-start">
                <span class="text-blue-400 mr-2 flex-shrink-0">•</span>
                <span class="break-words">{subject}</span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>
