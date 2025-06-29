import aiosqlite

class AsyncSQLiteClient:
    def __init__(self, db_name):
        self.db_name = db_name
        self.conn = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_name)
        # Включаем возврат строк в виде словарей (опционально)
        self.conn.row_factory = aiosqlite.Row

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def execute(self, sql, params=()):
        async with self.conn.execute(sql, params) as cursor:
            await self.conn.commit()
            return await cursor.fetchall()

    async def execute_no_return(self, sql, params=()):
        await self.conn.execute(sql, params)
        await self.conn.commit()

    async def execute_insert(self, sql, params=()):
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cursor.lastrowid

    async def execute_update(self, sql, params=()):
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cursor.rowcount

    async def execute_delete(self, sql, params=()):
        cursor = await self.conn.execute(sql, params)
        await self.conn.commit()
        return cursor.rowcount

    async def execute_select(self, sql, params=()):
        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchall()

    async def execute_select_one(self, sql, params=()):
        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

# import asyncio

# async def main():
#     db = AsyncSQLiteClient("test.db")
#     await db.connect()
#     await db.execute(
#         "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)"
#     )
#     user_id = await db.execute_insert("INSERT INTO users (name) VALUES (?)", ["Иван"])
#     print("Inserted user id:", user_id)
#     users = await db.execute_select("SELECT * FROM users")
#     print("All users:", users)
#     await db.close()

# asyncio.run(main())
