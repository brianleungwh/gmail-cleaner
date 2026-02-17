/**
 * Gmail API wrapper using gapi.client.gmail
 *
 * All functions use the access token managed internally by gapi.client
 * (set automatically by GIS after authentication).
 */

import { requestAccessToken } from './auth.js';

/**
 * Wraps an API call with automatic token refresh on 401 errors.
 */
async function withTokenRefresh(apiCall) {
  try {
    const response = await apiCall();
    return response.result;
  } catch (err) {
    if (err.status === 401) {
      await requestAccessToken();
      const response = await apiCall();
      return response.result;
    }
    throw err;
  }
}

/**
 * Get inbox label info (includes threadsTotal for progress reporting).
 */
export function getInboxInfo() {
  return withTokenRefresh(() =>
    gapi.client.gmail.users.labels.get({
      userId: 'me',
      id: 'INBOX',
    })
  );
}

/**
 * List all user labels.
 */
export function listLabels() {
  return withTokenRefresh(() =>
    gapi.client.gmail.users.labels.list({
      userId: 'me',
    })
  );
}

/**
 * List threads with pagination support.
 */
export function listThreads({ maxResults = 100, pageToken = null, q = 'in:inbox' } = {}) {
  const params = { userId: 'me', maxResults, q };
  if (pageToken) params.pageToken = pageToken;

  return withTokenRefresh(() =>
    gapi.client.gmail.users.threads.list(params)
  );
}

/**
 * Get a single thread with metadata.
 */
export function getThread(threadId, { format = 'metadata', metadataHeaders = ['From', 'Subject'] } = {}) {
  return withTokenRefresh(() =>
    gapi.client.gmail.users.threads.get({
      userId: 'me',
      id: threadId,
      format,
      metadataHeaders,
    })
  );
}

/**
 * Move a thread to trash.
 */
export function trashThread(threadId) {
  return withTokenRefresh(() =>
    gapi.client.gmail.users.threads.trash({
      userId: 'me',
      id: threadId,
    })
  );
}
