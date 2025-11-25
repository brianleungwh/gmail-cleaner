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
  <div class="bg-white rounded-2xl shadow-xl shadow-gray-200/50 p-8 border border-gray-100/50 hover:shadow-2xl transition-shadow duration-300">
    <!-- Header -->
    <div class="mb-8">
      <h3 class="text-2xl font-bold text-gray-900 mb-2">Review Domains</h3>
      <p class="text-gray-600">Select domains to delete. Protected emails (starred, important, or labeled) are excluded.</p>
    </div>

    <!-- Controls Bar -->
    <div class="mb-6 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
      <!-- Search Box -->
      <div class="w-full sm:w-auto sm:flex-1 sm:max-w-md">
        <input
          bind:value={searchQuery}
          type="text"
          placeholder="🔎 Search domains and subjects..."
          class="w-full px-5 py-3 border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-400 focus:border-transparent transition-all shadow-sm"
        >
        <div class="text-xs text-gray-500 mt-2">{searchResultsText}</div>
      </div>

      <!-- Select Controls -->
      <div class="flex gap-3 flex-shrink-0">
        <button
          on:click={selectAll}
          class="bg-gradient-to-r from-gray-500 to-gray-600 hover:from-gray-600 hover:to-gray-700 text-white text-sm font-medium py-2.5 px-5 rounded-lg shadow-md hover:shadow-lg transition-all duration-200 hover:scale-105"
        >
          ✅ Select All
        </button>
        <button
          on:click={deselectAll}
          class="bg-gradient-to-r from-gray-500 to-gray-600 hover:from-gray-600 hover:to-gray-700 text-white text-sm font-medium py-2.5 px-5 rounded-lg shadow-md hover:shadow-lg transition-all duration-200 hover:scale-105"
        >
          ❌ Deselect All
        </button>
      </div>
    </div>

    <!-- Table Header -->
    <div class="bg-gradient-to-r from-purple-50 to-blue-50 border-b-2 border-purple-200 px-6 py-4 rounded-t-xl">
      <div class="flex items-center gap-3">
        <div class="w-5"></div>
        <div class="flex-1 text-sm font-bold text-gray-800">Domain</div>
        <div class="w-24 text-sm font-bold text-gray-800 text-right">Threads</div>
        <div class="w-10"></div>
      </div>
    </div>

    <!-- Domain List -->
    <div class="border-x-2 border-b-2 border-purple-100 rounded-b-xl overflow-hidden">
      {#if filteredDomains.length === 0}
        <div class="p-8 text-center text-gray-500">
          {#if searchQuery.trim()}
            No domains match your search.
          {:else}
            No domains found.
          {/if}
        </div>
      {:else}
        {#each filteredDomains as [domain, info], index (domain)}
          <div class:border-t={index > 0} class="border-gray-200">
            <DomainItem {domain} {info} />
          </div>
        {/each}
      {/if}
    </div>

    <!-- Summary Footer -->
    <div class="mt-6 p-5 bg-gradient-to-r from-purple-50 to-blue-50 border-2 border-purple-200 rounded-xl">
      <div class="flex items-center justify-between">
        <div class="text-sm font-semibold text-purple-900">
          ✨ {$selectedCount} {$selectedCount === 1 ? 'domain' : 'domains'} selected for deletion
        </div>
        {#if $selectedCount > 0}
          <div class="text-xs font-medium text-purple-700">
            Review your selection, then use Preview or Execute below
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}
