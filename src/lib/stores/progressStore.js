import { writable } from 'svelte/store';
import { MAX_LOG_MESSAGES } from '../constants.js';

export const progressVisible = writable(false);
export const progressPercent = writable(0);
export const progressText = writable('Waiting...');
export const progressIndeterminate = writable(false);
export const logs = writable([]);

export function addLog(message, type = 'info') {
  const timestamp = new Date().toLocaleTimeString();
  logs.update(currentLogs => {
    const newLogs = [...currentLogs, { timestamp, message, type }];
    return newLogs.slice(-MAX_LOG_MESSAGES);
  });
}

export function clearLogs() {
  logs.set([]);
}
