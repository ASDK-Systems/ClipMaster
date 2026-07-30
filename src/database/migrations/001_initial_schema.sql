```sql
-- Production PostgreSQL DDL Schema Migration

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users Table
CREATE TABLE IF NOT EXISTS "users" (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "email" VARCHAR(255) UNIQUE NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "role" VARCHAR(50) NOT NULL DEFAULT 'USER',
    "metadata" JSONB DEFAULT '{}'::jsonb,
    "isVerified" BOOLEAN NOT NULL DEFAULT FALSE,
    "version" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMPTZ DEFAULT NULL
);

-- Indices for performance optimization
CREATE INDEX IF NOT EXISTS "idx_users_email" ON "users" ("email") WHERE "deletedAt" IS NULL;
CREATE INDEX IF NOT EXISTS "idx_users_metadata_gin" ON "users" USING GIN ("metadata");

-- Products Table
CREATE TABLE IF NOT EXISTS "products" (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "name" VARCHAR(255) NOT NULL,
    "stock" INTEGER NOT NULL DEFAULT 0 CHECK ("stock" >= 0),
    "price" NUMERIC(12, 2) NOT NULL CHECK ("price" >= 0),
    "version" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMPTZ DEFAULT NULL
);

-- Orders Table
CREATE TABLE IF NOT EXISTS "orders" (
    "id" UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "userId" UUID NOT NULL REFERENCES "users"("id") ON DELETE RESTRICT,
    "items" JSONB NOT NULL,
    "totalAmount" NUMERIC(12, 2) NOT NULL,
    "status" VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    "idempotencyKey" VARCHAR(255) UNIQUE NOT NULL,
    "version" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS "idx_orders_user_status" ON "orders" ("userId", "status");
CREATE INDEX IF NOT EXISTS "idx_orders_idempotency" ON "orders" ("idempotencyKey");

-- Trigger for Auto-Updating updatedAt Column
CREATE OR REPLACE FUNCTION update_timestamp_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW."updatedAt" = CURRENT_TIMESTAMP;
   RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_modtime BEFORE UPDATE ON "users" FOR EACH ROW EXECUTE PROCEDURE update_timestamp_column();
CREATE TRIGGER update_products_modtime BEFORE UPDATE ON "products" FOR EACH ROW EXECUTE PROCEDURE update_timestamp_column();
CREATE TRIGGER update_orders_modtime BEFORE UPDATE ON "orders" FOR EACH ROW EXECUTE PROCEDURE update_timestamp_column();
```