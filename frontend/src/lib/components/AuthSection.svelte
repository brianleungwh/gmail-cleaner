<script>
  import { isAuthenticated, credentialsPath, uploadedCredentials, addLog } from '../stores/appState';

  let showUploadSection = true;
  let authBtnDisabled = true;
  let authBtnText = 'Connect Gmail';
  let dropZoneHighlight = false;
  let uploadSuccess = false;
  let fileInputElement;

  async function checkAuthStatus() {
    // Check URL parameters for OAuth callback
    const urlParams = new URLSearchParams(window.location.search);

    if (urlParams.has('auth_success')) {
      $isAuthenticated = true;
      addLog('Successfully authenticated with Gmail!', 'success');
      showUploadSection = false;
      await refreshAuthStatus();
      // Clear URL parameters
      window.history.replaceState({}, document.title, window.location.pathname);
      return;
    } else if (urlParams.has('auth_error')) {
      const error = urlParams.get('auth_error');
      addLog(`Authentication failed: ${error}`, 'error');
      window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Check if already authenticated
    try {
      const response = await fetch('/auth/status');
      if (response.ok) {
        const data = await response.json();

        if (data.credentials_path) {
          $credentialsPath = data.credentials_path;
        }

        if (data.authenticated) {
          $isAuthenticated = true;
          addLog('Already authenticated with Gmail', 'success');
          showUploadSection = false;
        }
      }
    } catch (error) {
      console.error('Error checking auth status:', error);
    }
  }

  async function refreshAuthStatus() {
    try {
      const response = await fetch('/auth/status');
      if (response.ok) {
        const data = await response.json();
        if (data.credentials_path) {
          $credentialsPath = data.credentials_path;
        }
      }
    } catch (error) {
      console.error('Error refreshing auth status:', error);
    }
  }

  async function handleFile(file) {
    if (!file) return;

    try {
      const text = await file.text();
      const json = JSON.parse(text);

      // Basic validation
      if (!json.installed && !json.web) {
        throw new Error('Invalid credentials file format');
      }

      $uploadedCredentials = json;
      authBtnDisabled = false;
      uploadSuccess = true;

      addLog('Credentials file uploaded successfully', 'success');
    } catch (error) {
      addLog(`Invalid credentials file: ${error.message}`, 'error');
    }
  }

  function handleFileInput(event) {
    const file = event.target.files[0];
    handleFile(file);
  }

  function handleDragOver(event) {
    event.preventDefault();
    dropZoneHighlight = true;
  }

  function handleDragLeave(event) {
    event.preventDefault();
    dropZoneHighlight = false;
  }

  function handleDrop(event) {
    event.preventDefault();
    dropZoneHighlight = false;

    const file = event.dataTransfer.files[0];
    if (file && file.type === 'application/json') {
      handleFile(file);
    } else {
      addLog('Please upload a valid JSON file', 'error');
    }
  }

  async function authenticate() {
    if (!$uploadedCredentials) {
      addLog('Please upload credentials.json first', 'error');
      return;
    }

    authBtnDisabled = true;
    authBtnText = 'Authenticating...';

    try {
      const response = await fetch('/auth/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify($uploadedCredentials)
      });

      if (response.ok) {
        const result = await response.json();

        if (result.auth_url) {
          if (result.credentials_path) {
            $credentialsPath = result.credentials_path;
          }
          addLog('Redirecting to Google for authentication...', 'info');
          window.location.href = result.auth_url;
        } else if (result.status === 'authenticated') {
          $isAuthenticated = true;
          addLog('Successfully authenticated with Gmail', 'success');

          if (result.credentials_path) {
            $credentialsPath = result.credentials_path;
          }

          showUploadSection = false;
        }
      } else {
        const errorText = await response.text();
        try {
          const error = JSON.parse(errorText);
          throw new Error(error.detail || 'Authentication failed');
        } catch (e) {
          throw new Error(`Authentication failed: ${response.status} ${response.statusText}`);
        }
      }
    } catch (error) {
      addLog(`Error: ${error.message}`, 'error');
    } finally {
      authBtnDisabled = false;
      authBtnText = 'Connect Gmail';
    }
  }

  function showCredentialsUpload() {
    showUploadSection = true;
    $isAuthenticated = false;
    $uploadedCredentials = null;
    authBtnDisabled = true;
    uploadSuccess = false;
    addLog('Ready to upload new credentials file', 'info');
  }

  // Check auth status on mount
  import { onMount } from 'svelte';
  onMount(() => {
    checkAuthStatus();
  });
</script>

<div class="bg-white rounded-2xl shadow-xl shadow-gray-200/50 p-8 border border-gray-100/50 hover:shadow-2xl transition-shadow duration-300">
  <div class="flex items-center justify-between mb-6">
    <div class="flex-1">
      <h2 class="text-2xl font-bold text-gray-900 mb-2">Authentication Status</h2>
      <p class="text-gray-600" class:text-green-600={$isAuthenticated} class:font-semibold={$isAuthenticated}>
        {$isAuthenticated ? 'Connected to Gmail' : 'Not connected to Gmail'}
      </p>
      {#if $credentialsPath}
        <p class="text-sm text-gray-500 mt-1">
          Using credentials: <span class="font-mono text-xs break-all">{$credentialsPath}</span>
        </p>
      {/if}
    </div>
    {#if $isAuthenticated}
      <div>
        <span class="text-green-600 font-semibold">✓ Connected</span>
      </div>
    {/if}
  </div>

  <!-- Change Credentials Button -->
  {#if $isAuthenticated}
    <div class="mb-3">
      <button
        on:click={showCredentialsUpload}
        class="px-4 py-2 bg-gray-500 hover:bg-gray-600 text-white text-sm rounded"
      >
        Change Credentials File
      </button>
    </div>
  {/if}

  <!-- Credentials Upload Section -->
  {#if showUploadSection && !$isAuthenticated}
    <div>
      <div
        role="button"
        tabindex="0"
        class="border-2 border-dashed rounded-lg p-6 text-center hover:border-blue-400 transition-colors"
        class:border-gray-300={!dropZoneHighlight && !uploadSuccess}
        class:border-blue-400={dropZoneHighlight}
        class:bg-blue-50={dropZoneHighlight}
        class:border-green-400={uploadSuccess}
        class:bg-green-50={uploadSuccess}
        on:dragover={handleDragOver}
        on:dragleave={handleDragLeave}
        on:drop={handleDrop}
      >
        <svg class="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
          <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        {#if uploadSuccess}
          <p class="mt-2 text-sm">
            <span class="text-green-600 font-semibold">✓ credentials.json uploaded</span><br>
            <span class="text-xs text-gray-500">Ready to connect</span>
          </p>
        {:else}
          <p class="mt-2 text-sm text-gray-600">
            <label for="file-upload" class="cursor-pointer">
              <span class="text-blue-600 hover:underline">Upload credentials.json</span>
              <span class="text-gray-500"> or drag and drop</span>
            </label>
          </p>
          <input
            id="file-upload"
            bind:this={fileInputElement}
            type="file"
            class="hidden"
            accept=".json"
            on:change={handleFileInput}
          >
          <p class="text-xs text-gray-500 mt-1">JSON file only</p>
        {/if}
      </div>

      <button
        on:click={authenticate}
        disabled={authBtnDisabled}
        class="w-full mt-4 bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded disabled:bg-gray-400 disabled:cursor-not-allowed"
      >
        {authBtnText}
      </button>
    </div>

    <!-- Instructions -->
    <div class="mt-4 p-4 bg-gray-50 rounded-lg">
      <h3 class="text-sm font-semibold text-gray-800 mb-2">How to get your credentials.json:</h3>
      <ol class="text-sm text-gray-600 space-y-1 list-decimal list-inside">
        <li>Go to <a href="https://console.cloud.google.com/" target="_blank" class="text-blue-600 hover:underline">Google Cloud Console</a></li>
        <li>Create a new project or select existing one</li>
        <li>Enable Gmail API in "APIs & Services"</li>
        <li>Go to "Credentials" → "Create Credentials" → "OAuth client ID"</li>
        <li>Choose "Desktop app" as application type</li>
        <li>Download the credentials as JSON</li>
        <li>Upload the file above</li>
      </ol>
    </div>
  {/if}
</div>
