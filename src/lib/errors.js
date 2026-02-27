/**
 * Centralized error message extraction
 */

/**
 * Extract a human-readable message from various error shapes.
 *
 * Handles:
 *  - Error objects (error.message)
 *  - Google API error responses (error.result.error.message)
 *  - Plain strings
 *  - Anything else (String coercion)
 *
 * @param {*} error
 * @returns {string}
 */
export function getErrorMessage(error) {
  if (!error) return 'Unknown error';

  // Google API error response shape
  if (error.result?.error?.message) {
    return error.result.error.message;
  }

  // Standard Error object
  if (error instanceof Error) {
    return error.message;
  }

  // Already a string
  if (typeof error === 'string') {
    return error;
  }

  // Fallback
  return String(error);
}
