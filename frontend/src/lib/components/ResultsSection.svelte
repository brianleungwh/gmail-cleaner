<script>
  import { resultsVisible, resultsData } from '../stores/appState';
</script>

{#if $resultsVisible && $resultsData}
  <div class="bg-white rounded-lg shadow-md p-6">
    <h3 class="text-lg font-semibold text-gray-800 mb-4">Cleanup Results</h3>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-blue-50 p-4 rounded-lg">
        <div class="text-2xl font-bold text-blue-600">{$resultsData.threads_processed}</div>
        <div class="text-sm text-blue-800">Threads Processed</div>
      </div>
      <div class="bg-red-50 p-4 rounded-lg">
        <div class="text-2xl font-bold text-red-600">{$resultsData.threads_deleted}</div>
        <div class="text-sm text-red-800">Threads Deleted</div>
      </div>
      <div class="bg-red-50 p-4 rounded-lg">
        <div class="text-2xl font-bold text-red-600">{$resultsData.messages_deleted}</div>
        <div class="text-sm text-red-800">Messages Deleted</div>
      </div>
      <div class="bg-green-50 p-4 rounded-lg">
        <div class="text-2xl font-bold text-green-600">{$resultsData.messages_kept}</div>
        <div class="text-sm text-green-800">Messages Kept</div>
      </div>
    </div>
  </div>
{/if}
