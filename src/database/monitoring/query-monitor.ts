```typescript
import { loadDatabaseConfig } from '../config/database.config';

export interface QueryMetric {
  sql: string;
  durationMs: number;
  timestamp: Date;
  success: boolean;
  error?: string;
}

export class QueryMonitor {
  private static metrics: QueryMetric[] = [];
  private static slowQueryThresholdMs = loadDatabaseConfig().slowQueryThresholdMs;

  public static trackQuery(sql: string, durationMs: number, success: boolean, error?: string): void {
    const metric: QueryMetric = {
      sql,
      durationMs,
      timestamp: new Date(),
      success,
      error,
    };

    this.metrics.push(metric);
    if (this.metrics.length > 5000) {
      this.metrics.shift(); // Keep buffer size bounded
    }

    if (durationMs >= this.slowQueryThresholdMs) {
      console.warn(`[SLOW QUERY DETECTED] Duration: ${durationMs}ms | SQL: ${sql}`);
    }
  }

  public static getMetricsSummary(): {
    totalQueries: number;
    avgLatencyMs: number;
    p95LatencyMs: number;
    errorRate: number;
  } {
    if (this.metrics.length === 0) {
      return { totalQueries: 0, avgLatencyMs: 0, p95LatencyMs: 0, errorRate: 0 };
    }

    const total = this.metrics.length;
    const errors = this.metrics.filter((m) => !m.success).length;
    const sorted = [...this.metrics].sort((a, b) => a.durationMs - b.durationMs);
    const sum = sorted.reduce((acc, m) => acc + m.durationMs, 0);

    const p95Index = Math.floor(total * 0.95);

    return {
      totalQueries: total,
      avgLatencyMs: Math.round((sum / total) * 100) / 100,
      p95LatencyMs: sorted[p95Index]?.durationMs || 0,
      errorRate: Math.round((errors / total) * 10000) / 100,
    };
  }
}
```