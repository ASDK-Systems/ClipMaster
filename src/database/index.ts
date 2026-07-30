```typescript
/**
 * Database Module Barrel Export
 */

export * from './config/database.config';
export * from './types/database.types';
export * from './errors/database.error';
export * from './connection/connection-pool';
export * from './connection/replica-router';
export * from './query-builder/query-builder';
export * from './transactions/unit-of-work';
export * from './cache/cache-manager';
export * from './repositories/base.repository';
export * from './repositories/user.repository';
export * from './repositories/order.repository';
export * from './migrations/migration-runner';
export * from './monitoring/query-monitor';
```