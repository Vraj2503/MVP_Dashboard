import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()

async def test_db():
    url = os.getenv("APP_DATABASE_URL")
    print(f"Testing URL: {url}")
    try:
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            print("Connection successful! Result:", result.scalar())
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.run(test_db())
