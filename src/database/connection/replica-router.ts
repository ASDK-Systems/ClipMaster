```typescript
import { ConnectionPool } from './connection-pool';
import { DatabaseConfig, loadDatabaseConfig } from '../config/database.config';
import { DatabaseClient } from '../types/database.types';

export class ReplicaRouter implements DatabaseClient {
  private primaryPool: ConnectionPool;
  private replicaPools: ConnectionPool[] = [];
  private rrIndex = 0;

  constructor(config?: DatabaseConfig) {
    const loaded = config || loadDatabaseConfig();
    this.primaryPool = ConnectionPool.getInstance(loaded);

    // Initialize replica connection pools if defined
    if (loaded.replicas && loaded.replicas.length > 0) {
      loaded.replicas.forEach((rep) => {
        this.replicaPools.push(
          ConnectionPool.getInstance({
            ...loaded,
            primary: rep,
            replicas: [],
          })
        );
      });
    }
  }

  public async query<T = unknown>(sql: string, params: unknown[] = [], useReplica = true): Promise<T[]> {
    if (useReplica && this.replicaPools.length > 0) {
      const pool = this.getNextReplica();
      try {
        return await pool.query<T>(sql, params);
      } catch (err) {
        // Degrade back to primary on replica error
        return this.primaryPool.query<T>(sql, params);
      }
    }
    return this.primaryPool.query<T>(sql, params);
  }

  public async execute(sql: string, params: unknown[] = []): Promise<{ rowsAffected: number }> {
    // Write operations always route to primary
    return this.primaryPool.execute(sql, params);
  }

  private getNextReplica(): ConnectionPool {
    const pool = this.replicaPools[this.rrIndex];
    this.rrIndex = (this.rrIndex + 1) % this.replicaPools.length;
    return pool;
  }
}
```