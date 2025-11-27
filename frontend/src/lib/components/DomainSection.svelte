<script>
  import { domainsVisible, domains, selectedDomains, selectedCount } from '../stores/appState';
  import DomainItem from './DomainItem.svelte';

  let searchQuery = '';
  let filteredDomains = [];

  function updateFilteredDomains() {
    if (!searchQuery.trim()) {
      filteredDomains = Object.entries($domains);
    } else {
      const query = searchQuery.toLowerCase();

      filteredDomains = Object.entries($domains).filter(([domain, info]) => {
        // Search in domain name
        if (domain.toLowerCase().includes(query)) {
          return true;
        }

        // Search in thread subjects
        const threads = info.threads || [];
        return threads.some(thread =>
          thread.subject.toLowerCase().includes(query)
        );
      });
    }
  }

  // Update filtered domains when domains or search query changes
  $: {
    $domains;  // React to domains changes
    searchQuery;  // React to search query changes
    updateFilteredDomains();
  }

  function selectAll() {
    // Select all visible domains
    selectedDomains.update(set => {
      const newSet = new Set(set);
      filteredDomains.forEach(([domain]) => newSet.add(domain));
      return newSet;
    });
  }

  function deselectAll() {
    // Deselect all visible domains
    selectedDomains.update(set => {
      const newSet = new Set(set);
      filteredDomains.forEach(([domain]) => newSet.delete(domain));
      return newSet;
    });
  }

  $: searchResultsText = searchQuery.trim()
    ? `Showing ${filteredDomains.length} of ${Object.keys($domains).length} domains`
    : 'Showing all domains';
</script>

{#if $domainsVisible}
  <div class="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
    <!-- Header -->
    <div class="mb-6">
      <h3 class="text-lg font-semibold text-gray-900 mb-1">Review Domains</h3>
      <p class="text-sm text-gray-500">Select domains to delete. Protected emails (starred, important, or labeled) are excluded.</p>
    </div>

    <!-- Controls Bar -->
    <div class="mb-4 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
      <!-- Search Box -->
      <div class="w-full sm:w-auto sm:flex-1 sm:max-w-md">
        <input
          bind:value={searchQuery}
          type="text"
          placeholder="Search domains and subjects..."
          class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-transparent text-sm"
        >
        <div class="text-xs text-gray-500 mt-1">{searchResultsText}</div>
      </div>

      <!-- Select Controls -->
      <div class="flex gap-2 flex-shrink-0">
        <button
          on:click={selectAll}
          class="bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium py-2 px-4 rounded-lg transition-colors"
        >
          Select All
        </button>
        <button
          on:click={deselectAll}
          class="bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium py-2 px-4 rounded-lg transition-colors"
        >
          Deselect All
        </button>
      </div>
    </div>

    <!-- Table Header -->
    <div class="bg-gray-50 border-b border-gray-200 px-4 py-3 rounded-t-lg">
      <div class="flex items-center gap-3">
        <div class="w-5"></div>
        <div class="flex-1 text-xs font-semibold text-gray-600 uppercase tracking-wide">Domain</div>
        <div class="w-20 text-xs font-semibold text-gray-600 uppercase tracking-wide text-right">Threads</div>
        <div class="w-8"></div>
      </div>
    </div>

    <!-- Domain List -->
    <div class="border border-t-0 border-gray-200 rounded-b-lg overflow-hidden">
      {#if filteredDomains.length === 0}
        <div class="p-6 text-center text-gray-500 text-sm">
          {#if searchQuery.trim()}
            No domains match your search.
          {:else}
            No domains found.
          {/if}
        </div>
      {:else}
        {#each filteredDomains as [domain, info], index (domain)}
          <div class:border-t={index > 0} class="border-gray-100">
            <DomainItem {domain} {info} />
          </div>
        {/each}
      {/if}
    </div>

    <!-- Summary Footer -->
    <div class="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
      <div class="flex items-center justify-between">
        <div class="text-sm font-medium text-gray-700">
          {$selectedCount} {$selectedCount === 1 ? 'domain' : 'domains'} selected for deletion
        </div>
        {#if $selectedCount > 0}
          <div class="text-xs text-gray-500">
            Review your selection, then use Preview or Execute above
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}
