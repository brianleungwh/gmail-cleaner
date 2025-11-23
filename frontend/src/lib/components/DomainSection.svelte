<script>
  import { domainsVisible, domains, selectedDomains, selectedCount } from '../stores/appState';
  import DomainItem from './DomainItem.svelte';
  import Fuse from 'fuse.js';

  let searchQuery = '';
  let fuse = null;
  let filteredDomains = [];

  // Initialize fuzzy search when domains change
  $: if (Object.keys($domains).length > 0) {
    const searchData = Object.entries($domains).map(([domain, info]) => ({
      domain,
      count: info.count,
      // Search through all thread subjects, not just samples
      subjects: info.threads?.map(t => t.subject).join(' ') || ''
    }));

    fuse = new Fuse(searchData, {
      keys: ['domain', 'subjects'],
      threshold: 0.3,
      includeScore: true
    });

    // Update filtered domains when search query or domains change
    updateFilteredDomains();
  }

  function updateFilteredDomains() {
    if (!searchQuery.trim()) {
      filteredDomains = Object.entries($domains);
    } else if (fuse) {
      const results = fuse.search(searchQuery);
      filteredDomains = results.map(result => [result.item.domain, $domains[result.item.domain]]);
    }
  }

  // Update filtered domains when search query changes
  $: {
    searchQuery;
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
  <div class="bg-white rounded-lg shadow-md p-6 mb-6">
    <!-- Header -->
    <div class="mb-6">
      <h3 class="text-xl font-semibold text-gray-800 mb-2">Review Domains</h3>
      <p class="text-sm text-gray-600">Select domains to delete. Protected emails (starred, important, or labeled) are excluded.</p>
    </div>

    <!-- Controls Bar -->
    <div class="mb-6 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
      <!-- Search Box -->
      <div class="w-full sm:w-auto sm:flex-1 sm:max-w-md">
        <input
          bind:value={searchQuery}
          type="text"
          placeholder="Search domains and subjects..."
          class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        >
        <div class="text-xs text-gray-500 mt-1">{searchResultsText}</div>
      </div>

      <!-- Select Controls -->
      <div class="flex gap-2 flex-shrink-0">
        <button
          on:click={selectAll}
          class="bg-gray-500 hover:bg-gray-600 text-white text-sm font-medium py-2 px-4 rounded transition-colors"
        >
          Select All
        </button>
        <button
          on:click={deselectAll}
          class="bg-gray-500 hover:bg-gray-600 text-white text-sm font-medium py-2 px-4 rounded transition-colors"
        >
          Deselect All
        </button>
      </div>
    </div>

    <!-- Table Header -->
    <div class="bg-gray-50 border-b-2 border-gray-200 px-4 py-3 rounded-t-lg">
      <div class="flex items-center gap-3">
        <div class="w-5"></div>
        <div class="flex-1 text-sm font-semibold text-gray-700">Domain</div>
        <div class="w-24 text-sm font-semibold text-gray-700 text-right">Threads</div>
        <div class="w-10"></div>
      </div>
    </div>

    <!-- Domain List -->
    <div class="border-x border-b border-gray-200 rounded-b-lg">
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
    <div class="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
      <div class="flex items-center justify-between">
        <div class="text-sm font-medium text-blue-900">
          {$selectedCount} {$selectedCount === 1 ? 'domain' : 'domains'} selected for deletion
        </div>
        {#if $selectedCount > 0}
          <div class="text-xs text-blue-700">
            Review your selection, then use Preview or Execute below
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}
