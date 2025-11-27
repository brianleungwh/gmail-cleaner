<script>
  import { resultsVisible, resultsData } from '../stores/appState';
</script>

{#if $resultsVisible && $resultsData}
  <div class="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
    <h3 class="text-lg font-semibold text-gray-900 mb-4">Cleanup Results</h3>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
        <div class="text-2xl font-bold text-gray-900">{$resultsData.threads_processed}</div>
        <div class="text-xs text-gray-500 mt-1">Threads Processed</div>
      </div>
      <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
        <div class="text-2xl font-bold text-red-600">{$resultsData.threads_deleted}</div>
        <div class="text-xs text-gray-500 mt-1">Threads Deleted</div>
      </div>
      <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
        <div class="text-2xl font-bold text-red-600">{$resultsData.messages_deleted}</div>
        <div class="text-xs text-gray-500 mt-1">Messages Deleted</div>
      </div>
      <div class="bg-gray-50 p-4 rounded-lg border border-gray-200">
        <div class="text-2xl font-bold text-green-600">{$resultsData.messages_kept}</div>
        <div class="text-xs text-gray-500 mt-1">Messages Kept</div>
      </div>
    </div>
  </div>
{/if}
