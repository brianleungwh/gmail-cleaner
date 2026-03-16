import { describe, it, expect } from 'vitest';
import { asyncPool } from '../asyncPool.js';

describe('asyncPool', () => {
  it('processes all items and returns results in order', async () => {
    const items = [1, 2, 3, 4, 5];
    const results = await asyncPool(items, 3, async (x) => x * 10);
    expect(results).toEqual([10, 20, 30, 40, 50]);
  });

  it('respects concurrency limit', async () => {
    let active = 0;
    let maxActive = 0;

    const items = Array.from({ length: 20 }, (_, i) => i);
    await asyncPool(items, 3, async () => {
      active++;
      maxActive = Math.max(maxActive, active);
      await new Promise((r) => setTimeout(r, 10));
      active--;
    });

    expect(maxActive).toBeLessThanOrEqual(3);
    expect(maxActive).toBeGreaterThan(1); // actually used concurrency
  });

  it('handles empty array', async () => {
    const results = await asyncPool([], 5, async (x) => x);
    expect(results).toEqual([]);
  });

  it('handles concurrency greater than item count', async () => {
    const items = [1, 2];
    const results = await asyncPool(items, 10, async (x) => x + 1);
    expect(results).toEqual([2, 3]);
  });

  it('propagates errors', async () => {
    const items = [1, 2, 3];
    await expect(
      asyncPool(items, 2, async (x) => {
        if (x === 2) throw new Error('fail');
        return x;
      }),
    ).rejects.toThrow('fail');
  });

  it('passes index as second argument', async () => {
    const items = ['a', 'b', 'c'];
    const results = await asyncPool(items, 2, async (item, i) => `${item}${i}`);
    expect(results).toEqual(['a0', 'b1', 'c2']);
  });
});
