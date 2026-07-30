```typescript
import { CacheConfig, loadDatabaseConfig } from '../config/database.config';

export class CacheManager {
  private static instance: CacheManager;
  private l1Cache: Map<string, { value: unknown; expiresAt: number }> = new Map();
  private inflightRequests: Map<string, Promise<unknown>> = new Map();
  private config: CacheConfig;

  private constructor(config?: CacheConfig) {
    this.config = config?.l1MaxEntries ? config : loadDatabaseConfig().cache;
  }

  public static getInstance(config?: CacheConfig): CacheManager {
    if (!CacheManager.instance) {
      CacheManager.instance = new CacheManager(config);
    }
    return CacheManager.instance;
  }

  /**
   * Prevents Cache Stampede / Thundering Herd Problem via Single-Flight pattern
   */
  public async getOrFetch<T>(
    key: string,
    fetchFn: () => Promise<T>,
    ttlMs?: number
  ): Promise<T> {
    const now = Date.now();
    const cached = this.l1Cache.get(key);

    if (cached && cached.expiresAt > now) {
      return cached.value as T;
    }

    // Single-Flight Request Coalescing
    if (this.inflightRequests.has(key)) {
      return this.inflightRequests.get(key) as Promise<T>;
    }

    const fetchPromise = (async () => {
      try {
        const result = await fetchFn();
        this.set(key, result, ttlMs || this.config.l1TtlMs);
        return result;
      } finally {
        this.inflightRequests.delete(key);
      }
    })();

    this.inflightRequests.set(key, fetchPromise);
    return fetchPromise;
  }

  public set(key: string, value: unknown, ttlMs: number): void {
    if (this.l1Cache.size >= this.config.l1MaxEntries) {
      // LRU Eviction heuristic
      const firstKey = this.l1Cache.keys().next().value;
      if (firstKey) this.l1Cache.delete(firstKey);
    }
    this.l1Cache.set(key, {
      value,
      expiresAt: Date.now() + ttlMs,
    });
  }

  public invalidate(keyOrPrefix: string): void {
    for (const key of this.l1Cache.keys()) {
      if (key.startsWith(keyOrPrefix)) {
        this.l1Cache.delete(key);
      }
    }
  }

  public clear(): void {
    this.l1Cache.clear();
    this.inflightRequests.clear();
  }
}
```