import asyncio
from sqlalchemy import text
from app.db import engine

async def do_alter():
    async with engine.begin() as c:
        try:
            await c.execute(text('ALTER TABLE chat_logs ADD COLUMN session_id VARCHAR(36)'))
            print("Altered")
        except Exception as e:
            print("Error or already altered:", e)

if __name__ == '__main__':
    asyncio.run(do_alter())
