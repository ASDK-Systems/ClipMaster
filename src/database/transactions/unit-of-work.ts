```typescript
import { ConnectionPool } from '../connection/connection-pool';
import { TransactionContext, DatabaseClient } from '../types/database.types';
import { DeadlockError, TransactionError } from '../errors/database.error';

export class UnitOfWork {
  private pool: ConnectionPool;

  constructor(pool?: ConnectionPool) {
    this.pool = pool || ConnectionPool.getInstance();
  }

  public async executeTransaction<T>(
    work: (tx: TransactionContext) => Promise<T>,
    maxRetries = 3
  ): Promise<T> {
    let attempt = 0;
    while (attempt <= maxRetries) {
      const tx = await this.createTransactionContext();
      try {
        await tx.execute('BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED;');
        const result = await work(tx);
        await tx.execute('COMMIT;');
        return result;
      } catch (error: any) {
        await tx.execute('ROLLBACK;').catch(() => {});
        
        const isDeadlockOrSerialization =
          error?.code === '40P01' || error?.code === '40001' || error instanceof DeadlockError;

        if (isDeadlockOrSerialization && attempt < maxRetries) {
          attempt++;
          const backoff = Math.pow(2, attempt) * 50 + Math.random() * 25;
          await new Promise((r) => setTimeout(r, backoff));
          continue;
        }

        throw new TransactionError(
          `Transaction failed on attempt ${attempt + 1}: ${error.message}`,
          error
        );
      }
    }
    throw new TransactionError(`Transaction retries exhausted (${maxRetries} attempts)`);
  }

  private async createTransactionContext(): Promise<TransactionContext> {
    const txId = `tx_${Math.random().toString(36).substring(2, 9)}`;
    const pool = this.pool;

    return {
      id: txId,
      async query<T = unknown>(sql: string, params?: unknown[]): Promise<T[]> {
        return pool.query<T>(sql, params);
      },
      async execute(sql: string, params?: unknown[]): Promise<{ rowsAffected: number }> {
        return pool.execute(sql, params);
      },
      async savepoint(name: string): Promise<void> {
        await pool.execute(`SAVEPOINT ${name};`);
      },
      async rollbackToSavepoint(name: string): Promise<void> {
        await pool.execute(`ROLLBACK TO SAVEPOINT ${name};`);
      },
      async releaseSavepoint(name: string): Promise<void> {
        await pool.execute(`RELEASE SAVEPOINT ${name};`);
      },
    };
  }
}
```