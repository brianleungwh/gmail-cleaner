<script>
  import { resultsVisible, resultsData } from '../stores/appState';
</script>

{#if $resultsVisible && $resultsData}
  <div class="bg-white rounded-2xl shadow-xl shadow-gray-200/50 p-8 border border-gray-100/50 hover:shadow-2xl transition-shadow duration-300">
    <h3 class="text-2xl font-bold text-gray-900 mb-6">Cleanup Results</h3>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
      <div class="bg-gradient-to-br from-purple-50 to-blue-50 p-6 rounded-xl border-2 border-purple-200 hover:border-purple-300 transition-all duration-200 hover:shadow-lg">
        <div class="text-3xl font-bold bg-gradient-to-r from-purple-600 to-blue-600 bg-clip-text text-transparent">{$resultsData.threads_processed}</div>
        <div class="text-sm font-semibold text-purple-800 mt-2">Threads Processed</div>
      </div>
      <div class="bg-gradient-to-br from-orange-50 to-red-50 p-6 rounded-xl border-2 border-orange-200 hover:border-orange-300 transition-all duration-200 hover:shadow-lg">
        <div class="text-3xl font-bold bg-gradient-to-r from-orange-600 to-red-600 bg-clip-text text-transparent">{$resultsData.threads_deleted}</div>
        <div class="text-sm font-semibold text-orange-800 mt-2">Threads Deleted</div>
      </div>
      <div class="bg-gradient-to-br from-red-50 to-pink-50 p-6 rounded-xl border-2 border-red-200 hover:border-red-300 transition-all duration-200 hover:shadow-lg">
        <div class="text-3xl font-bold bg-gradient-to-r from-red-600 to-pink-600 bg-clip-text text-transparent">{$resultsData.messages_deleted}</div>
        <div class="text-sm font-semibold text-red-800 mt-2">Messages Deleted</div>
      </div>
      <div class="bg-gradient-to-br from-green-50 to-emerald-50 p-6 rounded-xl border-2 border-green-200 hover:border-green-300 transition-all duration-200 hover:shadow-lg">
        <div class="text-3xl font-bold bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">{$resultsData.messages_kept}</div>
        <div class="text-sm font-semibold text-green-800 mt-2">Messages Kept</div>
      </div>
    </div>
  </div>
{/if}
