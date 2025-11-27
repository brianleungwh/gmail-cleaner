<script>
  import {
    isAuthenticated,
    excludedDomains,
    useLabelProtection,
    protectedLabelIds,
    availableLabels
  } from '../stores/appState';

  let isExpanded = false;
  let domainInput = '';
  let isLoadingLabels = false;
  let labelsLoaded = false;
  let labelsError = '';

  // Sync excluded domains input with store
  $: domainInput = $excludedDomains.join(', ');

  function handleDomainInputChange(event) {
    const value = event.target.value;
    // Parse comma-separated domains
    const domains = value
      .split(',')
      .map(d => d.trim().toLowerCase())
      .filter(d => d.length > 0);
    excludedDomains.set(domains);
  }

  function removeDomain(domain) {
    excludedDomains.update(domains => domains.filter(d => d !== domain));
  }

  async function fetchLabels() {
    if (labelsLoaded || isLoadingLabels) return;

    isLoadingLabels = true;
    labelsError = '';
    try {
      const response = await fetch('/labels');
      if (response.ok) {
        const data = await response.json();
        availableLabels.set(data.labels || []);
        labelsLoaded = true;
      } else {
        const error = await response.json();
        labelsError = error.detail || 'Failed to fetch labels';
      }
    } catch (error) {
      console.error('Failed to fetch labels:', error);
      labelsError = 'Failed to connect to server';
    } finally {
      isLoadingLabels = false;
    }
  }

  function toggleExpanded() {
    isExpanded = !isExpanded;
    // Fetch labels when expanding if authenticated
    if (isExpanded && $isAuthenticated && !labelsLoaded) {
      fetchLabels();
    }
  }

  function handleLabelToggle(labelId) {
    if ($protectedLabelIds === null) {
      // Currently protecting all - switch to only this one
      protectedLabelIds.set([labelId]);
    } else if ($protectedLabelIds.includes(labelId)) {
      // Remove this label
      const updated = $protectedLabelIds.filter(id => id !== labelId);
      protectedLabelIds.set(updated.length > 0 ? updated : null);
    } else {
      // Add this label
      protectedLabelIds.set([...$protectedLabelIds, labelId]);
    }
  }

  function selectAllLabels() {
    protectedLabelIds.set(null);  // null means all
  }

  function selectNoLabels() {
    protectedLabelIds.set([]);  // empty array means none
  }

  $: allLabelsSelected = $protectedLabelIds === null;
  $: noLabelsSelected = $protectedLabelIds !== null && $protectedLabelIds.length === 0;
</script>

<div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
  <!-- Header / Toggle -->
  <button
    on:click={toggleExpanded}
    class="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
  >
    <div class="flex items-center gap-2">
      <span class="text-sm font-medium text-gray-700">Filter Options</span>
      {#if $excludedDomains.length > 0 || !$useLabelProtection || ($protectedLabelIds !== null && $protectedLabelIds.length > 0)}
        <span class="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">
          Active
        </span>
      {/if}
    </div>
    <svg
      class="w-5 h-5 text-gray-400 transform transition-transform duration-200"
      class:rotate-180={isExpanded}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
    </svg>
  </button>

  <!-- Expanded Content -->
  {#if isExpanded}
    <div class="px-6 pb-6 border-t border-gray-100 space-y-6">
      <!-- Excluded Domains -->
      <div class="pt-4">
        <label for="excluded-domains" class="block text-sm font-medium text-gray-700 mb-2">
          Exclude Domains from Scan
        </label>
        <p class="text-xs text-gray-500 mb-2">
          Threads from these domains will not appear in scan results
        </p>
        <input
          id="excluded-domains"
          type="text"
          value={$excludedDomains.join(', ')}
          on:input={handleDomainInputChange}
          placeholder="example.com, newsletter.com"
          class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-400 focus:border-transparent"
        />
        {#if $excludedDomains.length > 0}
          <div class="flex flex-wrap gap-2 mt-2">
            {#each $excludedDomains as domain}
              <span class="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
                {domain}
                <button
                  on:click={() => removeDomain(domain)}
                  class="text-gray-400 hover:text-gray-600"
                  aria-label="Remove {domain}"
                >
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </span>
            {/each}
          </div>
        {/if}
      </div>

      <!-- Label Protection Toggle -->
      <div>
        <div class="flex items-center justify-between">
          <div>
            <span class="block text-sm font-medium text-gray-700">
              Protect Labeled Threads
            </span>
            <p class="text-xs text-gray-500">
              Threads with custom labels won't appear in scan results
            </p>
          </div>
          <button
            on:click={() => useLabelProtection.update(v => !v)}
            class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
            class:bg-slate-600={$useLabelProtection}
            class:bg-gray-200={!$useLabelProtection}
            role="switch"
            aria-checked={$useLabelProtection}
            aria-label="Toggle label protection"
          >
            <span
              class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
              class:translate-x-6={$useLabelProtection}
              class:translate-x-1={!$useLabelProtection}
            ></span>
          </button>
        </div>
      </div>

      <!-- Label Selection (shown when protection is enabled) -->
      {#if $useLabelProtection}
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="block text-sm font-medium text-gray-700">
              Select Labels to Protect
            </span>
            <div class="flex gap-2">
              <button
                on:click={selectAllLabels}
                class="text-xs text-blue-600 hover:text-blue-700"
                class:font-semibold={allLabelsSelected}
              >
                All
              </button>
              <span class="text-gray-300">|</span>
              <button
                on:click={selectNoLabels}
                class="text-xs text-blue-600 hover:text-blue-700"
                class:font-semibold={noLabelsSelected}
              >
                None
              </button>
            </div>
          </div>
          <p class="text-xs text-gray-500 mb-3">
            {#if allLabelsSelected}
              All custom labels will protect threads from being scanned
            {:else if noLabelsSelected}
              No labels will protect threads (only starred/important)
            {:else}
              Only selected labels will protect threads
            {/if}
          </p>

          {#if !$isAuthenticated}
            <p class="text-xs text-gray-400 italic">
              Authenticate to load your Gmail labels
            </p>
          {:else if isLoadingLabels}
            <p class="text-xs text-gray-400">Loading labels...</p>
          {:else if labelsError}
            <p class="text-xs text-red-500">{labelsError}</p>
          {:else if $availableLabels.length === 0}
            <p class="text-xs text-gray-400 italic">No custom labels found</p>
          {:else}
            <div class="flex flex-wrap gap-2 max-h-40 overflow-y-auto p-2 bg-gray-50 rounded-lg">
              {#each $availableLabels as label}
                <button
                  on:click={() => handleLabelToggle(label.id)}
                  class="px-3 py-1 text-xs rounded-full border transition-colors"
                  class:bg-slate-600={allLabelsSelected || ($protectedLabelIds && $protectedLabelIds.includes(label.id))}
                  class:text-white={allLabelsSelected || ($protectedLabelIds && $protectedLabelIds.includes(label.id))}
                  class:border-slate-600={allLabelsSelected || ($protectedLabelIds && $protectedLabelIds.includes(label.id))}
                  class:bg-white={!allLabelsSelected && (!$protectedLabelIds || !$protectedLabelIds.includes(label.id))}
                  class:text-gray-700={!allLabelsSelected && (!$protectedLabelIds || !$protectedLabelIds.includes(label.id))}
                  class:border-gray-300={!allLabelsSelected && (!$protectedLabelIds || !$protectedLabelIds.includes(label.id))}
                >
                  {label.name}
                </button>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>
