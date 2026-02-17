import { writable } from 'svelte/store';

export const excludedDomains = writable([]);          // Domains to exclude from scan
export const useLabelProtection = writable(true);     // Whether custom labels protect threads
export const protectedLabelIds = writable(null);      // Specific labels to protect (null = all)
export const availableLabels = writable([]);           // Labels fetched from Gmail
