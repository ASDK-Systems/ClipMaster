```typescript
import { BaseEntity, IRepository, PaginatedResult, QueryOptions } from '../types/database.types';
import { DatabaseClient } from '../types/database.types';
import { QueryBuilder } from '../query-builder/query-builder';
import { CacheManager } from '../cache/cache-manager';
import { ConcurrentModificationError } from '../errors/database.error';

export abstract class BaseRepository<T extends BaseEntity> implements IRepository<T> {
  protected tableName: string;
  protected client: DatabaseClient;
  protected cache: CacheManager;

  constructor(tableName: string, client: DatabaseClient) {
    this.tableName = tableName;
    this.client = client;
    this.cache = CacheManager.getInstance();
  }

  public async findById(id: string, options?: { useReplica?: boolean }): Promise<T | null> {
    const cacheKey = `${this.tableName}:${id}`;
    return this.cache.getOrFetch(cacheKey, async () => {
      const qb = QueryBuilder.table(this.tableName)
        .where('id', '=', id)
        .where('deletedAt', 'IS NULL');
      
      const { sql, params } = qb.buildSelect();
      const rows = await this.client.query<T>(sql, params);
      return rows.length > 0 ? rows[0] : null;
    });
  }

  public async findByIds(ids: string[]): Promise<Map<string, T>> {
    if (ids.length === 0) return new Map();
    const uniqueIds = Array.from(new Set(ids));
    
    const qb = QueryBuilder.table(this.tableName)
      .where('id', 'IN', uniqueIds)
      .where('deletedAt', 'IS NULL');
      
    const { sql, params } = qb.buildSelect();
    const rows = await this.client.query<T>(sql, params);

    const map = new Map<string, T>();
    rows.forEach((row) => map.set(row.id, row));
    return map;
  }

  public async findMany(options: QueryOptions = {}): Promise<PaginatedResult<T>> {
    const qb = QueryBuilder.table(this.tableName);

    if (!options.includeDeleted) {
      qb.where('deletedAt', 'IS NULL');
    }

    if (options.filters) {
      options.filters.forEach((f) => qb.where(f.field, f.operator, f.value));
    }

    if (options.sort) {
      options.sort.forEach((s) => qb.orderBy(s.field, s.direction));
    }

    const limit = (options.pagination as any)?.limit || 20;
    const page = (options.pagination as any)?.page || 1;
    qb.paginateOffset(page, limit);

    const { sql, params } = qb.buildSelect();
    const rows = await this.client.query<T>(sql, params);

    // Count query execution
    const countSql = `SELECT COUNT(*) as total FROM "${this.tableName}" WHERE "deletedAt" IS NULL`;
    const countRes = await this.client.query<{ total: string }>(countSql);
    const total = parseInt(countRes[0]?.total || '0', 10);

    return {
      data: rows,
      total,
      page,
      totalPages: Math.ceil(total / limit),
      hasMore: page * limit < total,
    };
  }

  public async create(entity: Omit<T, 'id' | 'createdAt' | 'updatedAt' | 'version'>): Promise<T> {
    const id = `uuid_${Math.random().toString(36).substr(2, 9)}`;
    const now = new Date();
    const newRecord = {
      ...entity,
      id,
      createdAt: now,
      updatedAt: now,
      version: 1,
      deletedAt: null,
    } as unknown as T;

    const keys = Object.keys(newRecord);
    const placeholders = keys.map((_, i) => `$${i + 1}`).join(', ');
    const columns = keys.map((k) => `"${k}"`).join(', ');
    const values = Object.values(newRecord);

    const sql = `INSERT INTO "${this.tableName}" (${columns}) VALUES (${placeholders}) RETURNING *`;
    await this.client.execute(sql, values);

    return newRecord;
  }

  public async update(id: string, patch: Partial<T>, currentVersion?: number): Promise<T> {
    const existing = await this.findById(id);
    if (!existing) {
      throw new Error(`Record with id ${id} not found in ${this.tableName}`);
    }

    if (currentVersion !== undefined && existing.version !== currentVersion) {
      throw new ConcurrentModificationError(this.tableName, id, currentVersion);
    }

    const nextVersion = existing.version + 1;
    const updatedRecord = {
      ...existing,
      ...patch,
      updatedAt: new Date(),
      version: nextVersion,
    };

    const keys = Object.keys(patch).filter((k) => k !== 'id' && k !== 'createdAt');
    keys.push('updatedAt', 'version');

    const setClauses = keys.map((key, i) => `"${key}" = $${i + 1}`).join(', ');
    const params = keys.map((key) => (updatedRecord as any)[key]);
    params.push(id, existing.version);

    const sql = `UPDATE "${this.tableName}" SET ${setClauses} WHERE "id" = $${params.length - 1} AND "version" = $${params.length}`;
    
    const result = await this.client.execute(sql, params);
    if (result.rowsAffected === 0) {
      throw new ConcurrentModificationError(this.tableName, id, existing.version);
    }

    this.cache.invalidate(`${this.tableName}:${id}`);
    return updatedRecord;
  }

  public async delete(id: string, hardDelete = false): Promise<boolean> {
    if (hardDelete) {
      const sql = `DELETE FROM "${this.tableName}" WHERE "id" = $1`;
      const res = await this.client.execute(sql, [id]);
      this.cache.invalidate(`${this.tableName}:${id}`);
      return res.rowsAffected > 0;
    } else {
      const sql = `UPDATE "${this.tableName}" SET "deletedAt" = $1 WHERE "id" = $2 AND "deletedAt" = NULL`;
      const res = await this.client.execute(sql, [new Date(), id]);
      this.cache.invalidate(`${this.tableName}:${id}`);
      return res.rowsAffected > 0;
    }
  }
}
```