import { writable } from 'svelte/store';
import { progressVisible } from './progressStore.js';
import { clearLogs } from './progressStore.js';
import { resultsVisible, resultsData } from './resultsStore.js';

export const domainsVisible = writable(false);

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
