```typescript
/**
 * Core Database Generic Interfaces & Types
 */

export interface BaseEntity {
  id: string;
  createdAt: Date;
  updatedAt: Date;
  version: number;
  deletedAt?: Date | null;
}

export type QueryOperator =
  | '='
  | '!='
  | '>'
  | '>='
  | '<'
  | '<='
  | 'IN'
  | 'NOT IN'
  | 'LIKE'
  | 'ILIKE'
  | 'IS NULL'
  | 'IS NOT NULL'
  | 'BETWEEN';

export interface FilterCondition {
  field: string;
  operator: QueryOperator;
  value?: unknown;
}

export interface SortOptions {
  field: string;
  direction: 'ASC' | 'DESC';
}

export interface OffsetPaginationOptions {
  page: number;
  limit: number;
}

export interface CursorPaginationOptions {
  cursor?: string;
  limit: number;
  direction?: 'forward' | 'backward';
}

export interface PaginatedResult<T> {
  data: T[];
  total: number;
  page?: number;
  totalPages?: number;
  nextCursor?: string;
  hasMore: boolean;
}

export interface QueryOptions {
  filters?: FilterCondition[];
  sort?: SortOptions[];
  pagination?: OffsetPaginationOptions | CursorPaginationOptions;
  includeDeleted?: boolean;
  useReplica?: boolean;
  cacheTtlMs?: number;
}

export interface DatabaseClient {
  query<T = unknown>(sql: string, params?: unknown[]): Promise<T[]>;
  execute(sql: string, params?: unknown[]): Promise<{ rowsAffected: number }>;
}

export interface TransactionContext extends DatabaseClient {
  id: string;
  savepoint(name: string): Promise<void>;
  rollbackToSavepoint(name: string): Promise<void>;
  releaseSavepoint(name: string): Promise<void>;
}

export interface IRepository<T extends BaseEntity> {
  findById(id: string, options?: { useReplica?: boolean }): Promise<T | null>;
  findMany(options?: QueryOptions): Promise<PaginatedResult<T>>;
  create(entity: Omit<T, 'id' | 'createdAt' | 'updatedAt' | 'version'>): Promise<T>;
  update(id: string, patch: Partial<T>, currentVersion?: number): Promise<T>;
  delete(id: string, hardDelete?: boolean): Promise<boolean>;
  findByIds(ids: string[]): Promise<Map<string, T>>;
}
```