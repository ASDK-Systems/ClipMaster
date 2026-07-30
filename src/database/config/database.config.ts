```typescript
/**
 * Database Configuration Schema and Environment Parser
 */

export interface DatabasePoolConfig {
  min: number;
  max: number;
  idleTimeoutMillis: number;
  connectionTimeoutMillis: number;
  statementTimeoutMillis: number;
}

export interface ReplicaConfig {
  host: string;
  port: number;
  user: string;
  password?: string;
  database: string;
}

export interface CircuitBreakerConfig {
  failureThreshold: number;
  resetTimeoutMs: number;
}

export interface CacheConfig {
  l1MaxEntries: number;
  l1TtlMs: number;
  enableL2: boolean;
  redisUrl?: string;
}

export interface DatabaseConfig {
  primary: {
    host: string;
    port: number;
    user: string;
    password?: string;
    database: string;
    ssl: boolean;
  };
  replicas: ReplicaConfig[];
  pool: DatabasePoolConfig;
  circuitBreaker: CircuitBreakerConfig;
  cache: CacheConfig;
  slowQueryThresholdMs: number;
  maxTransactionRetries: number;
}

export function loadDatabaseConfig(): DatabaseConfig {
  return {
    primary: {
      host: process.env.DB_HOST || 'localhost',
      port: parseInt(process.env.DB_PORT || '5432', 10),
      user: process.env.DB_USER || 'postgres',
      password: process.env.DB_PASSWORD || 'postgres',
      database: process.env.DB_NAME || 'app_db',
      ssl: process.env.DB_SSL === 'true',
    },
    replicas: process.env.DB_REPLICAS
      ? JSON.parse(process.env.DB_REPLICAS)
      : [],
    pool: {
      min: parseInt(process.env.DB_POOL_MIN || '5', 10),
      max: parseInt(process.env.DB_POOL_MAX || '20', 10),
      idleTimeoutMillis: parseInt(process.env.DB_IDLE_TIMEOUT || '30000', 10),
      connectionTimeoutMillis: parseInt(process.env.DB_CONN_TIMEOUT || '5000', 10),
      statementTimeoutMillis: parseInt(process.env.DB_STATEMENT_TIMEOUT || '10000', 10),
    },
    circuitBreaker: {
      failureThreshold: parseInt(process.env.DB_CB_FAILURE_THRESHOLD || '5', 10),
      resetTimeoutMs: parseInt(process.env.DB_CB_RESET_TIMEOUT || '15000', 10),
    },
    cache: {
      l1MaxEntries: parseInt(process.env.DB_CACHE_L1_MAX || '1000', 10),
      l1TtlMs: parseInt(process.env.DB_CACHE_L1_TTL || '60000', 10),
      enableL2: process.env.DB_CACHE_L2_ENABLE === 'true',
      redisUrl: process.env.REDIS_URL,
    },
    slowQueryThresholdMs: parseInt(process.env.DB_SLOW_QUERY_THRESHOLD || '200', 10),
    maxTransactionRetries: parseInt(process.env.DB_TX_MAX_RETRIES || '3', 10),
  };
}
```