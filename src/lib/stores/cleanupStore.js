import { writable, derived } from 'svelte/store';

export const isCleaning = writable(false);
export const selectedDomains = writable(new Set());
export const expandedDomains = writable(new Set());

export const hasSelection = derived(selectedDomains, $selectedDomains => $selectedDomains.size > 0);
export const selectedCount = derived(selectedDomains, $selectedDomains => $selectedDomains.size);
