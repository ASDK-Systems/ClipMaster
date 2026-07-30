```typescript
/**
 * Custom Error Hierarchy for Database Operations
 */

export abstract class DatabaseError extends Error {
  public readonly timestamp: Date;

  constructor(
    message: string,
    public readonly code: string,
    public readonly originalError?: Error | unknown,
    public readonly details?: Record<string, unknown>
  ) {
    super(message);
    this.name = this.constructor.name;
    this.timestamp = new Date();
    Error.captureStackTrace(this, this.constructor);
  }
}

export class ConnectionError extends DatabaseError {
  constructor(message: string, originalError?: Error | unknown, details?: Record<string, unknown>) {
    super(message, 'DB_CONNECTION_ERROR', originalError, details);
  }
}

export class QueryTimeoutError extends DatabaseError {
  constructor(query: string, timeoutMs: number) {
    super(`Query timed out after ${timeoutMs}ms`, 'DB_QUERY_TIMEOUT', undefined, { query, timeoutMs });
  }
}

export class UniqueConstraintViolationError extends DatabaseError {
  constructor(constraint: string, table: string, originalError?: Error | unknown) {
    super(`Unique constraint '${constraint}' violated on table '${table}'`, 'DB_UNIQUE_VIOLATION', originalError, {
      constraint,
      table,
    });
  }
}

export class ForeignKeyViolationError extends DatabaseError {
  constructor(constraint: string, table: string, originalError?: Error | unknown) {
    super(`Foreign key constraint '${constraint}' violated on table '${table}'`, 'DB_FOREIGN_KEY_VIOLATION', originalError, {
      constraint,
      table,
    });
  }
}

export class DeadlockError extends DatabaseError {
  constructor(message: string, originalError?: Error | unknown) {
    super(message, 'DB_DEADLOCK_DETECTED', originalError);
  }
}

export class ConcurrentModificationError extends DatabaseError {
  constructor(entityName: string, id: string | number, currentVersion: number) {
    super(
      `Concurrent modification detected for ${entityName} [id: ${id}, expected version: ${currentVersion}]`,
      'DB_CONCURRENT_MODIFICATION',
      undefined,
      { entityName, id, currentVersion }
    );
  }
}

export class TransactionError extends DatabaseError {
  constructor(message: string, originalError?: Error | unknown) {
    super(message, 'DB_TRANSACTION_ERROR', originalError);
  }
}

export class MigrationError extends DatabaseError {
  constructor(message: string, originalError?: Error | unknown) {
    super(message, 'DB_MIGRATION_ERROR', originalError);
  }
}
```