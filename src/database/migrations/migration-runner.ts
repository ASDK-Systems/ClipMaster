```typescript
import { DatabaseClient } from '../types/database.types';
import { MigrationError } from '../errors/database.error';

export interface MigrationScript {
  id: string;
  name: string;
  upSql: string;
  downSql: string;
  checksum: string;
}

export class MigrationRunner {
  private client: DatabaseClient;

  constructor(client: DatabaseClient) {
    this.client = client;
  }

  public async initializeMigrationTable(): Promise<void> {
    const sql = `
      CREATE TABLE IF NOT EXISTS "_schema_migrations" (
        "id" VARCHAR(255) PRIMARY KEY,
        "name" VARCHAR(255) NOT NULL,
        "checksum" VARCHAR(64) NOT NULL,
        "executedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
      );
    `;
    await this.client.execute(sql);
  }

  public async runMigrations(migrations: MigrationScript[]): Promise<void> {
    await this.initializeMigrationTable();

    // Acquire PostgreSQL Advisory Lock to prevent concurrent instance migrations
    const LOCK_ID = 987654321;
    await this.client.execute(`SELECT pg_advisory_lock(${LOCK_ID});`);

    try {
      const executed = await this.client.query<{ id: string; checksum: string }>(
        `SELECT "id", "checksum" FROM "_schema_migrations"`
      );
      const executedMap = new Map(executed.map((m) => [m.id, m.checksum]));

      for (const migration of migrations) {
        if (executedMap.has(migration.id)) {
          const prevChecksum = executedMap.get(migration.id);
          if (prevChecksum !== migration.checksum) {
            throw new MigrationError(
              `Migration checksum mismatch for ${migration.name}! Applied: ${prevChecksum}, Existing: ${migration.checksum}`
            );
          }
          continue;
        }

        console.log(`Executing migration: ${migration.name}`);
        await this.client.execute(migration.upSql);
        await this.client.execute(
          `INSERT INTO "_schema_migrations" ("id", "name", "checksum") VALUES ($1, $2, $3)`,
          [migration.id, migration.name, migration.checksum]
        );
      }
    } finally {
      await this.client.execute(`SELECT pg_advisory_unlock(${LOCK_ID});`);
    }
  }
}
```