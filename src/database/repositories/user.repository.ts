```typescript
import { BaseRepository } from './base.repository';
import { BaseEntity, DatabaseClient } from '../types/database.types';

export interface UserEntity extends BaseEntity {
  email: string;
  name: string;
  role: 'ADMIN' | 'USER' | 'AUDITOR';
  metadata: Record<string, unknown>;
  isVerified: boolean;
}

export class UserRepository extends BaseRepository<UserEntity> {
  constructor(client: DatabaseClient) {
    super('users', client);
  }

  public async findByEmail(email: string): Promise<UserEntity | null> {
    const cacheKey = `${this.tableName}:email:${email}`;
    return this.cache.getOrFetch(cacheKey, async () => {
      const sql = `SELECT * FROM "${this.tableName}" WHERE "email" = $1 AND "deletedAt" IS NULL LIMIT 1`;
      const rows = await this.client.query<UserEntity>(sql, [email.toLowerCase()]);
      return rows.length > 0 ? rows[0] : null;
    });
  }

  public async updateRole(userId: string, newRole: UserEntity['role']): Promise<UserEntity> {
    return this.update(userId, { role: newRole });
  }

  public async searchByMetadataJSON(key: string, value: unknown): Promise<UserEntity[]> {
    const sql = `SELECT * FROM "${this.tableName}" WHERE "metadata"->>$1 = $2 AND "deletedAt" IS NULL`;
    return this.client.query<UserEntity>(sql, [key, String(value)]);
  }
}
```