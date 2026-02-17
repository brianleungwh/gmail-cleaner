<script>
  import { excludedDomains } from '../stores/filterStore.js';

  function handleDomainInputChange(event) {
    const value = event.target.value;
    const domains = value
      .split(',')
      .map(d => d.trim().toLowerCase())
      .filter(d => d.length > 0);
    excludedDomains.set(domains);
  }

  function removeDomain(domain) {
    excludedDomains.update(domains => domains.filter(d => d !== domain));
  }
</script>

<div>
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
