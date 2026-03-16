/**
 * Run an async function over an array with bounded concurrency.
 *
 * Workers pull items from a shared index so no item is processed twice
 * (index++ is atomic in single-threaded JS).
 */
export async function asyncPool(items, concurrency, fn) {
  const results = [];
  let index = 0;

  async function worker() {
    while (index < items.length) {
      const i = index++;
      results[i] = await fn(items[i], i);
    }
  }

  const workers = Array.from({ length: Math.min(concurrency, items.length) }, () => worker());
  await Promise.all(workers);
  return results;
}
