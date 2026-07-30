```typescript
import { BaseRepository } from './base.repository';
import { BaseEntity, TransactionContext } from '../types/database.types';
import { UnitOfWork } from '../transactions/unit-of-work';

export interface OrderItem {
  productId: string;
  quantity: number;
  price: number;
}

export interface OrderEntity extends BaseEntity {
  userId: string;
  items: OrderItem[];
  totalAmount: number;
  status: 'PENDING' | 'PAID' | 'CANCELLED' | 'SHIPPED';
  idempotencyKey: string;
}

export class OrderRepository extends BaseRepository<OrderEntity> {
  private uow: UnitOfWork;

  constructor(client: any) {
    super('orders', client);
    this.uow = new UnitOfWork();
  }

  public async createOrderWithInventoryCheck(
    orderData: Omit<OrderEntity, 'id' | 'createdAt' | 'updatedAt' | 'version'>
  ): Promise<OrderEntity> {
    return this.uow.executeTransaction(async (tx: TransactionContext) => {
      // 1. Check Idempotency Key
      const existing = await tx.query<OrderEntity>(
        `SELECT * FROM "orders" WHERE "idempotencyKey" = $1 LIMIT 1`,
        [orderData.idempotencyKey]
      );
      if (existing.length > 0) {
        return existing[0];
      }

      // 2. Reserve Stock with Row-Level Locking (SELECT ... FOR UPDATE)
      for (const item of orderData.items) {
        const stockRows = await tx.query<{ stock: number }>(
          `SELECT stock FROM "products" WHERE "id" = $1 FOR UPDATE`,
          [item.productId]
        );
        if (stockRows.length === 0 || stockRows[0].stock < item.quantity) {
          throw new Error(`Insufficient inventory for product: ${item.productId}`);
        }

        await tx.execute(
          `UPDATE "products" SET "stock" = "stock" - $1 WHERE "id" = $2`,
          [item.quantity, item.productId]
        );
      }

      // 3. Create Order
      const newOrder: Omit<OrderEntity, 'id' | 'createdAt' | 'updatedAt' | 'version'> = {
        ...orderData,
        status: 'PENDING',
      };

      const orderRepo = new OrderRepository(tx);
      return orderRepo.create(newOrder);
    });
  }
}
```