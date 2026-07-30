```typescript
import { FilterCondition, SortOptions, OffsetPaginationOptions, CursorPaginationOptions } from '../types/database.types';

export interface BuiltQuery {
  sql: string;
  params: unknown[];
}

export class QueryBuilder {
  private table: string;
  private selectFields: string[] = ['*'];
  private conditions: FilterCondition[] = [];
  private sortRules: SortOptions[] = [];
  private offsetPagination?: OffsetPaginationOptions;
  private cursorPagination?: CursorPaginationOptions;
  private parameterIndex = 1;

  constructor(table: string) {
    this.table = table;
  }

  public static table(table: string): QueryBuilder {
    return new QueryBuilder(table);
  }

  public select(fields: string[]): this {
    this.selectFields = fields;
    return this;
  }

  public where(field: string, operator: FilterCondition['operator'], value?: unknown): this {
    this.conditions.push({ field, operator, value });
    return this;
  }

  public orderBy(field: string, direction: 'ASC' | 'DESC' = 'ASC'): this {
    this.sortRules.push({ field, direction });
    return this;
  }

  public paginateOffset(page: number, limit: number): this {
    this.offsetPagination = { page, limit };
    return this;
  }

  public paginateCursor(limit: number, cursor?: string): this {
    this.cursorPagination = { limit, cursor };
    return this;
  }

  public buildSelect(): BuiltQuery {
    const params: unknown[] = [];
    const whereClauses: string[] = [];

    for (const cond of this.conditions) {
      if (cond.operator === 'IS NULL' || cond.operator === 'IS NOT NULL') {
        whereClauses.push(`"${cond.field}" ${cond.operator}`);
      } else if (cond.operator === 'IN' || cond.operator === 'NOT IN') {
        if (Array.isArray(cond.value)) {
          const placeholders = cond.value.map(() => `$${this.parameterIndex++}`).join(', ');
          whereClauses.push(`"${cond.field}" ${cond.operator} (${placeholders})`);
          params.push(...cond.value);
        }
      } else if (cond.operator === 'BETWEEN' && Array.isArray(cond.value)) {
        const p1 = `$${this.parameterIndex++}`;
        const p2 = `$${this.parameterIndex++}`;
        whereClauses.push(`"${cond.field}" BETWEEN ${p1} AND ${p2}`);
        params.push(cond.value[0], cond.value[1]);
      } else {
        whereClauses.push(`"${cond.field}" ${cond.operator} $${this.parameterIndex++}`);
        params.push(cond.value);
      }
    }

    // Cursor pagination decoding support
    if (this.cursorPagination?.cursor) {
      const decodedCursor = Buffer.from(this.cursorPagination.cursor, 'base64').toString('utf8');
      const [cursorField, cursorVal] = decodedCursor.split(':');
      if (cursorField && cursorVal) {
        whereClauses.push(`"${cursorField}" > $${this.parameterIndex++}`);
        params.push(cursorVal);
      }
    }

    let sql = `SELECT ${this.selectFields.map((f) => `"${f}"`).join(', ')} FROM "${this.table}"`;

    if (whereClauses.length > 0) {
      sql += ` WHERE ${whereClauses.join(' AND ')}`;
    }

    if (this.sortRules.length > 0) {
      const sortClause = this.sortRules.map((s) => `"${s.field}" ${s.direction}`).join(', ');
      sql += ` ORDER BY ${sortClause}`;
    }

    if (this.offsetPagination) {
      const offset = (this.offsetPagination.page - 1) * this.offsetPagination.limit;
      sql += ` LIMIT $${this.parameterIndex++} OFFSET $${this.parameterIndex++}`;
      params.push(this.offsetPagination.limit, offset);
    } else if (this.cursorPagination) {
      sql += ` LIMIT $${this.parameterIndex++}`;
      params.push(this.cursorPagination.limit + 1); // fetch +1 for hasNext checking
    }

    return { sql, params };
  }

  public static encodeCursor(field: string, value: string | number): string {
    return Buffer.from(`${field}:${value}`).toString('base64');
  }
}
```