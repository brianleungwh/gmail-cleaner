import { writable, derived } from 'svelte/store';

// Authentication state
export const isAuthenticated = writable(false);
export const credentialsPath = writable(null);
export const uploadedCredentials = writable(null);

// Collection state
export const isCollecting = writable(false);
export const domains = writable({});
export const totalThreads = writable(0);

// Cleanup state
export const isCleaning = writable(false);
export const selectedDomains = writable(new Set());
export const expandedDomains = writable(new Set());

// Progress state
export const progressVisible = writable(false);
export const progressPercent = writable(0);
export const progressText = writable('Waiting...');
export const progressIndeterminate = writable(false);
export const logs = writable([]);

// Results state
export const resultsVisible = writable(false);
export const resultsData = writable(null);

// Sections visibility
export const domainsVisible = writable(false);

// Derived stores
export const hasCollectedDomains = derived(domains, $domains => Object.keys($domains).length > 0);
export const hasSelection = derived(selectedDomains, $selectedDomains => $selectedDomains.size > 0);
export const selectedCount = derived(selectedDomains, $selectedDomains => $selectedDomains.size);

// Helper functions
export function addLog(message, type = 'info') {
  const timestamp = new Date().toLocaleTimeString();
  logs.update(currentLogs => {
    const newLogs = [...currentLogs, { timestamp, message, type }];
    // Keep only last 200 messages
    return newLogs.slice(-200);
  });
}

export function clearLogs() {
  logs.set([]);
}

export function showProgress() {
  progressVisible.set(true);
  domainsVisible.set(false);
  resultsVisible.set(false);
  clearLogs();
}

export function hideProgress() {
  progressVisible.set(false);
}

export function showDomains() {
  domainsVisible.set(true);
  progressVisible.set(false);
  resultsVisible.set(false);
}

export function showResults(data) {
  resultsVisible.set(true);
  domainsVisible.set(false);
  progressVisible.set(false);
  resultsData.set(data);
}
